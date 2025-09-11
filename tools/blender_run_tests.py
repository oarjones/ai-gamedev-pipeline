from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
from typing import List


DEFAULT_TESTS = [
    "mcp_blender_addon.tests.test_modeling_flow_1",
    "mcp_blender_addon.tests.test_modeling_flow_2",
]


def _bootstrap_code(project_root: str, test_modules: List[str]) -> str:
    # Python code to be executed inside Blender with --python-expr
    tests_list = ",".join(repr(m) for m in test_modules)
    return textwrap.dedent(
        f"""
        import sys, os, importlib
        sys.path.insert(0, {project_root!r})
        # Register add-on (ensures commands are imported) and start WS server
        import mcp_blender_addon as addon
        try:
            addon.register()
        except Exception as e:
            print("[bootstrap] register failed:", e)
        try:
            addon.start_server("127.0.0.1", 8765)
            print("[bootstrap] WS server started at ws://127.0.0.1:8765")
        except Exception as e:
            print("[bootstrap] start_server failed:", e)
        # Optionally list commands
        try:
            from mcp_blender_addon.commands import _analysis_metrics  # noqa
            from mcp_blender_addon.server.context import SessionContext
            ctx = SessionContext(has_bpy=True, executor=None)
        except Exception as e:
            print("[bootstrap] ctx failed:", e)
            ctx = None

        failures = 0
        tests = [{tests_list}]
        for modname in tests:
            try:
                mod = importlib.import_module(modname)
                if hasattr(mod, 'run'):
                    code = mod.run() if ctx is None else mod.run()
                    # If run() returns a non-zero code, count as failure
                    if int(code or 0) != 0:
                        failures += 1
                else:
                    print(f"[bootstrap] module {{modname}} has no run()")
                    failures += 1
            except SystemExit as se:
                failures += int(getattr(se, 'code', 1) or 1)
            except Exception as e:
                print(f"[bootstrap] exception in {{modname}}:", e)
                failures += 1

        # Exit Blender with appropriate code
        import bpy
        try:
            bpy.ops.wm.quit_blender()
        except Exception:
            pass
        import sys as _sys
        _sys.exit(failures)
        """
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Blender add-on tests (flows)")
    ap.add_argument("--blender", dest="blender", default=os.environ.get("BLENDER_EXE", "blender"), help="Path to Blender executable")
    ap.add_argument("--project-root", dest="root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), help="Project root path")
    ap.add_argument("tests", nargs="*", default=DEFAULT_TESTS, help="Test module paths (python import paths)")
    ap.add_argument("--background", dest="background", action="store_true", help="Run Blender in background mode")
    args = ap.parse_args()

    blender = args.blender
    root = os.path.abspath(args.root)
    tests = list(args.tests)
    code = _bootstrap_code(root, tests)

    cmd = [
        blender,
        "--python-use-system-env",
    ]
    if args.background:
        cmd.append("--background")
    cmd.extend(["--python-expr", code])

    print("[runner] launching:", " ".join(cmd[:3] + ["<bootstrap>..."]))
    try:
        res = subprocess.run(cmd, check=False)
        return int(res.returncode or 0)
    except FileNotFoundError:
        print("[runner] Blender executable not found:", blender)
        return 127


# - python tools/blender_run_tests.py --background
# - o con ruta explícita de Blender: python tools/blender_run_tests.py --background --blender "C:\Path\To\blender.exe"

if __name__ == "__main__":
    raise SystemExit(main())
