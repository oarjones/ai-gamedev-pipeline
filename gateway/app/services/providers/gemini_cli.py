from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .base import IAgentProvider, SessionCtx, ProviderEvent, EventCallback


def _resolve_command() -> list[str]:
    # Prefer centralized config if present
    try:
        from app.services.config_service import get_all
        cfg = get_all(mask_secrets=True) or {}
        prov = ((cfg.get("providers") or {}).get("geminiCli") or {})
        cmd = prov.get("command") if isinstance(prov, dict) else None
        if cmd:
            if isinstance(cmd, str):
                return shlex.split(cmd)
            if isinstance(cmd, list):
                return [str(c) for c in cmd]
    except Exception:
        pass
    # Fallback to 'gemini' on PATH
    return ["gemini"]


@dataclass
class _State:
    proc: Optional[asyncio.subprocess.Process] = None
    reader_task: Optional[asyncio.Task] = None
    err_task: Optional[asyncio.Task] = None


class GeminiCliProvider(IAgentProvider):
    def __init__(self, session: SessionCtx) -> None:
        self._session = session
        self._state = _State()
        self._cb: Optional[EventCallback] = None

    def onEvent(self, cb: EventCallback) -> None:
        self._cb = cb

    async def start(self, session: SessionCtx) -> None:
        if self._state.proc and self._state.proc.returncode is None:
            return
        cmd = _resolve_command()
        # Working dir set to project folder if exists
        cwd = Path("projects") / session.projectId
        if not cwd.exists():
            cwd = Path.cwd()
        env = os.environ.copy()
        self._state.proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._state.reader_task = asyncio.create_task(self._stdout_reader(), name="gemini-cli-stdout")
        self._state.err_task = asyncio.create_task(self._stderr_reader(), name="gemini-cli-stderr")

    async def stop(self) -> None:
        p = self._state.proc
        if not p:
            return
        try:
            if p.returncode is None:
                p.terminate()
                try:
                    await asyncio.wait_for(p.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    p.kill()
                    try:
                        await asyncio.wait_for(p.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
        finally:
            self._state.proc = None
            # Cancel readers
            for t in (self._state.reader_task, self._state.err_task):
                if t and not t.done():
                    t.cancel()
                    try:
                        await t
                    except Exception:
                        pass
            self._state.reader_task = None
            self._state.err_task = None

    async def send(self, user_message: str) -> None:
        p = self._state.proc
        if not p or p.returncode is not None or not p.stdin:
            raise RuntimeError("Provider process is not running")
        line = (user_message or "") + "\n"
        p.stdin.write(line.encode("utf-8"))
        await p.stdin.drain()

    def status(self) -> dict:
        p = self._state.proc
        running = bool(p and p.returncode is None)
        pid = p.pid if running and p else None
        return {"name": "gemini_cli", "running": running, "pid": pid}

    async def _stdout_reader(self) -> None:
        p = self._state.proc
        if not p or not p.stdout:
            return
        try:
            while True:
                raw = await p.stdout.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if not text:
                    continue
                ev = _parse_line(text)
                await self._emit(ev)
        except asyncio.CancelledError:
            pass

    async def _stderr_reader(self) -> None:
        p = self._state.proc
        if not p or not p.stderr:
            return
        try:
            while True:
                raw = await p.stderr.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                await self._emit(ProviderEvent(kind="error", payload={"message": text}))
        except asyncio.CancelledError:
            pass

    async def _emit(self, ev: ProviderEvent) -> None:
        if self._cb:
            try:
                await self._cb(ev)
            except Exception:
                pass


def _parse_line(line: str) -> ProviderEvent:
    # Detect tool_call shim
    try:
        obj = json.loads(line)
        if isinstance(obj, dict) and isinstance(obj.get("tool_call"), dict):
            tc = obj["tool_call"]
            name = str(tc.get("name"))
            args = tc.get("args")
            return ProviderEvent(kind="tool_call", payload={"name": name, "args": args})
    except Exception:
        pass
    # Default: token stream
    return ProviderEvent(kind="token", payload={"content": line})

