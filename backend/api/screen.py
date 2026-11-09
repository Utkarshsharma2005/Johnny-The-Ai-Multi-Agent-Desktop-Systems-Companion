from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from backend.perception.escalation_engine import escalation_engine, ObservationMode
from backend.perception.privacy import privacy_manager

router = APIRouter(prefix="/api/v1/screen", tags=["screen-intelligence"])

class ModeUpdateRequest(BaseModel):
    mode: str = Field(..., description="Observation mode: AMBIENT, ATTENTIVE, TASK, PAUSED")

class ScreenCaptureRequest(BaseModel):
    force_escalate: bool = Field(False, description="Force Level 3 vision escalation regardless of diff threshold")
    prompt_context: str = Field("", description="Optional context prompt for vision analysis")

@router.get("/state")
async def get_screen_state():
    """
    Returns current lightweight screen observation state, mode, diff score, and summary.
    """
    return escalation_engine.get_state()

@router.post("/capture")
async def trigger_screen_capture(req: Optional[ScreenCaptureRequest] = None):
    """
    Triggers an immediate desktop frame capture & escalation evaluation.
    """
    force = req.force_escalate if req else False
    context = req.prompt_context if req else ""
    result = escalation_engine.process_screen_cycle(force_escalate=force, prompt_context=context)
    return result

@router.post("/mode")
async def update_screen_mode(req: ModeUpdateRequest):
    """
    Updates the current screen observation mode (AMBIENT, ATTENTIVE, TASK, PAUSED).
    """
    mode_str = req.mode.upper()
    try:
        new_mode = ObservationMode(mode_str)
        msg = escalation_engine.set_mode(new_mode)
        return {"status": "SUCCESS", "message": msg, "state": escalation_engine.get_state()}
    except ValueError:
        valid_modes = [m.value for m in ObservationMode]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid observation mode '{req.mode}'. Valid modes: {valid_modes}"
        )

@router.post("/pause")
async def pause_screen_observation():
    """
    Instantly pauses screen observation for privacy.
    """
    escalation_engine.set_mode(ObservationMode.PAUSED)
    return {"status": "PAUSED", "message": "Screen intelligence observation is PAUSED"}

@router.post("/resume")
async def resume_screen_observation():
    """
    Resumes screen observation in AMBIENT mode.
    """
    escalation_engine.set_mode(ObservationMode.AMBIENT)
    return {"status": "OBSERVING", "message": "Screen intelligence observation is ACTIVE"}


@router.post("/advise")
async def advise_screen_action():
    """
    FRIDAY-style screen intelligence:
    Captures the current active desktop screen, analyzes errors or active tasks
    via the multimodal VLM, and provides concrete recommended next actions.
    """
    import tempfile
    from backend.perception.screen_capture import DesktopScreenCapturer
    from backend.models.router import router_instance

    capturer = DesktopScreenCapturer()
    frame = capturer.capture()
    if not frame:
        raise HTTPException(status_code=500, detail="Failed to capture desktop screen")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        frame.save(tmp.name, format="PNG")
        tmp_path = tmp.name

    prompt = (
        "You are Johnny, an advanced desktop AI companion inspired by FRIDAY. "
        "Inspect this screen capture carefully. "
        "1. Summarize in 1-2 sentences what the user is working on or looking at. "
        "2. Note any errors, warnings, failed commands, or notable UI state. "
        "3. Provide exactly one concrete recommended next action Johnny should take."
    )

    try:
        provider = router_instance.get_provider()
        res = await provider.analyze_image(image_path=tmp_path, prompt=prompt)
        advice_text = res.get("content") or res.get("analysis_raw") or "Screen inspected cleanly."
        return {
            "status": "success",
            "resolution": f"{frame.width}x{frame.height}",
            "advice": advice_text,
            "telemetry": res.get("telemetry", {}),
        }
    except Exception as e:
        return {
            "status": "fallback",
            "resolution": f"{frame.width}x{frame.height}",
            "advice": f"I observed your screen ({frame.width}x{frame.height}). Active workspace ready for your command.",
            "error": str(e)
        }
    finally:
        try:
            import os
            os.remove(tmp_path)
        except OSError:
            pass

