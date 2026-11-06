"""Render measured run facts as a short page for researchers."""

import hashlib
import json
import math
import os
import re
import tempfile
from datetime import date, datetime
from importlib import resources
from pathlib import Path

from jsonschema import Draft202012Validator

from .loader import load_yaml
from .manifest import hash_file


class RunSummaryError(ValueError):
    """A required measured fact is missing or inconsistent."""


def _matches_after_crlf_to_lf(path: Path, expected_hash: str) -> bool:
    """Check whether checkout changed LF bytes to CRLF without loading the file into memory."""
    digest = hashlib.sha256()
    trailing_cr = False
    changed = False
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if trailing_cr:
                chunk = b"\r" + chunk
            trailing_cr = chunk.endswith(b"\r")
            if trailing_cr:
                chunk = chunk[:-1]
            changed |= b"\r\n" in chunk
            digest.update(chunk.replace(b"\r\n", b"\n"))
    if trailing_cr:
        digest.update(b"\r")
    return changed and digest.hexdigest() == expected_hash


def carry_forward_skipped_steps(current: dict, previous: dict | None) -> dict:
    """Keep the last measured time, memory, basis and date for skipped steps."""
    old_steps = {step["name"]: step for step in (previous or {}).get("steps", [])}
    result = {**current, "steps": []}
    for step in current.get("steps", []):
        if step.get("skipped"):
            old = old_steps.get(step.get("name"))
            required = ("elapsed_seconds", "peak_rss_mb", "rss_basis", "measurement_run_date_utc")
            if old is None or any(field not in old for field in required):
                raise RunSummaryError(f"The step '{step.get('name', 'unknown')}' was skipped, but its last measurement is missing. Run that step again before making a run summary.")
            result["steps"].append({**step, **{field: old[field] for field in required}})
        else:
            result["steps"].append(step.copy())
    return result


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunSummaryError(f"This run has no {path.name}. Record it during reproduce, then make the summary again.") from exc
    except (OSError, ValueError) as exc:
        raise RunSummaryError(f"{path.name} could not be read. Fix that run file, then make the summary again.") from exc
    if not isinstance(value, dict):
        raise RunSummaryError(f"{path.name} does not contain a record. Run reproduce again, then retry.")
    return value


def _require(record: dict, key: str, filename: str):
    if not isinstance(record, dict):
        raise RunSummaryError(f"{filename} does not contain a usable {key}. Fix that run file and retry.")
    value = record.get(key)
    if value is None:
        raise RunSummaryError(f"{filename} is missing {key}. Run reproduce again so it records this value, then retry.")
    return value


def _validate_metrics(metrics: dict) -> None:
    schema_file = resources.files("reprokit").joinpath("schemas", "run_metrics.json")
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(metrics))
    if not errors:
        for step in metrics["steps"]:
            if not math.isfinite(step["elapsed_seconds"]) or not math.isfinite(step["peak_rss_mb"]):
                raise RunSummaryError(f"The measurement for step '{step['name']}' is not a finite number. Record its time and memory again, then retry.")
        return
    error = min(errors, key=lambda item: (list(map(str, item.path)), item.message))
    missing = re.search(r"'([^']+)' is a required property", error.message)
    field = missing.group(1) if missing else ".".join(map(str, error.path))
    if len(error.path) > 1 and error.path[0] == "steps" and isinstance(error.path[1], int):
        index = error.path[1]
        name = metrics.get("steps", [{}])[index].get("name", f"number {index + 1}")
        raise RunSummaryError(f"The measurement for step '{name}' is missing or invalid ({field}). Record it in run_metrics.json and run reproduce again.")
    raise RunSummaryError(f"run_metrics.json is missing or has an invalid {field}. Run reproduce again so it records this value.")


def _duration(seconds: float) -> str:
    rounded = round(seconds)
    minutes, remainder = divmod(rounded, 60)
    if minutes and remainder:
        return f"{minutes} minute{'s' if minutes != 1 else ''} {remainder} second{'s' if remainder != 1 else ''}"
    if minutes:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{remainder} second{'s' if remainder != 1 else ''}"


def _month(value: str) -> str:
    day = date.fromisoformat(value)
    return f"{day:%B} {day.year}"


