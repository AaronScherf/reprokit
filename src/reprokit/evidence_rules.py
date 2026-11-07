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


def _stray_files(repo_dir: Path) -> list[Problem]:
    problems = []
    cache = repo_dir / "cache"
    if cache.is_dir():
        gitignore = repo_dir / ".gitignore"
        lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.is_file() else []
        if "/cache/" not in (line.strip() for line in lines):
            problems.append(Problem(str(gitignore), "cache", "The cache/ directory is not ignored by git. Add a line '/cache/' to .gitignore so downloaded files are never committed."))
    for file in sorted(repo_dir.rglob("*")):
        relative = file.relative_to(repo_dir)
        if not file.is_file() or relative.parts[0] in {".git", "cache"}:
            continue
        if file.suffix.lower() in _BLOCKED_SUFFIXES:
            problems.append(Problem(str(file), "", "Source documents (PDF, EPUB, DOCX) must not be stored in the repository. Move the file into the gitignored cache/ directory or delete it."))
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
