"""
FastAPI application entrypoint: logging, DB init, CORS, API routes, optional SPA.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router
from app.config import _project_root, clear_settings_cache, get_settings
from app.schemas.api import HealthResponse
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: logging, directories."""
    clear_settings_cache()   # always re-read .env on startup
    settings = get_settings()
    setup_logging(settings.log_level)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.templates_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Started %s (env=%s)", settings.app_name, settings.env)
    yield
    logger.info("Shutdown %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_root() -> HealthResponse:
        """Backward-compatible health check at root (e.g. load balancers)."""
        return HealthResponse(status="ok", version=__version__)

    app.include_router(router, prefix="/api")

    dist = _project_root() / "frontend" / "dist"
    if dist.is_dir() and (dist / "index.html").is_file():
        assets_dir = dist / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="spa_assets",
            )

        @app.get("/")
        async def spa_index() -> FileResponse:
            """Serve the Vite-built SPA (production: ``npm run build`` in ``frontend/``)."""
            return FileResponse(dist / "index.html")

        logger.info("Serving SPA index from %s", dist)
    return app


app = create_app()
