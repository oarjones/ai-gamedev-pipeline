from __future__ import annotations

import json
import os
from typing import Dict

import json
import socket
import struct
import time


def _ensure_dirs() -> Dict[str, str]:
    base = os.path.join("Generated", "tests", "flow1")
    screens = os.path.join(base, "screens")
    os.makedirs(screens, exist_ok=True)
    return {"base": base, "screens": screens}


def _ws_connect(host: str = "127.0.0.1", port: int = 8765) -> socket.socket:
    # Minimal RFC6455 client (text frames only)
    s = socket.create_connection((host, port), timeout=5)
    key = "dGhlIHNhbXBsZSBub25jZQ=="  # fixed works for simple handshake
    req = (
        f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode("utf-8"))
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = s.recv(1024)
        if not chunk:
            raise RuntimeError("websocket handshake failed")
        buf += chunk
    if b"101" not in buf.split(b"\r\n", 1)[0]:
        raise RuntimeError("websocket handshake not switching protocols")
    return s


def _ws_send_text(s: socket.socket, text: str) -> None:
    payload = text.encode("utf-8")
    b1 = 0x80 | 0x1
    # client frames must be masked
    mask_bit = 0x80
    mask = b"\x12\x34\x56\x78"
    n = len(payload)
    if n < 126:
        header = bytes([b1, mask_bit | n])
    elif n <= 0xFFFF:
        header = bytes([b1, mask_bit | 126]) + struct.pack(">H", n)
    else:
        raise ValueError("payload too large")
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    s.sendall(header + mask + masked)


def _ws_recv_text(s: socket.socket, timeout: float = 15.0) -> str:
    s.settimeout(timeout)
    hdr = s.recv(2)
    if len(hdr) < 2:
        raise RuntimeError("ws closed")
    b1, b2 = hdr[0], hdr[1]
    opcode = b1 & 0x0F
    masked = (b2 & 0x80) != 0
    if opcode == 0x8:
        return ""
    if opcode != 0x1:
        raise RuntimeError("unexpected opcode")
    ln = b2 & 0x7F
    if ln == 126:
        ln = struct.unpack(">H", s.recv(2))[0]
    elif ln == 127:
        raise RuntimeError("unsupported len=127 in test client")
    mask = s.recv(4) if masked else b""
    payload = b""
    while len(payload) < ln:
        chunk = s.recv(ln - len(payload))
        if not chunk:
            raise RuntimeError("ws closed during payload")
        payload += chunk
    if masked and mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return payload.decode("utf-8")


def _call(s: socket.socket, command: str, params: Dict) -> Dict:
    _ws_send_text(s, json.dumps({"command": command, "params": params}))
    raw = _ws_recv_text(s)
    try:
        return json.loads(raw)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"invalid JSON from server: {e}: {raw}")


def run() -> int:
    # Connect WS (runner started the server)
    s = _ws_connect()
    # Identify
    _ws_send_text(s, json.dumps({"identify": True}))
    _ = _ws_recv_text(s)

    # 1) Clear scene
    rc = _call(s, "scene.clear", {})
    assert rc.get("status") == "ok", rc

    # 2) Create primitive cube
    name = "Flow1Cube"
    res = _call(s, "modeling.create_primitive", {"kind": "cube", "params": {"size": 2.0}, "name": name})
    assert res.get("status") == "ok", res
    r = res.get("result", {})
    obj_name = r.get("object_name") or r.get("object", name)

    # 3) Add modifiers and apply all
    assert _call(s, "mod.add_mirror", {"object": obj_name, "axis": "X", "use_clip": True}).get("status") == "ok"
    assert _call(s, "mod.add_subsurf", {"object": obj_name, "levels": 1}).get("status") == "ok"
    assert _call(s, "mod.add_solidify", {"object": obj_name, "thickness": 0.05, "offset": 0.0}).get("status") == "ok"
    assert _call(s, "mod.apply_all", {"object": obj_name}).get("status") == "ok"

    # 4) Edit mesh
    ex = _call(s, "edit.extrude_normal", {"object": obj_name, "face_indices": list(range(4)), "amount": 0.05})
    assert ex.get("status") == "ok", ex
    bv = _call(s, "edit.bevel_edges", {"object": obj_name, "edge_indices": list(range(12)), "offset": 0.02, "segments": 2})
    assert bv.get("status") == "ok", bv

    # 5) Cleanup + metrics + non-manifold
    cl = _call(s, "topology.cleanup_basic", {"object": obj_name, "merge_distance": 1e-5, "limited_angle": 0.349, "force_tris": False})
    assert cl.get("status") == "ok", cl
    stats = _call(s, "analysis.mesh_stats", {"object": obj_name})
    assert stats.get("status") == "ok", stats
    nm = _call(s, "analysis.non_manifold_edges", {"object": obj_name})
    assert nm.get("status") == "ok" and nm.get("result", {}).get("count") == 10, nm

    # 6) Snapshots
    dirs = _ensure_dirs()
    shots: Dict[str, str] = {}
    for view in ("front", "top", "iso"):
        shot = _call(
            s,
            "helpers.snapshot.capture_view",
            {
                "view": view,
                "perspective": (view == "iso"),
                "width": 768 if view == "iso" else 640,
                "height": 768 if view == "iso" else 640,
                "shading": "SOLID",
                "solid_wire": True,
                "enhance": True,
                "color_type": "SINGLE",
                "single_color": [0.25, 0.7, 0.95],
                "bg": "WORLD",
                "world_color": [1.0, 1.0, 1.0],
                "return_base64": False,
            },
        )
        assert shot.get("status") == "ok", shot
        path = shot["result"]["result"]["path"]
        dest = os.path.join(dirs["screens"], f"{view}.png")
        try:
            os.replace(path, dest)
        except Exception:
            try:
                import shutil
                shutil.copy2(path, dest)
            except Exception:
                pass
        shots[view] = dest

    # 7) Summary JSON
    r_stats = stats.get("result", {})
    summary = {
        "object": obj_name,
        "counts": r_stats.get("counts"),
        "surface": r_stats.get("surface"),
        "edge_length": r_stats.get("quality", {}).get("edge_length"),
        "screens": shots,
    }
    with open(os.path.join(dirs["base"], "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    s.close()
    print(json.dumps({"status": "ok", "flow": 1, "summary": summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
