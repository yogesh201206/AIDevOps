"""
GitHub integration exceptions.

Structured exception hierarchy for all GitHub API interactions.
Each exception provides a standard error code and HTTP status code
for clean FastAPI error responses.
"""

from typing import Any, Dict, Optional


class GitHubException(Exception):
    """Base exception for all GitHub-related errors."""

    def __init__(
        self,
        message: str = "GitHub API error",
        code: str = "GITHUB_API_ERROR",
        status_code: int = 502,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class GitHubNotConfiguredError(GitHubException):
    """Raised when GitHub token is not configured."""

    def __init__(self, message: str = "GitHub token is not configured"):
        super().__init__(
            message=message,
            code="GITHUB_NOT_CONFIGURED",
            status_code=400,
        )


class GitHubAuthenticationError(GitHubException):
    """Raised when GitHub returns 401 Unauthorized."""

    def __init__(self, message: str = "GitHub authentication failed"):
        super().__init__(
            message=message,
            code="GITHUB_AUTH_ERROR",
            status_code=401,
        )


class GitHubPermissionError(GitHubException):
    """Raised when GitHub returns 403 Forbidden (not rate-limited)."""

    def __init__(self, message: str = "GitHub permission denied"):
        super().__init__(
            message=message,
            code="GITHUB_FORBIDDEN",
            status_code=403,
        )


class GitHubNotFoundError(GitHubException):
    """Raised when a GitHub repository, branch, run or resource is not found (404)."""

    def __init__(self, message: str = "GitHub resource not found"):
        super().__init__(
            message=message,
            code="GITHUB_NOT_FOUND",
            status_code=404,
        )


class GitHubValidationError(GitHubException):
    """Raised when GitHub returns 422 Unprocessable Entity."""

    def __init__(self, message: str = "GitHub validation error"):
        super().__init__(
            message=message,
            code="GITHUB_VALIDATION_ERROR",
            status_code=422,
        )


class GitHubRateLimitError(GitHubException):
    """Raised when GitHub returns 429 or 403 Rate Limit Exceeded."""

    def __init__(self, message: str = "GitHub API rate limit exceeded"):
        super().__init__(
            message=message,
            code="GITHUB_RATE_LIMITED",
            status_code=429,
        )


class GitHubServerError(GitHubException):
    """Raised when GitHub returns 5xx server error."""

    def __init__(self, message: str = "GitHub upstream server error"):
        super().__init__(
            message=message,
            code="GITHUB_SERVER_ERROR",
            status_code=502,
        )


class GitHubTimeoutError(GitHubException):
    """Raised when a request to GitHub times out."""

    def __init__(self, message: str = "GitHub request timed out"):
        super().__init__(
            message=message,
            code="GITHUB_TIMEOUT",
            status_code=504,
        )


class GitHubNetworkError(GitHubException):
    """Raised when a network failure occurs while connecting to GitHub."""

    def __init__(self, message: str = "Failed to connect to GitHub API"):
        super().__init__(
            message=message,
            code="GITHUB_NETWORK_ERROR",
            status_code=503,
        )
