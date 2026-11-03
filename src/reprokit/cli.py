import argparse
import subprocess
import sys
from pathlib import Path

from .charter_rules import check_charter_consistency
from .config_rules import check_config_consistency
from .descriptor_rules import VERIFIED_STATES, check_descriptor_claims
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
from .validate import check_descriptor_license, validate_document

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


def _validate_folder(folder: Path, schema: str, config: dict | None = None, repo_dir: Path | None = None) -> tuple[list[Problem], int]:
    problems = []
    old_verified = 0
    for path in sorted(folder.glob("*.yaml")):
        document_problems = validate_document(path, schema, include_claims=False)
        problems.extend(document_problems)
        if schema == "descriptor" and not document_problems:
            doc, _ = load_yaml(path)
            problems.extend(check_descriptor_license(doc, path))
            problems.extend(check_descriptor_claims(doc, path, config, repo_dir or folder))
            old_verified += doc["schema_version"] == "0.1.0" and doc["verification_status"] in VERIFIED_STATES
    return problems, old_verified


def _validate_instance(instance_dir: Path, repo_dir: Path) -> tuple[list[Problem], int]:
    problems = []
    config = instance_dir / "config.yaml"
    config_doc = None
    if config.exists():
        config_problems = _check_document(config, "config", check_config_consistency)
        problems.extend(config_problems)
        if not config_problems:
            config_doc, _ = load_yaml(config)
    descriptor_problems, old_verified = _validate_folder(instance_dir / "data" / "descriptors", "descriptor", config_doc, repo_dir)
    problems.extend(descriptor_problems)
    harmonization_problems, _ = _validate_folder(instance_dir / "harmonization", "harmonization")
    problems.extend(harmonization_problems)
    return problems, old_verified


def _validate(repo_dir: Path) -> int:
    if not repo_dir.is_dir():
        print(Problem(str(repo_dir), "", "directory not found"))
        return 1
    problems = []
    old_verified = 0
    old_charter = False
    config_doc = None
    for name, schema, rule in ROOT_FILES:
        path = repo_dir / name
        if path.exists():
            document_problems = _check_document(path, schema, rule)
            problems.extend(document_problems)
            if name == "project.yaml" and not document_problems:
                charter_doc, _ = load_yaml(path)
                old_charter = charter_doc["schema_version"] == "0.1.0"
            if name == "config.yaml" and not document_problems:
                config_doc, _ = load_yaml(path)
    descriptor_problems, count = _validate_folder(repo_dir / "data" / "descriptors", "descriptor", config_doc, repo_dir)
    problems.extend(descriptor_problems)
    old_verified += count
    for instance_dir in sorted(path for path in (repo_dir / "instances").glob("*") if path.is_dir()):
        instance_problems, count = _validate_instance(instance_dir, repo_dir)
        problems.extend(instance_problems)
        old_verified += count
    for problem in problems:
        print(problem)
    if old_verified:
        print(f"Notice: {old_verified} checked sources still use descriptor schema 0.1.0, so coverage and note checks did not run. Update them to 0.2.0 to get those checks.")
    if old_charter:
        print("Notice: This project uses charter schema 0.1.0, so the quick check requirement did not run. Update project.yaml to 0.2.0 to get that check.")
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


def _quick_check(repo_dir: Path) -> int:
    script = repo_dir / "quick_check.py"
    if not script.is_file():
        print("FAIL  This project has no quick check script.\n      What to do: add quick_check.py with a made-up-data run, then retry.")
        return 1
    return subprocess.run([sys.executable, str(script.resolve())], cwd=repo_dir, check=False).returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reprokit")
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate")
    validate.add_argument("repo_dir", nargs="?", type=Path, default=Path("."))
    quick_check = subcommands.add_parser("quick-check", help="run the project's made-up-data check")
    quick_check.add_argument("repo_dir", nargs="?", type=Path, default=Path("."))
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
    if args.command == "quick-check":
        return _quick_check(args.repo_dir)
    if args.command == "gate":
        return _gate(args.baseline, args.config, args.records)
    return _manifest(args.config, args.raw_dir, args.out)
