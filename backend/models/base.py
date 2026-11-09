from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List, Optional


class ModelProvider(ABC):
    """
    Abstract Model Provider Interface.
    All model integrations (NIM, local, mock) must implement this contract.

    Design contract:
    - generate() and stream() accept optional conversation `history` for multi-turn context.
    - Implementations MUST raise on hard failures — do not silently fall back.
    - analyze_image() raises on hard failures.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> str:
        """Generate a complete text response. Raises on failure."""
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens asynchronously. Raises on failure."""
        pass

    @abstractmethod
    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        model_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Analyze an image and return structured analysis. Raises on failure."""
        pass

    @abstractmethod
    def supports_tools(self) -> bool:
        """Check if provider supports tool calling."""
        pass

    @abstractmethod
    def supports_vision(self) -> bool:
        """Check if provider supports vision/multimodal input."""
        pass
