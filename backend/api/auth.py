"""
api/auth.py — Token bootstrap endpoint for the local desktop frontend.

GET /api/v1/auth/token
Returns the local API token ONLY when the request Origin is in the same
CORS allowlist as the Tauri/Vite frontend. Cross-origin browsers can never
read the response (CORS blocks the read), and remote clients can only reach
the loopback listener. Can be disabled entirely via
JOHNNY_DISABLE_TOKEN_BOOTSTRAP=1 in the real environment.
"""

import os
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Mirrors the CORS allowlist in backend/main.py
_BOOTSTRAP_ALLOWED_ORIGINS = {
    "http://localhost:1420", "http://127.0.0.1:1420",
    "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost",
    "http://localhost:5173", "http://127.0.0.1:5173",
}


@router.get("/token")
def get_api_token(request: Request):
    if os.environ.get("JOHNNY_DISABLE_TOKEN_BOOTSTRAP", "") == "1":
        raise HTTPException(status_code=404, detail="Token bootstrap disabled.")

    origin = request.headers.get("origin", "")
    if origin not in _BOOTSTRAP_ALLOWED_ORIGINS:
        from backend.core.api_security import audit_log
        audit_log("auth_token_bootstrap_denied", origin or "no-origin", "rejected", severity="warn")
        raise HTTPException(status_code=403, detail="Origin is not permitted to bootstrap the API token.")

    from backend.core.api_security import API_TOKEN
    return {"token": API_TOKEN, "header": "X-Johnny-Token"}
