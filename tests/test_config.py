from backend.core.config import settings

def test_settings_defaults():
    assert bool(settings.LLAMA_MODEL_ID)
    assert bool(settings.MINIMAX_MODEL_ID)
    assert settings.MODEL_PROVIDER in ["nim", "mock"]
    assert settings.PORT == 8000
