"""Turn a literature_review.md into an evidence manifest (abstracts and citation counts are dropped)."""
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .problems import Problem

_HEADING = re.compile(r"^### (?:<a id=\"[^\"]*\"></a>)?\s*(?:\d+\.\s*)?(.+?)\s*$")
_FIELD = re.compile(r"^- \*\*(.+?):\*\*\s*(.*?)\s*$")
_BARE = re.compile(r"https?://\S+|10\.\d{4,9}/\S+")
_DOI = re.compile(r"doi\.org/(10\.\S+)$", re.IGNORECASE)
_OPENALEX = re.compile(r"openalex\.org/(?:works/)?(W\d+)", re.IGNORECASE)


def parse_review(text: str) -> list[dict]:
    papers, current = [], None
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            current = {"title": heading.group(1), "authors": [], "year": None, "link": None}
            papers.append(current)
            continue
        field = _FIELD.match(line)
        if not (field and current):
            continue
        name, value = field.group(1).lower(), field.group(2)
        if name == "authors":
            current["authors"] = [a.strip() for a in value.split(",") if a.strip()]
        elif name == "publication year" and re.fullmatch(r"\d{4}", value):
            current["year"] = int(value)
        elif name.startswith("doi"):
            current["link"] = _link(value)
    return papers


def _targets(value: str) -> list[str]:
    """URLs of every markdown link on the line; inner balanced parentheses survive."""
    found, pos = [], 0
    while (start := value.find("](", pos)) != -1:
        depth, i = 1, start + 2
        while i < len(value) and depth:
            depth += {"(": 1, ")": -1}.get(value[i], 0)
            i += 1
        if depth == 0:
            found.append(value[start + 2:i - 1].strip())
        pos = start + 2
    return found


def _clean_bare(token: str) -> str:
    token = token.rstrip(".,;:")
    while token.endswith(")") and token.count(")") > token.count("("):
        token = token[:-1].rstrip(".,;:")
    return token


def _host_rank(candidate: str) -> int:
    host = urlparse(candidate).hostname or ""
    if host in ("doi.org", "dx.doi.org", "www.doi.org"):
        return 0
    return 1 if host.endswith("openalex.org") else 2


def _link(value: str) -> str | None:
    candidates = [t.rstrip(".,;") for t in _targets(value)]
    if not candidates:
        candidates = [_clean_bare(t) for t in _BARE.findall(value)]
    candidates = [c for c in candidates if c]
    return min(candidates, key=_host_rank) if candidates else None  # min is stable: first wins ties


def _identifier(link: str | None) -> dict | None:
    if not link:
        return None
    if m := _DOI.search(link):
        ident = {"scheme": "doi", "value": m.group(1)}
    elif m := _OPENALEX.search(link):
        ident = {"scheme": "openalex", "value": m.group(1)}
    elif re.match(r"10\.\d{4,9}/\S+$", link):
        ident = {"scheme": "doi", "value": link}
    else:
        ident = {"scheme": "url", "value": link}
    return ident if _balanced(ident["value"]) and not re.search(r"\s", ident["value"]) else None


def _balanced(value: str) -> bool:
    depth = 0
    for ch in value:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if depth < 0:
            return False
    return depth == 0


def _slug(authors: list[str], year: int | None) -> str:
    surname = authors[0].split()[-1] if authors else "source"
    ascii_name = unicodedata.normalize("NFKD", surname).encode("ascii", "ignore").decode().lower()
    stem = re.sub(r"[^a-z0-9_-]", "", ascii_name).lstrip("-_") or "source"
    return f"{stem}-{year}" if year else stem


def _convert(text: str, retrieved_on: str, status: str) -> tuple[list[dict], list[str]]:
    sources, skipped, used = [], [], {}
    for paper in parse_review(text):
        ident = _identifier(paper["link"])
        if not ident:
            skipped.append(paper["title"])
            continue
        base = _slug(paper["authors"], paper["year"])
        used[base] = used.get(base, 0) + 1
        sid = base if used[base] == 1 else (f"{base}-{chr(ord('a') + used[base] - 1)}" if used[base] <= 26 else f"{base}-{used[base]}")
        source = {"id": sid, "type": "article", "identifier": ident, "title": paper["title"]}
        if paper["year"]:
            source["year"] = paper["year"]
        source.update(retrieved_on=retrieved_on, access_class="unknown", screening_status=status, verification_status="proposed")
        sources.append(source)
    return sources, skipped


# A review lists search hits, not screening decisions: entries are candidates unless the caller says otherwise.
def review_to_manifest(text: str, retrieved_on: str, status: str = "candidate") -> dict:
    return {"schema_version": "0.1.0", "sources": _convert(text, retrieved_on, status)[0]}


def migrate_review(review: Path, out: Path, retrieved_on: str | None, force: bool, status: str = "candidate") -> int:
    if out.exists() and not force:
        print(Problem(str(out), "output", "That output file already exists. Choose another --out, or add --force to replace it."))
        return 1
    if retrieved_on is not None:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", retrieved_on):
                raise ValueError(retrieved_on)
            date.fromisoformat(retrieved_on)
        except ValueError:
            print(Problem(retrieved_on, "--retrieved-on", "--retrieved-on must be a real date written YYYY-MM-DD, for example 2026-11-06."))
            return 1
    if not review.is_file():
        print(Problem(str(review), "review", "The review file was not found. Check the path."))
        return 1
    sources, skipped = _convert(review.read_text(encoding="utf-8-sig"), retrieved_on or date.today().isoformat(), status)
    for title in skipped:
        print(f"Skipped '{title}': no DOI / Link found; add it to the manifest by hand", file=sys.stderr)
    if skipped:
        print(f"{len(skipped)} skipped", file=sys.stderr)
    doc = {"schema_version": "0.1.0", "sources": sources}
    if not sources:
        print(Problem(str(review), "papers", "No paper blocks with a DOI / Link were found. Expected '### N. Title' headings followed by '- **DOI / Link:**' lines."))
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
    print(f"Wrote {len(doc['sources'])} sources to {out}. Review them, then run reprokit validate.")
    return 0
