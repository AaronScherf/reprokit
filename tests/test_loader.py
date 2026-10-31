from pathlib import Path

from reprokit.loader import load_yaml


def test_missing_file_gives_one_problem(tmp_path):
    doc, problems = load_yaml(tmp_path / "missing.yaml")
    assert doc is None and len(problems) == 1
    assert "not found" in problems[0].message


def test_empty_file_gives_one_problem(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("")
    doc, problems = load_yaml(path)
    assert doc is None and len(problems) == 1
    assert "empty" in problems[0].message


def test_invalid_yaml_reports_line(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("thing: [oops\n")
    doc, problems = load_yaml(path)
    assert doc is None and len(problems) == 1
    assert "line" in problems[0].message


def test_crlf_and_bom_file_loads(tmp_path):
    source = Path(__file__).parent / "fixtures" / "charter_valid.yaml"
    raw = source.read_bytes().replace(b"\n", b"\r\n")
    path = tmp_path / "windows.yaml"
    path.write_bytes(b"\xef\xbb\xbf" + raw)
    assert b"\r\n" in path.read_bytes()
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert load_yaml(path) == load_yaml(source)