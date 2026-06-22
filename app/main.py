from __future__ import annotations

from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.auth_routes import router as auth_router
from app.api.conversation_routes import router as conversation_router
from app.api.routes import router
from app.core.config import get_settings
from app.core.deps import get_vector_store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ensure Qdrant collection exists before serving traffic."""
    get_vector_store().ensure_collection()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    if origins:
        allow_credentials = True
        if "*" in origins:
            allow_credentials = False
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(conversation_router)

    # In single-service deployments we serve the compiled frontend from FastAPI.
    frontend_dist = Path('/app/frontend_dist')
    if frontend_dist.exists():
        app.mount('/', StaticFiles(directory=str(frontend_dist), html=True), name='frontend')

    return app


app = create_app()
