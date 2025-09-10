"""Verification script for post-cleanup checks.

Runs lightweight validations: inventory present, API endpoints (if running), and basic file presence.
Collects outputs into reports/cleanup_runlogs/.
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / 'reports' / 'cleanup_runlogs'
REPORTS.mkdir(parents=True, exist_ok=True)


def tcp(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def fetch(url: str, timeout: float = 2.0) -> tuple[int, str]:
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec - local
            body = resp.read().decode('utf-8', errors='replace')
            return int(resp.getcode()), body
    except Exception as e:
        return 0, str(e)


def main() -> None:
    logs: Dict[str, Any] = {}
    # Check inventory exists
    inv = ROOT / 'reports' / 'inventory.csv'
    logs['inventory_csv'] = inv.exists()

    # Try API endpoints if gateway is running
    if tcp('127.0.0.1', 8000):
        for path in ['/api/v1/health', '/api/v1/agent/status']:
            code, body = fetch(f'http://127.0.0.1:8000{path}')
            logs[path] = {'code': code, 'ok': 200 <= code < 400}
    else:
        logs['gateway_running'] = False

    out = REPORTS / 'verify_cleanup.json'
    out.write_text(json.dumps(logs, indent=2), encoding='utf-8')
    print(f"Wrote {out}")


if __name__ == '__main__':
    main()

