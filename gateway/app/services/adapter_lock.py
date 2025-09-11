from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


LOCKFILE_NAME = "agp_mcp_adapter.lock"


def lock_path() -> Path:
    return Path(os.environ.get("TEMP", tempfile.gettempdir())) / LOCKFILE_NAME


def _is_pid_alive(pid: int) -> bool:
    try:
        if pid <= 0:
            return False
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            OpenProcess = kernel32.OpenProcess
            OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            OpenProcess.restype = wintypes.HANDLE
            GetExitCodeProcess = kernel32.GetExitCodeProcess
            GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            GetExitCodeProcess.restype = wintypes.BOOL
            CloseHandle = kernel32.CloseHandle
            CloseHandle.argtypes = [wintypes.HANDLE]
            CloseHandle.restype = wintypes.BOOL

            h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            try:
                code = wintypes.DWORD()
                if not GetExitCodeProcess(h, ctypes.byref(code)):
                    return False
                return int(code.value) == STILL_ACTIVE
            finally:
                try:
                    CloseHandle(h)
                except Exception:
                    pass
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def read() -> Optional[Dict[str, Any]]:
    p = lock_path()
    try:
        if not p.exists():
            return None
        data = p.read_text(encoding="utf-8")
        obj = json.loads(data)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def status() -> Dict[str, Any]:
    info = read() or {}
    pid = int(info.get("pid") or 0)
    running = _is_pid_alive(pid) if pid else False
    return {"running": running, "pid": pid if running else None, "startedAt": info.get("startedAt")}

