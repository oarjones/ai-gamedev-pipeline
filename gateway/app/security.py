"""Minimal security: API key header validation and helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer
from typing import Optional

from app.config import settings

# Create security scheme
security = HTTPBearer(auto_error=False)

async def require_api_key(request: Request) -> None:
    """Validate API key from request headers."""
    if not settings.auth.require_api_key:
        return
    
    # Check X-API-Key header first
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    
    # If not found, try Authorization header
    if not api_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]  # Remove "Bearer " prefix
    
    if not api_key or api_key != settings.auth.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing or invalid API key",
            headers={"WWW-Authenticate": "Bearer"}
        )