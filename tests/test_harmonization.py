from reprokit.harmonization import check_gate, structural_changes

BASE = {"displacement": {"provider": "UNHCR/NRC", "dataset": "x"}}
NEW = {"displacement": {"provider": "IOM", "dataset": "y"}}


def test_case_and_whitespace_difference_is_not_structural():
    assert structural_changes({"conflict": {"provider": "ACLED "}}, {"conflict": {"provider": "acled"}}) == []


def test_different_provider_is_structural():
    assert structural_changes(BASE, NEW) == ["displacement"]


def test_gate_blocks_without_record(tmp_path):
    problems = check_gate(BASE, NEW, tmp_path)
    assert len(problems) == 1
    assert "displacement" in str(problems[0]) and str(tmp_path / "displacement.yaml") in str(problems[0])


def test_gate_passes_with_valid_record(tmp_path):
    (tmp_path / "displacement.yaml").write_text("schema_version: 0.1.0\nrole: displacement\nfrom_source: UNHCR/NRC\nto_source: IOM\ndifferences: changed categories\ndecision: harmonize\nrationale: comparable\naffected_outputs: []\napproved_by: owner\ndate: '2026-10-31'\n")
    assert check_gate(BASE, NEW, tmp_path) == []


def test_gate_rejects_record_missing_rationale(tmp_path):
    (tmp_path / "displacement.yaml").write_text("schema_version: 0.1.0\nrole: displacement\nfrom_source: UNHCR/NRC\nto_source: IOM\ndifferences: changed categories\ndecision: harmonize\naffected_outputs: []\napproved_by: owner\ndate: '2026-10-31'\n")
    assert "rationale" in str(check_gate(BASE, NEW, tmp_path)[0])