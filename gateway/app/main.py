"""Minimal FastAPI app to expose AgentRunner endpoints for Tarea 4.

Note: This minimal app is focused on the agent runner. When the full
gateway skeleton (Tasks 1–3) is merged into feature/hybrid-dashboard,
this file can be aligned to the canonical structure and settings.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers.agent import router as agent_router


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Gateway (AgentRunner minimal)",
    version="0.1.0"
)

# Basic permissive CORS for local dev; can be tightened via settings later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "service": "ai-gateway-minimal"}
    )


app.include_router(agent_router, prefix="/api/v1/agent", tags=["agent"])

