"""Turn a literature_review.md into an evidence manifest (abstracts and citation counts are dropped)."""
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import yaml

from .evidence_review_links import identifier as _identifier
from .evidence_review_links import link as _link
from .problems import Problem

_HEADING = re.compile(r"^### (<a id=\"[^\"]*\"></a>)?\s*(?:\d+\.\s*)?(.+)$")
_ANY_HEADING = re.compile(r"#{1,6} ")
_ANCHOR = re.compile(r"<a id=\"paper-\d+\"></a>")
_FIELD = re.compile(r"^- \*\*(.+?):\*\*\s*(.*)$")
_PAPER_FIELDS = ("authors", "publication year")
_LETTERS = str.maketrans({"ø": "o", "ß": "ss", "ł": "l", "æ": "ae", "œ": "oe", "đ": "d", "þ": "th", "ð": "d"})
_SUFFIXES = {"jr", "sr", "ii", "iii"}  # compared without a trailing dot


def parse_review(text: str) -> list[dict]:
    """Paper blocks: a '###' heading with the paper-N anchor, or followed by an Authors, Publication Year
    or DOI / Link field. Other '###' headings (methods notes and the like) are not papers."""
    papers, current = [], None
    for line in text.splitlines():
        line = line.rstrip()  # keeps the patterns below linear on long runs of spaces
        heading = _HEADING.match(line)
        if heading:
            current = {"title": heading.group(2), "authors": [], "year": None, "link": None,
                       "paper": bool(heading.group(1) and _ANCHOR.fullmatch(heading.group(1)))}
            papers.append(current)
            continue
        if _ANY_HEADING.match(line):
            current = None  # a heading of any level ends the paper block
            continue
        field = _FIELD.match(line)
        if not (field and current):
            continue
        name, value = field.group(1).lower(), field.group(2)
        current["paper"] = current["paper"] or name in _PAPER_FIELDS or name.startswith("doi")
        if name == "authors":
            current["authors"] = [a.strip() for a in value.split(",") if a.strip()]
        elif name == "publication year" and re.fullmatch(r"\d{4}", value):
            current["year"] = int(value)
        elif name.startswith("doi"):
            current["link"] = _link(value)
    return [{k: v for k, v in p.items() if k != "paper"} for p in papers if p["paper"]]


def _surname(author: str) -> str:
    tokens = author.split()
    while len(tokens) > 1:
        tail = [t.lower().rstrip(".") for t in tokens[-2:]]
        if tail == ["et", "al"]:
            tokens = tokens[:-2]
        elif tail[-1] in _SUFFIXES:
            tokens = tokens[:-1]
        else:
            break
    return tokens[-1] if tokens else "source"


def _slug(authors: list[str], year: int | None) -> str:
    surname = _surname(authors[0]).lower().translate(_LETTERS) if authors else "source"
    ascii_name = unicodedata.normalize("NFKD", surname).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^a-z0-9_-]", "", ascii_name).lstrip("-_") or "source"
    return f"{stem}-{year}" if year else stem


def _convert(text: str, retrieved_on: str, status: str) -> tuple[list[dict], list[tuple[str, str]]]:
    sources, skipped, used = [], [], {}
    for paper in parse_review(text):
        ident = _identifier(paper["link"])
        if not ident:
            reason = ("no DOI / Link field with a URL or DOI" if not paper["link"]
                      else f"the link '{paper['link']}' is not a usable identifier")
            skipped.append((paper["title"], reason))
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
    for title, reason in skipped:
        print(f"Skipped '{title}': {reason}; add it to the manifest by hand", file=sys.stderr)
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
