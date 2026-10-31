from pathlib import Path

import yaml

from .problems import Problem

TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings and rejects duplicate keys."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key: {key}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep)


_Loader.yaml_implicit_resolvers = {
    first_char: [(tag, pattern) for tag, pattern in resolvers if tag != TIMESTAMP_TAG]
    for first_char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_yaml(path: Path) -> tuple[dict | None, list[Problem]]:
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            doc = yaml.load(stream, Loader=_Loader)
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