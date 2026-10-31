from pathlib import Path

from .problems import Problem
from .validate import validate_document


def _provider(source: dict) -> str:
    return source["provider"].strip().casefold()


def structural_changes(baseline: dict, current: dict) -> list[str]:
    """Roles whose provider changed, or that were added or removed, sorted by name."""
    changed = []
    for role in sorted(set(baseline) | set(current)):
        added_or_removed = role not in baseline or role not in current
        if added_or_removed or _provider(baseline[role]) != _provider(current[role]):
            changed.append(role)
    return changed


def check_gate(baseline: dict, current: dict, records_dir: Path) -> list[Problem]:
    problems = []
    for role in structural_changes(baseline, current):
        record = records_dir / f"{role}.yaml"
        if record.exists():
            problems.extend(validate_document(record, "harmonization"))
        else:
            problems.append(Problem(str(record), "role", f"structural change in {role} requires {record}"))
    return problems
