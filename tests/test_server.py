"""Tests for the FastAPI web backend (offline — brain is mocked)."""

import pytest
from fastapi.testclient import TestClient

import server
import tools
from memory import MemoryManager


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate memory and the file workspace to a temp dir.
    monkeypatch.setattr(tools, "WORKSPACE_DIR", str(tmp_path / "ws"))
    monkeypatch.setattr(server, "_memory", MemoryManager(db_path=str(tmp_path / "m.db")))
    return TestClient(server.app)


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "provider" in body and "model" in body
    assert "dangerous_tools_enabled" in body
    assert isinstance(body["wake_words"], list) and body["wake_words"]


def test_chat_uses_brain(client, monkeypatch):
    monkeypatch.setattr(server._brain, "think", lambda msg: f"echo:{msg}")
    body = client.post("/chat", json={"message": "hi"}).json()
    assert body["reply"] == "echo:hi"


def test_chat_empty_message(client):
    body = client.post("/chat", json={"message": "   "}).json()
    assert "Please" in body["reply"]


def test_files_upload_list_download(client):
    up = client.post("/files/upload", files={"file": ("greet.txt", b"hello", "text/plain")})
    assert up.status_code == 200

    listing = client.get("/files").json()
    assert any(f["name"] == "greet.txt" for f in listing["files"])

    dl = client.get("/files/greet.txt")
    assert dl.status_code == 200
    assert dl.content == b"hello"


def test_upload_traversal_rejected(client):
    up = client.post("/files/upload", files={"file": ("../evil.txt", b"x", "text/plain")})
    assert up.status_code == 400


def test_memory_facts_list_and_delete(client):
    server._memory.store_fact("city", "London")
    facts = client.get("/memory/facts").json()["facts"]
    assert any(f["key"] == "city" for f in facts)

    deleted = client.delete("/memory/facts/city").json()
    assert deleted["deleted"] is True
    assert client.get("/memory/facts").json()["facts"] == []


def test_stream_websocket_events(client, monkeypatch):
    def fake_stream(msg):
        yield {"type": "tool", "name": "get_time"}
        yield {"type": "tool_result", "name": "get_time", "result": "It's 9 PM."}
        yield {"type": "final", "text": "It's 9 PM."}

    monkeypatch.setattr(server._brain, "stream_turn", fake_stream)
    with client.websocket_connect("/stream") as ws:
        ws.send_json({"message": "what time is it"})
        e1 = ws.receive_json()
        e2 = ws.receive_json()
        e3 = ws.receive_json()
    assert e1["type"] == "tool"
    assert e2["type"] == "tool_result"
    assert e3 == {"type": "final", "text": "It's 9 PM."}
