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
