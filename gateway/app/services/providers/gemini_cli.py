from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import shutil
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import re
import os

from .base import IAgentProvider, SessionCtx, ProviderEvent, EventCallback

logger = logging.getLogger(__name__)


def _mask(val: Optional[str]) -> str:
    try:
        if not val:
            return "-"
        s = str(val)
        return "****" + s[-4:] if len(s) > 4 else "****"
    except Exception:
        return "-"


def _resolve_command() -> list[str]:
    # Prefer centralized config if present
    try:
        from app.services.config_service import get_all
        cfg = get_all(mask_secrets=True) or {}
        prov = ((cfg.get("providers") or {}).get("geminiCli") or {})
        cmd = prov.get("command") if isinstance(prov, dict) else None
        if cmd:
            if isinstance(cmd, str):
                return shlex.split(cmd)
            if isinstance(cmd, list):
                return [str(c) for c in cmd]
    except Exception:
        pass
    # Fallback to 'gemini' on PATH
    return ["gemini"]


def _find_gemini_fallback() -> Optional[str]:
    """Try to discover gemini CLI in common locations when not on PATH.

    - Windows global npm: %APPDATA%/npm/gemini.cmd or gemini.ps1
    - Repo-local node_modules/.bin/gemini(.cmd)
    """
    try:
        # Windows global npm bin
        appdata = os.environ.get("APPDATA")
        candidates: list[Path] = []
        if appdata:
            candidates.extend([
                Path(appdata) / "npm" / "gemini.cmd",
                Path(appdata) / "npm" / "gemini.ps1",
                Path(appdata) / "npm" / "gemini",
            ])
        # Repo-local node_modules/.bin
        try:
            repo_root = Path(__file__).resolve().parents[4]
        except Exception:
            repo_root = Path.cwd()
        candidates.extend([
            repo_root / "node_modules" / ".bin" / "gemini.cmd",
            repo_root / "node_modules" / ".bin" / "gemini.ps1",
            repo_root / "node_modules" / ".bin" / "gemini",
        ])
        for p in candidates:
            if p.exists():
                return str(p)
    except Exception:
        pass
    return None


@dataclass
class _State:
    proc: Optional[asyncio.subprocess.Process] = None
    reader_task: Optional[asyncio.Task] = None
    err_task: Optional[asyncio.Task] = None


