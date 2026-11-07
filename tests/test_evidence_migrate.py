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


def test_parse_review_reads_title_authors_year():
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
    assert (s["type"], s["access_class"], s["screening_status"], s["verification_status"]) == ("article", "unknown", "candidate", "proposed")
    assert s["retrieved_on"] == "2026-11-06" and s["year"] == 2018


def test_status_included_is_explicit_opt_in(tmp_path):
    out = tmp_path / "manifest.yaml"
    assert main(["migrate-review", str(SAMPLE), "--out", str(out), "--status", "included"]) == 0
    manifest, problems = load_manifest(out, confidentiality="public")
    assert problems == [] and {s["screening_status"] for s in manifest["sources"]} == {"included"}
    assert {s["screening_status"] for s in review_to_manifest(_text(), "2026-11-06")["sources"]} == {"candidate"}
    with pytest.raises(SystemExit):
        main(["migrate-review", str(SAMPLE), "--out", str(out), "--force", "--status", "excluded"])


def test_abstract_not_in_output():
    out = yaml.safe_dump(review_to_manifest(_text(), "2026-11-06"))
    assert "ZEBRA-ABSTRACT" not in out and "citations" not in out.lower()


def test_missing_author_uses_source_stem():
    text = "### <a id=\"paper-1\"></a>1. No Author Paper\n\n- **Publication Year:** 2020\n- **DOI / Link:** https://doi.org/10.9999/example.9\n"
    assert review_to_manifest(text, "2026-11-06")["sources"][0]["id"] == "source-2020"


def test_output_validates_against_manifest_schema(tmp_path):
    out = tmp_path / "manifest.yaml"
    assert main(["migrate-review", str(SAMPLE), "--out", str(out), "--retrieved-on", "2026-11-06"]) == 0
    manifest, problems = load_manifest(out, confidentiality="public")
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


def _one(link):
    text = f"### 1. T\n\n- **Authors:** A Smith\n- **Publication Year:** 2020\n- **DOI / Link:** {link}\n"
    return review_to_manifest(text, "2026-11-06")["sources"]


@pytest.mark.parametrize("link", [
    "[https://doi.org/10.9999/S0000-0000(20)00000-5](https://doi.org/10.9999/S0000-0000(20)00000-5)",
    "https://doi.org/10.9999/S0000-0000(20)00000-5",
    "https://dx.doi.org/10.9999/S0000-0000(20)00000-5.",
    "https://DOI.org/10.9999/S0000-0000(20)00000-5",
    "10.9999/S0000-0000(20)00000-5",
])
def test_parenthesised_and_bare_dois(link):
    assert _one(link)[0]["identifier"] == {"scheme": "doi", "value": "10.9999/S0000-0000(20)00000-5"}


def test_trailing_period_stripped_in_markdown_link():
    assert _one("[x](https://doi.org/10.9999/example.1.)")[0]["identifier"]["value"] == "10.9999/example.1"


def test_skipped_papers_warn_and_exit_zero(tmp_path, capsys):
    review = tmp_path / "r.md"
    review.write_text("### 1. Has Link\n\n- **Authors:** A Smith\n- **Publication Year:** 2020\n- **DOI / Link:** 10.9999/example.1\n\n"
                      "### 2. No Link\n\n- **Authors:** B Jones\n- **Publication Year:** 2020\n- **DOI / Link:** N/A\n", encoding="utf-8")
    out = tmp_path / "m.yaml"
    assert main(["migrate-review", str(review), "--out", str(out)]) == 0
    err = capsys.readouterr().err
    assert "Skipped 'No Link': no DOI / Link found; add it to the manifest by hand" in err
    assert "1 skipped" in err
    assert len(load_manifest(out, confidentiality="public")[0]["sources"]) == 1


def test_all_skipped_exits_one_and_writes_nothing(tmp_path, capsys):
    review = tmp_path / "r.md"
    review.write_text("### 1. No Link\n\n- **Authors:** B Jones\n- **DOI / Link:** N/A\n", encoding="utf-8")
    out = tmp_path / "m.yaml"
    assert main(["migrate-review", str(review), "--out", str(out)]) == 1
    assert not out.exists()
    assert "Skipped 'No Link'" in capsys.readouterr().err


def test_many_collisions_stay_valid(tmp_path):
    block = "### {n}. Paper {n}\n\n- **Authors:** A Smith\n- **Publication Year:** 2020\n- **DOI / Link:** 10.9999/example.{n}\n\n"
    review = tmp_path / "r.md"
    review.write_text("".join(block.format(n=n) for n in range(28)), encoding="utf-8")
    out = tmp_path / "m.yaml"
    assert main(["migrate-review", str(review), "--out", str(out)]) == 0
    manifest, problems = load_manifest(out, confidentiality="public")
    ids = [s["id"] for s in manifest["sources"]]
    assert problems == [] and len(set(ids)) == 28 and ids[25] == "smith-2020-z" and ids[26] == "smith-2020-27"


DOI = {"scheme": "doi", "value": "10.9999/example.1"}


@pytest.mark.parametrize("link", [
    "(https://doi.org/10.9999/example.1)",
    "[a](https://doi.org/10.9999/example.1) [b](https://example.invalid/two)",
    "[a](https://example.invalid/one) [b](https://doi.org/10.9999/example.1)",
    "[x](https://doi.org/10.9999/example.1) (open access)",
    "[a] b](https://doi.org/10.9999/example.1)",
    "[[x]](https://doi.org/10.9999/example.1)",
])
def test_link_scanner_variants(link):
    assert _one(link)[0]["identifier"] == DOI


def test_parenthesised_doi_with_trailing_text():
    link = "[x](https://doi.org/10.9999/S0000-0000(20)00000-5) (open access)"
    assert _one(link)[0]["identifier"]["value"] == "10.9999/S0000-0000(20)00000-5"


def test_openalex_preferred_over_plain_url():
    link = "[a](https://example.invalid/one) [b](https://openalex.org/W42)"
    assert _one(link)[0]["identifier"] == {"scheme": "openalex", "value": "W42"}


@pytest.mark.parametrize("link", ["[x](https://doi.org/10.9999/S0000(20", "https://doi.org/10.9999/S0000(20"])
def test_unmatched_paren_is_skipped_with_warning(tmp_path, capsys, link):
    review = tmp_path / "r.md"
    review.write_text(f"### 1. Odd\n\n- **Authors:** A Smith\n- **DOI / Link:** {link}\n", encoding="utf-8")
    assert main(["migrate-review", str(review), "--out", str(tmp_path / "m.yaml")]) == 1
    assert "Skipped 'Odd'" in capsys.readouterr().err
