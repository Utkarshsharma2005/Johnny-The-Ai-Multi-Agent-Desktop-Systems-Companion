"""
first_run.py — Guaranteed first-run API key setup, regardless of how the
backend is started (run_backend.sh, IDE run button, `python -m backend.main`,
`uvicorn backend.main:app` …).

Two distinct entry points (signal-safety matters):

  * run_setup_if_needed()     — NON-BLOCKING, safe inside the asyncio event
    loop (FastAPI lifespan). Only prints a banner; NEVER prompts. Reason:
    uvicorn replaces the SIGINT handler with an internal shutdown flag, and
    while the loop is blocked in a sync prompt that flag is never processed →
    Ctrl+C becomes dead. Interactive prompts must NEVER run at this layer.

  * run_interactive_setup()   — runs the wizard in a PLAIN CLI context,
    before the event loop exists (run_backend.sh / `python -m backend.main`).
    Ctrl+C works normally here (default KeyboardInterrupt handling).
"""

import os
import sys
from pathlib import Path


def _marker_path() -> Path:
    return (Path(__file__).resolve().parent.parent.parent /
            ".johnny" / "credentials" / ".setup_declined")


def _touch_marker() -> None:
    m = _marker_path()
    m.parent.mkdir(parents=True, exist_ok=True)
    m.touch(exist_ok=True)


def _has_decline_marker() -> bool:
    return _marker_path().exists()


def _wizard():
    """Import the root-level setup_keys.py (repo root is on sys.path in main.py)."""
    import importlib.util
    root = Path(__file__).resolve().parent.parent.parent
    wizard_path = root / "setup_keys.py"
    if not wizard_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("johnny_setup_keys", wizard_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _apply_keys_live() -> None:
    """
    After the wizard stores keys in this (already-running) process, push them
    into the live Settings/ModelRouter so the CURRENT server starts using real
    inference — no restart needed.
    """
    from backend.core.secrets_loader import load_secrets, nim_api_key_configured

    try:
        load_secrets()
        from backend.core.config import settings
        if nim_api_key_configured():
            settings.NIM_API_KEY = os.environ.get("NIM_API_KEY", settings.NIM_API_KEY)
            # Note: settings is a pydantic BaseSettings object; mutation is
            # permitted and scoped to this process (restart re-reads .env).
            if settings.MODEL_PROVIDER == "mock":
                settings.MODEL_PROVIDER = "nim"
                print("🔄  Provider switched: mock → nim (live, no restart needed)")
        # Live-refresh the model router singleton so the new provider is used
        try:
            from backend.models import router as _router_mod
            _router_mod.router_instance.refresh()
        except Exception:
            pass
    except Exception as e:  # live-apply is best-effort; keys are safely stored
        print(f"⚠️  Keys saved, but live configuration refresh failed: {e}",
              file=sys.stderr)


def needs_setup() -> bool:
    """True when the user has never configured keys (and has no real env key)."""
    from backend.core.secrets_loader import (
        credentials_file, nim_api_key_configured,
    )

    # Real environment already provides a NIM key (advanced setup)
    if nim_api_key_configured():
        return False

    cred = credentials_file()
    if cred.exists():
        return False  # wizard ran before (even if fields were left blank)

    return True


def run_setup_if_needed() -> None:
    """
    NON-BLOCKING startup check (FastAPI lifespan). Never prompts — see the
    module docstring for why prompts must not run inside the event loop.
    """
    if not needs_setup():
        return
    if _has_decline_marker() and not os.environ.get("FORCE_SETUP_BANNER"):
        return  # user previously skipped; flag visible via /health instead

    if sys.stdin is not None and sys.stdin.isatty():
        print()
        print("🔑  Johnny is NOT configured with API keys yet — running in OFFLINE MOCK MODE.")
        print("    Chat replies will be simulated until you add keys.")
        print()
        print("    → To set up now: press Ctrl+C (stops the server cleanly), then run:")
        print("          python setup_keys.py")
        print("    → Or keep using MOCK mode and add keys later anytime.")
        print()
    else:
        _print_offline_banner()


def run_interactive_setup() -> None:
    """
    Interactive wizard — ONLY call from a plain CLI context BEFORE the asyncio
    event loop starts (run_backend.sh, `python -m backend.main`). Ctrl+C works
    normally here because there are no custom signal handlers / event loops.
    """
    if not needs_setup():
        return
    wizard = _wizard()
    if wizard is None:
        return
    try:
        wizard.run_wizard()
    except SystemExit:
        # Wizard itself cancelled (Ctrl+C/Ctrl+D → exit code 2): keep the
        # process exit code so launchers stop instead of silently starting.
        _touch_marker()
        raise
    except (KeyboardInterrupt, EOFError):
        print("\n⚠️  Setup skipped — Johnny will run in offline MOCK mode.")
        _touch_marker()
        return
    _apply_keys_live()
    if needs_setup():
        _touch_marker()  # user left everything blank


def _print_offline_banner() -> None:
    print()
    print("┌──────────────────────────────────────────────────────────────────┐")
    print("│  ⚠️  NO API KEYS CONFIGURED — running in OFFLINE MOCK MODE         │")
    print("│  Chat answers will be simulated; no model inference.              │")
    print("│                                                                    │")
    print("│  To enable real models: run the setup wizard                       │")
    print("│      python setup_keys.py                                          │")
    print("│  Keys are stored securely in .johnny/credentials/api_keys.env      │")
    print("│  (0600, gitignored) and loaded automatically on every start.       │")
    print("└──────────────────────────────────────────────────────────────────┘")
    print()
    _touch_marker()
