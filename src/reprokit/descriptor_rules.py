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
        problems.append(Problem(str(path), "coverage_period", "The source coverage starts after it ends. Correct the two dates and retry."))
    if doc["verification_status"] in VERIFIED_STATES:
        if config is None:
            problems.append(Problem(str(path), "coverage_period", "The study settings are missing or invalid, so coverage could not be checked. Fix config.yaml and retry."))
        else:
            period = config["period"]
            outside = start > date.fromisoformat(period["start"]) or end < date.fromisoformat(period["end"])
            if outside and not doc.get("coverage_gap_note", "").strip():
                problems.append(Problem(str(path), "coverage_gap_note", "This source does not cover the full study period. Add a coverage_gap_note explaining the missing dates, or correct the coverage dates."))
        note = doc.get("verification_note", "")
        if not note.strip():
            problems.append(Problem(str(path), "verification_note", "This checked source has no verification note. Add the path to a note that records what was checked."))
        else:
            root = repo_dir.resolve()
            note_path = (root / note).resolve()
            if not note_path.is_relative_to(root):
                problems.append(Problem(str(path), "verification_note", "The verification note points outside this project. Put the note inside the project and update its path."))
            elif not note_path.is_file():
                problems.append(Problem(str(path), "verification_note", f"The verification note {note} is missing. Create it or correct its path."))
            elif doc["verification_status"] not in note_path.read_text(encoding="utf-8"):
                problems.append(Problem(str(path), "verification_note", f"The verification note does not say '{doc['verification_status']}'. Record that exact status in the note or correct the descriptor's status."))
    return problems
