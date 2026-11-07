from pathlib import Path

import pytest
import yaml

from reprokit.cli import main
from reprokit.evidence_manifest import load_manifest
from reprokit.evidence_migrate import parse_review, review_to_manifest

SAMPLE = Path(__file__).parent / "fixtures" / "evidence" / "literature_review_sample.md"


def _text():
    return SAMPLE.read_text(encoding="utf-8")


def _by_id():
    doc = review_to_manifest(_text(), "2026-11-06")
    return {s["id"]: s for s in doc["sources"]}


def test_parse_two_papers():
    papers = parse_review(_text())
    assert len(papers) == 4
    assert papers[0]["title"] == "A Made-Up Study of Imaginary Wells"
    assert papers[0]["authors"] == ["Ana Okafor", "Bo Lee"]
    assert papers[0]["year"] == 2018


def test_doi_extracted_from_link():
    sources = _by_id()
    assert sources["okafor-2018"]["identifier"] == {"scheme": "doi", "value": "10.9999/example.1"}
    assert sources["okafor-2018-b"]["identifier"] == {"scheme": "openalex", "value": "W1234567890"}
    assert sources["obrien-lund-2019"]["identifier"]["scheme"] == "url"


def test_collision_gets_suffix():
    assert set(_by_id()) == {"okafor-2018", "okafor-2018-b", "obrien-lund-2019", "okafor-2018-c"}


def test_defaults_and_no_venue():
    s = _by_id()["okafor-2018"]
    assert (s["type"], s["access_class"], s["screening_status"], s["verification_status"]) == ("article", "unknown", "included", "proposed")
    assert s["retrieved_on"] == "2026-11-06" and s["year"] == 2018


def test_abstract_not_in_output():
    out = yaml.safe_dump(review_to_manifest(_text(), "2026-11-06"))
    assert "ZEBRA-ABSTRACT" not in out and "citations" not in out.lower()


def test_missing_author_uses_source_stem():
    text = "### <a id=\"paper-1\"></a>1. No Author Paper\n\n- **Publication Year:** 2020\n- **DOI / Link:** https://doi.org/10.9999/example.9\n"
    assert review_to_manifest(text, "2026-11-06")["sources"][0]["id"] == "source-2020"


def test_output_validates_against_manifest_schema(tmp_path):
    out = tmp_path / "manifest.yaml"
    assert main(["migrate-review", str(SAMPLE), "--out", str(out), "--retrieved-on", "2026-11-06"]) == 0
    manifest, problems = load_manifest(out)
    assert problems == [] and len(manifest["sources"]) == 4


def test_refuses_overwrite_without_force(tmp_path, capsys):
    out = tmp_path / "manifest.yaml"
    out.write_text("keep", encoding="utf-8")
    assert main(["migrate-review", str(SAMPLE), "--out", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "keep"
    assert "--force" in capsys.readouterr().out
    assert main(["migrate-review", str(SAMPLE), "--out", str(out), "--force"]) == 0
    assert out.read_text(encoding="utf-8") != "keep"


def test_zero_papers_writes_nothing(tmp_path, capsys):
    review = tmp_path / "empty.md"
    review.write_text("# nothing here\n", encoding="utf-8")
    out = tmp_path / "manifest.yaml"
    assert main(["migrate-review", str(review), "--out", str(out)]) == 1
    assert not out.exists()
    assert "paper" in capsys.readouterr().out
