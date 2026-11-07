"""validate, evidence-run and verify-sources agree on which file is the manifest."""
from pathlib import Path

import pytest
import yaml

from reprokit import evidence_verify
from reprokit.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "evidence"


def _charter(**extra):
    doc = {
        "schema_version": "0.2.0", "name": "Evidence", "kind": "evidence", "purpose": "side_project",
        "confidentiality": "public",
        "audiences": [{"name": "readers", "needs": "summary", "technical_level": "non_technical", "channel": "public"}],
        "publication": {"venues": [], "preregistration": ""}, "deliverables": [],
        "taxonomy": {"tags": []}, "sources": [], "siblings": [],
    }
    doc.update(extra)
    return doc


def _source(sid):
    return {"id": sid, "type": "article", "identifier": {"scheme": "doi", "value": f"10.0000/{sid}"}, "title": "T",
            "access_class": "open", "screening_status": "included", "verification_status": "proposed"}


def _record(sid):
    return {"source_id": sid, "extractor": "m", "prompt_version": "1", "source_content_hash": "h", "cost": {"usd": 0.1},
            "fields": {"sample_size": 7}, "locators": {"sample_size": "p. 1"}}


def _repo(tmp_path, charter_text):
    (tmp_path / "project.yaml").write_text(charter_text, encoding="utf-8")
    (tmp_path / "evidence" / "extractions").mkdir(parents=True)
    # The default location holds a broken manifest: any command reading it fails.
    (tmp_path / "evidence" / "manifest.yaml").write_text("not: a manifest\n", encoding="utf-8")
    (tmp_path / "evidence" / "extraction_schema.yaml").write_text((FIXTURES / "extraction_schema_ok.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "evidence" / "extractions" / "a.yaml").write_text(yaml.safe_dump(_record("a")), encoding="utf-8")
    (tmp_path / "synthesis.md").write_text("# Synthesis\n", encoding="utf-8")
    return tmp_path


def test_all_three_commands_read_the_same_custom_manifest(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, yaml.safe_dump(_charter(evidence={"manifest": "lit/sub/sources.yaml"})))
    (repo / "lit" / "sub").mkdir(parents=True)
    (repo / "lit" / "sub" / "sources.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": [_source("a")]}), encoding="utf-8")
    assert main(["validate", str(repo)]) == 0, capsys.readouterr().out
    assert main(["evidence-run", str(repo)]) == 0, capsys.readouterr().out
    out = yaml.safe_load((repo / "outputs" / "evidence_aggregate.yaml").read_text(encoding="utf-8"))
    assert out["aggregate"]["fields"]["sample_size"] == 7
    seen = []
    monkeypatch.setattr(evidence_verify, "default_resolver", lambda ident: seen.append(ident["value"]) or True)
    assert main(["verify-sources", str(repo)]) == 0, capsys.readouterr().out
    assert seen == ["10.0000/a"]


@pytest.mark.parametrize("command", ["evidence-run", "verify-sources"])
@pytest.mark.parametrize("charter_text,location", [
    ("kind: [unclosed\n", "line"),
    ("kind: evidence\nevidence: just-text\n", "evidence"),
    ("kind: evidence\nevidence: {manifest: ../benign.yaml}\n", "evidence.manifest"),
])
def test_bad_charter_is_a_problem_not_a_traceback(tmp_path, capsys, command, charter_text, location):
    (tmp_path / "repo").mkdir()
    repo = _repo(tmp_path / "repo", charter_text)
    (tmp_path / "benign.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": [_source("a")]}), encoding="utf-8")
    assert main([command, str(repo)]) == 1
    out = capsys.readouterr().out
    assert "project.yaml" in out and location in out
    assert not (repo / "outputs").exists()
