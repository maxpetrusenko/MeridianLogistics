from fastapi import APIRouter

from backend.app.api.routes.actions import router as actions_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.sessions import router as sessions_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(sessions_router)
api_router.include_router(jobs_router)
api_router.include_router(actions_router)
