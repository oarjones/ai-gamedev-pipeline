"""Process manager for Unity, Blender and bridge servers."""

import logging
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class CircularBuffer:
    def __init__(self, max_size: int = 10240):
        self.buf: List[str] = []
        self.max_size = max_size

    def append(self, text: str) -> None:
        self.buf.append(text)
        size = sum(len(s) for s in self.buf)
        while size > self.max_size and len(self.buf) > 1:
            removed = self.buf.pop(0)
            size -= len(removed)

    def get_text(self, limit: Optional[int] = None) -> str:
        result = "".join(self.buf)
        return result[-limit:] if limit else result


class ManagedProcess:
    def __init__(self, name: str, command: List[str], timeout_start: float = 15.0):
        self.name = name
        self.command = command
        self.timeout_start = timeout_start
        self.proc: Optional[subprocess.Popen] = None
        self.started_at: Optional[str] = None
        self.last_error: Optional[str] = None
        self._stdout_buf = CircularBuffer()
        self._stderr_buf = CircularBuffer()
        self._reader_threads: List[threading.Thread] = []

    def _stream_reader(self, stream, buf: CircularBuffer, label: str) -> None:
        try:
            while True:
                line = stream.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                buf.append(decoded)
                logger.debug(f"[{self.name}/{label}] {decoded.rstrip()}")
        except Exception as e:
            logger.debug(f"Stream reader error for {self.name}/{label}: {e}")

    def start(self) -> None:
        if self.proc:
            return
        
        # Log detallado del comando que se va a ejecutar
        logger.info(f"[{self.name}] Starting process with command: {self.command}")
        logger.info(f"[{self.name}] Executable path: {self.command[0]}")
        
        # Verificar si el ejecutable existe antes de intentar lanzarlo
        exe_path = Path(self.command[0])
        if not exe_path.exists():
            error_msg = f"Executable not found at path: {exe_path}"
            logger.error(f"[{self.name}] {error_msg}")
            logger.error(f"[{self.name}] Absolute path: {exe_path.absolute()}")
            self.last_error = error_msg
            raise FileNotFoundError(error_msg)
            
        try:
            self.proc = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            self.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{self.name}] Process started with PID {self.proc.pid}")
            
            # Start stream readers
            stdout_thread = threading.Thread(
                target=self._stream_reader,
                args=(self.proc.stdout, self._stdout_buf, "stdout"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._stream_reader,
                args=(self.proc.stderr, self._stderr_buf, "stderr"),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()
            self._reader_threads = [stdout_thread, stderr_thread]
            
            # Wait for startup
            time.sleep(min(self.timeout_start, 2.0))
            
        except Exception as e:
            logger.error(f"[{self.name}] Failed to start process: {e}")
            self.last_error = str(e)
            self.proc = None
            raise

    def stop(self, graceful: bool = True) -> None:
        if not self.proc:
            return
        try:
            if graceful:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=2)
            else:
                self.proc.kill()
                self.proc.wait(timeout=2)
        except Exception as e:
            logger.warning(f"[{self.name}] Error stopping process: {e}")
        finally:
            self.proc = None

    def status(self) -> Dict:
        running = self.proc is not None and self.proc.poll() is None
        return {
            "name": self.name,
            "running": running,
            "pid": self.proc.pid if self.proc else None,
            "returnCode": self.proc.returncode if self.proc and not running else None,
            "lastOutput": (self._stdout_buf.get_text())[-1024:],
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
        # Obtener configuración
        proc_cfg = (settings.processes or {}).get("unity", {})
        exe = proc_cfg.get("exe")
        
        # Log detallado de la configuración
        logger.info(f"Unity configuration from settings: {proc_cfg}")
        logger.info(f"Unity exe path from config: {exe}")
        
        if not exe:
            error_msg = "Unity executable path not configured in settings.yaml"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        # Convertir a Path y verificar existencia
        exe_path = Path(exe)
        logger.info(f"Checking Unity executable at: {exe_path}")
        logger.info(f"Absolute path: {exe_path.absolute()}")
        logger.info(f"Exists: {exe_path.exists()}")
        
        if not exe_path.exists():
            # Intentar expandir variables de entorno o rutas relativas
            expanded = Path(os.path.expandvars(os.path.expanduser(exe)))
            logger.info(f"Expanded path: {expanded}")
            logger.info(f"Expanded exists: {expanded.exists()}")
            
            if expanded.exists():
                exe_path = expanded
            else:
                error_msg = f"Unity executable not found at: {exe} (expanded: {expanded})"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
        
        args = list(proc_cfg.get("args", []))
        
        # Resolve project path
        project_path = proc_cfg.get("project_path")
        if not project_path and project_id:
            project_path = str(Path("projects") / project_id)
        if project_path:
            args.extend(["-projectPath", str(project_path)])
            
        logger.info(f"Unity command built: {[str(exe_path)] + args}")
        return [str(exe_path), *args]

    def _build_unity_bridge_cmd(self) -> List[str]:
        proc_cfg = (settings.processes or {}).get("unity_bridge", {})
        host = proc_cfg.get("host", "127.0.0.1")
        port = int(proc_cfg.get("port", 8001))
        python_exe = proc_cfg.get("python", sys.executable)
        app_import = proc_cfg.get("app_import", "mcp_unity_bridge.src.mcp_unity_server.main:app")
        
        logger.info(f"Unity Bridge configuration: host={host}, port={port}, python={python_exe}")
        
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
        
        logger.info(f"Blender configuration: {proc_cfg}")
        logger.info(f"Blender exe path: {exe}")
        
        if not exe:
            error_msg = "Blender executable path not configured"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        exe_path = Path(exe)
        if not exe_path.exists():
            # Intentar expandir variables de entorno
            expanded = Path(os.path.expandvars(os.path.expanduser(exe)))
            if expanded.exists():
                exe_path = expanded
            else:
                error_msg = f"Blender executable not found at: {exe} (expanded: {expanded})"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
                
        args = list(proc_cfg.get("args", []))
        return [str(exe_path), *args]

    def _build_blender_bridge_cmd(self) -> List[str]:
        proc_cfg = (settings.processes or {}).get("blender_bridge", {})
        exe = (settings.processes or {}).get("blender", {}).get("exe")
        
        if not exe:
            error_msg = "Blender executable not configured for bridge"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        exe_path = Path(exe)
        if not exe_path.exists():
            expanded = Path(os.path.expandvars(os.path.expanduser(exe)))
            if expanded.exists():
                exe_path = expanded
            else:
                error_msg = f"Blender executable not found for bridge: {exe}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
                
        script_path = proc_cfg.get("script_path")
        if not script_path or not Path(script_path).exists():
            error_msg = f"Blender bridge script not found: {script_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        host = proc_cfg.get("host", "127.0.0.1")
        port = int(proc_cfg.get("port", 8002))
        
        # Launch blender with python script and pass host/port via args
        return [
            str(exe_path),
            "--background",
            "--python",
            str(script_path),
            "--",
            "--host",
            host,
            "--port",
            str(port),
        ]

    def _spawn(self, name: str, cmd: List[str], timeout: float = 15.0) -> ManagedProcess:
        mp = ManagedProcess(name=name, command=cmd, timeout_start=timeout)
        mp.start()
        with self._lock:
            self.procs[name] = mp
        return mp

    def startUnity(self, project_id: Optional[str]) -> Dict:
        try:
            cmd = self._build_unity_cmd(project_id)
            timeout = float((settings.processes or {}).get("unity", {}).get("timeout", 15))
            proc = self._spawn("unity", cmd, timeout)
            return proc.status()
        except Exception as e:
            logger.error(f"Failed to start Unity: {e}")
            raise

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

    def start_sequence(self, project_id: Optional[str]) -> List[Dict]:
        statuses = []
        
        # Unity
        try:
            logger.info("Starting Unity...")
            statuses.append(self.startUnity(project_id))
        except Exception as e:
            logger.error(f"Unity start failed: {e}")
            raise
            
        # Unity Bridge
        try:
            logger.info("Starting Unity Bridge...")
            statuses.append(self.startUnityBridge())
        except Exception as e:
            logger.error(f"Unity Bridge start failed: {e}")
            # Continue even if bridge fails
            statuses.append({"name": "unity_bridge", "running": False, "error": str(e)})
            
        # Blender (opcional)
        try:
            logger.info("Starting Blender...")
            statuses.append(self.startBlender())
        except Exception as e:
            logger.warning(f"Blender start failed (non-critical): {e}")
            statuses.append({"name": "blender", "running": False, "error": str(e)})
            
        # Blender Bridge (opcional)
        try:
            logger.info("Starting Blender Bridge...")
            statuses.append(self.startBlenderBridge())
        except Exception as e:
            logger.warning(f"Blender Bridge start failed (non-critical): {e}")
            statuses.append({"name": "blender_bridge", "running": False, "error": str(e)})
            
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
                    logger.info(f"Stopping {name}...")
                    proc.stop(graceful=True)
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
            finally:
                with self._lock:
                    self.procs.pop(name, None)

    def status(self) -> List[Dict]:
        with self._lock:
            return [proc.status() for proc in self.procs.values()]


# Global manager instance
process_manager = ProcessManager()