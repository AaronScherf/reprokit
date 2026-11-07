import math
from pathlib import Path

from .loader import load_yaml
from .problems import Problem
from .validate import validate_document

MAX_TEXT = 500
MAX_RECORD_TEXT = 4000
_TYPES = {"number": (int, float), "boolean": (bool,), "string": (str,), "list": (list,)}
_KEEP = {".gitkeep"}


def load_extraction_schema(path: Path) -> tuple[dict | None, list[Problem]]:
    problems = validate_document(path, "extraction_schema")
    if problems:
        return None, problems
    doc, _ = load_yaml(path)
    return doc, []


def _text_length(value) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict):
        return sum(_text_length(v) for v in value.values())
    if isinstance(value, list):
        return sum(_text_length(v) for v in value)
    return 0


def _finite(value) -> bool:
    return not isinstance(value, float) or math.isfinite(value)


def _check_fields(record: dict, schema: dict, path: str) -> list[Problem]:
    problems = []
    declared = schema["fields"]
    for name, value in record["fields"].items():
        where = f"fields.{name}"
        if name not in declared:
            problems.append(Problem(path, where, f"The field '{name}' is not in the extraction schema. Add it to evidence/extraction_schema.yaml or remove it from this record."))
            continue
        kind = declared[name]["type"]
        ok = isinstance(value, _TYPES[kind]) and not (kind == "number" and isinstance(value, bool))
        if not ok:
            problems.append(Problem(path, where, f"The field '{name}' should be a {kind}. Fix the value in this record."))
            continue
        items = value if kind == "list" else [value]
        if kind == "list" and not all(isinstance(v, (str, int, float, bool)) for v in items):
            problems.append(Problem(path, where, f"The field '{name}' must be a flat list of text, numbers or true/false values. Remove nested lists or mappings."))
        elif not all(_finite(v) for v in items):
            problems.append(Problem(path, where, f"The field '{name}' holds nan or inf. Write a finite number, or leave the field out."))
        elif any(isinstance(v, str) and len(v) > MAX_TEXT for v in items):
            problems.append(Problem(path, where, f"The field '{name}' has text longer than {MAX_TEXT} characters. Summarize it in your own words instead of quoting the source."))
    return problems


def _check_record(record: dict, file: Path, known: set) -> list[Problem]:
    path, sid = str(file), record["source_id"]
    if sid != file.stem:
        return [Problem(path, "source_id", f"The filename '{file.stem}' must equal the record's source_id '{sid}'. Rename the file or fix the source_id.")]
    if sid not in known:
        return [Problem(path, "source_id", f"record for unknown source '{sid}'; remove it or add the source to the manifest")]
    return []


def _check_limits(record: dict, path: str) -> list[Problem]:
    problems = []
    if not _finite(record["cost"]["usd"]):
        problems.append(Problem(path, "cost.usd", "The cost holds nan or inf. Write the cost in US dollars as a finite number, such as 0.02."))
    if _text_length(record) > MAX_RECORD_TEXT:
        problems.append(Problem(path, "", f"this record holds more than {MAX_RECORD_TEXT} characters of text; extraction records must stay short summaries, not copied passages"))
    return problems


def load_records(folder: Path, manifest: dict, schema: dict) -> tuple[dict[str, dict], list[Problem]]:
    records, problems, seen = {}, [], set()
    known = {s.get("id") for s in manifest.get("sources", [])}
    files = sorted(f for f in folder.iterdir() if f.is_file()) if folder.is_dir() else []
    for file in files:
        if file.suffix != ".yaml":
            if file.name not in _KEEP:
                problems.append(Problem(str(file), "", f"Extraction records must end in .yaml. Rename '{file.name}' to '{file.stem}.yaml', or move it out of {folder.name}/ if it is not a record."))
            continue
        seen.add(file.stem)
        bad = validate_document(file, "extraction_record")
        if bad:
            problems.extend(bad)
            continue
        record, _ = load_yaml(file)
        found = _check_record(record, file, known) or (_check_limits(record, str(file)) + _check_fields(record, schema, str(file)))
        problems.extend(found)
        if not found:
            records[record["source_id"]] = record
    for source in manifest.get("sources", []):
        if source.get("screening_status") == "included" and source["id"] not in seen:
            problems.append(Problem(str(folder), source["id"], f"The included source '{source['id']}' has no extraction record. Add evidence/extractions/{source['id']}.yaml, or set the source's screening_status to candidate or excluded."))
    return records, problems


def _stale_reasons(sid: str, rec: dict, current_hash, schema: dict | None) -> list[tuple[str, str]]:
    reasons = []
    if rec.get("source_content_hash") and current_hash and rec["source_content_hash"] != current_hash:
        reasons.append(("source_content_hash", f"The record for '{sid}' was extracted from an older version of the source. Re-run extraction for '{sid}'."))
    for key, label in (("extractor", "extractor"), ("prompt_version", "prompt version")):
        expected = (schema or {}).get(key)
        if expected is not None and rec.get(key) != expected:
            reasons.append((key, f"The record for '{sid}' was made with {label} '{rec.get(key)}', but evidence/extraction_schema.yaml now expects '{expected}'. Re-run extraction for '{sid}'."))
    return reasons


def stale_records(records: dict, manifest: dict, schema: dict | None = None) -> list[str]:
    hashes = {s["id"]: s.get("content_hash") for s in manifest.get("sources", [])}
    return [sid for sid, rec in records.items() if _stale_reasons(sid, rec, hashes.get(sid), schema)]


def stale_warnings(records: dict, manifest: dict, schema: dict | None, folder: Path) -> list[Problem]:
    """One warning per reason a record is stale (source hash, extractor or prompt version changed)."""
    hashes = {s["id"]: s.get("content_hash") for s in manifest.get("sources", [])}
    return [Problem(str(folder / f"{sid}.yaml"), key, message)
            for sid, rec in records.items() for key, message in _stale_reasons(sid, rec, hashes.get(sid), schema)]
