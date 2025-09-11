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
from datetime import datetime


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
    ap.add_argument("--selftest", action="store_true", help="Run a short context-based self test")
    ap.add_argument("--identify", action="store_true", help="Send identify message instead of a command")
    ap.add_argument("--suite", choices=["single", "smoke"], default="smoke", help="Run a predefined smoke suite")
    args = ap.parse_args(argv)

    def save_log(step: str, payload_raw: str | None, payload_obj: dict | None) -> None:
        day = datetime.now().strftime("%Y%m%d")
        base = os.path.join("Generated", "logs", day)
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, f"{step}.json")
        try:
            if payload_obj is not None:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload_obj, f, ensure_ascii=False, indent=2)
            elif payload_raw is not None:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(payload_raw)
        except Exception as e:
            print(f"Failed to write log {path}: {e}")

    if args.suite == "smoke":
        s = ws_connect(args.host, args.port)
        # 01 Identify
        ws_send_text(s, json.dumps({"identify": True}))
        r1_raw = ws_recv_text(s)
        print(r1_raw)
        try:
            r1 = json.loads(r1_raw)
        except Exception:
            r1 = None
        save_log("01_identify", r1_raw, r1)

        # 02 Create primitive (cube)
        name = "SmokeCube"
        cparams = {"type": "cube", "size": 1.0, "name": name}
        ws_send_text(s, json.dumps({"command": "modeling.create_primitive", "params": cparams}))
        r2_raw = ws_recv_text(s)
        print(r2_raw)
        try:
            r2 = json.loads(r2_raw)
        except Exception:
            r2 = None
        save_log("02_create_primitive", r2_raw, r2)

        # 03 Extrude normals on all cube faces (indices 0..5)
        eparams = {"object": name, "face_indices": [0, 1, 2, 3, 4, 5], "distance": 0.2}
        ws_send_text(s, json.dumps({"command": "modeling.extrude_normal", "params": eparams}))
        r3_raw = ws_recv_text(s)
        print(r3_raw)
        try:
            r3 = json.loads(r3_raw)
        except Exception:
            r3 = None
        save_log("03_extrude_normal", r3_raw, r3)

        # 04 Bevel edges on first 12 edges
        bparams = {"object": name, "edge_indices": list(range(12)), "offset": 0.05, "segments": 2, "clamp": True}
        ws_send_text(s, json.dumps({"command": "topology.bevel_edges", "params": bparams}))
        r4_raw = ws_recv_text(s)
        print(r4_raw)
        try:
            r4 = json.loads(r4_raw)
        except Exception:
            r4 = None
        save_log("04_bevel_edges", r4_raw, r4)

        # 05 Recalc normals outward
        nparams = {"object": name, "outside": True}
        ws_send_text(s, json.dumps({"command": "normals.recalc", "params": nparams}))
        r5_raw = ws_recv_text(s)
        print(r5_raw)
        try:
            r5 = json.loads(r5_raw)
        except Exception:
            r5 = None
        save_log("05_normals_recalc", r5_raw, r5)

        s.close()
        return 0

    if args.identify:
        s = ws_connect(args.host, args.port)
        ws_send_text(s, json.dumps({"identify": True}))
        print(ws_recv_text(s))
        s.close()
        return 0
    elif args.selftest:
        s = ws_connect(args.host, args.port)
        for cmd, p in [
            ("server.ping", {}),
            ("topology.ensure_object_mode", {}),
            ("topology.touch_active", {}),
        ]:
            ws_send_text(s, json.dumps({"command": cmd, "params": p}))
            print(ws_recv_text(s))
            time.sleep(0.05)
        s.close()
        return 0
    else:
        s = ws_connect(args.host, args.port)
        payload = json.dumps({"command": args.command, "params": json.loads(args.params)})
        ws_send_text(s, payload)
        resp = ws_recv_text(s)
        print(resp)
        s.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
