import urllib.error

import yaml

from reprokit import evidence_verify
from reprokit.cli import main
from reprokit.evidence_verify import default_resolver, verify_sources


def _src(sid, scheme="doi", value=None, status="included", also=None):
    s = {"id": sid, "identifier": {"scheme": scheme, "value": value or f"10.1/{sid}"}, "screening_status": status}
    if also:
        s["also"] = also
    return s


def test_unresolvable_included_entry_reported():
    problems = verify_sources({"sources": [_src("a"), _src("b")]}, lambda ident: ident["value"] != "10.1/b")
    assert [p.location for p in problems] == ["b"]
    assert "Check" in problems[0].message


def test_excluded_entries_not_checked():
    seen = []
    verify_sources({"sources": [_src("a", status="excluded")]}, lambda i: seen.append(i) or False)
    assert seen == []


def test_non_doi_schemes_skipped():
    seen = []
    m = {"sources": [_src("u", "url", "https://x.org"), _src("f", "file_hash", "ab"), _src("d", "dataset_doi", "10.5/x")]}
    assert verify_sources(m, lambda i: seen.append(i) or False) == []
    assert seen == []


def test_cli_exits_nonzero_on_unresolved(tmp_path, monkeypatch, capsys):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "manifest.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": [dict(_src("a"), type="article", title="T", access_class="open", verification_status="proposed")]}), encoding="utf-8")
    (tmp_path / "project.yaml").write_text("kind: evidence\n", encoding="utf-8")
    monkeypatch.setattr(evidence_verify, "default_resolver", lambda ident: False)
    assert main(["verify-sources", str(tmp_path)]) == 1
    assert "a" in capsys.readouterr().out
    monkeypatch.setattr(evidence_verify, "default_resolver", lambda ident: True)
    assert main(["verify-sources", str(tmp_path)]) == 0


def test_default_resolver_url_and_headers(monkeypatch):
    calls = []

    class Resp:
        status = 200

    monkeypatch.setattr(evidence_verify, "_open", lambda req: calls.append(req) or Resp())
    assert default_resolver({"scheme": "doi", "value": "10.1002/(SICI)1097 <x>#1"})
    req = calls[0]
    assert req.full_url == "https://doi.org/10.1002/%28SICI%291097%20%3Cx%3E%231"
    assert req.get_method() == "HEAD"
    assert req.get_header("User-agent") == "reprokit-verify-sources"
    assert default_resolver({"scheme": "openalex", "value": "W123"})
    assert calls[1].full_url == "https://api.openalex.org/works/W123"


def test_default_resolver_refuses_other_scheme(monkeypatch):
    monkeypatch.setattr(evidence_verify, "_open", lambda req: (_ for _ in ()).throw(AssertionError("network")))
    assert default_resolver({"scheme": "url", "value": "https://evil.example"}) is False


def test_default_resolver_status_handling(monkeypatch):
    def err(code):
        def f(req):
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)
        return f
    monkeypatch.setattr(evidence_verify, "_open", err(302))
    assert default_resolver({"scheme": "doi", "value": "10.1/a"}) is True
    monkeypatch.setattr(evidence_verify, "_open", err(404))
    assert default_resolver({"scheme": "doi", "value": "10.1/a"}) is False
    monkeypatch.setattr(evidence_verify, "_open", lambda req: (_ for _ in ()).throw(urllib.error.URLError("down")))
    assert default_resolver({"scheme": "doi", "value": "10.1/a"}) is False
