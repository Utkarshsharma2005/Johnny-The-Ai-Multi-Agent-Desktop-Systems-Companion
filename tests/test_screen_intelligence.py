import pytest
from PIL import Image, ImageDraw
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.perception.screen_capture import DesktopScreenCapturer
from backend.perception.change_detector import ScreenChangeDetector
from backend.perception.privacy import ScreenPrivacyManager, ScreenObservationStatus
from backend.perception.escalation_engine import ScreenEscalationEngine, ObservationMode, EscalationLevel

def test_screen_capturer_synthetic_fallback():
    success, msg, img = DesktopScreenCapturer.capture_frame()
    assert success is True
    assert img is not None
    assert img.width > 0 and img.height > 0

    downscaled = DesktopScreenCapturer.downscale_image(img, max_dim=400)
    assert max(downscaled.size) <= 400

def test_change_detector_identical_frames():
    img1 = Image.new("RGB", (200, 200), color=(100, 100, 100))
    img2 = Image.new("RGB", (200, 200), color=(100, 100, 100))

    diff_res = ScreenChangeDetector.compute_diff(img1, img2, threshold=0.02)
    assert diff_res.has_changed is False
    assert diff_res.diff_score == 0.0

def test_change_detector_modified_frames():
    img1 = Image.new("RGB", (200, 200), color=(0, 0, 0))
    img2 = Image.new("RGB", (200, 200), color=(255, 255, 255))

    diff_res = ScreenChangeDetector.compute_diff(img1, img2, threshold=0.02)
    assert diff_res.has_changed is True
    assert diff_res.diff_score > 0.9

def test_privacy_manager_pause_resume():
    pm = ScreenPrivacyManager()
    assert pm.is_paused is False
    assert pm.status == ScreenObservationStatus.OBSERVING

    pm.pause()
    assert pm.is_paused is True
    assert pm.status == ScreenObservationStatus.PAUSED

    pm.resume()
    assert pm.is_paused is False
    assert pm.status == ScreenObservationStatus.OBSERVING

def test_privacy_manager_window_exclusions():
    pm = ScreenPrivacyManager()
    assert pm.is_window_excluded("1Password - Vault") is True
    assert pm.is_window_excluded("Bitwarden Password Manager") is True
    assert pm.is_window_excluded("VS Code - johnny project") is False

def test_escalation_engine_level1_diff_stop():
    engine = ScreenEscalationEngine()
    engine.set_mode(ObservationMode.AMBIENT)

    # First capture (initial frame -> level 3 or level 1 depending on setup)
    res1 = engine.process_screen_cycle(force_escalate=False)
    assert "status" in res1

    # Second capture with identical frame -> should stop at Level 1 diff
    res2 = engine.process_screen_cycle(force_escalate=False)
    assert res2["escalation_level"] == EscalationLevel.LEVEL_1_DIFF.value
    assert res2["status"] == ScreenObservationStatus.OBSERVING.value

def test_escalation_engine_paused_mode():
    engine = ScreenEscalationEngine()
    engine.set_mode(ObservationMode.PAUSED)

    res = engine.process_screen_cycle()
    assert res["status"] == ScreenObservationStatus.PAUSED.value
    assert res["escalation_level"] == EscalationLevel.LEVEL_0_CAPTURE.value

@pytest.mark.asyncio
async def test_screen_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/v1/screen/state
        res_state = await client.get("/api/v1/screen/state")
        assert res_state.status_code == 200
        state = res_state.json()
        assert "mode" in state
        assert "status" in state

        # POST /api/v1/screen/mode
        res_mode = await client.post("/api/v1/screen/mode", json={"mode": "ATTENTIVE"})
        assert res_mode.status_code == 200
        assert res_mode.json()["state"]["mode"] == "ATTENTIVE"

        # POST /api/v1/screen/capture
        res_cap = await client.post("/api/v1/screen/capture", json={"force_escalate": False})
        assert res_cap.status_code == 200
        assert "escalation_level" in res_cap.json()

        # POST /api/v1/screen/pause
        res_pause = await client.post("/api/v1/screen/pause")
        assert res_pause.status_code == 200
        assert res_pause.json()["status"] == "PAUSED"

        # POST /api/v1/screen/resume
        res_resume = await client.post("/api/v1/screen/resume")
        assert res_resume.status_code == 200
        assert res_resume.json()["status"] == "OBSERVING"
