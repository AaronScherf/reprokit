import os
import re
import subprocess
import sys
import time
from pathlib import Path

import copier
import pytest

from reprokit.cli import main

TEMPLATE = Path(__file__).parent.parent / "template"
ANSWERS = {"project_name": "Demo Study", "author": "Test Author"}


def generate(tmp_path, **overrides):
    destination = tmp_path / "generated"
    data = {**ANSWERS, "purpose": "side_project", "confidentiality": "public", **overrides}
    copier.run_copy(str(TEMPLATE), destination, data=data, defaults=True, unsafe=False)
    return destination


@pytest.mark.parametrize(
    ("purpose", "confidentiality"),
    [
        ("academic_publication", "public"),
        ("dissertation", "private_until_release"),
        ("consulting", "confidential"),
        ("side_project", "public"),
    ],
)
def test_generated_repo_passes_reprokit_validate(tmp_path, capsys, purpose, confidentiality):
    repo = generate(tmp_path, purpose=purpose, confidentiality=confidentiality)
    assert main(["validate", str(repo)]) == 0, capsys.readouterr().out


def test_generated_gitignore_excludes_raw_derived_outputs_and_env(tmp_path):
    lines = (generate(tmp_path) / ".gitignore").read_text().splitlines()
    for expected in ("/data/raw/*", "/data/derived/*", "/outputs/*", "/.env"):
        assert expected in lines


def test_generated_gitattributes_preserves_data_bytes(tmp_path):
    repo = generate(tmp_path)
    assert (repo / ".gitattributes").is_file()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    result = subprocess.run(
        ["git", "check-attr", "text", "--", "data/derived/example.csv"],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "data/derived/example.csv: text: unset"


def test_generated_agents_md_has_derivative_rules_and_restricted_data_rule(tmp_path):
    text = (generate(tmp_path) / "AGENTS.md").read_text()
    assert "## Derivative rules" in text
    assert "external AI" in text and "reprokit validate" in text


def test_generated_agents_yaml_forbids_restricted_data_to_external_ai(tmp_path):
    assert "restricted_data_to_external_ai: false" in (generate(tmp_path) / "agents.yaml").read_text()


def test_generated_ci_runs_validate_and_secret_scan(tmp_path):
    ci = (generate(tmp_path) / ".github/workflows/ci.yml").read_text()
    assert "uv sync --locked" in ci and "reprokit validate" in ci and "gitleaks" in ci
    assert "ubuntu-latest, windows-latest" in ci
    assert "uv run reprokit quick-check" in ci and "timeout-minutes: 1" in ci
    assert ci.index("uv run reprokit quick-check") < ci.index("uv run reprokit validate") < ci.index("uv run pytest")


def test_generated_dependency_pins_v03_tag(tmp_path):
    pyproject = (generate(tmp_path) / "pyproject.toml").read_text()
    assert "github.com/AaronScherf/reprokit@v0.3.2" in pyproject


def test_generated_project_has_a_passing_unit_test(tmp_path):
    repo = generate(tmp_path)
    assert (repo / "tests/test_project.py").is_file()
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")}
    result = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=repo, env=env, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_placeholder_quick_check_is_readable_and_fast(tmp_path, capfd, monkeypatch):
    repo = generate(tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).parent.parent / "src"))
    started = time.perf_counter()
    assert main(["quick-check", str(repo)]) == 0
    assert time.perf_counter() - started < 60
    output = capfd.readouterr().out
    assert "Quick check: This is the template's placeholder in `./quick_check.py` in the project folder." in output
    assert "Quick check: It checks nothing about your project yet. Edit that file before relying on this as evidence." in output
    assert "Quick check: PASS. The project ran from raw data to final table on made-up data" in output
    assert "This does not test the real data" in output


def test_generated_readme_and_note_link_run_summary(tmp_path):
    repo = generate(tmp_path)
    readme = (repo / "README.md").read_text()
    note = (repo / "notes/verification.md").read_text()
    assert "uv run reprokit quick-check" in readme
    assert "outputs/RUN_SUMMARY.md" in readme
    assert "../outputs/RUN_SUMMARY.md" in note
    assert "13 minutes" not in readme and "4,292" not in readme


def test_generated_readme_explains_account_setup(tmp_path):
    readme = (generate(tmp_path) / "README.md").read_text()
    for expected in ("## Accounts and keys", "copy .env.example .env", "cp .env.example .env",
                     "reprokit.env", "git-ignored", "never be committed"):
        assert expected in readme


def test_generated_fetch_guidance_covers_partial_failures_and_manual_downloads(tmp_path):
    repo = generate(tmp_path)
    for path in (repo / "README.md", repo / "protocol.md"):
        text = path.read_text()
        for expected in ("## Fetching data", "each failure", "non-zero", "public downloads",
                         "overwrite", "refresh", "manual"):
            assert expected in text, (path, expected)


def test_generated_readme_explains_first_commands_and_results(tmp_path):
    readme = (generate(tmp_path) / "README.md").read_text()
    for expected in ("PowerShell", "Terminal", "cd C:\\path\\to\\demo-study", "uv lock", "uv sync --locked", "python -m uv", "PASS", "does not show", "After the quick check", "If the quick check fails", "Checksum"):
        assert expected in readme


def test_generated_readme_declares_ai_and_compute_costs(tmp_path):
    assert "## AI and compute" in (generate(tmp_path) / "README.md").read_text()


def test_generated_files_have_no_unrendered_template_syntax(tmp_path):
    for path in generate(tmp_path).rglob("*"):
        if path.is_file():
            assert not re.search(r"(?<!\$)\{\{|\{%", path.read_text(encoding="utf-8")), path


def test_generated_layout_has_data_dirs(tmp_path):
    repo = generate(tmp_path)
    for relative in ("data/raw/.gitkeep", "data/derived/.gitkeep", "data/descriptors/.gitkeep", "outputs/.gitkeep", "comms/.gitkeep"):
        assert (repo / relative).exists(), relative


def test_confidentiality_question_is_required(tmp_path):
    with pytest.raises(Exception, match="confidentiality"):
        copier.run_copy(str(TEMPLATE), tmp_path / "x", data={**ANSWERS, "purpose": "side_project"}, defaults=True, unsafe=False)
