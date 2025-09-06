"""WebSocket event handling for AI Gateway."""

import json
import logging
from typing import Dict, Set
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for event broadcasting."""
    
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket) -> None:
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a personal message to a specific WebSocket."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all connected WebSockets."""
        if not self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for event streaming."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                # Parse JSON message
                message_data = json.loads(data)
                event_type = message_data.get("type", "unknown")
                payload = message_data.get("payload", {})
                
                logger.info(f"Received WebSocket message: type={event_type}")
                
                # Echo message back to sender with timestamp
                response = {
                    "type": "echo",
                    "original_type": event_type,
                    "payload": payload,
                    "timestamp": datetime.utcnow().isoformat(),
                    "server": "ai-gateway"
                }
                
                await manager.send_personal_message(json.dumps(response), websocket)
                
                # Broadcast to all other clients (excluding sender)
                if event_type == "broadcast":
                    broadcast_msg = {
                        "type": "broadcast",
                        "payload": payload,
                        "timestamp": datetime.utcnow().isoformat(),
                        "server": "ai-gateway"
                    }
                    
                    for conn in manager.active_connections:
                        if conn != websocket:
                            await manager.send_personal_message(json.dumps(broadcast_msg), conn)
                
            except json.JSONDecodeError:
                # Handle non-JSON messages as simple text echo
                response = {
                    "type": "text_echo",
                    "message": data,
                    "timestamp": datetime.utcnow().isoformat(),
                    "server": "ai-gateway"
                }
                await manager.send_personal_message(json.dumps(response), websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)