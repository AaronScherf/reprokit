"""Checks on manifest entries that point at other files in the repo (descriptor, extraction)."""
from pathlib import Path

from .evidence_manifest import inside_repo
from .problems import Problem
from .validate import validate_document


def _outside(path: str, where: str, sid, key: str, rel: str) -> Problem:
    return Problem(path, where, f"The {key} path '{rel}' of source '{sid}' points outside this repo. Use a path relative to the repo root that stays inside it.")


def _descriptor(repo_dir: Path, source: dict, where: str, path: str) -> list[Problem]:
    rel, sid = source.get("descriptor"), source.get("id")
    if source.get("type") != "dataset" or not rel:
        return []
    target = inside_repo(repo_dir, rel)
    if target is None:
        return [_outside(path, where, sid, "descriptor", rel)]
    if not target.is_file():
        return [Problem(path, where, f"Dataset '{sid}' links to descriptor '{rel}', which does not exist. Create the descriptor there (for example in data/descriptors/) or fix the path.")]
    return validate_document(target, "descriptor")


def _extraction(repo_dir: Path, source: dict, where: str, path: str, screening: bool) -> list[Problem]:
    rel, sid = source.get("extraction"), source.get("id")
    if not rel:
        return []
    target = inside_repo(repo_dir, rel)
    if target is None:
        return [_outside(path, where, sid, "extraction", rel)]
    if not screening:
        return []
    if not target.is_file():
        return [Problem(path, where, f"Source '{sid}' points to extraction record '{rel}', which does not exist. Fix the path, such as evidence/extractions/{sid}.yaml, or remove the extraction line.")]
    if target.name != f"{sid}.yaml":
        return [Problem(path, where, f"Source '{sid}' points to extraction record '{target.name}', but its record must be named '{sid}.yaml'. Point extraction to evidence/extractions/{sid}.yaml.")]
    return []


def check_pointers(repo_dir: Path, manifest: dict, path: str, *, screening: bool) -> list[Problem]:
    """Descriptor and extraction paths must stay in the repo; in the screening tier extraction files must exist."""
    problems = []
    for index, source in enumerate(manifest.get("sources", [])):
        problems += _descriptor(repo_dir, source, f"sources[{index}].descriptor", path)
        problems += _extraction(repo_dir, source, f"sources[{index}].extraction", path, screening)
    return problems
