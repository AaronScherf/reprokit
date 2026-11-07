from pathlib import Path

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

EVIDENCE_BLOCK = {"manifest": "evidence/manifest.yaml", "inclusion_criteria": ["peer reviewed"], "search_protocol": "protocol.md", "zotero_group": "12345"}


def test_evidence_block_valid_for_evidence_kind(tmp_path):
    import yaml

    from reprokit.validate import validate_document

    base = yaml.safe_load((Path(__file__).parent / "fixtures" / "charter_valid.yaml").read_text())
    base.update({"schema_version": "0.2.0", "kind": "evidence", "quick_check": "python quick_check.py", "evidence": EVIDENCE_BLOCK})
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(base))
    assert validate_document(path, "charter") == []
    assert check_charter_consistency(base, str(path)) == []
    base["evidence"] = {"bogus": 1}
    path.write_text(yaml.safe_dump(base))
    assert validate_document(path, "charter") != []


def test_evidence_block_rejected_for_study_kind():
    doc = {**charter(), "kind": "study", "evidence": EVIDENCE_BLOCK}
    problems = check_charter_consistency(doc, "project.yaml")
    text = " ".join(p.message for p in problems)
    assert "kind: evidence" in text and "remove" in text
    assert any(p.location == "evidence" for p in problems)


def test_existing_0_1_and_0_2_charters_still_validate(tmp_path):
    import yaml

    from reprokit.validate import validate_document

    fixture = Path(__file__).parent / "fixtures" / "charter_valid.yaml"
    assert validate_document(fixture, "charter") == []
    doc = yaml.safe_load(fixture.read_text())
    doc.update({"schema_version": "0.2.0", "quick_check": "python quick_check.py"})
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(doc))
    assert validate_document(path, "charter") == []
