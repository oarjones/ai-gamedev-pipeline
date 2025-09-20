"""Sessions endpoints: list, detail, resume."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.db import db
from app.services.sessions_service import sessions_service
from app.services.agent_runner import agent_runner


router = APIRouter()


@router.get("")
async def list_sessions(project_id: str, limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    rows = db.list_sessions(project_id, limit=limit)
    return [
        {
            "id": s.id,
            "project_id": s.project_id,
            "provider": s.provider,
            "startedAt": s.started_at.isoformat() + "Z",
            "endedAt": s.ended_at.isoformat() + "Z" if s.ended_at else None,
            "hasSummary": bool(s.summary_text),
        }
        for s in rows
    ]


@router.get("/{session_id}")
async def get_session(session_id: int, recent: int = Query(10, ge=1, le=100)) -> Dict[str, Any]:
    s = db.get_user_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    msgs = db.list_agent_messages(session_id, limit=recent)
    arts = db.list_artifacts(session_id, limit=20)
    return {
        "id": s.id,
        "project_id": s.project_id,
        "provider": s.provider,
        "startedAt": s.started_at.isoformat() + "Z",
        "endedAt": s.ended_at.isoformat() + "Z" if s.ended_at else None,
        "summary": s.summary_text,
        "recentMessages": [
            {"role": m.role, "content": m.content, "tool": m.tool_name, "ts": m.ts.isoformat() + "Z"}
            for m in msgs
        ],
        "artifacts": [{"type": a.type, "path": a.path, "ts": a.ts.isoformat() + "Z"} for a in arts],
    }


@router.post("/{session_id}/resume")
async def resume_session(session_id: int) -> Dict[str, Any]:
    s = db.get_user_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    # Build context pack for this specific session
    cp = sessions_service.build_context_pack(s.project_id, session_id=session_id)
    context_pack = {
        "project_manifest": cp.project_manifest,
        "plan_of_record": cp.plan_of_record,
        "last_summary": cp.last_summary,
        "recent_messages": cp.recent_messages,
        "artifacts": cp.artifacts,
    }
    # Start runner with provider and context pack
    cwd = Path("gateway/projects") / s.project_id
    try:
        rs = await agent_runner.start(cwd, provider="gemini_cli", context_pack=context_pack)  # type: ignore[arg-type]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "resumed": True,
        "sessionId": session_id,
        "runner": {"running": rs.running, "pid": rs.pid, "cwd": rs.cwd},
    }