def write_run_summary(manifest_path: Path, report_path: Path, metrics_path: Path, config_path: Path, out_path: Path) -> Path:
    """Write RUN_SUMMARY.md from structured run records; never use prose as data."""
    manifest = _read_json(manifest_path)
    report = _read_json(report_path)
    metrics = _read_json(metrics_path)
    _validate_metrics(metrics)
    config, problems = load_yaml(config_path)
    if problems or not isinstance(config, dict):
        raise RunSummaryError(f"Could not read {config_path.name}. Fix the settings file and retry.")
    try:
        geography = _require(config, "geography", config_path.name)
        period = _require(config, "period", config_path.name)
        start = _month(period["start"])
        end = _month(period["end"])
        rows = _require(_require(report, "stats", report_path.name), "panel_rows", report_path.name)
        version = _require(manifest, "code_version", manifest_path.name)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, RunSummaryError):
            raise
        raise RunSummaryError("A setting or row count is invalid. Fix the structured run files and retry.") from exc
    if not isinstance(rows, int) or rows < 0:
        raise RunSummaryError("The final row count is invalid. Fix run_report.json and retry.")
    if not isinstance(geography, str) or not geography.strip() or not isinstance(version, str) or not version.strip():
        raise RunSummaryError("The geography or code version is missing. Fix the structured run files and retry.")
    root = metrics_path.parent.resolve()
    hashes = []
    for output in metrics["outputs"]:
        target = (root / output["path"]).resolve()
        if target == out_path.resolve() or target.name.lower() == "run_summary.md":
            raise RunSummaryError("The run summary cannot list its own checksum. Remove it from run_metrics.json and retry.")
        if not target.is_relative_to(root) or not target.is_file():
            raise RunSummaryError(f"The checksum for {output['path']} does not match a file from this run. Run reproduce again and retry.")
        if hash_file(target) != output["sha256"]:
            if _matches_after_crlf_to_lf(target, output["sha256"]):
                raise RunSummaryError(f"The line endings in {output['path']} changed, most likely because of Git on Windows. It matches the recorded file after CRLF is converted to LF. Restore the original LF file or run reproduce again, then retry.")
            raise RunSummaryError(f"The checksum for {output['path']} does not match a file from this run. Run reproduce again and retry.")
        try:
            display_path = target.relative_to(config_path.parent.resolve()).as_posix()
        except ValueError:
            display_path = target.as_posix()
        hashes.append(f"| `{display_path}` | `{output['sha256']}` |")
    steps = metrics["steps"]
    measured_now = [step for step in steps if not step["skipped"]]
    total = sum(step["elapsed_seconds"] for step in measured_now)
    window = f"for {start}" if start == end else f"from {start} to {end}"
    lines = [
        "# Run summary",
        "",
        f"This run used the {geography} settings {window}.",
    ]
    if measured_now:
        lines.append(f"It produced {rows:,} row{'s' if rows != 1 else ''}. The work completed in this run took {_duration(total)}.")
    else:
        lines.append(f"It produced {rows:,} row{'s' if rows != 1 else ''}. All steps were already up to date.")
    lines += [
        "", "## Files made", "",
        "A checksum (a fingerprint of the file) helps you compare this output with the original authors' output. File paths start from the folder containing `config.yaml`.",
        "", "| File path | SHA-256 checksum |", "| --- | --- |", *hashes, "",
        "Compare each checksum with the one in the original authors' run summary. If they match, your file copy is identical.",
        "", "## Time and memory", "",
        "| Step | Time | Peak memory |", "| --- | --- | --- |",
    ]
    for step in steps:
        step_memory = f"{step['peak_rss_mb'] / 1024:.1f} GB"
        step_basis = "including child processes" if step["rss_basis"] == "tree" else "for the main process only"
        if step["skipped"]:
            measured = datetime.fromisoformat(step["measurement_run_date_utc"])
            step_time = f"{_duration(step['elapsed_seconds'])} (last measured {measured:%B} {measured.day}, {measured.year}; skipped this run)"
        else:
            step_time = _duration(step["elapsed_seconds"])
        lines.append(f"| {step['name']} | {step_time} | {step_memory} ({step_basis}) |")
    lines += ["", f"Program version used: `{version}`. Use this to check that you ran the same code as the original authors.", ""]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=out_path.parent, delete=False, newline="\n") as stream:
        temp_path = Path(stream.name)
        stream.write("\n".join(lines))
    try:
        os.replace(temp_path, out_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return out_path
