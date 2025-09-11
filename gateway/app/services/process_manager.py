"""Local process orchestration for Unity, Blender, Bridges, and MCP Adapter (Windows-friendly).

This module exposes a `ProcessManager` singleton with methods to start/stop
Unity, Unity Bridge, Blender, and Blender Bridge, capturing
stdout/stderr into small circular buffers and reporting status via dicts.
"""

from __future__ import annotations

import os
import signal
import sys
import time
import threading
import subprocess
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, List, Optional

from app.config import settings
from app.services.projects import project_service


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class CircularBuffer:
    """Simple circular buffer for text with byte-size cap."""

    def __init__(self, capacity_bytes: int = 4096) -> None:
        self.capacity = max(512, capacity_bytes)
        self._buf: Deque[bytes] = deque()
        self._size = 0
        self._lock = threading.Lock()

    def append(self, data: bytes) -> None:
        if not data:
            return
        with self._lock:
            self._buf.append(data)
            self._size += len(data)
            while self._size > self.capacity and self._buf:
                dropped = self._buf.popleft()
                self._size -= len(dropped)

    def get_text(self, encoding: str = "utf-8", errors: str = "replace") -> str:
        with self._lock:
            chunks = list(self._buf)
        try:
            return b"".join(chunks).decode(encoding, errors)
        except Exception:
            return ""


@dataclass
class ManagedProcess:
    name: str
    command: List[str]
    cwd: Optional[Path] = None
    env: Optional[Dict[str, str]] = None
    timeout_start: float = 15.0
    grace_stop: float = 5.0
    retries: int = 1
    started_at: Optional[str] = None
    pid: Optional[int] = None
    last_error: Optional[str] = None
    _proc: Optional[subprocess.Popen] = field(default=None, init=False, repr=False)
    _stdout_buf: CircularBuffer = field(default_factory=lambda: CircularBuffer(4096), init=False, repr=False)
    _stderr_buf: CircularBuffer = field(default_factory=lambda: CircularBuffer(4096), init=False, repr=False)
    _stdout_thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _stderr_thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)

    def _reader(self, stream, buffer: CircularBuffer) -> None:
        try:
            while True:
                chunk = stream.readline()
                if not chunk:
                    break
                buffer.append(chunk)
        except Exception:
            pass

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        if self.is_running():
            return
        self.last_error = None

        creationflags = 0
        startupinfo = None
        if os.name == "nt":
            # Create a new process group to allow sending CTRL_BREAK_EVENT to the group
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            self._proc = subprocess.Popen(
                self.command,
                cwd=str(self.cwd) if self.cwd else None,
                env=self.env if self.env else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                creationflags=creationflags,
                startupinfo=startupinfo,
                text=False,
                bufsize=1,
            )
            self.pid = self._proc.pid
            self.started_at = _now_iso()

            # Start reader threads
            if self._proc.stdout is not None:
                self._stdout_thread = threading.Thread(target=self._reader, args=(self._proc.stdout, self._stdout_buf), daemon=True)
                self._stdout_thread.start()
            if self._proc.stderr is not None:
                self._stderr_thread = threading.Thread(target=self._reader, args=(self._proc.stderr, self._stderr_buf), daemon=True)
                self._stderr_thread.start()

            # Optional: wait for a short period to see if it crashes immediately
            deadline = time.time() + max(0.5, min(self.timeout_start, 2.0))
            while time.time() < deadline and self._proc.poll() is None:
                time.sleep(0.05)

            if self._proc.poll() is not None and self._proc.returncode != 0:
                self.last_error = f"Exited immediately with code {self._proc.returncode}"
                raise RuntimeError(self.last_error)
        except Exception as e:
            # Retry once if configured
            self._cleanup_handles()
            if self.retries > 0:
                self.retries -= 1
                time.sleep(0.5)
                self.start()
                return
            self.last_error = str(e)
            raise

    def stop(self, graceful: bool = True) -> None:
        if not self._proc:
            return
        if self._proc.poll() is not None:
            self._cleanup_handles()
            return

        try:
            if graceful:
                if os.name == "nt":
                    # Try to send CTRL_BREAK to the process group
                    try:
                        os.kill(self._proc.pid, getattr(signal, "CTRL_BREAK_EVENT", 1))  # type: ignore
                    except Exception:
                        pass
                else:
                    try:
                        self._proc.terminate()
                    except Exception:
                        pass
                self._wait_for_exit(self.grace_stop)

            if self._proc and self._proc.poll() is None:
                # Force kill
                try:
                    self._proc.kill()
                except Exception:
                    pass
                self._wait_for_exit(2.0)
        finally:
            self._cleanup_handles()

    def _wait_for_exit(self, timeout: float) -> None:
        try:
            self._proc.wait(timeout=timeout)  # type: ignore[union-attr]
        except Exception:
            pass

    def _cleanup_handles(self) -> None:
        try:
            if self._proc and self._proc.stdout:
                try:
                    self._proc.stdout.close()
                except Exception:
                    pass
            if self._proc and self._proc.stderr:
                try:
                    self._proc.stderr.close()
                except Exception:
                    pass
            if self._proc and self._proc.stdin:
                try:
                    self._proc.stdin.close()
                except Exception:
                    pass
        finally:
            self._proc = None

    def status(self) -> Dict[str, Optional[str]]:
        running = self.is_running()
        return {
            "name": self.name,
            "pid": str(self.pid) if self.pid else None,
            "running": running,
            "lastStdout": self._stdout_buf.get_text()[-1024:],
            "lastStderr": self._stderr_buf.get_text()[-1024:],
            "lastError": self.last_error or (self._stderr_buf.get_text()[-1024:] if not running else None),
            "startedAt": self.started_at,
        }


