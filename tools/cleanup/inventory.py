import csv
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

def main() -> None:
    rows = []
    for p in ROOT.rglob('*'):
        if p.is_dir():
            continue
        try:
            stat = p.stat()
            rows.append({
                'path': str(p.relative_to(ROOT)).replace('\\','/'),
                'size': stat.st_size,
                'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'ext': p.suffix,
                'dir': str(p.parent.relative_to(ROOT)).replace('\\','/'),
            })
        except Exception:
            pass
    out = REPORTS / 'inventory.csv'
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['path','size','mtime','ext','dir'])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out}")

if __name__ == '__main__':
    main()

