#!/usr/bin/env python3
"""
setup_keys.py — Johnny first-run API key wizard.

Asks for API keys ONCE, stores them securely in
.johnny/credentials/api_keys.env (mode 0600, gitignored). The backend picks
them up automatically on every run afterwards — you never re-enter them.

Never stored in tracked files, never printed back in full, never in git.

Usage:
  python setup_keys.py            # interactive wizard
  python setup_keys.py --status   # show masked key status (no secrets)
  python setup_keys.py --remove NIM_API_KEY   # delete one stored key
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.core.secrets_loader import (  # noqa: E402
    SUPPORTED_KEYS, credentials_file, mask_status, nim_api_key_configured,
    store_keys,
)


def _status_line(entry: dict, key: str) -> str:
    if entry["masked"]:
        return f"✔ {key}: configured ({entry['masked']}) from {entry['source']}"
    return f"✖ {key}: not set"


def show_status() -> None:
    print("🔐 Johnny API key status")
    print(f"   Store: {credentials_file()}")
    for key, entry in mask_status().items():
        print("   " + _status_line(entry, key))
    print()
    if nim_api_key_configured():
        print("✔ NVIDIA NIM enabled — chat/models will use live inference.")
    else:
        print("ℹ️  No NIM key yet — Johnny runs in offline MOCK mode (no API usage).")
        print("   Get a free NVIDIA key at https://build.nvidia.com/")


def ask_key(prompt: str, default_raw: str) -> tuple[str, bool]:
    """Returns (value, changed). Empty input keeps existing. Input is hidden."""
    if default_raw:
        shown = default_raw[:4] + "••••" + default_raw[-4:]
        hint = f"[current: {shown} — press Enter to keep]"
    else:
        hint = "[not set]"
    try:
        raw = getpass.getpass(f"{prompt} {hint}> ").strip()
    except (KeyboardInterrupt, EOFError):
        # Cancel (Ctrl+C / Ctrl+D) — exit code 2 lets launchers stop cleanly
        # instead of silently continuing with a MOCK server.
        print("\n\nSetup cancelled — nothing changed.")
        sys.exit(2)
    return raw, bool(raw)


def run_wizard() -> None:
    print("=" * 62)
    print("  Johnny — first-run API key setup")
    print("=" * 62)
    print("Keys will be stored securely (0600) in:")
    print(f"  {credentials_file()}")
    print("This file is gitignored and never leaves your machine.")
    print("Press Ctrl+C anytime to abort without changes.\n")

    current = (credentials_file().read_text(encoding="utf-8")
               if credentials_file().exists() else "")
    import re
    existing = dict(re.findall(r"^([A-Z]=[^\n]+)$", current, re.M)) or {}
    # cheap parse for defaults display
    stored = {}
    for line in current.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            stored[k.strip()] = v.strip()

    updates = {}

    # 1. NVIDIA NIM key (the one Johnny actually uses)
    print("1️⃣  NVIDIA NIM API key — powers all chat/models (https://build.nvidia.com/)")
    val, changed = ask_key("   NIM_API_KEY", stored.get("NIM_API_KEY", ""))
    if changed:
        if not val.startswith("nvapi-"):
            confirm = input("   ⚠️  Key does not start with 'nvapi-'. Save anyway? [y/N] ").lower()
            if confirm != "y":
                print("   Skipped.")
            else:
                updates["NIM_API_KEY"] = val
        else:
            updates["NIM_API_KEY"] = val

    # 2. Optional: OpenRouter key (for future OpenRouter routing — currently unused)
    print("\n2️⃣  OpenRouter API key [optional] — reserved for OpenRouter routing; the")
    print("    backend currently routes DeepSeek via NVIDIA NIM, so this can be blank.")
    val, changed = ask_key("   OPENROUTER_API_KEY", stored.get("OPENROUTER_API_KEY", ""))
    if changed:
        updates["OPENROUTER_API_KEY"] = val

    # 3. Optional: local API token override
    print("\n3️⃣  Local API token [optional] — auto-generates if left blank.")
    val, changed = ask_key("   JOHNNY_API_TOKEN", stored.get("JOHNNY_API_TOKEN", ""))
    if changed:
        updates["JOHNNY_API_TOKEN"] = val

    if not updates:
        print("\nNothing to update.")
        return

    path = store_keys(updates)
    print(f"\n✅ Saved {len(updates)} key(s) to {path}")
    show_status()
    print("\nDone! Start the backend with:  ./run_backend.sh")


def remove_key(key: str) -> None:
    if key not in SUPPORTED_KEYS:
        print(f"❌ Unsupported key '{key}'. Supported: {SUPPORTED_KEYS}")
        sys.exit(1)
    import os
    cred = credentials_file()
    if not cred.exists():
        print("Nothing stored yet.")
        return
    lines = [l for l in cred.read_text(encoding="utf-8").splitlines()
             if not l.startswith(f"{key}=")]
    tmp = cred.with_suffix(".env.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(cred)
    print(f"✅ Removed '{key}' from {cred}")


def main() -> None:
    args = sys.argv[1:]
    if "--status" in args:
        show_status()
    elif "--remove" in args:
        idx = args.index("--remove")
        if idx + 1 >= len(args):
            print("Usage: setup_keys.py --remove KEY")
            sys.exit(1)
        remove_key(args[idx + 1])
    else:
        run_wizard()


if __name__ == "__main__":
    main()
