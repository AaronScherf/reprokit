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
    record = {"offline": True, "success": True, "required_outputs": [
        {"path": "panel.csv", "sha256": hashlib.sha256(output.read_bytes()).hexdigest()},
    ]}
    result.write_text(json.dumps(record))
    assert verify_smoke_result(result, tmp_path) == []
    record["offline"] = False
    record["required_outputs"][0]["sha256"] = "0" * 64
    result.write_text(json.dumps(record))
    locations = {problem.location for problem in verify_smoke_result(result, tmp_path)}
    assert locations == {"offline", "required_outputs[0].sha256"}


def test_smoke_verifier_requires_outputs_and_rejects_escape(tmp_path):
    result = tmp_path / "smoke_result.json"
    result.write_text(json.dumps({"offline": True, "success": True, "required_outputs": []}))
    assert verify_smoke_result(result, tmp_path)[0].location == "required_outputs"
    result.write_text(json.dumps({"offline": True, "success": True, "required_outputs": [
        {"path": "../outside.csv", "sha256": "0" * 64},
    ]}))
    assert verify_smoke_result(result, tmp_path)[0].location == "required_outputs[0].path"


def test_fixture_project_runs_synthetic_smoke(tmp_path):
    project = tmp_path / "project"
    shutil.copytree(Path(__file__).parent / "fixtures/smoke_project", project)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")}
    result = subprocess.run([sys.executable, "smoke.py"], cwd=project, env=env, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert verify_smoke_result(project / "outputs/smoke_result.json", project / "outputs") == []
