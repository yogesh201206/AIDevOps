"""
Application configuration using pydantic-settings.
Environment variables are loaded from .env file or the environment.
"""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings.

    All values can be overridden via environment variables.
    Sensitive fields (tokens, keys) are marked Optional so Phase 1
    runs without them; future phases will validate them explicitly.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "AI DevOps Agent"
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = (
        "AI-powered DevOps agent for investigating failed deployments, "
        "analyzing logs, and suggesting fixes."
    )

    # ── API ───────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"

    # ── Server ────────────────────────────────────────────────────────────────
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # The default value targets the local Vite dev server.
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── GitHub Integration (Phase 2) ─────────────────────────────────────────
    GITHUB_TOKEN: str | None = None
    GITHUB_API_URL: str = "https://api.github.com"
    GITHUB_APP_ID: str | None = None
    GITHUB_WEBHOOK_SECRET: str | None = None

    # ── AI / LLM Provider (Phase 3) ──────────────────────────────────────────
    OMNIROUTE_BASE_URL: str = "http://localhost:20128/v1"
    OMNIROUTE_API_KEY: str | None = None
    OMNIROUTE_MODEL: str = "gpt-4o-mini"
    OMNIROUTE_TIMEOUT: int = 120
    AI_TEMPERATURE: float = 0.1
    MAX_LOG_CHARS: int = 50000
    MAX_CONTEXT_CHARS: int = 30000

    # ── Future: Kubernetes (Phase 4) ─────────────────────────────────────────
    KUBECONFIG: str | None = None

    # ── Future: Docker (Phase 4) ──────────────────────────────────────────────
    DOCKER_HOST: str | None = None


# Single shared instance – import this throughout the app
settings = Settings()
