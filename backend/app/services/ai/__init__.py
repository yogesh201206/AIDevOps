"""
AI service module for OmniRoute integration and LLM analysis.
"""

from app.services.ai.ai_service import AIService
from app.services.ai.exceptions import (
    AIClientError,
    AIException,
    AIParseError,
    AIRateLimitError,
    AITimeoutError,
    AIUnavailableError,
)
from app.services.ai.omniroute_client import OmniRouteClient
from app.services.ai.parser import AIOutputSchema, parse_ai_response
from app.services.ai.prompts import (
    DEVOPS_INVESTIGATOR_SYSTEM_PROMPT,
    USER_INVESTIGATION_PROMPT_TEMPLATE,
)

__all__ = [
    "AIService",
    "OmniRouteClient",
    "AIOutputSchema",
    "parse_ai_response",
    "DEVOPS_INVESTIGATOR_SYSTEM_PROMPT",
    "USER_INVESTIGATION_PROMPT_TEMPLATE",
    "AIException",
    "AIUnavailableError",
    "AITimeoutError",
    "AIRateLimitError",
    "AIParseError",
    "AIClientError",
]
