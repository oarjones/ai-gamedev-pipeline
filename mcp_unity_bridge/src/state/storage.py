from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class IStateStorage(ABC):
    @abstractmethod
    def init(self) -> None: ...

    @abstractmethod
    def insert_checkpoint(self, cp_row: Dict[str, Any]) -> None: ...

    @abstractmethod
    def get_checkpoint_meta(self, cid: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def get_checkpoint_data(self, cid: str) -> Optional[Tuple[bytes, bool, str]]: ...

    @abstractmethod
    def get_history(self, limit: int = 10, action_filter: Optional[str] = None) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def delete_checkpoint(self, cid: str) -> None: ...

    @abstractmethod
    def backup_if_needed(self) -> None: ...

    @abstractmethod
    def vacuum_if_needed(self) -> None: ...


class SQLiteStorage(IStateStorage):
    def __init__(self, db_path: str, backup_interval: int = 10):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._backup_interval = backup_interval
        self._insert_count = 0

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init(self) -> None:
        with self._lock, self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    timestamp INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    data BLOB,
                    metadata TEXT,
                    parent_id TEXT,
                    hash TEXT NOT NULL,
                    size_bytes INTEGER,
                    compressed BOOLEAN,
                    fmt TEXT
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_cp_ts ON checkpoints(timestamp);"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_cp_action ON checkpoints(action_type);"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_cp_parent ON checkpoints(parent_id);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS state_branches (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at INTEGER,
                    head_checkpoint TEXT,
                    description TEXT
                );
                """
            )

    def insert_checkpoint(self, cp_row: Dict[str, Any]) -> None:
        with self._lock, self._connect() as con:
            con.execute(
                """
                INSERT INTO checkpoints (id, timestamp, action_type, data, metadata, parent_id, hash, size_bytes, compressed, fmt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cp_row["id"],
                    cp_row["timestamp"],
                    cp_row["action_type"],
                    cp_row.get("data"),
                    json.dumps(cp_row.get("metadata", {})),
                    cp_row.get("parent_id"),
                    cp_row["hash"],
                    cp_row.get("size_bytes", 0),
                    1 if cp_row.get("compressed") else 0,
                    cp_row.get("fmt", "json"),
                ),
            )
            self._insert_count += 1
        self.backup_if_needed()
        self.vacuum_if_needed()

    def get_checkpoint_meta(self, cid: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as con:
            cur = con.execute(
                "SELECT id, timestamp, action_type, metadata, parent_id, hash, size_bytes, compressed, fmt FROM checkpoints WHERE id = ?",
                (cid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            meta = {
                "id": row[0],
                "timestamp": row[1],
                "action_type": row[2],
                "metadata": json.loads(row[3]) if row[3] else {},
                "parent_id": row[4],
                "hash": row[5],
                "size_bytes": row[6],
                "compressed": bool(row[7]),
                "fmt": row[8],
            }
            return meta

    def get_checkpoint_data(self, cid: str) -> Optional[Tuple[bytes, bool, str, str]]:
        with self._lock, self._connect() as con:
            cur = con.execute(
                "SELECT data, compressed, fmt, hash FROM checkpoints WHERE id = ?",
                (cid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return row[0], bool(row[1]), row[2], row[3]

    def get_history(self, limit: int = 10, action_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as con:
            if action_filter:
                cur = con.execute(
                    "SELECT id, timestamp, action_type, metadata, parent_id, size_bytes FROM checkpoints WHERE action_type = ? ORDER BY timestamp DESC LIMIT ?",
                    (action_filter, limit),
                )
            else:
                cur = con.execute(
                    "SELECT id, timestamp, action_type, metadata, parent_id, size_bytes FROM checkpoints ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            out: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                out.append(
                    {
                        "id": row[0],
                        "timestamp": row[1],
                        "action_type": row[2],
                        "metadata": json.loads(row[3]) if row[3] else {},
                        "parent_id": row[4],
                        "size_bytes": row[5],
                    }
                )
            return out

    def delete_checkpoint(self, cid: str) -> None:
        with self._lock, self._connect() as con:
            con.execute("DELETE FROM checkpoints WHERE id = ?", (cid,))

    def backup_if_needed(self) -> None:
        if self._insert_count % self._backup_interval != 0:
            return
        backups = self.db_path.parent / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        shutil.copy2(self.db_path, backups / f"state_{ts}.db")

    def vacuum_if_needed(self) -> None:
        try:
            size = self.db_path.stat().st_size
        except FileNotFoundError:
            return
        if size < 100 * 1024 * 1024:
            return
        with self._lock, self._connect() as con:
            con.execute("VACUUM;")
