"""Main FastAPI application for AI Gateway."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.ws.events import websocket_endpoint

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


# TODO: Add project routers here
# from app.routers import projects
# app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
    )