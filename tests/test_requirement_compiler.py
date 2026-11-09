import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.core.requirement_compiler import RequirementCompiler, RequirementStatus

def test_requirement_compiler_inspection_and_locking():
    compiler = RequirementCompiler()
    assert compiler.status == RequirementStatus.UNCOMPILED

    # Compile
    state = compiler.compile_requirements("Build authentication for my application", workspace_path=".")
    assert compiler.status == RequirementStatus.QUESTIONNAIRE_READY
    assert "known_requirements" in state
    assert len(state["questions"]) > 0

    # Lock
    answers = {"auth_method": "JWT Bearer Tokens"}
    locked_state = compiler.lock_requirements(answers)
    assert compiler.status == RequirementStatus.LOCKED
    assert locked_state["locked_requirements"].get("auth_method") == "JWT Bearer Tokens"

    # Reset
    compiler.reset()
    assert compiler.status == RequirementStatus.UNCOMPILED

@pytest.mark.asyncio
async def test_requirement_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/v1/requirements/state
        res_state = await client.get("/api/v1/requirements/state")
        assert res_state.status_code == 200

        # POST /api/v1/requirements/compile
        res_comp = await client.post("/api/v1/requirements/compile", json={"goal": "Add user database storage"})
        assert res_comp.status_code == 200
        assert res_comp.json()["status"] == "QUESTIONNAIRE_READY"

        # POST /api/v1/requirements/lock
        res_lock = await client.post("/api/v1/requirements/lock", json={"answers": {"database_engine": "SQLite (Local File)"}})
        assert res_lock.status_code == 200
        assert res_lock.json()["status"] == "LOCKED"

        # POST /api/v1/requirements/reset
        res_reset = await client.post("/api/v1/requirements/reset")
        assert res_reset.status_code == 200
        assert res_reset.json()["status"] == "UNCOMPILED"
