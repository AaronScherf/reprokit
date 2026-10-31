from datetime import date

from .problems import Problem


def check_config_consistency(doc: dict, path: str) -> list[Problem]:
    period = doc.get("period", {})
    start = date.fromisoformat(period["start"])
    end = date.fromisoformat(period["end"])
    if start > end:
        return [Problem(path, "period.start", f"period.start ({start}) is after period.end ({end})")]
    return []
