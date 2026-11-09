from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from backend.core.requirement_compiler import requirement_compiler

router = APIRouter(prefix="/api/v1/requirements", tags=["Requirements"])

class CompileRequest(BaseModel):
    goal: str = Field(..., description="Task goal description prompt")
    workspace_path: Optional[str] = Field(".", description="Path to local workspace directory")

class LockRequest(BaseModel):
    answers: Dict[str, str] = Field(..., description="User selected answers for questionnaire items")

@router.get("/state")
async def get_requirement_state():
    """
    Returns current requirement compiler state (known environment, questionnaire, locked requirements).
    """
    return requirement_compiler.get_state()

@router.post("/compile")
async def compile_task_requirements(req: CompileRequest):
    """
    Inspects local environment and compiles consolidated requirement questionnaire.
    """
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Task goal description cannot be empty.")
    
    result = requirement_compiler.compile_requirements(
        goal_prompt=req.goal,
        workspace_path=req.workspace_path or "."
    )
    return result

@router.post("/lock")
async def lock_task_requirements(req: LockRequest):
    """
    Locks requirement choices into a RequirementLock state.
    """
    result = requirement_compiler.lock_requirements(req.answers)
    return result

@router.post("/reset")
async def reset_task_requirements():
    """
    Resets requirement compiler to UNCOMPILED state.
    """
    requirement_compiler.reset()
    return {"status": "UNCOMPILED", "message": "Requirement compiler reset successfully."}
