from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.core.verification_engine import verification_engine

router = APIRouter(prefix="/api/v1/verification", tags=["Verification"])

class VerificationRequest(BaseModel):
    checks: Optional[List[str]] = Field(None, description="List of checks: LINT, UNIT_TEST, HEALTH_CHECK")
    target_path: Optional[str] = Field(".", description="Target directory path for verification")

@router.post("/verify")
async def run_verification(req: Optional[VerificationRequest] = None):
    """
    Executes automated linting, unit testing, health check verification suite.
    """
    checks = req.checks if req else None
    target_path = req.target_path if req else "."
    result = verification_engine.run_full_verification(checks=checks, target_path=target_path)
    return result
