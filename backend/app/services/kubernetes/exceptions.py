"""
Kubernetes Intelligence custom exceptions.

Provides structured exception hierarchy for all Kubernetes-related
analysis and inspection operations in Phase 5.
"""


class KubernetesException(Exception):
    """Base exception for all Kubernetes intelligence operations."""

    def __init__(
        self,
        message: str = "Kubernetes intelligence error",
        code: str = "KUBERNETES_ERROR",
        status_code: int = 500,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class KubernetesUnavailableError(KubernetesException):
    """Raised when the Kubernetes cluster is unreachable or client is unconfigured."""

    def __init__(self, message: str = "Kubernetes cluster is not available or unreachable"):
        super().__init__(message, code="KUBERNETES_UNAVAILABLE", status_code=503)


class KubernetesConfigError(KubernetesException):
    """Raised when kubeconfig is missing, malformed, or context is invalid."""

    def __init__(self, message: str = "Kubernetes configuration or context error"):
        super().__init__(message, code="KUBERNETES_CONFIG_ERROR", status_code=400)


class KubernetesAuthError(KubernetesException):
    """Raised when Kubernetes authentication or RBAC authorization fails."""

    def __init__(self, message: str = "Kubernetes authentication or authorization failure"):
        super().__init__(message, code="KUBERNETES_AUTH_ERROR", status_code=403)


class KubernetesTimeoutError(KubernetesException):
    """Raised when a Kubernetes API request times out."""

    def __init__(self, message: str = "Kubernetes API request timed out"):
        super().__init__(message, code="KUBERNETES_TIMEOUT", status_code=504)


class KubernetesParseError(KubernetesException):
    """Raised when a Kubernetes YAML manifest cannot be parsed."""

    def __init__(self, message: str = "Failed to parse Kubernetes manifest"):
        super().__init__(message, code="KUBERNETES_PARSE_ERROR", status_code=400)


class KubernetesResourceNotFoundError(KubernetesException):
    """Raised when a requested Kubernetes resource does not exist."""

    def __init__(self, message: str = "Kubernetes resource not found"):
        super().__init__(message, code="KUBERNETES_NOT_FOUND", status_code=404)


class KubernetesCommandForbiddenError(KubernetesException):
    """Raised when a mutating or forbidden operation is requested in read-only mode."""

    def __init__(self, message: str = "Operation is not permitted in read-only mode"):
        super().__init__(message, code="KUBERNETES_FORBIDDEN", status_code=403)
