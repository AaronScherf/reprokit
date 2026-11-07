import http.client
import urllib.error

import pytest
import yaml

from reprokit import evidence_verify
from reprokit.cli import main
from reprokit.evidence_verify import SourceUnreachable, default_resolver, verify_sources


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


def _raise(exc):
    def f(req):
        raise exc
    return f


@pytest.mark.parametrize("code", [404, 410])
def test_not_found_statuses_return_false(monkeypatch, code):
    monkeypatch.setattr(evidence_verify, "_open", _raise(urllib.error.HTTPError("u", code, "x", {}, None)))
    assert default_resolver({"scheme": "doi", "value": "10.1/a"}) is False


@pytest.mark.parametrize("exc", [urllib.error.HTTPError("u", c, "x", {}, None) for c in (403, 429, 503)]
                         + [urllib.error.URLError("down"), TimeoutError("timeout"), http.client.RemoteDisconnected("x")])
def test_other_failures_raise_unreachable(monkeypatch, exc):
    monkeypatch.setattr(evidence_verify, "_open", _raise(exc))
    with pytest.raises(SourceUnreachable):
        default_resolver({"scheme": "doi", "value": "10.1/a"})


def _unreachable(ident):
    raise SourceUnreachable("timeout")


def test_unreachable_reported_distinctly_without_typo_advice():
    problems = verify_sources({"sources": [_src("a")]}, _unreachable)
    assert len(problems) == 1
    assert "network or server problem" in problems[0].message and "timeout" in problems[0].message
    assert "typos" not in problems[0].message


