"""
VidScholar Backend - Application Entry Point
================================================
This is the FastAPI application factory and entry point.
It wires together:
  - CORS middleware (so the Vite frontend on a different port can call this API)
  - Logging configuration
  - Global exception handling for unhandled errors
  - The /health endpoint used by the frontend to verify backend connectivity
  - Router registration (routers will be added in later phases)
"""

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db.session import init_db
from app.api.routers import videos, chat, notes

# Initialize logging as early as possible, before anything else runs.
setup_logging()
logger = logging.getLogger("vidscholar")


def create_app() -> FastAPI:
    """
    Application factory pattern.
    Using a factory (instead of a bare module-level `app`) makes the app
    easier to test and easier to configure differently per environment.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="AI Powered YouTube Learning Assistant - Backend API",
        version=settings.API_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # ------------------------------------------------------------------
    # CORS Configuration
    # ------------------------------------------------------------------
    # The frontend (React/Vite) runs on a separate origin (e.g. localhost:5173)
    # than the backend (e.g. localhost:8000). Without CORS configured, the
    # browser will block all requests from the frontend to this API.
    # settings.BACKEND_CORS_ORIGINS is parsed from the .env file.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS_LIST,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Global Exception Handler
    # ------------------------------------------------------------------
    # Catches any unhandled exception so the API never leaks a raw 500
    # traceback to the client. Logs the full error server-side instead.
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Internal server error. Please try again later.",
            },
        )

    # ------------------------------------------------------------------
    # Startup: initialize database tables
    # ------------------------------------------------------------------
    # Suitable for SQLite/dev. In production with Postgres, this would
    # typically be replaced by an Alembic migration step instead.
    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(videos.router)
    app.include_router(chat.router)
    app.include_router(notes.router)
    # ------------------------------------------------------------------
    # Health Check Endpoint
    # ------------------------------------------------------------------
    # The frontend pings this on load to confirm backend connectivity.
    # Kept directly in main.py (rather than a router) since it has no
    # business logic and is foundational infrastructure.
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "ok",
            "service": settings.PROJECT_NAME,
            "version": settings.API_VERSION,
            "environment": settings.ENVIRONMENT,
        }

    @app.get("/", tags=["Health"])
    async def root():
        return {
            "message": f"{settings.PROJECT_NAME} API is running.",
            "docs": "/api/docs",
            "health": "/health",
        }

    logger.info(f"{settings.PROJECT_NAME} application initialized successfully.")
    return app


# Module-level app instance used by uvicorn: `uvicorn app.main:app --reload`
app = create_app()
