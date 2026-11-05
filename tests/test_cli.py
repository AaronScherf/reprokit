import shutil
from pathlib import Path

from reprokit.cli import main
from reprokit.validate import validate_document

FIXTURE = Path(__file__).parent / "fixtures" / "repo_valid"


def repo(tmp_path):
    target = tmp_path / "repo"
    shutil.copytree(FIXTURE, target)
    return target


def test_validate_clean_repo_returns_0(tmp_path, capsys):
    assert main(["validate", str(repo(tmp_path))]) == 0
    output = capsys.readouterr().out
    assert "1 checked sources still use descriptor schema 0.1.0" in output
    assert "charter schema 0.1.0" in output


def test_validate_reports_every_problem_and_returns_1(tmp_path, capsys):
    target = repo(tmp_path)
    (target / "project.yaml").write_text("not: a charter\n")
    (target / "compute.yaml").write_text("not: a profile\n")
    assert main(["validate", str(target)]) == 1
    output = capsys.readouterr().out
    assert "project.yaml" in output and "compute.yaml" in output


def test_validate_skips_absent_optional_files(tmp_path):
    assert main(["validate", str(tmp_path)]) == 0


def test_validate_checks_every_descriptor(tmp_path, capsys):
    target = repo(tmp_path)
    (target / "data/descriptors/another.yaml").write_text("wrong: true\n")
    assert main(["validate", str(target)]) == 1
    assert "another.yaml" in capsys.readouterr().out


def test_manifest_command_writes_valid_file(tmp_path):
    target = repo(tmp_path)
    raw = target / "data/raw/prices"
    raw.mkdir(parents=True)
    (raw / "prices.csv").write_text("price\n1\n")
    out = target / "outputs/manifest.json"
    assert main(["manifest", "--config", str(target / "config.yaml"), "--raw-dir", str(target / "data/raw"), "--out", str(out)]) == 0
    assert validate_document(out, "manifest") == []


def test_validate_flags_reversed_period(tmp_path, capsys):
    target = repo(tmp_path)
    config = target / "config.yaml"
    config.write_text(config.read_text().replace("'2020-01-01'", "'2021-06-01'"))
    assert main(["validate", str(target)]) == 1
    assert "period.start" in capsys.readouterr().out


def test_validate_missing_directory_is_an_error(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "typo")]) == 1
    assert "typo" in capsys.readouterr().out


INSTANCES = Path(__file__).parent / "fixtures" / "repo_instances"


def instance_repo(tmp_path):
    target = tmp_path / "study"
    shutil.copytree(INSTANCES, target)
    return target


def set_provider(config, provider):
    text = config.read_text().replace("provider: Synthetic", f"provider: {provider}")
    config.write_text(text)


def test_validate_walks_every_instance(tmp_path, capsys):
    target = instance_repo(tmp_path)
    assert main(["validate", str(target)]) == 0
    (target / "instances/b/data/descriptors/prices.yaml").write_text("wrong: true\n")
    assert main(["validate", str(target)]) == 1
    output = capsys.readouterr().out
    assert "instances" in output and "b" in output and "prices.yaml" in output
    assert "instances/a" not in output.replace("\\", "/")


def test_validate_instance_period_rule(tmp_path, capsys):
    target = instance_repo(tmp_path)
    config = target / "instances/a/config.yaml"
    config.write_text(config.read_text().replace("'2020-01-01'", "'2021-06-01'"))
    assert main(["validate", str(target)]) == 1
    assert "period.start" in capsys.readouterr().out


def test_validate_checks_harmonization_records(tmp_path, capsys):
    target = instance_repo(tmp_path)
    record = target / "instances/b/harmonization/prices.yaml"
    record.write_text(record.read_text().replace("rationale: comparable staples exist in both\n", ""))
    assert main(["validate", str(target)]) == 1
    assert "rationale" in capsys.readouterr().out


