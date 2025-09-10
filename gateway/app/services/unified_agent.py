"""Unified Agent Runner supporting 'gemini' (CLI/MCP), 'openai', and 'claude'.

Delegates Gemini to existing AgentRunner (CLI). For OpenAI/Claude, uses
direct HTTP calls and streams responses into the chat pipeline.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.services.agent_runner import agent_runner as _gemini_runner
from app.services.config_service import get_all
from app.services.process_manager import process_manager


@dataclass
class AgentStatus:
    agentType: Optional[str]
    running: bool
    pid: Optional[int]
    cwd: Optional[str]
    lastError: Optional[str]


class UnifiedAgent:
    def __init__(self) -> None:
        self._active_type: Optional[str] = None
        self._project_id: Optional[str] = None
        self._cwd: Optional[Path] = None
        self._openai: Optional[dict] = None
        self._claude: Optional[dict] = None
        self._last_error: Optional[str] = None

    async def start(self, cwd: Path, agent_type: str) -> AgentStatus:
        at = (agent_type or "gemini").lower()
        if at not in ("gemini", "openai", "claude"):
            raise ValueError("Unsupported agentType")
        self._cwd = Path(cwd)
        self._project_id = self._cwd.name
        self._last_error = None

        if at == "gemini":
            # Validate preconditions: bridges up
            st = process_manager.status()
            names = {s.get("name") for s in st if s.get("running")}
            if not {"unity_bridge", "blender_bridge"}.issubset(names):
                self._last_error = "Bridges not ready (require unity_bridge and blender_bridge)"
                raise RuntimeError(self._last_error)
            rs = await _gemini_runner.start(self._cwd)
            self._active_type = "gemini"
            return AgentStatus(agentType=self._active_type, running=rs.running, pid=rs.pid, cwd=rs.cwd, lastError=None)

        cfg = get_all(mask_secrets=False)
        if at == "openai":
            ok = cfg.get("integrations", {}).get("openai", {}) or {}
            api_key = ok.get("apiKey")
            model = ok.get("defaultModel") or "gpt-3.5-turbo"
            if not api_key:
                self._last_error = "OpenAI API key missing in config"
                raise RuntimeError(self._last_error)
            self._openai = {"api_key": api_key, "model": model}
            self._claude = None
            self._active_type = "openai"
            return AgentStatus(agentType=self._active_type, running=True, pid=None, cwd=str(self._cwd), lastError=None)

        # claude
        ak = cfg.get("integrations", {}).get("anthropic", {}) or {}
        api_key = ak.get("apiKey")
        model = ak.get("defaultModel") or "claude-3-haiku-20240307"
        if not api_key:
            self._last_error = "Anthropic API key missing in config"
            raise RuntimeError(self._last_error)
        self._claude = {"api_key": api_key, "model": model}
        self._openai = None
        self._active_type = "claude"
        return AgentStatus(agentType=self._active_type, running=True, pid=None, cwd=str(self._cwd), lastError=None)

    async def stop(self) -> AgentStatus:
        if self._active_type == "gemini":
            rs = await _gemini_runner.stop()
            self._active_type = None
            self._openai = None
            self._claude = None
            return AgentStatus(agentType=None, running=False, pid=None, cwd=rs.cwd, lastError=None)
        # Providers: clear state
        self._active_type = None
        self._openai = None
        self._claude = None
        return AgentStatus(agentType=None, running=False, pid=None, cwd=str(self._cwd) if self._cwd else None, lastError=None)

    def status(self) -> AgentStatus:
        if self._active_type == "gemini":
            rs = _gemini_runner.status()
            return AgentStatus(agentType="gemini", running=rs.running, pid=rs.pid, cwd=rs.cwd, lastError=self._last_error)
        return AgentStatus(agentType=self._active_type, running=bool(self._active_type), pid=None, cwd=str(self._cwd) if self._cwd else None, lastError=self._last_error)

    async def send(self, text: str, correlation_id: Optional[str] = None) -> dict:
        if (self._active_type or "gemini") == "gemini":
            return await _gemini_runner.send(text, correlation_id=correlation_id)
        if self._active_type == "openai" and self._openai:
            content = await self._call_openai(text)
        elif self._active_type == "claude" and self._claude:
            content = await self._call_claude(text)
        else:
            raise RuntimeError("No agent is running")
        # Push response into chat pipeline
        from app.services.chat import chat_service
        await chat_service.on_agent_output_line(self._project_id or "", content, correlation_id)
        return {"queued": True, "msgId": None}

    async def _call_openai(self, text: str) -> str:
        assert self._openai is not None
        api_key = self._openai["api_key"]
        model = self._openai["model"]
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "temperature": 0.2,
        }).encode("utf-8")
        req = urllib.request.Request(
            url="https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=body,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec - controlled URL
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        msg = (data.get("choices") or [{}])[0].get("message", {}).get("content")
        return str(msg or "")

    async def _call_claude(self, text: str) -> str:
        assert self._claude is not None
        api_key = self._claude["api_key"]
        model = self._claude["model"]
        body = json.dumps({
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": text}],
        }).encode("utf-8")
        req = urllib.request.Request(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            data=body,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec - controlled URL
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        content = data.get("content") or []
        if content and isinstance(content, list) and isinstance(content[0], dict):
            return str(content[0].get("text") or "")
        return ""


# Singleton
agent = UnifiedAgent()

