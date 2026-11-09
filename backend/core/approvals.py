"""Short lived, one use approval grants bound to an exact server action."""
import hashlib
import json
import secrets
import threading
import time
from typing import Any, Dict, Optional


class ApprovalBroker:
    TTL_SECONDS = 180
    MAX_RECORDS = 500

    def __init__(self):
        self._items: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def digest(action: str, arguments: Dict[str, Any]) -> str:
        body = json.dumps({"action": action, "arguments": arguments}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def request(self, action: str, arguments: Dict[str, Any], *, task_id: Optional[str] = None,
                step_number: Optional[int] = None, risk_level: int = 2) -> Dict[str, Any]:
        now = time.time()
        ticket = secrets.token_urlsafe(32)
        record = {"id": ticket, "action": action, "digest": self.digest(action, arguments),
                  "arguments": arguments, "task_id": task_id, "step_number": step_number,
                  "risk_level": risk_level, "status": "pending", "created_at": now,
                  "expires_at": now + self.TTL_SECONDS}
        with self._lock:
            self._prune(now)
            if len(self._items) >= self.MAX_RECORDS:
                oldest = min(self._items, key=lambda key: self._items[key]["expires_at"])
                del self._items[oldest]
            self._items[ticket] = record
        return self.public(record)

    def public(self, record: Dict[str, Any]) -> Dict[str, Any]:
        risk_level = {0: "low", 1: "low", 2: "high", 3: "critical"}.get(record["risk_level"], "high")
        return {
            "id": record["id"], "agent": "executor", "action": record["action"],
            "description": f"Review the exact arguments below before allowing {record['action']} to run.",
            "risk_level": risk_level, "arguments": record["arguments"],
            "task_id": record["task_id"], "step_number": record["step_number"],
            "metadata": {"arguments": record["arguments"], "task_id": record["task_id"],
                         "step_number": record["step_number"]},
            "timestamp": record["created_at"], "status": record["status"],
            "expires_at": record["expires_at"], **({"result": record["result"]} if "result" in record else {}),
        }

    def set_result(self, ticket: str, result: Dict[str, Any]) -> None:
        with self._lock:
            if ticket in self._items:
                self._items[ticket]["result"] = result

    def list_pending(self):
        with self._lock:
            self._prune(time.time())
            return [self.public(item) for item in self._items.values() if item["status"] == "pending"]

    def resolve(self, ticket: str, approved: bool) -> bool:
        with self._lock:
            self._prune(time.time())
            item = self._items.get(ticket)
            if not item or item["status"] != "pending":
                return False
            item["status"] = "approved" if approved else "denied"
            return True

    def consume(self, ticket: str, action: str, arguments: Dict[str, Any], *,
                task_id: Optional[str] = None, step_number: Optional[int] = None) -> bool:
        with self._lock:
            self._prune(time.time())
            item = self._items.get(ticket)
            if not item or item["status"] != "approved":
                return False
            if (item["action"] != action or item["task_id"] != task_id or item["step_number"] != step_number
                    or not secrets.compare_digest(item["digest"], self.digest(action, arguments))):
                return False
            item["status"] = "consumed"
            return True

    def get(self, ticket: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            self._prune(time.time())
            item = self._items.get(ticket)
            return self.public(item) if item else None

    def _prune(self, now: float):
        for key in [key for key, value in self._items.items() if value["expires_at"] <= now]:
            del self._items[key]


approval_broker = ApprovalBroker()
