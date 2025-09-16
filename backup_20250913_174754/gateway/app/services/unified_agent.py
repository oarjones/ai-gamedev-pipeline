"""
Servicio de Agente Simplificado
Reemplaza: gateway/app/services/unified_agent.py

Este servicio gestiona el ciclo de vida del agente Gemini CLI de forma simple y robusta.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from app.services.process_manager import process_manager

logger = logging.getLogger(__name__)


@dataclass 
class AgentStatus:
    """Estado del agente."""
    running: bool
    pid: Optional[int]
    cwd: Optional[str]
    agentType: str = "gemini"
    lastError: Optional[str] = None
    bridgesReady: bool = False


class SimpleAgentService:
    """
    Servicio simplificado para gestionar Gemini CLI.
    
    Principios:
    - Simplicidad: Solo gestiona el proceso, no intercepta comunicación
    - Robustez: Manejo de errores y recuperación automática
    - Transparencia: Gemini CLI se comunica directamente con MCP
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.provider: Optional[Any] = None  # GeminiCliProvider
        self.project_id: Optional[str] = None
        self.cwd: Optional[Path] = None
        self.last_error: Optional[str] = None
        self._lock = asyncio.Lock()
        
    async def start(self, cwd: Path, agent_type: str = "gemini") -> AgentStatus:
        """
        Inicia el agente en el directorio del proyecto.
        
        Args:
            cwd: Directorio del proyecto
            agent_type: Tipo de agente (solo 'gemini' soportado actualmente)
        """
        async with self._lock:
            if agent_type != "gemini":
                raise ValueError(f"Tipo de agente no soportado: {agent_type}")
            
            self.cwd = Path(cwd)
            self.project_id = self.cwd.name
            self.last_error = None
            
            try:
                # Paso 1: Verificar que los bridges están listos (opcional)
                bridges_ready = await self._check_bridges()
                if not bridges_ready:
                    self.logger.warning(
                        "Bridges no detectados. Gemini puede no tener acceso a todas las tools."
                    )
                
                # Paso 2: Crear e iniciar el provider
                from .providers.gemini_cli import GeminiCliProvider, GeminiChatIntegration
                
                self.provider = GeminiCliProvider(self.project_id)
                integration = GeminiChatIntegration(self.provider)
                self.provider.set_output_callback(integration.handle_output)
                
                # Paso 3: Iniciar Gemini CLI
                show_console = await self._should_show_console()
                status = await self.provider.start(self.cwd, show_console=show_console)
                
                if not status.running:
                    raise RuntimeError("No se pudo iniciar Gemini CLI")
                
                self.logger.info(
                    f"Agente Gemini iniciado - PID: {status.pid}, CWD: {status.cwd}"
                )
                
                return AgentStatus(
                    running=True,
                    pid=status.pid,
                    cwd=str(self.cwd),
                    agentType="gemini",
                    lastError=None,
                    bridgesReady=bridges_ready
                )
                
            except Exception as e:
                self.logger.error(f"Error iniciando agente: {e}")
                self.last_error = str(e)
                
                # Intentar diagnóstico
                diagnostic = await self._diagnose_startup_error(e)
                if diagnostic:
                    self.last_error = f"{self.last_error}\n{diagnostic}"
                
                return AgentStatus(
                    running=False,
                    pid=None,
                    cwd=str(self.cwd),
                    agentType="gemini",
                    lastError=self.last_error,
                    bridgesReady=False
                )
    
    async def stop(self) -> AgentStatus:
        """Detiene el agente si está ejecutándose."""
        async with self._lock:
            if self.provider:
                try:
                    await self.provider.stop()
                    self.logger.info("Agente detenido correctamente")
                except Exception as e:
                    self.logger.error(f"Error deteniendo agente: {e}")
                finally:
                    self.provider = None
            
            return AgentStatus(
                running=False,
                pid=None,
                cwd=str(self.cwd) if self.cwd else None,
                agentType="gemini",
                lastError=None
            )
    
    def status(self) -> AgentStatus:
        """Obtiene el estado actual del agente."""
        if not self.provider:
            return AgentStatus(
                running=False,
                pid=None,
                cwd=str(self.cwd) if self.cwd else None,
                agentType="gemini",
                lastError=self.last_error
            )
        
        status = self.provider.status()
        bridges_ready = self._check_bridges_sync()
        
        return AgentStatus(
            running=status.running,
            pid=status.pid,
            cwd=status.cwd,
            agentType="gemini",
            lastError=self.last_error,
            bridgesReady=bridges_ready
        )
    
    async def send(self, text: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía texto al agente.
        
        Args:
            text: Mensaje a enviar
            correlation_id: ID de correlación opcional para tracking
        """
        if not self.provider:
            raise RuntimeError("El agente no está ejecutándose")
        
        try:
            # Enviar al proceso
            await self.provider.send(text)
            
            # Registrar en chat service
            from app.services.chat import chat_service
            from uuid import uuid4
            
            msg_id = str(uuid4())
            
            # Persistir mensaje del usuario
            try:
                from app.db import ChatMessageDB, db
                db.add_chat_message(
                    ChatMessageDB(
                        msg_id=msg_id,
                        project_id=self.project_id or "",
                        role="user",
                        content=text
                    )
                )
            except Exception as e:
                self.logger.error(f"Error persistiendo mensaje: {e}")
            
            # Enviar evento de chat por WebSocket
            from app.ws.events import manager
            from app.models import Envelope, EventType
            import json
            
            env = Envelope(
                type=EventType.CHAT,
                project_id=self.project_id,
                payload={
                    "role": "user",
                    "content": text,
                    "msgId": msg_id
                },
                correlationId=correlation_id
            )
            
            await manager.broadcast_project(
                self.project_id or "",
                json.dumps(env.model_dump(by_alias=True))
            )
            
            return {
                "queued": True,
                "msgId": msg_id,
                "correlationId": correlation_id
            }
            
        except Exception as e:
            self.logger.error(f"Error enviando mensaje: {e}")
            raise RuntimeError(f"Error comunicándose con el agente: {e}")
    
    async def _check_bridges(self) -> bool:
        """Verifica si los bridges están ejecutándose."""
        try:
            statuses = process_manager.status()
            running_processes = {s.get("name") for s in statuses if s.get("running")}
            
            # Unity Bridge es el principal
            unity_bridge_ok = "unity_bridge" in running_processes
            
            # También verificar via health check si es posible
            if not unity_bridge_ok:
                unity_bridge_ok = await self._probe_unity_bridge()
            
            return unity_bridge_ok
            
        except Exception as e:
            self.logger.debug(f"Error verificando bridges: {e}")
            return False
    
    def _check_bridges_sync(self) -> bool:
        """Versión síncrona de check_bridges para status()."""
        try:
            statuses = process_manager.status()
            running_processes = {s.get("name") for s in statuses if s.get("running")}
            return "unity_bridge" in running_processes
        except:
            return False
    
    async def _probe_unity_bridge(self) -> bool:
        """Intenta conectar al Unity Bridge para verificar que está activo."""
        try:
            from app.services.config_service import get_all
            cfg = get_all(mask_secrets=False) or {}
            port = cfg.get("bridges", {}).get("unityBridgePort", 8001)
            
            # Intento simple de conexión TCP
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            
            return result == 0
            
        except Exception:
            return False
    
    async def _should_show_console(self) -> bool:
        """Determina si mostrar la consola de Gemini CLI."""
        try:
            from app.services.config_service import get_all
            cfg = get_all(mask_secrets=False) or {}
            return cfg.get("providers", {}).get("geminiCli", {}).get("showConsole", False)
        except:
            return False
    
    async def _diagnose_startup_error(self, error: Exception) -> Optional[str]:
        """
        Intenta diagnosticar el error de inicio para dar mejor feedback.
        """
        error_str = str(error).lower()
        diagnostics = []
        
        if "not found" in error_str or "no such file" in error_str:
            diagnostics.append(
                "Gemini CLI no encontrado. Instalar con:\n"
                "  npm install -g @google/generative-ai-cli"
            )
        
        if "permission" in error_str:
            diagnostics.append(
                "Error de permisos. Verificar que el usuario tiene acceso al directorio del proyecto."
            )
        
        if "bridge" in error_str:
            diagnostics.append(
                "Los bridges no están activos. Iniciar con:\n"
                "  POST /api/v1/system/start"
            )
        
        return "\n".join(diagnostics) if diagnostics else None
    
    async def ensure_bridges_running(self) -> bool:
        """
        Intenta asegurar que los bridges estén ejecutándose.
        Útil para auto-recuperación.
        """
        if await self._check_bridges():
            return True
        
        try:
            self.logger.info("Intentando iniciar bridges automáticamente...")
            
            # Iniciar Unity Bridge
            process_manager.startUnityBridge()
            await asyncio.sleep(2)
            
            # Verificar de nuevo
            return await self._check_bridges()
            
        except Exception as e:
            self.logger.error(f"No se pudieron iniciar bridges: {e}")
            return False


# Instancia singleton
agent_service = SimpleAgentService()

# Alias para compatibilidad
agent = agent_service