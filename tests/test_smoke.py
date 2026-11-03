import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from reprokit.smoke import verify_smoke_result


def test_smoke_verifier_checks_offline_success_and_output_hash(tmp_path):
    output = tmp_path / "panel.csv"
    output.write_bytes(b"month,count\n2020-01,2\n")
    result = tmp_path / "smoke_result.json"
    record = {"offline": True, "success": True, "elapsed_seconds": 38, "required_outputs": [
        {"path": "panel.csv", "sha256": hashlib.sha256(output.read_bytes()).hexdigest()},
    ]}
    result.write_text(json.dumps(record))
    check = verify_smoke_result(result, tmp_path)
    assert check.passed
    assert check.text == "PASS  The project ran from raw data to final table on made-up data in 38 seconds.\n      Your setup works. This does not test the real data. For that, run: reproduce"
    record["offline"] = False
    record["required_outputs"][0]["sha256"] = "0" * 64
    result.write_text(json.dumps(record))
    check = verify_smoke_result(result, tmp_path)
    assert not check.passed and "not recorded as offline" in check.text and "What to do:" in check.text


def test_smoke_verifier_requires_outputs_and_rejects_escape(tmp_path):
    result = tmp_path / "smoke_result.json"
    result.write_text(json.dumps({"offline": True, "success": True, "required_outputs": []}))
    assert "did not list a final output" in verify_smoke_result(result, tmp_path).text
    result.write_text(json.dumps({"offline": True, "success": True, "required_outputs": [
        {"path": "../outside.csv", "sha256": "0" * 64},
    ]}))
    assert "outside the quick check folder" in verify_smoke_result(result, tmp_path).text


def test_fixture_project_runs_synthetic_smoke(tmp_path):
    project = tmp_path / "project"
    shutil.copytree(Path(__file__).parent / "fixtures/smoke_project", project)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")}
    result = subprocess.run([sys.executable, "smoke.py"], cwd=project, env=env, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert verify_smoke_result(project / "outputs/smoke_result.json", project / "outputs").passed
    assert result.stdout.startswith("PASS  ")


def test_quick_check_failure_names_step_and_next_action(tmp_path):
    result = tmp_path / "result.json"
    result.write_text(json.dumps({"offline": True, "success": False, "failed_step": "fuse", "failure_reason": "a required file was missing"}))
    check = verify_smoke_result(result, tmp_path)
    assert not check.passed
    assert check.text == 'FAIL  The step "fuse" stopped: a required file was missing.\n      What to do: run `uv sync --locked` again, then retry.'
