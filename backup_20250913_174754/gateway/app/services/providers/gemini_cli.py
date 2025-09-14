"""
Gemini CLI Provider - Puente Transparente Simplificado
Reemplaza: gateway/app/services/providers/gemini_cli.py

Este provider actúa como un puente transparente entre la UI y Gemini CLI.
NO intenta interceptar o procesar tool calls ya que Gemini CLI las maneja directamente.
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
from typing import Optional, Callable, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GeminiStatus:
    """Estado del proceso Gemini CLI."""
    running: bool
    pid: Optional[int]
    started_at: Optional[datetime]
    cwd: Optional[str]
    command: Optional[str]


class GeminiCliProvider:
    """
    Puente transparente entre UI y Gemini CLI.
    
    Responsabilidades:
    - Lanzar el proceso Gemini CLI en el directorio del proyecto
    - Enviar input del usuario a stdin
    - Leer stdout/stderr y enviarlo a la UI vía WebSocket
    - NO procesar tool calls (Gemini las maneja internamente)
    """
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.process: Optional[asyncio.subprocess.Process] = None
        self.stdout_task: Optional[asyncio.Task] = None
        self.stderr_task: Optional[asyncio.Task] = None
        self.status_info = GeminiStatus(
            running=False,
            pid=None,
            started_at=None,
            cwd=None,
            command=None
        )
        self._output_callback: Optional[Callable] = None
        self._running = False
        self._lock = asyncio.Lock()
        
    def set_output_callback(self, callback: Callable[[str, str], asyncio.Coroutine]) -> None:
        """
        Establece callback para manejar salida del CLI.
        callback(text: str, stream: 'stdout'|'stderr') -> None
        """
        self._output_callback = callback
        
    async def start(self, cwd: Path, show_console: bool = False) -> GeminiStatus:
        """Inicia Gemini CLI en el directorio del proyecto."""
        async with self._lock:
            if self._running and self.process:
                logger.warning("Gemini CLI ya está ejecutándose")
                return self.status_info
                
            # Obtener comando de Gemini
            command = self._get_gemini_command()
            if not command:
                raise RuntimeError(
                    "Gemini CLI no encontrado. Instalar con:\n"
                    "npm install -g @google/generative-ai-cli"
                )
            
            # Preparar entorno
            env = os.environ.copy()
            # NO necesitamos GEMINI_API_KEY si el usuario ya está autenticado
            
            # Preparar comando para Windows
            launch_cmd = self._prepare_launch_command(command, cwd)
            
            logger.info(f"Iniciando Gemini CLI: {' '.join(launch_cmd)}")
            logger.info(f"Directorio de trabajo: {cwd}")
            
            try:
                # Configurar flags para Windows si se quiere mostrar consola
                creation_flags = 0
                if os.name == 'nt' and show_console:
                    import subprocess
                    creation_flags = subprocess.CREATE_NEW_CONSOLE  # type: ignore
                
                # Lanzar proceso
                self.process = await asyncio.create_subprocess_exec(
                    *launch_cmd,
                    cwd=str(cwd),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    creationflags=creation_flags if os.name == 'nt' else 0
                )
                
                self._running = True
                self.status_info = GeminiStatus(
                    running=True,
                    pid=self.process.pid,
                    started_at=datetime.now(),
                    cwd=str(cwd),
                    command=' '.join(launch_cmd)
                )
                
                # Iniciar lectores de salida
                self.stdout_task = asyncio.create_task(
                    self._read_stdout(),
                    name=f"gemini-stdout-{self.project_id}"
                )
                self.stderr_task = asyncio.create_task(
                    self._read_stderr(),
                    name=f"gemini-stderr-{self.project_id}"
                )
                
                logger.info(f"Gemini CLI iniciado con PID: {self.process.pid}")
                return self.status_info
                
            except FileNotFoundError as e:
                self._running = False
                raise RuntimeError(f"No se pudo ejecutar Gemini CLI: {e}")
            except Exception as e:
                self._running = False
                logger.error(f"Error iniciando Gemini CLI: {e}")
                raise
                
    async def stop(self) -> None:
        """Detiene el proceso Gemini CLI de forma limpia."""
        async with self._lock:
            if not self.process:
                return
                
            logger.info(f"Deteniendo Gemini CLI (PID: {self.process.pid})")
            
            # Cancelar tareas de lectura
            for task in [self.stdout_task, self.stderr_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Terminar proceso
            if self.process.returncode is None:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Timeout esperando terminación, forzando kill")
                    self.process.kill()
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
            
            self.process = None
            self._running = False
            self.status_info.running = False
            logger.info("Gemini CLI detenido")
            
    async def send(self, text: str) -> None:
        """Envía texto al stdin de Gemini CLI."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Gemini CLI no está ejecutándose")
        
        # Asegurar que termina con newline
        if not text.endswith('\n'):
            text += '\n'
        
        try:
            logger.debug(f"Enviando a Gemini: {text[:100]}...")
            self.process.stdin.write(text.encode('utf-8'))
            await self.process.stdin.drain()
        except Exception as e:
            logger.error(f"Error enviando texto a Gemini: {e}")
            raise RuntimeError(f"Error comunicándose con Gemini CLI: {e}")
            
    def status(self) -> GeminiStatus:
        """Retorna el estado actual del proceso."""
        # Verificar si el proceso sigue vivo
        if self.process and self.process.returncode is not None:
            self._running = False
            self.status_info.running = False
        return self.status_info
        
    async def _read_stdout(self) -> None:
        """Lee stdout línea por línea y envía a callback."""
        if not self.process or not self.process.stdout:
            return
            
        try:
            while True:
                line_bytes = await self.process.stdout.readline()
                if not line_bytes:
                    break  # EOF
                    
                line = line_bytes.decode('utf-8', errors='replace').rstrip('\r\n')
                if line and self._output_callback:
                    try:
                        await self._output_callback(line, 'stdout')
                    except Exception as e:
                        logger.error(f"Error en callback stdout: {e}")
                        
        except asyncio.CancelledError:
            logger.debug("Lectura de stdout cancelada")
        except Exception as e:
            logger.error(f"Error leyendo stdout: {e}")
            
    async def _read_stderr(self) -> None:
        """Lee stderr línea por línea y envía a callback."""
        if not self.process or not self.process.stderr:
            return
            
        try:
            while True:
                line_bytes = await self.process.stderr.readline()
                if not line_bytes:
                    break  # EOF
                    
                line = line_bytes.decode('utf-8', errors='replace').rstrip('\r\n')
                
                # Filtrar mensajes conocidos que no son errores
                if self._is_benign_stderr(line):
                    logger.debug(f"Gemini stderr (benigno): {line}")
                    continue
                    
                if line and self._output_callback:
                    try:
                        # stderr generalmente son errores o warnings
                        await self._output_callback(line, 'stderr')
                    except Exception as e:
                        logger.error(f"Error en callback stderr: {e}")
                        
        except asyncio.CancelledError:
            logger.debug("Lectura de stderr cancelada")
        except Exception as e:
            logger.error(f"Error leyendo stderr: {e}")
            
    def _is_benign_stderr(self, line: str) -> bool:
        """Identifica mensajes de stderr que no son errores reales."""
        benign_patterns = [
            "Error during discovery for server",  # MCP discovery normal
            "Connection closed",  # Cierre normal de conexión
            "Starting MCP server",  # Mensaje informativo
        ]
        return any(pattern in line for pattern in benign_patterns)
        
    def _get_gemini_command(self) -> Optional[list[str]]:
        """Obtiene el comando para ejecutar Gemini CLI."""
        # 1. Verificar configuración
        try:
            from app.services.config_service import get_all
            cfg = get_all(mask_secrets=False) or {}
            cmd = cfg.get("providers", {}).get("geminiCli", {}).get("command")
            if cmd:
                if isinstance(cmd, str):
                    return shlex.split(cmd)
                elif isinstance(cmd, list):
                    return cmd
        except Exception as e:
            logger.debug(f"No se pudo leer config: {e}")
        
        # 2. Buscar en PATH
        gemini_path = shutil.which("gemini")
        if gemini_path:
            return [gemini_path]
        
        # 3. Buscar en ubicaciones comunes (Windows)
        if os.name == 'nt':
            candidates = self._find_windows_gemini()
            if candidates:
                return [candidates[0]]
        
        # 4. Buscar en node_modules local
        local_paths = [
            Path("node_modules/.bin/gemini"),
            Path("node_modules/.bin/gemini.cmd"),
        ]
        for p in local_paths:
            if p.exists():
                return [str(p)]
        
        return None
        
    def _find_windows_gemini(self) -> list[str]:
        """Busca Gemini en ubicaciones comunes de Windows."""
        paths = []
        appdata = os.environ.get("APPDATA")
        
        if appdata:
            # npm global
            npm_paths = [
                Path(appdata) / "npm" / "gemini.cmd",
                Path(appdata) / "npm" / "gemini.ps1",
                Path(appdata) / "npm" / "gemini",
            ]
            for p in npm_paths:
                if p.exists():
                    paths.append(str(p))
                    
        return paths
        
    def _prepare_launch_command(self, command: list[str], cwd: Path) -> list[str]:
        """Prepara el comando para lanzar en Windows/Unix."""
        if os.name != 'nt':
            return command
            
        # Windows: manejar diferentes tipos de scripts
        cmd_path = Path(command[0])
        ext = cmd_path.suffix.lower()
        
        if ext == '.cmd' or ext == '.bat':
            # Usar cmd.exe para archivos .cmd/.bat
            return ["cmd.exe", "/c", str(cmd_path)] + command[1:]
        elif ext == '.ps1':
            # Usar PowerShell para scripts .ps1
            return [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(cmd_path)
            ] + command[1:]
        else:
            # Ejecutar directamente
            return command


