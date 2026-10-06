"""
Health-check endpoints for /api/v1/health.

Provides two endpoints:
  GET /health        – liveness probe (is the process alive?)
  GET /health/ready  – readiness probe (is the app ready to serve traffic?)

In Phase 1, readiness reflects internal application state only.
Future phases will extend this to check GitHub API reachability,
AI provider connectivity, and database availability.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    summary="Liveness probe",
    response_description="Service liveness status",
)
async def health_liveness() -> Dict[str, Any]:
    """
    Liveness probe.

    Returns HTTP 200 with a 'healthy' status as long as the process
    is running. Kubernetes / Docker Compose use this to decide whether
    to restart a crashed container.
    """
    logger.debug("Liveness probe called")
    return {
        "status": "healthy",
        "service": "ai-devops-agent-backend",
    }


@router.get(
    "/ready",
    summary="Readiness probe",
    response_description="Service readiness status",
)
async def health_readiness() -> Dict[str, Any]:
    """
    Readiness probe.

    Returns HTTP 200 when the application is fully initialised and
    ready to handle requests. In Phase 1, readiness is identical to
    liveness. Future phases will add checks for:
      - GitHub API reachability
      - AI provider availability
      - Database connectivity
    """
    logger.debug("Readiness probe called")
    return {
        "status": "ready",
        "service": "ai-devops-agent-backend",
        "environment": settings.APP_ENV,
        "version": settings.APP_VERSION,
        "checks": {
            "application": "ok",
            # Future: "github_api": "ok" | "degraded" | "unavailable"
            # Future: "ai_provider": "ok" | "degraded" | "unavailable"
            # Future: "database": "ok" | "degraded" | "unavailable"
        },
    }
