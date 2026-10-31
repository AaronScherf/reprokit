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
    assert capsys.readouterr().out == ""


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
