"""Chat service handling persistence and event broadcasting.

Responsibilities:
- Persist user/agent messages in SQLite (via DatabaseManager)
- Publish Envelope(type=chat) events over WS as lines arrive from the CLI
- Enforce basic constraints (max length) from settings

Notes:
- For now, AgentRunner returns a single line per send(). If streaming becomes
  multi-line, this service can iterate and publish each line.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4
from pathlib import Path

from app.config import settings
from app.db import ChatMessageDB, db
from app.models import Envelope, EventType
from app.ws.events import manager


logger = logging.getLogger(__name__)


@dataclass
class SendJob:
    project_id: str
    text: str
    correlation_id: Optional[str]


class ChatService:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[SendJob] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker(), name="chat-worker")

    async def send_user_message(self, project_id: str, text: str, correlation_id: Optional[str] = None) -> dict:
        """Validate, enqueue user message for processing, and return ack.

        Returns a dict with basic metadata (msgId).
        """
        if not text:
            raise ValueError("Message text must not be empty")

        max_len = settings.chat.max_message_length
        if len(text) > max_len:
            raise ValueError(f"Message exceeds max length ({max_len})")

        job = SendJob(project_id=project_id, text=text, correlation_id=correlation_id)
        await self._queue.put(job)
        self._ensure_worker()
        msg_id = str(uuid4())
        # Persist user message immediately
        self._persist_message(project_id, "user", text, msg_id)
        # Broadcast user message to WS clients
        await self._broadcast_chat(project_id, "user", text, msg_id, correlation_id)
        return {"queued": True, "msgId": msg_id}

    async def get_history(self, project_id: str, limit: Optional[int] = None) -> list[dict]:
        lim = int(limit or settings.chat.history_limit_default)
        rows = db.list_chat_messages(project_id, limit=lim)
        return [
            {
                "msgId": r.msg_id,
                "projectId": r.project_id,
                "role": r.role,
                "content": r.content,
                "createdAt": r.created_at.isoformat() + "Z",
            }
            for r in rows
        ]

    async def _worker(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                # Send to agent CLI and stream response lines (single-line for now)
                from app.services.agent_runner import agent_runner
                out = await agent_runner.send(job.text, correlation_id=job.correlation_id)
                agent_msg_id = str(uuid4())
                self._persist_message(job.project_id, "agent", out, agent_msg_id)
                await self._broadcast_chat(job.project_id, "agent", out, agent_msg_id, job.correlation_id)

                # Try to detect plan JSON in the agent output and orchestrate
                plan = self._maybe_parse_plan(out)
                if plan is not None:
                    # Fire-and-forget orchestration; errors are broadcast inside orchestrator
                    asyncio.create_task(self._run_plan(job.project_id, plan, job.correlation_id))
            except Exception as e:
                logger.error("Chat worker error: %s", e)
            finally:
                self._queue.task_done()

    async def _broadcast_chat(self, project_id: str, role: str, content: str, msg_id: str, correlation_id: Optional[str]) -> None:
        env = Envelope(
            type=EventType.CHAT,
            projectId=project_id,
            payload={
                "role": role,
                "content": content,
                "msgId": msg_id,
                "correlationId": correlation_id,
            },
        )
        try:
            await manager.broadcast(json.dumps(env.model_dump(by_alias=True, mode="json")))
        except Exception as e:
            logger.error("Failed to broadcast chat event: %s", e)

    def _persist_message(self, project_id: str, role: str, content: str, msg_id: str) -> None:
        try:
            db.add_chat_message(
                ChatMessageDB(
                    msg_id=msg_id,
                    project_id=project_id,
                    role=role,
                    content=content,
                )
            )
        except Exception as e:
            logger.error("Failed to persist chat message: %s", e)

    def _maybe_parse_plan(self, text: str) -> Optional[list[dict]]:
        s = (text or "").strip()
        try:
            if s.startswith("["):
                data = json.loads(s)
                if isinstance(data, list) and all(isinstance(x, dict) for x in data):
                    # Validate each step has 'tool'
                    if all("tool" in x for x in data):
                        return data  # type: ignore
        except Exception:
            return None
        return None

    async def _run_plan(self, project_id: str, plan: list[dict], correlation_id: Optional[str]) -> None:
        try:
            from app.services.actions import action_orchestrator
            await action_orchestrator.run_plan(project_id, plan, correlation_id=correlation_id)
        except Exception as e:
            logger.error("Orchestrator error: %s", e)


# Singleton instance
chat_service = ChatService()
