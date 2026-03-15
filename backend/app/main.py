from __future__ import annotations

from functools import lru_cache
from fastapi import FastAPI
import uvicorn

from backend.app.api.router import api_router
from backend.app.autonomy.service import BoundedAutonomyService
from backend.app.config import load_config
from backend.app.confirmation_grant.store import ConfirmationGrantStore
from backend.app.db.read_repository import ReadRepository
from backend.app.gateway.idempotency_store import IdempotencyMapping
from backend.app.jobs.store import InMemoryJobStore
from backend.app.session.store import InMemorySessionStore
from backend.app.storage.service import StorageService


def create_app() -> FastAPI:
    config = load_config()
    app = FastAPI(
        title="Meridian Logistics API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.config = config
    app.state.read_repository = ReadRepository()
    app.state.session_store = InMemorySessionStore(database_url=config.state_database_url)
    app.state.job_store = InMemoryJobStore(database_url=config.state_database_url)
    app.state.idempotency_store: IdempotencyMapping = {}
    app.state.confirmation_grant_store = ConfirmationGrantStore(database_url=config.state_database_url)
    app.state.storage_service = StorageService.from_env()
    app.state.autonomy_service = BoundedAutonomyService(config)
    app.include_router(api_router)
    return app


@lru_cache(maxsize=1)
def _default_app() -> FastAPI:
    return create_app()


async def app(scope: dict, receive: object, send: object) -> None:
    await _default_app()(scope, receive, send)


if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