class GeminiCliProvider(IAgentProvider):
    def __init__(self, session: SessionCtx) -> None:
        self._session = session
        self._state = _State()
        self._cb: Optional[EventCallback] = None
        # One-shot configuration
        try:
            from app.services.config_service import get_all
            cfg = get_all(mask_secrets=False) or {}
            provs = (cfg.get("providers") or {})
            # Support both snake_case (new) and camelCase (legacy)
            g_new = provs.get("gemini_cli") or {}
            g_old = provs.get("geminiCli") or {}
            node_path = g_new.get("node_executable_path") or g_old.get("nodeExecutablePath") or g_old.get("node") or "node"
            script_path = g_new.get("gemini_script_path") or g_old.get("geminiScriptPath") or g_old.get("script")
            self.node_path = str(node_path or "node")
            self.script_path = str(script_path or "")
            if not self.script_path or not os.path.exists(self.script_path):
                raise FileNotFoundError(f"Gemini CLI JS script not found at: {self.script_path}")
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.warning("[GeminiCliProvider] Failed to load one-shot config: %s", e)
            # Defaults allow later fallback discovery in legacy start()/send() flow
            self.node_path = "node"
            self.script_path = ""

    def onEvent(self, cb: EventCallback) -> None:
        self._cb = cb

    async def start(self, session: SessionCtx) -> None:
        if self._state.proc and self._state.proc.returncode is None:
            return
        cmd = _resolve_command()
        # Validate executable availability or attempt fallback discovery
        exe = cmd[0] if cmd else None
        if not exe:
            raise RuntimeError("Gemini CLI command not configured (providers.geminiCli.command)")
        path_exists = Path(exe).exists()
        on_path = shutil.which(exe) is not None
        if not path_exists and not on_path:
            fb = _find_gemini_fallback()
            if fb:
                logger.info("[GeminiCliProvider] Using fallback gemini at %s", fb)
                cmd[0] = fb
            else:
                raise RuntimeError(
                    f"Gemini CLI not found: '{exe}'. Configure gateway.config.providers.geminiCli.command or add to PATH."
                )
        # Working dir set to project folder if exists
        cwd = Path("projects") / session.project_id
        if not cwd.exists():
            cwd = Path.cwd()
        env = os.environ.copy()
        # Read optional provider config
        show_console = False
        extra_args: list[str] = []
        use_project_bat = False
        try:
            from app.services.config_service import get_all
            cfg = get_all(mask_secrets=True) or {}
            prov = ((cfg.get("providers") or {}).get("geminiCli") or {})
            show_console = bool(prov.get("showConsole", False))
            use_project_bat = bool(prov.get("useProjectBat", False))
            ea = prov.get("args")
            if isinstance(ea, list):
                extra_args = [str(x) for x in ea]
            xenv = prov.get("extraEnv") or {}
            if isinstance(xenv, dict):
                for k, v in xenv.items():
                    env[str(k)] = str(v)
            # Ensure repo root in PYTHONPATH for local imports the CLI may need
            repo_root = Path(__file__).resolve().parents[4]
            pyp = env.get("PYTHONPATH")
            newp = str(repo_root)
            env["PYTHONPATH"] = f"{newp}{os.pathsep}{pyp}" if pyp else newp
            logger.info("[GeminiCliProvider] Set PYTHONPATH for subprocess: %s", env["PYTHONPATH"])
        except Exception:
            pass
        # Add repo root to PYTHONPATH to find the 'mcp' package and other local modules.
        # This is crucial for the subprocess to resolve local dependencies.
        try:
            repo_root = Path(__file__).resolve().parents[4]
            existing_path = env.get("PYTHONPATH", "")
            # Prepend repo_root to ensure it's checked first.
            env["PYTHONPATH"] = os.pathsep.join(p for p in [str(repo_root), existing_path] if p)
            logger.info("[GeminiCliProvider] Set PYTHONPATH for subprocess: %s", env["PYTHONPATH"])
        except Exception as e:
            logger.warning("[GeminiCliProvider] Failed to set PYTHONPATH for subprocess: %s", e)
        # Windows: wrap .cmd/.bat/.ps1 with proper host
        launch_cmd = list(cmd)
        try:
            if use_project_bat:
                bat = (cwd / "start_gemini_cli.bat").resolve()
                if not bat.exists():
                    raise RuntimeError(f"Launcher BAT not found at {bat}")
                logger.info("[GeminiCliProvider] Using project launcher: %s", str(bat))
                if os.name == 'nt':
                    launch_cmd = ["cmd.exe", "/c", str(bat), *extra_args]
                else:
                    # Fallback for non-Windows environments
                    launch_cmd = [str(bat), *extra_args]
                # When launching via BAT, prefer showing console and don't capture IO
                show_console = True or show_console
            else:
                if os.name == 'nt':
                    exe_path = Path(cmd[0])
                    ext = exe_path.suffix.lower()
                    if ext in ('.cmd', '.bat'):
                        launch_cmd = ["cmd.exe", "/c", str(exe_path), *cmd[1:], *extra_args]
                    elif ext == '.ps1':
                        launch_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(exe_path), *cmd[1:], *extra_args]
                    else:
                        launch_cmd = [*cmd, *extra_args]
                else:
                    launch_cmd = [*cmd, *extra_args]
        except Exception:
            pass

        safe_cmd = " ".join(shlex.quote(p) for p in launch_cmd)
        # Detailed diagnostics before launch
        try:
            import json as _json
            logger.info("[GeminiCliProvider] Starting: %s (cwd=%s)", safe_cmd, str(cwd))
            logger.info("[GeminiCliProvider] argv: %s", _json.dumps(launch_cmd))
            path = env.get("PATH", "")
            has_npm = ("AppData" in path and "npm" in path) or ("node_modules" in path)
            logger.info(
                "[GeminiCliProvider] Env: GEMINI_API_KEY=%s, PYTHONPATH=%s, PATH_HAS_NPM=%s, showConsole=%s",
                _mask(env.get("GEMINI_API_KEY")), env.get("PYTHONPATH"), has_npm, str(show_console),
            )
        except Exception:
            pass
        try:
            creationflags = 0
            if os.name == 'nt' and show_console:
                try:
                    creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
                except Exception:
                    creationflags = 0
            # If showing console, do not capture stdout/stderr so the window displays output
            capture = not show_console
            self._state.proc = await asyncio.create_subprocess_exec(
                *launch_cmd,
                cwd=str(cwd),
                stdin=asyncio.subprocess.PIPE,
                stdout=(asyncio.subprocess.PIPE if capture else None),
                stderr=(asyncio.subprocess.PIPE if capture else None),
                env=env,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Gemini CLI executable not found: '{exe}'. Configure providers.geminiCli.command in settings.yaml"
            )
        except NotImplementedError:
            # Fallback for Windows event loops without subprocess support
            creationflags = 0
            if os.name == 'nt' and show_console:
                try:
                    creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
                except Exception:
                    creationflags = 0
            p = subprocess.Popen(
                launch_cmd,
                cwd=str(cwd),
                stdin=subprocess.PIPE,
                stdout=(subprocess.PIPE if not show_console else None),
                stderr=(subprocess.PIPE if not show_console else None),
                env=env,
                creationflags=creationflags,
            )

            class _PopenWrap:
                def __init__(self, pop: subprocess.Popen):
                    self._p = pop
                @property
                def returncode(self):
                    return self._p.poll()
                @property
                def stdin(self):
                    return self._p.stdin
                @property
                def stdout(self):
                    return self._p.stdout
                @property
                def stderr(self):
                    return self._p.stderr
                @property
                def pid(self):
                    return self._p.pid
                def terminate(self):
                    try: self._p.terminate()
                    except Exception: pass
                def kill(self):
                    try: self._p.kill()
                    except Exception: pass
            self._state.proc = _PopenWrap(p)  # type: ignore[assignment]
        except Exception as e:
            logger.error("[GeminiCliProvider] Failed to start: %s", e)
            raise
        # If output is captured, start readers; otherwise rely on console window for debugging
        if self._state.proc.stdout is not None:
            self._state.reader_task = asyncio.create_task(self._stdout_reader(), name="gemini-cli-stdout")
        if self._state.proc.stderr is not None:
            self._state.err_task = asyncio.create_task(self._stderr_reader(), name="gemini-cli-stderr")

    # One-Shot execution path (non-REPL)
    def run_one_shot(self, full_prompt: str, working_dir: str) -> Tuple[Optional[str], Optional[str]]:
        """Run Gemini CLI once by invoking node with the CLI entry script.

        Returns (answer_clean, stderr_raw). If stderr has content but answer exists,
        it's considered a warning; if stderr has content and answer is empty, it's an error.
        """
        if not self.script_path or not os.path.exists(self.script_path):
            return None, f"CLI script not found: {self.script_path}"
        command = [self.node_path, self.script_path, full_prompt]
        print(f"[GeminiProvider] Ejecutando One-Shot en CWD: {working_dir}")
        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                check=False,
            )
            stdout_raw = result.stdout or ""
            stderr_raw = result.stderr or ""
            
            logger.info(f"[GeminiCliProvider] raw stdout: {stdout_raw}")

            answer_clean = self._clean_output(stdout_raw)
            if stderr_raw and not answer_clean:
                logger.error("[GEMINI_STDERR_FATAL] %s", stderr_raw.strip())
                return None, stderr_raw
            if stderr_raw and answer_clean:
                logger.warning("[GEMINI_STDERR_WARN] %s", stderr_raw.strip())
            return answer_clean, (stderr_raw or None)
        except subprocess.TimeoutExpired:
            return None, "Error: Timeout. El CLI tardó demasiado."
        except Exception as e:
            return None, f"Error crítico de Python (Subprocess): {str(e)}"

    def _clean_output(self, raw_output: str) -> str:
        """Remove ANSI escapes and known CLI noise from output."""
        # Extract JSON from markdown block
        match = re.search(r"```json\n({.*})\n```", raw_output, re.DOTALL)
        if match:
            return match.group(1).strip()

        if not raw_output:
            return ""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        processed = ansi_escape.sub("", raw_output)
        # Remove common noise lines
        noise_patterns = [
            r"Tips for getting started:.*",
            r"Loaded cached credentials\.",
            r"Authenticated via.*",
            r"^[-\\|/\\\\\\^]+$",  # spinners and lines
        ]
        for pat in noise_patterns:
            processed = re.sub(pat, "", processed, flags=re.MULTILINE)
        return processed.strip()

    async def stop(self) -> None:
        p = self._state.proc
        if not p:
            return
        try:
            if p.returncode is None:
                p.terminate()
                try:
                    await asyncio.wait_for(p.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    p.kill()
                    try:
                        await asyncio.wait_for(p.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
        finally:
            self._state.proc = None
            # Cancel readers
            for t in (self._state.reader_task, self._state.err_task):
                if t and not t.done():
                    t.cancel()
                    try:
                        await t
                    except Exception:
                        pass
            self._state.reader_task = None
            self._state.err_task = None

    async def send(self, user_message: str) -> None:
        p = self._state.proc
        if not p or p.returncode is not None or not p.stdin:
            raise RuntimeError("Provider process is not running")
        line = (user_message or "") + "\n"
        p.stdin.write(line.encode("utf-8"))

        # Handle both asyncio StreamWriter and wrapped subprocess.PIPE
        if hasattr(p.stdin, 'drain'):
            await p.stdin.drain()
        else:
            # For wrapped subprocess.Popen, flush synchronously
            if hasattr(p.stdin, 'flush'):
                p.stdin.flush()

    def status(self) -> dict:
        p = self._state.proc
        running = bool(p and p.returncode is None)
        pid = p.pid if running and p else None
        return {"name": "gemini_cli", "running": running, "pid": pid}

    async def _stdout_reader(self) -> None:
        p = self._state.proc
        if not p or not p.stdout:
            logger.error("[GeminiCliProvider] No stdout to read from.")
            return
        logger.info("[GeminiCliProvider] Starting stdout reader.")
        try:
            # Try async stream first
            try:
                while True:
                    raw = await p.stdout.readline()
                    if not raw:
                        logger.info("[GeminiCliProvider] stdout EOF.")
                        break
                    text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    logger.info(f"[GeminiCliProvider] stdout: {text}")
                    if not text:
                        continue
                    ev = _parse_line(text)
                    await self._emit(ev)
            except TypeError:
                # Fallback: blocking readline in executor
                loop = asyncio.get_running_loop()
                while True:
                    raw = await loop.run_in_executor(None, p.stdout.readline)
                    if not raw:
                        logger.info("[GeminiCliProvider] stdout EOF.")
                        break
                    text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    logger.info(f"[GeminiCliProvider] stdout: {text}")
                    if not text:
                        continue
                    ev = _parse_line(text)
                    await self._emit(ev)
        except asyncio.CancelledError:
            logger.info("[GeminiCliProvider] stdout reader cancelled.")
        except Exception as e:
            logger.error("Error reading from stdout: %s", e, exc_info=True)
            await self._emit(ProviderEvent(kind="error", payload={"message": f"stdout reader failed: {e}"}))

    async def _stderr_reader(self) -> None:
        p = self._state.proc
        if not p or not p.stderr:
            logger.error("[GeminiCliProvider] No stderr to read from.")
            return
        logger.info("[GeminiCliProvider] Starting stderr reader.")
        try:
            try:
                while True:
                    raw = await p.stderr.readline()
                    if not raw:
                        logger.info("[GeminiCliProvider] stderr EOF.")
                        break
                    text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    logger.info(f"[GeminiCliProvider] stderr: {text}")
                    # Known benign MCP discovery message; downgrade to debug
                    if "Error during discovery for server 'unity_editor'" in text and "Connection closed" in text:
                        logger.debug("[GeminiCliProvider] MCP discovery closed: %s", text)
                    else:
                        await self._emit(ProviderEvent(kind="error", payload={"message": text}))
            except TypeError:
                loop = asyncio.get_running_loop()
                while True:
                    raw = await loop.run_in_executor(None, p.stderr.readline)
                    if not raw:
                        logger.info("[GeminiCliProvider] stderr EOF.")
                        break
                    text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    logger.info(f"[GeminiCliProvider] stderr: {text}")
                    if "Error during discovery for server 'unity_editor'" in text and "Connection closed" in text:
                        logger.debug("[GeminiCliProvider] MCP discovery closed: %s", text)
                    else:
                        await self._emit(ProviderEvent(kind="error", payload={"message": text}))
        except asyncio.CancelledError:
            logger.info("[GeminiCliProvider] stderr reader cancelled.")
        except Exception as e:
            logger.error("Error reading from stderr: %s", e, exc_info=True)

    async def _emit(self, ev: ProviderEvent) -> None:
        if self._cb:
            try:
                await self._cb(ev)
            except Exception:
                pass


def _parse_line(line: str) -> ProviderEvent:
    # Detect tool_call shim
    try:
        obj = json.loads(line)
        if isinstance(obj, dict) and isinstance(obj.get("tool_call"), dict):
            tc = obj["tool_call"]
            name = str(tc.get("name"))
            args = tc.get("args")
            return ProviderEvent(kind="tool_call", payload={"name": name, "args": args})
    except Exception:
        pass
    # Default: token stream
    return ProviderEvent(kind="token", payload={"content": line})
