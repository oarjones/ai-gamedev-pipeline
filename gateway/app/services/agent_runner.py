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

        # Drain remaining output for logs
        await self._drain_pipes_for_logging()
        self._proc = None
        return RunnerStatus(running=False, pid=None, cwd=str(self._cwd) if self._cwd else None)

    async def send(self, text: str, correlation_id: str | None = None, timeout: Optional[float] = None) -> str:
        """Send a line of text to the agent and return a single-line response.

        Uses an IO lock to serialize writes/reads to avoid interleaving.
        """
        if not self._proc or self._proc.returncode is not None or not self._proc.stdin or not self._proc.stdout:
            raise RuntimeError("Agent process is not running")

        tout = float(timeout) if timeout is not None else self._default_timeout
        async with self._io_lock:
            # Write input line
            line = (text or "") + "\n"
            logger.debug("[%s] >> %s", correlation_id or "-", text)
            self._proc.stdin.write(line.encode("utf-8"))
            await self._proc.stdin.drain()

            # Read one response line
            try:
                raw = await asyncio.wait_for(self._proc.stdout.readline(), timeout=tout)
            except asyncio.TimeoutError as e:
                logger.warning("[%s] Timeout waiting for agent response", correlation_id or "-")
                raise e

            out = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            logger.debug("[%s] << %s", correlation_id or "-", out)
            # Also capture any stderr produced synchronously
            await self._log_stderr_nonblocking()
            return out

    def status(self) -> RunnerStatus:
        """Return current runner status (running, pid, cwd)."""
        running = bool(self._proc and self._proc.returncode is None)
        pid = self._proc.pid if running and self._proc else None
        return RunnerStatus(running=running, pid=pid, cwd=str(self._cwd) if self._cwd else None)

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

