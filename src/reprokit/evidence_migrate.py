"""Turn a literature_review.md into an evidence manifest (abstracts and citation counts are dropped)."""
import re
import unicodedata
from datetime import date
from pathlib import Path

import yaml

from .problems import Problem

_HEADING = re.compile(r"^### (?:<a id=\"[^\"]*\"></a>)?\s*(?:\d+\.\s*)?(.+?)\s*$")
_FIELD = re.compile(r"^- \*\*(.+?):\*\*\s*(.*?)\s*$")
_URL = re.compile(r"\((https?://[^)\s]+)\)|(https?://[^\s)\]]+)")
_DOI = re.compile(r"doi\.org/(10\.\S+)$", re.I)
_OPENALEX = re.compile(r"openalex\.org/(?:works/)?(W\d+)", re.I)


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
            url = _URL.search(value)
            current["link"] = (url.group(1) or url.group(2)) if url else None
    return papers


def _identifier(link: str | None) -> dict | None:
    if not link:
        return None
    if m := _DOI.search(link):
        return {"scheme": "doi", "value": m.group(1)}
    if m := _OPENALEX.search(link):
        return {"scheme": "openalex", "value": m.group(1)}
    return {"scheme": "url", "value": link}


def _slug(authors: list[str], year: int | None) -> str:
    surname = authors[0].split()[-1] if authors else "source"
    ascii_name = unicodedata.normalize("NFKD", surname).encode("ascii", "ignore").decode().lower()
    stem = re.sub(r"[^a-z0-9_-]", "", ascii_name).lstrip("-_") or "source"
    return f"{stem}-{year}" if year else stem


def review_to_manifest(text: str, retrieved_on: str) -> dict:
    sources, used = [], {}
    for paper in parse_review(text):
        ident = _identifier(paper["link"])
        if not ident:
            continue
        base = _slug(paper["authors"], paper["year"])
        used[base] = used.get(base, 0) + 1
        sid = base if used[base] == 1 else f"{base}-{chr(ord('a') + used[base] - 1)}"
        source = {"id": sid, "type": "article", "identifier": ident, "title": paper["title"]}
        if paper["year"]:
            source["year"] = paper["year"]
        source.update(retrieved_on=retrieved_on, access_class="unknown", screening_status="included", verification_status="proposed")
        sources.append(source)
    return {"schema_version": "0.1.0", "sources": sources}


def migrate_review(review: Path, out: Path, retrieved_on: str | None, force: bool) -> int:
    if out.exists() and not force:
        print(Problem(str(out), "output", "That output file already exists. Choose another --out, or add --force to replace it."))
        return 1
    if not review.is_file():
        print(Problem(str(review), "review", "The review file was not found. Check the path."))
        return 1
    doc = review_to_manifest(review.read_text(encoding="utf-8"), retrieved_on or date.today().isoformat())
    if not doc["sources"]:
        print(Problem(str(review), "papers", "No paper blocks with a DOI / Link were found. Expected '### N. Title' headings followed by '- **DOI / Link:**' lines."))
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {len(doc['sources'])} sources to {out}. Review them, then run reprokit validate.")
    return 0
