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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    logger.info("AI Gateway starting up...")
    logger.info(f"Server config: {settings.server.host}:{settings.server.port}")
    logger.info(f"CORS origins: {settings.cors.allow_origins}")
    yield
    logger.info("AI Gateway shutting down...")


# Create FastAPI app
_deps = [Depends(require_api_key)] if settings.auth.require_api_key else []
app = FastAPI(
    title="AI Gateway",
    description="AI Gateway service for ai-gamedev-pipeline",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=_deps,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)

# No further overrides; WebSocket auth handled in websocket_endpoint


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "ai-gateway",
            "version": "0.1.0",
        }
    )


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """WebSocket endpoint for event streaming."""
    await websocket_endpoint(websocket)


# Include routers
from app.routers import projects_router, agent_router, chat_router, timeline_router, tools_router, context_router, config_router, deps_router
from app.routers.health import router as health_router
from app.routers.pipeline import router as pipeline_router
from app.routers.system import router as system_router

app.include_router(
    projects_router,
    prefix="/api/v1/projects",
    tags=["projects"]
)

# Agent runner endpoints
app.include_router(
    agent_router,
    prefix="/api/v1/agent",
    tags=["agent"]
)

# Chat endpoints
app.include_router(
    chat_router,
    prefix="/api/v1/chat",
    tags=["chat"]
)

# Timeline endpoints
app.include_router(
    timeline_router,
    prefix="/api/v1/timeline",
    tags=["timeline"]
)

# Tools and action execution
app.include_router(
    tools_router,
    prefix="/api/v1",
    tags=["tools", "actions"],
)

# Context (scene, screenshots)
app.include_router(
    context_router,
    prefix="/api/v1",
    tags=["context"],
)

# System (process orchestration)
app.include_router(
    system_router,
    prefix="/api/v1",
    tags=["system"],
)

# Config (centralized)
app.include_router(
    config_router,
    prefix="/api/v1",
    tags=["config"],
)

# Dependencies / venvs
app.include_router(
    deps_router,
    prefix="/api/v1",
    tags=["dependencies"],
)

# Health
app.include_router(
    health_router,
    prefix="/api/v1",
    tags=["health"],
)

# Pipeline
app.include_router(
    pipeline_router,
    prefix="/api/v1",
    tags=["pipeline"],
)


# Dummy endpoint to include Envelope model in OpenAPI schema
@app.post("/api/v1/events", tags=["contracts"])
async def send_event_schema(envelope: Envelope) -> dict:
    """Send an event through the API.
    
    This endpoint is included for API contract documentation.
    Events are typically sent via WebSocket at /ws/events.
    """
    raise NotImplementedError("Event sending via HTTP not implemented yet")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
    )
