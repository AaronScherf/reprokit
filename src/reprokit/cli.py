import argparse
from pathlib import Path

from .charter_rules import check_charter_consistency
from .config_rules import check_config_consistency
from .harmonization import check_gate
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


def _validate_folder(folder: Path, schema: str) -> list[Problem]:
    problems = []
    for path in sorted(folder.glob("*.yaml")):
        problems.extend(validate_document(path, schema))
    return problems


def _validate_instance(instance_dir: Path) -> list[Problem]:
    problems = []
    config = instance_dir / "config.yaml"
    if config.exists():
        problems.extend(_check_document(config, "config", check_config_consistency))
    problems.extend(_validate_folder(instance_dir / "data" / "descriptors", "descriptor"))
    problems.extend(_validate_folder(instance_dir / "harmonization", "harmonization"))
    return problems


def _validate(repo_dir: Path) -> int:
    if not repo_dir.is_dir():
        print(Problem(str(repo_dir), "", "directory not found"))
        return 1
    problems = []
    for name, schema, rule in ROOT_FILES:
        path = repo_dir / name
        if path.exists():
            problems.extend(_check_document(path, schema, rule))
    problems.extend(_validate_folder(repo_dir / "data" / "descriptors", "descriptor"))
    for instance_dir in sorted(path for path in (repo_dir / "instances").glob("*") if path.is_dir()):
        problems.extend(_validate_instance(instance_dir))
    for problem in problems:
        print(problem)
    return int(bool(problems))


def _gate(baseline: Path, config: Path, records: Path) -> int:
    problems = []
    for path in (baseline, config):
        problems.extend(_check_document(path, "config", check_config_consistency))
    if not problems:
        baseline_doc, _ = load_yaml(baseline)
        config_doc, _ = load_yaml(config)
        problems = check_gate(baseline_doc["sources"], config_doc["sources"], records)
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
    gate = subcommands.add_parser("gate", help="require harmonization records for provider changes against a baseline")
    gate.add_argument("--baseline", type=Path, required=True)
    gate.add_argument("--config", type=Path, required=True)
    gate.add_argument("--records", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        return _validate(args.repo_dir)
    if args.command == "gate":
        return _gate(args.baseline, args.config, args.records)
    return _manifest(args.config, args.raw_dir, args.out)
