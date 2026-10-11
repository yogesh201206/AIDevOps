"""
Pydantic schemas for Docker Intelligence (Phase 4).

Defines structured evidence models compatible with the existing Phase 3
investigation pipeline schemas.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DockerComponent(str, Enum):
    """Docker system component that produced the evidence."""

    DOCKERFILE = "dockerfile"
    BUILD = "build"
    IMAGE = "image"
    CONTAINER = "container"
    COMPOSE = "compose"
    RUNTIME = "runtime"
    UNKNOWN = "unknown"


class DockerSeverity(str, Enum):
    """Severity rating for a Docker evidence item."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DockerEvidence(BaseModel):
    """Structured evidence item produced by Docker intelligence analysis."""

    model_config = ConfigDict(from_attributes=True)

    source: str = Field(
        ...,
        description="Evidence source label (e.g. 'Docker Build', 'Dockerfile', 'Docker Container')",
    )
    component: DockerComponent = Field(
        ...,
        description="Docker component that produced this evidence",
    )
    category: str = Field(
        ...,
        description="Short category label (e.g. 'image_pull_failure', 'copy_failed')",
    )
    severity: DockerSeverity = Field(
        ...,
        description="Severity rating for this evidence item",
    )
    message: str = Field(
        ...,
        description="Human-readable description of the problem",
    )
    evidence: str = Field(
        ...,
        description="Raw evidence text (log lines, file excerpt, etc.) supporting the finding",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this finding (0.0 to 1.0)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured metadata (image reference, stage name, etc.)",
    )


class DockerAnalysisRequest(BaseModel):
    """Request payload for the Docker analysis endpoint."""

    dockerfile_content: Optional[str] = Field(
        None,
        description="Raw text content of the Dockerfile to analyze",
    )
    build_log: Optional[str] = Field(
        None,
        description="Docker build log output to analyze",
    )
    compose_content: Optional[str] = Field(
        None,
        description="Raw text content of docker-compose.yml to analyze",
    )
    container_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Container diagnostic data (from docker inspect or similar)",
    )
    container_logs: Optional[str] = Field(
        None,
        description="Container stdout/stderr log output to analyze",
    )
    image_reference: Optional[str] = Field(
        None,
        description="Docker image reference string to validate (e.g. 'myapp:latest')",
    )
    github_actions_log: Optional[str] = Field(
        None,
        description="GitHub Actions workflow log to correlate Docker evidence against",
    )


class DockerAnalysisResponse(BaseModel):
    """Response from the Docker intelligence analysis endpoint."""

    model_config = ConfigDict(from_attributes=True)

    evidence: List[DockerEvidence] = Field(
        default_factory=list,
        description="Structured Docker evidence findings",
    )
    summary: str = Field(
        default="",
        description="Human-readable summary of all Docker findings",
    )
    highest_severity: str = Field(
        default="info",
        description="Highest severity across all evidence items",
    )
    components_analyzed: List[str] = Field(
        default_factory=list,
        description="List of Docker components that were analyzed",
    )
    context_block: str = Field(
        default="",
        description="Formatted context block ready for injection into the AI investigation prompt",
    )
