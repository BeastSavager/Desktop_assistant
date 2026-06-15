"""Tests for the pluggable LLM provider resolution in config."""

import importlib
import os
from types import SimpleNamespace

import config


def _reload_with(env: dict):
    saved = {k: os.environ.get(k) for k in env}
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        importlib.reload(config)
        # Snapshot now, before the finally block reloads config back to defaults.
        return SimpleNamespace(
            LLM_PROVIDER=config.LLM_PROVIDER,
            IS_OLLAMA=config.IS_OLLAMA,
            LLM_BASE_URL=config.LLM_BASE_URL,
            LLM_API_KEY=config.LLM_API_KEY,
            LLM_MODEL=config.LLM_MODEL,
        )
    finally:
        # Restore env and reload back to defaults so other tests are unaffected.
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(config)


def test_defaults_to_ollama():
    cfg = _reload_with({"LLM_PROVIDER": None})
    assert cfg.LLM_PROVIDER == "ollama"
    assert cfg.IS_OLLAMA is True
    assert cfg.LLM_API_KEY == "ollama"


def test_openai_compatible_switch():
    cfg = _reload_with(
        {
            "LLM_PROVIDER": "openai_compatible",
            "LLM_BASE_URL": "https://example.test/v1",
            "LLM_API_KEY": "sk-test",
            "LLM_MODEL": "gpt-4o-mini",
        }
    )
    assert cfg.IS_OLLAMA is False
    assert cfg.LLM_BASE_URL == "https://example.test/v1"
    assert cfg.LLM_MODEL == "gpt-4o-mini"
    assert cfg.LLM_API_KEY == "sk-test"


def test_unknown_provider_falls_back_to_ollama():
    cfg = _reload_with({"LLM_PROVIDER": "banana"})
    assert cfg.IS_OLLAMA is True
    assert cfg.LLM_PROVIDER == "ollama"
