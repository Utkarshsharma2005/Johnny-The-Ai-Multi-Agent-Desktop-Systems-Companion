"""
agent_bus.py — In-memory event bus for multi-agent communication.

Agents publish events here (reasoning steps, decisions, debates, permission
requests). The frontend subscribes via SSE to get a live feed.

Design:
  - Ring buffer (max 200 events) — no database needed.
  - asyncio.Queue per SSE subscriber — fan-out to all listeners.
  - Permission requests: blocking Future that the frontend resolves.
"""

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from backend.core import redaction


class EventType(str, Enum):
    AGENT_THOUGHT    = "AGENT_THOUGHT"      # Internal reasoning step
    AGENT_DECISION   = "AGENT_DECISION"     # Agent decided something
    AGENT_DEBATE     = "AGENT_DEBATE"       # Two agents disagree / debate
    AGENT_ACTION     = "AGENT_ACTION"       # Agent about to run a tool
    AGENT_RESULT     = "AGENT_RESULT"       # Tool result / outcome
    PERMISSION_REQ   = "PERMISSION_REQUEST" # Needs user approval
    PERMISSION_RESP  = "PERMISSION_RESPONSE"# User approved/denied
    TASK_STATUS      = "TASK_STATUS"        # Task lifecycle update
    SYSTEM_INFO      = "SYSTEM_INFO"        # System / meta messages


@dataclass
class AgentEvent:
    id:          str       = field(default_factory=lambda: uuid.uuid4().hex[:12])
    type:        EventType = EventType.SYSTEM_INFO
    agent:       str       = "system"          # Which agent produced this
    target:      str       = ""                # Which agent it's directed at
    content:     str       = ""                # Human-readable message
    metadata:    Dict[str, Any] = field(default_factory=dict)
    timestamp:   float     = field(default_factory=time.time)
    severity:    str       = "info"            # "info" | "warn" | "critical"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d


@dataclass
class PermissionRequest:
    id:          str       = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent:       str       = "system"
    action:      str       = ""                # Short action label
    description: str       = ""                # Full description for user
    risk_level:  str       = "medium"          # "low" | "medium" | "high" | "critical"
    metadata:    Dict[str, Any] = field(default_factory=dict)
    timestamp:   float     = field(default_factory=time.time)
    # Internal: resolved by user
    _future:     Optional[asyncio.Future] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":          self.id,
            "agent":       self.agent,
            "action":      self.action,
            "description": self.description,
            "risk_level":  self.risk_level,
            "metadata":    self.metadata,
            "timestamp":   self.timestamp,
        }


class AgentEventBus:
    """Singleton event bus — import and use `agent_bus` directly."""

    MAX_HISTORY = 200

    def __init__(self):
        self._history:     Deque[AgentEvent]            = deque(maxlen=self.MAX_HISTORY)
        self._subscribers: List[asyncio.Queue]           = []
        self._pending_permissions: Dict[str, PermissionRequest] = {}

    # ── Publishing ────────────────────────────────────────────────────────────

    def publish(self, event: AgentEvent) -> None:
        """Synchronous publish (safe to call from sync code).
        SECURITY: content and metadata are redacted before broadcast so API
        keys/tokens never flow to untrusted subscribers."""
        event.content = redaction.redact_text(event.content or "")
        event.metadata = redaction.redact_json(event.metadata or {})
        self._history.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow subscriber — skip frame, don't block

    async def publish_async(self, event: AgentEvent) -> None:
        """Async publish — awaits each subscriber queue put."""
        self.publish(event)  # redaction happens in the sync path
        for q in list(self._subscribers):
            await q.put(event)

    def publish_thought(self, agent: str, content: str, target: str = "", severity: str = "info") -> AgentEvent:
        ev = AgentEvent(type=EventType.AGENT_THOUGHT, agent=agent, target=target, content=content, severity=severity)
        self.publish(ev)
        return ev

    def publish_decision(self, agent: str, content: str, metadata: Optional[Dict] = None) -> AgentEvent:
        ev = AgentEvent(type=EventType.AGENT_DECISION, agent=agent, content=content, metadata=metadata or {})
        self.publish(ev)
        return ev

    def publish_debate(self, agent: str, target: str, content: str, severity: str = "warn") -> AgentEvent:
        ev = AgentEvent(type=EventType.AGENT_DEBATE, agent=agent, target=target, content=content, severity=severity)
        self.publish(ev)
        return ev

    def publish_action(self, agent: str, action: str, metadata: Optional[Dict] = None) -> AgentEvent:
        ev = AgentEvent(type=EventType.AGENT_ACTION, agent=agent, content=action, metadata=metadata or {})
        self.publish(ev)
        return ev

    def publish_result(self, agent: str, content: str, success: bool = True) -> AgentEvent:
        ev = AgentEvent(
            type=EventType.AGENT_RESULT,
            agent=agent,
            content=content,
            severity="info" if success else "warn"
        )
        self.publish(ev)
        return ev

    # ── Permission Requests ────────────────────────────────────────────────────

    async def request_permission(
        self,
        agent: str,
        action: str,
        description: str,
        risk_level: str = "medium",
        metadata: Optional[Dict] = None,
        timeout: float = 120.0,
    ) -> bool:
        """
        Agents call this to ask the user for permission before a risky action.
        Blocks until user approves/denies (or timeout → auto-deny).
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        req = PermissionRequest(
            agent=agent,
            action=action,
            description=description,
            risk_level=risk_level,
            metadata=metadata or {},
            _future=future,
        )
        self._pending_permissions[req.id] = req

        # Notify all SSE subscribers about the permission request
        ev = AgentEvent(
            type=EventType.PERMISSION_REQ,
            agent=agent,
            content=f"Permission required: {action}",
            metadata=req.to_dict(),
            severity="critical" if risk_level == "critical" else "warn",
        )
        self.publish(ev)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self.publish(AgentEvent(
                type=EventType.PERMISSION_RESP,
                agent="system",
                content=f"Permission request '{action}' timed out — auto-denied.",
                severity="warn",
            ))
            return False
        finally:
            self._pending_permissions.pop(req.id, None)

    def resolve_permission(self, request_id: str, approved: bool) -> bool:
        """Called by the API endpoint when the user responds."""
        req = self._pending_permissions.get(request_id)
        if req is None or req._future is None:
            return False
        if not req._future.done():
            req._future.set_result(approved)
            ev = AgentEvent(
                type=EventType.PERMISSION_RESP,
                agent="user",
                content=f"Permission {'GRANTED ✅' if approved else 'DENIED ❌'}: {req.action}",
                severity="info" if approved else "warn",
            )
            self.publish(ev)
            return True
        return False

    def list_pending_permissions(self) -> List[Dict]:
        return [r.to_dict() for r in self._pending_permissions.values()]

    # ── SSE Subscription ────────────────────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        """Returns a queue that receives all future events."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def history(self, limit: int = 50) -> List[Dict]:
        items = list(self._history)
        return [e.to_dict() for e in items[-limit:]]


# ── Global singleton ────────────────────────────────────────────────────────────
agent_bus = AgentEventBus()
