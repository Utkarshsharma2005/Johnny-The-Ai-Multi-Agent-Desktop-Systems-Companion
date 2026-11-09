import os

# ── Load stored secrets BEFORE Settings is created ────────────────────────────
# Reads .johnny/credentials/api_keys.env (0600, gitignored, produced by
# setup_keys.py) into os.environ — keys configured in the first-run wizard
# are then available on every run without re-entering them.
from backend.core.secrets_loader import load_secrets
load_secrets()

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    NIM_API_KEY: str = "nvapi-placeholder"
    NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    LLAMA_MODEL_ID: str = "nvidia/nemotron-3-ultra-550b-a55b"
    MINIMAX_MODEL_ID: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    DEEPSEEK_MODEL_ID: str = "nvidia/nemotron-3-ultra-550b-a55b"
    NEMOTRON_MODEL_ID: str = "nvidia/nemotron-3-ultra-550b-a55b"

    MODEL_PROVIDER: str = "nim"  # "nim" or "mock"

    # ── Local API auth token (see backend/core/api_security.py) ────────────────
    JOHNNY_API_TOKEN: str = ""  # generated on first run when unset

    # ── Browser egress control (SSRF hardening) ───────────────────────────────
    JOHNNY_EGRESS_ALLOWLIST: str = ""  # comma-separated hosts; enforced when set

    # ── Limits ─────────────────────────────────────────────────────────────────
    MAX_BODY_BYTES: int = 2 * 1024 * 1024   # request body cap (2 MB)
    NIM_CONNECT_TIMEOUT: float = 10.0
    NIM_REQUEST_TIMEOUT: float = 45.0

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    LOG_LEVEL: str = "info"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def safe_dump(self) -> dict:
        """Redacted view of settings for logging — never includes secrets."""
        from backend.core.secrets_loader import nim_api_key_configured
        return {
            "HOST": self.HOST, "PORT": self.PORT, "LOG_LEVEL": self.LOG_LEVEL,
            "MODEL_PROVIDER": self.MODEL_PROVIDER, "NIM_BASE_URL": self.NIM_BASE_URL,
            "api_key_configured": nim_api_key_configured(),
            "token_set": bool(self.JOHNNY_API_TOKEN),
        }

settings = Settings()
