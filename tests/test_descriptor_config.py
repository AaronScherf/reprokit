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


GATED = "access_class: account_required\n"
PROVENANCE = "accessed: '2026-10-31'\napplied_filters: country Somalia, 1997-01-01 to 2025-10-31\nmanipulation: aggregated to district-month counts\n"


def test_open_descriptor_needs_no_provenance_fields():
    assert validate_document(ROOT / "descriptor_valid.yaml", "descriptor") == []


def test_gated_descriptor_requires_accessed_filters_and_manipulation(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "access_class: open\n", GATED)
    text = " ".join(str(problem) for problem in validate_document(path, "descriptor"))
    assert "accessed" in text and "applied_filters" in text and "manipulation" in text


def test_gated_descriptor_with_provenance_passes(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "access_class: open\n", GATED + PROVENANCE)
    assert validate_document(path, "descriptor") == []


def test_request_required_descriptor_also_needs_provenance(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "access_class: open\n", "access_class: request_required\n")
    assert any("accessed" in str(problem) for problem in validate_document(path, "descriptor"))


def test_accessed_must_be_a_real_date(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "access_class: open\n", GATED + PROVENANCE.replace("2026-10-31", "2026-02-31"))
    assert any("accessed" in str(problem) for problem in validate_document(path, "descriptor"))


def test_proposed_descriptor_allows_placeholder_access_and_terms(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "access_class: open", "access_class: unverified")
    path.write_text(path.read_text().replace("reuse_terms: public domain", "reuse_terms: confirm before reuse").replace("verification_status: fixture-tested", "verification_status: proposed"))
    assert validate_document(path, "descriptor") == []


def test_verified_descriptor_rejects_placeholder_access_and_terms(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "access_class: open", "access_class: unverified")
    path.write_text(path.read_text().replace("reuse_terms: public domain", "reuse_terms: confirm before reuse").replace("verification_status: fixture-tested", "verification_status: source-verified"))
    assert [problem.location for problem in validate_document(path, "descriptor")] == ["access_class", "reuse_terms"]


def test_verified_descriptor_rejects_empty_and_tbd_terms(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "reuse_terms: public domain", "reuse_terms: '   '")
    assert [problem.location for problem in validate_document(path, "descriptor")] == ["reuse_terms"]
    path.write_text(path.read_text().replace("reuse_terms: '   '", "reuse_terms: TBD"))
    assert [problem.location for problem in validate_document(path, "descriptor")] == ["reuse_terms"]


def test_descriptor_v2_requires_dated_coverage_period(tmp_path):
    path = change(tmp_path, "descriptor_valid.yaml", "schema_version: 0.1.0", "schema_version: 0.2.0")
    assert any(problem.location == "coverage_period" for problem in validate_document(path, "descriptor"))
    path.write_text(path.read_text() + "\ncoverage_period:\n  start: '2020-02-31'\n  end: '2020-12-31'\n")
    assert any(problem.location == "coverage_period.start" for problem in validate_document(path, "descriptor"))
