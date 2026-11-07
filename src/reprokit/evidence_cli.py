from pathlib import Path

import yaml

from .evidence_extraction import load_extraction_schema, load_records
from .evidence_manifest import load_manifest
from .evidence_run import aggregate, delta
from .problems import Problem


def _ids(text: str | None) -> set[str]:
    return {part.strip() for part in (text or "").split(",") if part.strip()}


def evidence_run(repo_dir: Path, only: str | None, exclude: str | None) -> int:
    base = repo_dir / "evidence"
    manifest, problems = load_manifest(base / "manifest.yaml")
    schema, more = load_extraction_schema(base / "extraction_schema.yaml")
    problems += more
    if problems:
        return _fail(problems)
    known = {s["id"] for s in manifest["sources"]}
    chosen, dropped = _ids(only), _ids(exclude)
    unknown = sorted((chosen | dropped) - known)
    if unknown:
        return _fail([Problem(str(base / "manifest.yaml"), i, f"The source id '{i}' is not in the manifest. Check the spelling in --only/--exclude.") for i in unknown])
    records, problems = load_records(base / "extractions", manifest, schema)
    missing = [p for p in problems if p.path == str(base / "extractions")]
    if len(missing) != len(problems):
        return _fail([p for p in problems if p not in missing])
    selected = [s["id"] for s in manifest["sources"] if s.get("screening_status") == "included"
                and (not chosen or s["id"] in chosen) and s["id"] not in dropped]
    absent = [i for i in selected if i not in records]
    if absent:
        return _fail([Problem(str(base / "extractions"), i, f"The included source '{i}' has no extraction record. Add evidence/extractions/{i}.yaml, or leave it out with --exclude {i}.") for i in absent])
    full = aggregate(manifest, records, schema)
    result = {"aggregate": full}
    if chosen or dropped:
        sub = aggregate(manifest, records, schema, only=chosen or None, exclude=dropped)
        result = {"aggregate": sub, "delta": delta(full, sub)}
    out = repo_dir / "outputs" / "evidence_aggregate.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(result, sort_keys=False)
    out.write_text(text, encoding="utf-8")
    print(text)
    return 0


def _fail(problems: list[Problem]) -> int:
    for problem in problems:
        print(problem)
    return 1


def register(subcommands) -> None:
    run = subcommands.add_parser("evidence-run", help="combine extraction records into an aggregate (no AI calls)")
    run.add_argument("repo_dir", nargs="?", type=Path, default=Path("."))
    run.add_argument("--only", help="comma-separated source ids to include")
    run.add_argument("--exclude", help="comma-separated source ids to leave out")
    verify = subcommands.add_parser("verify-sources", help="check that included sources' DOIs resolve online (free, no credentials)")
    verify.add_argument("repo_dir", nargs="?", type=Path, default=Path("."))
    migrate = subcommands.add_parser("migrate-review", help="convert a literature_review.md into an evidence manifest")
    migrate.add_argument("review", type=Path)
    migrate.add_argument("--out", type=Path, default=Path("evidence/manifest.yaml"))
    migrate.add_argument("--retrieved-on", help="YYYY-MM-DD (default: today)")
    migrate.add_argument("--force", action="store_true", help="replace an existing output file")
