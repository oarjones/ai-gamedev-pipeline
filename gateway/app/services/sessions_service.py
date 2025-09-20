from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.db import db, SessionDB, AgentMessageDB, ArtifactDB


@dataclass
class ContextPack:
    project_manifest: Optional[str]
    plan_of_record: Optional[str]
    last_summary: Optional[str]
    recent_messages: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]


class SessionsService:
    def __init__(self) -> None:
        self.summary_every_n_messages = 20
        self.summary_every_k_toolcalls = 5

    # ---- sessions ----
    def start_session(self, project_id: str, provider: str = "gemini_cli") -> SessionDB:
        return db.create_session(project_id, provider)

    def end_session(self, session_id: int) -> None:
        db.end_session(session_id)

    # ---- messages ----
    def add_user_message(self, session_id: int, content: str) -> AgentMessageDB:
        return db.add_agent_message(AgentMessageDB(session_id=session_id, role="user", content=str(content or "")))

    def add_assistant_message(self, session_id: int, content: str) -> AgentMessageDB:
        return db.add_agent_message(AgentMessageDB(session_id=session_id, role="assistant", content=str(content or "")))

    def add_tool_call(self, session_id: int, name: str, args: Dict[str, Any]) -> AgentMessageDB:
        return db.add_agent_message(AgentMessageDB(session_id=session_id, role="tool", content="tool_call", tool_name=name, tool_args_json=json.dumps(args, ensure_ascii=False)))

    def add_tool_result(self, session_id: int, name: str, result: Dict[str, Any], ok: bool = True) -> AgentMessageDB:
        payload = {"ok": bool(ok), "result": result}
        return db.add_agent_message(AgentMessageDB(session_id=session_id, role="tool", content="tool_result", tool_name=name, tool_result_json=json.dumps(payload, ensure_ascii=False)))

    # ---- artifacts ----
    def add_artifact(self, session_id: int, type_: str, path: str, meta: Optional[Dict[str, Any]] = None) -> ArtifactDB:
        return db.add_artifact(ArtifactDB(session_id=session_id, type=type_, path=path, meta_json=json.dumps(meta or {}, ensure_ascii=False)))

    # ---- summary ----
    def maybe_generate_summary(self, session_id: int) -> Optional[str]:
        msgs = list(reversed(db.list_agent_messages(session_id, limit=100)))
        if len(msgs) < self.summary_every_n_messages:
            return None
        tools = [m for m in msgs if m.role == "tool"]
        if len(tools) < self.summary_every_k_toolcalls:
            return None
        # Simple heuristic summary
        last_user = next((m.content for m in reversed(msgs) if m.role == "user"), "")
        tool_stats: Dict[str, int] = {}
        for m in tools:
            if m.tool_name:
                tool_stats[m.tool_name] = tool_stats.get(m.tool_name, 0) + 1
        lines = ["# Session Summary", "", f"Messages: {len(msgs)}", f"Tool calls: {len(tools)}"]
        if tool_stats:
            lines.append("Tools used:")
            for k, v in tool_stats.items():
                lines.append(f"- {k}: {v}")
        if last_user:
            lines.append("")
            lines.append("Last user request:")
            lines.append(last_user[:500])
        summary = "\n".join(lines)
        db.update_session_summary(session_id, summary)
        return summary

    # ---- context pack ----
    def build_context_pack(self, project_id: str, recent_messages: int = 10, session_id: Optional[int] = None) -> ContextPack:
        proj_dir = Path("gateway/projects") / project_id
        manifest = None
        por = None
        try:
            pm = proj_dir / "project_manifest.yaml"
            if pm.exists():
                manifest = pm.read_text(encoding="utf-8")
        except Exception:
            pass
        try:
            pr = proj_dir / "plan_of_record.yaml"
            if pr.exists():
                por = pr.read_text(encoding="utf-8")
        except Exception:
            pass
        
        last = db.get_user_session(session_id) if session_id else db.get_last_session(project_id)
        last_summary = getattr(last, "summary_text", None) if last else None
        # Messages from last session
        recent: List[Dict[str, Any]] = []
        if last:
            for m in db.list_agent_messages(last.id, limit=recent_messages):
                try:
                    recent.append({"role": m.role, "content": m.content, "tool": m.tool_name})
                except Exception:
                    continue
        arts: List[Dict[str, Any]] = []
        if last:
            for a in db.list_artifacts(last.id, limit=20):
                arts.append({"type": a.type, "path": a.path})
        return ContextPack(project_manifest=manifest, plan_of_record=por, last_summary=last_summary, recent_messages=recent, artifacts=arts)


sessions_service = SessionsService()
