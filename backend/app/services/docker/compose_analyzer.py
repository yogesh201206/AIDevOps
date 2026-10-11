"""
Docker Compose Static Analyzer.

Performs rule-based static validation of docker-compose.yml files.
Detects syntax errors, missing service blocks, invalid depends_on targets,
host port collisions across services, unexpanded variables, and malformed volume mappings.
Does NOT require a Docker daemon or Docker Compose CLI.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

import yaml

from app.services.docker.schemas import (
    DockerComponent,
    DockerEvidence,
    DockerSeverity,
)

logger = logging.getLogger(__name__)

# Pattern to detect unexpanded bash-style variables: ${VARIABLE} or ${VARIABLE:-default}
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)(?::-[^}]*)?\}")


class DockerComposeAnalyzer:
    """Static analyzer for Docker Compose YAML configurations."""

    def analyze(self, compose_content: Optional[str]) -> List[DockerEvidence]:
        """
        Validate compose file content and return structured Docker evidence.
        """
        if compose_content is None:
            return []

        if not compose_content.strip():
            return [
                DockerEvidence(
                    source="Docker Compose",
                    component=DockerComponent.COMPOSE,
                    category="empty_compose_file",
                    severity=DockerSeverity.HIGH,
                    message="Docker Compose configuration is empty.",
                    evidence="Provided compose configuration contains no data.",
                    confidence=1.0,
                )
            ]

        # 1. Parse YAML
        try:
            doc = yaml.safe_load(compose_content)
        except yaml.YAMLError as exc:
            return [
                DockerEvidence(
                    source="Docker Compose",
                    component=DockerComponent.COMPOSE,
                    category="invalid_compose_yaml",
                    severity=DockerSeverity.CRITICAL,
                    message="Docker Compose YAML parsing failed due to invalid syntax.",
                    evidence=f"YAML parser error: {str(exc)}",
                    confidence=1.0,
                )
            ]

        if not isinstance(doc, dict):
            return [
                DockerEvidence(
                    source="Docker Compose",
                    component=DockerComponent.COMPOSE,
                    category="invalid_compose_structure",
                    severity=DockerSeverity.HIGH,
                    message="Docker Compose configuration root must be a YAML mapping (dictionary).",
                    evidence=f"Root parsed as {type(doc).__name__} instead of dictionary.",
                    confidence=1.0,
                )
            ]

        findings: List[DockerEvidence] = []

        # 2. Check services key
        services = doc.get("services")
        if not services or not isinstance(services, dict):
            findings.append(
                DockerEvidence(
                    source="Docker Compose",
                    component=DockerComponent.COMPOSE,
                    category="missing_services_block",
                    severity=DockerSeverity.CRITICAL,
                    message="Docker Compose file is missing a 'services' block or 'services' is empty.",
                    evidence="No service definitions found under 'services' key in compose file.",
                    confidence=1.0,
                )
            )
            return findings

        service_names = set(services.keys())

        # 3. Check depends_on integrity
        findings.extend(self._check_depends_on(services, service_names))

        # 4. Check Host Port Collisions across services
        findings.extend(self._check_port_collisions(services))

        # 5. Check build contexts & images
        findings.extend(self._check_service_images_and_build(services))

        # 6. Check unexpanded env vars
        findings.extend(self._check_unexpanded_env_vars(compose_content))

        # 7. Check volumes structure
        findings.extend(self._check_volume_definitions(doc, services))

        if not findings:
            findings.append(
                DockerEvidence(
                    source="Docker Compose",
                    component=DockerComponent.COMPOSE,
                    category="valid_compose_configuration",
                    severity=DockerSeverity.INFO,
                    message=f"Docker Compose file is valid with {len(service_names)} defined service(s): {', '.join(sorted(service_names))}.",
                    evidence=f"Services defined: {list(service_names)}",
                    confidence=1.0,
                )
            )

        logger.debug("DockerComposeAnalyzer complete | findings=%d", len(findings))
        return findings

    def _check_depends_on(
        self,
        services: Dict[str, Any],
        service_names: Set[str],
    ) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        for svc_name, svc_cfg in services.items():
            if not isinstance(svc_cfg, dict):
                continue
            depends_on = svc_cfg.get("depends_on")
            if not depends_on:
                continue

            target_deps: List[str] = []
            if isinstance(depends_on, list):
                target_deps = [str(d) for d in depends_on]
            elif isinstance(depends_on, dict):
                target_deps = list(depends_on.keys())

            for dep in target_deps:
                if dep not in service_names:
                    findings.append(
                        DockerEvidence(
                            source="Docker Compose",
                            component=DockerComponent.COMPOSE,
                            category="invalid_depends_on",
                            severity=DockerSeverity.HIGH,
                            message=f"Service '{svc_name}' depends on undefined service '{dep}'.",
                            evidence=f"Service '{svc_name}' specifies 'depends_on: {dep}', but '{dep}' is not defined in services: {list(service_names)}",
                            confidence=0.98,
                            metadata={"service": svc_name, "missing_dependency": dep},
                        )
                    )
        return findings

    def _check_port_collisions(self, services: Dict[str, Any]) -> List[DockerEvidence]:
        """Detect when two services attempt to bind the same host port."""
        findings: List[DockerEvidence] = []
        host_port_map: Dict[str, str] = {}  # host_port -> service_name

        for svc_name, svc_cfg in services.items():
            if not isinstance(svc_cfg, dict):
                continue
            ports = svc_cfg.get("ports") or []
            if not isinstance(ports, list):
                continue

            for p in ports:
                # Common formats: "8080:80", "127.0.0.1:8080:80", 8080
                p_str = str(p)
                parts = p_str.split(":")
                host_port: Optional[str] = None
                if len(parts) == 2:
                    host_port = parts[0].strip()
                elif len(parts) == 3:
                    host_port = parts[1].strip()

                if host_port and host_port.isdigit():
                    if host_port in host_port_map:
                        colliding_svc = host_port_map[host_port]
                        findings.append(
                            DockerEvidence(
                                source="Docker Compose",
                                component=DockerComponent.COMPOSE,
                                category="compose_port_collision",
                                severity=DockerSeverity.HIGH,
                                message=f"Host port collision on port {host_port} between service '{svc_name}' and service '{colliding_svc}'.",
                                evidence=f"Both '{colliding_svc}' and '{svc_name}' attempt to bind host port {host_port}.",
                                confidence=0.95,
                                metadata={
                                    "host_port": host_port,
                                    "services": [colliding_svc, svc_name],
                                },
                            )
                        )
                    else:
                        host_port_map[host_port] = svc_name
        return findings

    def _check_service_images_and_build(self, services: Dict[str, Any]) -> List[DockerEvidence]:
        """Verify each service defines either an image or a build directive."""
        findings: List[DockerEvidence] = []
        for svc_name, svc_cfg in services.items():
            if not isinstance(svc_cfg, dict):
                continue
            has_image = bool(svc_cfg.get("image"))
            has_build = bool(svc_cfg.get("build"))

            if not has_image and not has_build:
                findings.append(
                    DockerEvidence(
                        source="Docker Compose",
                        component=DockerComponent.COMPOSE,
                        category="missing_image_or_build",
                        severity=DockerSeverity.HIGH,
                        message=f"Service '{svc_name}' specifies neither an 'image' nor a 'build' context.",
                        evidence=f"Service '{svc_name}' configuration has no image or build instructions.",
                        confidence=0.95,
                        metadata={"service": svc_name},
                    )
                )
        return findings

    def _check_unexpanded_env_vars(self, raw_content: str) -> List[DockerEvidence]:
        """Detect any unexpanded environment variable expressions that lack defaults."""
        findings: List[DockerEvidence] = []
        matches = ENV_VAR_PATTERN.findall(raw_content)
        # Check variables that have no default value specified
        for var in set(matches):
            pattern_no_default = f"${{{var}}}"
            if pattern_no_default in raw_content:
                findings.append(
                    DockerEvidence(
                        source="Docker Compose",
                        component=DockerComponent.COMPOSE,
                        category="unexpanded_environment_variable",
                        severity=DockerSeverity.LOW,
                        message=f"Compose file references environment variable '${{{var}}}' without a fallback default.",
                        evidence=f"Expression '${{{var}}}' requires the variable to be present in the shell or .env file.",
                        confidence=0.80,
                        metadata={"variable": var},
                    )
                )
        return findings

    def _check_volume_definitions(self, doc: Dict[str, Any], services: Dict[str, Any]) -> List[DockerEvidence]:
        """Verify named volumes referenced by services are defined in top-level volumes block."""
        findings: List[DockerEvidence] = []
        top_volumes = set(doc.get("volumes", {}).keys()) if isinstance(doc.get("volumes"), dict) else set()

        for svc_name, svc_cfg in services.items():
            if not isinstance(svc_cfg, dict):
                continue
            volumes = svc_cfg.get("volumes") or []
            if not isinstance(volumes, list):
                continue

            for vol in volumes:
                if isinstance(vol, str) and ":" in vol:
                    source_part = vol.split(":")[0].strip()
                    # If it's not a path (doesn't start with . or /), it is a named volume
                    if not source_part.startswith((".", "/", "~")) and not source_part.isdigit():
                        if source_part not in top_volumes:
                            findings.append(
                                DockerEvidence(
                                    source="Docker Compose",
                                    component=DockerComponent.COMPOSE,
                                    category="undefined_named_volume",
                                    severity=DockerSeverity.MEDIUM,
                                    message=f"Service '{svc_name}' uses named volume '{source_part}' which is not declared under top-level 'volumes:'.",
                                    evidence=f"Volume '{source_part}' used in service '{svc_name}' volume mount '{vol}'.",
                                    confidence=0.90,
                                    metadata={"service": svc_name, "volume": source_part},
                                )
                            )
        return findings
