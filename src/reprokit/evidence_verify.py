"""verify-sources: check that included sources' DOIs and OpenAlex ids exist. Free, anonymous, HEAD-only."""
import http.client
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .evidence_cli import warn
from .evidence_manifest import (
    load_manifest,
    load_repo_charter,
    manifest_path,
    manifest_warnings,
)
from .problems import Problem

_URLS = {"doi": "https://doi.org/", "openalex": "https://api.openalex.org/works/"}
_OPENALEX = re.compile(r"(?:https://(?:api\.)?openalex\.org/(?:works/)?)?[Ww](\d+)", re.IGNORECASE)


class SourceUnreachable(Exception):
    """The check could not be made (network or server problem); the identifier was not judged."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # never follow: a redirect from doi.org already proves the DOI exists


def _open(req):
    return urllib.request.build_opener(_NoRedirect).open(req, timeout=10)


def openalex_id(value) -> str:
    """W<digits>, or a full openalex.org / api.openalex.org/works URL, as the bare W-id; ValueError otherwise."""
    match = _OPENALEX.fullmatch(str(value).strip())
    if not match:
        raise ValueError("not a valid OpenAlex id (use W followed by digits, e.g. W2741809807)")
    return "W" + match.group(1)


def default_resolver(identifier: dict) -> bool:
    scheme = identifier.get("scheme")
    if scheme not in _URLS:
        return False
    value = str(identifier.get("value", ""))
    if scheme == "openalex":
        value = openalex_id(value)
    url = _URLS[scheme] + urllib.parse.quote(value, safe="/")
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "reprokit-verify-sources"})
    try:
        _open(req)
        return True
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            return True
        if exc.code in (404, 410):
            return False
        raise SourceUnreachable(f"HTTP {exc.code}") from exc
    except ValueError:
        raise  # a malformed identifier, not a network problem
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        raise SourceUnreachable(str(getattr(exc, "reason", None) or exc) or type(exc).__name__) from exc


def _label(ident: dict) -> str:
    return f"{ident.get('scheme')}:{ident.get('value')}"


def _outcome(ident: dict, resolve: Callable[[dict], bool]) -> tuple[str, str]:
    """('found' | 'missing' | 'unreachable' | 'invalid', detail)."""
    try:
        if ident["scheme"] == "openalex":
            ident = dict(ident, value=openalex_id(ident.get("value", "")))
        return ("found" if resolve(ident) else "missing"), ""
    except SourceUnreachable as exc:
        return "unreachable", str(exc)
    except ValueError as exc:
        return "invalid", str(exc) or "malformed"


def _checkable(source: dict) -> list[dict]:
    return [i for i in [source.get("identifier"), *(source.get("also") or [])] if i and i.get("scheme") in _URLS]


def verify_sources(manifest: dict, resolve: Callable[[dict], bool], path: str = "",
                   warnings: list[Problem] | None = None) -> list[Problem]:
    """Problems for included sources none of whose identifiers resolve; a resolved `also` id behind an
    unresolved primary adds a warning to `warnings` (when given)."""
    problems = []
    for source in manifest.get("sources", []):
        if source.get("screening_status") != "included":
            continue
        sid, tried = source["id"], []
        for ident in _checkable(source):
            outcome, detail = _outcome(ident, resolve)
            if outcome == "found":
                if tried and tried[0][0] is source.get("identifier") and warnings is not None:
                    warnings.append(Problem(path, sid, f"primary identifier {_label(tried[0][0])} of '{sid}' did not resolve; {_label(ident)} did"))
                break
            tried.append((ident, outcome, detail))
        else:
            if tried:
                problems.append(_failure(path, sid, tried))
    return problems


def _failure(path: str, sid: str, tried: list) -> Problem:
    names = ", ".join(_label(i) for i, _, _ in tried)
    invalid = [f"{_label(i)}: {d}" for i, o, d in tried if o == "invalid"]
    if invalid:
        return Problem(path, sid, f"The source '{sid}' has an invalid identifier ({'; '.join(invalid)}). Fix the value in the manifest: a DOI looks like 10.1234/abc, an OpenAlex id like W2741809807.")
    reasons = [d for _, o, d in tried if o == "unreachable"]
    if reasons:
        return Problem(path, sid, f"Could not reach doi.org or api.openalex.org to check '{sid}' (tried {names}; {reasons[0]}). This is a network or server problem, so the identifier was not judged. Try again later.")
    return Problem(path, sid, f"The source '{sid}' has no identifier that could be found online (tried {names}). Check the DOI or OpenAlex id for typos, or mark the source as excluded.")


def summary(manifest: dict) -> str:
    included = [s for s in manifest.get("sources", []) if s.get("screening_status") == "included"]
    skipped = [s for s in included if not _checkable(s)]
    line = f"checked {len(included) - len(skipped)} sources ({len(skipped)} skipped"
    schemes = sorted({str((s.get("identifier") or {}).get("scheme")) for s in skipped})
    return line + (f": {', '.join(schemes)})" if skipped else ")")


def verify_sources_command(repo_dir: Path) -> int:
    charter, problems = load_repo_charter(repo_dir)
    path, more = manifest_path(repo_dir, charter)
    problems += more
    if not problems:
        # No charter: apply the strictest (public) rules.
        confidentiality = (charter or {}).get("confidentiality", "public")
        manifest, problems = load_manifest(path, confidentiality=confidentiality)
    if problems:
        for problem in problems:
            print(problem)
        return 1
    warnings = manifest_warnings(manifest, str(path), confidentiality)
    problems = verify_sources(manifest, default_resolver, str(path), warnings=warnings)
    warn(warnings)
    for problem in problems:
        print(problem)
    print(summary(manifest))
    return 1 if problems else 0
