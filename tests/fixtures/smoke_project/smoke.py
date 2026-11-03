"""Tiny project-owned synthetic pipeline used by reprokit contract tests."""

import hashlib
import json
import time
from pathlib import Path

from reprokit.smoke import verify_smoke_result


def main() -> int:
    started = time.perf_counter()
    outputs = Path("outputs")
    outputs.mkdir(exist_ok=True)
    panel = outputs / "panel.csv"
    panel.write_text("month,count\n2020-01,2\n", encoding="utf-8")
    result = outputs / "smoke_result.json"
    result.write_text(json.dumps({"offline": True, "success": True, "elapsed_seconds": time.perf_counter() - started, "required_outputs": [
        {"path": "panel.csv", "sha256": hashlib.sha256(panel.read_bytes()).hexdigest()},
    ]}) + "\n", encoding="utf-8")
    check = verify_smoke_result(result, outputs)
    print(check.text)
    return int(not check.passed)


if __name__ == "__main__":
    raise SystemExit(main())
