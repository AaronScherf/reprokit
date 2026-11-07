from pathlib import Path

import pytest
import yaml

from reprokit.evidence_manifest import (
    check_manifest_rules,
    load_manifest,
    load_repo_charter,
    manifest_path,
    manifest_warnings,
)

FIXTURE = Path(__file__).parent / "fixtures" / "evidence" / "manifest_ok.yaml"


def _doc():
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def _source(**over):
    base = {"id": "s1", "type": "article", "identifier": {"scheme": "doi", "value": "10.0/x"}, "title": "T",
            "access_class": "open", "screening_status": "included", "verification_status": "proposed"}
    return {**base, **over}


def _write(tmp_path, doc):
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


def test_fixture_manifest_is_valid():
    doc, problems = load_manifest(FIXTURE, confidentiality="public")
    assert problems == []
    assert len(doc["sources"]) == 2


def test_duplicate_id_is_a_problem(tmp_path):
    doc = {"schema_version": "0.1.0", "sources": [_source(), _source()]}
    _, problems = load_manifest(_write(tmp_path, doc), confidentiality="public")
    assert len(problems) == 1
    assert "'s1'" in problems[0].message


def test_abstract_field_is_rejected(tmp_path):
    doc = {"schema_version": "0.1.0", "sources": [_source(abstract="text")]}
    _, problems = load_manifest(_write(tmp_path, doc), confidentiality="public")
    assert problems and "abstract" in problems[0].message


def test_webpage_without_snapshot_cannot_be_source_verified():
    doc = {"schema_version": "0.1.0", "sources": [_source(type="webpage", verification_status="source-verified")]}
    problems = check_manifest_rules(doc, "m.yaml", "public")
    assert [p.location for p in problems] == ["sources[0].snapshot"]
    doc["sources"][0]["snapshot"] = {"url": "https://example.org", "date": "2026-01-01"}
    assert check_manifest_rules(doc, "m.yaml", "public") == []


def test_dataset_requires_descriptor_link():
    doc = {"schema_version": "0.1.0", "sources": [_source(type="dataset")]}
    problems = check_manifest_rules(doc, "m.yaml", "public")
    assert [p.location for p in problems] == ["sources[0].descriptor"]
    doc["sources"][0]["descriptor"] = "d.yaml"
    assert check_manifest_rules(doc, "m.yaml", "public") == []


def _one(**over):
    return {"schema_version": "0.1.0", "sources": [_source(**over)]}


@pytest.mark.parametrize("kind", ["article", "dataset", "project_package", "webpage"])
def test_confidential_entry_of_any_type_rejected_in_public_repo(kind):
    problems = check_manifest_rules(_one(type=kind, access_class="confidential", descriptor="d.yaml"), "m.yaml", "public")
    assert len(problems) == 1
    assert problems[0].location == "sources[0].access_class"
    assert "confidential but this repo is public" in problems[0].message and "private project" in problems[0].message


def test_restricted_entry_is_a_warning_not_a_problem_in_public_repo():
    doc = _one(access_class="restricted")
    assert check_manifest_rules(doc, "m.yaml", "public") == []
    warnings = manifest_warnings(doc, "m.yaml", "public")
    assert [w.location for w in warnings] == ["sources[0].access_class"]
    assert "restricted" in warnings[0].message and "public" in warnings[0].message


def test_open_project_package_pointer_only_allowed_in_public_repo():
    assert check_manifest_rules(_one(type="project_package"), "m.yaml", "public") == []
    problems = check_manifest_rules(_one(type="project_package", extraction="e.yaml"), "m.yaml", "public")
    assert [p.location for p in problems] == ["sources[0].extraction"]
    assert "pointer" in problems[0].message


@pytest.mark.parametrize("confidentiality", ["private_until_release", "confidential"])
@pytest.mark.parametrize("over", [
    {"access_class": "confidential"},
    {"access_class": "restricted"},
    {"type": "project_package", "access_class": "confidential", "extraction": "e.yaml"},
    {"type": "project_package", "extraction": "e.yaml"},
])
def test_private_repos_accept_everything(confidentiality, over):
    doc = _one(**over)
    assert check_manifest_rules(doc, "m.yaml", confidentiality) == []
    assert manifest_warnings(doc, "m.yaml", confidentiality) == []


def test_load_manifest_defaults_to_strictest_public_rules(tmp_path):
    path = _write(tmp_path, _one(access_class="confidential"))
    assert len(load_manifest(path)[1]) == 1
    assert load_manifest(path, confidentiality="confidential")[1] == []
    with pytest.raises(TypeError):
        load_manifest(path, "confidential")  # keyword-only


def test_load_manifest_missing_file_says_what_to_do(tmp_path):
    _, problems = load_manifest(tmp_path / "nope.yaml", confidentiality="public")
    assert len(problems) == 1 and "Create" in problems[0].message


def test_manifest_path_default_and_custom(tmp_path):
    assert manifest_path(tmp_path, None) == (tmp_path / "evidence" / "manifest.yaml", [])
    assert manifest_path(tmp_path, {"kind": "evidence"}) == (tmp_path / "evidence" / "manifest.yaml", [])
    custom = {"evidence": {"manifest": "lit/sub/sources.yaml"}}
    assert manifest_path(tmp_path, custom) == (tmp_path / "lit" / "sub" / "sources.yaml", [])


@pytest.mark.parametrize("value", ["../benign.yaml", "evidence/../../x.yaml", str(Path(__file__).resolve()), "/etc/m.yaml", 5, ["a"], ""])
def test_manifest_path_rejects_escape_and_non_string(tmp_path, value):
    path, problems = manifest_path(tmp_path, {"evidence": {"manifest": value}})
    assert path is None and len(problems) == 1
    assert problems[0].location == "evidence.manifest" and "project.yaml" in problems[0].path


def test_load_repo_charter_cases(tmp_path):
    assert load_repo_charter(tmp_path) == (None, [])
    (tmp_path / "project.yaml").write_text("kind: evidence\nevidence: {manifest: m.yaml}\n", encoding="utf-8")
    assert load_repo_charter(tmp_path) == ({"kind": "evidence", "evidence": {"manifest": "m.yaml"}}, [])
    (tmp_path / "project.yaml").write_text("kind: [unclosed\n", encoding="utf-8")
    charter, problems = load_repo_charter(tmp_path)
    assert charter is None and len(problems) == 1
    (tmp_path / "project.yaml").write_text("kind: evidence\nevidence: just-text\n", encoding="utf-8")
    charter, problems = load_repo_charter(tmp_path)
    assert charter == {"kind": "evidence"} and [p.location for p in problems] == ["evidence"]


def test_empty_sources_list_is_valid(tmp_path):
    doc, problems = load_manifest(_write(tmp_path, {"schema_version": "0.1.0", "sources": []}), confidentiality="public")
    assert problems == [] and doc["sources"] == []
