"""Minimal security: API key header validation and helpers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.config import settings


async def require_api_key(request: Request) -> None:
    if not settings.auth.require_api_key:
        return
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != settings.auth.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid API key")

