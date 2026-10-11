"""
Kubernetes Intelligence Core Service.

Main orchestration service for Phase 5 Kubernetes Intelligence:
- Connection and environment detection (graceful handling of missing/unreachable clusters)
- Safe, read-only cluster inspection (never mutates or executes shell commands)
- Coordinates Pod, Deployment, Event, Log, and Manifest analyzers
- Correlates CI/CD logs with Kubernetes error patterns
- Generates structured KubernetesEvidence, executive summaries, and AI-ready context blocks
- Strict security: Never logs or exposes credentials, tokens, or kubeconfig secrets
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.config import settings
from app.services.kubernetes.deployment_analyzer import DeploymentAnalyzer
from app.services.kubernetes.event_analyzer import EventAnalyzer
from app.services.kubernetes.exceptions import (
    KubernetesAuthError,
    KubernetesCommandForbiddenError,
    KubernetesConfigError,
    KubernetesException,
    KubernetesResourceNotFoundError,
    KubernetesTimeoutError,
    KubernetesUnavailableError,
)
from app.services.kubernetes.log_analyzer import KubernetesLogAnalyzer
from app.services.kubernetes.manifest_analyzer import KubernetesManifestAnalyzer
from app.services.kubernetes.pod_analyzer import PodAnalyzer
from app.services.kubernetes.schemas import (
    KubernetesAnalysisRequest,
    KubernetesAnalysisResponse,
    KubernetesComponent,
    KubernetesEvidence,
    KubernetesResourceInspectionRequest,
    KubernetesSeverity,
    KubernetesStatusResponse,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {
    KubernetesSeverity.INFO: 0,
    KubernetesSeverity.LOW: 1,
    KubernetesSeverity.MEDIUM: 2,
    KubernetesSeverity.HIGH: 3,
    KubernetesSeverity.CRITICAL: 4,
}


class KubernetesService:
    """Facade service orchestrating all Kubernetes Intelligence capabilities."""

    def __init__(
        self,
        pod_analyzer: Optional[PodAnalyzer] = None,
        deployment_analyzer: Optional[DeploymentAnalyzer] = None,
        event_analyzer: Optional[EventAnalyzer] = None,
        log_analyzer: Optional[KubernetesLogAnalyzer] = None,
        manifest_analyzer: Optional[KubernetesManifestAnalyzer] = None,
    ):
        self.pod_analyzer = pod_analyzer or PodAnalyzer()
        self.deployment_analyzer = deployment_analyzer or DeploymentAnalyzer()
        self.event_analyzer = event_analyzer or EventAnalyzer()
        self.log_analyzer = log_analyzer or KubernetesLogAnalyzer()
        self.manifest_analyzer = manifest_analyzer or KubernetesManifestAnalyzer()

        # Cache client state
        self._k8s_client_available = self._detect_kubernetes_package()

    def _detect_kubernetes_package(self) -> bool:
        """Check if official kubernetes Python client library is importable."""
        try:
            import kubernetes  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_kubeconfig_path(self) -> Optional[str]:
        """Locate configured or default kubeconfig file path."""
        # 1. Explicit setting or env
        cfg_path = getattr(settings, "KUBECONFIG", None) or os.getenv("KUBECONFIG")
        if cfg_path and os.path.isfile(cfg_path):
            return cfg_path

        # 2. Default ~/.kube/config
        default_path = os.path.expanduser("~/.kube/config")
        if os.path.isfile(default_path):
            return default_path

        return None

    def check_connection_status(self) -> KubernetesStatusResponse:
        """
        Safely check Kubernetes support and connectivity without crashing.
        Never exposes sensitive tokens, certs, or internal IP addresses.
        """
        if not self._k8s_client_available:
            return KubernetesStatusResponse(
                installed=False,
                configured=False,
                connected=False,
                current_context=None,
                cluster_name=None,
                server_version=None,
                message="Official Kubernetes Python client is not installed in the current environment.",
                read_only_mode=True,
            )

        kubeconfig_path = self._get_kubeconfig_path()
        if not kubeconfig_path:
            return KubernetesStatusResponse(
                installed=True,
                configured=False,
                connected=False,
                current_context=None,
                cluster_name=None,
                server_version=None,
                message="No kubeconfig found at $KUBECONFIG or ~/.kube/config. Kubernetes Intelligence operating in static-analysis mode.",
                read_only_mode=True,
            )

        # Attempt to inspect current context safely without mutating
        try:
            from kubernetes import client, config
            from kubernetes.config.config_exception import ConfigException

            contexts, active_context = config.list_kube_config_contexts(config_file=kubeconfig_path)
            if not active_context:
                return KubernetesStatusResponse(
                    installed=True,
                    configured=True,
                    connected=False,
                    current_context=None,
                    cluster_name=None,
                    server_version=None,
                    message="Kubeconfig present but no active context is selected.",
                    read_only_mode=True,
                )

            context_name = active_context.get("name", "unknown")
            cluster_raw = active_context.get("context", {}).get("cluster", "unknown")
            safe_cluster_name = self._sanitize_cluster_name(cluster_raw)

            # Try a lightweight, strictly read-only version check
            try:
                config.load_kube_config(config_file=kubeconfig_path)
                api_client = client.ApiClient()
                version_api = client.VersionApi(api_client)
                version_info = version_api.get_code(_request_timeout=getattr(settings, "KUBERNETES_TIMEOUT_SECONDS", 5.0))
                git_version = version_info.git_version if hasattr(version_info, "git_version") else "unknown"

                return KubernetesStatusResponse(
                    installed=True,
                    configured=True,
                    connected=True,
                    current_context=context_name,
                    cluster_name=safe_cluster_name,
                    server_version=git_version,
                    message=f"Connected to Kubernetes cluster '{safe_cluster_name}' in read-only mode.",
                    read_only_mode=True,
                )
            except Exception as conn_err:
                err_str = str(conn_err)
                logger.warning("Kubernetes cluster ping failed: %s", err_str[:120])
                msg = f"Kubeconfig loaded for context '{context_name}', but cluster is unreachable or timed out."
                if "Unauthorized" in err_str or "401" in err_str:
                    msg = f"Kubernetes authentication failed for context '{context_name}' (401 Unauthorized)."
                elif "Forbidden" in err_str or "403" in err_str:
                    msg = f"Kubernetes authorization failed for context '{context_name}' (403 Forbidden)."

                return KubernetesStatusResponse(
                    installed=True,
                    configured=True,
                    connected=False,
                    current_context=context_name,
                    cluster_name=safe_cluster_name,
                    server_version=None,
                    message=msg,
                    read_only_mode=True,
                )

        except Exception as exc:
            logger.warning("Failed to parse kubeconfig: %s", str(exc)[:120])
            return KubernetesStatusResponse(
                installed=True,
                configured=True,
                connected=False,
                current_context=None,
                cluster_name=None,
                server_version=None,
                message="Error reading kubeconfig structure.",
                read_only_mode=True,
            )

    def _sanitize_cluster_name(self, raw_cluster: str) -> str:
        """Sanitizes cluster URL or identifier to avoid leaking internal hostnames or tokens."""
        if not raw_cluster:
            return "unnamed-cluster"
        if raw_cluster.startswith(("http://", "https://")):
            parsed = urlparse(raw_cluster)
            # Return safe hostname or IP without port/credentials
            host = parsed.hostname or "cluster-endpoint"
            return f"cluster-{host}"
        return raw_cluster.split("/")[-1]

    def analyze(self, request: KubernetesAnalysisRequest) -> KubernetesAnalysisResponse:
        """
        Execute comprehensive Kubernetes analysis on provided inputs (manifest, pod status,
        deployment status, events, logs, or CI/CD logs).
        """
        all_evidence: List[KubernetesEvidence] = []
        components_analyzed: List[str] = []

        # 1. Manifest analysis (static, cluster not required)
        if request.manifest_content:
            components_analyzed.append("manifest")
            manifest_findings = self.manifest_analyzer.analyze(
                yaml_content=request.manifest_content,
                filename="submitted-manifest.yaml",
            )
            all_evidence.extend(manifest_findings)

        # 2. Pod status analysis
        if request.pod_status:
            components_analyzed.append("pod")
            pod_findings = self.pod_analyzer.analyze(
                pod_data=request.pod_status,
                pod_events=request.events,
            )
            all_evidence.extend(pod_findings)

        # 3. Deployment status analysis
        if request.deployment_status:
            components_analyzed.append("deployment")
            dep_findings = self.deployment_analyzer.analyze(
                deployment_data=request.deployment_status,
                deployment_events=request.events,
            )
            all_evidence.extend(dep_findings)

        # 4. Events analysis
        if request.events and not request.pod_status and not request.deployment_status:
            # If events were provided without being absorbed into pod/deployment
            components_analyzed.append("event")
            event_findings = self.event_analyzer.analyze(
                events=request.events,
                target_namespace=request.namespace,
                target_resource_name=request.resource_name,
            )
            all_evidence.extend(event_findings)

        # 5. Log analysis
        if request.logs:
            components_analyzed.append("log")
            log_findings = self.log_analyzer.analyze(
                logs=request.logs,
                pod_name=request.resource_name,
                namespace=request.namespace,
            )
            all_evidence.extend(log_findings)

        # 6. CI/CD / GitHub Actions log correlation
        if request.github_actions_log:
            gh_findings = self.correlate_github_log(request.github_actions_log)
            if gh_findings:
                if "github_actions" not in components_analyzed:
                    components_analyzed.append("github_actions")
                all_evidence.extend(gh_findings)

        # 7. Optional Live Inspection (strictly read-only)
        cluster_status = self.check_connection_status()
        if request.live_inspect:
            if not cluster_status.connected:
                all_evidence.append(
                    KubernetesEvidence(
                        source="Kubernetes Cluster Diagnostic",
                        component=KubernetesComponent.CLUSTER,
                        resource_kind="Cluster",
                        resource_name="live-cluster",
                        namespace=request.namespace or "default",
                        category="cluster_unavailable",
                        severity=KubernetesSeverity.LOW,
                        message="Live cluster inspection skipped: " + cluster_status.message,
                        evidence=cluster_status.message,
                        confidence=1.0,
                        probable_root_cause="Cluster is disconnected or unconfigured.",
                        suggested_fix="Ensure a valid kubeconfig is present and cluster endpoint is reachable.",
                        validation_steps=[],
                        uncertainties=[],
                    )
                )
            else:
                # Perform read-only query
                components_analyzed.append("live_cluster")
                live_findings = self._inspect_live_resource(
                    namespace=request.namespace or "default",
                    resource_name=request.resource_name,
                )
                all_evidence.extend(live_findings)

        # Determine highest severity
        highest_sev = KubernetesSeverity.INFO
        for ev in all_evidence:
            if SEVERITY_ORDER.get(ev.severity, 0) > SEVERITY_ORDER.get(highest_sev, 0):
                highest_sev = ev.severity

        summary = self._generate_summary(all_evidence, components_analyzed)
        context_block = self.build_context_block(all_evidence)

        return KubernetesAnalysisResponse(
            evidence=all_evidence,
            summary=summary,
            highest_severity=highest_sev.value,
            components_analyzed=components_analyzed,
            cluster_status=cluster_status,
            context_block=context_block,
        )

    def correlate_github_log(self, github_log: str) -> List[KubernetesEvidence]:
        """
        Scans GitHub Actions CI/CD logs for embedded kubectl errors, Helm deploy issues,
        or Kubernetes container crash signatures.
        """
        if not github_log or not github_log.strip():
            return []

        findings = self.log_analyzer.analyze(
            logs=github_log,
            pod_name="ci-pipeline",
            namespace="ci",
        )
        for f in findings:
            f.source = "GitHub Actions (Kubernetes Step)"

        return findings

    def inspect_resources_live(
        self,
        request: KubernetesResourceInspectionRequest,
    ) -> List[KubernetesEvidence]:
        """
        Execute targeted read-only resource inspection against a live cluster.
        Guarantees strictly read-only API calls.
        """
        status = self.check_connection_status()
        if not status.connected:
            raise KubernetesUnavailableError(
                f"Cannot inspect live resources: {status.message}"
            )

        return self._inspect_live_resource(
            namespace=request.namespace,
            resource_name=request.resource_name,
            resource_kind=request.resource_kind,
            include_logs=request.include_logs,
            container_name=request.container_name,
            previous_logs=request.previous_logs,
            log_tail_lines=request.log_tail_lines,
        )

    def _inspect_live_resource(
        self,
        namespace: str,
        resource_name: Optional[str] = None,
        resource_kind: str = "pod",
        include_logs: bool = False,
        container_name: Optional[str] = None,
        previous_logs: bool = False,
        log_tail_lines: int = 100,
    ) -> List[KubernetesEvidence]:
        """Read-only API queries to live Kubernetes cluster."""
        findings: List[KubernetesEvidence] = []
        try:
            from kubernetes import client

            core_v1 = client.CoreV1Api()
            apps_v1 = client.AppsV1Api()

            # Retrieve Pod(s)
            if resource_kind.lower() == "pod":
                if resource_name:
                    try:
                        pod = core_v1.read_namespaced_pod(name=resource_name, namespace=namespace)
                        pod_dict = client.ApiClient().sanitize_for_serialization(pod)
                        findings.extend(self.pod_analyzer.analyze(pod_dict))

                        if include_logs:
                            try:
                                logs = core_v1.read_namespaced_pod_log(
                                    name=resource_name,
                                    namespace=namespace,
                                    container=container_name,
                                    previous=previous_logs,
                                    tail_lines=min(log_tail_lines, 500),
                                    _request_timeout=getattr(settings, "KUBERNETES_TIMEOUT_SECONDS", 10.0),
                                )
                                if logs:
                                    findings.extend(
                                        self.log_analyzer.analyze(
                                            logs=logs,
                                            pod_name=resource_name,
                                            container_name=container_name,
                                            namespace=namespace,
                                        )
                                    )
                            except Exception as log_err:
                                logger.info("Could not read pod logs for %s: %s", resource_name, str(log_err)[:80])

                    except client.exceptions.ApiException as api_err:
                        if api_err.status == 404:
                            raise KubernetesResourceNotFoundError(f"Pod '{resource_name}' not found in namespace '{namespace}'")
                        elif api_err.status in {401, 403}:
                            raise KubernetesAuthError(f"Permission denied reading Pod in namespace '{namespace}': {api_err.reason}")
                        raise KubernetesException(f"Kubernetes API error: {api_err.reason}")
                else:
                    # List pods in namespace
                    pod_list = core_v1.list_namespaced_pod(namespace=namespace, limit=20)
                    for pod in pod_list.items:
                        pod_dict = client.ApiClient().sanitize_for_serialization(pod)
                        findings.extend(self.pod_analyzer.analyze(pod_dict))

            # Retrieve Deployment(s)
            elif resource_kind.lower() == "deployment":
                if resource_name:
                    try:
                        dep = apps_v1.read_namespaced_deployment(name=resource_name, namespace=namespace)
                        dep_dict = client.ApiClient().sanitize_for_serialization(dep)
                        findings.extend(self.deployment_analyzer.analyze(dep_dict))
                    except client.exceptions.ApiException as api_err:
                        if api_err.status == 404:
                            raise KubernetesResourceNotFoundError(f"Deployment '{resource_name}' not found in namespace '{namespace}'")
                        elif api_err.status in {401, 403}:
                            raise KubernetesAuthError(f"Permission denied reading Deployment: {api_err.reason}")
                        raise KubernetesException(f"Kubernetes API error: {api_err.reason}")
                else:
                    dep_list = apps_v1.list_namespaced_deployment(namespace=namespace, limit=20)
                    for dep in dep_list.items:
                        dep_dict = client.ApiClient().sanitize_for_serialization(dep)
                        findings.extend(self.deployment_analyzer.analyze(dep_dict))

        except (KubernetesException, KubernetesUnavailableError, KubernetesResourceNotFoundError, KubernetesAuthError):
            raise
        except Exception as exc:
            logger.error("Live inspection error: %s", str(exc))
            raise KubernetesException(f"Live Kubernetes inspection failed: {str(exc)}")

        return findings

    def _generate_summary(self, evidence: List[KubernetesEvidence], components: List[str]) -> str:
        """Create concise executive summary from collected evidence."""
        if not evidence:
            comp_str = ", ".join(components) if components else "submitted inputs"
            return f"Kubernetes intelligence analysis completed across {comp_str}. No Kubernetes defects or runtime failures were identified."

        critical_count = sum(1 for e in evidence if e.severity == KubernetesSeverity.CRITICAL)
        high_count = sum(1 for e in evidence if e.severity == KubernetesSeverity.HIGH)
        total = len(evidence)

        primary = evidence[0]
        return (
            f"Kubernetes analysis detected {total} finding(s) ({critical_count} critical, {high_count} high) "
            f"across {', '.join(components) if components else 'analyzed resources'}. "
            f"Primary issue: {primary.message}."
        )

    def build_context_block(self, evidence: List[KubernetesEvidence]) -> str:
        """
        Formats structured Kubernetes evidence for injection into the AI investigation context.
        """
        if not evidence:
            return ""

        lines = [
            "==================================================",
            "KUBERNETES INTELLIGENCE EVIDENCE (PHASE 5)",
            "==================================================",
            f"Total Findings: {len(evidence)}",
            "",
        ]

        for idx, ev in enumerate(evidence, 1):
            lines.append(f"[{idx}] Finding: {ev.message}")
            lines.append(f"    Resource: {ev.resource_kind}/{ev.resource_name} (Namespace: {ev.namespace})")
            lines.append(f"    Component: {ev.component.value} | Severity: {ev.severity.value.upper()} | Confidence: {ev.confidence:.2f}")
            lines.append(f"    Category: {ev.category}")
            if ev.probable_root_cause:
                lines.append(f"    Probable Root Cause: {ev.probable_root_cause}")
            if ev.suggested_fix:
                lines.append(f"    Suggested Fix: {ev.suggested_fix}")
            if ev.validation_steps:
                lines.append(f"    Validation Steps: {'; '.join(ev.validation_steps)}")
            if ev.uncertainties:
                lines.append(f"    Uncertainties: {'; '.join(ev.uncertainties)}")
            lines.append(f"    Evidence Excerpt:")
            for e_line in ev.evidence.splitlines()[:10]:
                lines.append(f"      {e_line}")
            lines.append("")

        lines.append("==================================================")
        return "\n".join(lines)
