import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def collect_role_files(raw_dir: Path, roles: Iterable[str]) -> dict[str, list[Path]]:
    result = {}
    for role in roles:
        role_dir = raw_dir / role
        files = sorted((p for p in role_dir.rglob("*") if p.is_file() and p.name != ".gitkeep"), key=lambda p: p.relative_to(raw_dir).as_posix())
        if not files:
            raise FileNotFoundError(f"no files for role {role} in {role_dir}")
        result[role] = files
    return result


def build_manifest(config: dict, inputs: dict[str, list[Path]], raw_dir: Path, code_version: str, resolved_packages: dict[str, str], now: datetime | None = None) -> dict:
    timestamp = now or datetime.now(UTC)
    return {
        "schema_version": "0.1.0",
        "code_version": code_version,
        "parameters": config["parameters"],
        "inputs": {role: [{"path": path.relative_to(raw_dir).as_posix(), "sha256": hash_file(path)} for path in files] for role, files in inputs.items()},
        "packages": resolved_packages,
        "created_utc": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


def write_manifest(manifest: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")