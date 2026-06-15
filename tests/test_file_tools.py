"""Tests for the sandboxed workspace file tools, including path-traversal."""

import pytest

import tools


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "WORKSPACE_DIR", str(tmp_path))
    return tmp_path


def test_write_read_roundtrip(workspace):
    assert "Wrote" in tools.write_file("a.txt", "hello world")
    assert tools.read_file("a.txt") == "hello world"


def test_append(workspace):
    tools.write_file("a.txt", "one")
    tools.append_file("a.txt", "-two")
    assert tools.read_file("a.txt") == "one-two"


def test_list_and_search(workspace):
    tools.write_file("notes.txt", "the dentist is on monday")
    tools.write_file("other.txt", "groceries")
    assert "notes.txt" in tools.list_files()
    hits = tools.search_in_files("dentist")
    assert "notes.txt" in hits
    assert "other.txt" not in hits


def test_read_missing_file(workspace):
    assert "not found" in tools.read_file("nope.txt").lower()


def test_path_traversal_rejected_on_read(workspace):
    result = tools.read_file("../config.py")
    assert "Refused" in result


def test_path_traversal_rejected_on_write(workspace):
    result = tools.write_file("../escape.txt", "x")
    assert "Refused" in result
    # And nothing was written outside the sandbox.
    assert not (workspace.parent / "escape.txt").exists()


def test_safe_path_absolute_escape_rejected(workspace):
    with pytest.raises(ValueError):
        tools._safe_path("C:/Windows/system32/evil.txt" if tools._IS_WINDOWS else "/etc/passwd")


def test_summarize_file_wraps_content(workspace):
    tools.write_file("doc.txt", "important content")
    out = tools.summarize_file("doc.txt")
    assert "important content" in out
    assert "summarize" in out.lower()
