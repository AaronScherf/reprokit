from pathlib import Path

import pytest
import yaml

from reprokit.evidence_extraction import load_extraction_schema, load_records, stale_records

SCHEMA_FIXTURE = Path(__file__).parent / "fixtures" / "evidence" / "extraction_schema_ok.yaml"


def _schema():
    schema, problems = load_extraction_schema(SCHEMA_FIXTURE)
    assert problems == []
    return schema


def _manifest(*sources):
    return {"sources": [{"id": sid, "screening_status": status, **extra} for sid, status, extra in sources]}


def _record(sid="smith-2020", **over):
    rec = {
        "source_id": sid, "extractor": "model-x", "prompt_version": "1",
        "source_content_hash": "abc", "cost": {"usd": 0.01},
        "fields": {"sample_size": 120, "outcome": "income"}, "locators": {"sample_size": "p. 3"},
    }
    rec.update(over)
    return rec


def _write(folder, rec, name=None):
    folder.mkdir(exist_ok=True)
    (folder / f"{name or rec['source_id']}.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")


MANIFEST = _manifest(("smith-2020", "included", {"content_hash": "abc"}))


def test_valid_record_loads(tmp_path):
    _write(tmp_path, _record())
    records, problems = load_records(tmp_path, MANIFEST, _schema())
    assert problems == []
    assert records["smith-2020"]["fields"]["sample_size"] == 120


def test_unknown_field_rejected(tmp_path):
    _write(tmp_path, _record(fields={"mystery": 1}))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert any("mystery" in p.message for p in problems)


def test_filename_must_match_source_id(tmp_path):
    _write(tmp_path, _record(), name="other")
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert any("filename" in p.message.lower() for p in problems)


def test_overlong_text_rejected(tmp_path):
    _write(tmp_path, _record(fields={"outcome": "x" * 501}))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert any("500" in p.message for p in problems)


def test_wrong_value_type_rejected(tmp_path):
    _write(tmp_path, _record(fields={"sample_size": "many"}))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert any("sample_size" in p.message for p in problems)


def test_stale_record_detected_when_hash_differs():
    records = {"a": {"source_content_hash": "old"}, "b": {"source_content_hash": "same"}, "c": {"source_content_hash": ""}}
    manifest = _manifest(("a", "included", {"content_hash": "new"}), ("b", "included", {"content_hash": "same"}), ("c", "included", {"content_hash": "z"}), ("d", "included", {}))
    assert stale_records(records, manifest) == ["a"]


def test_included_source_without_record_is_a_problem(tmp_path):
    manifest = _manifest(("a", "included", {}), ("b", "excluded", {}), ("c", "candidate", {}))
    records, problems = load_records(tmp_path, manifest, _schema())
    assert records == {}
    assert len(problems) == 1 and "a" in problems[0].message


def test_list_aggregate_accepted_and_unknown_rejected(tmp_path):
    assert _schema()["fields"]["countries"]["aggregate"] == "list"
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 0.1.0\nfields:\n  x: {type: list, aggregate: median}\n", encoding="utf-8")
    schema, problems = load_extraction_schema(bad)
    assert schema is None and problems


@pytest.mark.parametrize("over", [
    {"locators": {"sample_size": "q" * 501}},
    {"extractor": "q" * 501},
    {"prompt_version": "q" * 501},
])
def test_overlong_metadata_text_rejected(tmp_path, over):
    _write(tmp_path, _record(**over))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert problems


def test_nested_list_element_rejected(tmp_path):
    _write(tmp_path, _record(fields={"countries": [["x" * 5000]]}))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert any("nested" in p.message.lower() for p in problems)


def test_overlong_list_element_rejected(tmp_path):
    _write(tmp_path, _record(fields={"countries": ["ok", "x" * 501]}))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert any("500" in p.message for p in problems)
