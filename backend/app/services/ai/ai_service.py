"""
AI Service layer.

High-level business service orchestrating OmniRoute client communication,
prompt composition, and response parsing.
"""

import logging
from typing import Optional

from app.config import settings
from app.services.ai.omniroute_client import OmniRouteClient
from app.services.ai.parser import AIOutputSchema, parse_ai_response
from app.services.ai.prompts import (
    DEVOPS_INVESTIGATOR_SYSTEM_PROMPT,
    USER_INVESTIGATION_PROMPT_TEMPLATE,
)
from app.services.investigation.schemas import AIStatusResponse

logger = logging.getLogger(__name__)


class AIService:
    """Service encapsulating AI-driven DevOps analysis and OmniRoute connectivity."""

    def __init__(self, client: Optional[OmniRouteClient] = None):
        self.client = client or OmniRouteClient()

    async def get_status(self) -> AIStatusResponse:
        """
        Check AI provider configuration and connectivity status.
        Does not raise exceptions; returns graceful status even if unavailable.
        """
        configured = self.client.is_configured
        available = False
        if configured:
            available = await self.client.check_availability()

        model_name = settings.OMNIROUTE_MODEL or "gpt-4o-mini"
        return AIStatusResponse(
            configured=configured,
            available=available,
            provider="omniroute",
            model=model_name,
        )

    async def analyze_investigation_context(
        self,
        context: str,
        model: Optional[str] = None,
    ) -> AIOutputSchema:
        """
        Send investigation context to OmniRoute and parse the structured diagnosis.
        """
        user_prompt = USER_INVESTIGATION_PROMPT_TEMPLATE.format(context=context)
        messages = [
            {"role": "system", "content": DEVOPS_INVESTIGATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw_response = await self.client.create_chat_completion(
            messages=messages,
            model=model,
        )

        return parse_ai_response(raw_response)
