from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import time


GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def random_key() -> str:
    return base64.b64encode(os.urandom(16)).decode()


def ws_connect(host: str, port: int, path: str = "/") -> socket.socket:
    s = socket.create_connection((host, port), timeout=3)
    key = random_key()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode("utf-8"))
    resp = recv_until(s, b"\r\n\r\n", 8192)
    if not resp or b"101" not in resp.split(b"\r\n", 1)[0]:
        raise RuntimeError("handshake failed")
    return s


def recv_until(s: socket.socket, token: bytes, max_bytes: int) -> bytes:
    buf = b""
    while token not in buf:
        chunk = s.recv(1024)
        if not chunk:
            break
        buf += chunk
        if len(buf) > max_bytes:
            break
    return buf


def ws_send_text(s: socket.socket, text: str) -> None:
    # Client must mask frames
    payload = text.encode("utf-8")
    b1 = 0x80 | 0x1
    mask_bit = 0x80
    length = len(payload)
    mask = os.urandom(4)
    if length < 126:
        header = bytes([b1, mask_bit | length])
    elif length <= 0xFFFF:
        header = bytes([b1, mask_bit | 126]) + struct.pack(">H", length)
    else:
        raise ValueError("payload too large for this smoke client")
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    s.sendall(header + mask + masked)


def ws_recv_text(s: socket.socket) -> str:
    hdr = recv_exact(s, 2)
    b1, b2 = hdr[0], hdr[1]
    opcode = b1 & 0x0F
    masked = (b2 & 0x80) != 0
    if opcode == 0x8:
        return ""
    if opcode != 0x1:
        raise RuntimeError("unexpected opcode")
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack(">H", recv_exact(s, 2))[0]
    elif length == 127:
        raise RuntimeError("length 127 unsupported in smoke client")
    mask = recv_exact(s, 4) if masked else b""
    payload = recv_exact(s, length)
    if masked and mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return payload.decode("utf-8")


def recv_exact(s: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise RuntimeError("connection closed")
        buf += chunk
    return buf


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Smoke test for MCP Blender addon WS server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument(
        "--command",
        default="server.ping",
        help="Command to send (e.g., server.ping, modeling.echo)",
    )
    ap.add_argument("--params", default="{}", help="JSON params object")
    args = ap.parse_args(argv)

    s = ws_connect(args.host, args.port)
    payload = json.dumps({"command": args.command, "params": json.loads(args.params)})
    ws_send_text(s, payload)
    resp = ws_recv_text(s)
    print(resp)
    s.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

