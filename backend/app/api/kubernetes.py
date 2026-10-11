"""
Kubernetes Intelligence API Endpoints.

Provides REST endpoints to:
1. Check Kubernetes client installation and safe cluster connection status.
2. Analyze Kubernetes manifests, pod status, deployment status, events, and logs.
3. Perform static analysis on YAML manifests without requiring a cluster.
4. Safely inspect live cluster resources in strictly read-only mode.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, status

from app.services.kubernetes.exceptions import (
    KubernetesException,
    KubernetesUnavailableError,
)
from app.services.kubernetes.kubernetes_service import KubernetesService
from app.services.kubernetes.schemas import (
    KubernetesAnalysisRequest,
    KubernetesAnalysisResponse,
    KubernetesEvidence,
    KubernetesManifestAnalysisRequest,
    KubernetesResourceInspectionRequest,
    KubernetesStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kubernetes", tags=["Kubernetes Intelligence"])


def get_kubernetes_service() -> KubernetesService:
    return KubernetesService()


@router.get(
    "/status",
    response_model=KubernetesStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Kubernetes cluster availability status",
    description=(
        "Safely checks if the Kubernetes client is installed, whether a kubeconfig is present, "
        "and tests read-only connectivity to the active cluster context. "
        "Never exposes credentials, certificates, or tokens."
    ),
)
async def get_kubernetes_status(
    service: KubernetesService = Depends(get_kubernetes_service),
) -> KubernetesStatusResponse:
    """Read-only safe cluster status check."""
    return service.check_connection_status()


@router.post(
    "/analyze",
    response_model=KubernetesAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Kubernetes resources, manifests, events, and logs",
    description=(
        "Analyzes provided Kubernetes artifacts (manifests, pod statuses, deployment rollouts, "
        "events, and logs) for failures, misconfigurations, and root causes. "
        "Returns structured KubernetesEvidence items."
    ),
)
async def analyze_kubernetes(
    request: KubernetesAnalysisRequest,
    service: KubernetesService = Depends(get_kubernetes_service),
) -> KubernetesAnalysisResponse:
    """Analyze Kubernetes state and artifacts for runtime failures and misconfigurations."""
    return service.analyze(request)


@router.post(
    "/manifests/analyze",
    response_model=List[KubernetesEvidence],
    status_code=status.HTTP_200_OK,
    summary="Perform static analysis on Kubernetes YAML manifests",
    description=(
        "Parses and validates Kubernetes YAML manifests without requiring a live cluster. "
        "Detects syntax errors, missing fields, selector mismatches, deprecated APIs, "
        "and misconfigurations. Never outputs raw secret values."
    ),
)
async def analyze_manifests(
    request: KubernetesManifestAnalysisRequest,
    service: KubernetesService = Depends(get_kubernetes_service),
) -> List[KubernetesEvidence]:
    """Static analysis for Kubernetes YAML manifests."""
    return service.manifest_analyzer.analyze(
        yaml_content=request.yaml_content,
        filename=request.filename,
    )


@router.post(
    "/resources/inspect",
    response_model=List[KubernetesEvidence],
    status_code=status.HTTP_200_OK,
    summary="Targeted read-only inspection of live cluster resources",
    description=(
        "Queries live cluster resources in strictly read-only mode (get/list/log). "
        "Requires connected cluster. If unconfigured or unreachable, returns 503."
    ),
)
async def inspect_live_resources(
    request: KubernetesResourceInspectionRequest,
    service: KubernetesService = Depends(get_kubernetes_service),
) -> List[KubernetesEvidence]:
    """Targeted read-only resource inspection against live cluster."""
    return service.inspect_resources_live(request)
