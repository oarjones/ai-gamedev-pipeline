from __future__ import annotations

import hashlib
import json
import time
import zlib
from dataclasses import dataclass
from typing import Any, Optional, Tuple

try:
    import msgpack  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    msgpack = None


def _sha256(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _serialize(data: Any) -> Tuple[bytes, str]:
    if msgpack is not None:
        try:
            return msgpack.dumps(data, use_bin_type=True), "msgpack"
        except Exception:
            pass
    return json.dumps(data, separators=(",", ":")).encode("utf-8"), "json"


def _deserialize(data: bytes, fmt: str) -> Any:
    if fmt == "msgpack" and msgpack is not None:
        return msgpack.loads(data, raw=False)
    return json.loads(data.decode("utf-8"))


@dataclass(frozen=True)
class Checkpoint:
    id: str
    timestamp: int
    action: str
    parent_id: Optional[str]
    hash: str
    compressed: bool
    size_bytes: int
    fmt: str

    @staticmethod
    def create(action: str, data: Any, parent_id: Optional[str] = None, compress: bool = True) -> Tuple["Checkpoint", bytes]:
        ts = int(time.time() * 1000)
        payload, fmt = _serialize(data)
        if compress:
            cdata = zlib.compress(payload)
            compressed = True
        else:
            cdata = payload
            compressed = False
        h = _sha256(cdata)
        # id could be hash + timestamp for uniqueness
        cid = f"{ts:x}-{h[:16]}"
        cp = Checkpoint(
            id=cid,
            timestamp=ts,
            action=action,
            parent_id=parent_id,
            hash=h,
            compressed=compressed,
            size_bytes=len(cdata),
            fmt=fmt,
        )
        return cp, cdata

    @staticmethod
    def encode_data(data: Any, compress: bool = True) -> Tuple[bytes, str, bool, int]:
        payload, fmt = _serialize(data)
        if compress:
            cdata = zlib.compress(payload)
            return cdata, fmt, True, len(cdata)
        return payload, fmt, False, len(payload)

    @staticmethod
    def decode_data(raw: bytes, compressed: bool, fmt: str) -> Any:
        blob = zlib.decompress(raw) if compressed else raw
        return _deserialize(blob, fmt)

