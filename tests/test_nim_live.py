import os
import pytest
from backend.models.nim_provider import NimProvider
from backend.core.config import settings

LIVE_NIM_KEY = os.environ.get("NIM_API_KEY") or os.environ.get("NVIDIA_API_KEY")
IS_LIVE_NIM_CONFIGURED = bool(LIVE_NIM_KEY and not LIVE_NIM_KEY.startswith("nvapi-your-key") and not LIVE_NIM_KEY == "nvapi-placeholder")

pytestmark = pytest.mark.skipif(
    not IS_LIVE_NIM_CONFIGURED or os.environ.get("MODEL_PROVIDER") == "mock",
    reason="NIM API Key not set in environment or running in mock provider mode."
)

@pytest.mark.asyncio
async def test_live_nim_llama_generate():
    provider = NimProvider(api_key=LIVE_NIM_KEY)
    response = await provider.generate("Say 'Hello from Llama 3.3 70B' in 5 words.", model_id=settings.LLAMA_MODEL_ID)
    assert response is not None
    assert len(response) > 0

@pytest.mark.asyncio
async def test_live_nim_llama_stream():
    provider = NimProvider(api_key=LIVE_NIM_KEY)
    tokens = []
    async for chunk in provider.stream("Count 1 2 3", model_id=settings.LLAMA_MODEL_ID):
        tokens.append(chunk)
    assert len(tokens) > 0
    text = "".join([c[1] if isinstance(c, (tuple, list)) else c for c in tokens])
    assert text.strip() != ""