def test_gate_blocks_provider_swap_without_record(tmp_path, capsys):
    target = instance_repo(tmp_path)
    set_provider(target / "instances/b/config.yaml", "Other")
    records = tmp_path / "no-records"
    records.mkdir()
    code = main(["gate", "--baseline", str(target / "instances/a/config.yaml"), "--config", str(target / "instances/b/config.yaml"), "--records", str(records)])
    assert code == 1
    output = capsys.readouterr().out
    assert "prices" in output and "prices.yaml" in output


def test_gate_passes_with_valid_record(tmp_path):
    target = instance_repo(tmp_path)
    set_provider(target / "instances/b/config.yaml", "Other")
    code = main(["gate", "--baseline", str(target / "instances/a/config.yaml"), "--config", str(target / "instances/b/config.yaml"), "--records", str(target / "instances/b/harmonization")])
    assert code == 0


def test_gate_exit_0_when_providers_match_ignoring_case(tmp_path):
    target = instance_repo(tmp_path)
    set_provider(target / "instances/b/config.yaml", "synthetic ")
    records = tmp_path / "none"
    records.mkdir()
    assert main(["gate", "--baseline", str(target / "instances/a/config.yaml"), "--config", str(target / "instances/b/config.yaml"), "--records", str(records)]) == 0


def test_gate_reports_invalid_config_before_comparing(tmp_path, capsys):
    target = instance_repo(tmp_path)
    (target / "instances/b/config.yaml").write_text("not: a config\n")
    code = main(["gate", "--baseline", str(target / "instances/a/config.yaml"), "--config", str(target / "instances/b/config.yaml"), "--records", str(tmp_path)])
    assert code == 1 and "config.yaml" in capsys.readouterr().out


def descriptor_v2(target, coverage="  start: '2020-01-01'\n  end: '2020-12-31'\n", note="notes/verification.md"):
    path = target / "data/descriptors/prices.yaml"
    text = path.read_text().replace("schema_version: 0.1.0", "schema_version: 0.2.0")
    text += f"\ncoverage_period:\n{coverage}verification_note: {note}\n"
    path.write_text(text)
    return path


def test_v2_descriptor_checks_coverage_and_note(tmp_path, capsys):
    target = repo(tmp_path)
    descriptor_v2(target)
    assert main(["validate", str(target)]) == 1
    assert "verification_note" in capsys.readouterr().out
    note = target / "notes/verification.md"
    note.parent.mkdir()
    note.write_text("Status: fixture-tested\n")
    assert main(["validate", str(target)]) == 0
    assert "charter schema 0.1.0" in capsys.readouterr().out


def test_v2_descriptor_reports_license_coverage_and_note_together(tmp_path, capsys):
    target = repo(tmp_path)
    descriptor = descriptor_v2(target, "  start: '2020-03-01'\n  end: '2020-10-31'\n")
    descriptor.write_text(descriptor.read_text().replace("reuse_terms: public domain", "reuse_terms: confirm before reuse"))
    assert main(["validate", str(target)]) == 1
    output = capsys.readouterr().out
    assert "reuse_terms" in output and "coverage_gap_note" in output and "verification_note" in output
    assert "Read the provider's page" in output
    assert "Add a coverage_gap_note" in output
    assert "Create it or correct its path" in output


def test_validate_prints_one_notice_for_old_verified_descriptors(tmp_path, capsys):
    target = instance_repo(tmp_path)
    assert main(["validate", str(target)]) == 0
    output = capsys.readouterr().out
    assert output.count("Notice:") == 1
    assert "2 checked sources still use descriptor schema 0.1.0" in output


def test_readme_states_verification_note_limit():
    text = (Path(__file__).parent.parent / "README.md").read_text()
    assert "does not prove the claim is true" in text
    assert "NOT yet run on acquired data" in text


def test_v2_descriptor_requires_gap_note_for_short_coverage(tmp_path, capsys):
    target = repo(tmp_path)
    descriptor = descriptor_v2(target, "  start: '2020-03-01'\n  end: '2020-10-31'\n")
    note = target / "notes/verification.md"
    note.parent.mkdir()
    note.write_text("fixture-tested\n")
    assert main(["validate", str(target)]) == 1
    assert "coverage_gap_note" in capsys.readouterr().out
    descriptor.write_text(descriptor.read_text() + "coverage_gap_note: Data only available March to October.\n")
    assert main(["validate", str(target)]) == 0