# Clase de integración con el ChatService
class GeminiChatIntegration:
    """Integra GeminiCliProvider con el sistema de chat/WebSocket."""
    
    def __init__(self, provider: GeminiCliProvider):
        self.provider = provider
        self.project_id = provider.project_id
        
    async def handle_output(self, text: str, stream: str) -> None:
        """Maneja la salida de Gemini y la envía por WebSocket."""
        from app.services.chat import chat_service
        from app.ws.events import manager
        from app.models import Envelope, EventType
        import json
        from uuid import uuid4
        
        if stream == 'stderr':
            # Errores van como eventos de log
            env = Envelope(
                type=EventType.LOG,
                projectId=self.project_id,
                payload={
                    "level": "error",
                    "message": text
                }
            )
            await manager.broadcast_project(
                self.project_id,
                json.dumps(env.model_dump(by_alias=True))
            )
        else:
            # stdout va como mensaje del agente
            msg_id = str(uuid4())
            
            # Persistir en BD
            try:
                from app.db import ChatMessageDB, db
                db.add_chat_message(
                    ChatMessageDB(
                        msg_id=msg_id,
                        project_id=self.project_id,
                        role="agent",
                        content=text
                    )
                )
            except Exception as e:
                logger.error(f"Error persistiendo mensaje: {e}")
            
            # Enviar por WebSocket
            env = Envelope(
                type=EventType.CHAT,
                projectId=self.project_id,
                payload={
                    "role": "agent",
                    "content": text,
                    "msgId": msg_id
                }
            )
            await manager.broadcast_project(
                self.project_id,
                json.dumps(env.model_dump(by_alias=True))
            )