import codecs
import os
from pathlib import Path

import pytest
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


@pytest.mark.parametrize("line", ["/cache/", "/cache", "cache/", "cache", "  cache/  "])
def test_cache_ignore_line_accepts_common_forms(tmp_path, line):
    repo = _repo(tmp_path)
    (repo / "cache").mkdir()
    (repo / "cache" / "x.pdf").write_bytes(b"")
    (repo / ".gitignore").write_text(f"# local\n\n{line}\n", encoding="utf-8")
    assert _run(repo) == ([], [])


@pytest.mark.parametrize("line", ["!cache/keep.txt", "!/cache/sources/", "!cache"])
def test_gitignore_negation_under_cache_is_a_problem(tmp_path, line):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text(f"/cache/\n{line}\n", encoding="utf-8")
    problems, _ = _run(repo)
    assert [p.message for p in problems] == ["this .gitignore re-includes files under cache/; remove the '!' line, cache/ must stay ignored"]


def test_public_repo_rejects_project_package_with_extraction(tmp_path):
    charter = _charter("public")
    repo = _repo(tmp_path, charter, [_source("pkg", type="project_package", access_class="open", extraction="e.yaml")])
    problems, _ = _run(repo, charter)
    assert any("pkg" in p.message and "public" in p.message for p in problems)


def test_public_repo_accepts_open_project_package_pointer(tmp_path):
    charter = _charter("public")
    repo = _repo(tmp_path, charter, [_source("pkg", type="project_package", access_class="open")])
    assert _run(repo, charter) == ([], [])


def test_public_repo_restricted_entry_is_printed_as_warning(tmp_path, capsys):
    charter = _charter("public")
    repo = _repo(tmp_path, charter, [_source("r", access_class="restricted")])
    problems, warnings = _run(repo, charter)
    assert problems == [] and len(warnings) == 1 and "'r'" in warnings[0].message
    assert main(["validate", str(repo)]) == 0
    assert "restricted" in capsys.readouterr().out.split("[warning]")[0]


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


def test_confidential_charter_accepts_confidential_entry_that_public_rejects(tmp_path):
    src = _source("secret", access_class="confidential")
    for name, expect_problem in ("public", True), ("private_until_release", False), ("confidential", False):
        charter = _charter(name)
        folder = tmp_path / name
        folder.mkdir()
        problems, _ = _run(_repo(folder, charter, [src]), charter)
        assert bool(problems) is expect_problem
        assert all("confidential but this repo is public" in p.message for p in problems)


def test_manifest_path_outside_repo_is_rejected(tmp_path):
    (tmp_path / "benign.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": []}), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    for value in ("../benign.yaml", str(tmp_path / "benign.yaml")):
        charter = _charter(evidence={"manifest": value})
        problems, _ = _run(_repo(repo, charter), charter)
        assert [p.location for p in problems] == ["evidence.manifest"]


def test_custom_manifest_path_in_subfolder_is_checked(tmp_path):
    charter = _charter(evidence={"manifest": "lit/sub/sources.yaml"})
    repo = _repo(tmp_path, charter, manifest=False)
    (repo / "lit" / "sub").mkdir(parents=True)
    (repo / "lit" / "sub" / "sources.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": [_source(), _source()]}), encoding="utf-8")
    problems, _ = _run(repo, charter)
    assert [p.location for p in problems] == ["sources[1].id"] and "sources.yaml" in problems[0].path


def test_unsupported_claim_reported(tmp_path):
    repo = _repo(tmp_path)
    (repo / "synthesis.md").write_text("Claim [@ghost].\n", encoding="utf-8")
    problems, _ = _run(repo)
    assert any("ghost" in p.message for p in problems)


