from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth_routes import router as auth_router
from app.api.admin_routes import router as admin_router
from app.api.conversation_routes import router as conversation_router
from app.api.demo_routes import router as demo_router
from app.api.agent_routes import router as agent_router
from app.api.openai_routes import router as openai_router
from app.api.mcp_routes import router as mcp_router
from app.api.schedule_routes import router as schedule_router
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
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(conversation_router)
    app.include_router(schedule_router)
    app.include_router(mcp_router)
    app.include_router(agent_router)
    app.include_router(openai_router)
    app.include_router(demo_router)

    @app.middleware("http")
    async def demo_embed_frame_policy(request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/demo"):
            return response
        allowed = [origin.strip() for origin in settings.demo_embed_allowed_origins.split(",") if origin.strip()]
        if allowed:
            frame_src = " ".join(["'self'", *allowed])
            response.headers["Content-Security-Policy"] = f"frame-ancestors {frame_src}"
        return response

    # In single-service deployments we serve the compiled frontend from FastAPI.
    frontend_dist = Path('/app/frontend_dist')
    if frontend_dist.exists():
        index_html = frontend_dist / 'index.html'

        @app.get('/demo', include_in_schema=False)
        async def demo_spa() -> FileResponse:
            if not index_html.is_file():
                raise HTTPException(status_code=404, detail='Not Found')
            return FileResponse(index_html)

        app.mount('/', StaticFiles(directory=str(frontend_dist), html=True), name='frontend')

    return app


app = create_app()
