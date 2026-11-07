import os
from pathlib import Path

from .evidence_claims import check_claims
from .evidence_extraction import load_extraction_schema, load_records, stale_records
from .evidence_manifest import check_manifest_rules
from .loader import load_yaml
from .problems import Problem
from .validate import validate_document

_BLOCKED_SUFFIXES = {".pdf", ".epub", ".docx"}


def _check_manifest(base: Path, rel: str, confidentiality: str) -> tuple[dict | None, list[Problem]]:
    path = base / rel
    if not path.is_file():
        return None, [Problem(str(path), "", f"The evidence manifest is missing. Create {rel} listing your sources.")]
    problems = validate_document(path, "evidence_manifest")
    if problems:
        return None, problems
    doc, _ = load_yaml(path)
    # The charter's confidentiality drives the public-repo project_package rule.
    problems = check_manifest_rules(doc, str(path), confidentiality)
    return (None if problems else doc), problems


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
    block = charter.get("evidence") or {}
    base = repo_dir / "evidence"
    manifest, problems = _check_manifest(repo_dir, block.get("manifest", "evidence/manifest.yaml"), charter["confidentiality"])
    warnings = []
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
