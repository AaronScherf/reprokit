import json
import re
from importlib import resources
from pathlib import Path

from jsonschema import Draft202012Validator

from .loader import load_yaml
from .problems import Problem


def _location(parts) -> str:
    result = ""
    for part in parts:
        result += f"[{part}]" if isinstance(part, int) else (f".{part}" if result else str(part))
    return result


def validate_document(path: Path, schema_name: str) -> list[Problem]:
    doc, problems = load_yaml(path)
    if problems:
        return problems
    schema_file = resources.files("reprokit").joinpath("schemas", f"{schema_name}.json")
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    errors = Draft202012Validator(schema).iter_errors(doc)
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
        result.append(Problem(str(path), location, message))
    return result