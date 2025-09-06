"""Timeline service: persistence, listing, and basic revert stub.

Represents timeline entries in a normalized API shape:
- id: int
- projectId: str
- type: str (e.g., 'step', 'event:<kind>')
- payload: dict
- ts: ISO-8601 timestamp
- relatedIds: list[str]

Persistence uses TimelineEventDB from app.db. For generic events, we encode:
- tool = f"event:{type}"
- args_json = {"relatedIds": [...]} as JSON
- result_json = payload as JSON
- status = "event"
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db import TimelineEventDB, db
from app.models import Envelope, EventType
from app.ws.events import manager
from app.services.mcp_client import mcp_client


logger = logging.getLogger(__name__)


class TimelineService:
    def _to_api_item(self, ev: TimelineEventDB) -> dict:
        # Derive type
        ev_type = ev.tool if ev.tool else ""
        if ev_type.startswith("event:"):
            ev_type_api = ev_type.split(":", 1)[1]
        else:
            ev_type_api = "step"

        # payload selection
        try:
            payload = json.loads(ev.result_json) if ev.result_json else None
        except Exception:
            payload = None
        # related ids
        related = []
        try:
            aj = json.loads(ev.args_json) if ev.args_json else {}
            related = aj.get("relatedIds", []) or []
        except Exception:
            related = []
        ts = (ev.finished_at or ev.started_at or datetime.utcnow()).isoformat() + "Z"
        return {
            "id": ev.id,
            "projectId": ev.project_id,
            "type": ev_type_api,
            "payload": payload,
            "ts": ts,
            "relatedIds": related,
        }

    async def list(self, project_id: str, limit: int = 100) -> List[dict]:
        rows = db.list_timeline_events(project_id, limit=limit)
        return [self._to_api_item(r) for r in rows]

    async def record_event(
        self,
        project_id: str,
        type_: str,
        payload: Dict[str, Any] | None = None,
        related_ids: List[str] | None = None,
        correlation_id: Optional[str] = None,
    ) -> dict:
        payload = payload or {}
        related_ids = related_ids or []
        ev = db.add_timeline_event(
            TimelineEventDB(
                project_id=project_id,
                step_index=-1,
                tool=f"event:{type_}",
                args_json=json.dumps({"relatedIds": related_ids}, ensure_ascii=False),
                status="event",
                result_json=json.dumps(payload, ensure_ascii=False),
                correlation_id=correlation_id,
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
        )
        item = self._to_api_item(ev)

        # WS broadcast
        env = Envelope(
            type=EventType.TIMELINE,
            projectId=project_id,
            payload={
                "index": item["id"],
                "tool": item["type"],
                "status": "event",
                "result": item["payload"],
                "timestamp": item["ts"],
                "correlationId": correlation_id,
            },
        )
        try:
            await manager.broadcast(json.dumps(env.model_dump(by_alias=True, mode="json")))
        except Exception as e:
            logger.error("Failed to broadcast timeline event: %s", e)
        return item

    async def revert(self, event_id: int) -> dict:
        """Attempt a very basic revert. If not supported, enqueue/pending.

        Returns dict with { status: 'pending'|'reverted', note?: str }
        """
        ev = db.get_timeline_event(event_id)
        if not ev:
            return {"status": "error", "error": "event not found"}

        # Derive type/tool and minimal revert attempt
        ev_tool = ev.tool or ""
        reverted = False
        note = None
        try:
            # Simple case: try to undo a Unity instantiation by asset path
            if ev_tool == "unity.instantiate_fbx" and ev.result_json:
                data = json.loads(ev.result_json)
                asset = data.get("instantiated")
                if isinstance(asset, str) and asset:
                    code = (
                        "using UnityEditor; using UnityEngine;\n"
                        f"var go = AssetDatabase.LoadAssetAtPath<GameObject>(@\"{asset}\");\n"
                        "if (go!=null){ var instances = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);\n"
                        "foreach (var i in instances){ if (i.name==go.name){ Object.DestroyImmediate(i); } } }\n"
                    )
                    from mcp_unity_bridge import mcp_adapter as _adapter  # type: ignore
                    s = await _adapter.unity_command(code)
                    # If adapter returns JSON ok, mark reverted; we ignore content parsing here
                    reverted = True
                    note = "Destroyed GameObjects matching asset name"
        except Exception as e:
            logger.warning("Revert attempt failed: %s", e)

        status = "reverted" if reverted else "pending"
        # Record a revert-requested/reverted event linked to original
        await self.record_event(
            ev.project_id,
            f"revert-{status}",
            payload={"target": ev.id, "note": note},
            related_ids=[str(ev.id)],
            correlation_id=ev.correlation_id,
        )
        return {"status": status, "note": note}


# Singleton
timeline_service = TimelineService()

