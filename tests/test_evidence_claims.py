import pytest

from reprokit.evidence_claims import check_claims, extract_markers


def _manifest(*entries):
    return {"sources": [{"id": i, "screening_status": s, "verification_status": v} for i, s, v in entries]}


OK = _manifest(("a-1", "included", "source-verified"), ("b-2", "included", "fixture-tested"))


def test_unknown_marker_reported_with_line():
    problems = check_claims("Intro\n\nClaim [@ghost-9].\n", OK, "synthesis.md")
    assert len(problems) == 1
    assert problems[0].location == "line 3"
    assert "ghost-9" in problems[0].message


def test_multi_citation_marker_resolves_both():
    text = "Both [@a-1; @b-2] agree.\n"
    assert extract_markers(text) == [(1, "a-1"), (1, "b-2")]
    assert check_claims(text, OK, "s.md") == []
    bad = check_claims("x [@a-1; @nope].", OK, "s.md")
    assert len(bad) == 1 and "nope" in bad[0].message


def test_crlf_text_resolves():
    text = "one\r\ntwo [@a-1]\r\nthree [@b-2]\r\n"
    assert extract_markers(text) == [(2, "a-1"), (3, "b-2")]
    assert check_claims(text, OK, "s.md") == []


def test_excluded_and_proposed_entries_reported_with_id():
    m = _manifest(("ex", "excluded", "source-verified"), ("cand", "candidate", "source-verified"),
                  ("prop", "included", "proposed"))
    problems = check_claims("[@ex]\n[@cand]\n[@prop]\n", m, "s.md")
    assert [p.location for p in problems] == ["line 1", "line 2", "line 3"]
    for p, sid in zip(problems, ["ex", "cand", "prop"]):
        assert sid in p.message


def test_text_without_markers_has_no_problems():
    assert check_claims("No citations. Email a@b.com [link](x) [ref]\n", OK, "s.md") == []
    m = _manifest(("unused", "included", "proposed"))
    assert check_claims("nothing", m, "s.md") == []


@pytest.mark.parametrize("marker", ["[@a-1, @b-2]", "[@smith 2020]", "[@ smith-2020]", "[@]", "[@a-1;]"])
def test_malformed_marker_reported(marker):
    problems = check_claims(f"Intro\n\nClaim {marker}.\n", OK, "s.md")
    assert [p.message for p in problems] == [f"malformed citation marker '{marker}' on line 3; write [@id] or [@id1; @id2]"]
    assert problems[0].location == "line 3"


def test_markers_in_code_are_ignored():
    text = ("Use `[@smith-2020]` or ``[@a, @b]`` as shown.\n"
            "```\n[@ghost] [@smith 2020]\n```\n"
            "~~~markdown\n[@ghost]\n~~~\n"
            "Real [@a-1].\n")
    assert extract_markers(text) == [(8, "a-1")]
    assert check_claims(text, OK, "s.md") == []


def test_malformed_marker_line_with_crlf_and_after_code_block():
    text = "```\r\nx\r\n```\r\none [@a-1]\r\ntwo [@a-1, @b-2]\r\n"
    problems = check_claims(text, OK, "s.md")
    assert [p.location for p in problems] == ["line 5"]


def test_problems_are_ordered_by_line():
    problems = check_claims("[@ghost]\n[@bad id]\n[@ghost2]\n", OK, "s.md")
    assert [p.location for p in problems] == ["line 1", "line 2", "line 3"]