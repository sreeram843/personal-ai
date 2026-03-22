from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)
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

    # In single-service deployments we serve the compiled frontend from FastAPI.
    frontend_dist = Path('/app/frontend_dist')
    if frontend_dist.exists():
        app.mount('/', StaticFiles(directory=str(frontend_dist), html=True), name='frontend')

    return app


app = create_app()
