import codecs
import os
from pathlib import Path

import yaml

from reprokit.cli import main
from reprokit.evidence_rules import validate_evidence

FIXTURES = Path(__file__).parent / "fixtures"


def _charter(confidentiality="confidential", **extra):
    doc = {
        "schema_version": "0.2.0", "name": "Evidence", "kind": "evidence", "purpose": "side_project",
        "confidentiality": confidentiality,
        "audiences": [{"name": "readers", "needs": "summary", "technical_level": "non_technical", "channel": "public"}],
        "publication": {"venues": [], "preregistration": ""}, "deliverables": [],
        "taxonomy": {"tags": []}, "sources": [], "siblings": [],
    }
    doc.update(extra)
    return doc


def _repo(tmp_path, charter=None, sources=(), manifest=True):
    charter = charter or _charter()
    (tmp_path / "project.yaml").write_text(yaml.safe_dump(charter), encoding="utf-8")
    if manifest:
        (tmp_path / "evidence").mkdir(exist_ok=True)
        (tmp_path / "evidence" / "manifest.yaml").write_text(
            yaml.safe_dump({"schema_version": "0.1.0", "sources": list(sources)}), encoding="utf-8")
    (tmp_path / "synthesis.md").write_text("# Synthesis\n", encoding="utf-8")
    return tmp_path


def _source(sid="a", **over):
    src = {"id": sid, "type": "article", "identifier": {"scheme": "doi", "value": "10.0000/x"}, "title": "T",
           "access_class": "open", "screening_status": "included", "verification_status": "proposed"}
    src.update(over)
    return src


def _run(repo, charter=None):
    return validate_evidence(repo, charter or _charter())


def test_minimal_evidence_repo_validates(tmp_path):
    repo = _repo(tmp_path)
    assert _run(repo) == ([], [])
    assert main(["validate", str(repo)]) == 0


def test_missing_manifest_reported(tmp_path):
    problems, _ = _run(_repo(tmp_path, manifest=False))
    assert any("manifest" in p.path for p in problems)


def test_pdf_in_nested_directory_rejected(tmp_path):
    repo = _repo(tmp_path)
    (repo / "papers" / "deep").mkdir(parents=True)
    (repo / "papers" / "deep" / "x.pdf").write_bytes(b"")
    problems, _ = _run(repo)
    assert any("x.pdf" in p.path for p in problems)


def test_uppercase_pdf_rejected(tmp_path):
    repo = _repo(tmp_path)
    (repo / "X.PDF").write_bytes(b"")
    (repo / "b.Epub").write_bytes(b"")
    problems, _ = _run(repo)
    assert any("X.PDF" in p.path for p in problems) and any("b.Epub" in p.path for p in problems)


def test_cache_directory_must_be_gitignored(tmp_path):
    repo = _repo(tmp_path)
    (repo / "cache").mkdir()
    (repo / "cache" / "x.pdf").write_bytes(b"")
    problems, _ = _run(repo)
    assert any(".gitignore" in p.message and "/cache/" in p.message for p in problems)
    assert not any("x.pdf" in p.path for p in problems)
    (repo / ".gitignore").write_text("*.log\n/cache/\n", encoding="utf-8")
    assert _run(repo) == ([], [])


def test_public_repo_rejects_project_package_without_pointer(tmp_path):
    charter = _charter("public")
    repo = _repo(tmp_path, charter, [_source("pkg", type="project_package", access_class="open")])
    problems, _ = _run(repo, charter)
    assert any("pkg" in p.message and "public" in p.message for p in problems)


def test_pdf_in_listed_venv_not_flagged(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".venv" / "lib").mkdir(parents=True)
    (repo / ".venv" / "lib" / "t.pdf").write_bytes(b"")
    (repo / ".gitignore").write_bytes(codecs.BOM_UTF8 + b"# env" + os.linesep.encode() + b".venv/" + os.linesep.encode())
    assert _run(repo) == ([], [])


def test_pdf_in_unlisted_venv_flagged(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".venv").mkdir()
    (repo / ".venv" / "t.pdf").write_bytes(b"")
    problems, _ = _run(repo)
    assert any("t.pdf" in p.path for p in problems)


def test_docx_flagged_and_nested_cache_name_flagged(tmp_path):
    repo = _repo(tmp_path)
    (repo / "notes" / "cache").mkdir(parents=True)
    (repo / "notes" / "cache" / "x.pdf").write_bytes(b"")
    (repo / "memo.docx").write_bytes(b"")
    problems, _ = _run(repo)
    assert any("memo.docx" in p.path for p in problems) and any("x.pdf" in p.path for p in problems)


def test_git_directory_skipped(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".git").mkdir()
    (repo / ".git" / "obj.pdf").write_bytes(b"")
    assert _run(repo) == ([], [])


def test_unreadable_gitignore_is_problem(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_bytes(bytes([0xff, 0xfe, 0, 0x80]))
    problems, _ = _run(repo)
    assert any(".gitignore" in p.path for p in problems)


def test_confidential_charter_accepts_project_package_that_public_rejects(tmp_path):
    src = _source("pkg", type="project_package", access_class="open")
    for name, expect_problem in ("public", True), ("confidential", False):
        charter = _charter(name)
        folder = tmp_path / name
        folder.mkdir()
        problems, _ = _run(_repo(folder, charter, [src]), charter)
        assert bool(problems) is expect_problem


def test_unsupported_claim_reported(tmp_path):
    repo = _repo(tmp_path)
    (repo / "synthesis.md").write_text("Claim [@ghost].\n", encoding="utf-8")
    problems, _ = _run(repo)
    assert any("ghost" in p.message for p in problems)


def test_stale_record_is_warning_not_problem(tmp_path):
    repo = _repo(tmp_path, sources=[_source("a", content_hash="new")])
    shutil_schema = (FIXTURES / "evidence" / "extraction_schema_ok.yaml").read_text(encoding="utf-8")
    (repo / "evidence" / "extraction_schema.yaml").write_text(shutil_schema, encoding="utf-8")
    (repo / "evidence" / "extractions").mkdir()
    rec = {"source_id": "a", "extractor": "m", "prompt_version": "1", "source_content_hash": "old",
           "cost": {"usd": 0.01}, "fields": {"sample_size": 1}, "locators": {"sample_size": "p. 1"}}
    (repo / "evidence" / "extractions" / "a.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")
    problems, warnings = _run(repo)
    assert problems == [] and len(warnings) == 1 and "a" in warnings[0].message
    assert main(["validate", str(repo)]) == 0


def test_missing_extraction_record_reported(tmp_path):
    repo = _repo(tmp_path, sources=[_source("a")])
    (repo / "evidence" / "extraction_schema.yaml").write_text(
        (FIXTURES / "evidence" / "extraction_schema_ok.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    problems, _ = _run(repo)
    assert any("'a'" in p.message and "extraction record" in p.message for p in problems)


def test_study_kind_repo_unaffected(capsys):
    assert main(["validate", str(FIXTURES / "repo_valid")]) == 0
    assert "evidence" not in capsys.readouterr().out
