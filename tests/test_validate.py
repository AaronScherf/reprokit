from pathlib import Path

from reprokit.validate import validate_document

FIXTURE = Path(__file__).parent / "fixtures" / "charter_valid.yaml"


def test_valid_charter_has_no_problems():
    assert validate_document(FIXTURE, "charter") == []


def test_unknown_key_names_the_key(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text(FIXTURE.read_text() + "\nconfidentialty: public\n")
    problems = validate_document(path, "charter")
    assert len(problems) == 1
    assert "confidentialty" in problems[0].message


def test_missing_required_field_names_location(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text(FIXTURE.read_text().replace("purpose: side_project\n", ""))
    problems = validate_document(path, "charter")
    assert len(problems) == 1
    assert problems[0].location in ("purpose", "")
    assert "purpose" in problems[0].message


def test_bad_enum_lists_allowed_values(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text(FIXTURE.read_text().replace("confidentiality: public", "confidentiality: secret"))
    assert "private_until_release" in validate_document(path, "charter")[0].message


def test_charter_0_1_0_with_evidence_block_is_rejected_with_upgrade_advice(tmp_path):
    path = tmp_path / "project.yaml"
    text = FIXTURE.read_text().replace("kind: study", "kind: evidence")
    path.write_text(text + "\nevidence:\n  manifest: evidence/manifest.yaml\n")
    problems = validate_document(path, "charter")
    assert [p.location for p in problems] == ["evidence"]
    assert "schema_version: 0.2.0" in problems[0].message


def test_verified_states_is_public():
    from reprokit.validate import VERIFIED_STATES

    assert "source-verified" in VERIFIED_STATES and "proposed" not in VERIFIED_STATES


def test_verified_states_has_one_definition():
    from reprokit import descriptor_rules, validate

    assert validate.VERIFIED_STATES is descriptor_rules.VERIFIED_STATES
