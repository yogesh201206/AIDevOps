"""
Kubernetes Event Intelligence Analyzer.

Analyzes Kubernetes Events to identify common warnings and failures:
- FailedScheduling (resource pressure, taints, affinity)
- FailedMount / FailedAttachVolume (PVC, Secrets, ConfigMaps)
- BackOff (CrashLoopBackOff, container restart backoff)
- Unhealthy (readiness and liveness probe failures)
- FailedPull / ErrImagePull / ImagePullBackOff
- FailedCreate (quota limits, admission webhooks, forbidden resources)
- PersistentVolumeClaim binding issues

Security protections:
- Normalizes event data.
- Treats event messages as UNTRUSTED INPUT, defending against prompt injection.
- Secret redaction on event messages.
- Filters out unrelated cluster-wide events when scoping to target namespace/resource.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.investigation.log_processor import LogProcessor
from app.services.kubernetes.schemas import (
    KubernetesComponent,
    KubernetesEvidence,
    KubernetesSeverity,
)

logger = logging.getLogger(__name__)

# Malicious prompt injection / system override patterns to neutralize
PROMPT_INJECTION_PATTERN = re.compile(
    r"(?:ignore\s+previous\s+instructions|system\s+prompt|you\s+are\s+now|override\s+all\s+rules|"
    r"developer\s+mode|as\s+an\s+ai|act\s+as|forget\s+everything)",
    re.IGNORECASE,
)

CRITICAL_EVENT_REASONS = {
    "FailedScheduling",
    "FailedMount",
    "FailedAttachVolume",
    "BackOff",
    "Unhealthy",
    "FailedPull",
    "ErrImagePull",
    "ImagePullBackOff",
    "FailedCreate",
    "FailedBinding",
    "FailedSync",
    "NodeNotReady",
    "Preempting",
}


class EventAnalyzer:
    """Specialized analyzer for Kubernetes Events."""

    def sanitize_untrusted_message(self, message: str) -> str:
        """
        Sanitizes untrusted event message strings to prevent prompt injection
        and remove any accidental credentials.
        """
        if not message:
            return ""

        # Redact any embedded tokens or passwords
        clean = LogProcessor.redact_secrets(message)

        # Defend against prompt injection patterns by neutering them
        if PROMPT_INJECTION_PATTERN.search(clean):
            clean = PROMPT_INJECTION_PATTERN.sub("[UNTRUSTED_INJECTION_FILTERED]", clean)

        # Strip unprintable control characters
        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", clean)
        return clean.strip()

    def analyze(
        self,
        events: List[Dict[str, Any]],
        target_namespace: Optional[str] = None,
        target_resource_name: Optional[str] = None,
    ) -> List[KubernetesEvidence]:
        """
        Analyze a list of event objects or dictionaries.
        Filters by namespace and resource name when specified to avoid cluster noise.
        """
        findings: List[KubernetesEvidence] = []
        if not events or not isinstance(events, list):
            return findings

        for ev in events:
            if not isinstance(ev, dict):
                continue

            # Extract event fields (support both Kubernetes API Event objects and flat dicts)
            metadata = ev.get("metadata", {})
            namespace = (
                metadata.get("namespace")
                or ev.get("namespace")
                or ev.get("involvedObject", {}).get("namespace")
                or "default"
            )

            involved_obj = ev.get("involvedObject", {})
            resource_kind = involved_obj.get("kind") or ev.get("resource_kind") or "Unknown"
            resource_name = involved_obj.get("name") or ev.get("resource_name") or "unknown"

            # Filter out unrelated events if target filters are provided
            if target_namespace and namespace != target_namespace and namespace != "default":
                continue
            if target_resource_name and resource_name != target_resource_name:
                continue

            event_type = ev.get("type", "Normal")
            reason = ev.get("reason", "Unknown")
            raw_message = ev.get("message", "")
            count = ev.get("count", 1)
            first_timestamp = ev.get("firstTimestamp") or metadata.get("creationTimestamp")
            last_timestamp = ev.get("lastTimestamp") or first_timestamp

            # Sanitize untrusted message
            safe_message = self.sanitize_untrusted_message(raw_message)

            # Skip benign normal events unless target specifically requested
            if event_type == "Normal" and reason not in CRITICAL_EVENT_REASONS:
                continue

            # Determine category, severity, and suggested fix based on reason
            category = reason.lower()
            severity = KubernetesSeverity.HIGH
            confidence = 0.90
            probable_root_cause = f"Kubernetes event warning: {reason}"
            suggested_fix = "Review cluster event details and involved resource specification."
            validation_steps = [f"kubectl describe {resource_kind.lower()} {resource_name} -n {namespace}"]

            if reason == "FailedScheduling":
                category = "failed_scheduling"
                if any(kw in safe_message.lower() for kw in ["insufficient memory", "insufficient cpu", "nodes"]):
                    category = "insufficient_resources"
                    probable_root_cause = f"Scheduler could not place pod due to resource constraints: {safe_message}"
                    suggested_fix = "Check node CPU/Memory capacity ('kubectl top nodes') and reduce pod resource requests."
                else:
                    probable_root_cause = f"Pod scheduling failed: {safe_message}"
                    suggested_fix = "Check node taints, tolerations, and nodeAffinity rules on the pod."
                validation_steps.extend(["kubectl top nodes", f"kubectl describe pod {resource_name} -n {namespace}"])

            elif reason in {"FailedMount", "FailedAttachVolume"}:
                category = "failed_volume_mount"
                probable_root_cause = f"Storage volume or secret/configmap mount failed: {safe_message}"
                suggested_fix = "Verify the target PVC exists and is bound, or verify that the referenced Secret/ConfigMap exists."
                validation_steps.extend([f"kubectl get pvc -n {namespace}", f"kubectl describe pod {resource_name} -n {namespace}"])

            elif reason in {"FailedPull", "ErrImagePull", "ImagePullBackOff"}:
                category = "image_pull_failure"
                probable_root_cause = f"Kubelet failed to pull container image: {safe_message}"
                suggested_fix = "Verify image tag and registry existence, and ensure imagePullSecrets are configured."
                validation_steps.extend([f"kubectl describe pod {resource_name} -n {namespace}"])

            elif reason == "Unhealthy":
                category = "probe_failed"
                probable_root_cause = f"Readiness or liveness probe failed: {safe_message}"
                suggested_fix = "Check application HTTP endpoint status or command exit code within the container."
                validation_steps.extend([f"kubectl logs {resource_name} -n {namespace}"])

            elif reason == "BackOff":
                category = "backoff_restart"
                severity = KubernetesSeverity.CRITICAL
                probable_root_cause = f"Container failed and kubelet is backing off restarts: {safe_message}"
                suggested_fix = "Inspect prior container logs for application crash or configuration error."
                validation_steps.extend([f"kubectl logs {resource_name} -n {namespace} --previous"])

            elif reason == "FailedCreate":
                category = "failed_create"
                probable_root_cause = f"Controller failed to create child resource: {safe_message}"
                suggested_fix = "Verify namespace resource quotas and security admission policies."
                validation_steps.extend([f"kubectl describe {resource_kind.lower()} {resource_name} -n {namespace}"])

            elif reason == "FailedBinding":
                category = "pvc_binding_failed"
                probable_root_cause = f"PersistentVolumeClaim could not bind to a volume: {safe_message}"
                suggested_fix = "Check available StorageClasses and ensure a dynamic provisioner or PV is available."
                validation_steps.extend([f"kubectl get sc", f"kubectl get pv", f"kubectl describe pvc {resource_name} -n {namespace}"])

            # Map to Component
            component = KubernetesComponent.EVENT
            kind_lower = resource_kind.lower()
            if "pod" in kind_lower:
                component = KubernetesComponent.POD
            elif "deployment" in kind_lower:
                component = KubernetesComponent.DEPLOYMENT
            elif "replicaset" in kind_lower:
                component = KubernetesComponent.REPLICASET
            elif "service" in kind_lower:
                component = KubernetesComponent.SERVICE
            elif "pvc" in kind_lower or "persistentvolumeclaim" in kind_lower:
                component = KubernetesComponent.PVC

            evidence_str = (
                f"Event [{reason}] on {resource_kind}/{resource_name} (namespace: {namespace}) "
                f"Count: {count} | Last Seen: {last_timestamp or 'recently'}\n"
                f"Message: {safe_message}"
            )

            findings.append(
                KubernetesEvidence(
                    source=f"Kubernetes Event ({reason})",
                    component=component,
                    resource_kind=resource_kind,
                    resource_name=resource_name,
                    namespace=namespace,
                    category=category,
                    severity=severity,
                    message=f"{reason} event on {resource_kind} '{resource_name}': {safe_message[:120]}",
                    evidence=evidence_str,
                    confidence=confidence,
                    probable_root_cause=probable_root_cause,
                    suggested_fix=suggested_fix,
                    validation_steps=validation_steps,
                    uncertainties=[],
                    metadata={
                        "reason": reason,
                        "type": event_type,
                        "count": count,
                        "source_component": ev.get("source", {}).get("component") if isinstance(ev.get("source"), dict) else "kubelet",
                    },
                )
            )

        return findings