def test_stale_record_is_warning_not_problem(tmp_path):
    repo = _repo(tmp_path, sources=[_source("a", content_hash="new")])
    schema_text = (FIXTURES / "evidence" / "extraction_schema_ok.yaml").read_text(encoding="utf-8")
    (repo / "evidence" / "extraction_schema.yaml").write_text(schema_text, encoding="utf-8")
    (repo / "evidence" / "extractions").mkdir()
    rec = {"source_id": "a", "extractor": "m", "prompt_version": "1", "source_content_hash": "old",
           "cost": {"usd": 0.01}, "fields": {"sample_size": 1}, "locators": {"sample_size": "p. 1"}}
    (repo / "evidence" / "extractions" / "a.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")
    problems, warnings = _run(repo)
    assert problems == [] and len(warnings) == 1 and "a" in warnings[0].message
    assert main(["validate", str(repo)]) == 0


def test_record_from_old_prompt_version_is_stale_warning(tmp_path):
    repo = _repo(tmp_path, sources=[_source("a", content_hash="h")])
    schema_text = (FIXTURES / "evidence" / "extraction_schema_ok.yaml").read_text(encoding="utf-8")
    (repo / "evidence" / "extraction_schema.yaml").write_text(schema_text + "extractor: m\nprompt_version: '2'\n", encoding="utf-8")
    (repo / "evidence" / "extractions").mkdir()
    rec = {"source_id": "a", "extractor": "m", "prompt_version": "1", "source_content_hash": "h",
           "cost": {"usd": 0.01}, "fields": {"sample_size": 1}, "locators": {}}
    (repo / "evidence" / "extractions" / "a.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")
    problems, warnings = _run(repo)
    assert problems == [] and [w.location for w in warnings] == ["prompt_version"]
    assert "'1'" in warnings[0].message and "'2'" in warnings[0].message


def _dataset(descriptor):
    return _source("panel", type="dataset", identifier={"scheme": "dataset_doi", "value": "10.0/p"}, descriptor=descriptor)


