from __future__ import annotations

import json
import os
from typing import Dict

import json
import socket
import struct


def _ensure_dirs() -> Dict[str, str]:
    base = os.path.join("Generated", "tests", "flow2")
    screens = os.path.join(base, "screens")
    os.makedirs(screens, exist_ok=True)
    return {"base": base, "screens": screens}


def _templates_root() -> str:
    # Expect blueprint images to live under project templates directory
    # e.g., templates/front.png, templates/left.png, templates/top.png
    here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    # here points to project root (ai-gamedev-pipeline)
    # If tests are moved, adjust accordingly
    return os.path.join(here, "templates")


def _ws_connect(host: str = "127.0.0.1", port: int = 8765) -> socket.socket:
    s = socket.create_connection((host, port), timeout=5)
    key = "dGhlIHNhbXBsZSBub25jZQ=="
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
    s = _ws_connect()
    _ws_send_text(s, json.dumps({"identify": True}))
    _ = _ws_recv_text(s)

    # 1) Clear scene
    assert _call(s, "scene.clear", {}).get("status") == "ok"

    # 2) Create base object
    base_name = "Flow2Base"
    cres = _call(s, "modeling.create_primitive", {"kind": "cube", "params": {"size": 2.0}, "name": base_name})
    assert cres.get("status") == "ok", cres
    r = cres.get("result", {})
    obj_name = r.get("object_name") or r.get("object", base_name)

    # 3) Setup blueprints using templates
    troot = _templates_root()
    img_front = os.path.join(troot, "front.png")
    img_left = os.path.join(troot, "left.png")
    img_top = os.path.join(troot, "top.png")
    bps = _call(s, "ref.blueprints_setup", {"front": img_front, "left": img_left, "top": img_top, "size": 2.0, "opacity": 0.5, "lock": True})
    assert bps.get("status") == "ok", bps

    # 4) Fit bbox to front
    fit = _call(s, "reference.fit_bbox_to_blueprint", {"object": obj_name, "view": "front", "threshold": 0.5, "uniform_scale": False})
    assert fit.get("status") == "ok", fit

    # 5) Snap silhouette (front)
    snap = _call(s, "reference.snap_silhouette_to_blueprint", {"object": obj_name, "view": "front", "threshold": 0.5, "max_iters": 5, "step": 0.02, "smooth_lambda": 0.25, "smooth_iters": 1})
    assert snap.get("status") == "ok", snap

    # 6) Reconstruct from alpha (left) and boolean union
    rec = _call(s, "reference.reconstruct_from_alpha", {"name": "Flow2FromAlpha", "image": img_left, "view": "left", "thickness": 0.15, "threshold": 0.5, "simplify_tol": 2.0})
    assert rec.get("status") == "ok", rec
    new_obj = rec.get("result", {}).get("object_name")
    m = _call(s, "mod.add_boolean", {"object": obj_name, "operation": "UNION", "operand_object": new_obj})
    assert m.get("status") == "ok", m
    ap = _call(s, "mod.apply", {"object": obj_name, "name": m.get("result", {}).get("modifier")})
    assert ap.get("status") == "ok", ap

    # 7) Snapshots
    dirs = _ensure_dirs()
    shots: Dict[str, str] = {}
    for view, persp in (("front", False), ("left", False), ("top", False), ("iso", True)):
        shot = _call(
            s,
            "helpers.snapshot.capture_view",
            {
                "view": view,
                "perspective": persp,
                "width": 768 if view == "iso" else 640,
                "height": 768 if view == "iso" else 640,
                "shading": "SOLID",
                "solid_wire": True,
                "enhance": True,
                "color_type": "MATERIAL",
                "bg": "WORLD",
                "return_base64": False,
            },
        )
        assert shot.get("status") == "ok", shot
        path = shot["result"]["path"]
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

    # 8) Metrics
    met = _call(s, "analysis.mesh_stats", {"object": obj_name})
    assert met.get("status") == "ok", met
    nm = _call(s, "analysis.non_manifold_edges", {"object": obj_name})
    assert nm.get("status") == "ok", nm

    # 9) Summary
    summary = {
        "object": obj_name,
        "counts": met.get("result", {}).get("counts"),
        "non_manifold": nm.get("result", {}).get("count"),
        "screens": shots,
        "blueprints": {"front": img_front, "left": img_left, "top": img_top},
    }
    with open(os.path.join(dirs["base"], "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    s.close()
    print(json.dumps({"status": "ok", "flow": 2, "summary": summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