def test_v2_descriptor_note_must_match_status_and_stay_in_project(tmp_path, capsys):
    target = repo(tmp_path)
    descriptor = descriptor_v2(target)
    note = target / "notes/verification.md"
    note.parent.mkdir()
    note.write_text("source-verified\n")
    assert main(["validate", str(target)]) == 1
    assert "does not say 'fixture-tested'" in capsys.readouterr().out
    descriptor.write_text(descriptor.read_text().replace("notes/verification.md", "../outside.md"))
    assert main(["validate", str(target)]) == 1
    assert "inside the project" in capsys.readouterr().out


def test_v1_descriptor_does_not_require_coverage_or_note(tmp_path):
    target = repo(tmp_path)
    assert main(["validate", str(target)]) == 0


def test_v2_proposed_descriptor_allows_gap_and_missing_note(tmp_path):
    target = repo(tmp_path)
    descriptor = descriptor_v2(target, "  start: '2020-03-01'\n  end: '2020-10-31'\n")
    descriptor.write_text(descriptor.read_text().replace("verification_status: fixture-tested", "verification_status: proposed"))
    assert main(["validate", str(target)]) == 0


def test_v2_instance_uses_its_own_config(tmp_path, capsys):
    target = instance_repo(tmp_path)
    descriptor = target / "instances/a/data/descriptors/prices.yaml"
    descriptor.write_text(descriptor.read_text().replace("schema_version: 0.1.0", "schema_version: 0.2.0") +
                          "\ncoverage_period:\n  start: '2020-01-01'\n  end: '2020-12-31'\nverification_note: notes/verification.md\n")
    note = target / "notes/verification.md"
    note.parent.mkdir()
    note.write_text("fixture-tested\n")
    assert main(["validate", str(target)]) == 0
    config = target / "instances/a/config.yaml"
    config.write_text(config.read_text().replace("'2020-12-31'", "'2021-01-31'"))
    assert main(["validate", str(target)]) == 1
    assert "coverage_gap_note" in capsys.readouterr().out


def test_v2_charter_requires_quick_check_when_build_exists(tmp_path, capsys):
    target = repo(tmp_path)
    charter = target / "project.yaml"
    charter.write_text(charter.read_text().replace("schema_version: 0.1.0", "schema_version: 0.2.0"))
    assert main(["validate", str(target)]) == 1
    assert "Add a quick_check command" in capsys.readouterr().out
    charter.write_text(charter.read_text() + "\nquick_check: uv run reprokit quick-check\n")
    (target / "quick_check.py").write_text("print('PASS')\n")
    assert main(["validate", str(target)]) == 0
    assert "charter schema 0.1.0" not in capsys.readouterr().out


def test_v2_charter_with_no_build_needs_no_quick_check(tmp_path):
    target = repo(tmp_path)
    charter = target / "project.yaml"
    charter.write_text(charter.read_text().replace("schema_version: 0.1.0", "schema_version: 0.2.0").replace("build: make report", "build: ''"))
    assert main(["validate", str(target)]) == 0


def test_quick_check_missing_script_gives_next_step(tmp_path, capsys):
    assert main(["quick-check", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "Quick check: FAIL. The file `./quick_check.py` is missing" in output
    assert "README.md" in output and "uv run reprokit quick-check" in output


def test_validate_names_missing_quick_check_script(tmp_path, capsys):
    target = repo(tmp_path)
    charter = target / "project.yaml"
    charter.write_text(charter.read_text().replace("schema_version: 0.1.0", "schema_version: 0.2.0") + "\nquick_check: uv run reprokit quick-check\n")
    assert main(["validate", str(target)]) == 1
    assert "project.yaml names a quick check but quick_check.py is missing. Add the script or remove the line." in capsys.readouterr().out
