"""
Tests for health-check endpoints.

Covers:
  GET /                    – root information endpoint
  GET /api/v1/health       – liveness probe
  GET /api/v1/health/ready – readiness probe
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
async def client() -> AsyncClient:
    """Provide an async test client wired to the ASGI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ── Root endpoint ──────────────────────────────────────────────────────────

class TestRoot:
    async def test_status_code(self, client: AsyncClient) -> None:
        response = await client.get("/")
        assert response.status_code == 200

    async def test_response_contains_name(self, client: AsyncClient) -> None:
        data = (await client.get("/")).json()
        assert data["name"] == settings.APP_NAME

    async def test_response_contains_version(self, client: AsyncClient) -> None:
        data = (await client.get("/")).json()
        assert "version" in data

    async def test_response_contains_health_path(self, client: AsyncClient) -> None:
        data = (await client.get("/")).json()
        assert "health" in data


# ── Liveness ───────────────────────────────────────────────────────────────

class TestHealthLiveness:
    async def test_status_code(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_status_value(self, client: AsyncClient) -> None:
        data = (await client.get("/api/v1/health")).json()
        assert data["status"] == "healthy"

    async def test_service_name(self, client: AsyncClient) -> None:
        data = (await client.get("/api/v1/health")).json()
        assert data["service"] == "ai-devops-agent-backend"

    async def test_response_is_json(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/health")
        assert response.headers["content-type"].startswith("application/json")


# ── Readiness ──────────────────────────────────────────────────────────────

class TestHealthReadiness:
    async def test_status_code(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 200

    async def test_status_value(self, client: AsyncClient) -> None:
        data = (await client.get("/api/v1/health/ready")).json()
        assert data["status"] == "ready"

    async def test_service_name(self, client: AsyncClient) -> None:
        data = (await client.get("/api/v1/health/ready")).json()
        assert data["service"] == "ai-devops-agent-backend"

    async def test_environment_field(self, client: AsyncClient) -> None:
        data = (await client.get("/api/v1/health/ready")).json()
        assert "environment" in data

    async def test_version_field(self, client: AsyncClient) -> None:
        data = (await client.get("/api/v1/health/ready")).json()
        assert "version" in data

    async def test_checks_field(self, client: AsyncClient) -> None:
        data = (await client.get("/api/v1/health/ready")).json()
        assert "checks" in data
        assert data["checks"]["application"] == "ok"
