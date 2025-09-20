"""Main FastAPI application for AI Gateway."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import CreateProject, Envelope, EventType, Project
from app.ws.events import websocket_endpoint
from app.security import require_api_key

# Configure logging
try:
    from app.logging_config import setup_logging
    setup_logging("INFO")
except Exception:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    logger.info("AI Gateway starting up...")
    logger.info(f"Server config: {settings.server.host}:{settings.server.port}")
    logger.info(f"CORS origins: {settings.cors.allow_origins}")
    logger.info(f"Auth config: require_api_key={settings.auth.require_api_key}, api_key={settings.auth.api_key[:8]}...")
    yield
    logger.info("AI Gateway shutting down...")


# Create FastAPI app WITHOUT global dependencies
# We'll apply auth per router instead
app = FastAPI(
    title="AI Gateway",
    description="AI Gateway service for ai-gamedev-pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)

# Health endpoint WITHOUT authentication
@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint (no auth required)."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "ai-gateway",
            "version": "0.1.0",
            "auth_enabled": settings.auth.require_api_key,
        }
    )

# Root endpoint WITHOUT authentication
@app.get("/")
async def root() -> JSONResponse:
    """Root endpoint (no auth required)."""
    return JSONResponse(
        status_code=200,
        content={
            "service": "ai-gateway",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health"
        }
    )

@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """WebSocket endpoint for event streaming."""
    await websocket_endpoint(websocket)


# Include routers WITH authentication dependency
from app.routers import projects_router, agent_router, chat_router, timeline_router, tools_router, context_router, config_router, deps_router
from app.routers import sessions as sessions_router
from app.routers import manifest as manifest_router
from app.routers import tasks as tasks_router
from app.routers.health import router as health_router
from app.routers.pipeline import router as pipeline_router
from app.routers.system import router as system_router

# Apply auth dependency to protected routers
_auth_deps = [Depends(require_api_key)] if settings.auth.require_api_key else []

app.include_router(
    projects_router,
    prefix="/api/v1/projects",
    tags=["projects"],
    dependencies=_auth_deps
)

# Agent runner endpoints
app.include_router(
    agent_router,
    prefix="/api/v1/agent",
    tags=["agent"],
    dependencies=_auth_deps
)

# Chat endpoints
app.include_router(
    chat_router,
    prefix="/api/v1/chat",
    tags=["chat"],
    dependencies=_auth_deps
)

# Timeline endpoints
app.include_router(
    timeline_router,
    prefix="/api/v1/timeline",
    tags=["timeline"],
    dependencies=_auth_deps
)

# Tools and action execution
app.include_router(
    tools_router,
    prefix="/api/v1",
    tags=["tools", "actions"],
    dependencies=_auth_deps
)

# Context (scene, screenshots)
app.include_router(
    context_router,
    prefix="/api/v1",
    tags=["context"],
    dependencies=_auth_deps
)

# System (process orchestration)
app.include_router(
    system_router,
    prefix="/api/v1",
    tags=["system"],
    dependencies=_auth_deps
)

# Config (centralized)
app.include_router(
    config_router,
    prefix="/api/v1",
    tags=["config"],
    dependencies=_auth_deps
)

# Dependencies / venvs
app.include_router(
    deps_router,
    prefix="/api/v1",
    tags=["dependencies"],
    dependencies=_auth_deps
)

# Health router - NO AUTH required for health endpoints
app.include_router(
    health_router,
    prefix="/api/v1",
    tags=["health"]
)

# Pipeline
app.include_router(
    pipeline_router,
    prefix="/api/v1",
    tags=["pipeline"],
    dependencies=_auth_deps
)

# Sessions
app.include_router(
    sessions_router.router,
    prefix="/api/v1/sessions",
    tags=["sessions"],
    dependencies=_auth_deps
)

# Project manifest / plan
app.include_router(
    manifest_router.router,
    prefix="/api/v1/projects",
    tags=["project-manifest"],
    dependencies=_auth_deps
)

# Tasks
app.include_router(
    tasks_router.router,
    prefix="/api/v1/tasks",
    tags=["tasks"],
    dependencies=_auth_deps
)

# Plans (from Tarea 5)
from app.routers import plans as plans_router

app.include_router(
    plans_router.router,
    prefix="/api/v1/plans",
    tags=["plans"],
    dependencies=_auth_deps
)

# Artifacts (from Tarea 7)
from app.routers import artifacts as artifacts_router

app.include_router(
    artifacts_router.router,
    prefix="/api/v1", # Using root prefix for task-nested routes
    tags=["artifacts"],
    dependencies=_auth_deps
)

# Context (from Tarea 13)
from app.routers import context as context_router

app.include_router(
    context_router.router,
    prefix="/api/v1",
    tags=["context"],
    dependencies=_auth_deps
)


# Dummy endpoint to include Envelope model in OpenAPI schema
@app.post("/api/v1/events", tags=["contracts"], dependencies=_auth_deps)
async def send_event_schema(envelope: Envelope) -> dict:
    """Send an event through the API.
    
    This endpoint is included for API contract documentation.
    Events are typically sent via WebSocket at /ws/events.
    """
    return {"status": "received"}
