from typing import Optional
from backend.models.base import ModelProvider
from backend.models.nim_provider import NimProvider
from backend.models.mock_provider import MockProvider
from backend.core.config import settings

class ModelRouter:
    """
    Centralized Model Router for selecting providers and model identifiers based on intent.
    """

    def __init__(self, provider_type: Optional[str] = None):
        self._build(provider_type)

    def _build(self, provider_type: Optional[str] = None):
        self.provider_type = (provider_type or settings.MODEL_PROVIDER).lower()
        if self.provider_type == "nim":
            self.provider: ModelProvider = NimProvider()
        else:
            self.provider: ModelProvider = MockProvider()

    def refresh(self):
        """Rebuild provider from current settings (used after live key setup)."""
        self._build()

    def get_provider(self) -> ModelProvider:
        return self.provider

    def resolve_model_id(self, task_type: str) -> str:
        task_lower = task_type.lower()
        if "vision" in task_lower or "image" in task_lower:
            return settings.MINIMAX_MODEL_ID
        elif "code" in task_lower or "debug" in task_lower:
            return settings.DEEPSEEK_MODEL_ID
        elif "plan" in task_lower:
            return settings.NEMOTRON_MODEL_ID
        else:
            return settings.LLAMA_MODEL_ID

# Global router instance
router_instance = ModelRouter()
