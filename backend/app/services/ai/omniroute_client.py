"""
OmniRoute AI Client.

Provides OpenAI-compatible HTTP client abstraction for communicating with
OmniRoute or compatible LLM gateways.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.ai.exceptions import (
    AIClientError,
    AIRateLimitError,
    AITimeoutError,
    AIUnavailableError,
)

logger = logging.getLogger(__name__)


class OmniRouteClient:
    """Async client communicating with OmniRoute via OpenAI-compatible endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        raw_url = base_url if base_url is not None else settings.OMNIROUTE_BASE_URL
        self.base_url = raw_url.rstrip("/") if raw_url else ""
        self.api_key = api_key if api_key is not None else settings.OMNIROUTE_API_KEY
        self.timeout = float(timeout if timeout is not None else settings.OMNIROUTE_TIMEOUT)

    @property
    def is_configured(self) -> bool:
        """Return True if an OmniRoute base URL is configured."""
        return bool(self.base_url)

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key and self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        return headers

    async def check_availability(self, timeout_sec: float = 3.0) -> bool:
        """
        Perform a lightweight ping to the OmniRoute API (/models endpoint).
        Returns True if reachable and responding, False otherwise.
        Never raises exceptions.
        """
        if not self.is_configured:
            return False

        url = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                response = await client.get(url, headers=self._get_headers())
                # Any 2xx or 401 (service reachable, just needs auth) indicates server is running
                if response.status_code in {200, 204, 401}:
                    return True
                logger.debug("OmniRoute ping returned HTTP %s", response.status_code)
                return False
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError):
            logger.debug("OmniRoute unreachable at %s", url)
            return False
        except Exception as exc:
            logger.debug("OmniRoute availability check failed: %s", exc)
            return False

    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Send a chat completion request to OmniRoute.

        Returns raw assistant text message content.
        Raises AIUnavailableError, AITimeoutError, AIRateLimitError, or AIClientError.
        """
        if not self.is_configured:
            raise AIUnavailableError("OmniRoute base URL is not configured.")

        selected_model = model or settings.OMNIROUTE_MODEL or "gpt-4o-mini"
        selected_temp = (
            temperature if temperature is not None else settings.AI_TEMPERATURE
        )

        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": selected_temp,
            "max_tokens": 4096,
        }

        logger.info(
            "Sending AI investigation chat completion request | model=%s url=%s timeout=%.1fs",
            selected_model,
            url,
            self.timeout,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as exc:
            logger.warning("Failed to connect to OmniRoute: %s", exc)
            raise AIUnavailableError(
                "AI provider is unavailable. Verify that OmniRoute is running."
            ) from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
            logger.warning("OmniRoute request timed out: %s", exc)
            raise AITimeoutError("AI request timed out during analysis.") from exc
        except Exception as exc:
            logger.exception("Unexpected error connecting to OmniRoute: %s", exc)
            raise AIClientError(f"Network error communicating with AI provider: {str(exc)}") from exc

        # Handle HTTP status codes
        if response.status_code == 429:
            raise AIRateLimitError("AI provider rate limit exceeded. Please retry shortly.")

        if response.status_code in {401, 403}:
            raise AIClientError(
                "Authentication failed with AI provider. Verify OMNIROUTE_API_KEY.",
                code="AI_AUTH_ERROR",
                status_code=response.status_code,
            )

        if response.status_code >= 500:
            logger.error("OmniRoute returned server error %s: %s", response.status_code, response.text[:200])
            raise AIUnavailableError(
                f"OmniRoute service error ({response.status_code}). Verify provider status."
            )

        if response.status_code != 200:
            logger.error("OmniRoute error response %s: %s", response.status_code, response.text[:200])
            raise AIClientError(
                f"AI provider returned HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise AIClientError("AI provider returned no choices in completion response.")
            content = choices[0].get("message", {}).get("content", "")
            return content
        except Exception as exc:
            logger.warning("Failed to extract content from OmniRoute response: %s", exc)
            raise AIClientError(f"Invalid completion response payload: {str(exc)}") from exc
