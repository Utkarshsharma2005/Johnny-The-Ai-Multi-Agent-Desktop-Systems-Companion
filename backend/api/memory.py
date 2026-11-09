from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from backend.memory.memory_manager import memory_manager, MemoryItem

router = APIRouter(prefix="/api/v1/memory", tags=["Memory"])

_VALID_TIERS = {"short_term", "project", "long_term", "all"}
_MAX_KEY_LENGTH = 256
_MAX_VALUE_LENGTH = 4_000   # ~3K tokens; memory items must be compact summaries
_MAX_TAGS = 10


class RecordMemoryRequest(BaseModel):
    tier: str = Field(..., description="short_term | project | long_term")
    key: str = Field(..., description="Key or topic title", max_length=_MAX_KEY_LENGTH)
    value: Any = Field(..., description="Memory payload or text")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for search indexing")

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        allowed = {"short_term", "project", "long_term"}
        if v.lower().strip() not in allowed:
            raise ValueError(f"Invalid tier '{v}'. Allowed: {allowed}")
        return v.lower().strip()

    @field_validator("value")
    @classmethod
    def validate_value_size(cls, v: Any) -> Any:
        import json
        try:
            serialized = json.dumps(v) if not isinstance(v, str) else v
        except (TypeError, ValueError):
            serialized = str(v)
        if len(serialized) > _MAX_VALUE_LENGTH:
            raise ValueError(
                f"Memory value too large ({len(serialized)} chars). "
                f"Maximum is {_MAX_VALUE_LENGTH} chars. Summarize before storing."
            )
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags_count(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v and len(v) > _MAX_TAGS:
            raise ValueError(f"Too many tags ({len(v)}). Maximum is {_MAX_TAGS}.")
        return v


@router.get("/query", response_model=List[MemoryItem])
async def query_memory_endpoint(
    term: str = Query("", description="Search term or key keyword (empty returns all in tier)"),
    tier: Optional[str] = Query(None, description="Optional tier filter: short_term | project | long_term")
):
    """
    Queries memory items across short-term, project, and long-term memory tiers.
    """
    # Validate tier query param if provided
    if tier and tier.lower() not in _VALID_TIERS:
        raise HTTPException(status_code=400, detail=f"Invalid tier '{tier}'. Valid: {_VALID_TIERS}")

    if not term.strip() and tier:
        tier_clean = tier.lower().strip()
        if tier_clean in ["short_term", "shortterm"]:
            return memory_manager.short_term.get_all()
        if tier_clean in ["project", "project_memory"]:
            return memory_manager.project.get_all()
        if tier_clean in ["long_term", "longterm", "global"]:
            return memory_manager.long_term.get_all()
    return memory_manager.query(term, tier=tier)


@router.post("/record", response_model=MemoryItem)
async def record_memory_endpoint(req: RecordMemoryRequest):
    """
    Stores a new memory entry in the specified memory tier.
    """
    if not req.key.strip():
        raise HTTPException(status_code=400, detail="Memory key cannot be empty.")

    try:
        return memory_manager.record(req.tier, req.key, req.value, req.tags)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.delete("/clear/{tier}")
async def clear_memory_endpoint(tier: str):
    """
    Clears memories for the specified tier ('short_term', 'project', 'long_term', or 'all').
    """
    if tier.lower() not in _VALID_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier '{tier}'. Valid tiers: {sorted(_VALID_TIERS)}"
        )
    target = None if tier.lower() == "all" else tier
    memory_manager.clear(target)
    return {"status": "success", "message": f"Cleared memory tier '{tier}'."}
