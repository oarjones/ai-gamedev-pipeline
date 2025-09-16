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
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import json
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


logger = logging.getLogger(__name__)

# Adapter interfaces
from app.services.adapters.registry import get_adapter
from app.services.adapters.base import AgentAdapter, StreamEvent
from app.services.providers.registry import registry as provider_registry
from app.services.providers.base import IAgentProvider, SessionCtx, ProviderEvent
from app.services.adapter_lock import status as adapter_status
from app.services.config_service import get_all as get_cfg


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
        self._provider: Optional[IAgentProvider] = None
        self._provider_name: Optional[str] = None
        self._tool_catalog: Optional[dict] = None
        self._turn_id: Optional[str] = None
        self._turn_calls: int = 0
        self._tool_max_calls: int = 4
        self._tool_timeout_sec: float = 15.0
        self._tool_results: asyncio.Queue = asyncio.Queue()
        # MCP Adapter process (owned by AgentRunner when configured)
        self._adapter_proc: Optional[asyncio.subprocess.Process] = None
        self._adapter_owned: bool = False

    @staticmethod
    def _mask(s: str) -> str:
        import re
        if not s:
            return s
        redacted = re.sub(r"(?i)(api[-_ ]?key|token|secret)\s*[:=]\s*([^\s]+)", r"\1=[REDACTED]", s)
        return (redacted[:120] + "…") if len(redacted) > 120 else redacted

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

    async def start(self, cwd: Path, provider: Optional[str] = None, context_pack: Optional[dict] = None) -> RunnerStatus:
        """Start the agent process in the provided working directory.

        If a process is already running, returns its status without restarting.
        """
        if self._proc and self._proc.returncode is None:
            return self.status()

        self._cwd = Path(cwd)
        if not self._cwd.exists() or not self._cwd.is_dir():
            raise FileNotFoundError(f"Project directory not found: {self._cwd}")

        # Ensure MCP adapter if ownership is configured (needed for provider tool-calls)
        await self._ensure_mcp_adapter()
        self._project_id = self._cwd.name

        if provider:
            # Provider mode
            self._provider_name = provider
            # Build tool catalog for provider session
            try:
                from app.services.tool_catalog import get_catalog_cached
                catalog = get_catalog_cached()
            except Exception:
                catalog = None
            self._tool_catalog = catalog
            # Load limits from config
            self._load_toolshim_config()
            # Start session and build context pack
            # Build context pack if not provided
            if context_pack is None:
                try:
                    from app.services.sessions_service import sessions_service
                    sess = sessions_service.start_session(self._project_id, provider)
                    self._session_id = getattr(sess, "id", None)
                    cp = sessions_service.build_context_pack(self._project_id)
                    context_pack = {
                        "project_manifest": cp.project_manifest,
                        "plan_of_record": cp.plan_of_record,
                        "last_summary": cp.last_summary,
                        "recent_messages": cp.recent_messages,
                        "artifacts": cp.artifacts,
                    }
                except Exception:
                    self._session_id = None
                    context_pack = None
            session = SessionCtx(project_id=self._project_id, sessionId=_gen_session_id(), toolCatalog=catalog, contextPack=context_pack)
            # Late register default provider
            _ensure_default_providers()
            self._provider = provider_registry.get(provider, session)
            self._provider.onEvent(self._on_provider_event)
            logger.info("[AgentRunner] Starting provider '%s' for project %s", provider, self._project_id)
            try:
                await self._provider.start(session)
            except Exception as e:
                logger.error("[AgentRunner] Provider '%s' failed to start: %s", provider, e)
                raise
            return self.status()

        # Legacy CLI mode
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
        safe_cmd = " ".join(shlex.quote(p) for p in cmd)
        logger.info("Starting agent CLI: %s (cwd=%s)", safe_cmd, str(self._cwd))
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self._cwd),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._start_readers()
        return self.status()

    async def stop(self) -> RunnerStatus:
        """Stop the agent process gracefully (terminate → kill)."""
        if self._provider:
            try:
                await self._provider.stop()
            except Exception:
                pass
            self._provider = None
            self._provider_name = None
        # End DB session if created
        try:
            if getattr(self, "_session_id", None) is not None:
                from app.services.sessions_service import sessions_service
                sessions_service.end_session(self._session_id)  # type: ignore[arg-type]
        except Exception:
            pass
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
        # Stop MCP adapter if we own it
        await self._stop_mcp_adapter_if_owned()
        return RunnerStatus(running=False, pid=None, cwd=str(self._cwd) if self._cwd else None)

    async def send(self, text: str, correlation_id: str | None = None, timeout: Optional[float] = None) -> dict:
        """Send a line to the agent non-blocking; background readers stream output.

        Returns an ack dict: {queued: True, msgId: <generated or None>}
        """
        if self._provider:
            # Start a new turn
            self._turn_id = _gen_session_id()
            self._turn_calls = 0
            self._last_correlation_id = correlation_id
            # Persist user message
            try:
                if getattr(self, "_session_id", None) is not None:
                    from app.services.sessions_service import sessions_service
                    sessions_service.add_user_message(self._session_id, text)  # type: ignore[arg-type]
            except Exception:
                pass
            await self._provider.send(text)
            return {"queued": True, "msgId": None}
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
            try:
                masked = self._mask(text)
            except Exception:
                masked = text
            logger.debug("[%s] >> %s", correlation_id or "-", masked)
            self._proc.stdin.write(line.encode("utf-8"))
            await self._proc.stdin.drain()
            return {"queued": True, "msgId": None}

    def status(self) -> RunnerStatus:
        """Return current runner status (running, pid, cwd)."""
        if self._provider:
            st = self._provider.status()
            running = bool(st.get("running"))
            pid = st.get("pid") if running else None
        else:
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

    def _load_toolshim_config(self) -> None:
        """Load tool shim limits from centralized config with safe defaults."""
        try:
            from app.services.config_service import get_all
            cfg = get_all(mask_secrets=False) or {}
            toolshim = ((cfg.get("agents") or {}).get("toolShim") or {})
            self._tool_max_calls = int(toolshim.get("maxCallsPerTurn", 4))
            self._tool_timeout_sec = float(toolshim.get("toolTimeoutSeconds", 15))
        except Exception:
            self._tool_max_calls = 4
            self._tool_timeout_sec = 15.0

    async def _on_provider_event(self, ev: ProviderEvent) -> None:
        project_id = self._project_id or ""
        corr = self._last_correlation_id
        try:
            if ev.kind == "tool_call":
                # Persist tool call
                try:
                    if getattr(self, "_session_id", None) is not None:
                        from app.services.sessions_service import sessions_service
                        sessions_service.add_tool_call(self._session_id, str((ev.payload or {}).get("name")), (ev.payload or {}).get("args") or {})  # type: ignore[arg-type]
                except Exception:
                    pass
                # Shim: validate -> execute -> inject result
                await self._handle_tool_call(ev.payload, project_id, corr)
            elif ev.kind == "token":
                from app.services.chat import chat_service
                await chat_service.on_agent_output_line(project_id, ev.payload.get("content", ""), correlation_id=corr)
            elif ev.kind == "final":
                # no-op placeholder for now
                pass
            elif ev.kind == "error":
                from app.ws.events import manager
                from app.models import Envelope, EventType
                payload = {"level": "error", "message": ev.payload.get("message", "")}
                env = Envelope(type=EventType.LOG, project_id=project_id, payload=payload, correlationId=corr)
                await manager.broadcast_project(project_id, env.model_dump_json(by_alias=True))
        except Exception:
            pass

    async def _ensure_mcp_adapter(self) -> None:
        """Start MCP Adapter if configured to be owned by AgentRunner.

        Respects lockfile and does nothing if an instance is already running.
        """
        try:
            full = _read_settings_yaml()
            ownership = str((((full.get("agent") or {}).get("mcp") or {}).get("adapterOwnership") or "agent_runner_only")).lower()
        except Exception:
            ownership = "agent_runner_only"

        if ownership != "agent_runner_only":
            return

        st = adapter_status()
        if st.get("running"):
            # Do not start another instance; not owned
            self._adapter_owned = False
            self._adapter_proc = None
            return

        # Build env from config
        cfg = get_cfg(mask_secrets=False)
        ub_port = int(((cfg.get("bridges") or {}).get("unityBridgePort") or 8001))
        bb_port = int(((cfg.get("bridges") or {}).get("blenderBridgePort") or 8002))
        mcp_ws = f"ws://127.0.0.1:{ub_port}/ws/gemini_cli_adapter"
        blender_ws = f"ws://127.0.0.1:{bb_port}"
        env = os.environ.copy()
        env["MCP_SERVER_URL"] = mcp_ws
        env["BLENDER_SERVER_URL"] = blender_ws

        # Launch adapter as module
        # Prefer configured Python if provided (ensures correct venv for adapter deps)
        try:
            raw = _read_settings_yaml()
            py_cfg = (((raw.get("gateway") or {}).get("processes") or {}).get("mcp_adapter") or {}).get("python")
            python_exe = str(py_cfg) if py_cfg else sys.executable
        except Exception:
            python_exe = sys.executable
        logger.info("[AgentRunner] MCP Adapter python: %s", python_exe)
        cmd = [python_exe, "-u", "-m", "bridges.mcp_adapter"]
        # Use repo root as cwd
        cwd = Path(__file__).resolve().parents[3]
        try:
            self._adapter_proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except NotImplementedError:
            # Windows SelectorEventLoop without subprocess support: fallback to Popen
            p = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            class _PopenAdapter:
                def __init__(self, pop: subprocess.Popen):
                    self._p = pop

                @property
                def pid(self) -> int:
                    return self._p.pid

                @property
                def returncode(self) -> Optional[int]:
                    return self._p.poll()

                def terminate(self) -> None:
                    try:
                        self._p.terminate()
                    except Exception:
                        pass

                def kill(self) -> None:
                    try:
                        self._p.kill()
                    except Exception:
                        pass

                async def wait(self) -> int:
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(None, self._p.wait)

            self._adapter_proc = _PopenAdapter(p)  # type: ignore[assignment]
        self._adapter_owned = True

    # Public helper to allow other services to ensure the MCP adapter
    async def ensure_mcp_adapter_public(self) -> None:
        await self._ensure_mcp_adapter()

    async def _stop_mcp_adapter_if_owned(self) -> None:
        if not self._adapter_owned:
            return
        if not self._adapter_proc:
            self._adapter_owned = False
            return
        try:
            if self._adapter_proc.returncode is None:
                self._adapter_proc.terminate()
                try:
                    await asyncio.wait_for(self._adapter_proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._adapter_proc.kill()
                    try:
                        await asyncio.wait_for(self._adapter_proc.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
        except Exception:
            pass
        finally:
            self._adapter_proc = None
            self._adapter_owned = False


def _read_settings_yaml() -> dict:
    """Read raw config/settings.yaml for flags not normalized in config_service."""
    p = Path("config") / "settings.yaml"
    try:
        import yaml  # type: ignore
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}
    except Exception:
        return {}

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
                env = Envelope(type=EventType.LOG, project_id=project_id, payload=payload, correlationId=corr)
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
                    env = Envelope(type=EventType.ACTION, project_id=project_id, payload=payload, correlationId=corr)
                    await manager.broadcast_project(project_id, env.model_dump_json(by_alias=True))
                elif ev.kind == "event":
                    from app.ws.events import manager
                    from app.models import Envelope, EventType
                    env = Envelope(type=EventType.UPDATE, project_id=project_id, payload=ev.payload, correlationId=corr)
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
        if self._proc and self._proc.stderr:
            try:
                raw = await asyncio.wait_for(self._proc.stderr.readline(), timeout=0.01)
                if raw:
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        logger.debug("[agent stderr] %s", line)
            except asyncio.TimeoutError:
                pass

    def _load_toolshim_config(self) -> None:
        try:
            from app.services.config_service import get_all
            cfg = get_all(mask_secrets=False) or {}
            toolshim = ((cfg.get("agents") or {}).get("toolShim") or {})
            self._tool_max_calls = int(toolshim.get("maxCallsPerTurn", 4))
            self._tool_timeout_sec = float(toolshim.get("toolTimeoutSeconds", 15))
        except Exception:
            self._tool_max_calls = 4
            self._tool_timeout_sec = 15.0

    async def _handle_tool_call(self, payload: dict, project_id: str, corr: Optional[str]) -> None:
        import uuid, time
        request_id = uuid.uuid4().hex[:8]

        # Enforce per-turn max
        if self._turn_id is None:
            self._turn_id = uuid.uuid4().hex
            self._turn_calls = 0
        if self._turn_calls >= max(1, self._tool_max_calls):
            await self._inject_tool_result({
                "ok": False,
                "error": f"maxCallsPerTurn exceeded ({self._tool_max_calls})",
            })
            return

        name = str((payload or {}).get("name", "")).strip()
        args = (payload or {}).get("args") or {}

        # Timeline started
        try:
            from app.services.timeline import timeline_service
            await timeline_service.record_event(project_id, "tool_call.started", {"name": name, "args": args, "requestId": request_id}, correlation_id=corr)
        except Exception:
            pass

        # Validate against catalog
        valid, verror = self._validate_tool_args(name, args)
        if not valid:
            await self._inject_tool_result({"name": name, "ok": False, "error": verror})
            try:
                from app.services.timeline import timeline_service
                await timeline_service.record_event(project_id, "tool_call.finished", {"name": name, "ok": False, "error": verror, "requestId": request_id}, correlation_id=corr)
            except Exception:
                pass
            # Count attempt
            self._turn_calls += 1
            return

        # Execute via MCP with timeout (special-case 'ping')
        t0 = time.time()
        ok = True
        result: dict | None = None
        err: str | None = None
        try:
            if name == "ping":
                # Adapter ping: return deterministic payload
                result = {"mcp_ping": "pong"}
            else:
                from app.services.mcp_client import mcp_client
                async def run():
                    return await mcp_client.run_tool(project_id, name, args, correlation_id=corr)
                result = await asyncio.wait_for(run(), timeout=max(1.0, float(self._tool_timeout_sec)))
        except asyncio.TimeoutError:
            ok = False
            err = "timeout"
        except Exception as e:
            ok = False
            err = str(e)

        # Inject result to provider
        if ok and result is not None:
            await self._inject_tool_result({"name": name, "ok": True, "result": result})
        else:
            await self._inject_tool_result({"name": name, "ok": False, "error": err or "execution failed"})

        # Timeline finished
        try:
            from app.services.timeline import timeline_service
            await timeline_service.record_event(project_id, "tool_call.finished", {"name": name, "ok": ok, "durationMs": int((time.time()-t0)*1000), "requestId": request_id, "error": err, "result": result}, correlation_id=corr)
        except Exception:
            pass

        self._turn_calls += 1

    async def _inject_tool_result(self, data: dict) -> None:
        if not self._provider:
            return
        try:
            line = json.dumps({"tool_result": data}, ensure_ascii=False)
            await self._provider.send(line)
        except Exception:
            pass
        # Also push into internal queue for self-tests/awaiters
        try:
            item = {**data, "correlationId": self._last_correlation_id, "turnId": self._turn_id}
            self._tool_results.put_nowait(item)
        except Exception:
            pass

    def _validate_tool_args(self, name: str, args: dict) -> tuple[bool, str | None]:
        try:
            catalog = self._tool_catalog or {}
            fs = catalog.get("functionSchema") or []
            schema = None
            for s in fs:
                if str(s.get("name")) == name:
                    schema = s.get("parameters")
                    break
            if not schema:
                return False, "unknown tool"
            # jsonschema validation if available
            try:
                import jsonschema  # type: ignore
                jsonschema.validate(instance=args, schema=schema)  # type: ignore
                return True, None
            except Exception as e:
                # Fall back to basic required check
                req = (schema or {}).get("required") or []
                for r in req:
                    if r not in (args or {}):
                        return False, f"missing required arg: {r}"
                # Accept if basic check passes
                return True, None
        except Exception as e:
            return False, str(e)

    async def wait_tool_result(self, name: str, correlation_id: Optional[str], timeout: float = 5.0) -> Optional[dict]:
        end = asyncio.get_event_loop().time() + max(0.1, float(timeout))
        while True:
            remaining = end - asyncio.get_event_loop().time()
            if remaining <= 0:
                return None
            try:
                item = await asyncio.wait_for(self._tool_results.get(), timeout=remaining)
                if str(item.get("name")) == name and (correlation_id is None or item.get("correlationId") == correlation_id):
                    return item
            except asyncio.TimeoutError:
                return None


# Singleton instance used by API routes
agent_runner = AgentRunner()


def _gen_session_id() -> str:
    import uuid
    return uuid.uuid4().hex


def _ensure_default_providers() -> None:
    from app.services.providers.registry import registry
    try:
        # Register gemini_cli if not present
        registry.get  # type: ignore[attr-defined]
    except Exception:
        pass
    # Avoid duplicate registration
    try:
        registry.get("__probe__", SessionCtx(project_id="_", sessionId="_"))
    except Exception:
        pass
    # Always (re)register
    from app.services.providers.gemini_cli import GeminiCliProvider
    def factory(session: SessionCtx):
        return GeminiCliProvider(session)
    provider_registry.register("gemini_cli", factory)

