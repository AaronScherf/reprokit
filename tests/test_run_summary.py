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
    assert "It produced 1 row. Steps run now took 38 seconds." in text
    assert "read (38 seconds), using up to 0.9 GB" in text
    assert "fuse step was already up to date" in text and "November 2, 2026" in text
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
    with pytest.raises(RunSummaryError, match="checksum for panel.csv"):
        render(target)


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
