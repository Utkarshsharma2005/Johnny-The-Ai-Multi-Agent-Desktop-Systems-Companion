from fastapi import APIRouter
from backend.core.config import settings
from backend.core.secrets_loader import nim_api_key_configured

router = APIRouter(prefix="/api/v1", tags=["Health"])

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": "Johnny Backend Service",
        "version": "0.1.0",
        "provider": settings.MODEL_PROVIDER,
        "keys_configured": nim_api_key_configured(),
        "mock_only": settings.MODEL_PROVIDER != "nim" or not nim_api_key_configured(),
        "models": {
            "chat": settings.LLAMA_MODEL_ID,
            "vision": settings.MINIMAX_MODEL_ID,
            "coding": settings.DEEPSEEK_MODEL_ID,
            "planning": settings.NEMOTRON_MODEL_ID
        }
    }
