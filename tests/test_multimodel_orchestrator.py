import pytest
import tempfile
from PIL import Image
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.core.config import settings
from backend.core.evidence_merger import EvidenceMerger, ModelOpinion, MergedEvidenceReport
from backend.models.orchestrator import MultimodelOrchestrator, multimodel_orchestrator
from backend.models.mock_provider import MockProvider

def test_evidence_merger_consensus_and_conflict():
    op1 = ModelOpinion(
        model_id="meta/llama-3.3-70b-instruct",
        raw_output="System is healthy and operational.",
        confidence=0.90,
        key_assertions=["System is healthy and operational."]
    )
    op2 = ModelOpinion(
        model_id="deepseek-ai/deepseek-r1",
        raw_output="System is healthy and operational.",
        confidence=0.95,
        key_assertions=["System is healthy and operational."]
    )

    report = EvidenceMerger.merge_opinions("Is system healthy?", "ensemble", [op1, op2])
    assert report.consensus_ratio == 1.0
    assert report.conflict_detected is False
    assert len(report.evidence_items) == 1
    assert report.evidence_items[0].status == "CONSENSUS"

    # Conflicting case
    op3 = ModelOpinion(
        model_id="nvidia/nemotron-4-340b-instruct",
        raw_output="Critical memory leak detected in system daemon.",
        confidence=0.85,
        key_assertions=["Critical memory leak detected in system daemon."]
    )

    report_conflict = EvidenceMerger.merge_opinions("Is system healthy?", "ensemble", [op1, op2, op3])
    # FIXED (hardening): a single-model claim absent from other outputs is
    # UNVERIFIED (no corroboration), NOT a conflict — no one opposed it.
    assert report_conflict.conflict_detected is False
    assert len(report_conflict.evidence_items) >= 2
    assert any(i.status == "UNVERIFIED" for i in report_conflict.evidence_items)

@pytest.mark.asyncio
async def test_orchestrator_ensemble_strategy():
    orchestrator = MultimodelOrchestrator(provider=MockProvider())
    report = await orchestrator.deliberate(
        query="Design scalable microservices architecture",
        strategy="ensemble",
        models=["meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1"]
    )

    assert report.strategy_used == "ensemble"
    assert len(report.opinions) == 2
    assert report.synthesized_recommendation is not None

@pytest.mark.asyncio
async def test_orchestrator_cascade_strategy():
    orchestrator = MultimodelOrchestrator(provider=MockProvider())
    report = await orchestrator.deliberate(
        query="Verify and debug complex algorithm",
        strategy="cascade"
    )

    assert report.strategy_used == "cascade"
    assert len(report.opinions) >= 1
    assert "Primary Recommendation" in report.synthesized_recommendation

@pytest.mark.asyncio
async def test_orchestrator_multimodal_fusion():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(tmp.name)
        tmp_path = tmp.name

    orchestrator = MultimodelOrchestrator(provider=MockProvider())
    report = await orchestrator.deliberate(
        query="Inspect image and describe UI element status",
        strategy="multimodal_fusion",
        image_path=tmp_path
    )

    assert report.strategy_used == "multimodal_fusion"
    assert len(report.opinions) >= 2
    model_ids = [op.model_id for op in report.opinions]
    assert settings.MINIMAX_MODEL_ID in model_ids

@pytest.mark.asyncio
async def test_orchestration_api_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_deliberate = await ac.post("/api/v1/orchestration/deliberate", json={
            "query": "Review system memory usage and propose optimizations",
            "strategy": "ensemble"
        })
        assert res_deliberate.status_code == 200
        data = res_deliberate.json()
        assert "session_id" in data
        assert "synthesized_recommendation" in data
        assert data["strategy_used"] == "ensemble"

        res_history = await ac.get("/api/v1/orchestration/history")
        assert res_history.status_code == 200
        history = res_history.json()
        assert isinstance(history, list)
        assert len(history) >= 1
