import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.core import redaction

log = logging.getLogger(__name__)

# Task ID must only contain safe characters to prevent path traversal via task filenames
_TASK_ID_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9_\-]")
_MAX_TASK_ID_LENGTH = 128

class TaskPersistenceStore:
    """
    Atomic disk-backed task checkpoint store for Johnny task execution persistence.
    Saves and loads state files in .johnny/tasks/
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.tasks_dir = Path(base_dir).expanduser().resolve() / ".johnny" / "tasks"
        else:
            self.tasks_dir = Path.cwd() / ".johnny" / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def _get_task_file(self, task_id: str) -> Path:
        # Sanitize: strip all non-alphanumeric/hyphen/underscore characters
        safe_id = _TASK_ID_SAFE_PATTERN.sub("_", task_id)
        if len(safe_id) > _MAX_TASK_ID_LENGTH:
            safe_id = safe_id[:_MAX_TASK_ID_LENGTH]
        if not safe_id:
            raise ValueError("Task ID produced an empty filename after sanitization.")
        return self.tasks_dir / f"{safe_id}.json"

    def save_checkpoint(self, task_id: str, state_data: Dict[str, Any]) -> str:
        """
        Atomically saves task state data to disk using temporary file swap.
        SECURITY: the payload is redacted before persisting (logs/outputs can
        contain secrets collected during tool execution).
        """
        task_file = self._get_task_file(task_id)
        tmp_file = task_file.with_suffix(".json.tmp")

        redacted_data = redaction.redact_json(state_data)
        if redaction.contains_secret(json.dumps(state_data, default=str)):
            log.warning(
                "Task checkpoint '%s' contained credential-like content — data was redacted before persistence.",
                task_id,
            )

        payload = {
            **redacted_data,
            "task_id": task_id,
            "last_updated_at": datetime.now().isoformat()
        }

        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            tmp_file.replace(task_file)
            return str(task_file)
        except Exception as e:
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to save task checkpoint for '{task_id}': {str(e)}")

    def load_checkpoint(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Loads saved task state data from disk.
        """
        task_file = self._get_task_file(task_id)
        if not task_file.exists():
            return None

        try:
            with open(task_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to read checkpoint file '{task_file}': {str(e)}")

    def list_interrupted_tasks(self) -> List[Dict[str, Any]]:
        """
        Returns list of task state checkpoints that were interrupted before completion.
        """
        interrupted = []
        if not self.tasks_dir.exists():
            return interrupted

        for file_path in self.tasks_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    status = (data.get("status") or "").lower()
                    if status and status not in ["completed", "failed"]:
                        interrupted.append(data)
            except Exception:
                continue

        return interrupted

    def delete_checkpoint(self, task_id: str) -> bool:
        """
        Deletes checkpoint file for task_id.
        """
        task_file = self._get_task_file(task_id)
        if task_file.exists():
            task_file.unlink()
            return True
        return False

# Global task store instance
task_store = TaskPersistenceStore()
