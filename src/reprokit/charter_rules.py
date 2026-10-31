from .problems import Problem


def check_charter_consistency(doc: dict, path: str) -> list[Problem]:
    problems = []
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
    return problems