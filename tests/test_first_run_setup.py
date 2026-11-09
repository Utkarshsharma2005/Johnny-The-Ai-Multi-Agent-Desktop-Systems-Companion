"""
Tests for the first-run API key setup flow.

SIGNAL SAFETY NOTE (why there are two entry points):
  Interactive prompts must NEVER run inside the FastAPI lifespan/asyncio loop —
  uvicorn replaces the SIGINT handler and, while the loop is blocked inside a
  sync prompt, the shutdown flag is never processed → Ctrl+C hangs the server.
  run_setup_if_needed() (lifespan) is therefore banner-only; the interactive
  wizard lives in run_interactive_setup() (plain CLI, before the loop).
"""

import os
import sys
from pathlib import Path

import pytest

import backend.core.first_run as first_run
import backend.core.secrets_loader as sl


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("JOHNNY_HOME", str(tmp_path / ".johnny"))
    # isolate the decline marker into the tmp dir too
    monkeypatch.setattr(first_run, "__file__",
                        str(tmp_path / "backend" / "core" / "first_run.py"))
    for k in sl.SUPPORTED_KEYS:
        monkeypatch.delenv(k, raising=False)
    yield sl


def test_needs_setup_true_when_nothing_configured(tmp_store):
    assert first_run.needs_setup() is True


def test_needs_setup_false_when_credential_file_exists(tmp_store):
    sl.store_keys({"NIM_API_KEY": "nvapi-wizard-key-1111"})
    assert first_run.needs_setup() is False


def test_needs_setup_false_when_real_env_key(tmp_store, monkeypatch):
    monkeypatch.setenv("NIM_API_KEY", "nvapi-real-env-key-222")
    assert first_run.needs_setup() is False


def test_setup_not_needed_is_silent(tmp_store, capsys):
    sl.store_keys({"NIM_API_KEY": "nvapi-x-12345"})
    first_run.run_setup_if_needed()
    assert capsys.readouterr().out == ""  # fully silent when keys exist


# ─── lifespan path: NEVER prompts, NEVER blocks ────────────────────────────────

def test_lifespan_check_prints_banner_and_does_not_prompt(tmp_store, capsys, monkeypatch):
    fake_stdin = type("FakeStdin", (), {"isatty": lambda self: False})()
    monkeypatch.setattr(sys, "stdin", fake_stdin, raising=False)

    first_run.run_setup_if_needed()
    out = capsys.readouterr().out
    assert "OFFLINE MOCK MODE" in out
    assert "python setup_keys.py" in out
    #Critical: must NOT have blocked or created keys
    assert not sl.credentials_file().exists()


def test_lifespan_check_respects_decline_marker(tmp_store, capsys):
    first_run._touch_marker()
    first_run.run_setup_if_needed()
    assert capsys.readouterr().out == ""  # silent after declined before


# ─── interactive path (plain CLI, safe for Ctrl+C) ─────────────────────────────

def test_interactive_setup_runs_wizard(tmp_store, monkeypatch):
    calls = {"n": 0}
    class FakeWizard:
        @staticmethod
        def run_wizard():
            calls["n"] += 1
            sl.store_keys({"NIM_API_KEY": "nvapi-from-wizard-5555"})

    monkeypatch.setattr(first_run, "_wizard", lambda: FakeWizard, raising=False)

    # Restore process-global settings after the live-switch side effects
    from backend.core.config import settings as global_settings
    monkeypatch.setattr(global_settings, "MODEL_PROVIDER", global_settings.MODEL_PROVIDER)
    monkeypatch.setattr(global_settings, "NIM_API_KEY", global_settings.NIM_API_KEY)

    first_run.run_interactive_setup()
    assert calls["n"] == 1
    # Keys applied to the live process (no restart needed)
    assert os.environ.get("NIM_API_KEY") == "nvapi-from-wizard-5555"
    assert global_settings.MODEL_PROVIDER == "nim"
    monkeypatch.delenv("NIM_API_KEY", raising=False)


def test_interactive_setup_ctrl_c_exits_cleanly(tmp_store, monkeypatch, capsys):
    class FakeWizard:
        @staticmethod
        def run_wizard():
            raise KeyboardInterrupt

    monkeypatch.setattr(first_run, "_wizard", lambda: FakeWizard, raising=False)
    # MUST return normally (no hang) and write the decline marker
    first_run.run_interactive_setup()
    out = capsys.readouterr().out
    assert "skipped" in out.lower()
    marker = tmp_store.credentials_file().parent / ".setup_declined"
    assert marker.exists()


def test_interactive_setup_blank_wizard_defaults_marker(tmp_store, monkeypatch):
    class FakeWizard:
        @staticmethod
        def run_wizard():
            pass  # user entered nothing → nothing stored

    monkeypatch.setattr(first_run, "_wizard", lambda: FakeWizard, raising=False)
    first_run.run_interactive_setup()
    marker = tmp_store.credentials_file().parent / ".setup_declined"
    assert marker.exists()


def test_health_reports_keys_flag(tmp_store, monkeypatch):
    from backend.main import app

    import asyncio
    loop = asyncio.new_event_loop()
    try:
        data = loop.run_until_complete(fetch_health(app))
    finally:
        loop.close()
    assert isinstance(data["keys_configured"], bool)
    assert isinstance(data["mock_only"], bool)


def fetch_health(app):
    from httpx import AsyncClient, ASGITransport

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/health")
            return res.json()

    return _run()


def run_health(app):
    from httpx import AsyncClient, ASGITransport

    async def _do():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/health")
            return res.json()

    return _do()