def test_dataset_descriptor_inside_repo_and_valid_passes(tmp_path):
    repo = _repo(tmp_path, sources=[_dataset("data/descriptors/panel.yaml")])
    (repo / "data" / "descriptors").mkdir(parents=True)
    (repo / "data" / "descriptors" / "panel.yaml").write_text(
        (FIXTURES / "repo_valid" / "data" / "descriptors" / "prices.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    assert _run(repo) == ([], [])


def test_dataset_descriptor_escaping_repo_rejected(tmp_path):
    outside = tmp_path / "outside.yaml"
    outside.write_text((FIXTURES / "repo_valid" / "data" / "descriptors" / "prices.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    for value in ("../outside.yaml", str(outside)):
        problems, _ = _run(_repo(repo, sources=[_dataset(value)]))
        assert [p.location for p in problems] == ["sources[0].descriptor"]
        assert "outside this repo" in problems[0].message


def test_dataset_descriptor_missing_file_rejected(tmp_path):
    problems, _ = _run(_repo(tmp_path, sources=[_dataset("data/descriptors/none.yaml")]))
    assert [p.location for p in problems] == ["sources[0].descriptor"]
    assert "data/descriptors/none.yaml" in problems[0].message and "does not exist" in problems[0].message


def test_dataset_descriptor_invalid_reports_its_problems(tmp_path):
    repo = _repo(tmp_path, sources=[_dataset("data/descriptors/panel.yaml")])
    (repo / "data" / "descriptors").mkdir(parents=True)
    (repo / "data" / "descriptors" / "panel.yaml").write_text("schema_version: 0.2.0\nid: panel\n", encoding="utf-8")
    problems, _ = _run(repo)
    assert problems and all(p.path.endswith("panel.yaml") for p in problems)


def test_cli_reports_a_linked_descriptor_problem_once(tmp_path, capsys):
    repo = _repo(tmp_path, sources=[_dataset("data/descriptors/panel.yaml")])
    (repo / "data" / "descriptors").mkdir(parents=True)
    (repo / "data" / "descriptors" / "panel.yaml").write_text("schema_version: 0.2.0\nid: panel\n", encoding="utf-8")
    assert main(["validate", str(repo)]) == 1
    lines = [line for line in capsys.readouterr().out.splitlines() if "panel.yaml" in line]
    assert lines and len(lines) == len(set(lines))


def test_extraction_pointer_escaping_repo_rejected(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for value in ("../a.yaml", str(tmp_path / "a.yaml")):
        problems, _ = _run(_repo(repo, sources=[_source("a", extraction=value)]))
        assert [p.location for p in problems] == ["sources[0].extraction"]
        assert "outside this repo" in problems[0].message


def _screening_repo(tmp_path, pointer, record_name="a"):
    repo = _repo(tmp_path, sources=[_source("a", extraction=pointer)])
    (repo / "evidence" / "extraction_schema.yaml").write_text(
        (FIXTURES / "evidence" / "extraction_schema_ok.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (repo / "evidence" / "extractions").mkdir()
    rec = {"source_id": record_name, "extractor": "m", "prompt_version": "1", "source_content_hash": "h",
           "cost": {"usd": 0}, "fields": {"sample_size": 1}, "locators": {}}
    (repo / "evidence" / "extractions" / f"{record_name}.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")
    return repo


def test_extraction_pointer_to_existing_record_passes(tmp_path):
    assert _run(_screening_repo(tmp_path, "evidence/extractions/a.yaml")) == ([], [])


def test_extraction_pointer_to_missing_file_rejected_in_screening_tier(tmp_path):
    problems, _ = _run(_screening_repo(tmp_path, "evidence/extractions/gone/a.yaml"))
    assert [p.location for p in problems] == ["sources[0].extraction"]
    assert "does not exist" in problems[0].message


def test_extraction_pointer_with_wrong_name_rejected_in_screening_tier(tmp_path):
    repo = _screening_repo(tmp_path, "evidence/extractions/b.yaml")
    (repo / "evidence" / "extractions" / "b.yaml").write_text("x: 1\n", encoding="utf-8")
    problems, _ = _run(repo)
    pointer = [p for p in problems if p.location == "sources[0].extraction"]
    assert len(pointer) == 1 and "a.yaml" in pointer[0].message and "b.yaml" in pointer[0].message


def test_missing_extraction_record_reported(tmp_path):
    repo = _repo(tmp_path, sources=[_source("a")])
    (repo / "evidence" / "extraction_schema.yaml").write_text(
        (FIXTURES / "evidence" / "extraction_schema_ok.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    problems, _ = _run(repo)
    assert any("'a'" in p.message and "extraction record" in p.message for p in problems)
    message = next(p.message for p in problems if "extraction record" in p.message)
    assert "--exclude" not in message and "evidence/extractions/a.yaml" in message
    assert "screening_status to candidate or excluded" in message


def test_study_kind_repo_unaffected(capsys):
    assert main(["validate", str(FIXTURES / "repo_valid")]) == 0
    assert "evidence" not in capsys.readouterr().out


def test_more_document_suffixes_blocked_case_insensitively(tmp_path):
    repo = _repo(tmp_path)
    (repo / "papers").mkdir()
    (repo / "papers" / "a.djvu").write_bytes(b"")
    (repo / "papers" / "B.RTF").write_bytes(b"")
    (repo / "cache").mkdir()
    (repo / ".gitignore").write_text("/cache/\n", encoding="utf-8")
    (repo / "cache" / "c.doc").write_bytes(b"")
    problems, _ = _run(repo)
    paths = " ".join(p.path for p in problems)
    assert "a.djvu" in paths and "B.RTF" in paths and "c.doc" not in paths


def test_non_utf8_synthesis_is_a_problem_not_a_traceback(tmp_path):
    repo = _repo(tmp_path, sources=[_source()])
    (repo / "synthesis.md").write_bytes(b"\xff\xfe\x00bad")
    problems, _ = _run(repo)
    assert any("synthesis.md" in p.path and "UTF-8" in p.message for p in problems)
