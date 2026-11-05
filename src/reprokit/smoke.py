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


def _fail(reason: str, action: str = "Run `uv sync --locked` to restore the project's packages.") -> QuickCheckResult:
    sentence = reason if reason.endswith((".", "!", "?")) else f"{reason}."
    return QuickCheckResult(False, f"Quick check: FAIL. {sentence}\nQuick check: The file `./quick_check.py` in the project folder runs this test. See 'If the quick check fails' in README.md.\nQuick check: What to do: {action} Then type `uv run reprokit quick-check` again.")


def verify_smoke_result(result_path: Path, output_root: Path) -> QuickCheckResult:
    """Verify the recorded offline run and required files, then return readable text."""
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _fail("The quick check result could not be read.")
    if not isinstance(result, dict):
        return _fail("The quick check result is incomplete.")
    if result.get("offline") is not True:
        return _fail("The quick check was not recorded as offline.", "Remove network calls from `./quick_check.py`.")
    if result.get("success") is not True:
        step = result.get("failed_step")
        reason = result.get("failure_reason")
        if isinstance(step, str) and step and isinstance(reason, str) and reason:
            return _fail(f'The step "{step}" stopped: {reason}')
        return _fail("The quick check did not finish its made-up-data run.")
    outputs = result.get("required_outputs")
    if not isinstance(outputs, list) or not outputs:
        return _fail("The quick check did not list a final output to check.", "Record the final table and its checksum in `./quick_check.py`.")
    root = output_root.resolve()
    for item in outputs:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            return _fail("A final output has no file name or checksum.", "Record both in the quick check result made by `./quick_check.py`.")
        target = (root / item["path"]).resolve()
        if not target.is_relative_to(root) or target == root:
            return _fail("A final output points outside the quick check folder.", "Keep made-up-data outputs inside that folder.")
        if not target.is_file():
            return _fail(f'The final output "{item["path"]}" is missing.')
        if hash_file(target) != item["sha256"]:
            return _fail(f'The final output "{item["path"]}" no longer matches its checksum.', "Check that `./quick_check.py` records the checksum of the table it just made.")
    elapsed = result.get("elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or not math.isfinite(elapsed) or elapsed < 0:
        return _fail("The quick check did not record how long it took.", "Record elapsed time in `./quick_check.py`.")
    seconds = round(elapsed)
    unit = "second" if seconds == 1 else "seconds"
    return QuickCheckResult(True, f"Quick check: PASS. The project ran from raw data to final table on made-up data in {seconds} {unit}.\nQuick check: Your basic setup works. This does not test the real data.\nQuick check: Next, type `uv run reprokit validate`. See 'After the quick check' in README.md for the real-data build.")
