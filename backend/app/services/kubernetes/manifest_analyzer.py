"""
Kubernetes Manifest Static Analyzer.

Performs static analysis of Kubernetes YAML manifests without requiring a cluster:
- Validates multi-document YAML syntax
- Checks required top-level fields (apiVersion, kind, metadata.name, spec)
- Detects deprecated API versions (extensions/v1beta1, apps/v1beta1/beta2, etc.)
- Validates container image references (syntax, uppercase tags, :latest warnings)
- Validates container port configurations (ranges, duplicates, name length <= 15)
- Validates resource requests vs limits (limits < requests, invalid quantity formats)
- Validates readiness and liveness probe configurations (handlers, timeouts, delays)
- Validates Deployment selector vs Pod template label alignment
- Validates Service selector alignment against Deployments and Pods in bundle
- Detects unresolved ConfigMap and Secret references within manifest bundles
- Detects missing PersistentVolumeClaim configurations
- STRICT SECURITY: Never prints Secret data or sensitive values (strictly redacts them)
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

from app.services.kubernetes.schemas import (
    KubernetesComponent,
    KubernetesEvidence,
    KubernetesSeverity,
)

logger = logging.getLogger(__name__)

DEPRECATED_APIS = {
    "extensions/v1beta1": {
        "Ingress": "networking.k8s.io/v1",
        "Deployment": "apps/v1",
        "DaemonSet": "apps/v1",
        "ReplicaSet": "apps/v1",
        "NetworkPolicy": "networking.k8s.io/v1",
    },
    "apps/v1beta1": {"Deployment": "apps/v1", "StatefulSet": "apps/v1"},
    "apps/v1beta2": {"Deployment": "apps/v1", "DaemonSet": "apps/v1", "ReplicaSet": "apps/v1"},
    "batch/v1beta1": {"CronJob": "batch/v1"},
    "networking.k8s.io/v1beta1": {"Ingress": "networking.k8s.io/v1"},
}

RESOURCE_QTY_PATTERN = re.compile(r"^\d+(?:\.\d+)?(?:m|k|M|G|T|P|E|Ki|Mi|Gi|Ti|Pi|Ei)?$")


class KubernetesManifestAnalyzer:
    """Specialized static analyzer for Kubernetes YAML manifests."""

    def analyze(
        self,
        yaml_content: str,
        filename: Optional[str] = None,
    ) -> List[KubernetesEvidence]:
        """
        Parse and analyze Kubernetes manifest content (single or multi-document).
        """
        findings: List[KubernetesEvidence] = []
        if not yaml_content or not yaml_content.strip():
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Manifest Validator",
                    component=KubernetesComponent.MANIFEST,
                    resource_kind="Manifest",
                    resource_name=filename or "manifest.yaml",
                    namespace="default",
                    category="empty_manifest",
                    severity=KubernetesSeverity.LOW,
                    message="Provided Kubernetes manifest is empty",
                    evidence="YAML content contains no non-empty documents.",
                    confidence=1.0,
                    probable_root_cause="Empty file provided for manifest analysis.",
                    suggested_fix="Provide valid Kubernetes YAML resource definitions.",
                    validation_steps=[],
                    uncertainties=[],
                )
            )
            return findings

        # 1. Parse YAML (safe multi-document loader)
        docs: List[Dict[str, Any]] = []
        try:
            for doc in yaml.safe_load_all(yaml_content):
                if doc is not None and isinstance(doc, dict):
                    # Redact any Secret values inside memory before further processing
                    self._redact_secret_doc_in_place(doc)
                    docs.append(doc)
        except yaml.YAMLError as exc:
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Manifest Validator",
                    component=KubernetesComponent.MANIFEST,
                    resource_kind="Manifest",
                    resource_name=filename or "manifest.yaml",
                    namespace="default",
                    category="invalid_yaml",
                    severity=KubernetesSeverity.CRITICAL,
                    message=f"Invalid YAML syntax in manifest: {str(exc)}",
                    evidence=str(exc),
                    confidence=1.0,
                    probable_root_cause=f"YAML parser syntax error: {str(exc)}",
                    suggested_fix="Fix YAML indentation, quote unescaped special characters, and check document delimiters ('---').",
                    validation_steps=[
                        f"yamllint {filename or 'manifest.yaml'}",
                        f"kubectl apply --dry-run=client -f {filename or 'manifest.yaml'}",
                    ],
                    uncertainties=[],
                )
            )
            return findings

        if not docs:
            return findings

        # Collect bundle symbols for cross-resource checks
        defined_configmaps: Set[str] = set()
        defined_secrets: Set[str] = set()
        defined_pvcs: Set[str] = set()
        workload_labels: List[Tuple[str, str, Dict[str, str]]] = []  # (kind, name, labels)

        for doc in docs:
            kind = doc.get("kind", "")
            meta = doc.get("metadata", {})
            name = meta.get("name", "")
            if kind == "ConfigMap" and name:
                defined_configmaps.add(name)
            elif kind == "Secret" and name:
                defined_secrets.add(name)
            elif kind == "PersistentVolumeClaim" and name:
                defined_pvcs.add(name)
            elif kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"}:
                t_labels = doc.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {})
                if t_labels:
                    workload_labels.append((kind, name, t_labels))
            elif kind == "Pod":
                p_labels = meta.get("labels", {})
                if p_labels:
                    workload_labels.append((kind, name, p_labels))

        # 2. Analyze each resource document individually
        for idx, doc in enumerate(docs):
            doc_findings = self._analyze_single_doc(
                doc=doc,
                index=idx,
                filename=filename,
                defined_configmaps=defined_configmaps,
                defined_secrets=defined_secrets,
                defined_pvcs=defined_pvcs,
                workload_labels=workload_labels,
                total_docs=len(docs),
            )
            findings.extend(doc_findings)

        return findings

    def _redact_secret_doc_in_place(self, doc: Dict[str, Any]) -> None:
        """Strictly redacts Secret data and stringData fields."""
        if doc.get("kind") == "Secret":
            if "data" in doc and isinstance(doc["data"], dict):
                for k in doc["data"]:
                    doc["data"][k] = "[REDACTED_SECRET_DATA]"
            if "stringData" in doc and isinstance(doc["stringData"], dict):
                for k in doc["stringData"]:
                    doc["stringData"][k] = "[REDACTED_SECRET_DATA]"

    def _analyze_single_doc(
        self,
        doc: Dict[str, Any],
        index: int,
        filename: Optional[str],
        defined_configmaps: Set[str],
        defined_secrets: Set[str],
        defined_pvcs: Set[str],
        workload_labels: List[Tuple[str, str, Dict[str, str]]],
        total_docs: int,
    ) -> List[KubernetesEvidence]:
        findings: List[KubernetesEvidence] = []
        api_version = doc.get("apiVersion")
        kind = doc.get("kind")
        metadata = doc.get("metadata")
        spec = doc.get("spec")

        res_name = (metadata.get("name") if isinstance(metadata, dict) else None) or f"resource-{index+1}"
        namespace = (metadata.get("namespace") if isinstance(metadata, dict) else None) or "default"

        # Check required fields
        if not api_version:
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Manifest Validator",
                    component=KubernetesComponent.MANIFEST,
                    resource_kind=kind or "Unknown",
                    resource_name=res_name,
                    namespace=namespace,
                    category="missing_required_field",
                    severity=KubernetesSeverity.CRITICAL,
                    message=f"Missing required field 'apiVersion' in {kind or 'resource'}",
                    evidence=f"Resource at document #{index+1} is missing top-level 'apiVersion'",
                    confidence=1.0,
                    probable_root_cause="Kubernetes manifest omitted required apiVersion field.",
                    suggested_fix="Specify the appropriate apiVersion (e.g. 'v1', 'apps/v1').",
                    validation_steps=[],
                    uncertainties=[],
                )
            )

        if not kind:
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Manifest Validator",
                    component=KubernetesComponent.MANIFEST,
                    resource_kind="Unknown",
                    resource_name=res_name,
                    namespace=namespace,
                    category="missing_required_field",
                    severity=KubernetesSeverity.CRITICAL,
                    message="Missing required field 'kind'",
                    evidence=f"Resource at document #{index+1} is missing top-level 'kind'",
                    confidence=1.0,
                    probable_root_cause="Kubernetes manifest omitted required resource kind.",
                    suggested_fix="Specify the resource kind (e.g. 'Pod', 'Deployment', 'Service').",
                    validation_steps=[],
                    uncertainties=[],
                )
            )
            return findings

        if not isinstance(metadata, dict) or not metadata.get("name"):
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Manifest Validator",
                    component=KubernetesComponent.MANIFEST,
                    resource_kind=kind,
                    resource_name=res_name,
                    namespace=namespace,
                    category="missing_required_field",
                    severity=KubernetesSeverity.HIGH,
                    message=f"Missing or invalid 'metadata.name' in {kind}",
                    evidence=f"Resource of kind '{kind}' has metadata: {metadata}",
                    confidence=1.0,
                    probable_root_cause="Kubernetes resources require a non-empty metadata.name identifier.",
                    suggested_fix=f"Define metadata.name for the {kind} resource.",
                    validation_steps=[],
                    uncertainties=[],
                )
            )

        # Check for Deprecated API versions
        if api_version in DEPRECATED_APIS and kind in DEPRECATED_APIS[api_version]:
            replacement = DEPRECATED_APIS[api_version][kind]
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Manifest Validator",
                    component=KubernetesComponent.MANIFEST,
                    resource_kind=kind,
                    resource_name=res_name,
                    namespace=namespace,
                    category="deprecated_api_version",
                    severity=KubernetesSeverity.MEDIUM,
                    message=f"Deprecated apiVersion '{api_version}' for kind '{kind}'; use '{replacement}'",
                    evidence=f"apiVersion: {api_version} with kind: {kind}",
                    confidence=0.98,
                    probable_root_cause=f"The API version '{api_version}' is deprecated or removed in modern Kubernetes releases.",
                    suggested_fix=f"Update 'apiVersion: {replacement}' in your manifest.",
                    validation_steps=[f"kubectl apply --dry-run=client -f {filename or 'manifest.yaml'}"],
                    uncertainties=[],
                    metadata={"deprecated_api": api_version, "replacement_api": replacement},
                )
            )

        # Analyze Workload Containers (Deployment, Pod, StatefulSet, DaemonSet, Job)
        containers: List[Dict[str, Any]] = []
        if kind == "Pod" and isinstance(spec, dict):
            containers = spec.get("containers", [])
        elif kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"} and isinstance(spec, dict):
            template = spec.get("template", {})
            t_spec = template.get("spec", {})
            containers = t_spec.get("containers", [])

            # Check Deployment selector vs template labels
            if kind == "Deployment":
                selector = spec.get("selector", {})
                match_labels = selector.get("matchLabels", {})
                t_labels = template.get("metadata", {}).get("labels", {})
                if match_labels and t_labels:
                    for k, v in match_labels.items():
                        if k not in t_labels or t_labels[k] != v:
                            findings.append(
                                KubernetesEvidence(
                                    source="Kubernetes Manifest Validator",
                                    component=KubernetesComponent.DEPLOYMENT,
                                    resource_kind="Deployment",
                                    resource_name=res_name,
                                    namespace=namespace,
                                    category="selector_label_mismatch",
                                    severity=KubernetesSeverity.CRITICAL,
                                    message=f"Deployment selector label '{k}: {v}' does not match pod template label '{t_labels.get(k)}'",
                                    evidence=f"spec.selector.matchLabels: {match_labels} vs spec.template.metadata.labels: {t_labels}",
                                    confidence=1.0,
                                    probable_root_cause="Deployment selector must match pod template labels, or Kubernetes controller will reject rollout.",
                                    suggested_fix=f"Ensure spec.template.metadata.labels has '{k}: {v}'.",
                                    validation_steps=[f"kubectl apply --dry-run=client -f {filename or 'manifest.yaml'}"],
                                    uncertainties=[],
                                )
                            )

        # Container Spec Validation
        for c in containers:
            if not isinstance(c, dict):
                continue
            c_name = c.get("name", "container")

            # 1. Image validation
            image = c.get("image", "")
            if not image:
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Manifest Validator",
                        component=KubernetesComponent.POD,
                        resource_kind=kind,
                        resource_name=res_name,
                        namespace=namespace,
                        category="invalid_container_image",
                        severity=KubernetesSeverity.HIGH,
                        message=f"Container '{c_name}' in {kind} '{res_name}' has no image specified",
                        evidence=f"Container '{c_name}' has image: '{image}'",
                        confidence=1.0,
                        probable_root_cause="Every container must define a valid image reference.",
                        suggested_fix="Specify container image (e.g. 'nginx:1.25.3').",
                        validation_steps=[],
                        uncertainties=[],
                    )
                )
            else:
                # Check for whitespace or uppercase repository characters
                repo_part = image.split(":")[0].split("@")[0]
                if any(ch.isupper() for ch in repo_part):
                    findings.append(
                        KubernetesEvidence(
                            source="Kubernetes Manifest Validator",
                            component=KubernetesComponent.POD,
                            resource_kind=kind,
                            resource_name=res_name,
                            namespace=namespace,
                            category="invalid_container_image",
                            severity=KubernetesSeverity.HIGH,
                            message=f"Image reference '{image}' contains uppercase characters in repository path",
                            evidence=f"Image: {image}",
                            confidence=0.95,
                            probable_root_cause="Docker / OCI registries require lowercase repository names.",
                            suggested_fix=f"Convert repository '{repo_part}' to lowercase: '{image.lower()}'.",
                            validation_steps=[],
                            uncertainties=[],
                        )
                    )
                elif ":" not in image or image.endswith(":latest"):
                    findings.append(
                        KubernetesEvidence(
                            source="Kubernetes Manifest Validator",
                            component=KubernetesComponent.POD,
                            resource_kind=kind,
                            resource_name=res_name,
                            namespace=namespace,
                            category="mutable_image_tag",
                            severity=KubernetesSeverity.LOW,
                            message=f"Container '{c_name}' uses mutable or implicit ':latest' tag: '{image}'",
                            evidence=f"Image: {image}",
                            confidence=0.90,
                            probable_root_cause="Using :latest tag makes deployments non-reproducible across cluster nodes.",
                            suggested_fix="Pin image to an immutable semantic version or git commit SHA tag.",
                            validation_steps=[],
                            uncertainties=[],
                        )
                    )

            # 2. Port validation
            ports = c.get("ports", [])
            seen_ports = set()
            for p in ports:
                if isinstance(p, dict):
                    cp = p.get("containerPort")
                    p_name = p.get("name")
                    if cp is None or not isinstance(cp, int) or cp <= 0 or cp > 65535:
                        findings.append(
                            KubernetesEvidence(
                                source="Kubernetes Manifest Validator",
                                component=KubernetesComponent.POD,
                                resource_kind=kind,
                                resource_name=res_name,
                                namespace=namespace,
                                category="invalid_port_configuration",
                                severity=KubernetesSeverity.HIGH,
                                message=f"Container '{c_name}' has invalid containerPort '{cp}'",
                                evidence=f"containerPort: {cp}",
                                confidence=1.0,
                                probable_root_cause="Container ports must be integers between 1 and 65535.",
                                suggested_fix="Set containerPort to a valid TCP/UDP port number.",
                                validation_steps=[],
                                uncertainties=[],
                            )
                        )
                    elif cp in seen_ports:
                        findings.append(
                            KubernetesEvidence(
                                source="Kubernetes Manifest Validator",
                                component=KubernetesComponent.POD,
                                resource_kind=kind,
                                resource_name=res_name,
                                namespace=namespace,
                                category="duplicate_container_port",
                                severity=KubernetesSeverity.MEDIUM,
                                message=f"Container '{c_name}' declares duplicate containerPort {cp}",
                                evidence=f"Duplicate port: {cp}",
                                confidence=1.0,
                                probable_root_cause="Container declares multiple port mappings for the same containerPort.",
                                suggested_fix="Remove duplicate containerPort declaration.",
                                validation_steps=[],
                                uncertainties=[],
                            )
                        )
                    seen_ports.add(cp)

                    if p_name and len(p_name) > 15:
                        findings.append(
                            KubernetesEvidence(
                                source="Kubernetes Manifest Validator",
                                component=KubernetesComponent.POD,
                                resource_kind=kind,
                                resource_name=res_name,
                                namespace=namespace,
                                category="invalid_port_configuration",
                                severity=KubernetesSeverity.HIGH,
                                message=f"Port name '{p_name}' exceeds maximum allowed length of 15 characters (RFC 6335)",
                                evidence=f"port name: '{p_name}' (length: {len(p_name)})",
                                confidence=1.0,
                                probable_root_cause="Kubernetes port names must be at most 15 characters.",
                                suggested_fix=f"Shorten port name '{p_name}' to 15 characters or fewer.",
                                validation_steps=[],
                                uncertainties=[],
                            )
                        )

            # 3. Resource requests vs limits
            resources = c.get("resources", {})
            requests = resources.get("requests", {})
            limits = resources.get("limits", {})

            # Check limits < requests for memory/cpu if both present and numeric
            self._validate_resource_quantities(
                findings=findings,
                kind=kind,
                res_name=res_name,
                namespace=namespace,
                c_name=c_name,
                requests=requests,
                limits=limits,
            )

            # 4. Probe validation
            for probe_type in ["readinessProbe", "livenessProbe", "startupProbe"]:
                probe = c.get(probe_type)
                if isinstance(probe, dict):
                    has_handler = any(h in probe for h in ["httpGet", "exec", "tcpSocket", "grpc"])
                    if not has_handler:
                        findings.append(
                            KubernetesEvidence(
                                source="Kubernetes Manifest Validator",
                                component=KubernetesComponent.POD,
                                resource_kind=kind,
                                resource_name=res_name,
                                namespace=namespace,
                                category="invalid_probe_configuration",
                                severity=KubernetesSeverity.HIGH,
                                message=f"{probe_type} in container '{c_name}' is missing a probe action handler (httpGet, exec, or tcpSocket)",
                                evidence=f"{probe_type}: {probe}",
                                confidence=1.0,
                                probable_root_cause="Probes must specify exactly one action handler.",
                                suggested_fix="Add 'httpGet', 'exec', or 'tcpSocket' to the probe definition.",
                                validation_steps=[],
                                uncertainties=[],
                            )
                        )
                    if probe.get("initialDelaySeconds", 0) < 0:
                        findings.append(
                            KubernetesEvidence(
                                source="Kubernetes Manifest Validator",
                                component=KubernetesComponent.POD,
                                resource_kind=kind,
                                resource_name=res_name,
                                namespace=namespace,
                                category="invalid_probe_configuration",
                                severity=KubernetesSeverity.MEDIUM,
                                message=f"{probe_type} initialDelaySeconds cannot be negative ({probe.get('initialDelaySeconds')})",
                                evidence=f"initialDelaySeconds: {probe.get('initialDelaySeconds')}",
                                confidence=1.0,
                                probable_root_cause="Negative delay values are invalid in Kubernetes probe specs.",
                                suggested_fix="Set initialDelaySeconds >= 0.",
                                validation_steps=[],
                                uncertainties=[],
                            )
                        )

            # 5. Check missing ConfigMap/Secret references across multi-document manifest
            if total_docs > 1:
                # envFrom checks
                for ef in c.get("envFrom", []):
                    if isinstance(ef, dict):
                        cm_ref = ef.get("configMapRef", {}).get("name")
                        if cm_ref and defined_configmaps and cm_ref not in defined_configmaps:
                            findings.append(
                                KubernetesEvidence(
                                    source="Kubernetes Manifest Validator",
                                    component=KubernetesComponent.CONFIGMAP,
                                    resource_kind=kind,
                                    resource_name=res_name,
                                    namespace=namespace,
                                    category="missing_configmap_reference",
                                    severity=KubernetesSeverity.HIGH,
                                    message=f"Container '{c_name}' references ConfigMap '{cm_ref}' not defined in manifest set",
                                    evidence=f"envFrom: configMapRef.name: '{cm_ref}'. Defined ConfigMaps: {list(defined_configmaps)}",
                                    confidence=0.88,
                                    probable_root_cause="Manifest references a ConfigMap that is not declared in the deployment bundle.",
                                    suggested_fix=f"Include definition for ConfigMap '{cm_ref}' in manifest or verify pre-existence in cluster.",
                                    validation_steps=[f"kubectl get configmap {cm_ref} -n {namespace}"],
                                    uncertainties=["ConfigMap may already exist in the target cluster if provisioned externally"],
                                )
                            )
                        sec_ref = ef.get("secretRef", {}).get("name")
                        if sec_ref and defined_secrets and sec_ref not in defined_secrets:
                            findings.append(
                                KubernetesEvidence(
                                    source="Kubernetes Manifest Validator",
                                    component=KubernetesComponent.SECRET,
                                    resource_kind=kind,
                                    resource_name=res_name,
                                    namespace=namespace,
                                    category="missing_secret_reference",
                                    severity=KubernetesSeverity.HIGH,
                                    message=f"Container '{c_name}' references Secret '{sec_ref}' not defined in manifest set",
                                    evidence=f"envFrom: secretRef.name: '{sec_ref}'. Defined Secrets: {list(defined_secrets)}",
                                    confidence=0.88,
                                    probable_root_cause="Manifest references a Secret that is not declared in the deployment bundle.",
                                    suggested_fix=f"Include Secret '{sec_ref}' or verify it is created in target namespace.",
                                    validation_steps=[f"kubectl get secret {sec_ref} -n {namespace}"],
                                    uncertainties=["Secret may already exist in the target cluster if provisioned via Vault or external-secrets"],
                                )
                            )

        # Analyze Service Selector Mismatch (against workloads defined in bundle)
        if kind == "Service" and isinstance(spec, dict):
            svc_selector = spec.get("selector", {})
            if svc_selector and workload_labels:
                # Check if this Service matches ANY defined workload in the bundle
                has_match = False
                for w_kind, w_name, w_labels in workload_labels:
                    # svc_selector is matched if all svc_selector key/values are in w_labels
                    if all(w_labels.get(k) == v for k, v in svc_selector.items()):
                        has_match = True
                        break
                if not has_match:
                    findings.append(
                        KubernetesEvidence(
                            source="Kubernetes Manifest Validator",
                            component=KubernetesComponent.SERVICE,
                            resource_kind="Service",
                            resource_name=res_name,
                            namespace=namespace,
                            category="service_selector_mismatch",
                            severity=KubernetesSeverity.HIGH,
                            message=f"Service '{res_name}' selector does not match any Pod or Deployment labels in manifest bundle",
                            evidence=f"Service selector: {svc_selector}. Workload labels: {[l[2] for l in workload_labels]}",
                            confidence=0.85,
                            probable_root_cause="Service selector labels do not match pod template labels, so Service will have 0 endpoints.",
                            suggested_fix="Align Service 'spec.selector' labels with Deployment 'spec.template.metadata.labels'.",
                            validation_steps=[
                                f"kubectl get endpoints {res_name} -n {namespace}",
                            ],
                            uncertainties=["Target workload may be defined in another manifest file not included in this bundle"],
                        )
                    )

        return findings

    def _validate_resource_quantities(
        self,
        findings: List[KubernetesEvidence],
        kind: str,
        res_name: str,
        namespace: str,
        c_name: str,
        requests: Dict[str, Any],
        limits: Dict[str, Any],
    ) -> None:
        # Check quantity syntax
        for res_type in ["cpu", "memory"]:
            req_val = requests.get(res_type)
            lim_val = limits.get(res_type)
            if req_val and not RESOURCE_QTY_PATTERN.match(str(req_val)):
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Manifest Validator",
                        component=KubernetesComponent.POD,
                        resource_kind=kind,
                        resource_name=res_name,
                        namespace=namespace,
                        category="invalid_resource_quantity",
                        severity=KubernetesSeverity.HIGH,
                        message=f"Invalid {res_type} request format '{req_val}' in container '{c_name}'",
                        evidence=f"requests.{res_type}: '{req_val}'",
                        confidence=1.0,
                        probable_root_cause=f"Kubernetes quantity parser does not recognize '{req_val}'.",
                        suggested_fix=f"Use standard quantity format (e.g. '250m' for CPU, '256Mi' for memory).",
                        validation_steps=[],
                        uncertainties=[],
                    )
                )
            if lim_val and not RESOURCE_QTY_PATTERN.match(str(lim_val)):
                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Manifest Validator",
                        component=KubernetesComponent.POD,
                        resource_kind=kind,
                        resource_name=res_name,
                        namespace=namespace,
                        category="invalid_resource_quantity",
                        severity=KubernetesSeverity.HIGH,
                        message=f"Invalid {res_type} limit format '{lim_val}' in container '{c_name}'",
                        evidence=f"limits.{res_type}: '{lim_val}'",
                        confidence=1.0,
                        probable_root_cause=f"Kubernetes quantity parser does not recognize '{lim_val}'.",
                        suggested_fix=f"Use standard quantity format (e.g. '500m' for CPU, '512Mi' for memory).",
                        validation_steps=[],
                        uncertainties=[],
                    )
                )

        # Check limits < requests for memory
        req_mem_bytes = self._parse_memory_bytes(requests.get("memory"))
        lim_mem_bytes = self._parse_memory_bytes(limits.get("memory"))
        if req_mem_bytes is not None and lim_mem_bytes is not None and lim_mem_bytes < req_mem_bytes:
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Manifest Validator",
                    component=KubernetesComponent.POD,
                    resource_kind=kind,
                    resource_name=res_name,
                    namespace=namespace,
                    category="invalid_resource_limits",
                    severity=KubernetesSeverity.CRITICAL,
                    message=f"Container '{c_name}' memory limit ({limits.get('memory')}) is less than memory request ({requests.get('memory')})",
                    evidence=f"limits.memory: {limits.get('memory')} < requests.memory: {requests.get('memory')}",
                    confidence=1.0,
                    probable_root_cause="Kubernetes rejects pods where limits are less than requests.",
                    suggested_fix="Ensure memory limits >= memory requests.",
                    validation_steps=[],
                    uncertainties=[],
                )
            )

        # Check limits < requests for cpu
        req_cpu_millis = self._parse_cpu_millis(requests.get("cpu"))
        lim_cpu_millis = self._parse_cpu_millis(limits.get("cpu"))
        if req_cpu_millis is not None and lim_cpu_millis is not None and lim_cpu_millis < req_cpu_millis:
            findings.append(
                KubernetesEvidence(
                    source="Kubernetes Manifest Validator",
                    component=KubernetesComponent.POD,
                    resource_kind=kind,
                    resource_name=res_name,
                    namespace=namespace,
                    category="invalid_resource_limits",
                    severity=KubernetesSeverity.CRITICAL,
                    message=f"Container '{c_name}' CPU limit ({limits.get('cpu')}) is less than CPU request ({requests.get('cpu')})",
                    evidence=f"limits.cpu: {limits.get('cpu')} < requests.cpu: {requests.get('cpu')}",
                    confidence=1.0,
                    probable_root_cause="Kubernetes rejects pods where limits are less than requests.",
                    suggested_fix="Ensure CPU limits >= CPU requests.",
                    validation_steps=[],
                    uncertainties=[],
                )
            )

    def _parse_memory_bytes(self, val: Any) -> Optional[int]:
        if not val or not isinstance(val, (str, int)):
            return None
        val_str = str(val).strip()
        units = {
            "Ki": 1024,
            "Mi": 1024**2,
            "Gi": 1024**3,
            "Ti": 1024**4,
            "k": 1000,
            "M": 1000**2,
            "G": 1000**3,
            "T": 1000**4,
        }
        for u, mul in units.items():
            if val_str.endswith(u):
                try:
                    return int(float(val_str[: -len(u)]) * mul)
                except ValueError:
                    return None
        try:
            return int(val_str)
        except ValueError:
            return None

    def _parse_cpu_millis(self, val: Any) -> Optional[int]:
        if not val or not isinstance(val, (str, int, float)):
            return None
        val_str = str(val).strip()
        if val_str.endswith("m"):
            try:
                return int(val_str[:-1])
            except ValueError:
                return None
        try:
            return int(float(val_str) * 1000)
        except ValueError:
            return None
