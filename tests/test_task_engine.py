import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.agents.task_engine import AutonomousTaskEngine, TaskStatus

def test_autonomous_task_engine_lifecycle():
    engine = AutonomousTaskEngine()

    # Create Task
    task = engine.create_task("Verify workspace git status and directory contents")
    assert task.status == TaskStatus.PLANNING
    assert len(task.steps) > 0

    # Execute Task
    exec_result = engine.execute_task(task.id)
    assert exec_result["status"] == TaskStatus.COMPLETED.value
    assert exec_result["verification_report"] is not None
    assert exec_result["verification_report"]["is_verified"] is True

@pytest.mark.asyncio
async def test_tasks_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/v1/tasks
        res_list = await client.get("/api/v1/tasks")
        assert res_list.status_code == 200

        # POST /api/v1/tasks/create
        res_create = await client.post("/api/v1/tasks/create", json={"goal": "Verify backend health and run linting"})
        assert res_create.status_code == 200
        task_id = res_create.json()["id"]

        # GET /api/v1/tasks/{task_id}
        res_get = await client.get(f"/api/v1/tasks/{task_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == task_id

        # POST /api/v1/tasks/{task_id}/execute
        res_exec = await client.post(f"/api/v1/tasks/{task_id}/execute")
        assert res_exec.status_code == 200
        assert res_exec.json()["status"] in ["COMPLETED", "VERIFYING"]
