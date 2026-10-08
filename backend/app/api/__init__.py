"""
API package initialiser.

Exposes a single ``api_router`` that aggregates all versioned sub-routers.
Mount this in ``main.py`` under the ``API_V1_PREFIX`` setting.

Adding a new feature router in future phases:
    1. Create  app/api/<feature>.py  with its own ``APIRouter``.
    2. Import the router here and register it with ``api_router``.
"""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.github import router as github_router
from app.api.ai import router as ai_router
from app.api.investigations import router as investigations_router

# Top-level v1 router – all feature routers are included here
api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(github_router)
api_router.include_router(ai_router)
api_router.include_router(investigations_router)

# Future phase routers – uncomment as implemented:
# from app.api.agents   import router as agents_router
# from app.api.docker   import router as docker_router
# from app.api.kube     import router as kube_router
# from app.api.fixes    import router as fixes_router
