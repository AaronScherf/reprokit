from pathlib import Path

from reprokit.validate import validate_document

ROOT = Path(__file__).parent / "fixtures"


def change(tmp_path, fixture, old, new):
    path = tmp_path / fixture
    path.write_text((ROOT / fixture).read_text().replace(old, new))
    return path


def test_valid_descriptor_passes():
    assert validate_document(ROOT / "descriptor_valid.yaml", "descriptor") == []


def test_descriptor_requires_find_in_other_geography(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "find_in_other_geography: Find a price series", "")
    assert "find_in_other_geography" in str(validate_document(path, "descriptor")[0])


def test_descriptor_variables_need_meaning_and_unit(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "    meaning: item price\n    unit: USD\n", "")
    assert len(validate_document(path, "descriptor")) == 2


def test_valid_config_passes():
    assert validate_document(ROOT / "config_valid.yaml", "config") == []


def test_config_unknown_top_level_key_fails(tmp_path):
    path = change(tmp_path, "config_valid.yaml", "geography: Exampleland", "geography: Exampleland\ngeografy: wrong")
    assert "geografy" in str(validate_document(path, "config")[0])


def test_config_source_needs_role_and_provider(tmp_path):
    path = change(tmp_path, "config_valid.yaml", "    provider: Synthetic\n", "")
    assert "provider" in str(validate_document(path, "config")[0])

def test_config_impossible_date_is_rejected(tmp_path):
    path = change(tmp_path, "config_valid.yaml", "'2020-01-01'", "'2020-13-45'")
    assert any("period.start" in str(problem) for problem in validate_document(path, "config"))


def test_config_non_date_text_is_rejected(tmp_path):
    path = change(tmp_path, "config_valid.yaml", "'2020-12-31'", "tomorrow")
    assert any("period.end" in str(problem) for problem in validate_document(path, "config"))
