from reprokit.charter_rules import check_charter_consistency


def charter():
    return {"purpose": "side_project", "confidentiality": "confidential", "audiences": [{"name": "readers", "channel": "public"}], "deliverables": [{"id": "report", "audience": "readers"}], "publication": {"venues": [], "preregistration": ""}}


def test_confidential_with_public_deliverable_fails_without_redaction():
    assert "requires_redaction" in str(check_charter_consistency(charter(), "project.yaml")[0])


def test_redaction_flag_clears_it():
    doc = charter()
    doc["deliverables"][0]["requires_redaction"] = True
    assert check_charter_consistency(doc, "project.yaml") == []


def test_unknown_deliverable_audience_names_it():
    doc = charter()
    doc["deliverables"][0]["audience"] = "unknown"
    assert "unknown" in str(check_charter_consistency(doc, "project.yaml")[0])


def test_academic_without_venue_or_preregistration_fails():
    doc = charter()
    doc["purpose"] = "academic_publication"
    doc["deliverables"] = []
    assert "publication" in str(check_charter_consistency(doc, "project.yaml")[0])


def test_side_project_needs_no_venue():
    doc = charter()
    doc["deliverables"] = []
    assert check_charter_consistency(doc, "project.yaml") == []