class ProcessManager:
    def __init__(self) -> None:
        self.procs: Dict[str, ManagedProcess] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _port_in_use(host: str, port: int, timeout: float = 0.5) -> bool:
        import socket
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except Exception:
            return False

    def _build_unity_cmd(self, project_id: Optional[str]) -> List[str]:
        proc_cfg = (settings.processes or {}).get("unity", {})
        exe = proc_cfg.get("exe")
        if not exe or not Path(exe).exists():
            raise FileNotFoundError(f"Unity executable not found: {exe}")
        args = list(proc_cfg.get("args", []))
        # Resolve project path
        project_path = proc_cfg.get("project_path")
        if not project_path and project_id:
            project_path = str(Path("projects") / project_id)
        if project_path:
            args.extend(["-projectPath", str(project_path)])
        return [str(exe), *args]

    def _build_unity_bridge_cmd(self) -> List[str]:
        proc_cfg = (settings.processes or {}).get("unity_bridge", {})
        host = proc_cfg.get("host", "127.0.0.1")
        port = int(proc_cfg.get("port", 8001))
        python_exe = proc_cfg.get("python", sys.executable)
        app_import = proc_cfg.get("app_import", "mcp_unity_bridge.src.mcp_unity_server.main:app")
        return [
            python_exe,
            "-m",
            "uvicorn",
            app_import,
            "--host",
            host,
            "--port",
            str(port),
        ]

    def _build_blender_cmd(self) -> List[str]:
        proc_cfg = (settings.processes or {}).get("blender", {})
        exe = proc_cfg.get("exe")
        if not exe or not Path(exe).exists():
            raise FileNotFoundError(f"Blender executable not found: {exe}")
        args = list(proc_cfg.get("args", []))
        return [str(exe), *args]

    def _build_blender_bridge_cmd(self) -> List[str]:
        proc_cfg = (settings.processes or {}).get("blender_bridge", {})
        exe = (settings.processes or {}).get("blender", {}).get("exe")
        if not exe or not Path(exe).exists():
            raise FileNotFoundError(f"Blender executable not found for bridge: {exe}")
        script_path = proc_cfg.get("script_path")
        if not script_path or not Path(script_path).exists():
            raise FileNotFoundError(f"Blender bridge script not found: {script_path}")
        host = proc_cfg.get("host", "127.0.0.1")
        port = int(proc_cfg.get("port", 8002))
        # Launch blender with python script and pass host/port via args
        return [
            str(exe),
            "--background",
            "--python",
            str(script_path),
            "--",
            "--host",
            host,
            "--port",
            str(port),
        ]

    # MCP Adapter lifecycle is managed by AgentRunner when configured

    def _spawn(self, name: str, cmd: List[str], timeout: float = 15.0) -> ManagedProcess:
        mp = ManagedProcess(name=name, command=cmd, timeout_start=timeout)
        mp.start()
        with self._lock:
            self.procs[name] = mp
        return mp

    def startUnity(self, project_id: Optional[str]) -> Dict:
        cmd = self._build_unity_cmd(project_id)
        timeout = float((settings.processes or {}).get("unity", {}).get("timeout", 15))
        proc = self._spawn("unity", cmd, timeout)
        return proc.status()

    def startUnityBridge(self) -> Dict:
        # Preflight: port free
        proc_cfg = (settings.processes or {}).get("unity_bridge", {})
        host = proc_cfg.get("host", "127.0.0.1")
        port = int(proc_cfg.get("port", 8001))
        if self._port_in_use(host, port):
            raise RuntimeError(f"Port in use for unity_bridge: {host}:{port}")
        cmd = self._build_unity_bridge_cmd()
        timeout = float((settings.processes or {}).get("unity_bridge", {}).get("timeout", 15))
        proc = self._spawn("unity_bridge", cmd, timeout)
        return proc.status()

    def startBlender(self) -> Dict:
        cmd = self._build_blender_cmd()
        timeout = float((settings.processes or {}).get("blender", {}).get("timeout", 20))
        proc = self._spawn("blender", cmd, timeout)
        return proc.status()

    def startBlenderBridge(self) -> Dict:
        # Preflight: port free
        proc_cfg = (settings.processes or {}).get("blender_bridge", {})
        host = proc_cfg.get("host", "127.0.0.1")
        port = int(proc_cfg.get("port", 8002))
        if self._port_in_use(host, port):
            raise RuntimeError(f"Port in use for blender_bridge: {host}:{port}")
        cmd = self._build_blender_bridge_cmd()
        timeout = float((settings.processes or {}).get("blender_bridge", {}).get("timeout", 20))
        proc = self._spawn("blender_bridge", cmd, timeout)
        return proc.status()

    # def startMCPAdapter(self) -> Dict: ... removed

    def start_sequence(self, project_id: Optional[str]) -> List[Dict]:
        statuses = []
        # Unity
        statuses.append(self.startUnity(project_id))
        # Unity Bridge
        statuses.append(self.startUnityBridge())
        # Blender
        statuses.append(self.startBlender())
        # Blender Bridge
        statuses.append(self.startBlenderBridge())
        # MCP Adapter removed from automatic sequence; managed by AgentRunner
        return statuses

    def stopAll(self) -> None:
        with self._lock:
            names = list(self.procs.keys())
        # Desired stop order: blender_bridge -> unity_bridge -> blender -> unity, then others
        preferred = ["blender_bridge", "unity_bridge", "blender", "unity"]
        ordered = [n for n in preferred if n in names] + [n for n in names if n not in preferred]
        for name in ordered:
            try:
                proc = self.procs.get(name)
                if proc:
                    proc.stop(graceful=True)
            finally:
                with self._lock:
                    self.procs.pop(name, None)

    def status(self) -> List[Dict]:
        with self._lock:
            return [proc.status() for proc in self.procs.values()]


# Global manager instance
process_manager = ProcessManager()
