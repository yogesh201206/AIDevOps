"""
GitHub API HTTP Client.

Provides a robust, reusable async HTTP client for interacting with the GitHub REST API.
Handles authentication, error normalization, rate limiting, and timeouts securely.
Ensures tokens are never logged or leaked in error messages.
"""

import logging
from typing import Any, Dict, Optional
import httpx

from app.config import settings
from app.github.exceptions import (
    GitHubAuthenticationError,
    GitHubException,
    GitHubNetworkError,
    GitHubNotConfiguredError,
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
    GitHubServerError,
    GitHubTimeoutError,
    GitHubValidationError,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0
GITHUB_API_VERSION = "2022-11-28"


class GitHubClient:
    """Reusable asynchronous GitHub REST API client."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.token = token or settings.GITHUB_TOKEN
        self.base_url = (base_url or settings.GITHUB_API_URL).rstrip("/")
        self.timeout = timeout
        self._external_client = client is not None
        self._client: Optional[httpx.AsyncClient] = client

    @property
    def is_configured(self) -> bool:
        """Return True if a GitHub token is configured."""
        return bool(self.token and self.token.strip())

    def _get_headers(self, accept: str = "application/vnd.github+json") -> Dict[str, str]:
        """Construct secure headers without leaking secrets."""
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": f"AI-DevOps-Agent/{settings.APP_VERSION}",
        }
        if self.is_configured:
            headers["Authorization"] = f"Bearer {self.token.strip()}"
        return headers

    async def get_http_client(self) -> httpx.AsyncClient:
        """Return the shared httpx.AsyncClient instance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client if managed internally."""
        if not self._external_client and self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _handle_http_error(self, response: httpx.Response) -> None:
        """Map HTTP error status codes to typed GitHubException subclasses."""
        status = response.status_code
        try:
            body = response.json()
            message = body.get("message", response.text) if isinstance(body, dict) else response.text
        except Exception:
            message = response.text or f"HTTP {status}"

        # Truncate overly long error messages
        if len(message) > 500:
            message = message[:500] + "..."

        # Check rate limiting indicators
        rate_limit_remaining = response.headers.get("x-ratelimit-remaining")
        is_rate_limited = (
            status == 429
            or (status == 403 and rate_limit_remaining == "0")
            or "rate limit" in message.lower()
        )

        if is_rate_limited:
            raise GitHubRateLimitError(
                message=f"GitHub API rate limit exceeded: {message}"
            )

        if status == 401:
            raise GitHubAuthenticationError(
                message="GitHub authentication failed. Check your GITHUB_TOKEN."
            )
        elif status == 403:
            raise GitHubPermissionError(
                message=f"GitHub permission denied: {message}"
            )
        elif status == 404:
            raise GitHubNotFoundError(
                message=f"GitHub resource not found: {message}"
            )
        elif status == 422:
            raise GitHubValidationError(
                message=f"GitHub validation error: {message}"
            )
        elif status >= 500:
            raise GitHubServerError(
                message=f"GitHub server error ({status}): {message}"
            )
        else:
            raise GitHubException(
                message=f"GitHub API error ({status}): {message}",
                status_code=status,
            )

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        accept: str = "application/vnd.github+json",
        require_auth: bool = True,
    ) -> httpx.Response:
        """
        Execute an HTTP request against GitHub API.
        Does not log headers or auth tokens.
        """
        if require_auth and not self.is_configured:
            raise GitHubNotConfiguredError()

        url = endpoint if endpoint.startswith("http") else f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers(accept=accept)
        client = await self.get_http_client()

        # Clean params of None values
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}

        logger.debug(
            "GitHub API request: method=%s url=%s params=%s",
            method,
            endpoint,
            clean_params,
        )

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=clean_params,
                json=json_data,
            )
        except httpx.TimeoutException as exc:
            logger.warning("GitHub API timeout on %s %s", method, endpoint)
            raise GitHubTimeoutError(f"Request to GitHub timed out: {str(exc)}") from exc
        except httpx.RequestError as exc:
            logger.warning("GitHub API network error on %s %s", method, endpoint)
            raise GitHubNetworkError(f"Network error connecting to GitHub: {str(exc)}") from exc

        if response.is_error:
            self._handle_http_error(response)

        return response

    async def get_json(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        require_auth: bool = True,
    ) -> Any:
        """Send a GET request and parse JSON response."""
        response = await self.request(
            method="GET",
            endpoint=endpoint,
            params=params,
            require_auth=require_auth,
        )
        return response.json()

    async def get_raw(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        accept: str = "application/vnd.github+json",
        require_auth: bool = True,
    ) -> httpx.Response:
        """Send a GET request and return the raw Response object."""
        return await self.request(
            method="GET",
            endpoint=endpoint,
            params=params,
            accept=accept,
            require_auth=require_auth,
        )
