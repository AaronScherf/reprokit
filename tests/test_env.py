import logging
import os

from reprokit.env import load_project_env


def test_project_env_parsing_and_environment_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    (tmp_path / ".env").write_text(
        "# comment\n\n EXISTING=file\nSINGLE='one two'\nDOUBLE=\"three four\"\nPLAIN=tail\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EXISTING", "ambient")
    for name in ("SINGLE", "DOUBLE", "PLAIN"):
        monkeypatch.delenv(name, raising=False)
    load_project_env(tmp_path)
    assert os.environ["EXISTING"] == "ambient"
    assert (os.environ["SINGLE"], os.environ["DOUBLE"], os.environ["PLAIN"]) == (
        "one two", "three four", "tail"
    )


def test_missing_project_env_is_ok(tmp_path):
    load_project_env(tmp_path)


def test_values_never_appear_in_output(tmp_path, monkeypatch, capsys, caplog):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    secret = "never-print-this-test-value"
    (tmp_path / ".env").write_text(f"SECRET_FOR_TEST='{secret}'\n", encoding="utf-8")
    monkeypatch.delenv("SECRET_FOR_TEST", raising=False)
    with caplog.at_level(logging.DEBUG):
        load_project_env(tmp_path)
    captured = capsys.readouterr()
    assert os.environ["SECRET_FOR_TEST"] == secret
    assert secret not in captured.out + captured.err + caplog.text
