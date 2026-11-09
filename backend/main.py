import sys
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

from backend.core.config import settings
from backend.core.first_run import run_setup_if_needed, needs_setup
from backend.core import api_security
from backend.api.health import router as health_router
from backend.api.chat import router as chat_router
from backend.api.image import router as image_router
from backend.api.screen import router as screen_router
from backend.api.requirements import router as requirements_router
from backend.api.tools import router as tools_router
from backend.api.verification import router as verification_router
from backend.api.tasks import router as tasks_router
from backend.api.orchestration import router as orchestration_router
from backend.api.persistence import router as persistence_router
from backend.api.memory import router as memory_router
from backend.api.browser import router as browser_router
from backend.api.agent_bus import router as agent_bus_router
from backend.api.auth import router as auth_router
from backend.api.system import router as system_router

# ─── First-run key setup (safe, non-blocking) ──────────────────────────────────
# Interactive prompts NEVER run inside the event loop — they'd swallow Ctrl+C
# (uvicorn's signal handler is only processed by a free loop). The lifespan
# therefore only prints a banner; the interactive wizard lives in:
#   • run_backend.sh (before uvicorn starts), and
#   • `python -m backend.main` below (also before uvicorn starts).
@asynccontextmanager
async def lifespan(app: FastAPI):
    run_setup_if_needed()
    yield

app = FastAPI(
    title="Johnny Desktop AI Pet API",
    description="Backend API service for Johnny Linux Desktop AI Pet",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS: Restrict to local Tauri + local Vite dev origins only ───────────────
# SECURITY: Never use allow_origins=["*"] — that exposes the API to any web page
# the user visits (CSRF via browser fetch). Tauri and local Vite are the only
# legitimate callers of this API.
_ALLOWED_ORIGINS = [
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    # Allow any localhost port for Vite dev server flexibility
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Johnny-Token"],
)

# ─── Security middleware: token auth + rate limiting + body size + headers ─────
app.middleware("http")(api_security.api_auth_middleware)


# ─── Global unhandled exception handler ───────────────────────────────────────
# Prevents raw Python tracebacks from leaking into API responses (security + UX)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Check server logs."},
    )

# Register API Routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(image_router)
app.include_router(screen_router)
app.include_router(requirements_router)
app.include_router(tools_router)
app.include_router(verification_router)
app.include_router(tasks_router)
app.include_router(orchestration_router)
app.include_router(persistence_router)
app.include_router(memory_router)
app.include_router(browser_router)
app.include_router(agent_bus_router)
app.include_router(auth_router)
app.include_router(system_router)

if __name__ == "__main__":
    # SECURITY/UX: the interactive key wizard runs in this plain CLI context
    # BEFORE the event loop starts — Ctrl+C works normally here, which is why
    # it must never be moved into the lifespan hook.
    from backend.core.first_run import run_interactive_setup
    run_interactive_setup()

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL,
        timeout_keep_alive=10,
        limit_max_requests=0,
    )
