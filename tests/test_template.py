import hashlib
import json
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
# Hash listing of a study repo generated with ANSWERS before the evidence variant
# was added; study output must stay byte-identical to it.
STUDY_BASELINE = Path(__file__).parent / "fixtures" / "study_baseline.json"


def generate(tmp_path, **overrides):
    destination = tmp_path / "generated"
    data = {**ANSWERS, "purpose": "side_project", "confidentiality": "public", **overrides}
    copier.run_copy(str(TEMPLATE), destination, data=data, defaults=True, unsafe=False)
    return destination


def tree_hashes(repo):
    """Map each generated file's POSIX path to the sha256 of its bytes.

    CRLF is normalized to LF before hashing so the listing is the same whether
    git checked the template out with Windows or Unix line endings.
    """
    hashes = {}
    for path in sorted(repo.rglob("*")):
        if path.is_file():
            data = path.read_bytes().replace(b"\r\n", b"\n")
            hashes[path.relative_to(repo).as_posix()] = hashlib.sha256(data).hexdigest()
    return hashes


def test_study_output_is_byte_identical_to_baseline(tmp_path):
    baseline = json.loads(STUDY_BASELINE.read_text(encoding="utf-8"))
    assert tree_hashes(generate(tmp_path)) == baseline


def test_study_env_example_is_raw_copy_of_template_source(tmp_path):
    # tree_hashes normalizes CRLF, so check this raw-copied file byte for byte.
    source = TEMPLATE / "{% if kind != 'evidence' %}.env.example{% endif %}"
    assert (generate(tmp_path) / ".env.example").read_bytes() == source.read_bytes()


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
    assert "github.com/AaronScherf/reprokit@v0.4.0" in pyproject


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


# --- evidence kind -----------------------------------------------------------
# Generated once per module; tests that only read share these repos.

@pytest.fixture(scope="module")
def evidence_repo(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("evidence"), kind="evidence")


@pytest.fixture(scope="module")
def screening_repo(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("screening"), kind="evidence", screening_pipeline=True)


def _src_pythonpath(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).parent.parent / "src"))


def test_minimal_evidence_repo_passes_validate_and_quick_check(evidence_repo, capfd, monkeypatch):
    assert main(["validate", str(evidence_repo)]) == 0, capfd.readouterr().out
    capfd.readouterr()
    _src_pythonpath(monkeypatch)
    started = time.perf_counter()
    assert main(["quick-check", str(evidence_repo)]) == 0, capfd.readouterr().out
    assert time.perf_counter() - started < 30
    output = capfd.readouterr().out
    assert "Quick check: PASS." in output
    assert "evidence" in output


def test_evidence_project_yaml_has_evidence_block(evidence_repo):
    from reprokit.loader import load_yaml
    charter, problems = load_yaml(evidence_repo / "project.yaml")
    assert problems == []
    assert charter["kind"] == "evidence"
    assert charter["evidence"]["manifest"] == "evidence/manifest.yaml"


def test_evidence_manifest_and_synthesis_are_generated(evidence_repo):
    from reprokit.evidence_manifest import load_manifest
    manifest, problems = load_manifest(evidence_repo / "evidence/manifest.yaml", confidentiality="public")
    assert problems == [] and manifest["sources"] == [] and manifest["schema_version"] == "0.1.0"
    assert (evidence_repo / "synthesis.md").is_file()
    assert "search" in (evidence_repo / "protocol.md").read_text().lower()


def test_evidence_repo_has_no_study_scaffolding(evidence_repo):
    for relative in ("data", "config.yaml", "compute.yaml", "agents.yaml",
                     "evidence/extraction_schema.yaml", "evidence/extractions"):
        assert not (evidence_repo / relative).exists(), relative


def test_study_repo_has_no_evidence_files(tmp_path):
    paths = json.loads(STUDY_BASELINE.read_text(encoding="utf-8"))
    assert not [p for p in paths if p == "synthesis.md" or p.startswith("evidence/")]
    # screening_pipeline cannot change study output.
    with_flag = generate(tmp_path / "a", kind="study", screening_pipeline=True)
    without_flag = generate(tmp_path / "b", kind="study")
    raw = lambda repo: {
        p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*") if p.is_file()
    }
    assert raw(with_flag) == raw(without_flag)


def test_evidence_gitignore_excludes_cache(evidence_repo):
    lines = (evidence_repo / ".gitignore").read_text().splitlines()
    for expected in ("/cache/", "/outputs/*", "/.env"):
        assert expected in lines
    assert "/data/raw/*" not in lines


def test_screening_pipeline_adds_extraction_and_compute_files(screening_repo, capfd):
    from reprokit.evidence_extraction import load_extraction_schema
    for relative in ("evidence/extraction_schema.yaml", "evidence/extractions/.gitkeep", "compute.yaml", "agents.yaml"):
        assert (screening_repo / relative).is_file(), relative
    schema, problems = load_extraction_schema(screening_repo / "evidence/extraction_schema.yaml")
    assert problems == [] and schema["fields"]
    assert not (screening_repo / "data").exists()
    assert main(["validate", str(screening_repo)]) == 0, capfd.readouterr().out


