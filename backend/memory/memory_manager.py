import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Strict resource optimization limits to prevent memory hoards
MAX_VALUE_LENGTH = 1000       # Cap payload string representation length
MAX_SHORT_TERM_ITEMS = 20    # Sliding window capacity
MAX_PROJECT_ITEMS = 50       # Cap project memory entries
MAX_GLOBAL_ITEMS = 50        # Cap long-term user memory entries

def _sanitize_value(val: Any) -> Any:
    """
    Truncates memory payloads if they exceed MAX_VALUE_LENGTH to avoid RAM bloat.
    """
    if isinstance(val, str):
        if len(val) > MAX_VALUE_LENGTH:
            return val[:MAX_VALUE_LENGTH] + "... [truncated for memory efficiency]"
        return val
    elif isinstance(val, (dict, list)):
        dumped = json.dumps(val)
        if len(dumped) > MAX_VALUE_LENGTH:
            return f"{dumped[:MAX_VALUE_LENGTH]}... [truncated]"
        return val
    return val

class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:8]}")
    tier: str = Field(..., description="short_term | project | long_term")
    key: str = Field(..., description="Key or topic identifier")
    value: Any = Field(..., description="Memory payload or content")
    tags: List[str] = Field(default_factory=list, description="Associated search tags")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class ShortTermMemory:
    """
    In-memory sliding window buffer with strict capacity enforcement.
    """
    def __init__(self, capacity: int = MAX_SHORT_TERM_ITEMS):
        self.capacity = capacity
        self.items: List[MemoryItem] = []

    def add(self, key: str, value: Any, tags: Optional[List[str]] = None) -> MemoryItem:
        sanitized = _sanitize_value(value)
        item = MemoryItem(tier="short_term", key=key, value=sanitized, tags=tags or [])
        self.items.append(item)
        while len(self.items) > self.capacity:
            self.items.pop(0)  # FIFO eviction
        return item

    def query(self, term: str) -> List[MemoryItem]:
        term_clean = term.lower()
        results = []
        for item in self.items:
            content_str = f"{item.key} {json.dumps(item.value)} {' '.join(item.tags)}".lower()
            if term_clean in content_str:
                results.append(item)
        return results

    def clear(self):
        self.items.clear()

    def get_all(self) -> List[MemoryItem]:
        return list(self.items)

class PersistentMemoryTier:
    """
    Ultra-lightweight disk-persistent memory store with capacity bounds and atomic writes.
    """
    def __init__(self, tier_name: str, file_path: Path, max_capacity: int = 50):
        self.tier_name = tier_name
        self.file_path = file_path
        self.max_capacity = max_capacity
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._items: Dict[str, MemoryItem] = {}
        self._load()

    def _load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item_dict in data:
                        item = MemoryItem(**item_dict)
                        self._items[item.id] = item
                self._enforce_capacity()
            except Exception:
                self._items = {}

    def _enforce_capacity(self):
        """Evicts oldest items if capacity exceeds limit to prevent memory hoard."""
        if len(self._items) > self.max_capacity:
            sorted_keys = sorted(self._items.keys(), key=lambda k: self._items[k].timestamp)
            excess = len(self._items) - self.max_capacity
            for k in sorted_keys[:excess]:
                del self._items[k]

    def _save(self):
        self._enforce_capacity()
        tmp_file = self.file_path.with_suffix(".json.tmp")
        payload = [item.model_dump() for item in self._items.values()]
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(',', ':'))  # Compact JSON without whitespace bloat
        tmp_file.replace(self.file_path)

    def add(self, key: str, value: Any, tags: Optional[List[str]] = None) -> MemoryItem:
        sanitized = _sanitize_value(value)
        item = MemoryItem(tier=self.tier_name, key=key, value=sanitized, tags=tags or [])
        self._items[item.id] = item
        self._save()
        return item

    def query(self, term: str) -> List[MemoryItem]:
        term_clean = term.lower()
        results = []
        for item in self._items.values():
            content_str = f"{item.key} {json.dumps(item.value)} {' '.join(item.tags)}".lower()
            if term_clean in content_str:
                results.append(item)
        return results

    def clear(self):
        self._items.clear()
        self._save()

    def get_all(self) -> List[MemoryItem]:
        return list(self._items.values())

