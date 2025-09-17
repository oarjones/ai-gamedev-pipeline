"""Unified Agent Runner supporting 'gemini' (CLI/MCP), 'openai', and 'claude'.

Delegates Gemini to existing AgentRunner (CLI). For OpenAI/Claude, uses
direct HTTP calls and streams responses into the chat pipeline.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Optional, Tuple
import os

from app.services.agent_runner import agent_runner as _gemini_runner
from app.services.config_service import get_all
from app.services.process_manager import process_manager
from app.services.adapter_lock import status as adapter_status


@dataclass
class AgentStatus:
    agentType: Optional[str]
    running: bool
    pid: Optional[int]
    cwd: Optional[str]
    lastError: Optional[str]


class UnifiedAgent:
    def __init__(self) -> None:
        self._log = logging.getLogger(__name__)
        self._active_type: Optional[str] = None
        self._project_id: Optional[str] = None
        self._cwd: Optional[Path] = None
        self._openai: Optional[dict] = None
        self._claude: Optional[dict] = None
        self._last_error: Optional[str] = None
        # Base dir for one-shot sessions
        try:
            cfg = get_all(mask_secrets=False) or {}
            # Prefer explicit project_dir_base if provided, else fall back
            self.project_base_dir: str = (
                str(cfg.get("project_dir_base"))
                or str((cfg.get("projects") or {}).get("root") or "projects")
            )
        except Exception:
            self.project_base_dir = "projects"

    async def start(self, cwd: Path, agent_type: str) -> AgentStatus:
        at = (agent_type or "gemini").lower()
        if at not in ("gemini", "openai", "claude"):
            raise ValueError("Unsupported agentType")
        self._cwd = Path(cwd)
        self._project_id = self._cwd.name
        self._last_error = None

        if at == "gemini":
            # Validate preconditions: either MCP adapter is running, or unity_bridge is up
            st = process_manager.status()
            names = {s.get("name") for s in st if s.get("running")}
            ad = adapter_status()
            mcp_ok = bool(ad.get("running"))
            unity_ok = "unity_bridge" in names
            # Log current environment and adapter lock details
            try:
                from app.services.adapter_lock import lock_path as _lock_path
                self._log.info(
                    "[UnifiedAgent] Pre-check: adapter_lock running=%s pid=%s startedAt=%s lock=%s, unity_bridge=%s",
                    mcp_ok,
                    ad.get("pid"),
                    ad.get("startedAt"),
                    str(_lock_path()),
                    unity_ok,
                )
            except Exception:
                pass

            if not mcp_ok:
                # Fallback: attempt a lightweight bridge handshake as health probe
                probe_ok, probe_err = await self._probe_bridge_health()
                if not probe_ok:
                    self._last_error = f"MCP adapter not ready and bridge probe failed: {probe_err or 'unknown error'}"
                    self._log.error("[UnifiedAgent] Health check failed: %s", self._last_error)
                    # raise RuntimeError(self._last_error)
                else:
                    self._log.warning(
                        "[UnifiedAgent] Adapter lock not detected but bridge handshake succeeded; continuing startup"
                    )
            
            # Ensure MCP adapter via AgentRunner, then start CLI provider
            try:
                rs = await _gemini_runner.start(self._cwd, provider="gemini_cli")
            except Exception as e:
                self._last_error = f"Failed to start provider: {e!r}"
                self._log.exception("[UnifiedAgent] Provider start error: %r", e)
                raise
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

    async def _probe_bridge_health(self) -> tuple[bool, Optional[str]]:
        """Try a very lightweight handshake to the Unity Bridge WS used by the MCP adapter.

        This does not exercise the MCP stdio server directly, but verifies the downstream
        bridge the adapter talks to. Useful when lockfile checks are unreliable.
        Returns (ok, error).
        """
        try:
            # Build WS URL like MCPClient does to avoid import cycles
            from app.services.config_service import get_all as _cfg
            cfg = _cfg(mask_secrets=False) or {}
            ub_port = int(((cfg.get("bridges") or {}).get("unityBridgePort") or 8001))
            url = f"ws://127.0.0.1:{ub_port}/ws/gemini_cli_adapter"
        except Exception as e:
            return False, f"config error: {e}"

        try:
            import asyncio
            import websockets  # type: ignore
            # Very short connection attempt and immediate close
            async def _try():
                ws = await websockets.connect(url)  # type: ignore
                try:
                    # Optional: send a noop frame that bridge can ignore
                    await ws.send("{}")
                finally:
                    await ws.close()
            await asyncio.wait_for(_try(), timeout=1.5)
            return True, None
        except Exception as e:
            return False, str(e)

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


    # --- One-Shot API ---
    def ask_one_shot(self, session_id: str, new_question: str) -> Tuple[Optional[str], Optional[str]]:
        """Run a single-turn prompt via the gemini_cli provider without starting a REPL.

        Returns (answer, error). If answer is present and error also present, error should be treated as a warning.
        """
        try:
            base = self.project_base_dir or "projects"
            session_work_dir = os.path.join(base, session_id)
            os.makedirs(session_work_dir, exist_ok=True)
            full_prompt = new_question  # TODO: Prepend history & context to create Mega-Prompt
            from app.services.providers.registry import registry as provider_registry
            from app.services.providers.base import SessionCtx
            from app.services.providers.gemini_cli import GeminiCliProvider  # ensure class is loaded
            session = SessionCtx(project_id=session_id, sessionId=session_id)
            try:
                provider = provider_registry.get("gemini_cli", session)
            except Exception:
                provider = GeminiCliProvider(session)
            answer, error = provider.run_one_shot(full_prompt, session_work_dir)  # type: ignore[attr-defined]
            # TODO: Save question and answer to DB via self.chat_service
            return answer, error
        except Exception as e:
            self._log.exception("ask_one_shot failed: %s", e)
            return None, str(e)

# Singleton
agent = UnifiedAgent()
