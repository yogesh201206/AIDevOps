"""
AI DevOps Agent – FastAPI application entry point.

Bootstraps the application:
  1. Configures logging
  2. Creates the FastAPI instance with metadata
  3. Registers middleware (CORS)
  4. Mounts the versioned API router
  5. Adds a root informational endpoint

Run with:
    uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import settings
from app.github.exceptions import GitHubException
from app.logging_config import setup_logging

# ── Bootstrap logging before any other imports use the logger ──────────────
setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Application started | env=%s version=%s",
        settings.APP_ENV,
        settings.APP_VERSION,
    )
    yield
    logger.info("Application shutting down")


# ── FastAPI application ────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS middleware ────────────────────────────────────────────────────────
# Allow only the configured frontend origin(s).
# Use ALLOWED_ORIGINS in .env to extend (e.g. for staging URLs).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Global Exception Handlers ──────────────────────────────────────────────
@app.exception_handler(GitHubException)
async def github_exception_handler(request: Request, exc: GitHubException) -> JSONResponse:
    """Format all GitHub errors consistently without exposing internals."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


# ── Versioned API router ───────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ── Root endpoint ──────────────────────────────────────────────────────────
@app.get("/", summary="API information", tags=["Root"])
async def root() -> dict:
    """
    Return basic API metadata.

    Useful as a quick sanity check that the backend is reachable.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
    }