class ProjectMemory(PersistentMemoryTier):
    """
    Disk-persistent project-level memory stored in .johnny/memory/project.json
    """
    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            path = Path(base_dir).expanduser().resolve() / ".johnny" / "memory" / "project.json"
        else:
            path = Path.cwd() / ".johnny" / "memory" / "project.json"
        super().__init__(tier_name="project", file_path=path, max_capacity=MAX_PROJECT_ITEMS)

class LongTermMemory(PersistentMemoryTier):
    """
    Disk-persistent global user memory stored in ~/.johnny/memory/global.json
    """
    def __init__(self, custom_path: Optional[str] = None):
        if custom_path:
            path = Path(custom_path).expanduser().resolve()
        else:
            path = Path.home() / ".johnny" / "memory" / "global.json"
        super().__init__(tier_name="long_term", file_path=path, max_capacity=MAX_GLOBAL_ITEMS)

class MemoryManager:
    """
    Unified Memory Subsystem facade aggregating short-term, project, and long-term memory tiers.
    Optimized for zero-leak, compact memory footprint and fast atomic writes.
    """
    def __init__(
        self,
        short_term: Optional[ShortTermMemory] = None,
        project: Optional[ProjectMemory] = None,
        long_term: Optional[LongTermMemory] = None
    ):
        self.short_term = short_term or ShortTermMemory()
        self.project = project or ProjectMemory()
        self.long_term = long_term or LongTermMemory()

    def record(self, tier: str, key: str, value: Any, tags: Optional[List[str]] = None) -> MemoryItem:
        tier_clean = tier.lower().strip()
        if tier_clean in ["short_term", "shortterm"]:
            return self.short_term.add(key, value, tags)
        elif tier_clean in ["project", "project_memory"]:
            return self.project.add(key, value, tags)
        elif tier_clean in ["long_term", "longterm", "global"]:
            return self.long_term.add(key, value, tags)
        else:
            raise ValueError(f"Unknown memory tier '{tier}'. Supported: short_term, project, long_term.")

    def query(self, term: str, tier: Optional[str] = None) -> List[MemoryItem]:
        results = []
        if not tier or tier.lower() in ["short_term", "shortterm"]:
            results.extend(self.short_term.query(term))
        if not tier or tier.lower() in ["project", "project_memory"]:
            results.extend(self.project.query(term))
        if not tier or tier.lower() in ["long_term", "longterm", "global"]:
            results.extend(self.long_term.query(term))
        return results

    def clear(self, tier: Optional[str] = None):
        if not tier or tier.lower() in ["short_term", "shortterm"]:
            self.short_term.clear()
        if not tier or tier.lower() in ["project", "project_memory"]:
            self.project.clear()
        if not tier or tier.lower() in ["long_term", "longterm", "global"]:
            self.long_term.clear()

    def enrich_prompt_context(self, prompt: str) -> str:
        """
        Injects relevant project & long-term memories into system prompt context.
        Truncates enriched context blocks to prevent token bloat.
        """
        relevant_project = self.project.get_all()[:2]
        relevant_global = self.long_term.get_all()[:2]

        if not relevant_project and not relevant_global:
            return prompt

        context_blocks = []
        if relevant_project:
            p_str = "\n".join([f"- {item.key}: {json.dumps(item.value)}" for item in relevant_project])
            context_blocks.append(f"[Project Context Memory]:\n{p_str}")

        if relevant_global:
            g_str = "\n".join([f"- {item.key}: {json.dumps(item.value)}" for item in relevant_global])
            context_blocks.append(f"[User Long-Term Preferences]:\n{g_str}")

        enriched_context = "\n\n".join(context_blocks)
        return f"{enriched_context}\n\n[User Prompt]:\n{prompt}"

# Global MemoryManager instance
memory_manager = MemoryManager()
