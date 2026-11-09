from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional

from backend.agents.task_engine import task_engine
from backend.core.api_security import audit_log

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])

class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(..., description="Goal prompt description for autonomous task")
    locked_requirements: Optional[Dict[str, Any]] = Field(None, description="Optional locked requirement parameters")

class TaskExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_id: Optional[str] = None

@router.get("")
async def list_tasks():
    """
    Returns list of all active and historical autonomous tasks.
    """
    return {"total_tasks": len(task_engine._tasks), "tasks": task_engine.list_tasks()}

@router.post("/terminate-all")
async def terminate_all_tasks():
    """
    Emergency termination of all active and pending autonomous tasks.
    """
    return task_engine.terminate_all_tasks()

@router.post("/create")
async def create_task(req: TaskCreateRequest):
    """
    Initializes a new autonomous task and decomposes goal into plan steps.
    """
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Task goal prompt cannot be empty.")
    
    task = task_engine.create_task(goal=req.goal, locked_requirements=req.locked_requirements)
    return task.to_dict()

@router.get("/{task_id}")
async def get_task_details(task_id: str):
    """
    Retrieves detailed task state, plan steps, verification report, and execution logs.
    """
    task = task_engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task.to_dict()

@router.post("/{task_id}/execute")
async def execute_task(task_id: str, request: Request, body: TaskExecutionRequest = TaskExecutionRequest()):
    """
    Executes autonomous step-by-step tool actions and closed-loop verification loop.
    """
    task = task_engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    result = task_engine.execute_task(task_id, approval_id=body.approval_id)
    audit_log("task_execute", task_id, task.status.value, request=request,
              severity="warn" if body.approval_id else "info")
    return result
