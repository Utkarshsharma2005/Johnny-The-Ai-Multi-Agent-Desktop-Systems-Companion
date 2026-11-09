"""
api_security.py — Local API security layer for Johnny.

Contains:
  * Token management (JOHNNY_API_TOKEN env or generated, persisted 0600
    under .johnny/credentials/api_token)
  * Authentication middleware (X-Johnny-Token / Authorization: Bearer)
  * In-house sliding-window rate limiter (per-IP, per-endpoint-class),
    returns 429 + Retry-After
  * Request body size limit enforcement
  * Structured audit logging to backend/logs/audit.log
  * Security response headers

Auth can be disabled ONLY via the real environment variable
JOHNNY_DISABLE_API_AUTH=1 (for dev/test) — .env cannot disable it.
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from backend.core import redaction

# ─── Token management ───────────────────────────────────────────────────────────

_TOKEN_ENV_VAR = "JOHNNY_API_TOKEN"

def _credentials_file() -> Path:
    base = Path(os.getenv("JOHNNY_HOME", Path.cwd() / ".johnny"))
    return base / "credentials" / "api_token"


def load_or_create_token() -> str:
    """Token source priority: env var → persisted credential file → generate."""
    env_token = os.environ.get(_TOKEN_ENV_VAR, "").strip()
    if env_token:
        return env_token

    cred_file = _credentials_file()
    try:
        existing = cred_file.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    except Exception:
        # unreadable credential file → fall through to generation
        pass

    new_token = secrets.token_urlsafe(32)
    try:
        cred_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(cred_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_token)
        os.chmod(cred_file, 0o600)
    except Exception:
        pass  # token still returned in-memory even if persistence failed
    return new_token


API_TOKEN = load_or_create_token()


def token_hash(token: str = "") -> str:
    """Short hash of the token for audit logs (never the token itself)."""
    t = token or API_TOKEN
    return hashlib.sha256(t.encode()).hexdigest()[:12]


def _auth_disabled() -> bool:
    # Only the true environment can disable auth — .env cannot (supply-chain safety)
    return os.environ.get("JOHNNY_DISABLE_API_AUTH", "") == "1"


def _extract_token(request: Request) -> Optional[str]:
    header = request.headers.get("X-Johnny-Token") or ""
    if header.strip():
        return header.strip()
    authz = request.headers.get("Authorization", "")
    if authz.startswith("Bearer "):
        return authz.removeprefix("Bearer ").strip()
    return None


def _is_exempt(request: Request) -> bool:
    path = request.url.path
    if request.method == "OPTIONS":
        return True
    if path in ("/health", "/api/v1/health"):
        return True
    if path == "/api/v1/auth/token":
        return True
    return False


def verify_api_token(request: Request) -> Optional[Tuple[int, str]]:
    """Returns (status, detail) tuple when request is REJECTED, else None."""
    if _auth_disabled():
        return None
    supplied = _extract_token(request)
    if supplied and hmac.compare_digest(supplied, API_TOKEN):
        return None
    return (401, "Missing or invalid API token. Provide header X-Johnny-Token (see docs/API_SECURITY.md).")


# ─── Rate limiting (in-house sliding window) ────────────────────────────────────

# (url_prefix, requests_per_minute) — most specific prefix wins
_RATE_LIMITS = [
    ("/api/v1/agent-bus/permissions", 180),  # polling endpoint from desktop UI
    ("/api/v1/agent-bus", 60),
    ("/api/v1/orchestration", 30),
    ("/api/v1/chat", 60),
    ("/api/v1/browser", 10),
    ("/api/v1/tools", 60),
    ("/api/v1/tasks", 60),
    ("/api/v1/", 180),  # generic catch-all per IP
]

_WINDOW_SECONDS = 60.0


class SlidingWindowLimiter:
    def __init__(self):
        self.enabled = not _auth_disabled()  # dev/test override shares auth flag
        self._hits: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=256))
        self._lock = threading.Lock()

    def check(self, ip: str, path: str) -> Tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        if not self.enabled:
            return True, 0
        limit = _RATE_LIMITS[-1][1]
        for prefix, per_minute in _RATE_LIMITS:
            if path.startswith(prefix):
                limit = per_minute
                break

        key = f"{path}:{ip}"
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            while dq and now - dq[0] > _WINDOW_SECONDS:
                dq.popleft()
            if len(dq) >= limit:
                oldest = dq[0]
                retry_after = max(1, int(_WINDOW_SECONDS - (now - oldest)) + 1)
                return False, min(retry_after, _WINDOW_SECONDS)
            dq.append(now)
        return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = SlidingWindowLimiter()


# ─── Audit log ──────────────────────────────────────────────────────────────────

_audit_lock = threading.Lock()
_AUDIT_LOG_PATH = Path("backend/logs/audit.log")


def audit_log(action: str, target: str, result: str, request: Optional[Request] = None,
              severity: str = "info") -> None:
    """Append a structured JSON audit record for a sensitive action."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "target": (target or "")[:300],
        "result": result,
        "severity": severity,
        "token_hash": token_hash(),
    }
    if request is not None:
        entry["client"] = request.client.host if request.client else "unknown"
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(redaction.redact_json(entry))
        with _audit_lock:
            with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass  # audit must never break the API path


# ─── Middleware (registered in main.py) ─────────────────────────────────────────

def security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    return response


async def api_auth_middleware(request: Request, call_next):
    """Auth + rate-limit + body-size gate for all requests."""
    # 1. Authentication
    rejection = verify_api_token(request)
    if rejection is not None and not _is_exempt(request):
        resp = JSONResponse(status_code=rejection[0], content={"detail": rejection[1]}, headers={"Retry-After": "0"})
        return security_headers(resp)

    # 2. Request body size limit
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > settings_MAX_BODY():
        return security_headers(JSONResponse(
            status_code=413,
            content={"detail": f"Request body too large (limit {settings_MAX_BODY()} bytes)."},
        ))

    # 3. Rate limiting (per-IP, per-endpoint-class)
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.check(ip, request.url.path)
    if not allowed:
        return security_headers(JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Slow down and retry later."},
            headers={"Retry-After": str(retry_after)},
        ))

    response = await call_next(request)
    return security_headers(response)


def settings_MAX_BODY() -> int:
    from backend.core.config import settings
    return settings.MAX_BODY_BYTES
