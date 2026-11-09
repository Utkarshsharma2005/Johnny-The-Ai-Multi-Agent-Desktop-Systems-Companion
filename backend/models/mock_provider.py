import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.models.base import ModelProvider


class MockProvider(ModelProvider):
    """
    Deterministic Mock Model Provider for testing and offline development.
    Conforms to the updated base interface including history parameter.
    """

    async def generate(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> str:
        ctx = f" (context: {len(history)} prior turns)" if history else ""
        return f"[Mock {model_id or 'Llama-3.3-70B'}]{ctx} Woof! I processed: '{prompt}'"

    async def stream(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        ctx = f" ({len(history)} turns of context)" if history else ""
        response = (
            f"[Mock {model_id or 'Llama-3.3-70B'}]{ctx} "
            f"Woof! Johnny here. Received: '{prompt}'. Running in mock mode!"
        )
        for word in response.split(" "):
            await asyncio.sleep(0.03)
            yield word + " "

    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        model_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.05)
        return {
            "status": "success",
            "model_used": model_id or "minimax/minimax-m3",
            "image_path": image_path,
            "analysis_raw": f"[Mock Vision] Analysis of '{image_path}': code editor, terminal, pixel dog detected.",
            "latency_ms": 50.0,
        }

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True
