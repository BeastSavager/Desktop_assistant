"""Tests for the brain's agent loop, focusing on fallback logic and tool rounds.

The Ollama/OpenAI client is replaced with fakes so these tests run offline.
"""

from types import SimpleNamespace

import pytest

from brain import FALLBACK_REPLY, JarvisBrain
from memory import MemoryManager


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call(call_id, name, arguments="{}"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


@pytest.fixture
def brain(tmp_path):
    mem = MemoryManager(db_path=str(tmp_path / "mem.db"))
    return JarvisBrain(mem)


def test_plain_text_reply(brain, monkeypatch):
    monkeypatch.setattr(
        brain.client.chat.completions,
        "create",
        lambda **kw: _response(_msg(content="Hello, I am Jarvis.")),
    )
    assert brain.think("hi") == "Hello, I am Jarvis."


def test_empty_reply_uses_fallback(brain, monkeypatch):
    monkeypatch.setattr(
        brain.client.chat.completions,
        "create",
        lambda **kw: _response(_msg(content="")),
    )
    assert brain.think("hi") == FALLBACK_REPLY


def test_whitespace_reply_uses_fallback(brain, monkeypatch):
    monkeypatch.setattr(
        brain.client.chat.completions,
        "create",
        lambda **kw: _response(_msg(content="   \n  ")),
    )
    assert brain.think("hi") == FALLBACK_REPLY


def test_none_reply_uses_fallback(brain, monkeypatch):
    monkeypatch.setattr(
        brain.client.chat.completions,
        "create",
        lambda **kw: _response(_msg(content=None)),
    )
    assert brain.think("hi") == FALLBACK_REPLY


def test_api_error_returns_friendly_message(brain, monkeypatch):
    def boom(**kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(brain.client.chat.completions, "create", boom)
    reply = brain.think("hi")
    assert "trouble connecting" in reply


def test_tool_round_then_final_answer(brain, monkeypatch):
    """First call requests a tool; second call returns the final text."""
    calls = {"n": 0}

    def fake_create(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return _response(_msg(tool_calls=[_tool_call("c1", "get_time")]))
        # Second round: the tool result is restated back as a user message so
        # the model can answer with the actual data.
        assert any(
            m["role"] == "user" and "Results from the tools" in m["content"] for m in kw["messages"]
        )
        return _response(_msg(content="The time is now."))

    monkeypatch.setattr(brain.client.chat.completions, "create", fake_create)
    reply = brain.think("what time is it")
    assert reply == "The time is now."
    assert calls["n"] == 2


def test_history_is_persisted(brain, monkeypatch):
    monkeypatch.setattr(
        brain.client.chat.completions,
        "create",
        lambda **kw: _response(_msg(content="ok")),
    )
    brain.think("remember this")
    recent = brain.memory.get_recent_messages()
    assert {"role": "user", "content": "remember this"} in recent
    assert {"role": "assistant", "content": "ok"} in recent
