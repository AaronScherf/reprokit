import hashlib
import json
import shutil
from pathlib import Path

import pytest

from reprokit.run_summary import (
    RunSummaryError,
    carry_forward_skipped_steps,
    write_run_summary,
)

FIXTURE = Path(__file__).parent / "fixtures/smoke_project"


def test_documented_example_is_generated_from_fixture(tmp_path):
    text = (Path(__file__).parent.parent / "docs/examples/RUN_SUMMARY.md").read_text(encoding="utf-8")
    assert text.startswith("# Run summary - made-up sample")
    assert "tests/fixtures/smoke_project/outputs/panel.csv" in text
    assert (FIXTURE / "outputs/panel.csv").is_file()
    generated = write_run_summary(
        FIXTURE / "outputs/manifest.json", FIXTURE / "outputs/run_report.json",
        FIXTURE / "outputs/run_metrics.json", FIXTURE / "config.yaml", tmp_path / "RUN_SUMMARY.md",
    ).read_text(encoding="utf-8")
    assert text.split("\n\n", 2)[2] == generated.split("\n\n", 1)[1]


def project(tmp_path):
    target = tmp_path / "project"
    shutil.copytree(FIXTURE, target)
    panel = target / "outputs/panel.csv"
    panel.write_bytes(b"month,count\n2020-01,2\n")
    return target


def metrics(target):
    panel = target / "outputs/panel.csv"
    return {
        "schema_version": "0.1.0",
        "run_date_utc": "2026-11-03T12:00:00Z",
        "steps": [
            {"name": "read", "elapsed_seconds": 38, "peak_rss_mb": 900, "rss_basis": "tree", "measurement_run_date_utc": "2026-11-03T12:00:00Z", "skipped": False},
            {"name": "fuse", "elapsed_seconds": 10, "peak_rss_mb": 500, "rss_basis": "tree", "measurement_run_date_utc": "2026-11-02T12:00:00Z", "skipped": True},
        ],
        "outputs": [{"path": "panel.csv", "sha256": hashlib.sha256(panel.read_bytes()).hexdigest()}],
    }


def render(target):
    return write_run_summary(
        target / "outputs/manifest.json", target / "outputs/run_report.json", target / "outputs/run_metrics.json",
        target / "config.yaml", target / "outputs/RUN_SUMMARY.md",
    )


def test_run_summary_uses_structured_values_and_labels_skipped_measurement(tmp_path):
    target = project(tmp_path)
    (target / "outputs/run_metrics.json").write_text(json.dumps(metrics(target)))
    text = render(target).read_text()
    assert "Exampleland settings for January 2020" in text
    assert "It produced 1 row. The work completed in this run took 38 seconds." in text
    assert "| read | 38 seconds | 0.9 GB" in text
    assert "| fuse | 10 seconds (last measured November 2, 2026; skipped this run) | 0.5 GB" in text
    assert "checksum (a fingerprint of the file)" in text
    assert "`outputs/panel.csv`" in text
    assert hashlib.sha256((target / "outputs/panel.csv").read_bytes()).hexdigest() in text
    assert "RUN_SUMMARY.md:" not in text


def test_run_summary_fails_when_measurement_is_missing(tmp_path):
    target = project(tmp_path)
    record = metrics(target)
    del record["steps"][0]["elapsed_seconds"]
    (target / "outputs/run_metrics.json").write_text(json.dumps(record))
    with pytest.raises(RunSummaryError, match="step 'read'.*elapsed_seconds"):
        render(target)


def test_existing_manifest_and_report_shape_need_metrics_file(tmp_path):
    target = project(tmp_path)
    (target / "outputs/run_metrics.json").unlink()
    with pytest.raises(RunSummaryError, match="This run has no run_metrics.json"):
        render(target)


def test_run_summary_rejects_its_own_hash_and_stale_output_hash(tmp_path):
    target = project(tmp_path)
    record = metrics(target)
    record["outputs"].append({"path": "RUN_SUMMARY.md", "sha256": "0" * 64})
    path = target / "outputs/run_metrics.json"
    path.write_text(json.dumps(record))
    with pytest.raises(RunSummaryError, match="cannot list its own checksum"):
        render(target)
    record["outputs"].pop()
    record["outputs"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(record))
    with pytest.raises(RunSummaryError) as error:
        render(target)
    assert str(error.value) == "The checksum for panel.csv does not match a file from this run. Run reproduce again and retry."
    assert "matches the recorded file" not in str(error.value)


def test_run_summary_explains_crlf_only_checksum_mismatch(tmp_path):
    target = project(tmp_path)
    record = metrics(target)
    (target / "outputs/run_metrics.json").write_text(json.dumps(record))
    panel = target / "outputs/panel.csv"
    panel.write_bytes(panel.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(RunSummaryError) as error:
        render(target)
    message = str(error.value)
    assert "panel.csv" in message
    assert "line endings" in message
    assert "Git on Windows" in message
    assert "Restore the original LF file or run reproduce again" in message


def test_run_summary_keeps_real_mismatch_message_with_crlf(tmp_path):
    target = project(tmp_path)
    record = metrics(target)
    (target / "outputs/run_metrics.json").write_text(json.dumps(record))
    (target / "outputs/panel.csv").write_bytes(b"month,count\r\n2020-01,3\r\n")
    with pytest.raises(RunSummaryError) as error:
        render(target)
    assert str(error.value) == "The checksum for panel.csv does not match a file from this run. Run reproduce again and retry."
    assert "matches the recorded file" not in str(error.value)


def test_skipped_step_keeps_previous_measurement_and_date(tmp_path):
    target = project(tmp_path)
    previous = metrics(target)
    current = {**previous, "run_date_utc": "2026-11-04T12:00:00Z", "steps": [{"name": "read", "skipped": True}]}
    updated = carry_forward_skipped_steps(current, previous)
    assert updated["steps"][0]["elapsed_seconds"] == 38
    assert updated["steps"][0]["peak_rss_mb"] == 900
    assert updated["steps"][0]["measurement_run_date_utc"] == "2026-11-03T12:00:00Z"
    assert updated["run_date_utc"] == "2026-11-04T12:00:00Z"
    with pytest.raises(RunSummaryError, match="last measurement is missing"):
        carry_forward_skipped_steps(current, None)
