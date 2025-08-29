from __future__ import annotations

from typing import Any, Iterable, Optional


class ParamError(ValueError):
    pass


def get_str(params: dict, key: str, default: Optional[str] = None, required: bool = False) -> str:
    if key not in params:
        if required:
            raise ParamError(f"missing param: {key}")
        return default  # type: ignore[return-value]
    v = params[key]
    if not isinstance(v, str):
        raise ParamError(f"param '{key}' must be str")
    return v


def get_float(
    params: dict,
    key: str,
    default: Optional[float] = None,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if key not in params:
        if default is None:
            raise ParamError(f"missing param: {key}")
        v = float(default)
    else:
        try:
            v = float(params[key])
        except Exception as e:
            raise ParamError(f"param '{key}' must be float: {e}")
    if positive and not (v > 0):
        raise ParamError(f"param '{key}' must be > 0")
    if nonnegative and not (v >= 0):
        raise ParamError(f"param '{key}' must be >= 0")
    return v


def get_int(params: dict, key: str, default: Optional[int] = None, *, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    if key not in params:
        if default is None:
            raise ParamError(f"missing param: {key}")
        v = int(default)
    else:
        try:
            v = int(params[key])
        except Exception as e:
            raise ParamError(f"param '{key}' must be int: {e}")
    if min_value is not None and v < min_value:
        raise ParamError(f"param '{key}' must be >= {min_value}")
    if max_value is not None and v > max_value:
        raise ParamError(f"param '{key}' must be <= {max_value}")
    return v


def get_list_int(params: dict, key: str, required: bool = True) -> list[int]:
    if key not in params:
        if required:
            raise ParamError(f"missing param: {key}")
        return []
    v = params[key]
    if not isinstance(v, Iterable) or isinstance(v, (str, bytes)):
        raise ParamError(f"param '{key}' must be list[int]")
    try:
        return [int(x) for x in v]  # type: ignore[arg-type]
    except Exception as e:
        raise ParamError(f"param '{key}' must be list[int]: {e}")

