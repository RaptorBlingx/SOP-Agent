"""FastAPI application assembly (Section 6).

Mounts all route modules, configures CORS, lifespan, and health check.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.api.schemas import HealthResponse

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown."""
    settings = get_settings()
    setup_logging()
    settings.ensure_directories()

    from app.core.database import init_database
    await init_database()

    logger.info("SOP Agent API starting — provider=%s", settings.model_provider)
    yield
    logger.info("SOP Agent API shutting down")


def create_app() -> FastAPI:
    """Factory function for the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="SOP Agent API",
        version="1.2.0",
        description="AI-powered Standard Operating Procedure execution agent",
        lifespan=lifespan,
    )

    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routes
    from app.api.routes.ingest import router as ingest_router
    from app.api.routes.execute import router as execute_router
    from app.api.routes.intervene import router as intervene_router
    from app.api.routes.report import router as report_router
    from app.api.routes.session import router as session_router

    app.include_router(ingest_router, tags=["Ingestion"])
    app.include_router(execute_router, tags=["Execution"])
    app.include_router(intervene_router, tags=["Intervention"])
    app.include_router(report_router, tags=["Report"])
    app.include_router(session_router, tags=["Sessions"])

    # MCP SSE transport
    from app.mcp.sse import router as mcp_router
    app.include_router(mcp_router, tags=["MCP"])

    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check() -> HealthResponse:
        return HealthResponse()

    return app


app = create_app()
