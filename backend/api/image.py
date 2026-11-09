from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.perception.image_loader import LocalImageInspector
from backend.models.router import router_instance
from backend.telemetry.latency import LatencyTracker, async_measure_stage

router = APIRouter(prefix="/api/v1/image", tags=["Image"])

class ImageAnalyzeRequest(BaseModel):
    image_path: str
    prompt: Optional[str] = "Describe what you see in this screenshot or image in detail."

@router.post("/analyze")
async def analyze_image_endpoint(request: ImageAnalyzeRequest):
    tracker = LatencyTracker()
    tracker.start()

    # Step 1: Local Image Inspection & Security Check
    async with async_measure_stage(tracker, "tool"):
        valid, msg, metadata = LocalImageInspector.inspect_image_file(request.image_path)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)

    # Step 2: Route to Vision Model (MiniMax M3)
    async with async_measure_stage(tracker, "routing"):
        provider = router_instance.get_provider()
        model_id = router_instance.resolve_model_id("vision")

    # Step 3: Vision Analysis Execution
    async with async_measure_stage(tracker, "model"):
        analysis_result = await provider.analyze_image(
            image_path=request.image_path,
            prompt=request.prompt or "Analyze this image",
            model_id=model_id
        )

    telemetry = tracker.stop()
    return {
        "status": "success",
        "image_metadata": metadata,
        "vision_result": analysis_result,
        "telemetry": telemetry
    }
