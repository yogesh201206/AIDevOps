"""
Pydantic schemas for Kubernetes Intelligence (Phase 5).

Defines structured evidence models compatible with the Phase 3 investigation pipeline
and Phase 4 Docker intelligence models.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class KubernetesComponent(str, Enum):
    """Kubernetes resource kind or architectural component that produced the evidence."""

    POD = "pod"
    DEPLOYMENT = "deployment"
    REPLICASET = "replicaset"
    SERVICE = "service"
    CONFIGMAP = "configmap"
    SECRET = "secret"
    PVC = "persistentvolumeclaim"
    INGRESS = "ingress"
    EVENT = "event"
    MANIFEST = "manifest"
    LOG = "log"
    CLUSTER = "cluster"
    UNKNOWN = "unknown"


class KubernetesSeverity(str, Enum):
    """Severity rating for Kubernetes evidence items."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class KubernetesEvidence(BaseModel):
    """Structured evidence item produced by Kubernetes intelligence analysis."""

    model_config = ConfigDict(from_attributes=True)

    source: str = Field(
        ...,
        description="Origin of evidence (e.g. 'Kubernetes Pod Status', 'Kubernetes Event', 'Manifest Analysis')",
    )
    component: KubernetesComponent = Field(
        ...,
        description="Kubernetes component or resource kind that produced this evidence",
    )
    resource_kind: str = Field(
        ...,
        description="Kubernetes API resource kind (e.g. 'Pod', 'Deployment', 'Service')",
    )
    resource_name: str = Field(
        ...,
        description="Name of the affected Kubernetes resource",
    )
    namespace: str = Field(
        default="default",
        description="Kubernetes namespace of the resource",
    )
    category: str = Field(
        ...,
        description="Diagnostic category (e.g. 'crash_loop_backoff', 'image_pull_backoff', 'progress_deadline_exceeded')",
    )
    severity: KubernetesSeverity = Field(
        ...,
        description="Severity rating for this evidence item",
    )
    message: str = Field(
        ...,
        description="Human-readable description of the identified condition or failure",
    )
    evidence: str = Field(
        ...,
        description="Raw supporting evidence text (status details, event message, manifest excerpt, log lines)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Evidence-based confidence score (0.0 to 1.0)",
    )
    probable_root_cause: Optional[str] = Field(
        None,
        description="Identified or inferred probable root cause",
    )
    suggested_fix: Optional[str] = Field(
        None,
        description="Recommended technical remediation for human review",
    )
    validation_steps: List[str] = Field(
        default_factory=list,
        description="Recommended verification checks before or after applying remediation",
    )
    uncertainties: List[str] = Field(
        default_factory=list,
        description="Missing information or ambiguities that prevent complete certainty",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured metadata (container name, restart count, exit code, etc.)",
    )


class KubernetesStatusResponse(BaseModel):
    """Health, connectivity, and configuration status of the Kubernetes cluster."""

    model_config = ConfigDict(from_attributes=True)

    installed: bool = Field(
        ...,
        description="Whether official Kubernetes Python client is installed",
    )
    configured: bool = Field(
        ...,
        description="Whether a valid kubeconfig file or in-cluster config is present",
    )
    connected: bool = Field(
        ...,
        description="Whether a read-only ping to the Kubernetes API server succeeded",
    )
    current_context: Optional[str] = Field(
        None,
        description="Active kubeconfig context name (sanitized, credentials excluded)",
    )
    cluster_name: Optional[str] = Field(
        None,
        description="Sanitized cluster identifier (credentials and sensitive endpoints excluded)",
    )
    server_version: Optional[str] = Field(
        None,
        description="Kubernetes API server GitVersion if reachable",
    )
    message: str = Field(
        ...,
        description="Descriptive status message or reason for unavailability",
    )
    read_only_mode: bool = Field(
        default=True,
        description="Guarantees read-only inspection safety mode",
    )


class KubernetesManifestAnalysisRequest(BaseModel):
    """Request payload for static Kubernetes YAML manifest analysis."""

    yaml_content: str = Field(
        ...,
        description="Raw Kubernetes YAML manifest content to analyze (single or multi-document)",
    )
    filename: Optional[str] = Field(
        None,
        description="Optional filename or path for context in diagnostic reports",
    )


class KubernetesResourceInspectionRequest(BaseModel):
    """Request payload for targeted read-only resource inspection against a live cluster."""

    namespace: str = Field(
        default="default",
        description="Kubernetes namespace to inspect",
    )
    resource_kind: str = Field(
        default="pod",
        description="Resource kind to inspect ('pod', 'deployment', 'replicaset', 'event')",
    )
    resource_name: Optional[str] = Field(
        None,
        description="Specific resource name to inspect (optional; if omitted, lists resources)",
    )
    include_logs: bool = Field(
        default=False,
        description="Whether to retrieve container logs for Pods (strictly bounded)",
    )
    container_name: Optional[str] = Field(
        None,
        description="Target container name within the Pod (optional)",
    )
    previous_logs: bool = Field(
        default=False,
        description="Whether to retrieve previous terminated container instance logs",
    )
    log_tail_lines: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum lines of log output to collect (capped at 500)",
    )


class KubernetesAnalysisRequest(BaseModel):
    """Composite request payload for Kubernetes Intelligence analysis."""

    manifest_content: Optional[str] = Field(
        None,
        description="Raw Kubernetes YAML manifest content for static analysis",
    )
    pod_status: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured Pod status dictionary (from API or fixture)",
    )
    deployment_status: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured Deployment status dictionary (from API or fixture)",
    )
    events: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of Kubernetes event objects or dictionaries",
    )
    logs: Optional[str] = Field(
        None,
        description="Container logs text to analyze for runtime errors",
    )
    namespace: Optional[str] = Field(
        None,
        description="Optional target namespace filter",
    )
    resource_name: Optional[str] = Field(
        None,
        description="Optional target resource name filter",
    )
    github_actions_log: Optional[str] = Field(
        None,
        description="GitHub Actions CI/CD log to correlate Kubernetes/kubectl errors from",
    )
    live_inspect: bool = Field(
        default=False,
        description="If True and cluster connected, inspect live resources for the target namespace/name",
    )


class KubernetesAnalysisResponse(BaseModel):
    """Response payload returned by the Kubernetes Intelligence analysis endpoint."""

    model_config = ConfigDict(from_attributes=True)

    evidence: List[KubernetesEvidence] = Field(
        default_factory=list,
        description="Structured Kubernetes evidence items",
    )
    summary: str = Field(
        default="",
        description="Human-readable executive summary of Kubernetes findings",
    )
    highest_severity: str = Field(
        default="info",
        description="Highest severity level observed across findings",
    )
    components_analyzed: List[str] = Field(
        default_factory=list,
        description="List of Kubernetes components analyzed",
    )
    cluster_status: Optional[KubernetesStatusResponse] = Field(
        None,
        description="Cluster connectivity status during analysis",
    )
    context_block: str = Field(
        default="",
        description="Sanitized formatted context block ready for AI investigation prompt injection",
    )
