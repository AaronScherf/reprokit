"""verify-sources: check that included sources' DOIs and OpenAlex ids exist. Free, anonymous, HEAD-only."""
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

import yaml

from .evidence_manifest import load_manifest
from .problems import Problem

_URLS = {"doi": "https://doi.org/", "openalex": "https://api.openalex.org/works/"}


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
        return 300 <= exc.code < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def verify_sources(manifest: dict, resolve: Callable[[dict], bool], path: str = "") -> list[Problem]:
    problems = []
    for source in manifest.get("sources", []):
        if source.get("screening_status") != "included":
            continue
        idents = [i for i in [source.get("identifier"), *(source.get("also") or [])]
                  if i and i.get("scheme") in _URLS]
        if idents and not any(resolve(i) for i in idents):
            problems.append(Problem(path, source["id"], f"The source '{source['id']}' has an identifier that could not be found online. Check the DOI or OpenAlex id for typos, or mark the source as excluded."))
    return problems


def verify_sources_command(repo_dir: Path) -> int:
    charter = {}
    charter_path = repo_dir / "project.yaml"
    if charter_path.is_file():
        charter = yaml.safe_load(charter_path.read_text(encoding="utf-8")) or {}
    rel = (charter.get("evidence") or {}).get("manifest", "evidence/manifest.yaml")
    manifest, problems = load_manifest(repo_dir / rel)
    if not problems:
        problems = verify_sources(manifest, default_resolver, str(repo_dir / rel))
    for problem in problems:
        print(problem)
    return 1 if problems else 0
