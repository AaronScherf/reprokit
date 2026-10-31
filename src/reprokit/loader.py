from pathlib import Path

import yaml

from .problems import Problem


def load_yaml(path: Path) -> tuple[dict | None, list[Problem]]:
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            doc = yaml.safe_load(stream)
    except FileNotFoundError:
        return None, [Problem(str(path), "", "file not found")]
    except (OSError, UnicodeError) as exc:
        return None, [Problem(str(path), "", str(exc))]
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f"line {mark.line + 1}" if mark else ""
        return None, [Problem(str(path), location, f"invalid YAML at {location}: {exc}")]
    if doc is None:
        return None, [Problem(str(path), "", "empty YAML file")]
    if not isinstance(doc, dict):
        return None, [Problem(str(path), "", "expected a mapping")]
    return doc, []