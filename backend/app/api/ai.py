"""
AI provider status endpoint.
"""

from fastapi import APIRouter, Depends

from app.services.ai.ai_service import AIService
from app.services.investigation.schemas import AIStatusResponse

router = APIRouter(prefix="/ai", tags=["AI Provider"])


def get_ai_service() -> AIService:
    return AIService()


@router.get(
    "/status",
    response_model=AIStatusResponse,
    summary="Check AI provider health and status",
    description="Check whether OmniRoute or the configured AI provider is operational.",
)
async def get_ai_status(
    service: AIService = Depends(get_ai_service),
) -> AIStatusResponse:
    """Return connectivity and configuration status for the AI provider."""
    return await service.get_status()
