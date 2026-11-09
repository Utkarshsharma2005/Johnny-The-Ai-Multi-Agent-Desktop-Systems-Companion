import time
from enum import Enum
from typing import Dict, Any, Optional
from PIL import Image

from backend.perception.screen_capture import DesktopScreenCapturer
from backend.perception.change_detector import ScreenChangeDetector, ScreenDiffResult
from backend.perception.privacy import privacy_manager, ScreenObservationStatus
from backend.models.router import ModelRouter

class ObservationMode(str, Enum):
    AMBIENT = "AMBIENT"
    ATTENTIVE = "ATTENTIVE"
    TASK = "TASK"
    PAUSED = "PAUSED"

class EscalationLevel(int, Enum):
    LEVEL_0_CAPTURE = 0      # Local Frame Capture
    LEVEL_1_DIFF = 1         # Change Detection
    LEVEL_2_METADATA = 2     # Local Metadata & Layout
    LEVEL_3_VISION = 3       # Vision Model Escalation (MiniMax M3)

class ScreenEscalationEngine:
    """
    Orchestrates continuous screen observation using a 4-tier escalation policy.
    Ensures expensive LLM vision calls only occur when meaningful visual changes occur.
    """

    MODE_CONFIGS: Dict[ObservationMode, Dict[str, Any]] = {
        ObservationMode.AMBIENT: {
            "interval_seconds": 5.0,
            "diff_threshold": 0.05,
            "description": "Low-cost passive desktop monitoring"
        },
        ObservationMode.ATTENTIVE: {
            "interval_seconds": 1.5,
            "diff_threshold": 0.02,
            "description": "Active observation following user prompt"
        },
        ObservationMode.TASK: {
            "interval_seconds": 1.0,
            "diff_threshold": 0.01,
            "description": "Focused continuous task monitoring"
        },
        ObservationMode.PAUSED: {
            "interval_seconds": 0.0,
            "diff_threshold": 1.0,
            "description": "Screen observation paused"
        }
    }

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()
        self._mode: ObservationMode = ObservationMode.AMBIENT
        self._previous_frame: Optional[Image.Image] = None
        self._last_capture_time: float = 0.0
        self._last_escalation_level: EscalationLevel = EscalationLevel.LEVEL_0_CAPTURE
        self._last_diff_score: float = 0.0
        self._last_screen_summary: str = "No screen captures recorded yet."
        self._active_window: str = "Johnny Desktop Environment"
        self._total_captures: int = 0
        self._total_escalations: int = 0  # Number of Level 3 MiniMax vision calls

    @property
    def mode(self) -> ObservationMode:
        return self._mode

    def set_mode(self, mode: ObservationMode) -> str:
        self._mode = mode
        if mode == ObservationMode.PAUSED:
            privacy_manager.pause()
        else:
            if privacy_manager.is_paused:
                privacy_manager.resume()
        return f"Observation mode updated to {mode.value}"

    def process_screen_cycle(self, force_escalate: bool = False, prompt_context: str = "") -> Dict[str, Any]:
        """
        Executes one observation cycle following the 4-tier escalation policy:
        Level 0 -> Level 1 -> Level 2 -> Level 3
        """
        # Check global privacy pause
        if privacy_manager.is_paused or self._mode == ObservationMode.PAUSED:
            return {
                "status": ScreenObservationStatus.PAUSED.value,
                "mode": ObservationMode.PAUSED.value,
                "escalation_level": EscalationLevel.LEVEL_0_CAPTURE.value,
                "diff_score": 0.0,
                "summary": "Screen observation is PAUSED",
                "message": "Observation paused for user privacy."
            }

        # Check window privacy exclusion
        if privacy_manager.is_window_excluded(self._active_window):
            return {
                "status": "EXCLUDED",
                "mode": self._mode.value,
                "escalation_level": EscalationLevel.LEVEL_0_CAPTURE.value,
                "diff_score": 0.0,
                "summary": f"Window '{self._active_window}' is excluded by privacy policy.",
                "message": "Excluded window active."
            }

        start_time = time.time()
        self._total_captures += 1

        # ----------------------------------------------------
        # LEVEL 0: Local Screen Capture
        # ----------------------------------------------------
        success, cap_msg, frame = DesktopScreenCapturer.capture_frame()
        if not success or frame is None:
            return {
                "status": "CAPTURE_ERROR",
                "mode": self._mode.value,
                "escalation_level": EscalationLevel.LEVEL_0_CAPTURE.value,
                "diff_score": 0.0,
                "summary": f"Failed to capture screen: {cap_msg}",
                "message": cap_msg
            }

        # ----------------------------------------------------
        # LEVEL 1: Local Change Detection
        # ----------------------------------------------------
        mode_threshold = self.MODE_CONFIGS[self._mode]["diff_threshold"]
        diff_res: ScreenDiffResult = ScreenChangeDetector.compute_diff(
            current_frame=frame,
            previous_frame=self._previous_frame,
            threshold=mode_threshold
        )
        self._last_diff_score = diff_res.diff_score

        # Update previous frame for next cycle
        self._previous_frame = frame.copy()
        self._last_capture_time = start_time

        # If no meaningful change and escalation not explicitly forced, stop at Level 1
        if not diff_res.has_changed and not force_escalate:
            self._last_escalation_level = EscalationLevel.LEVEL_1_DIFF
            return {
                "status": ScreenObservationStatus.OBSERVING.value,
                "mode": self._mode.value,
                "escalation_level": EscalationLevel.LEVEL_1_DIFF.value,
                "diff_score": diff_res.diff_score,
                "summary": self._last_screen_summary,
                "message": diff_res.description,
                "total_captures": self._total_captures,
                "total_escalations": self._total_escalations
            }

        # ----------------------------------------------------
        # LEVEL 2: Local Layout & Metadata Extraction
        # ----------------------------------------------------
        dhash = ScreenChangeDetector.compute_dhash(frame)
        width, height = frame.size
        local_layout_desc = f"Screen resolution {width}x{height}, visual hash {dhash}, diff score {diff_res.diff_score:.4f}"
        
        # ----------------------------------------------------
        # LEVEL 3: Vision Model Escalation (MiniMax M3)
        # ----------------------------------------------------
        # Only invoke expensive model if diff is significant or forced
        self._total_escalations += 1
        self._last_escalation_level = EscalationLevel.LEVEL_3_VISION

        vision_prompt = (
            f"Analyze this desktop screenshot compact state. "
            f"Identify active applications, text changes, or key visual elements. "
            f"Context: {prompt_context or 'Desktop continuous observation'}. "
            f"Keep summary concise."
        )

        try:
            # Route to MiniMax M3 Vision provider via ModelRouter
            vision_result = self.model_router.analyze_image(
                image_input=frame,
                prompt=vision_prompt,
                intent="vision"
            )
            
            if vision_result and vision_result.get("text"):
                self._last_screen_summary = vision_result["text"]
            else:
                self._last_screen_summary = f"Visual change detected ({local_layout_desc})"
        except Exception as e:
            self._last_screen_summary = f"Visual change detected ({local_layout_desc}). Vision fallback: {str(e)}"

        return {
            "status": ScreenObservationStatus.OBSERVING.value,
            "mode": self._mode.value,
            "escalation_level": EscalationLevel.LEVEL_3_VISION.value,
            "diff_score": diff_res.diff_score,
            "summary": self._last_screen_summary,
            "message": "Level 3 Vision Escalation triggered",
            "total_captures": self._total_captures,
            "total_escalations": self._total_escalations,
            "timestamp": self._last_capture_time
        }

    def get_state(self) -> Dict[str, Any]:
        """Returns the lightweight current screen intelligence state."""
        return {
            "status": privacy_manager.status.value,
            "mode": self._mode.value,
            "last_escalation_level": self._last_escalation_level.value,
            "last_diff_score": self._last_diff_score,
            "screen_summary": self._last_screen_summary,
            "active_window": self._active_window,
            "total_captures": self._total_captures,
            "total_escalations": self._total_escalations,
            "mode_config": self.MODE_CONFIGS[self._mode]
        }

# Global singleton escalation engine
escalation_engine = ScreenEscalationEngine()
