import argparse
import subprocess
import tomllib
from importlib import metadata
from pathlib import Path

from .charter_rules import check_charter_consistency
from .loader import load_yaml
from .manifest import build_manifest, collect_role_files, write_manifest
from .validate import validate_document


def _validate(repo_dir: Path) -> int:
    known = [("project.yaml", "charter"), ("compute.yaml", "compute"), ("agents.yaml", "agents"), ("config.yaml", "config")]
    problems = []
    for relative, schema in known:
        path = repo_dir / relative
        if path.exists():
            errors = validate_document(path, schema)
            problems.extend(errors)
            if schema == "charter" and not errors:
                doc, _ = load_yaml(path)
                problems.extend(check_charter_consistency(doc, str(path)))
    for path in sorted((repo_dir / "data" / "descriptors").glob("*.yaml")):
        problems.extend(validate_document(path, "descriptor"))
    for problem in problems:
        print(problem)
    return int(bool(problems))


def _packages(config_path: Path) -> dict[str, str]:
    project = config_path.parent / "pyproject.toml"
    if not project.exists():
        return {}
    declared = tomllib.loads(project.read_text(encoding="utf-8"))["project"].get("dependencies", [])
    result = {}
    for requirement in declared:
        name = requirement.split("[")[0].split(">=")[0].split("==")[0].split("<")[0].strip()
        result[name] = metadata.version(name)
    return result


def _code_version(config_path: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config_path.parent, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _manifest(config_path: Path, raw_dir: Path, out: Path) -> int:
    problems = validate_document(config_path, "config")
    if problems:
        for problem in problems:
            print(problem)
        return 1
    config, _ = load_yaml(config_path)
    try:
        files = collect_role_files(raw_dir, config["sources"])
        manifest = build_manifest(config, files, raw_dir, _code_version(config_path), _packages(config_path))
        write_manifest(manifest, out)
    except (FileNotFoundError, metadata.PackageNotFoundError) as exc:
        print(f"{config_path}: inputs: {exc}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reprokit")
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate")
    validate.add_argument("repo_dir", nargs="?", type=Path, default=Path("."))
    manifest = subcommands.add_parser("manifest")
    manifest.add_argument("--config", type=Path, default=Path("config.yaml"))
    manifest.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    manifest.add_argument("--out", type=Path, default=Path("outputs/manifest.json"))
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args.repo_dir)
    return _manifest(args.config, args.raw_dir, args.out)