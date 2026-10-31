import hashlib
import json
from datetime import UTC, datetime

import pytest

from reprokit.manifest import (
    build_manifest,
    collect_role_files,
    hash_file,
    write_manifest,
)
from reprokit.validate import validate_document


def test_hash_file_matches_hashlib(tmp_path):
    path = tmp_path / "bytes"
    path.write_bytes(b"known bytes")
    assert hash_file(path) == hashlib.sha256(b"known bytes").hexdigest()


def test_hash_of_empty_file_is_sha256_of_empty(tmp_path):
    path = tmp_path / "empty"
    path.touch()
    assert hash_file(path) == hashlib.sha256(b"").hexdigest()


def test_collect_role_files_is_sorted_recursive_and_skips_gitkeep(tmp_path):
    role = tmp_path / "prices"
    (role / "z").mkdir(parents=True)
    (role / "b.csv").write_text("b")
    (role / "z" / "a.csv").write_text("a")
    (role / ".gitkeep").touch()
    assert [p.relative_to(tmp_path).as_posix() for p in collect_role_files(tmp_path, ["prices"])["prices"]] == ["prices/b.csv", "prices/z/a.csv"]


def test_build_manifest_records_role_files_hashes_and_params(tmp_path):
    role = tmp_path / "prices"
    role.mkdir()
    (role / "a.csv").write_bytes(b"a")
    doc = build_manifest({"parameters": {"x": 1}}, collect_role_files(tmp_path, ["prices"]), tmp_path, "abc", {"pyyaml": "6"}, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert doc["parameters"] == {"x": 1}
    assert doc["inputs"]["prices"] == [{"path": "prices/a.csv", "sha256": hashlib.sha256(b"a").hexdigest()}]


def test_role_with_no_files_raises_filenotfounderror_naming_role(tmp_path):
    with pytest.raises(FileNotFoundError, match="prices"):
        collect_role_files(tmp_path, ["prices"])


def test_written_manifest_validates_against_schema(tmp_path):
    path = tmp_path / "manifest.json"
    doc = build_manifest({"parameters": {}}, {}, tmp_path, "abc", {}, now=datetime(2026, 1, 1, tzinfo=UTC))
    write_manifest(doc, path)
    assert validate_document(path, "manifest") == []
    assert json.loads(path.read_text()) == doc


def test_two_writes_of_same_manifest_are_byte_identical(tmp_path):
    doc = build_manifest({"parameters": {}}, {}, tmp_path, "abc", {}, now=datetime(2026, 1, 1, tzinfo=UTC))
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    write_manifest(doc, first)
    write_manifest(doc, second)
    assert first.read_bytes() == second.read_bytes()

def test_resolved_packages_lists_installed_distributions_sorted():
    from importlib import metadata

    from reprokit.manifest import resolved_packages

    packages = resolved_packages()
    assert packages["pyyaml"] == metadata.version("pyyaml")
    assert packages["pytest"] == metadata.version("pytest")
    assert list(packages) == sorted(packages)