def test_cli_unreachable_exits_nonzero(tmp_path, monkeypatch, capsys):
    (tmp_path / "evidence").mkdir()
    full = dict(_src("a"), type="article", title="T", access_class="open", verification_status="proposed")
    (tmp_path / "evidence" / "manifest.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": [full]}), encoding="utf-8")
    monkeypatch.setattr(evidence_verify, "default_resolver", _unreachable)
    assert main(["verify-sources", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "network or server problem" in out and "typos" not in out


def test_cli_prints_restricted_source_warning_to_stderr(tmp_path, monkeypatch, capsys):
    (tmp_path / "evidence").mkdir()
    full = dict(_src("r"), type="article", title="T", access_class="restricted", verification_status="proposed")
    (tmp_path / "evidence" / "manifest.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": [full]}), encoding="utf-8")
    monkeypatch.setattr(evidence_verify, "default_resolver", lambda ident: True)
    assert main(["verify-sources", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert "restricted" not in captured.out
    assert "'r' is marked restricted" in captured.err and captured.err.rstrip().endswith("[warning]")

def test_failure_message_names_every_identifier_tried():
    src = _src("a", also=[{"scheme": "openalex", "value": "W9"}])
    problems = verify_sources({"sources": [src]}, lambda ident: False)
    assert "doi:10.1/a" in problems[0].message and "openalex:W9" in problems[0].message


def test_unreachable_message_names_identifiers_tried():
    problems = verify_sources({"sources": [_src("a")]}, _unreachable)
    assert "doi:10.1/a" in problems[0].message


def test_primary_unresolved_but_also_resolved_passes_with_warning():
    src = _src("a", value="10.1/typo", also=[{"scheme": "openalex", "value": "W9"}])
    warnings = []
    problems = verify_sources({"sources": [src]}, lambda ident: ident["scheme"] == "openalex", warnings=warnings)
    assert problems == []
    assert len(warnings) == 1 and warnings[0].location == "a"
    assert warnings[0].message == "primary identifier doi:10.1/typo of 'a' did not resolve; openalex:W9 did"


def test_primary_resolved_gives_no_warning():
    warnings = []
    src = _src("a", also=[{"scheme": "openalex", "value": "W9"}])
    assert verify_sources({"sources": [src]}, lambda ident: True, warnings=warnings) == []
    assert warnings == []


@pytest.mark.parametrize("value", ["W123", "w123", "https://openalex.org/W123", "https://api.openalex.org/works/w123"])
def test_openalex_forms_accepted_and_stripped(value):
    seen = []
    assert verify_sources({"sources": [_src("a", "openalex", value)]}, lambda i: seen.append(i["value"]) or True) == []
    assert seen == ["W123"]


@pytest.mark.parametrize("value", ["123", "W12x", "https://example.org/W123", "A123", "https://openalex.org/works/W1/extra"])
def test_invalid_openalex_reported_without_request(value):
    seen = []
    problems = verify_sources({"sources": [_src("a", "openalex", value)]}, lambda i: seen.append(i) or True)
    assert seen == []
    assert len(problems) == 1 and "not a valid OpenAlex id" in problems[0].message
    assert "Try again later" not in problems[0].message and f"openalex:{value}" in problems[0].message


def test_default_resolver_rejects_invalid_openalex_without_request(monkeypatch):
    monkeypatch.setattr(evidence_verify, "_open", lambda req: (_ for _ in ()).throw(AssertionError("network")))
    with pytest.raises(ValueError, match="not a valid OpenAlex id"):
        default_resolver({"scheme": "openalex", "value": "nope"})


def test_value_error_is_invalid_identifier_not_unreachable(monkeypatch):
    monkeypatch.setattr(evidence_verify, "_open", _raise(ValueError("unknown url type")))
    with pytest.raises(ValueError):
        default_resolver({"scheme": "doi", "value": "10.1/a"})

    def bad(ident):
        raise ValueError("malformed")

    problems = verify_sources({"sources": [_src("a")]}, bad)
    assert len(problems) == 1 and "invalid identifier" in problems[0].message
    assert "network or server problem" not in problems[0].message


def _write_repo(tmp_path, sources):
    (tmp_path / "evidence").mkdir()
    full = [dict(s, type="article", title="T", access_class="open", verification_status="proposed") for s in sources]
    (tmp_path / "evidence" / "manifest.yaml").write_text(yaml.safe_dump({"schema_version": "0.1.0", "sources": full}), encoding="utf-8")


def test_cli_prints_summary_line_on_clean_run(tmp_path, monkeypatch, capsys):
    _write_repo(tmp_path, [_src("a"), _src("b"), _src("u", "url", "https://x.org"),
                           _src("f", "file_hash", "ab"), _src("x", status="excluded")])
    monkeypatch.setattr(evidence_verify, "default_resolver", lambda ident: True)
    assert main(["verify-sources", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "checked 2 sources (2 skipped: file_hash, url)"


def test_cli_summary_without_skips_and_after_problems(tmp_path, monkeypatch, capsys):
    _write_repo(tmp_path, [_src("a")])
    monkeypatch.setattr(evidence_verify, "default_resolver", lambda ident: False)
    assert main(["verify-sources", str(tmp_path)]) == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == "checked 1 sources (0 skipped)"


def test_cli_prints_primary_warning_to_stderr(tmp_path, monkeypatch, capsys):
    _write_repo(tmp_path, [_src("a", value="10.1/typo", also=[{"scheme": "doi", "value": "10.1/ok"}])])
    monkeypatch.setattr(evidence_verify, "default_resolver", lambda ident: ident["value"] == "10.1/ok")
    assert main(["verify-sources", str(tmp_path)]) == 0
    err = capsys.readouterr().err
    assert "primary identifier doi:10.1/typo of 'a' did not resolve; doi:10.1/ok did" in err and "[warning]" in err


def test_no_redirect_handler_refuses_to_follow():
    import email.message
    import io
    import urllib.request

    req = urllib.request.Request("https://doi.org/10.1/a", method="HEAD")
    handler = evidence_verify._NoRedirect()
    assert handler.redirect_request(req, io.BytesIO(), 302, "Found", email.message.Message(), "https://publisher.example/a") is None


def test_real_opener_surfaces_3xx_as_resolved(monkeypatch):
    import email.message
    import io
    import urllib.request

    calls = []

    class FakeHTTPS(urllib.request.HTTPSHandler):
        def https_open(self, req):
            calls.append(req.full_url)
            headers = email.message.Message()
            headers["Location"] = "https://publisher.example/a"
            resp = urllib.response.addinfourl(io.BytesIO(b""), headers, req.full_url, code=302)
            resp.msg = "Found"
            return resp

    real = urllib.request.build_opener
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: real(*handlers, FakeHTTPS))
    assert default_resolver({"scheme": "doi", "value": "10.1/a"}) is True
    assert calls == ["https://doi.org/10.1/a"]  # the redirect was not followed


@pytest.mark.parametrize("primary_invalid", [True, False])
def test_invalid_openalex_reported_even_when_another_identifier_resolves(primary_invalid):
    bad = {"scheme": "openalex", "value": "not-an-id"}
    src = _src("a", also=[bad]) if not primary_invalid else _src("a", "openalex", "not-an-id", also=[{"scheme": "doi", "value": "10.1/ok"}])
    problems = verify_sources({"sources": [src]}, lambda ident: ident["scheme"] == "doi")
    assert len(problems) == 1 and "not a valid OpenAlex id" in problems[0].message
