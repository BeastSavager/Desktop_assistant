"""Tests for the tool dispatcher: selection, execution, safety gating, errors."""

import tools
from memory import MemoryManager


def test_unknown_tool_returns_message():
    result = tools.execute_tool("does_not_exist", {})
    assert "Unknown tool" in result


def test_get_time_executes():
    result = tools.execute_tool("get_time", {})
    assert result.startswith("It's")


def test_bad_arguments_are_reported():
    # get_time takes no args; passing one should surface a friendly error.
    result = tools.execute_tool("get_time", {"unexpected": 1})
    assert "bad arguments" in result


def test_normalize_url_adds_scheme():
    assert tools._normalize_url("example.com") == "https://example.com"
    assert tools._normalize_url("http://x.com") == "http://x.com"


def test_open_chrome_falls_back_to_default_browser(monkeypatch):
    opened = {}
    monkeypatch.setattr(tools, "_find_chrome", lambda: None)
    monkeypatch.setattr(tools.webbrowser, "open", lambda url: opened.setdefault("url", url))

    msg = tools.open_chrome("example.com")
    assert opened["url"] == "https://example.com"
    assert "default browser" in msg


def test_dangerous_tools_disabled_by_default(monkeypatch):
    monkeypatch.setattr(tools, "ALLOW_DANGEROUS_TOOLS", False)
    assert "disabled for safety" in tools.run_system_command("echo hi")
    assert "disabled for safety" in tools.type_text("hi")
    assert "disabled for safety" in tools.press_key("enter")


def test_dangerous_tool_runs_when_enabled(monkeypatch):
    monkeypatch.setattr(tools, "ALLOW_DANGEROUS_TOOLS", True)
    # Echo is portable enough for both Windows and POSIX shells.
    out = tools.run_system_command("echo hello")
    assert "hello" in out.lower()


def test_memory_tool_dispatch(tmp_path):
    mem = MemoryManager(db_path=str(tmp_path / "mem.db"))
    stored = tools.execute_tool("remember_fact", {"key": "pet", "value": "cat"}, memory=mem)
    assert "remember" in stored.lower()

    recalled = tools.execute_tool("recall_fact", {"key": "pet"}, memory=mem)
    assert "cat" in recalled


def test_memory_tool_without_memory_is_handled():
    result = tools.execute_tool("recall_fact", {"key": "x"}, memory=None)
    assert "needs memory" in result


def test_dangerous_schemas_hidden_when_disabled(monkeypatch):
    # The advertised schema list excludes dangerous tools when the flag is off.
    names = {s["function"]["name"] for s in tools._SAFE_SCHEMAS}
    assert "run_system_command" not in names
    assert "get_time" in names
