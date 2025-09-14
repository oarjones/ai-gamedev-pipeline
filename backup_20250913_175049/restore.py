#!/usr/bin/env python3
"""Script para restaurar backup"""
import shutil
from pathlib import Path

def restore():
    backup_dir = Path(__file__).parent
    root_dir = backup_dir.parent
    
    files = [
        "gateway/app/services/unified_agent.py",
        "gateway/app/services/providers/gemini_cli.py",
        "gateway/app/services/agent_runner.py",
        "config/settings.yaml",
    ]
    
    for file_path in files:
        src = backup_dir / file_path
        dst = root_dir / file_path
        if src.exists():
            print(f"Restaurando: {file_path}")
            shutil.copy2(src, dst)
    
    print("OK Restauracion completada")

if __name__ == "__main__":
    restore()
