import tempfile
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.core.task_store import TaskPersistenceStore, task_store
from backend.agents.task_engine import AutonomousTaskEngine, TaskStatus
from backend.agents.resumption_engine import CrashResumptionEngine

def test_task_store_save_load_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TaskPersistenceStore(base_dir=tmpdir)
        task_data = {
            "id": "task-test123",
            "goal": "Test goal for persistence",
            "status": "IN_PROGRESS",
            "steps": [{"step_number": 1, "description": "Step 1", "status": "COMPLETED"}]
        }

        # 1. Save checkpoint
        saved_path = store.save_checkpoint("task-test123", task_data)
        assert Path(saved_path).exists()

        # 2. Load checkpoint
        loaded = store.load_checkpoint("task-test123")
        assert loaded is not None
        assert loaded["id"] == "task-test123"
        assert loaded["status"] == "IN_PROGRESS"

        # 3. List interrupted tasks
        interrupted = store.list_interrupted_tasks()
        assert len(interrupted) == 1
        assert interrupted[0]["id"] == "task-test123"

        # 4. Delete checkpoint
        deleted = store.delete_checkpoint("task-test123")
        assert deleted is True
        assert store.load_checkpoint("task-test123") is None

def test_crash_resumption_engine_recovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TaskPersistenceStore(base_dir=tmpdir)
        engine = AutonomousTaskEngine()
        resumption = CrashResumptionEngine(store=store, engine=engine)

        task_id = "task-crash-test"
        checkpoint_data = {
            "id": task_id,
            "goal": "Simulate crash recovery",
            "status": "EXECUTION",
            "recovery_attempts": 0,
            "steps": [
                {
                    "step_number": 1,
                    "description": "Pre-crash step",
                    "tool_name": None,
                    "tool_args": {},
                    "status": "COMPLETED",
                    "output": {"success": True, "message": "Pre-crash step"},
                    "latency_ms": 1.0
                },
                {
                    "step_number": 2,
                    "description": "Post-crash step",
                    "tool_name": "git_status",
                    "tool_args": {},
                    "status": "PENDING",
                    "output": None,
                    "latency_ms": 0.0
                }
            ],
            "logs": ["Initial log before crash"]
        }
        store.save_checkpoint(task_id, checkpoint_data)

        # Verify detection of interrupted task
        interrupted = resumption.detect_interrupted_tasks()
        assert len(interrupted) >= 1
        found_ids = [t["id"] for t in interrupted]
        assert task_id in found_ids

        # Resume task execution
        resumed_dict = resumption.resume_task(task_id)
        assert resumed_dict["id"] == task_id
        assert resumed_dict["status"] in ["COMPLETED", "FAILED"]
        
        # Verify logs recorded crash resumption event
        logs_str = "".join(resumed_dict["logs"])
        assert "CrashResumptionEngine" in logs_str

@pytest.mark.asyncio
async def test_persistence_api_endpoints():
    task_id = "task-api-test"
    checkpoint_data = {
        "id": task_id,
        "goal": "Test API persistence endpoint",
        "status": "EXECUTION",
        "steps": [
            {
                "step_number": 1,
                "description": "Step 1",
                "tool_name": None,
                "tool_args": {},
                "status": "PENDING",
                "output": None,
                "latency_ms": 0.0
            }
        ],
        "logs": []
    }
    task_store.save_checkpoint(task_id, checkpoint_data)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. GET interrupted
        res_list = await ac.get("/api/v1/persistence/interrupted")
        assert res_list.status_code == 200
        interrupted = res_list.json()
        assert isinstance(interrupted, list)

        # 2. POST resume
        res_resume = await ac.post(f"/api/v1/persistence/resume/{task_id}")
        assert res_resume.status_code == 200
        resumed_data = res_resume.json()
        assert resumed_data["id"] == task_id

        # 3. DELETE checkpoint
        res_del = await ac.delete(f"/api/v1/persistence/checkpoints/{task_id}")
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "success"
