from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

from .models import LogEntry, QueryFilters


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts REAL NOT NULL,
              component TEXT NOT NULL,
              level TEXT NOT NULL,
              module TEXT NOT NULL,
              message TEXT NOT NULL,
              category TEXT,
              correlation_id TEXT,
              stack TEXT,
              performance_ms REAL,
              extra TEXT
            );
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_logs_component ON logs(component);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);")
        conn.commit()


def insert_log(db_path: Path, entry: LogEntry) -> None:
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO logs (ts, component, level, module, message, category, correlation_id, stack, performance_ms, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.timestamp,
                entry.component,
                entry.level.value,
                entry.module,
                entry.message,
                entry.category,
                entry.correlation_id,
                entry.stack,
                entry.performance_ms,
                (None if not entry.extra else __import__("json").dumps(entry.extra, ensure_ascii=False)),
            ),
        )
        conn.commit()


def query_logs(db_path: Path, filters: QueryFilters, limit: int = 500) -> List[LogEntry]:
    import json

    clauses: List[str] = []
    args: List[object] = []
    if filters.component:
        clauses.append("component = ?")
        args.append(filters.component)
    if filters.level:
        clauses.append("level = ?")
        args.append(filters.level.value)
    if filters.keyword:
        clauses.append("message LIKE ?")
        args.append(f"%{filters.keyword}%")
    if filters.start_ts is not None:
        clauses.append("ts >= ?")
        args.append(filters.start_ts)
    if filters.end_ts is not None:
        clauses.append("ts <= ?")
        args.append(filters.end_ts)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT ts, component, level, module, message, category, correlation_id, stack, performance_ms, extra FROM logs{where} ORDER BY ts DESC LIMIT ?"
    args.append(limit)

    rows: List[LogEntry] = []
    with sqlite3.connect(db_path) as conn:
        for r in conn.execute(sql, args):
            extra = json.loads(r[9]) if r[9] else {}
            rows.append(
                LogEntry(
                    timestamp=r[0],
                    component=r[1],
                    level=r[2],
                    module=r[3],
                    message=r[4],
                    category=r[5],
                    correlation_id=r[6],
                    stack=r[7],
                    performance_ms=r[8],
                    extra=extra,
                )
            )
    return rows


def export_logs(db_path: Path, filters: QueryFilters, fmt: str = "json", limit: int = 500) -> bytes:
    data = query_logs(db_path, filters, limit=limit)
    if fmt == "json":
        return __import__("json").dumps([d.model_dump() for d in data], ensure_ascii=False).encode("utf-8")
    elif fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["timestamp", "component", "level", "module", "message", "category", "correlation_id", "stack", "performance_ms"])
        for e in data:
            w.writerow([e.timestamp, e.component, e.level, e.module, e.message, e.category or "", e.correlation_id or "", (e.stack or "").replace("\n", "\\n"), e.performance_ms or ""])
        return buf.getvalue().encode("utf-8")
    else:
        raise ValueError("Unsupported export format")

