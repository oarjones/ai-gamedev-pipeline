import os
import time
import json
import subprocess
import sys
from pathlib import Path

from app.services.adapter_lock import lock_path, status as adapter_status


def _cleanup_lock():
    try:
        lp = lock_path()
        if lp.exists():
            lp.unlink()
    except Exception:
        pass


def test_adapter_start_stop_cycle():
    _cleanup_lock()

    # Start adapter as a subprocess (module)
    cmd = [sys.executable, "-u", "-m", "mcp_unity_bridge.mcp_adapter"]
    env = os.environ.copy()
    env["AGP_ADAPTER_TESTMODE"] = "1"
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        # Wait a bit for lockfile to appear
        deadline = time.time() + 5.0
        while time.time() < deadline:
            st = adapter_status()
            if st.get("running"):
                break
            time.sleep(0.1)
        st = adapter_status()
        assert st.get("running") is True
        assert isinstance(st.get("pid"), int) and st.get("pid") > 0

        # Stop
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except Exception:
            proc.kill()
            proc.wait(timeout=2.0)

        # After stop, status should become not running (allow a moment for cleanup)
        time.sleep(0.3)
        st2 = adapter_status()
        assert not st2.get("running")

        # Start again OK
        proc2 = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            deadline = time.time() + 5.0
            ok = False
            while time.time() < deadline:
                st3 = adapter_status()
                if st3.get("running"):
                    ok = True
                    break
                time.sleep(0.1)
            assert ok
        finally:
            try:
                proc2.terminate()
                proc2.wait(timeout=2.0)
            except Exception:
                try:
                    proc2.kill()
                    proc2.wait(timeout=1.0)
                except Exception:
                    pass
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=1.0)
            except Exception:
                pass
        _cleanup_lock()
