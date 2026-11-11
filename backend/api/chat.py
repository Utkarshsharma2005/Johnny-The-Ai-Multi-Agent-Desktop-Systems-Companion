"""
Chat API — streaming and non-streaming conversation endpoints.

Architecture decisions (senior system design perspective):
─────────────────────────────────────────────────────────
1. CONVERSATION HISTORY
   The frontend sends the full conversation history with each request.
   This is stateless by design — the server holds no session state.
   Session state in a desktop app adds complexity with zero benefit;
   the frontend is the single source of truth for history.

2. INTENT-BASED ROUTING
   Before hitting the model, we classify intent and pick the cheapest
   appropriate model via the router. Routing adds ~0ms overhead (pure Python).

3. STREAMING-FIRST
   /stream endpoint is primary. /generate is a non-streaming fallback.
   Both handle errors properly — no silent mock fallbacks.

4. TELEMETRY
   Every response carries routing_ms, model_ms, total_ms, token counts.
   This flows back to the frontend telemetry panel.
"""

import json
import logging
import time
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.models.router import router_instance
from backend.telemetry.latency import LatencyTracker, async_measure_stage
from backend.core.agent_bus import agent_bus, EventType, AgentEvent
from backend.memory.memory_manager import memory_manager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


def _process_memory_integration(prompt: str) -> str:
    """
    1. Checks if prompt contains explicit memory storage triggers (e.g. 'remember that...').
    2. Records short-term conversational context into memory manager.
    3. Returns prompt enriched with recalled project facts and user preferences.
    """
    clean_p = prompt.strip()
    lower_p = clean_p.lower()

    try:
        # Detect explicit memory storage triggers
        for trig in ["remember that", "remember:", "take note that", "please remember", "note that", "prefer that"]:
            if trig in lower_p:
                fact = clean_p[lower_p.find(trig) + len(trig):].strip(" :,-.")
                if fact:
                    tier = "project" if any(w in lower_p for w in ["project", "repo", "code", "app", "stack", "server", "backend"]) else "long_term"
                    memory_manager.record(
                        tier=tier,
                        key=f"fact_{int(time.time())}",
                        value=fact,
                        tags=["user_preference", "remembered_fact"]
                    )
                    break

        # Record prompt snippet into short-term buffer
        memory_manager.record("short_term", key="user_turn", value=clean_p[:250])

        # Enrich prompt with relevant memories
        return memory_manager.enrich_prompt_context(clean_p)
    except Exception as mem_err:
        log.warning("Memory integration error: %s", mem_err)
        return clean_p


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class HistoryMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., max_length=16_000)  # 16K chars per history message max

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"user", "assistant"}
        if v.lower() not in allowed:
            raise ValueError(f"Invalid role '{v}'. Only 'user' or 'assistant' are permitted.")
        return v.lower()


_MAX_PROMPT_CHARS = 32_000      # ~24K tokens — hard ceiling to prevent prompt bombs
_MAX_HISTORY_TURNS = 50         # 50 turns = 100 messages; beyond this, callers should summarize


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="Current user message", max_length=_MAX_PROMPT_CHARS)
    model_id: Optional[str] = Field(None, description="Override model. If None, auto-routed by intent.")
    history: List[HistoryMessage] = Field(
        default_factory=list,
        description="Prior conversation turns for multi-turn context. [{role, content}, ...]",
        max_length=_MAX_HISTORY_TURNS,
    )
    stream: bool = True


class ChatResponse(BaseModel):
    response: str
    reply: Optional[str] = None   # alias kept for frontend compatibility
    model_used: str
    telemetry: dict


# ─────────────────────────────────────────────────────────────────────────────
# Intent classifier — pure Python, ~0ms, no model call needed
# ─────────────────────────────────────────────────────────────────────────────

_CODE_KEYWORDS = {
    "code", "debug", "fix", "error", "exception", "traceback", "function",
    "class", "method", "bug", "implement", "refactor", "test", "compile",
    "syntax", "import", "python", "javascript", "typescript", "rust", "bash",
}
_PLAN_KEYWORDS = {
    "plan", "design", "architect", "strategy", "roadmap", "structure",
    "how should", "best way to", "approach for", "outline", "organize",
}
_VISION_KEYWORDS = {"image", "screenshot", "picture", "photo", "visual", "analyze image"}


