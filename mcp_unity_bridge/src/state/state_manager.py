from __future__ import annotations

import base64
import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .checkpoint import Checkpoint
from .storage import IStateStorage, SQLiteStorage


class _LRUCache:
    def __init__(self, capacity: int = 16):
        self.capacity = capacity
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._data:
                return None
            value = self._data.pop(key)
            self._data[key] = value
            return value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._data:
                self._data.pop(key)
            elif len(self._data) >= self.capacity:
                self._data.popitem(last=False)
            self._data[key] = value


class StateManager:
    def __init__(self, project_path: str, max_checkpoints: int = 50, storage: Optional[IStateStorage] = None):
        self.project_path = Path(project_path)
        self.state_dir = self.project_path / ".state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.state_dir / "state.db"
        self.storage = storage or SQLiteStorage(str(db_path))
        self.storage.init()
        self.max_checkpoints = max_checkpoints
        self._lock = threading.Lock()
        self._cache = _LRUCache(capacity=16)
        self._head: Optional[str] = None

    def create_checkpoint(self, action_type: str, data: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
        with self._lock:
            parent = self._head
            # Optional shallow-delta for dict payloads
            delta_meta: Optional[Dict[str, Any]] = None
            if parent is not None:
                try:
                    prev = self._load_checkpoint_data(parent)
                    if isinstance(prev, dict) and isinstance(data, dict):
                        diff = self._dict_diff(prev, data)
                        # If diff smaller than full by 30%+, store as delta
                        import json as _json
                        full_size = len(_json.dumps(data))
                        diff_size = len(_json.dumps(diff))
                        if diff_size < full_size * 0.7:
                            data_to_store = {"$delta": True, "base": parent, "ops": diff}
                            delta_meta = {"delta": True, "base": parent}
                            cp, blob = Checkpoint.create(action_type, data_to_store, parent_id=parent, compress=True)
                        else:
                            cp, blob = Checkpoint.create(action_type, data, parent_id=parent, compress=True)
                    else:
                        cp, blob = Checkpoint.create(action_type, data, parent_id=parent, compress=True)
                except Exception:
                    cp, blob = Checkpoint.create(action_type, data, parent_id=parent, compress=True)
            else:
                cp, blob = Checkpoint.create(action_type, data, parent_id=parent, compress=True)
            row = {
                "id": cp.id,
                "timestamp": cp.timestamp,
                "action_type": cp.action,
                "data": blob,
                "metadata": {**(metadata or {}), **(delta_meta or {})},
                "parent_id": cp.parent_id,
                "hash": cp.hash,
                "size_bytes": cp.size_bytes,
                "compressed": cp.compressed,
                "fmt": cp.fmt,
            }
            self.storage.insert_checkpoint(row)
            self._head = cp.id
            self._cache.put(cp.id, data)
            self.prune_old_checkpoints(self.max_checkpoints)
            return cp.id

    def rollback(self, steps: int = 1) -> Optional[str]:
        with self._lock:
            if not self._head:
                return None
            cur_meta = self.storage.get_checkpoint_meta(self._head)
            for _ in range(steps):
                if not cur_meta or not cur_meta.get("parent_id"):
                    break
                cur_meta = self.storage.get_checkpoint_meta(cur_meta["parent_id"])  # type: ignore
            if cur_meta:
                self._head = cur_meta["id"]
                return self._head
            return None

    def rollforward(self, steps: int = 1) -> Optional[str]:
        # Rollforward requires branch tracking; for simplicity we no-op here
        return self._head

    def get_history(self, limit: int = 10, filter: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.get_history(limit=limit, action_filter=filter)

    def prune_old_checkpoints(self, keep_last: int = 20) -> None:
        hist = self.storage.get_history(limit=10_000)
        if len(hist) <= keep_last:
            return
        to_delete = hist[keep_last:]
        for h in to_delete:
            self.storage.delete_checkpoint(h["id"])  # type: ignore

    def export_state(self, format: str = "json") -> Path:
        out = self.state_dir / ("export.json" if format == "json" else "export.bin")
        items: List[Dict[str, Any]] = []
        hist = list(reversed(self.storage.get_history(limit=10_000)))
        for meta in hist:
            raw = self.storage.get_checkpoint_data(meta["id"])  # type: ignore
            if not raw:
                continue
            blob, compressed, fmt = raw
            items.append(
                {
                    "meta": meta,
                    "compressed": compressed,
                    "fmt": fmt,
                    "data": base64.b64encode(blob).decode("ascii"),
                }
            )
        if format == "json":
            out.write_text(json.dumps(items), encoding="utf-8")
        else:
            out.write_bytes(json.dumps(items, separators=(",", ":")).encode("utf-8"))
        return out

    def import_state(self, file_path: str) -> None:
        p = Path(file_path)
        items = json.loads(p.read_text(encoding="utf-8"))
        for it in items:
            meta = it["meta"]
            blob = base64.b64decode(it["data"]) if isinstance(it["data"], str) else bytes(it["data"])  # type: ignore
            row = {
                "id": meta["id"],
                "timestamp": meta["timestamp"],
                "action_type": meta["action_type"],
                "data": blob,
                "metadata": meta.get("metadata", {}),
                "parent_id": meta.get("parent_id"),
                "hash": meta.get("hash", ""),
                "size_bytes": meta.get("size_bytes", len(blob)),
                "compressed": meta.get("compressed", True),
                "fmt": meta.get("fmt", "json"),
            }
            self.storage.insert_checkpoint(row)
        hist = self.storage.get_history(limit=1)
        if hist:
            self._head = hist[0]["id"]

    def get_diff(self, checkpoint_a: str, checkpoint_b: str) -> Dict[str, Any]:
        da = self._load_checkpoint_data(checkpoint_a)
        db = self._load_checkpoint_data(checkpoint_b)
        if isinstance(da, dict) and isinstance(db, dict):
            diff = {
                "added": {k: db[k] for k in db.keys() - da.keys()},
                "removed": {k: da[k] for k in da.keys() - db.keys()},
                "changed": {k: {"from": da[k], "to": db[k]} for k in da.keys() & db.keys() if da[k] != db[k]},
            }
        else:
            diff = {
                "type": f"{type(da).__name__} vs {type(db).__name__}",
                "equal": da == db,
            }
        return diff

    def _load_checkpoint_data(self, cid: str) -> Any:
        cached = self._cache.get(cid)
        if cached is not None:
            return cached
        raw = self.storage.get_checkpoint_data(cid)
        if not raw:
            return None
        blob, compressed, fmt, expected_hash = raw
        from .checkpoint import Checkpoint as CP
        # Integrity check
        import hashlib
        h = hashlib.sha256(blob).hexdigest()
        if expected_hash and h != expected_hash:
            # Corrupt entry; attempt cleanup and abort
            self.storage.delete_checkpoint(cid)
            return None
        data = CP.decode_data(blob, compressed, fmt)
        # Delta reconstruction
        meta = self.storage.get_checkpoint_meta(cid) or {}
        if isinstance(data, dict) and data.get("$delta"):
            base_id = data.get("base") or meta.get("parent_id")
            base = self._load_checkpoint_data(base_id) if base_id else {}
            data = self._apply_diff(base if isinstance(base, dict) else {}, data.get("ops", {}))
        self._cache.put(cid, data)
        return data

    def _dict_diff(self, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "added": {k: b[k] for k in b.keys() - a.keys()},
            "removed": list(a.keys() - b.keys()),
            "changed": {k: b[k] for k in a.keys() & b.keys() if a[k] != b[k]},
        }

    def _apply_diff(self, base: Dict[str, Any], diff: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(base)
        for k in diff.get("removed", []):
            out.pop(k, None)
        for k, v in diff.get("added", {}).items():
            out[k] = v
        for k, v in diff.get("changed", {}).items():
            out[k] = v
        return out
