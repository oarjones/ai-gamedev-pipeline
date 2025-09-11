"""Health checks for local services (Unity/Blender/Bridges/MCP) and self-test orchestration."""

from __future__ import annotations

import asyncio
import json
import socket
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from pathlib import Path

from app.services.process_manager import process_manager
from app.services.adapter_lock import status as adapter_status
from app.services.unified_agent import agent as unified_agent
from app.services.config_service import get_all


def _tcp_check(host: str, port: int, timeout: float = 1.5) -> Tuple[bool, str]:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True, "tcp-ok"
    except Exception as e:
        return False, f"tcp-fail: {e}"


async def _http_check(url: str, timeout: float = 1.5) -> Tuple[bool, str]:
    try:
        import urllib.request

        req = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - local URL
            code = resp.getcode()
            return (200 <= int(code) < 500), f"http-{code}"
    except Exception as e:
        return False, f"http-fail: {e}"


async def _ws_check(url: str, timeout: float = 2.0) -> Tuple[bool, str]:
    try:
        import websockets  # type: ignore

        async with websockets.connect(url, open_timeout=timeout, close_timeout=timeout):  # type: ignore
            return True, "ws-ok"
    except Exception as e:
        return False, f"ws-fail: {e}"


@dataclass
class ComponentStatus:
    name: str
    running: bool
    endpoint_ok: bool
    detail: str


async def get_health() -> Dict[str, Any]:
    cfg = get_all(mask_secrets=True)
    procs = {s.get("name"): s for s in process_manager.status()}

    ub_port = int(((cfg.get("bridges") or {}).get("unityBridgePort") or 8001))
    bb_port = int(((cfg.get("bridges") or {}).get("blenderBridgePort") or 8002))

    statuses: List[ComponentStatus] = []

    # Unity Bridge HTTP
    ok_tcp, det_tcp = _tcp_check("127.0.0.1", ub_port)
    ok_http, det_http = await _http_check(f"http://127.0.0.1:{ub_port}/")
    statuses.append(
        ComponentStatus(
            name="unity_bridge",
            running=bool(procs.get("unity_bridge", {}).get("running")),
            endpoint_ok=bool(ok_tcp and ok_http),
            detail=f"{det_tcp}; {det_http}",
        )
    )

    # Blender Bridge HTTP
    ok_tcp2, det_tcp2 = _tcp_check("127.0.0.1", bb_port)
    ok_http2, det_http2 = await _http_check(f"http://127.0.0.1:{bb_port}/")
    statuses.append(
        ComponentStatus(
            name="blender_bridge",
            running=bool(procs.get("blender_bridge", {}).get("running")),
            endpoint_ok=bool(ok_tcp2 and ok_http2),
            detail=f"{det_tcp2}; {det_http2}",
        )
    )

    # MCP Adapter (status by lockfile) + WS via Unity Bridge
    ok_ws, det_ws = await _ws_check(f"ws://127.0.0.1:{ub_port}/ws/gemini_cli_adapter")
    ad_st = adapter_status()
    statuses.append(
        ComponentStatus(
            name="mcp_adapter",
            running=bool(ad_st.get("running")),
            endpoint_ok=bool(ok_ws),
            detail=det_ws,
        )
    )

    # GUI processes: unity, blender (running flag only)
    for name in ("unity", "blender"):
        statuses.append(
            ComponentStatus(
                name=name,
                running=bool(procs.get(name, {}).get("running")),
                endpoint_ok=bool(procs.get(name, {}).get("running")),
                detail="process-running" if procs.get(name, {}).get("running") else "process-stopped",
            )
        )

    return {
        "ok": all(s.endpoint_ok for s in statuses),
        "components": [asdict(s) for s in statuses],
    }


async def run_selftest(project_id: Optional[str] = None) -> Dict[str, Any]:
    report: Dict[str, Any] = {"steps": []}

    def _step(name: str, ok: bool, detail: str = "") -> None:
        report["steps"].append({"name": name, "ok": bool(ok), "detail": detail})

    # 1) Ensure processes
    try:
        process_manager.start_sequence(project_id)
        _step("start-sequence", True, "started or already running")
    except Exception as e:
        _step("start-sequence", False, str(e))

    # 2) Health for endpoints
    health = await get_health()
    _step("health-check", bool(health.get("ok")), json.dumps(health))

    # 3) Agent-only ping via shim (deterministic)
    try:
        # Prepare temp session cwd (use active project if not provided)
        active = project_id
        if not active:
            st = unified_agent.status()
            active = (st.cwd or "").split("/")[-1] or None
        cwd = Path("projects") / (active or "_selftest")
        try:
            cwd.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        # Start provider-based session
        await unified_agent.start(cwd, "gemini")
        # Compose deterministic prompt for shim
        prompt = "Por favor, llama la tool `ping` y devuelve exactamente JSON {\"mcp_ping\":\"pong\"}. No añadas texto adicional."
        corr = "selftest-ping"
        await unified_agent.send(prompt, correlation_id=corr)
        # Await tool_result('ping') from AgentRunner internal queue
        from app.services.agent_runner import agent_runner as _runner
        item = await _runner.wait_tool_result("ping", corr, timeout=5.0)
        ok = bool(item and item.get("ok"))
        _step("agent-ping", ok, json.dumps(item or {}))
        # Clean up session
        try:
            await unified_agent.stop()
        except Exception:
            pass
    except Exception as e:
        _step("agent-ping", False, str(e))

    report["passed"] = all(s.get("ok") for s in report["steps"])  # type: ignore
    return report
