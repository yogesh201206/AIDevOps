"""
Docker Intelligence custom exceptions.

Provides structured exception hierarchy for all Docker-related
analysis operations in Phase 4.
"""


class DockerException(Exception):
    """Base exception for all Docker intelligence operations."""

    def __init__(
        self,
        message: str = "Docker intelligence error",
        code: str = "DOCKER_ERROR",
        status_code: int = 500,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class DockerParseError(DockerException):
    """Raised when a Dockerfile or Compose file cannot be parsed."""

    def __init__(self, message: str = "Failed to parse Docker configuration file"):
        super().__init__(message, code="DOCKER_PARSE_ERROR", status_code=400)


class DockerCommandError(DockerException):
    """Raised when a safe Docker CLI command fails to execute."""

    def __init__(self, message: str = "Docker command execution failed"):
        super().__init__(message, code="DOCKER_COMMAND_ERROR", status_code=500)


class DockerCommandForbiddenError(DockerException):
    """Raised when a requested Docker command is not on the allowlist."""

    def __init__(self, message: str = "Docker command is not permitted in read-only mode"):
        super().__init__(message, code="DOCKER_FORBIDDEN", status_code=403)


class DockerTimeoutError(DockerException):
    """Raised when a Docker CLI command exceeds its time limit."""

    def __init__(self, message: str = "Docker command timed out"):
        super().__init__(message, code="DOCKER_TIMEOUT", status_code=504)


class DockerNotAvailableError(DockerException):
    """Raised when the Docker daemon is not reachable."""

    def __init__(self, message: str = "Docker daemon is not available"):
        super().__init__(message, code="DOCKER_UNAVAILABLE", status_code=503)
