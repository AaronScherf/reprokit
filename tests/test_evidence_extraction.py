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


def test_overlong_content_hash_rejected(tmp_path):
    _write(tmp_path, _record(source_content_hash="h" * 129))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert [p.location for p in problems] == ["source_content_hash"]


def test_record_total_text_capped_at_4000_characters(tmp_path):
    # Every string is under the 500-character field cap, but together they are a copied passage.
    parts = ["y" * 450] * 8
    _write(tmp_path, _record(fields={"outcome": "x" * 400, "countries": parts}))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert len(problems) == 1 and "more than 4000 characters" in problems[0].message
    _write(tmp_path, _record(fields={"outcome": "x" * 400, "countries": parts[:7]}))
    assert load_records(tmp_path, MANIFEST, _schema())[1] == []


def test_record_for_unknown_source_rejected(tmp_path):
    _write(tmp_path, _record("ghost"))
    records, problems = load_records(tmp_path, _manifest(("smith-2020", "candidate", {})), _schema())
    assert records == {}
    assert [p.message for p in problems] == ["record for unknown source 'ghost'; remove it or add the source to the manifest"]


@pytest.mark.parametrize("value", [".nan", ".inf", "-.inf"])
def test_nan_and_inf_rejected_for_number_fields(tmp_path, value):
    text = yaml.safe_dump(_record()).replace("sample_size: 120", f"sample_size: {value}")
    tmp_path.joinpath("smith-2020.yaml").write_text(text, encoding="utf-8")
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert [p.location for p in problems] == ["fields.sample_size"]
    assert "finite" in problems[0].message


@pytest.mark.parametrize("value", [".nan", ".inf"])
def test_nan_and_inf_rejected_for_cost(tmp_path, value):
    text = yaml.safe_dump(_record()).replace("usd: 0.01", f"usd: {value}")
    tmp_path.joinpath("smith-2020.yaml").write_text(text, encoding="utf-8")
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert [p.location for p in problems] == ["cost.usd"]


def test_non_yaml_file_in_extractions_rejected(tmp_path):
    _write(tmp_path, _record())
    (tmp_path / "jones-2021.yml").write_text("source_id: jones-2021\n", encoding="utf-8")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    records, problems = load_records(tmp_path, MANIFEST, _schema())
    assert "smith-2020" in records
    assert len(problems) == 1 and "jones-2021.yml" in problems[0].path
    assert "jones-2021.yaml" in problems[0].message


def test_malformed_yaml_record_is_a_problem(tmp_path):
    (tmp_path / "smith-2020.yaml").write_text("source_id: [unclosed\n", encoding="utf-8")
    records, problems = load_records(tmp_path, MANIFEST, _schema())
    assert records == {} and any("invalid YAML" in p.message for p in problems)


def test_invalid_extraction_schema_file_is_a_problem(tmp_path):
    bad = tmp_path / "schema.yaml"
    bad.write_text("schema_version: 0.1.0\nfields:\n  x: {type: matrix, aggregate: sum}\n", encoding="utf-8")
    schema, problems = load_extraction_schema(bad)
    assert schema is None and [p.location for p in problems] == ["fields.x.type"]


def test_bool_given_for_number_field_rejected(tmp_path):
    _write(tmp_path, _record(fields={"sample_size": True}))
    _, problems = load_records(tmp_path, MANIFEST, _schema())
    assert [p.location for p in problems] == ["fields.sample_size"]


def test_duplicate_keys_in_record_rejected(tmp_path):
    text = yaml.safe_dump(_record()) + "extractor: other\n"
    (tmp_path / "smith-2020.yaml").write_text(text, encoding="utf-8")
    records, problems = load_records(tmp_path, MANIFEST, _schema())
    assert records == {} and any("duplicate key: extractor" in p.message for p in problems)


def _versioned_schema(tmp_path, **current):
    path = tmp_path / "extraction_schema.yaml"
    path.write_text(SCHEMA_FIXTURE.read_text(encoding="utf-8") + "".join(f"{k}: '{v}'\n" for k, v in current.items()), encoding="utf-8")
    schema, problems = load_extraction_schema(path)
    assert problems == []
    return schema


def test_stale_record_detected_when_extractor_or_prompt_version_changed(tmp_path):
    schema = _versioned_schema(tmp_path, extractor="model-y", prompt_version="2")
    records = {"a": {"source_content_hash": "h", "extractor": "model-y", "prompt_version": "2"},
               "b": {"source_content_hash": "h", "extractor": "model-x", "prompt_version": "2"},
               "c": {"source_content_hash": "h", "extractor": "model-y", "prompt_version": "1"}}
    manifest = _manifest(*((sid, "included", {"content_hash": "h"}) for sid in "abc"))
    assert stale_records(records, manifest, schema) == ["b", "c"]
    assert stale_records(records, manifest) == []
    assert stale_records(records, manifest, _schema()) == []


def test_os_junk_files_in_extractions_ignored(tmp_path):
    _write(tmp_path, _record())
    for name in (".DS_Store", "Thumbs.db", "desktop.ini"):
        (tmp_path / name).write_bytes(b"\x00junk")
    records, problems = load_records(tmp_path, MANIFEST, _schema())
    assert problems == [] and "smith-2020" in records