"""Lightweight cleanup audit runner.

Generates reports/cleanup_audit.json and .md based on available tools.
Safe: defaults to KEEP unless evidence strongly suggests otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"


def has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(cmd: List[str]) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return 127, "", str(e)


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    findings: List[Dict[str, Any]] = []

    # Example classification: scripts/archive/start_dashboard_old.bat -> MOVE
    legacy_candidates = [ROOT / 'scripts' / 'archive' / 'start_dashboard_old.bat']
    for p in legacy_candidates:
        if p.exists():
            findings.append({
                "file": str(p.relative_to(ROOT)).replace('\\','/'),
                "status": "MOVE",
                "reason": "replaced by dev_up/dev_down and Process Manager",
                "evidence": ["scripts/dev_up.bat", "gateway/app/services/process_manager.py"],
                "risk": "low",
            })

    # Depcheck and ts-prune (if installed)
    if has('npx'):
        code, out, err = run(['npx', 'depcheck', 'webapp'])
        (REPORTS / 'depcheck_webapp.txt').write_text(out or err, encoding='utf-8')
    if has('npx'):
        code, out, err = run(['npx', 'ts-prune', '-p', 'webapp/tsconfig.json'])
        (REPORTS / 'tsprune_webapp.txt').write_text(out or err, encoding='utf-8')

    # Python: vulture and pipdeptree if available in gateway venv
    py = ROOT / 'gateway' / '.venv' / 'Scripts' / 'python.exe'
    if py.exists():
        code, out, err = run([str(py), '-m', 'pipdeptree', '--json-tree'])
        (REPORTS / 'pipdeptree_gateway.json').write_text(out or err, encoding='utf-8')
        code, out, err = run([str(py), '-m', 'vulture', 'gateway', '--min-confidence', '70'])
        (REPORTS / 'vulture_gateway.txt').write_text((out or err), encoding='utf-8')

    # Write audit JSON/MD
    (REPORTS / 'cleanup_audit.json').write_text(json.dumps(findings, indent=2), encoding='utf-8')
    md = ["# Cleanup Audit (initial)", "", "Items:"]
    for f in findings:
        md.append(f"- {f['file']} → {f['status']} ({f['reason']})")
    (REPORTS / 'cleanup_audit.md').write_text("\n".join(md) + "\n", encoding='utf-8')
    print("Wrote cleanup_audit.json and .md")


if __name__ == '__main__':
    main()

