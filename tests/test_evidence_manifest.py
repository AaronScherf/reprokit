from pathlib import Path

import pytest
import yaml

from reprokit.evidence_manifest import check_manifest_rules, load_manifest

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
    doc, problems = load_manifest(FIXTURE)
    assert problems == []
    assert len(doc["sources"]) == 2


def test_duplicate_id_is_a_problem(tmp_path):
    doc = {"schema_version": "0.1.0", "sources": [_source(), _source()]}
    _, problems = load_manifest(_write(tmp_path, doc))
    assert len(problems) == 1
    assert "'s1'" in problems[0].message


def test_abstract_field_is_rejected(tmp_path):
    doc = {"schema_version": "0.1.0", "sources": [_source(abstract="text")]}
    _, problems = load_manifest(_write(tmp_path, doc))
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


@pytest.mark.parametrize("confidentiality,access,expected", [
    ("public", "open", 1),
    ("public", "confidential", 0),
    ("public", "restricted", 0),
    ("private_until_release", "open", 0),
    ("confidential", "open", 0),
])
def test_project_package_rejected_in_public_repo(confidentiality, access, expected):
    doc = {"schema_version": "0.1.0", "sources": [_source(type="project_package", access_class=access)]}
    assert len(check_manifest_rules(doc, "m.yaml", confidentiality)) == expected


def test_project_package_with_extraction_is_not_pointer_only():
    doc = {"schema_version": "0.1.0", "sources": [_source(type="project_package", access_class="confidential", extraction="e.yaml")]}
    assert len(check_manifest_rules(doc, "m.yaml", "public")) == 1


def test_empty_sources_list_is_valid(tmp_path):
    doc, problems = load_manifest(_write(tmp_path, {"schema_version": "0.1.0", "sources": []}))
    assert problems == [] and doc["sources"] == []
