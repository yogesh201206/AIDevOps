"""
Docker Intelligence Service package.

Phase 4: Provides read-only Docker diagnostics for the AI DevOps investigation
pipeline. Supports Dockerfile analysis, build log parsing, image reference
validation, container diagnostics, and Docker Compose analysis.

No Docker daemon is required for static analysis. Safe runtime inspection
methods use a restricted allowlist of read-only commands.
"""

from app.services.docker.compose_analyzer import DockerComposeAnalyzer
from app.services.docker.container_analyzer import ContainerAnalyzer
from app.services.docker.docker_service import DockerService
from app.services.docker.dockerfile_analyzer import DockerfileAnalyzer
from app.services.docker.exceptions import (
    DockerCommandError,
    DockerCommandForbiddenError,
    DockerException,
    DockerNotAvailableError,
    DockerParseError,
    DockerTimeoutError,
)
from app.services.docker.image_analyzer import DockerImageAnalyzer
from app.services.docker.log_analyzer import DockerLogAnalyzer
from app.services.docker.safe_executor import SafeDockerExecutor
from app.services.docker.schemas import (
    DockerAnalysisRequest,
    DockerAnalysisResponse,
    DockerComponent,
    DockerEvidence,
    DockerSeverity,
)

__all__ = [
    "DockerService",
    "DockerfileAnalyzer",
    "DockerLogAnalyzer",
    "DockerImageAnalyzer",
    "ContainerAnalyzer",
    "DockerComposeAnalyzer",
    "SafeDockerExecutor",
    "DockerAnalysisRequest",
    "DockerAnalysisResponse",
    "DockerComponent",
    "DockerEvidence",
    "DockerSeverity",
    "DockerException",
    "DockerParseError",
    "DockerCommandError",
    "DockerCommandForbiddenError",
    "DockerTimeoutError",
    "DockerNotAvailableError",
]
