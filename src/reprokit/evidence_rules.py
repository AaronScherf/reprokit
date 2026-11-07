import os
from pathlib import Path

from .evidence_claims import check_claims
from .evidence_extraction import load_extraction_schema, load_records, stale_warnings
from .evidence_manifest import load_manifest, manifest_path, manifest_warnings
from .evidence_pointers import check_pointers
from .problems import Problem

_BLOCKED_SUFFIXES = {".pdf", ".epub", ".docx", ".doc", ".rtf", ".odt", ".djvu", ".mobi", ".azw3", ".ps", ".xps"}
_CACHE_FORMS = {"/cache/", "/cache", "cache/", "cache"}


def _gitignore_lines(repo_dir: Path) -> tuple[list[str], list[Problem]]:
    path = repo_dir / ".gitignore"
    if not path.is_file():
        return [], []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return [], [Problem(str(path), "", "The .gitignore file could not be read as UTF-8 text. Re-save it as UTF-8 and try again.")]
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line and not line.startswith("#")], []


def _ignored_dirs(lines: list[str]) -> set[str]:
    # Only exact top-level forms: /D/, /D, D/, D. Not full gitignore semantics.
    return {line.strip("/") for line in lines if "/" not in line.strip("/") and line.strip("/")}


def _stray_files(repo_dir: Path) -> list[Problem]:
    lines, problems = _gitignore_lines(repo_dir)
    if any(line.startswith("!") and line[1:].lstrip("/").startswith("cache") for line in lines):
        problems.append(Problem(str(repo_dir / ".gitignore"), "cache", "this .gitignore re-includes files under cache/; remove the '!' line, cache/ must stay ignored"))
    if (repo_dir / "cache").is_dir() and not _CACHE_FORMS & set(lines):
        problems.append(Problem(str(repo_dir / ".gitignore"), "cache", "The cache/ directory is not ignored by git. Add a line '/cache/' to .gitignore so downloaded files are never committed."))
    skip = _ignored_dirs(lines) | {".git", "cache"}
    for root, dirs, files in os.walk(repo_dir):
        if Path(root) == repo_dir:
            dirs[:] = sorted(d for d in dirs if d not in skip)
        for name in sorted(files):
            if Path(name).suffix.lower() in _BLOCKED_SUFFIXES:
                problems.append(Problem(str(Path(root) / name), "", "Source documents (PDF, EPUB, DOCX, DOC, RTF, ODT, DJVU, MOBI, AZW3, PS, XPS) must not be stored in the repository. Move the file into the gitignored cache/ directory or delete it."))
    return problems


def validate_evidence(repo_dir: Path, charter: dict) -> tuple[list[Problem], list[Problem]]:
    """Return (problems, warnings) for an evidence-kind repo."""
    # Extraction schema and records always live under repo_dir/evidence/, wherever the manifest is.
    base = repo_dir / "evidence"
    manifest, warnings = None, []
    path, problems = manifest_path(repo_dir, charter)
    if path is not None:
        manifest, problems = load_manifest(path, confidentiality=charter["confidentiality"])
    schema_path = base / "extraction_schema.yaml"
    if manifest is not None:
        warnings += manifest_warnings(manifest, str(path), charter["confidentiality"])
        problems += check_pointers(repo_dir, manifest, str(path), screening=schema_path.is_file())
    synthesis = repo_dir / "synthesis.md"
    if manifest is not None and synthesis.is_file():
        try:
            claims_text = synthesis.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            problems.append(Problem(str(synthesis), "", "The synthesis.md file could not be read as UTF-8 text. Re-save it as UTF-8 and try again."))
        else:
            problems += check_claims(claims_text, manifest, str(synthesis))
    if manifest is not None and schema_path.is_file():
        schema, found = load_extraction_schema(schema_path)
        problems += found
        if schema is not None:
            records, found = load_records(base / "extractions", manifest, schema)
            problems += found
            warnings += stale_warnings(records, manifest, schema, base / "extractions")
    return problems + _stray_files(repo_dir), warnings
