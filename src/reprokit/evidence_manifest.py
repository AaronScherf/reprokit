from pathlib import Path

from .loader import load_yaml
from .problems import Problem
from .validate import _VERIFIED_STATES, validate_document

SOURCE_TYPES = ("article", "report", "dataset", "webpage", "project_package", "other")
ACCESS_CLASSES = ("open", "paywalled", "restricted", "confidential", "unknown")
SCREENING_STATUSES = ("candidate", "included", "excluded")
_POINTER_CLASSES = {"confidential", "restricted"}


def check_manifest_rules(doc: dict, path: str, confidentiality: str) -> list[Problem]:
    problems = []
    seen = set()
    for index, source in enumerate(doc.get("sources", [])):
        where = f"sources[{index}]"
        sid = source.get("id")
        if sid in seen:
            problems.append(Problem(path, f"{where}.id", f"The source id '{sid}' is used more than once. Give each source its own id."))
        seen.add(sid)
        kind = source.get("type")
        if kind == "webpage" and source.get("verification_status") in _VERIFIED_STATES and not source.get("snapshot"):
            problems.append(Problem(path, f"{where}.snapshot", f"Webpage '{sid}' is marked as checked but has no snapshot. Add a snapshot with the url and date, or set verification_status to proposed."))
        if kind == "dataset" and not source.get("descriptor"):
            problems.append(Problem(path, f"{where}.descriptor", f"Dataset '{sid}' has no descriptor link. Add a descriptor pointing to its dataset descriptor file."))
        if kind == "project_package" and confidentiality == "public":
            pointer_only = source.get("access_class") in _POINTER_CLASSES and not source.get("extraction")
            if not pointer_only:
                problems.append(Problem(path, f"{where}.type", f"Project package '{sid}' cannot be recorded in a public project. Mark it confidential or restricted with no extraction (pointer only), or move it to a private project."))
    return problems


def load_manifest(path: Path) -> tuple[dict | None, list[Problem]]:
    problems = validate_document(path, "evidence_manifest")
    if problems:
        return None, problems
    doc, _ = load_yaml(path)
    # No project context here, so the confidentiality-dependent check is left to callers
    # (use check_manifest_rules with the charter's confidentiality).
    problems = check_manifest_rules(doc, str(path), "confidential")
    return (None if problems else doc), problems
