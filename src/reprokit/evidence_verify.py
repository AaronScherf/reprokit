"""verify-sources: check that included sources' DOIs and OpenAlex ids exist. Free, anonymous, HEAD-only."""
import http.client
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from .evidence_cli import warn
from .evidence_manifest import load_manifest, load_repo_charter, manifest_path, manifest_warnings
from .problems import Problem

_URLS = {"doi": "https://doi.org/", "openalex": "https://api.openalex.org/works/"}


class SourceUnreachable(Exception):
    """The check could not be made (network or server problem); the identifier was not judged."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # never follow: a redirect from doi.org already proves the DOI exists


def _open(req):
    return urllib.request.build_opener(_NoRedirect).open(req, timeout=10)


def default_resolver(identifier: dict) -> bool:
    base = _URLS.get(identifier.get("scheme"))
    if base is None:
        return False
    url = base + urllib.parse.quote(str(identifier.get("value", "")), safe="/")
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
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as exc:
        raise SourceUnreachable(str(getattr(exc, "reason", None) or exc) or type(exc).__name__) from exc


def verify_sources(manifest: dict, resolve: Callable[[dict], bool], path: str = "") -> list[Problem]:
    problems = []
    for source in manifest.get("sources", []):
        if source.get("screening_status") != "included":
            continue
        idents = [i for i in [source.get("identifier"), *(source.get("also") or [])]
                  if i and i.get("scheme") in _URLS]
        found, reasons = False, []
        for ident in idents:
            try:
                found = found or resolve(ident)
            except SourceUnreachable as exc:
                reasons.append(str(exc))
        if not idents or found:
            continue
        sid = source["id"]
        if reasons:
            problems.append(Problem(path, sid, f"Could not reach doi.org or api.openalex.org to check '{sid}' ({reasons[0]}). This is a network or server problem, so the identifier was not judged. Try again later."))
        else:
            problems.append(Problem(path, sid, f"The source '{sid}' has an identifier that could not be found online. Check the DOI or OpenAlex id for typos, or mark the source as excluded."))
    return problems


def verify_sources_command(repo_dir: Path) -> int:
    charter, problems = load_repo_charter(repo_dir)
    path, more = manifest_path(repo_dir, charter)
    problems += more
    if not problems:
        # No charter: apply the strictest (public) rules.
        confidentiality = (charter or {}).get("confidentiality", "public")
        manifest, problems = load_manifest(path, confidentiality=confidentiality)
    if not problems:
        warn(manifest_warnings(manifest, str(path), confidentiality))
        problems = verify_sources(manifest, default_resolver, str(path))
    for problem in problems:
        print(problem)
    return 1 if problems else 0
