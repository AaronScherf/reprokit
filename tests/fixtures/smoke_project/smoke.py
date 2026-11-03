"""Tiny project-owned synthetic pipeline used by reprokit contract tests."""

import hashlib
import json
from pathlib import Path

from reprokit.smoke import verify_smoke_result


def main() -> int:
    outputs = Path("outputs")
    outputs.mkdir(exist_ok=True)
    panel = outputs / "panel.csv"
    panel.write_text("month,count\n2020-01,2\n", encoding="utf-8")
    result = outputs / "smoke_result.json"
    result.write_text(json.dumps({"offline": True, "success": True, "required_outputs": [
        {"path": "panel.csv", "sha256": hashlib.sha256(panel.read_bytes()).hexdigest()},
    ]}) + "\n", encoding="utf-8")
    problems = verify_smoke_result(result, outputs)
    for problem in problems:
        print(problem)
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
