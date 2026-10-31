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