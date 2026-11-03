import json
import re
from importlib import resources
from pathlib import Path

from jsonschema import Draft202012Validator

from .loader import load_yaml
from .problems import Problem

_PLACEHOLDER_TERMS = re.compile(r"\b(?:confirm|unverified|tbd|verify)\b", re.IGNORECASE)
_VERIFIED_STATES = {"source-verified", "fixture-tested", "run on acquired data", "independently reproduced"}


def _location(parts) -> str:
    result = ""
    for part in parts:
        result += f"[{part}]" if isinstance(part, int) else (f".{part}" if result else str(part))
    return result


def check_descriptor_license(doc: dict, path: Path) -> list[Problem]:
    if doc["verification_status"] not in _VERIFIED_STATES:
        return []
    result = []
    if doc["access_class"] == "unverified":
        result.append(Problem(str(path), "access_class", "Access is still marked unverified, but this source is marked as checked. Read the provider's access instructions and set the correct access class."))
    terms = doc["reuse_terms"]
    placeholder = _PLACEHOLDER_TERMS.search(terms)
    if not terms.strip():
        result.append(Problem(str(path), "reuse_terms", "The licence terms are blank, but this source is marked as checked. Read the provider's page and write the actual terms."))
    elif placeholder:
        result.append(Problem(str(path), "reuse_terms", f"The licence terms still say '{placeholder.group()}', but this source is marked as checked. Read the provider's page and write the actual terms."))
    return result


def validate_document(path: Path, schema_name: str, *, include_claims: bool = True) -> list[Problem]:
    doc, problems = load_yaml(path)
    if problems:
        return problems
    if schema_name == "descriptor" and isinstance(doc, dict):
        version = doc.get("schema_version")
        if version not in {"0.1.0", "0.2.0"}:
            return [Problem(str(path), "schema_version", f"unsupported descriptor schema version: {version}")]
        if version == "0.2.0":
            schema_name = "descriptor_0_2"
    if schema_name == "charter" and isinstance(doc, dict):
        version = doc.get("schema_version")
        if version not in {"0.1.0", "0.2.0"}:
            return [Problem(str(path), "schema_version", f"This charter uses an unsupported schema version ({version}). Set it to 0.1.0 or 0.2.0 and retry.")]
        if version == "0.2.0":
            schema_name = "charter_0_2"
    schema_file = resources.files("reprokit").joinpath("schemas", f"{schema_name}.json")
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    errors = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(doc)
    result = []
    for error in sorted(errors, key=lambda item: (list(map(str, item.path)), item.message)):
        location = _location(error.path)
        message = error.message
        if error.validator == "required":
            missing = re.search(r"'([^']+)' is a required property", message)
            if missing:
                location = _location([*error.path, missing.group(1)])
        if error.validator == "enum":
            message += f"; allowed values: {error.validator_value}"
        if schema_name == "charter_0_2" and (location == "quick_check" or (error.validator == "required" and "quick_check" in message)):
            location = "quick_check"
            message = "This project lists a build but has no quick check command. Add a quick_check command to project.yaml and retry."
        result.append(Problem(str(path), location, message))
    if include_claims and not result and schema_name in {"descriptor", "descriptor_0_2"}:
        result.extend(check_descriptor_license(doc, path))
    return result
