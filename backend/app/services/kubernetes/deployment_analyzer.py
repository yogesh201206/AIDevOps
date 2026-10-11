"""
Kubernetes Deployment and ReplicaSet Intelligence Analyzer.

Analyzes Deployments and ReplicaSets to detect:
- Desired replicas versus available replicas mismatch
- ProgressDeadlineExceeded condition
- Rollout timeouts and stalled progress
- Pods failing to become ready
- Selector and Pod-template label mismatches
- Never claims that a rollout failed solely because a Deployment is temporarily progressing.
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.kubernetes.schemas import (
    KubernetesComponent,
    KubernetesEvidence,
    KubernetesSeverity,
)

logger = logging.getLogger(__name__)


class DeploymentAnalyzer:
    """Specialized analyzer for Kubernetes Deployments and ReplicaSets."""

    def analyze(
        self,
        deployment_data: Dict[str, Any],
        related_replicasets: Optional[List[Dict[str, Any]]] = None,
        deployment_events: Optional[List[Dict[str, Any]]] = None,
    ) -> List[KubernetesEvidence]:
        """
        Analyze Deployment structure (dict representation of Deployment object or status).
        """
        findings: List[KubernetesEvidence] = []
        if not deployment_data or not isinstance(deployment_data, dict):
            return findings

        metadata = deployment_data.get("metadata", {})
        dep_name = metadata.get("name") or deployment_data.get("name") or "unknown-deployment"
        namespace = metadata.get("namespace") or deployment_data.get("namespace") or "default"

        spec = deployment_data.get("spec", {})
        status = deployment_data.get("status", {})

        desired_replicas = spec.get("replicas", 1)
        available_replicas = status.get("availableReplicas", 0)
        ready_replicas = status.get("readyReplicas", 0)
        updated_replicas = status.get("updatedReplicas", 0)
        unavailable_replicas = status.get("unavailableReplicas", 0)

        # 1. Analyze Conditions
        conditions = status.get("conditions", [])
        is_progress_deadline_exceeded = False
        is_temporarily_progressing = False

        for cond in conditions:
            c_type = cond.get("type")
            c_status = cond.get("status")
            c_reason = cond.get("reason", "")
            c_message = cond.get("message", "")

            # Progressing Condition analysis
            if c_type == "Progressing":
                if c_reason == "ProgressDeadlineExceeded":
                    is_progress_deadline_exceeded = True
                    findings.append(
                        KubernetesEvidence(
                            source="Kubernetes Deployment Conditions",
                            component=KubernetesComponent.DEPLOYMENT,
                            resource_kind="Deployment",
                            resource_name=dep_name,
                            namespace=namespace,
                            category="progress_deadline_exceeded",
                            severity=KubernetesSeverity.CRITICAL,
                            message=f"Deployment rollout exceeded progress deadline in namespace '{namespace}'",
                            evidence=f"Condition Progressing=False | Reason: {c_reason} | Message: {c_message}",
                            confidence=0.98,
                            probable_root_cause=f"Deployment failed to make progress within spec.progressDeadlineSeconds: {c_message}",
                            suggested_fix="Inspect pod failure reasons (e.g. CrashLoopBackOff or ImagePullBackOff) preventing new replica rollout, then rollback or update image.",
                            validation_steps=[
                                f"kubectl rollout status deployment/{dep_name} -n {namespace}",
                                f"kubectl describe deployment/{dep_name} -n {namespace}",
                                f"kubectl get pods -l app={dep_name} -n {namespace}",
                            ],
                            uncertainties=[],
                            metadata={"condition": c_type, "reason": c_reason, "message": c_message},
                        )
                    )
                elif c_status == "True" and c_reason in {"ReplicaSetUpdated", "NewReplicaSetAvailable"}:
                    # Normal progressing rollout – strictly DO NOT flag as failure
                    is_temporarily_progressing = True
                    logger.debug(
                        "Deployment %s is progressing normally (reason: %s); not flagged as failure",
                        dep_name,
                        c_reason,
                    )
                elif c_status == "False":
                    # Stalled or failed progress
                    findings.append(
                        KubernetesEvidence(
                            source="Kubernetes Deployment Conditions",
                            component=KubernetesComponent.DEPLOYMENT,
                            resource_kind="Deployment",
                            resource_name=dep_name,
                            namespace=namespace,
                            category="deployment_progress_stalled",
                            severity=KubernetesSeverity.HIGH,
                            message=f"Deployment progress is stalled: {c_reason}",
                            evidence=f"Condition Progressing=False | Reason: {c_reason} | Message: {c_message}",
                            confidence=0.90,
                            probable_root_cause=f"Rollout halted: {c_message}",
                            suggested_fix="Check underlying ReplicaSet and Pod events to determine why new pods are not ready.",
                            validation_steps=[
                                f"kubectl describe deployment {dep_name} -n {namespace}",
                            ],
                            uncertainties=[],
                            metadata={"condition": c_type, "reason": c_reason, "message": c_message},
                        )
                    )

            # Available Condition analysis
            elif c_type == "Available" and c_status == "False":
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Deployment Conditions",
                        component=KubernetesComponent.DEPLOYMENT,
                        resource_kind="Deployment",
                        resource_name=dep_name,
                        namespace=namespace,
                        category="deployment_unavailable",
                        severity=KubernetesSeverity.HIGH,
                        message=f"Deployment has no minimum available pods in namespace '{namespace}'",
                        evidence=f"Condition Available=False | Reason: {c_reason} | Message: {c_message}",
                        confidence=0.92,
                        probable_root_cause=f"Required minimum replicas are not ready: {c_message}",
                        suggested_fix="Inspect pods associated with this deployment to diagnose readiness or crash failures.",
                        validation_steps=[
                            f"kubectl get pods -n {namespace} -l <selector>",
                            f"kubectl describe deployment {dep_name} -n {namespace}",
                        ],
                        uncertainties=[],
                        metadata={"condition": c_type, "reason": c_reason, "message": c_message},
                    )
                )

        # 2. Desired vs Available Replicas Mismatch
        # Only flag if not merely in the middle of normal rapid progression without timeout, or if unavailable_replicas > 0
        if desired_replicas > 0 and available_replicas < desired_replicas:
            # If progress deadline is exceeded or unavailable > 0 or ready < desired
            if is_progress_deadline_exceeded or unavailable_replicas > 0 or not is_temporarily_progressing:
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Deployment Status",
                        component=KubernetesComponent.DEPLOYMENT,
                        resource_kind="Deployment",
                        resource_name=dep_name,
                        namespace=namespace,
                        category="replica_mismatch",
                        severity=KubernetesSeverity.HIGH,
                        message=f"Deployment '{dep_name}' has replica mismatch: {available_replicas}/{desired_replicas} available",
                        evidence=(
                            f"Desired replicas: {desired_replicas}, Available: {available_replicas}, "
                            f"Ready: {ready_replicas}, Updated: {updated_replicas}, Unavailable: {unavailable_replicas}"
                        ),
                        confidence=0.94,
                        probable_root_cause=(
                            f"Pods belonging to deployment '{dep_name}' are failing readiness probes, crashing, or unschedulable."
                        ),
                        suggested_fix="Check pod health and events for container crash or image pull failures.",
                        validation_steps=[
                            f"kubectl get pods -n {namespace}",
                            f"kubectl rollout status deployment/{dep_name} -n {namespace}",
                        ],
                        uncertainties=[
                            "Need individual Pod status to pinpoint whether failure is image pull, crash, or scheduling"
                        ],
                        metadata={
                            "desired_replicas": desired_replicas,
                            "available_replicas": available_replicas,
                            "ready_replicas": ready_replicas,
                            "unavailable_replicas": unavailable_replicas,
                        },
                    )
                )

        # 3. Selector and Pod Template Label Mismatch Check
        selector = spec.get("selector", {})
        match_labels = selector.get("matchLabels", {})
        template = spec.get("template", {})
        template_meta = template.get("metadata", {})
        template_labels = template_meta.get("labels", {})

        if match_labels and template_labels:
            mismatches = []
            for k, v in match_labels.items():
                if k not in template_labels or template_labels[k] != v:
                    mismatches.append(f"selector '{k}: {v}' != template '{k}: {template_labels.get(k)}'")

            if mismatches:
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Deployment Spec",
                        component=KubernetesComponent.DEPLOYMENT,
                        resource_kind="Deployment",
                        resource_name=dep_name,
                        namespace=namespace,
                        category="selector_label_mismatch",
                        severity=KubernetesSeverity.CRITICAL,
                        message=f"Deployment selector does not match Pod template labels: {', '.join(mismatches)}",
                        evidence=f"spec.selector.matchLabels: {match_labels} vs spec.template.metadata.labels: {template_labels}",
                        confidence=0.99,
                        probable_root_cause="Kubernetes rejects or orphans pods because Deployment selector matchLabels do not match template labels.",
                        suggested_fix="Ensure all labels specified in 'spec.selector.matchLabels' exist with identical values under 'spec.template.metadata.labels'.",
                        validation_steps=[
                            "kubectl apply --dry-run=client -f <deployment.yaml>",
                        ],
                        uncertainties=[],
                        metadata={"match_labels": match_labels, "template_labels": template_labels},
                    )
                )

        # 4. Check Related ReplicaSets (if provided)
        if related_replicasets:
            for rs in related_replicasets:
                rs_meta = rs.get("metadata", {})
                rs_name = rs_meta.get("name", "unknown-rs")
                rs_spec = rs.get("spec", {})
                rs_status = rs.get("status", {})

                rs_desired = rs_spec.get("replicas", 0)
                rs_ready = rs_status.get("readyReplicas", 0)
                rs_conditions = rs_status.get("conditions", [])

                for rc in rs_conditions:
                    if rc.get("type") == "ReplicaFailure":
                        findings.append(
                            KubernetesEvidence(
                                source="Kubernetes ReplicaSet Status",
                                component=KubernetesComponent.REPLICASET,
                                resource_kind="ReplicaSet",
                                resource_name=rs_name,
                                namespace=namespace,
                                category="replicaset_creation_failure",
                                severity=KubernetesSeverity.HIGH,
                                message=f"ReplicaSet '{rs_name}' failed to create pods: {rc.get('reason')}",
                                evidence=f"ReplicaSet Condition ReplicaFailure: {rc.get('message')}",
                                confidence=0.95,
                                probable_root_cause=f"ReplicaSet pod creation blocked: {rc.get('message')}",
                                suggested_fix="Check namespace quota or admission controller constraints blocking pod creation.",
                                validation_steps=[
                                    f"kubectl describe rs {rs_name} -n {namespace}",
                                ],
                                uncertainties=[],
                                metadata={"replicaset": rs_name, "reason": rc.get("reason")},
                            )
                        )

        return findings
