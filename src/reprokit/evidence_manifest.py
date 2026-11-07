from pathlib import Path

from .loader import load_yaml
from .problems import Problem
from .validate import VERIFIED_STATES, validate_document

SOURCE_TYPES = ("article", "report", "dataset", "webpage", "project_package", "other")
ACCESS_CLASSES = ("open", "paywalled", "restricted", "confidential", "unknown")
SCREENING_STATUSES = ("candidate", "included", "excluded")
DEFAULT_MANIFEST = "evidence/manifest.yaml"


def _public_rules(source: dict, where: str, path: str) -> list[Problem]:
    sid, access = source.get("id"), source.get("access_class")
    if access == "confidential":
        return [Problem(path, f"{where}.access_class", f"Source '{sid}' is marked confidential but this repo is public; move it to a private project or remove the entry.")]
    if source.get("type") != "project_package":
        return []
    if source.get("extraction"):
        return [Problem(path, f"{where}.extraction", f"Project package '{sid}' has an extraction pointer but this repo is public. Remove the extraction so the entry is a pointer only, or move it to a private project.")]
    if access not in ("open", "restricted"):
        return [Problem(path, f"{where}.access_class", f"Project package '{sid}' must be open (or restricted) to be listed in a public repo. Set access_class to open if it is public, or move it to a private project.")]
    return []


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
        if kind == "webpage" and source.get("verification_status") in VERIFIED_STATES and not source.get("snapshot"):
            problems.append(Problem(path, f"{where}.snapshot", f"Webpage '{sid}' is marked as checked but has no snapshot. Add a snapshot with the url and date, or set verification_status to proposed."))
        if kind == "dataset" and not source.get("descriptor"):
            problems.append(Problem(path, f"{where}.descriptor", f"Dataset '{sid}' has no descriptor link. Add a descriptor pointing to its dataset descriptor file."))
        if confidentiality == "public":
            problems.extend(_public_rules(source, where, path))
    return problems


def manifest_warnings(doc: dict, path: str, confidentiality: str) -> list[Problem]:
    if confidentiality != "public":
        return []
    return [
        Problem(path, f"sources[{index}].access_class", f"Source '{source.get('id')}' is marked restricted and this repo is public. Check that its title, identifier and notes may be shown publicly, or move it to a private project.")
        for index, source in enumerate(doc.get("sources", []))
        if source.get("access_class") == "restricted"
    ]


def load_repo_charter(repo_dir: Path) -> tuple[dict | None, list[Problem]]:
    """Read project.yaml without raising. A missing file is (None, [])."""
    path = repo_dir / "project.yaml"
    if not path.is_file():
        return None, []
    doc, problems = load_yaml(path)
    if problems:
        return None, problems
    block = doc.get("evidence")
    if block is not None and not isinstance(block, dict):
        rest = {key: value for key, value in doc.items() if key != "evidence"}
        return rest, [Problem(str(path), "evidence", "The evidence section of project.yaml must be a mapping such as 'manifest: evidence/manifest.yaml'. Fix it, or remove it to use the default manifest.")]
    return doc, []


def manifest_path(repo_dir: Path, charter: dict | None) -> tuple[Path | None, list[Problem]]:
    """The manifest file every evidence command uses: the charter's evidence.manifest, kept inside the repo."""
    block = (charter or {}).get("evidence")
    rel = block.get("manifest", DEFAULT_MANIFEST) if isinstance(block, dict) else DEFAULT_MANIFEST
    where = str(repo_dir / "project.yaml")
    if not isinstance(rel, str) or not rel.strip():
        return None, [Problem(where, "evidence.manifest", "The manifest path must be text, such as evidence/manifest.yaml. Fix evidence.manifest in project.yaml.")]
    path = inside_repo(repo_dir, rel)
    if path is None:
        return None, [Problem(where, "evidence.manifest", f"The manifest path '{rel}' points outside this repo. Use a path inside the repo, such as evidence/manifest.yaml.")]
    return path, []


def inside_repo(repo_dir: Path, rel: str) -> Path | None:
    """repo_dir / rel when rel is a relative path that stays inside the repo, else None."""
    path = repo_dir / rel
    if Path(rel).anchor or not path.resolve().is_relative_to(repo_dir.resolve()):
        return None
    return path


def load_manifest(path: Path, *, confidentiality: str = "public") -> tuple[dict | None, list[Problem]]:
    """Schema plus type rules. Pass the charter's confidentiality; the default is the strictest (public).

    Keyword-only with a default so a generated project's quick_check.py (which calls load_manifest(path)) keeps working.
    """
    if not path.is_file():
        return None, [Problem(str(path), "", "The evidence manifest is missing. Create it listing your sources (see docs/evidence-kind.md).")]
    problems = validate_document(path, "evidence_manifest")
    if problems:
        return None, problems
    doc, _ = load_yaml(path)
    problems = check_manifest_rules(doc, str(path), confidentiality)
    return (None if problems else doc), problems
