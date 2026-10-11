"""
Kubernetes Pod Intelligence Analyzer.

Analyzes Kubernetes Pod status, container states, and conditions to detect:
- Pending status and unschedulable states
- CrashLoopBackOff
- ImagePullBackOff / ErrImagePull
- CreateContainerConfigError / CreateContainerError
- OOMKilled containers
- ContainerCreating for prolonged periods
- Failed volume mounts
- Probe failures (readiness / liveness)
- Application startup failures
- Restart count analysis (strictly distinguishing single count from recurrence trends)

Clearly distinguishes confirmed API facts from likely causes and unknown causes.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.services.kubernetes.schemas import (
    KubernetesComponent,
    KubernetesEvidence,
    KubernetesSeverity,
)

logger = logging.getLogger(__name__)


class PodAnalyzer:
    """Specialized analyzer for Kubernetes Pod runtime state and container status."""

    def analyze(
        self,
        pod_data: Dict[str, Any],
        pod_events: Optional[List[Dict[str, Any]]] = None,
    ) -> List[KubernetesEvidence]:
        """
        Analyze pod structure (dict representation of Pod object or status).
        """
        findings: List[KubernetesEvidence] = []
        if not pod_data or not isinstance(pod_data, dict):
            return findings

        # Extract metadata
        metadata = pod_data.get("metadata", {})
        pod_name = metadata.get("name") or pod_data.get("name") or "unknown-pod"
        namespace = metadata.get("namespace") or pod_data.get("namespace") or "default"

        # Extract status & spec
        status = pod_data.get("status", {})
        spec = pod_data.get("spec", {})
        phase = status.get("phase", "Unknown")

        # 1. Analyze Pod Phase: Pending
        if phase == "Pending":
            findings.extend(self._analyze_pending_pod(pod_name, namespace, status, pod_events))

        # 2. Analyze Container Statuses
        container_statuses = status.get("containerStatuses", [])
        init_container_statuses = status.get("initContainerStatuses", [])

        for cs in init_container_statuses:
            findings.extend(
                self._analyze_container_status(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_status=cs,
                    is_init=True,
                    pod_events=pod_events,
                    pod_created_at=metadata.get("creationTimestamp"),
                )
            )

        for cs in container_statuses:
            findings.extend(
                self._analyze_container_status(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_status=cs,
                    is_init=False,
                    pod_events=pod_events,
                    pod_created_at=metadata.get("creationTimestamp"),
                )
            )

        # 3. Analyze Pod Conditions (e.g. PodScheduled, Ready, ContainersReady)
        conditions = status.get("conditions", [])
        for cond in conditions:
            c_type = cond.get("type")
            c_status = cond.get("status")
            c_reason = cond.get("reason", "")
            c_message = cond.get("message", "")

            if c_type == "PodScheduled" and c_status == "False":
                # Already partially handled in pending, but capture explicit condition
                if c_reason == "Unschedulable":
                    is_resource = any(
                        kw in c_message.lower()
                        for kw in ["insufficient cpu", "insufficient memory", "insufficient", "nodes"]
                    )
                    findings.append(
                        KubernetesEvidence(
                            source="Kubernetes Pod Conditions",
                            component=KubernetesComponent.POD,
                            resource_kind="Pod",
                            resource_name=pod_name,
                            namespace=namespace,
                            category="insufficient_resources" if is_resource else "failed_scheduling",
                            severity=KubernetesSeverity.HIGH,
                            message=f"Pod scheduling failed: {c_reason}",
                            evidence=f"Condition PodScheduled=False | Reason: {c_reason} | Message: {c_message}",
                            confidence=0.95,
                            probable_root_cause=f"Cluster nodes cannot schedule pod: {c_message}",
                            suggested_fix="Adjust pod resource requests or add/scale cluster worker node capacity.",
                            validation_steps=[
                                f"kubectl describe pod {pod_name} -n {namespace}",
                                "kubectl top nodes",
                            ],
                            uncertainties=[],
                            metadata={"condition": c_type, "reason": c_reason, "message": c_message},
                        )
                    )

            elif c_type == "ContainersReady" and c_status == "False" and phase == "Running":
                # Running pod with ContainersReady=False indicates readiness probe failure or container crash
                if any(kw in c_message.lower() for kw in ["readiness probe", "probe failed"]):
                    findings.append(
                        KubernetesEvidence(
                            source="Kubernetes Pod Conditions",
                            component=KubernetesComponent.POD,
                            resource_kind="Pod",
                            resource_name=pod_name,
                            namespace=namespace,
                            category="readiness_probe_failed",
                            severity=KubernetesSeverity.HIGH,
                            message=f"Pod containers failed readiness checks in namespace '{namespace}'",
                            evidence=f"Condition ContainersReady=False: {c_message}",
                            confidence=0.92,
                            probable_root_cause="Readiness probe endpoint returned unhealthy status or timed out.",
                            suggested_fix="Check container application readiness endpoint and increase initialDelaySeconds or timeoutSeconds if app takes longer to boot.",
                            validation_steps=[
                                f"kubectl describe pod {pod_name} -n {namespace}",
                                f"kubectl logs {pod_name} -n {namespace}",
                            ],
                            uncertainties=["Application internal logs required to determine why readiness check failed"],
                            metadata={"condition": c_type, "message": c_message},
                        )
                    )

        return findings

    def _analyze_pending_pod(
        self,
        pod_name: str,
        namespace: str,
        status: Dict[str, Any],
        pod_events: Optional[List[Dict[str, Any]]] = None,
    ) -> List[KubernetesEvidence]:
        findings: List[KubernetesEvidence] = []
        conditions = status.get("conditions", [])

        # Check conditions for Unschedulable
        unschedulable_cond = next(
            (c for c in conditions if c.get("type") == "PodScheduled" and c.get("reason") == "Unschedulable"),
            None,
        )

        # Check relevant events
        event_msgs = []
        if pod_events:
            for ev in pod_events:
                reason = ev.get("reason", "")
                msg = ev.get("message", "")
                if reason in {"FailedScheduling", "FailedMount", "FailedAttachVolume"}:
                    event_msgs.append(f"{reason}: {msg}")

        evidence_str = ""
        if unschedulable_cond:
            evidence_str = f"Condition: {unschedulable_cond.get('message', 'Pod is unschedulable')}"
        if event_msgs:
            evidence_str += (" | " if evidence_str else "") + "Events: " + "; ".join(event_msgs)

        if not evidence_str:
            evidence_str = f"Pod '{pod_name}' is in Pending phase with no schedule confirmation"

        is_resource_pressure = any(
            kw in evidence_str.lower()
            for kw in ["insufficient cpu", "insufficient memory", "insufficient pods", "nodes are available"]
        )
        is_volume_mount = any(
            kw in evidence_str.lower()
            for kw in ["mountvolume.setup failed", "failedmount", "pvc", "volume"]
        )

        category = "pending_unschedulable"
        if is_resource_pressure:
            category = "insufficient_resources"
        elif is_volume_mount:
            category = "failed_volume_mount"

        findings.append(
            KubernetesEvidence(
                source="Kubernetes Pod Status",
                component=KubernetesComponent.POD,
                resource_kind="Pod",
                resource_name=pod_name,
                namespace=namespace,
                category=category,
                severity=KubernetesSeverity.HIGH,
                message=f"Pod is stuck in Pending state in namespace '{namespace}' ({category.replace('_', ' ')})",
                evidence=evidence_str,
                confidence=0.90 if (unschedulable_cond or event_msgs) else 0.70,
                probable_root_cause=(
                    "Cluster nodes lack sufficient CPU/Memory resources to schedule pod"
                    if is_resource_pressure
                    else "Pod cannot be scheduled or volume cannot be attached"
                    if is_volume_mount
                    else "Pod is waiting for scheduler assignment or dependencies"
                ),
                suggested_fix=(
                    "Verify node resource availability with 'kubectl top nodes' and reduce pod resource requests."
                    if is_resource_pressure
                    else "Check PVC status and storage driver availability."
                    if is_volume_mount
                    else f"Inspect scheduling events with 'kubectl describe pod {pod_name} -n {namespace}'."
                ),
                validation_steps=[
                    f"kubectl describe pod {pod_name} -n {namespace}",
                    "kubectl get events -n " + namespace + " --sort-by='.metadata.creationTimestamp'",
                ],
                uncertainties=[] if (unschedulable_cond or event_msgs) else [
                    "No scheduler event details attached; cluster events needed to confirm exact bottleneck"
                ],
                metadata={"phase": "Pending", "category": category},
            )
        )
        return findings

    def _analyze_container_status(
        self,
        pod_name: str,
        namespace: str,
        container_status: Dict[str, Any],
        is_init: bool = False,
        pod_events: Optional[List[Dict[str, Any]]] = None,
        pod_created_at: Optional[str] = None,
    ) -> List[KubernetesEvidence]:
        findings: List[KubernetesEvidence] = []
        c_name = container_status.get("name", "container")
        image = container_status.get("image", "unknown")
        restart_count = container_status.get("restartCount", 0)
        state = container_status.get("state", {})
        last_state = container_status.get("lastState", {})

        # Inspect Waiting State
        waiting = state.get("waiting")
        if waiting:
            reason = waiting.get("reason", "")
            message = waiting.get("message", "")

            # 1. CrashLoopBackOff
            if reason == "CrashLoopBackOff":
                # Check lastState for terminated exitCode and reason
                last_term = last_state.get("terminated", {})
                exit_code = last_term.get("exitCode")
                term_reason = last_term.get("reason", "Error")

                evidence_text = f"Container '{c_name}' in CrashLoopBackOff. Restart count: {restart_count}."
                if exit_code is not None:
                    evidence_text += f" Last exit code: {exit_code} ({term_reason})."
                if message:
                    evidence_text += f" State message: {message}"

                # Handle restart count trend note
                uncertainties = [
                    "Single observation snapshot: cannot infer recurrence frequency trend without historical time-series data."
                ]
                if exit_code is None:
                    uncertainties.append("Last termination exit code and logs not recorded in status object.")

                probable_cause = (
                    f"Application process exited with non-zero exit code ({exit_code})."
                    if exit_code is not None
                    else "Container process terminated unexpectedly and Kubernetes is backing off restarts."
                )
                if term_reason == "OOMKilled" or exit_code == 137:
                    probable_cause = "Container was terminated by Linux kernel due to Out-Of-Memory (OOMKilled)."

                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Container Status",
                        component=KubernetesComponent.POD,
                        resource_kind="Pod",
                        resource_name=pod_name,
                        namespace=namespace,
                        category="crash_loop_backoff",
                        severity=KubernetesSeverity.CRITICAL,
                        message=f"Container '{c_name}' is in CrashLoopBackOff (exit code: {exit_code if exit_code is not None else 'unknown'})",
                        evidence=evidence_text,
                        confidence=0.95,
                        probable_root_cause=probable_cause,
                        suggested_fix="Inspect previous container logs (`kubectl logs --previous`) to diagnose application startup crash or unhandled exception.",
                        validation_steps=[
                            f"kubectl logs {pod_name} -c {c_name} -n {namespace} --previous",
                            f"kubectl describe pod {pod_name} -n {namespace}",
                        ],
                        uncertainties=uncertainties,
                        metadata={
                            "container": c_name,
                            "is_init": is_init,
                            "restart_count": restart_count,
                            "exit_code": exit_code,
                            "last_termination_reason": term_reason,
                            "image": image,
                        },
                    )
                )

            # 2. ImagePullBackOff & ErrImagePull
            elif reason in {"ImagePullBackOff", "ErrImagePull"}:
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Container Status",
                        component=KubernetesComponent.POD,
                        resource_kind="Pod",
                        resource_name=pod_name,
                        namespace=namespace,
                        category="image_pull_backoff" if reason == "ImagePullBackOff" else "err_image_pull",
                        severity=KubernetesSeverity.HIGH,
                        message=f"Container '{c_name}' failed to pull image '{image}': {reason}",
                        evidence=f"Container state waiting reason: {reason}. Message: {message or 'Pull failed'}. Image: {image}",
                        confidence=0.95,
                        probable_root_cause=f"Kubernetes kubelet cannot retrieve image '{image}'. Check registry repository existence, tag spelling, or imagePullSecrets authentication.",
                        suggested_fix=f"Verify that image '{image}' exists in container registry and cluster has valid pull credentials configured via imagePullSecrets.",
                        validation_steps=[
                            f"docker pull {image}  # (test locally or in CI)",
                            f"kubectl get secret -n {namespace}",
                            f"kubectl describe pod {pod_name} -n {namespace}",
                        ],
                        uncertainties=[] if message else ["Detailed registry error message not included in status"],
                        metadata={"container": c_name, "image": image, "reason": reason, "message": message},
                    )
                )

            # 3. CreateContainerConfigError & CreateContainerError
            elif reason in {"CreateContainerConfigError", "CreateContainerError"}:
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Container Status",
                        component=KubernetesComponent.POD,
                        resource_kind="Pod",
                        resource_name=pod_name,
                        namespace=namespace,
                        category="create_container_config_error",
                        severity=KubernetesSeverity.HIGH,
                        message=f"Container '{c_name}' configuration error: {reason}",
                        evidence=f"Container state waiting reason: {reason}. Details: {message or 'Missing ConfigMap or Secret'}",
                        confidence=0.93,
                        probable_root_cause=f"Required ConfigMap, Secret, or volume referenced in container spec does not exist or has invalid keys: {message}",
                        suggested_fix="Check all ConfigMaps, Secrets, and volume mounts referenced in the Pod spec to ensure they exist and have matching keys.",
                        validation_steps=[
                            f"kubectl get configmap,secret -n {namespace}",
                            f"kubectl describe pod {pod_name} -n {namespace}",
                        ],
                        uncertainties=[],
                        metadata={"container": c_name, "reason": reason, "message": message},
                    )
                )

            # 4. ContainerCreating for prolonged period
            elif reason == "ContainerCreating":
                is_prolonged = False
                duration_msg = ""
                if pod_created_at:
                    try:
                        created_dt = datetime.fromisoformat(pod_created_at.replace("Z", "+00:00"))
                        elapsed_seconds = (datetime.now(timezone.utc) - created_dt).total_seconds()
                        if elapsed_seconds > 300:  # > 5 minutes
                            is_prolonged = True
                            duration_msg = f"Pod created {int(elapsed_seconds)} seconds ago and still in ContainerCreating."
                    except Exception:
                        pass

                # Also check events for volume attach / network errors
                c_events = []
                if pod_events:
                    for ev in pod_events:
                        r = ev.get("reason", "")
                        if r in {"FailedMount", "FailedAttachVolume", "NetworkPluginNotReady"}:
                            c_events.append(f"{r}: {ev.get('message', '')}")
                            is_prolonged = True

                if is_prolonged:
                    findings.append(
                        KubernetesEvidence(
                            source="Kubernetes Container Status",
                            component=KubernetesComponent.POD,
                            resource_kind="Pod",
                            resource_name=pod_name,
                            namespace=namespace,
                            category="container_creating_prolonged",
                            severity=KubernetesSeverity.HIGH,
                            message=f"Container '{c_name}' stuck in ContainerCreating state",
                            evidence=f"Container in ContainerCreating. {duration_msg} " + ("; ".join(c_events) if c_events else ""),
                            confidence=0.88,
                            probable_root_cause="Volume mount, network interface setup, or CNI attachment is hanging or failed.",
                            suggested_fix="Inspect volume attachment and CNI plugin status with 'kubectl describe pod'.",
                            validation_steps=[
                                f"kubectl describe pod {pod_name} -n {namespace}",
                                f"kubectl get pvc -n {namespace}",
                            ],
                            uncertainties=["Requires node and kubelet logs to confirm CNI or CSI driver status"],
                            metadata={"container": c_name, "duration_note": duration_msg},
                        )
                    )

        # Inspect Terminated State
        terminated = state.get("terminated")
        if terminated:
            t_reason = terminated.get("reason", "")
            t_exit_code = terminated.get("exitCode", 0)
            t_message = terminated.get("message", "")

            # OOMKilled
            if t_reason == "OOMKilled" or t_exit_code == 137:
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Container Status",
                        component=KubernetesComponent.POD,
                        resource_kind="Pod",
                        resource_name=pod_name,
                        namespace=namespace,
                        category="oom_killed",
                        severity=KubernetesSeverity.CRITICAL,
                        message=f"Container '{c_name}' was OOMKilled (Exit Code 137)",
                        evidence=f"Terminated reason: {t_reason}, Exit code: {t_exit_code}. Message: {t_message or 'Exceeded memory limit'}",
                        confidence=0.98,
                        probable_root_cause="Container memory consumption exceeded configured 'resources.limits.memory' or node memory was exhausted.",
                        suggested_fix="Increase container memory limit in pod spec ('resources.limits.memory') or optimize memory consumption within the application.",
                        validation_steps=[
                            f"kubectl top pod {pod_name} -n {namespace}",
                            f"kubectl describe pod {pod_name} -n {namespace}",
                        ],
                        uncertainties=[],
                        metadata={"container": c_name, "exit_code": t_exit_code, "reason": t_reason},
                    )
                )

        # Inspect Restart Count (when NOT in active CrashLoopBackOff)
        if restart_count > 0 and not any(f.category == "crash_loop_backoff" for f in findings):
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Container Status",
                    component=KubernetesComponent.POD,
                    resource_kind="Pod",
                    resource_name=pod_name,
                    namespace=namespace,
                    category="restart_count_elevated",
                    severity=KubernetesSeverity.MEDIUM if restart_count < 5 else KubernetesSeverity.HIGH,
                    message=f"Container '{c_name}' has restarted {restart_count} time(s)",
                    evidence=f"Observed restartCount={restart_count} for container '{c_name}'. Container currently in state: {list(state.keys())[0] if state else 'unknown'}",
                    confidence=0.75,
                    probable_root_cause="Container process previously exited or failed liveness probe, triggering kubelet container restart.",
                    suggested_fix=f"Review previous logs (`kubectl logs {pod_name} -c {c_name} --previous`) to analyze past crashes.",
                    validation_steps=[
                        f"kubectl logs {pod_name} -c {c_name} -n {namespace} --previous",
                    ],
                    uncertainties=[
                        "Single observation snapshot: does not indicate whether restarts are increasing or recurring without time-series metrics"
                    ],
                    metadata={"container": c_name, "restart_count": restart_count},
                )
            )

        return findings
