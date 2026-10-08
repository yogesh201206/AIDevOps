"""
Custom exceptions for AI and OmniRoute integration.
"""

from typing import Optional


class AIException(Exception):
    """Base exception for all AI/OmniRoute operations."""

    def __init__(self, message: str, code: str = "AI_ERROR", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class AIUnavailableError(AIException):
    """Raised when OmniRoute or the underlying AI service is unreachable."""

    def __init__(self, message: str = "AI provider is unavailable. Verify that OmniRoute is running."):
        super().__init__(message, code="AI_UNAVAILABLE", status_code=503)


class AITimeoutError(AIException):
    """Raised when AI inference exceeds the configured timeout."""

    def __init__(self, message: str = "AI request timed out during analysis."):
        super().__init__(message, code="AI_TIMEOUT", status_code=504)


class AIRateLimitError(AIException):
    """Raised when OmniRoute or upstream provider rate limits the request."""

    def __init__(self, message: str = "AI provider rate limit exceeded. Please retry shortly."):
        super().__init__(message, code="AI_RATE_LIMITED", status_code=429)


class AIParseError(AIException):
    """Raised when AI output cannot be parsed into the required structured schema."""

    def __init__(self, message: str = "Failed to parse structured diagnostic report from AI response."):
        super().__init__(message, code="AI_PARSE_ERROR", status_code=502)


class AIClientError(AIException):
    """Raised on non-retryable client errors from OmniRoute."""

    def __init__(self, message: str, code: str = "AI_CLIENT_ERROR", status_code: int = 502):
        super().__init__(message, code=code, status_code=status_code)
