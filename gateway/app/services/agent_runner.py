"""Asynchronous AgentRunner to manage a per-project CLI subprocess.

This runner launches a CLI process with cwd set to a project folder and
exposes async methods to start/stop the process, send input, and inspect
status. It uses asyncio.create_subprocess_exec without PTY to be portable
across Windows/macOS/Linux.

Temporary mock command: a Python one-liner that echoes stdin lines.
To switch to the real CLI later, replace `_build_command()` implementation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import json
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


logger = logging.getLogger(__name__)


@dataclass
class RunnerStatus:
    running: bool
    pid: Optional[int]
    cwd: Optional[str]


@dataclass
class AgentConfig:
    executable: str
    args: List[str]
    env: Dict[str, str]
    default_timeout: float
    terminate_grace: float


class AgentRunner:
    """Manage a single long-lived CLI subprocess for the active project."""

    def __init__(self, default_timeout: float = 5.0, terminate_grace: float = 3.0) -> None:
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._cwd: Optional[Path] = None
        self._default_timeout = float(default_timeout)
        self._terminate_grace = float(terminate_grace)
        self._io_lock = asyncio.Lock()
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._project_id: Optional[str] = None
        self._last_correlation_id: Optional[str] = None
        self._adapter: Optional[AgentAdapter] = None

    @staticmethod
    def _load_project_agent_config(cwd: Path) -> AgentConfig:
        """Load per-project agent configuration.

        Precedence:
        1) projects/<id>/.agp/project.json -> key 'agent'
        2) gateway/config/projects/<id>.yaml (if exists)
        """
        project_id = cwd.name
        # 1) JSON in .agp/project.json
        pj = cwd / ".agp" / "project.json"
        agent: Dict[str, object] = {}
        if pj.exists():
            try:
                with open(pj, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                    agent = data.get("agent", {}) if isinstance(data, dict) else {}
            except Exception:
                agent = {}
        # 2) Fallback YAML per-project config
        if (not agent) and yaml is not None:
            ypath = Path("gateway") / "config" / "projects" / f"{project_id}.yaml"
            if ypath.exists():
                try:
                    with open(ypath, "r", encoding="utf-8") as f:
                        y = yaml.safe_load(f) or {}
                        agent = y.get("agent", {}) if isinstance(y, dict) else {}
                except Exception:
                    agent = {}

        if not isinstance(agent, dict):
            agent = {}

        executable = str(agent.get("executable", "")).strip()
        args = agent.get("args", [])
        env = agent.get("env", {})
        default_timeout = float(agent.get("default_timeout", 5.0) or 5.0)
        terminate_grace = float(agent.get("terminate_grace", 3.0) or 3.0)

        if not isinstance(args, list):
            args = []
        if not isinstance(env, dict):
            env = {}

        return AgentConfig(
            executable=executable,
            args=[str(a) for a in args],
            env={str(k): str(v) for k, v in env.items()},
            default_timeout=default_timeout,
            terminate_grace=terminate_grace,
        )

    @staticmethod
    def _resolve_executable(executable: str, cwd: Path) -> Optional[str]:
        """Resolve executable path, supporting absolute, relative, or PATH lookup."""
        if not executable:
            return None
        p = Path(executable)
        if not p.is_absolute():
            p = (cwd / executable).resolve()
        if p.exists():
            return str(p)
        # Try PATH
        which = shutil.which(executable)
        return which

    @staticmethod
    def _build_from_config(cwd: Path, cfg: AgentConfig) -> Tuple[List[str], Dict[str, str]]:
        resolved_exec = AgentRunner._resolve_executable(cfg.executable, cwd)
        if not resolved_exec:
            raise RuntimeError(f"Agent executable not found: '{cfg.executable}' (cwd={cwd})")

        cmd = [resolved_exec, *cfg.args]
        env = os.environ.copy()
        # Merge project env (override)
        for k, v in cfg.env.items():
            env[str(k)] = str(v)
        return cmd, env

    async def start(self, cwd: Path) -> RunnerStatus:
        """Start the agent process in the provided working directory.

        If a process is already running, returns its status without restarting.
        """
        if self._proc and self._proc.returncode is None:
            return self.status()

        self._cwd = Path(cwd)
        if not self._cwd.exists() or not self._cwd.is_dir():
            raise FileNotFoundError(f"Project directory not found: {self._cwd}")

        # Load per-project agent configuration
        cfg = self._load_project_agent_config(self._cwd)
        if not cfg.executable:
            raise RuntimeError("Agent executable not configured. Add 'agent.executable' in .agp/project.json or gateway/config/projects/{id}.yaml")
        # Update timeouts from config
        self._default_timeout = float(cfg.default_timeout)
        self._terminate_grace = float(cfg.terminate_grace)

        # Adapter per project
        self._adapter = get_adapter(getattr(cfg, "adapter", None))
        cmd, env = self._build_from_config(self._cwd, cfg)
        # Log safe command line (no env values)
        safe_cmd = " ".join(shlex.quote(p) for p in cmd)
        logger.info("Starting agent CLI: %s (cwd=%s)", safe_cmd, str(self._cwd))
        # DEBUG level logs of stdout/stderr will be written upon send() or when stopping
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self._cwd),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        # Track project id and start background readers
        self._project_id = self._cwd.name
        self._start_readers()
        return self.status()

    async def stop(self) -> RunnerStatus:
        """Stop the agent process gracefully (terminate → kill)."""
        if not self._proc or self._proc.returncode is not None:
            # Already stopped
            return self.status()

        assert self._proc is not None
        pid = self._proc.pid
        logger.info("Stopping agent CLI pid=%s", pid)
        try:
            self._proc.terminate()
        except ProcessLookupError:
            # Already gone
            self._proc = None
            return RunnerStatus(running=False, pid=None, cwd=str(self._cwd) if self._cwd else None)

        try:
            await asyncio.wait_for(self._proc.wait(), timeout=self._terminate_grace)
        except asyncio.TimeoutError:
            logger.warning("Terminate timed out; killing agent CLI pid=%s", pid)
            self._proc.kill()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.error("Failed to kill agent CLI pid=%s promptly", pid)

        # Cancel readers
        await self._cancel_readers()
        # Drain remaining output for logs
        await self._drain_pipes_for_logging()
        self._proc = None
        return RunnerStatus(running=False, pid=None, cwd=str(self._cwd) if self._cwd else None)

    async def send(self, text: str, correlation_id: str | None = None, timeout: Optional[float] = None) -> dict:
        """Send a line to the agent non-blocking; background readers stream output.

        Returns an ack dict: {queued: True, msgId: <generated or None>}
        """
        if not self._proc or self._proc.returncode is not None or not self._proc.stdin:
            raise RuntimeError("Agent process is not running")

        async with self._io_lock:
            line = (text or "") + "\n"
            if self._adapter:
                try:
                    prepared = self._adapter.prepare_input(text)
                    line = (prepared or "") + "\n"
                except Exception:
                    # Fallback to raw
                    line = (text or "") + "\n"
            self._last_correlation_id = correlation_id
            logger.debug("[%s] >> %s", correlation_id or "-", text)
            self._proc.stdin.write(line.encode("utf-8"))
            await self._proc.stdin.drain()
            return {"queued": True, "msgId": None}

    def status(self) -> RunnerStatus:
        """Return current runner status (running, pid, cwd)."""
        running = bool(self._proc and self._proc.returncode is None)
        pid = self._proc.pid if running and self._proc else None
        return RunnerStatus(running=running, pid=pid, cwd=str(self._cwd) if self._cwd else None)

    def _start_readers(self) -> None:
        if self._proc is None:
            return
        if self._reader_task is None or self._reader_task.done():
            self._reader_task = asyncio.create_task(self._stdout_reader(), name="agent-stdout-reader")
        if self._stderr_task is None or self._stderr_task.done():
            self._stderr_task = asyncio.create_task(self._stderr_reader(), name="agent-stderr-reader")

    async def _cancel_readers(self) -> None:
        for t in (self._reader_task, self._stderr_task):
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except Exception:
                    pass
        self._reader_task = None
        self._stderr_task = None

    async def _stdout_reader(self) -> None:
        if not self._proc or not self._proc.stdout:
            return
        try:
            while True:
                raw = await self._proc.stdout.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if not text:
                    continue
                await self._handle_output_line(text, stream="stdout")
        except asyncio.CancelledError:
            pass

    async def _stderr_reader(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        try:
            while True:
                raw = await self._proc.stderr.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if not text:
                    continue
                await self._handle_output_line(text, stream="stderr")
        except asyncio.CancelledError:
            pass

    async def _handle_output_line(self, text: str, stream: str) -> None:
        project_id = self._project_id or ""
        corr = self._last_correlation_id
        try:
            if stream == "stderr":
                # Map to LOG event
                from app.ws.events import manager
                from app.models import Envelope, EventType
                payload = {"level": "error", "message": text}
                env = Envelope(type=EventType.LOG, projectId=project_id, payload=payload, correlationId=corr)
                await manager.broadcast_project(project_id, env.model_dump_json(by_alias=True))
                return

            events: list[StreamEvent] = []
            if self._adapter:
                try:
                    events = self._adapter.on_stream(text)
                except Exception:
                    events = []
            if not events:
                events = [StreamEvent(kind="chat", payload={"content": text})]

            for ev in events:
                if ev.kind == "tool":
                    from app.ws.events import manager
                    from app.models import Envelope, EventType
                    payload = {"subtype": "tool", "data": ev.payload, "correlationId": corr}
                    env = Envelope(type=EventType.ACTION, projectId=project_id, payload=payload, correlationId=corr)
                    await manager.broadcast_project(project_id, env.model_dump_json(by_alias=True))
                elif ev.kind == "event":
                    from app.ws.events import manager
                    from app.models import Envelope, EventType
                    env = Envelope(type=EventType.UPDATE, projectId=project_id, payload=ev.payload, correlationId=corr)
                    await manager.broadcast_project(project_id, env.model_dump_json(by_alias=True))
                else:
                    from app.services.chat import chat_service
                    await chat_service.on_agent_output_line(project_id, ev.payload.get("content", text), correlation_id=corr)
        except Exception as e:
            logger.debug("Output handling error: %s", e)

    async def _drain_pipes_for_logging(self) -> None:
        """Drain stdout/stderr and log lines at DEBUG without blocking indefinitely."""
        if not self._proc:
            return
        # Try to read any remaining lines with short timeouts
        for stream_name, stream in (("stdout", self._proc.stdout), ("stderr", self._proc.stderr)):
            if not stream:
                continue
            try:
                while True:
                    raw = await asyncio.wait_for(stream.readline(), timeout=0.05)
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        logger.debug("[agent %s] %s", stream_name, line)
            except asyncio.TimeoutError:
                # No more data readily available
                pass

    async def _log_stderr_nonblocking(self) -> None:
        """Attempt to read a single stderr line quickly for logging."""
from app.services.adapters.registry import get_adapter
from app.services.adapters.base import AgentAdapter, StreamEvent
        if self._proc and self._proc.stderr:
            try:
                raw = await asyncio.wait_for(self._proc.stderr.readline(), timeout=0.01)
                if raw:
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        logger.debug("[agent stderr] %s", line)
            except asyncio.TimeoutError:
                pass


# Singleton instance used by API routes
agent_runner = AgentRunner()

