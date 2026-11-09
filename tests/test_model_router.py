from backend.models.router import ModelRouter
from backend.models.mock_provider import MockProvider
from backend.core.config import settings

def test_model_router_intent_resolution():
    router = ModelRouter(provider_type="mock")
    assert isinstance(router.get_provider(), MockProvider)

    assert router.resolve_model_id("chat") == settings.LLAMA_MODEL_ID
    assert router.resolve_model_id("vision") == settings.MINIMAX_MODEL_ID
    assert router.resolve_model_id("code") == settings.DEEPSEEK_MODEL_ID
    assert router.resolve_model_id("planning") == settings.NEMOTRON_MODEL_ID
