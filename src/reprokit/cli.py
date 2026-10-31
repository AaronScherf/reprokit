import argparse
from pathlib import Path

from .charter_rules import check_charter_consistency
from .config_rules import check_config_consistency
from .loader import load_yaml
from .manifest import (
    build_manifest,
    code_version,
    collect_role_files,
    resolved_packages,
    write_manifest,
)
from .problems import Problem
from .validate import validate_document

# file name in the repo root -> (schema name, extra cross-field rule run after the schema passes)
ROOT_FILES = [
    ("project.yaml", "charter", check_charter_consistency),
    ("compute.yaml", "compute", None),
    ("agents.yaml", "agents", None),
    ("config.yaml", "config", check_config_consistency),
]


def _check_document(path: Path, schema: str, rule) -> list[Problem]:
    problems = validate_document(path, schema)
    if problems or rule is None:
        return problems
    doc, _ = load_yaml(path)
    return rule(doc, str(path))


def _validate(repo_dir: Path) -> int:
    problems = []
    for name, schema, rule in ROOT_FILES:
        path = repo_dir / name
        if path.exists():
            problems.extend(_check_document(path, schema, rule))
    for descriptor in sorted((repo_dir / "data" / "descriptors").glob("*.yaml")):
        problems.extend(validate_document(descriptor, "descriptor"))
    for problem in problems:
        print(problem)
    return int(bool(problems))


def _manifest(config_path: Path, raw_dir: Path, out: Path) -> int:
    problems = _check_document(config_path, "config", check_config_consistency)
    if problems:
        for problem in problems:
            print(problem)
        return 1
    config, _ = load_yaml(config_path)
    try:
        files = collect_role_files(raw_dir, config["sources"])
    except FileNotFoundError as exc:
        print(Problem(str(config_path), "sources", str(exc)))
        return 1
    manifest = build_manifest(config, files, raw_dir, code_version(config_path.parent), resolved_packages())
    write_manifest(manifest, out)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reprokit")
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate")
    validate.add_argument("repo_dir", nargs="?", type=Path, default=Path("."))
    manifest = subcommands.add_parser("manifest")
    manifest.add_argument("--config", type=Path, default=Path("config.yaml"))
    manifest.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    manifest.add_argument("--out", type=Path, default=Path("outputs/manifest.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        return _validate(args.repo_dir)
    return _manifest(args.config, args.raw_dir, args.out)
