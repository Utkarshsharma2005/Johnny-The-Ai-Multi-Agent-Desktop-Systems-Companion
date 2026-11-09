from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from backend.agents.resumption_engine import resumption_engine
from backend.core.task_store import task_store

router = APIRouter(prefix="/api/v1/persistence", tags=["Persistence"])

@router.get("/interrupted", response_model=List[Dict[str, Any]])
async def list_interrupted_tasks_endpoint():
    """
    Returns list of interrupted or uncompleted task checkpoints available for crash recovery.
    """
    return resumption_engine.detect_interrupted_tasks()

@router.post("/resume/{task_id}")
async def resume_interrupted_task_endpoint(task_id: str):
    """
    Resumes execution of an interrupted task checkpoint seamlessly from disk state.
    """
    try:
        return resumption_engine.resume_task(task_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume task '{task_id}': {str(e)}")

@router.delete("/checkpoints/{task_id}")
async def delete_task_checkpoint_endpoint(task_id: str):
    """
    Deletes saved disk checkpoint file for a task ID.
    """
    deleted = task_store.delete_checkpoint(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Checkpoint for task '{task_id}' not found.")
    return {"status": "success", "message": f"Checkpoint for '{task_id}' deleted successfully."}
