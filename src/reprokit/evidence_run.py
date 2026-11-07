def _empty(value) -> bool:
    return value is None or value is False or value == "" or value == []


def aggregate(manifest: dict, records: dict, schema: dict, *, only: set[str] | None = None,
              exclude: set[str] = frozenset()) -> dict:
    """Combine extraction records of included sources; pure, never calls an AI service."""
    used = [
        s["id"] for s in manifest.get("sources", [])
        if s.get("screening_status") == "included" and s["id"] in records
        and (only is None or s["id"] in only) and s["id"] not in exclude
    ]
    fields = {}
    for name, spec in schema["fields"].items():
        values = [records[sid]["fields"][name] for sid in used if name in records[sid]["fields"]]
        mode = spec["aggregate"]
        if mode == "count":
            fields[name] = sum(not _empty(v) for v in values)
        elif mode == "sum":
            fields[name] = sum(v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool))
        elif mode == "list":
            fields[name] = sorted({item for v in values for item in v}, key=str)
    cost = round(sum(records[sid].get("cost", {}).get("usd", 0) for sid in used), 6)
    return {"sources": used, "fields": fields, "cost_usd": cost}


def delta(full: dict, subset: dict) -> dict:
    """Per-field change from the full aggregate to a subset, plus the source ids removed."""
    changes = {}
    for name, whole in full["fields"].items():
        part = subset["fields"].get(name)
        if isinstance(whole, list):
            changes[name] = {"removed": [x for x in whole if x not in part], "added": [x for x in part if x not in whole]}
        else:
            changes[name] = part - whole
    return {"removed": [s for s in full["sources"] if s not in subset["sources"]],
            "fields": changes, "cost_usd": round(subset["cost_usd"] - full["cost_usd"], 6)}
