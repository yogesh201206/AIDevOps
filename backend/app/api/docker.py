"""
Docker Intelligence API Endpoints.

Provides REST endpoints to analyze Dockerfile contents, build logs, compose files,
and container diagnostic data, as well as safe daemon status checks.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, status

from app.services.docker.docker_service import DockerService
from app.services.docker.schemas import (
    DockerAnalysisRequest,
    DockerAnalysisResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/docker", tags=["Docker Intelligence"])


def get_docker_service() -> DockerService:
    return DockerService()


@router.post(
    "/analyze",
    response_model=DockerAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Docker artifacts and evidence",
    description=(
        "Analyzes Dockerfiles, build logs, Docker Compose files, image references, "
        "and container diagnostics. Returns structured DockerEvidence and AI-ready context."
    ),
)
async def analyze_docker(
    request: DockerAnalysisRequest,
    service: DockerService = Depends(get_docker_service),
) -> DockerAnalysisResponse:
    """Analyze Docker assets for defects, misconfigurations, and runtime errors."""
    return service.analyze(request)


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Get Docker daemon availability status",
    description="Safely inspects if a local Docker daemon is reachable via read-only check.",
)
async def get_docker_status(
    service: DockerService = Depends(get_docker_service),
) -> Dict[str, Any]:
    """Check Docker daemon availability (read-only safe check)."""
    return await service.check_daemon_status()
