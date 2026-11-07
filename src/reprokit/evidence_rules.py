import os
from pathlib import Path

from .evidence_claims import check_claims
from .evidence_extraction import load_extraction_schema, load_records, stale_records
from .evidence_manifest import load_manifest, manifest_path, manifest_warnings
from .problems import Problem

_BLOCKED_SUFFIXES = {".pdf", ".epub", ".docx"}


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
    if (repo_dir / "cache").is_dir() and "/cache/" not in lines:
        problems.append(Problem(str(repo_dir / ".gitignore"), "cache", "The cache/ directory is not ignored by git. Add a line '/cache/' to .gitignore so downloaded files are never committed."))
    skip = _ignored_dirs(lines) | {".git", "cache"}
    for root, dirs, files in os.walk(repo_dir):
        if Path(root) == repo_dir:
            dirs[:] = sorted(d for d in dirs if d not in skip)
        for name in sorted(files):
            if Path(name).suffix.lower() in _BLOCKED_SUFFIXES:
                problems.append(Problem(str(Path(root) / name), "", "Source documents (PDF, EPUB, DOCX) must not be stored in the repository. Move the file into the gitignored cache/ directory or delete it."))
    return problems


def validate_evidence(repo_dir: Path, charter: dict) -> tuple[list[Problem], list[Problem]]:
    """Return (problems, warnings) for an evidence-kind repo."""
    # Extraction schema and records always live under repo_dir/evidence/, wherever the manifest is.
    base = repo_dir / "evidence"
    manifest, warnings = None, []
    path, problems = manifest_path(repo_dir, charter)
    if path is not None:
        manifest, problems = load_manifest(path, confidentiality=charter["confidentiality"])
    if manifest is not None:
        warnings += manifest_warnings(manifest, str(path), charter["confidentiality"])
    synthesis = repo_dir / "synthesis.md"
    if manifest is not None and synthesis.is_file():
        problems += check_claims(synthesis.read_text(encoding="utf-8"), manifest, str(synthesis))
    schema_path = base / "extraction_schema.yaml"
    if manifest is not None and schema_path.is_file():
        schema, found = load_extraction_schema(schema_path)
        problems += found
        if schema is not None:
            records, found = load_records(base / "extractions", manifest, schema)
            problems += found
            for sid in stale_records(records, manifest):
                warnings.append(Problem(str(base / "extractions" / f"{sid}.yaml"), "source_content_hash", f"The record for '{sid}' was extracted from an older version of the source. Re-run extraction for '{sid}'."))
    return problems + _stray_files(repo_dir), warnings
