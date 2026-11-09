import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.core.verification_engine import VerificationEngine

def test_verification_engine_checks():
    # Lint check
    lint_res = VerificationEngine.run_lint_check(target_path=".")
    assert lint_res.passed is True

    # Health check
    health_res = VerificationEngine.run_health_check()
    assert health_res.passed is True

    # Full verification suite
    full_report = VerificationEngine.run_full_verification(checks=["LINT", "HEALTH_CHECK"], target_path=".")
    assert full_report["is_verified"] is True
    assert full_report["confidence_score"] == 1.0

@pytest.mark.asyncio
async def test_verification_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/verification/verify", json={"checks": ["LINT", "HEALTH_CHECK"]})
        assert res.status_code == 200
        data = res.json()
        assert data["is_verified"] is True
        assert "passed_checks" in data
