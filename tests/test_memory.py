"""Tests for the SQLite memory layer: storage, retrieval, and persistence."""

from memory import MemoryManager


def test_add_and_get_recent_messages(tmp_path):
    db = tmp_path / "mem.db"
    mem = MemoryManager(db_path=str(db))

    mem.add_message("user", "hello")
    mem.add_message("assistant", "hi there")

    recent = mem.get_recent_messages(n=10)
    assert recent == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_get_recent_respects_limit_and_order(tmp_path):
    mem = MemoryManager(db_path=str(tmp_path / "mem.db"))
    for i in range(5):
        mem.add_message("user", f"msg{i}")

    recent = mem.get_recent_messages(n=2)
    # Most recent two, in chronological order.
    assert [m["content"] for m in recent] == ["msg3", "msg4"]


def test_store_and_get_fact(tmp_path):
    mem = MemoryManager(db_path=str(tmp_path / "mem.db"))
    mem.store_fact("favourite colour", "teal")
    assert mem.get_fact("favourite colour") == "teal"
    assert mem.get_fact("missing") is None


def test_store_fact_upsert(tmp_path):
    mem = MemoryManager(db_path=str(tmp_path / "mem.db"))
    mem.store_fact("city", "London")
    mem.store_fact("city", "Paris")  # same key overwrites
    assert mem.get_fact("city") == "Paris"


def test_search_memory(tmp_path):
    mem = MemoryManager(db_path=str(tmp_path / "mem.db"))
    mem.add_message("user", "remind me about the dentist appointment")
    mem.add_message("user", "what's the weather")

    hits = mem.search_memory("dentist")
    assert len(hits) == 1
    assert "dentist" in hits[0]["content"]


def test_persistence_across_instances(tmp_path):
    db = str(tmp_path / "mem.db")
    mem = MemoryManager(db_path=db)
    mem.store_fact("name", "Ada")
    mem.close()

    reopened = MemoryManager(db_path=db)
    assert reopened.get_fact("name") == "Ada"


def test_clear_short_term_keeps_facts(tmp_path):
    mem = MemoryManager(db_path=str(tmp_path / "mem.db"))
    mem.add_message("user", "temporary")
    mem.store_fact("keep", "this")

    mem.clear_short_term()
    assert mem.get_recent_messages() == []
    assert mem.get_fact("keep") == "this"
