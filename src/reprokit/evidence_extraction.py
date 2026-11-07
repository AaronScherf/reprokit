from pathlib import Path

from .loader import load_yaml
from .problems import Problem
from .validate import validate_document

MAX_TEXT = 500
_TYPES = {"number": (int, float), "boolean": (bool,), "string": (str,), "list": (list,)}


def load_extraction_schema(path: Path) -> tuple[dict | None, list[Problem]]:
    problems = validate_document(path, "extraction_schema")
    if problems:
        return None, problems
    doc, _ = load_yaml(path)
    return doc, []


def _check_fields(record: dict, schema: dict, path: str) -> list[Problem]:
    problems = []
    declared = schema["fields"]
    for name, value in record["fields"].items():
        where = f"fields.{name}"
        if name not in declared:
            problems.append(Problem(path, where, f"The field '{name}' is not in the extraction schema. Add it to evidence/extraction_schema.yaml or remove it from this record."))
            continue
        kind = declared[name]["type"]
        ok = isinstance(value, _TYPES[kind]) and not (kind == "number" and isinstance(value, bool))
        if not ok:
            problems.append(Problem(path, where, f"The field '{name}' should be a {kind}. Fix the value in this record."))
            continue
        items = value if kind == "list" else [value]
        if kind == "list" and not all(isinstance(v, (str, int, float, bool)) for v in items):
            problems.append(Problem(path, where, f"The field '{name}' must be a flat list of text, numbers or true/false values. Remove nested lists or mappings."))
        elif any(isinstance(v, str) and len(v) > MAX_TEXT for v in items):
            problems.append(Problem(path, where, f"The field '{name}' has text longer than {MAX_TEXT} characters. Summarize it in your own words instead of quoting the source."))
    return problems


def load_records(folder: Path, manifest: dict, schema: dict) -> tuple[dict[str, dict], list[Problem]]:
    records, problems, seen = {}, [], set()
    for file in sorted(folder.glob("*.yaml")) if folder.is_dir() else []:
        seen.add(file.stem)
        bad = validate_document(file, "extraction_record")
        if bad:
            problems.extend(bad)
            continue
        record, _ = load_yaml(file)
        if record["source_id"] != file.stem:
            problems.append(Problem(str(file), "source_id", f"The filename '{file.stem}' must equal the record's source_id '{record['source_id']}'. Rename the file or fix the source_id."))
            continue
        found = _check_fields(record, schema, str(file))
        problems.extend(found)
        if not found:
            records[record["source_id"]] = record
    for source in manifest.get("sources", []):
        if source.get("screening_status") == "included" and source["id"] not in seen:
            problems.append(Problem(str(folder), source["id"], f"The included source '{source['id']}' has no extraction record. Run evidence-run or add {source['id']}.yaml to the extractions folder."))
    return records, problems


def stale_records(records: dict, manifest: dict) -> list[str]:
    hashes = {s["id"]: s.get("content_hash") for s in manifest.get("sources", [])}
    return [
        sid for sid, rec in records.items()
        if rec.get("source_content_hash") and hashes.get(sid) and rec["source_content_hash"] != hashes[sid]
    ]