def test_migrated_manifest_passes_validate_on_screening_repo(screening_repo, tmp_path, capsys):
    import shutil
    repo = tmp_path / "repo"
    shutil.copytree(screening_repo, repo)
    review = Path(__file__).parent / "fixtures" / "evidence" / "literature_review_sample.md"
    manifest = str(repo / "evidence" / "manifest.yaml")
    assert main(["migrate-review", str(review), "--out", manifest, "--force"]) == 0
    assert main(["validate", str(repo)]) == 0, capsys.readouterr().out
    # Opting in to "included" without extraction records fails with the validate-time advice.
    assert main(["migrate-review", str(review), "--out", manifest, "--force", "--status", "included"]) == 0
    capsys.readouterr()
    assert main(["validate", str(repo)]) == 1
    out = capsys.readouterr().out
    assert "screening_status to candidate or excluded" in out and "--exclude" not in out


def test_evidence_docs_state_the_rules(evidence_repo):
    readme = (evidence_repo / "README.md").read_text()
    agents = (evidence_repo / "AGENTS.md").read_text()
    protocol = (evidence_repo / "protocol.md").read_text()
    for text in (readme, agents):
        for expected in ("cache/", "[@", "verify-sources", "evidence-run", "compute.yaml", "$1", "PDF"):
            assert expected in text, expected
    for expected in ("Search", "Screen", "Extract"):
        assert expected in protocol, expected


def test_evidence_generated_files_render_and_project_test_passes(screening_repo):
    for path in screening_repo.rglob("*"):
        if path.is_file():
            assert not re.search(r"(?<!\$)\{\{|\{%", path.read_text(encoding="utf-8")), path
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent / "src")}
    result = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], cwd=screening_repo,
                            env=env, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def _load_quick_check(repo):
    import importlib.util
    spec = importlib.util.spec_from_file_location("generated_quick_check", repo / "quick_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evidence_quick_check_uses_evidence_wording(evidence_repo, capsys):
    module = _load_quick_check(evidence_repo)
    assert module.main() == 0
    out = capsys.readouterr().out
    assert "A made-up fixture manifest went through validation, claim checking and aggregation" in out
    assert "raw data" not in out and "real-data build" not in out


def test_evidence_quick_check_reports_schema_problems_separately(evidence_repo, tmp_path, monkeypatch):
    from reprokit.problems import Problem
    # validate already loads the same schema, so a broken SCHEMA stops there; fake a loader-only failure.
    module = _load_quick_check(evidence_repo)
    monkeypatch.setattr(module, "load_extraction_schema", lambda path: (None, [Problem(str(path), "", "bad field")]))
    reason = module._run(tmp_path)
    assert reason.startswith("extraction schema problems: ") and "bad field" in reason


def test_evidence_quick_check_runs_offline_verify_sources(evidence_repo, tmp_path, monkeypatch):
    module = _load_quick_check(evidence_repo)
    assert "verify_sources" in (evidence_repo / "quick_check.py").read_text(encoding="utf-8")
    monkeypatch.setattr(module, "KNOWN_IDENTIFIERS", set())
    assert module._run(tmp_path).startswith("verify-sources reported: ")


def test_evidence_protocol_names_citation_form_and_commands(evidence_repo):
    protocol = (evidence_repo / "protocol.md").read_text(encoding="utf-8")
    for expected in ("`[@id]`", "`[@id1; @id2]`", "reprokit evidence-run", "reprokit verify-sources",
                     "reprokit migrate-review", "`candidate`"):
        assert expected in protocol, expected


def test_evidence_readme_and_agents_state_public_repo_rules(evidence_repo):
    for name in ("README.md", "AGENTS.md"):
        text = (evidence_repo / name).read_text(encoding="utf-8")
        for expected in ("confidential", "rejected", "restricted", "warning", "open pointer", "`candidate`",
                         "EPUB", "DjVu", "XPS", "transcriptions", "cache/"):
            assert expected in text, (name, expected)


def test_evidence_project_yaml_quick_check_comment(evidence_repo):
    text = (evidence_repo / "project.yaml").read_text(encoding="utf-8")
    assert "Replace the placeholder script" not in text
    assert "# The quick check runs made-up sources through reprokit's evidence checks" in text


def test_evidence_verification_note_and_env_example(evidence_repo):
    note = (evidence_repo / "notes" / "verification.md").read_text(encoding="utf-8")
    assert "Replace the template placeholder" not in note and "RUN_SUMMARY" not in note
    assert "verify-sources" in note and "made-up" in note
    env = (evidence_repo / ".env.example").read_text(encoding="utf-8")
    assert "Names are listed in the README" not in env and "ZOTERO_API_KEY" in env
