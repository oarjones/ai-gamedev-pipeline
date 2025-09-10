"""Dependencies and virtual environments manager.

Provides safe helpers to create venvs, install requirements/packages, and
check installed packages, broadcasting logs via the WebSocket manager.
"""

from __future__ import annotations

import os
import re
import sys
import time
import json
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from app.services import config_service
from app.ws.events import manager
from app.models.core import Envelope, EventType


REPO_ROOT = Path(".").resolve()


def _normalize_relpath(p: str) -> Path:
    """Resolve a repository-internal path safely (no escapes)."""
    if not p:
        raise ValueError("path required")
    pp = (REPO_ROOT / p).resolve()
    if not str(pp).startswith(str(REPO_ROOT)):
        raise ValueError("Path escapes repository root")
    return pp


def _venv_python(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _allowed_package(name: str, whitelist: Iterable[str]) -> bool:
    if not re.match(r"^[A-Za-z0-9_.\-]+$", name or ""):
        return False
    base = name.split("[")[0].split("==")[0].split(">=")[0].split("<=")[0]
    base = base.strip().lower()
    wl = {w.split("[")[0].split("==")[0].strip().lower() for w in whitelist}
    return base in wl


def _read_requirements(files: List[str]) -> List[str]:
    pkgs: List[str] = []
    for rf in files:
        p = _normalize_relpath(rf)
        if not p.exists():
            continue
        if p.suffix.lower() == ".txt":
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                pkgs.append(s)
        elif p.name == "pyproject.toml":
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                # naive parse of dependencies = [ ... ]
                import tomllib  # py3.11+; in 3.12 exists
                data = tomllib.loads(text)
                deps = data.get("project", {}).get("dependencies", [])
                if isinstance(deps, list):
                    pkgs.extend([str(d) for d in deps])
            except Exception:
                pass
    # Normalize dedupe
    norm = []
    seen = set()
    for s in pkgs:
        base = s.split("[")[0].split("==")[0].split(">=")[0].split("<=")[0].strip().lower()
        if base and base not in seen:
            seen.add(base)
            norm.append(s)
    return norm


def build_whitelist() -> List[str]:
    cfg = config_service.get_all(mask_secrets=False)
    deps_cfg = (cfg.get("dependencies") or {})
    files = deps_cfg.get("requirementFiles", []) or []
    extra = deps_cfg.get("extraAllowed", []) or []
    combined = _read_requirements(files)
    combined.extend(extra)
    # Deduplicate by base name
    out: List[str] = []
    seen = set()
    for s in combined:
        base = s.split("[")[0].split("==")[0].split(">=")[0].split("<=")[0].strip().lower()
        if base and base not in seen:
            seen.add(base)
            out.append(s)
    return out


def _broadcast_line(project_id: str, step: str, line: str, status: str = "progress") -> None:
    try:
        env = Envelope(
            type=EventType.LOG,
            project_id=project_id,
            payload={
                "source": "deps",
                "step": step,
                "status": status,
                "line": line,
            },
        )
        import json as _json
        manager.broadcast_project(project_id, env.model_dump_json(by_alias=True))  # type: ignore
    except Exception:
        pass


def _run_and_stream(cmd: List[str], cwd: Optional[Path], project_id: str, step: str, timeout: float) -> int:
    proc = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    start = time.time()
    _broadcast_line(project_id, step, f"$ {' '.join(shlex.quote(c) for c in cmd)}", status="started")
    assert proc.stdout is not None
    for line in proc.stdout:
        _broadcast_line(project_id, step, line.rstrip())
        if time.time() - start > timeout:
            proc.kill()
            _broadcast_line(project_id, step, "Timed out", status="error")
            return 124
    rc = proc.wait()
    _broadcast_line(project_id, step, f"exit code {rc}", status=("completed" if rc == 0 else "error"))
    return rc


def createVenv(path: str, project_id: str = "system") -> Dict[str, str]:
    venv_dir = _normalize_relpath(path)
    if venv_dir.exists():
        raise FileExistsError("virtual environment already exists")
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    python_exe = sys.executable
    rc = _run_and_stream([python_exe, "-m", "venv", str(venv_dir)], cwd=None, project_id=project_id, step="create-venv", timeout=90)
    if rc != 0:
        raise RuntimeError(f"venv creation failed with code {rc}")
    return {"venvPath": str(venv_dir)}


def installFromRequirements(venvPath: str, requirementsPath: str, project_id: str = "system") -> Dict[str, str]:
    venv = _normalize_relpath(venvPath)
    req = _normalize_relpath(requirementsPath)
    py = _venv_python(venv)
    if not py.exists():
        raise FileNotFoundError("venv python not found; create venv first")
    if not req.exists():
        raise FileNotFoundError("requirements file not found")
    rc = _run_and_stream([str(py), "-m", "pip", "install", "-r", str(req)], cwd=REPO_ROOT, project_id=project_id, step="install-reqs", timeout=600)
    if rc != 0:
        raise RuntimeError(f"pip install -r failed with code {rc}")
    return {"ok": "installed"}


def installPackages(venvPath: str, packages: List[str], project_id: str = "system") -> Dict[str, str]:
    venv = _normalize_relpath(venvPath)
    py = _venv_python(venv)
    if not py.exists():
        raise FileNotFoundError("venv python not found; create venv first")
    wl = build_whitelist()
    safe: List[str] = []
    for p in packages or []:
        if _allowed_package(p, wl):
            safe.append(p)
        else:
            raise ValueError(f"package not allowed: {p}")
    if not safe:
        return {"ok": "no-packages"}
    cmd = [str(py), "-m", "pip", "install", *safe]
    rc = _run_and_stream(cmd, cwd=REPO_ROOT, project_id=project_id, step="install-pkgs", timeout=600)
    if rc != 0:
        raise RuntimeError(f"pip install failed with code {rc}")
    return {"ok": "installed"}


def checkInstalled(venvPath: str, packages: List[str]) -> List[Dict[str, Optional[str]]]:
    venv = _normalize_relpath(venvPath)
    py = _venv_python(venv)
    if not py.exists():
        raise FileNotFoundError("venv python not found; create venv first")
    script = (
        "import json,sys;\n"
        "try:\n"
        " import importlib.metadata as md\n"
        "except Exception:\n"
        " import importlib_metadata as md\n"
        "res=[]\n"
        "for n in sys.argv[1:]:\n"
        "  try:\n"
        "   v=md.version(n.split('[')[0])\n"
        "   res.append({'name':n,'installed':True,'version':v})\n"
        "  except Exception:\n"
        "   res.append({'name':n,'installed':False})\n"
        "print(json.dumps(res))\n"
    )
    proc = subprocess.run([str(py), "-c", script, *packages], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    try:
        return json.loads(proc.stdout)
    except Exception:
        return []

