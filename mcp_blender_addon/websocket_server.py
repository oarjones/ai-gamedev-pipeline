from __future__ import annotations

import base64
import hashlib
import json
import socket
import threading
from typing import Any, Dict, Optional

from .server.logging import get_logger
from .server.registry import Registry
from .server.utils import parse_json_message, ok, error
from .server.executor import Executor


WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketServer:
    """Very small WebSocket server (RFC 6455 subset) using stdlib only.

    - Supports text frames from client (opcode 1) and sends text frames.
    - Handles payload lengths up to 65535 (no 64-bit lengths).
    - One thread for accept, per-connection handled sequentially (no broadcast).
    - Intended for local development/tools; not production-grade.
    """

    def __init__(self, host: str, port: int, registry: Registry, executor: Executor):
        self.host = host
        self.port = port
        self._registry = registry
        self._executor = executor
        self._log = get_logger(__name__)
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stopping = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopping.clear()
        self._thread = threading.Thread(target=self._serve, name="WS-Server", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        try:
            if self._sock:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._sock.close()
        finally:
            self._sock = None
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    # --- Internal server loop ---

    def _serve(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(1)
        self._sock = s
        self._log.info("Listening on ws://%s:%d", self.host, self.port)
        while not self._stopping.is_set():
            try:
                s.settimeout(0.5)
                conn, addr = s.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_conn, args=(conn, addr), daemon=True).start()

    def _handle_conn(self, conn: socket.socket, addr) -> None:
        conn.settimeout(5.0)
        try:
            if not self._handshake(conn):
                conn.close()
                return
            self._log.info("WebSocket connected: %s", addr)
            while not self._stopping.is_set():
                msg = self._recv_ws_text(conn)
                if msg is None:
                    break
                jm, err = parse_json_message(msg)
                if err:
                    self._send_ws_text(conn, json.dumps(error(err)))
                    continue
                try:
                    result = self._dispatch(jm.command, jm.params)
                    self._send_ws_text(conn, json.dumps(ok(result)))
                except KeyError as e:
                    self._send_ws_text(conn, json.dumps(error(str(e), code="unknown_command")))
                except Exception as e:  # noqa: BLE001
                    self._send_ws_text(conn, json.dumps(error(str(e), code="exception")))
        except Exception as e:  # noqa: BLE001
            self._log.info("Connection error: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _dispatch(self, name: str, params: Dict[str, Any]) -> Any:
        # If a command handler needs Blender main thread, it should use executor internally.
        return self._registry.dispatch(name, params)

    # --- WebSocket protocol helpers (tiny subset) ---

    def _handshake(self, conn: socket.socket) -> bool:
        # Read HTTP request
        request = self._recv_until(conn, b"\r\n\r\n", max_bytes=8192)
        if not request:
            return False
        headers = self._parse_http_headers(request.decode("utf-8", "replace"))
        if headers.get("upgrade", "").lower() != "websocket":
            return False
        key = headers.get("sec-websocket-key")
        if not key:
            return False
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        conn.sendall(response.encode("utf-8"))
        return True

    @staticmethod
    def _parse_http_headers(raw: str) -> Dict[str, str]:
        lines = raw.split("\r\n")
        out: Dict[str, str] = {}
        for ln in lines[1:]:
            if not ln or ":" not in ln:
                continue
            k, v = ln.split(":", 1)
            out[k.strip().lower()] = v.strip()
        return out

    @staticmethod
    def _recv_until(conn: socket.socket, token: bytes, max_bytes: int) -> bytes | None:
        buf = b""
        while token not in buf:
            chunk = conn.recv(1024)
            if not chunk:
                return None
            buf += chunk
            if len(buf) > max_bytes:
                return None
        return buf

    def _recv_exact(self, conn: socket.socket, n: int) -> bytes | None:
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _recv_ws_text(self, conn: socket.socket) -> Optional[str]:
        # Read frame header
        hdr = self._recv_exact(conn, 2)
        if not hdr:
            return None
        b1, b2 = hdr[0], hdr[1]
        fin = (b1 & 0x80) != 0
        opcode = b1 & 0x0F
        masked = (b2 & 0x80) != 0
        length = b2 & 0x7F
        if opcode == 0x8:  # close
            return None
        if opcode != 0x1:  # only text frames supported
            return None
        if length == 126:
            ext = self._recv_exact(conn, 2)
            if not ext:
                return None
            length = int.from_bytes(ext, "big")
        elif length == 127:
            # Not supported in this minimal implementation
            return None
        mask_key = self._recv_exact(conn, 4) if masked else None
        payload = self._recv_exact(conn, length)
        if payload is None:
            return None
        if masked and mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        try:
            return payload.decode("utf-8")
        except Exception:
            return None

    def _send_ws_text(self, conn: socket.socket, text: str) -> None:
        payload = text.encode("utf-8")
        b1 = 0x80 | 0x1  # FIN + text
        length = len(payload)
        if length < 126:
            header = bytes([b1, length])
        elif length <= 0xFFFF:
            header = bytes([b1, 126]) + length.to_bytes(2, "big")
        else:
            # Very large payloads not supported in this minimal server
            header = bytes([b1, 126]) + (0).to_bytes(2, "big")
        frame = header + payload
        conn.sendall(frame)

