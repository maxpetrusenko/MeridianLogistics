from __future__ import annotations

from fastapi import FastAPI
import uvicorn

from backend.app.api.router import api_router
from backend.app.config import load_config


def create_app() -> FastAPI:
    config = load_config()
    app = FastAPI(
        title="Meridian Logistics API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.config = config
    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
