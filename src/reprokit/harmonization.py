from pathlib import Path

from .problems import Problem
from .validate import validate_document


def structural_changes(baseline: dict, current: dict) -> list[str]:
    return sorted(role for role, source in current.items() if role in baseline and source["provider"].strip().casefold() != baseline[role]["provider"].strip().casefold())


def check_gate(baseline: dict, current: dict, records_dir: Path) -> list[Problem]:
    problems = []
    for role in structural_changes(baseline, current):
        path = records_dir / f"{role}.yaml"
        if not path.exists():
            problems.append(Problem(str(path), "role", f"structural change in {role} requires {path}"))
        else:
            problems.extend(validate_document(path, "harmonization"))
    return problems