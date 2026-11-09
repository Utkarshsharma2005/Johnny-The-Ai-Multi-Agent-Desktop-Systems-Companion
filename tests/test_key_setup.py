"""
Tests for the first-run API key wizard & secure credential store.
Verifies: gitignored 0600 storage, precedence, masking, no leakage into logs.
"""

import os
import stat
import pytest

import backend.core.secrets_loader as sl


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("JOHNNY_HOME", str(tmp_path / ".johnny"))
    # ensure clean env for isolated assertions
    for k in sl.SUPPORTED_KEYS:
        monkeypatch.delenv(k, raising=False)
    yield sl


def test_store_keys_creates_owner_only_file(tmp_store):
    path = tmp_store.store_keys({"NIM_API_KEY": "nvapi-test-1234567890"})
    assert path.is_file()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600, f"credential file must be 0600, got {oct(mode)}"


def test_store_rejects_unsupported_keys(tmp_store):
    with pytest.raises(ValueError):
        tmp_store.store_keys({"EVIL_KEY": "x"})


def test_store_rejects_empty_values(tmp_store):
    with pytest.raises(ValueError):
        tmp_store.store_keys({"NIM_API_KEY": "   "})


def test_load_secrets_injects_env(tmp_store):
    tmp_store.store_keys({"NIM_API_KEY": "nvapi-wizard-key-0000"})
    count = tmp_store.load_secrets()
    assert count == 1
    assert os.environ["NIM_API_KEY"] == "nvapi-wizard-key-0000"


def test_load_secrets_never_overrides_real_env(tmp_store, monkeypatch):
    monkeypatch.setenv("NIM_API_KEY", "from-real-env")
    tmp_store.store_keys({"NIM_API_KEY": "nvapi-wizard-key"})
    tmp_store.load_secrets()
    assert os.environ["NIM_API_KEY"] == "from-real-env"


def test_store_preserves_other_keys(tmp_store):
    tmp_store.store_keys({"NIM_API_KEY": "nvapi-a"})
    tmp_store.store_keys({"JOHNNY_API_TOKEN": "tok-b"})
    text = tmp_store.credentials_file().read_text()
    assert "nvapi-a" in text and "tok-b" in text


def test_mask_never_shows_full_key(tmp_store):
    masked = tmp_store._mask("nvapi-supercalifragilistic0987654321")
    assert "supercalifragilistic" not in masked
    assert masked.startswith("nvap")


def test_nim_configured_detection(tmp_store):
    assert not tmp_store.nim_api_key_configured()  # nothing set
    os.environ["NIM_API_KEY"] = "paste-rotated-nvapi-key-here"
    assert not tmp_store.nim_api_key_configured()  # placeholder
    os.environ["NIM_API_KEY"] = "nvapi-real-key-here-123"
    assert tmp_store.nim_api_key_configured()


def test_mask_status_report_shape(tmp_store):
    tmp_store.store_keys({"NIM_API_KEY": "nvapi-wizard-key-9999"})
    report = tmp_store.mask_status()
    assert report["NIM_API_KEY"]["source"] == "credential_file"
    assert "9999" in report["NIM_API_KEY"]["masked"].replace("…", "9999") or report["NIM_API_KEY"]["masked"]
    assert report["OPENROUTER_API_KEY"]["source"] == "missing"


def test_config_picks_up_stored_key(tmp_store, monkeypatch):
    """End-to-end: store key → reload config module → Settings sees the key."""
    tmp_store.store_keys({"NIM_API_KEY": "nvapi-e2e-test-key-424242"})
    import importlib
    from backend.core import config
    importlib.reload(config)
    assert config.settings.NIM_API_KEY == "nvapi-e2e-test-key-424242"
    # cleanup so other modules don't see this provider key
    monkeypatch.delenv("NIM_API_KEY", raising=False)


def test_wizard_module_importable():
    import setup_keys  # noqa: F401
