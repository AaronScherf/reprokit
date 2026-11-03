"""Check a project's recorded synthetic smoke result and its outputs."""

import json
from pathlib import Path

from .manifest import hash_file
from .problems import Problem


def verify_smoke_result(result_path: Path, output_root: Path) -> list[Problem]:
    """Return one problem per missing claim or mismatched required output."""
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [Problem(str(result_path), "", f"cannot read smoke result: {exc}")]
    if not isinstance(result, dict):
        return [Problem(str(result_path), "", "smoke result must be an object")]
    problems = []
    if result.get("offline") is not True:
        problems.append(Problem(str(result_path), "offline", "must be true"))
    if result.get("success") is not True:
        problems.append(Problem(str(result_path), "success", "must be true"))
    outputs = result.get("required_outputs")
    if not isinstance(outputs, list) or not outputs:
        return problems + [Problem(str(result_path), "required_outputs", "must list at least one required output")]
    root = output_root.resolve()
    for index, item in enumerate(outputs):
        location = f"required_outputs[{index}]"
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            problems.append(Problem(str(result_path), location, "requires path and sha256 strings"))
            continue
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or path == root:
            problems.append(Problem(str(result_path), f"{location}.path", "must stay inside output root"))
        elif not path.is_file():
            problems.append(Problem(str(result_path), f"{location}.path", f"file not found: {item['path']}"))
        elif hash_file(path) != item["sha256"]:
            problems.append(Problem(str(result_path), f"{location}.sha256", "does not match output file"))
    return problems
