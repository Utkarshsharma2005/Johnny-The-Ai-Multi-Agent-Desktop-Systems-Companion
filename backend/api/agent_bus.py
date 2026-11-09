"""
api/agent_bus.py — REST + SSE endpoints for the multi-agent event bus.

Endpoints:
  GET  /api/v1/agent-bus/stream        — SSE stream of live agent events
  GET  /api/v1/agent-bus/history       — Recent events (last 50)
  GET  /api/v1/agent-bus/permissions   — Pending permission requests
  POST /api/v1/agent-bus/permissions/{id}/resolve — Approve/deny
  POST /api/v1/agent-bus/permissions/{id}/resolve — Approve/deny

SECURITY: The debug /publish endpoint was REMOVED during the 2026-11 security
hardening — it allowed any local caller to inject forged events (including
fake permission approvals). Publishing is agent-internal only. Auth (token)
and rate limiting apply to all agent-bus endpoints via main.py middleware.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional

from backend.core.agent_bus import agent_bus, AgentEvent, EventType
from backend.core.api_security import audit_log
from backend.core.approvals import approval_broker
from backend.agents.task_engine import task_engine
from backend.tools.registry import tool_registry

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent-bus", tags=["agent-bus"])


# ── SSE Stream ───────────────────────────────────────────────────────────────

@router.get("/stream")
async def sse_stream(request: Request):
    """
    Server-Sent Events stream of all agent bus events in real time.
    Reconnect-safe: each event carries an `id` field.
    """
    queue = agent_bus.subscribe()

    async def generator():
        # Send a heartbeat first so the client knows the connection is live
        yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event: AgentEvent = await asyncio.wait_for(queue.get(), timeout=15.0)
                    data = json.dumps(event.to_dict())
                    yield f"id: {event.id}\nevent: {event.type.value}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat ping to keep connection alive
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            agent_bus.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── History ──────────────────────────────────────────────────────────────────

@router.get("/history")
def get_history(limit: int = 50):
    """Returns the last N events from the ring buffer."""
    return {"events": agent_bus.history(limit=min(limit, 200))}


# ── Pending Permissions ───────────────────────────────────────────────────────

@router.get("/permissions")
def list_permissions():
    """List all pending permission requests waiting for user approval."""
    return {"permissions": approval_broker.list_pending() + agent_bus.list_pending_permissions()}


class PermissionResolution(BaseModel):
    approved: bool


@router.post("/permissions/{request_id}/resolve")
def resolve_permission(request_id: str, body: PermissionResolution, request: Request):
    """Approve or deny a pending permission request from an agent."""
    ok = approval_broker.resolve(request_id, body.approved)
    approval = approval_broker.get(request_id) if ok else None
    if not ok:
        ok = agent_bus.resolve_permission(request_id, body.approved)
    elif body.approved and approval and approval.get("task_id"):
        try:
            task_engine.execute_task(approval["task_id"], approval_id=request_id)
        except Exception:
            log.exception("Approved task resumption failed for task %s", approval.get("task_id"))
    elif body.approved and approval:
        try:
            if approval_broker.consume(request_id, approval["action"], approval["arguments"]):
                outcome = tool_registry.execute_tool(approval["action"], approval["arguments"], user_approved=True)
                approval_broker.set_result(request_id, outcome)
                agent_bus.publish(AgentEvent(type=EventType.AGENT_RESULT, agent="executor",
                    content=f"Approved action {approval['action']} finished: {'success' if outcome.get('success') else 'failed'}.",
                    metadata={"approval_id": request_id, "success": bool(outcome.get("success"))},
                    severity="info" if outcome.get("success") else "warn"))
        except Exception:
            log.exception("Approved tool execution failed for ticket %s", request_id)
    elif not body.approved and approval and approval.get("task_id"):
        task_engine.deny_approval(approval["task_id"])
    audit_log(
        "agent_bus_permission_resolve",
        request_id,
        "approved" if body.approved else "denied" if ok else "not_found",
        request=request,
        severity="warn",
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"Permission request '{request_id}' not found or already resolved.")
    return {"status": "resolved", "approved": body.approved}


# ── Debug Publish ─────────────────────────────────────────────────────────────
# REMOVED (security hardening): the /publish endpoint allowed forged events and
# fake permission decisions for any local caller. See docs/API_SECURITY.md.
