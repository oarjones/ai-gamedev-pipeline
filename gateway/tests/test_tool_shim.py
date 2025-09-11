import asyncio
import json
import types

import pytest

from app.services.agent_runner import AgentRunner
from app.services.providers.base import SessionCtx, ProviderEvent


class FakeProvider:
    def __init__(self):
        self._cb = None
        self.sent = []

    def onEvent(self, cb):
        self._cb = cb

    async def start(self, session: SessionCtx):
        return None

    async def stop(self):
        return None

    async def send(self, user_message: str):
        # Capture messages injected back (tool_result)
        self.sent.append(user_message)

    def status(self):
        return {"name": "fake", "running": True, "pid": 123}


def test_tool_call_validation_and_injection(monkeypatch, tmp_path):
    async def _run():
        ar = AgentRunner()
        ar._provider = FakeProvider()
        ar._provider_name = "fake"
        ar._project_id = "proj1"
        ar._tool_catalog = {
            "functionSchema": [
                {"name": "blender.create_primitive", "description": "", "parameters": {"type": "object", "properties": {"type": {"type": "string"}}, "required": ["type"], "additionalProperties": False}}
            ]
        }
        # Avoid external timeline side effects
        async def _noop(*a, **k):
            return {"status": "ok"}
        import app.services.timeline as tl
        monkeypatch.setattr(tl, "timeline_service", types.SimpleNamespace(record_event=_noop))

        # Mock mcp_client.run_tool
        async def _fake_run_tool(project_id, name, args, correlation_id=None):
            return {"ok": True, "echo": {"name": name, "args": args}}

        import app.services.mcp_client as m
        monkeypatch.setattr(m, "mcp_client", types.SimpleNamespace(run_tool=_fake_run_tool))

        # Begin a turn
        await ar.send("hola", correlation_id="corr-1")
        # Simulate provider emitting tool_call (directly via shim)
        await ar._handle_tool_call({"name": "blender.create_primitive", "args": {"type": "cube"}}, project_id=ar._project_id, corr="corr-1")

        # Verify provider received tool_result JSON
        assert ar._provider.sent, "Expected tool_result sent back to provider"
        payload = json.loads(ar._provider.sent[-1])
        assert "tool_result" in payload
        assert payload["tool_result"]["ok"] is True

    asyncio.run(_run())


def test_tool_call_limit(monkeypatch):
    async def _run():
        ar = AgentRunner()
        ar._provider = FakeProvider()
        ar._provider_name = "fake"
        ar._project_id = "proj1"
        ar._tool_catalog = {"functionSchema": []}
        ar._tool_max_calls = 1

        await ar.send("hola", correlation_id="c2")
        # First call increments counter
        await ar._handle_tool_call({"name": "x", "args": {}}, project_id=ar._project_id, corr="c2")
        # Second call exceeds and should send error tool_result
        await ar._handle_tool_call({"name": "x", "args": {}}, project_id=ar._project_id, corr="c2")
        assert ar._provider.sent, "Expected error tool_result on limit exceeded"
        data = json.loads(ar._provider.sent[-1])
        assert data["tool_result"]["ok"] is False
        assert "maxCallsPerTurn" in data["tool_result"]["error"]

    asyncio.run(_run())
