from .problems import Problem


def check_charter_consistency(doc: dict, path: str) -> list[Problem]:
    problems = []
    if doc.get("schema_version") == "0.2.0" and any(item.get("build", "").strip() for item in doc.get("deliverables", [])) and not doc.get("quick_check", "").strip():
        problems.append(Problem(path, "quick_check", "This project lists a build but has no quick check command. Add a quick_check command to project.yaml and retry."))
    audiences = {audience["name"]: audience for audience in doc.get("audiences", [])}
    for index, deliverable in enumerate(doc.get("deliverables", [])):
        name = deliverable.get("audience")
        if name not in audiences:
            problems.append(Problem(path, f"deliverables[{index}].audience", f"unknown audience: {name}"))
        elif doc.get("confidentiality") == "confidential" and audiences[name].get("channel") == "public" and not deliverable.get("requires_redaction"):
            problems.append(Problem(path, f"deliverables[{index}].requires_redaction", "public deliverable requires_redaction: true"))
    publication = doc.get("publication", {})
    if doc.get("purpose") in ("academic_publication", "dissertation") and not (publication.get("venues") or publication.get("preregistration")):
        problems.append(Problem(path, "publication", "academic purpose requires a venue or preregistration"))
    if "evidence" in doc and doc.get("kind") != "evidence":
        problems.append(Problem(path, "evidence", "This charter has an evidence block but its kind is not evidence. Set kind: evidence or remove the evidence block, then retry."))
    return problems