def _classify_intent(prompt: str) -> str:
    """
    Classify prompt intent to select appropriate model.
    Returns: 'code' | 'plan' | 'vision' | 'chat'
    """
    lower = prompt.lower()
    if any(k in lower for k in _VISION_KEYWORDS):
        return "vision"
    if any(k in lower for k in _CODE_KEYWORDS):
        return "code"
    if any(k in lower for k in _PLAN_KEYWORDS):
        return "plan"
    return "chat"


# ─────────────────────────────────────────────────────────────────────────────
# Non-streaming endpoint (fallback)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse)
@router.post("/generate", response_model=ChatResponse)
async def generate_chat(request: ChatRequest):
    tracker = LatencyTracker()
    tracker.start()

    async with async_measure_stage(tracker, "routing"):
        provider = router_instance.get_provider()
        intent = _classify_intent(request.prompt)
        model_id = request.model_id or router_instance.resolve_model_id(intent)
        history = [{"role": m.role, "content": m.content} for m in request.history]
        effective_prompt = _process_memory_integration(request.prompt)

    log.info("Chat generate | intent=%s model=%s history_turns=%d", intent, model_id, len(history))

    agent_bus.publish(AgentEvent(
        type=EventType.AGENT_THOUGHT,
        agent="planner",
        content=f"Routing [{intent.upper()}] intent → {model_id}",
        severity="info",
    ))

    try:
        async with async_measure_stage(tracker, "model"):
            result = await provider.generate(effective_prompt, model_id=model_id, history=history)
    except Exception as e:
        log.error("NIM generate failed: %s", e)
        agent_bus.publish(AgentEvent(
            type=EventType.AGENT_RESULT,
            agent="executor",
            content=f"Model call failed for intent [{intent}]: {str(e)}",
            severity="warn",
        ))
        raise HTTPException(status_code=502, detail=f"Model call failed: {str(e)}")

    telemetry = tracker.stop()
    agent_bus.publish_result(
        agent="executor",
        content=f"Response ready [{model_id}]: {len(result)} chars, {telemetry.get('total_ms', 0):.0f}ms",
        success=True,
    )
    return ChatResponse(
        response=result,
        reply=result,
        model_used=model_id,
        telemetry=telemetry,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Streaming endpoint (primary)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/stream")
async def stream_chat(request: ChatRequest):
    provider = router_instance.get_provider()
    intent = _classify_intent(request.prompt)
    model_id = request.model_id or router_instance.resolve_model_id(intent)
    history = [{"role": m.role, "content": m.content} for m in request.history]
    effective_prompt = _process_memory_integration(request.prompt)

    log.info("Chat stream | intent=%s model=%s history_turns=%d", intent, model_id, len(history))

    agent_bus.publish(AgentEvent(
        type=EventType.AGENT_THOUGHT,
        agent="planner",
        content=f"Streaming [{intent.upper()}] → {model_id} | {len(history)} turns of context",
        severity="info",
    ))

    async def event_generator():
        tracker = LatencyTracker()
        tracker.start()
        tracker.record_stage("routing", 0.5)   # routing is sync, sub-ms
        model_start = time.perf_counter()
        tokens_yielded = 0

        try:
            async for chunk in provider.stream(effective_prompt, model_id=model_id, history=history):
                if isinstance(chunk, (tuple, list)):
                    chunk_type, token = chunk[0], chunk[1]
                else:
                    chunk_type, token = "token", chunk
                tokens_yielded += 1
                payload = json.dumps({"token": token, "type": chunk_type})
                yield f"data: {payload}\n\n"
        except Exception as e:
            log.error("NIM stream failed after %d tokens: %s", tokens_yielded, e)
            err_payload = json.dumps({
                "token": f"\n\n❌ Stream error: {str(e)}",
                "type": "error"
            })
            yield f"data: {err_payload}\n\n"

        model_elapsed = (time.perf_counter() - model_start) * 1000.0
        tracker.record_stage("model", model_elapsed)
        telemetry = tracker.stop()

        # Final telemetry frame — frontend parses this to update the telemetry panel
        final_payload = json.dumps({
            "type": "telemetry",
            "model_used": model_id,
            "intent": intent,
            "tokens_yielded": tokens_yielded,
            "telemetry": telemetry,
        })
        yield f"data: {final_payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disables nginx buffering if behind reverse proxy
        },
    )
