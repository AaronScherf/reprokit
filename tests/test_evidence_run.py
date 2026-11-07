from pathlib import Path

import yaml

from reprokit.cli import main
from reprokit.evidence_run import aggregate, delta

FIXTURES = Path(__file__).parent / "fixtures" / "evidence"
SCHEMA = yaml.safe_load((FIXTURES / "extraction_schema_ok.yaml").read_text(encoding="utf-8"))


def _source(sid, status="included"):
    return {"id": sid, "type": "article", "identifier": {"scheme": "doi", "value": f"10.0/{sid}"}, "title": "T",
            "access_class": "open", "screening_status": status, "verification_status": "proposed"}


def _record(sid, size, uses_rct, countries, usd=0.5):
    return {"source_id": sid, "extractor": "m", "prompt_version": "1", "source_content_hash": "h", "cost": {"usd": usd},
            "fields": {"sample_size": size, "uses_rct": uses_rct, "outcome": "x", "countries": countries}, "locators": {}}


MANIFEST = {"sources": [_source("a"), _source("b"), _source("c", "excluded")]}
RECORDS = {
    "a": _record("a", 100, True, ["KE", "UG"]),
    "b": _record("b", 50, False, ["KE", "TZ"]),
    "c": _record("c", 999, True, ["ZZ"]),
}


def test_aggregate_counts_sums_and_merges_lists():
    out = aggregate(MANIFEST, RECORDS, SCHEMA)
    assert out["sources"] == ["a", "b"]
    assert out["fields"] == {"sample_size": 150, "uses_rct": 1, "countries": ["KE", "TZ", "UG"]}
    assert out["cost_usd"] == 1.0


def test_exclude_removes_a_source_and_delta_shows_it():
    full = aggregate(MANIFEST, RECORDS, SCHEMA)
    sub = aggregate(MANIFEST, RECORDS, SCHEMA, exclude={"b"})
    assert sub["sources"] == ["a"]
    d = delta(full, sub)
    assert d["removed"] == ["b"]
    assert d["fields"]["sample_size"] == -50
    assert d["fields"]["uses_rct"] == 0
    assert d["fields"]["countries"] == {"removed": ["TZ"], "added": []}


def test_only_restricts_to_listed_ids():
    assert aggregate(MANIFEST, RECORDS, SCHEMA, only={"b"})["fields"]["sample_size"] == 50


def test_adding_a_source_needs_only_its_record():
    old = aggregate(MANIFEST, RECORDS, SCHEMA)
    manifest = {"sources": MANIFEST["sources"] + [_source("d")]}
    records = {**RECORDS, "d": _record("d", 10, True, ["ET"], usd=0.25)}
    new = aggregate(manifest, records, SCHEMA)
    assert new["fields"]["sample_size"] == old["fields"]["sample_size"] + 10
    assert new["fields"]["uses_rct"] == old["fields"]["uses_rct"] + 1
    assert new["fields"]["countries"] == sorted(old["fields"]["countries"] + ["ET"])
    assert new["cost_usd"] == old["cost_usd"] + 0.25


def _repo(tmp_path):
    (tmp_path / "evidence" / "extractions").mkdir(parents=True)
    (tmp_path / "evidence" / "manifest.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": [_source("a"), _source("b")]}), encoding="utf-8")
    (tmp_path / "evidence" / "extraction_schema.yaml").write_text((FIXTURES / "extraction_schema_ok.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    for sid, rec in (("a", _record("a", 100, True, ["KE"])), ("b", _record("b", 50, False, ["UG"]))):
        (tmp_path / "evidence" / "extractions" / f"{sid}.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")
    return tmp_path


def test_unknown_id_in_exclude_fails_with_clear_message(tmp_path, capsys):
    repo = _repo(tmp_path)
    assert main(["evidence-run", str(repo), "--exclude", "nope"]) == 1
    assert "nope" in capsys.readouterr().out
    assert not (repo / "outputs" / "evidence_aggregate.yaml").exists()


def test_cli_writes_output_file(tmp_path, capsys):
    repo = _repo(tmp_path)
    assert main(["evidence-run", str(repo)]) == 0
    out = yaml.safe_load((repo / "outputs" / "evidence_aggregate.yaml").read_text(encoding="utf-8"))
    assert out["aggregate"]["fields"]["sample_size"] == 150
    assert main(["evidence-run", str(repo), "--exclude", "b"]) == 0
    out = yaml.safe_load((repo / "outputs" / "evidence_aggregate.yaml").read_text(encoding="utf-8"))
    assert out["delta"]["removed"] == ["b"]
    assert out["aggregate"]["fields"]["sample_size"] == 100


def test_selected_source_without_record_fails_and_writes_nothing(tmp_path, capsys):
    repo = _repo(tmp_path)
    (repo / "evidence" / "extractions" / "b.yaml").unlink()
    assert main(["evidence-run", str(repo)]) == 1
    out = capsys.readouterr().out
    assert "'b'" in out and "evidence/extractions/b.yaml" in out and "--exclude" in out
    assert not (repo / "outputs" / "evidence_aggregate.yaml").exists()


def test_source_without_record_can_be_excluded_or_left_out(tmp_path):
    repo = _repo(tmp_path)
    (repo / "evidence" / "extractions" / "b.yaml").unlink()
    assert main(["evidence-run", str(repo), "--exclude", "b"]) == 0
    assert main(["evidence-run", str(repo), "--only", "a"]) == 0
