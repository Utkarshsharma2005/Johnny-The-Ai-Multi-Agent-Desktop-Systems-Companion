from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.models.orchestrator import multimodel_orchestrator
from backend.core.evidence_merger import MergedEvidenceReport
from backend.core.security import SecuritySandbox
from backend.core.api_security import audit_log
from backend.core.agent_bus import agent_bus

router = APIRouter(prefix="/api/v1/orchestration", tags=["Orchestration"])

_MAX_QUERY_LENGTH = 8_000   # ~6K tokens max — prevents prompt injection bombs
_MAX_MODELS_IN_REQUEST = 5  # Prevent accidental multi-model fan-out explosion

class DeliberateRequest(BaseModel):
    query: str = Field(..., description="Prompt or goal for multi-model deliberation", max_length=_MAX_QUERY_LENGTH)
    strategy: Optional[str] = Field("ensemble", description="ensemble | cascade | multimodal_fusion")
    models: Optional[List[str]] = Field(None, description="Optional explicit list of model IDs to query")
    image_path: Optional[str] = Field(None, description="Optional image path for multimodal fusion")

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"ensemble", "cascade", "multimodal_fusion"}
        if v and v.lower().strip() not in allowed:
            raise ValueError(f"Invalid strategy '{v}'. Allowed: {allowed}")
        return v

    @field_validator("models")
    @classmethod
    def validate_models_count(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v and len(v) > _MAX_MODELS_IN_REQUEST:
            raise ValueError(f"Too many models specified ({len(v)}). Maximum is {_MAX_MODELS_IN_REQUEST}.")
        return v

@router.post("/deliberate", response_model=MergedEvidenceReport)
async def run_deliberation(request: DeliberateRequest, http_request: Request):
    """
    Executes multi-model deliberation using selected strategy and synthesizes evidence report.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query prompt cannot be empty.")

    # Validate image_path through SecuritySandbox BEFORE forwarding to vision model
    safe_image_path: Optional[str] = None
    if request.image_path:
        valid, msg, resolved = SecuritySandbox.validate_file_path(request.image_path)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid image_path: {msg}")
        safe_image_path = str(resolved)

    try:
        audit_log(
            "orchestration_deliberate",
            f"strategy={request.strategy or 'ensemble'} models={request.models or 'auto'}",
            "started",
            request=http_request,
            severity="warn",
        )
        report = await multimodel_orchestrator.deliberate(
            query=request.query,
            strategy=request.strategy or "ensemble",
            models=request.models,
            image_path=safe_image_path,
        )
        for opinion in report.opinions:
            agent_bus.publish_thought(agent=opinion.model_id, content=opinion.raw_output[:1200])
        agent_bus.publish_decision(agent="orchestrator", content=report.synthesized_recommendation[:1200],
                                   metadata={"session_id": report.session_id, "consensus_ratio": report.consensus_ratio})
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deliberation failed: {str(e)}")


@router.get("/history", response_model=List[MergedEvidenceReport])
async def get_deliberation_history():
    """
    Returns history of multi-model deliberation sessions.
    """
    return multimodel_orchestrator.get_history()
