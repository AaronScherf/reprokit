"""Check a project's made-up-data run and explain the result plainly."""

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .manifest import hash_file


@dataclass(frozen=True)
class QuickCheckResult:
    passed: bool
    text: str


def _fail(reason: str, action: str = "run `uv sync --locked` again, then retry.") -> QuickCheckResult:
    sentence = reason if reason.endswith((".", "!", "?")) else f"{reason}."
    return QuickCheckResult(False, f"FAIL  {sentence}\n      What to do: {action}")


def verify_smoke_result(result_path: Path, output_root: Path) -> QuickCheckResult:
    """Verify the recorded offline run and required files, then return readable text."""
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _fail("The quick check result could not be read.")
    if not isinstance(result, dict):
        return _fail("The quick check result is incomplete.")
    if result.get("offline") is not True:
        return _fail("The quick check was not recorded as offline.", "remove network calls from the quick check, then retry.")
    if result.get("success") is not True:
        step = result.get("failed_step")
        reason = result.get("failure_reason")
        if isinstance(step, str) and step and isinstance(reason, str) and reason:
            return _fail(f'The step "{step}" stopped: {reason}')
        return _fail("The quick check did not finish its made-up-data run.")
    outputs = result.get("required_outputs")
    if not isinstance(outputs, list) or not outputs:
        return _fail("The quick check did not list a final output to check.", "record the final table and its checksum, then retry.")
    root = output_root.resolve()
    for item in outputs:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            return _fail("A final output has no file name or checksum.", "record both in the quick check result, then retry.")
        target = (root / item["path"]).resolve()
        if not target.is_relative_to(root) or target == root:
            return _fail("A final output points outside the quick check folder.", "keep made-up-data outputs inside that folder, then retry.")
        if not target.is_file():
            return _fail(f'The final output "{item["path"]}" is missing.')
        if hash_file(target) != item["sha256"]:
            return _fail(f'The final output "{item["path"]}" no longer matches its checksum.', "run quick-check again so it makes and checks a fresh table.")
    elapsed = result.get("elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or not math.isfinite(elapsed) or elapsed < 0:
        return _fail("The quick check did not record how long it took.", "record its elapsed time, then retry.")
    seconds = round(elapsed)
    unit = "second" if seconds == 1 else "seconds"
    return QuickCheckResult(True, f"PASS  The project ran from raw data to final table on made-up data in {seconds} {unit}.\n      Your setup works. This does not test the real data. For that, run: reproduce")
