"""Repository-level checks for version 0.2.0 descriptors."""

from datetime import date
from pathlib import Path

from .problems import Problem

VERIFIED_STATES = {"source-verified", "fixture-tested", "run on acquired data", "independently reproduced"}


def check_descriptor_claims(doc: dict, path: Path, config: dict | None, repo_dir: Path) -> list[Problem]:
    if doc["schema_version"] != "0.2.0":
        return []
    problems = []
    coverage = doc["coverage_period"]
    start, end = date.fromisoformat(coverage["start"]), date.fromisoformat(coverage["end"])
    if start > end:
        problems.append(Problem(str(path), "coverage_period", "start is after end"))
    if doc["verification_status"] in VERIFIED_STATES:
        if config is None:
            problems.append(Problem(str(path), "coverage_period", "config.yaml is required to check coverage"))
        else:
            period = config["period"]
            outside = start > date.fromisoformat(period["start"]) or end < date.fromisoformat(period["end"])
            if outside and not doc.get("coverage_gap_note", "").strip():
                problems.append(Problem(str(path), "coverage_gap_note", "required when coverage_period does not cover config period"))
        note = doc.get("verification_note", "")
        if not note.strip():
            problems.append(Problem(str(path), "verification_note", "required for source-verified or higher"))
        else:
            root = repo_dir.resolve()
            note_path = (root / note).resolve()
            if not note_path.is_relative_to(root):
                problems.append(Problem(str(path), "verification_note", "path must stay inside the project"))
            elif not note_path.is_file():
                problems.append(Problem(str(path), "verification_note", f"file not found: {note}"))
            elif doc["verification_status"] not in note_path.read_text(encoding="utf-8"):
                problems.append(Problem(str(path), "verification_note", "file does not contain the descriptor verification_status"))
    return problems
