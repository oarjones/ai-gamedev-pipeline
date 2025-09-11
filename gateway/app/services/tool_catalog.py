from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ADAPTER_PATH = Path("mcp_unity_bridge") / "mcp_adapter.py"
CACHE_PATH = Path("gateway") / ".cache" / "tool_catalog.json"


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    examples: List[str]
    safety: List[str]


def _file_hash(p: Path) -> str:
    data = p.read_bytes()
    return hashlib.sha1(data).hexdigest()


def _annotation_to_schema(ann: Optional[ast.AST]) -> Dict[str, Any]:
    if ann is None:
        return {"type": ["string", "number", "boolean", "object", "array", "null"]}
    try:
        if isinstance(ann, ast.Name):
            n = ann.id
        elif isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
            n = ann.value.id
        else:
            n = None
    except Exception:
        n = None
    mapping = {
        "str": {"type": "string"},
        "int": {"type": "integer"},
        "float": {"type": "number"},
        "bool": {"type": "boolean"},
        "dict": {"type": "object"},
        "list": {"type": "array"},
        "Any": {"type": ["string", "number", "boolean", "object", "array", "null"]},
        "Optional": {"type": ["string", "number", "boolean", "object", "array", "null"]},
    }
    return mapping.get(n or "", {"type": ["string", "number", "boolean", "object", "array", "null"]})


def _extract_examples(doc: Optional[str]) -> List[str]:
    if not doc:
        return []
    lines = [l.strip() for l in doc.splitlines()]
    out: List[str] = []
    capture = False
    buf: List[str] = []
    for l in lines:
        if l.lower().startswith("ejemplo") or l.lower().startswith("example"):
            capture = True
            # May contain the example after colon
            parts = l.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                out.append(parts[1].strip())
            continue
        if capture:
            if not l:
                if buf:
                    out.append(" ".join(buf))
                    buf = []
                capture = False
            else:
                buf.append(l)
    if buf:
        out.append(" ".join(buf))
    return out[:3]


def _func_to_tool(node: ast.FunctionDef) -> ToolSpec:
    # Name and docstring
    name = node.name
    doc = ast.get_docstring(node) or ""
    desc = doc.strip().splitlines()[0] if doc else name
    # Params schema
    props: Dict[str, Any] = {}
    required: List[str] = []
    for a in node.args.args:
        if a.arg == "self":
            continue
        ann = getattr(a, "annotation", None)
        props[a.arg] = _annotation_to_schema(ann)
    # Defaults handling (set required for non-defaults)
    total = len(node.args.args)
    defaults = node.args.defaults or []
    non_default_count = total - len(defaults)
    for i, a in enumerate([arg.arg for arg in node.args.args]):
        if a == "self":
            continue
        if i < non_default_count:
            required.append(a)
    params_schema = {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }
    examples = _extract_examples(doc)
    return ToolSpec(name=name, description=desc, parameters=params_schema, examples=examples, safety=[])


def _has_mcp_tool_decorator(node: ast.FunctionDef) -> bool:
    for d in node.decorator_list:
        # Matches @mcp.tool() or @mcp.tool
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute):
            if d.func.attr == "tool":
                return True
        if isinstance(d, ast.Attribute) and d.attr == "tool":
            return True
    return False


def _parse_adapter_tools(source: str) -> List[ToolSpec]:
    tree = ast.parse(source)
    tools: List[ToolSpec] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and _has_mcp_tool_decorator(node):
            try:
                tools.append(_func_to_tool(node))
            except Exception:
                continue
    return tools


def build_catalog() -> Dict[str, Any]:
    if not ADAPTER_PATH.exists():
        raise FileNotFoundError(f"Adapter not found: {ADAPTER_PATH}")
    src = ADAPTER_PATH.read_text(encoding="utf-8")
    h = _file_hash(ADAPTER_PATH)
    tools = _parse_adapter_tools(src)
    # Optional JSONSchema validation
    try:
        import jsonschema  # type: ignore
        for t in tools:
            jsonschema.Draft202012Validator.check_schema(t.parameters)  # type: ignore
    except Exception:
        pass
    prompt_list = _to_prompt_list(tools)
    fn_schema = _to_function_schema(tools)
    return {
        "version": h[:12],
        "hash": h,
        "count": len(tools),
        "promptList": prompt_list,
        "functionSchema": fn_schema,
    }


def _to_prompt_list(tools: List[ToolSpec]) -> str:
    lines: List[str] = []
    for t in tools:
        lines.append(f"- {t.name}: {t.description}")
        if t.examples:
            for ex in t.examples[:2]:
                lines.append(f"  e.g. {ex}")
    return "\n".join(lines)


def _to_function_schema(tools: List[ToolSpec]) -> List[Dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description, "parameters": t.parameters}
        for t in tools
    ]


def get_catalog_cached() -> Dict[str, Any]:
    try:
        if CACHE_PATH.exists():
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            cached_hash = data.get("hash")
            current_hash = _file_hash(ADAPTER_PATH)
            if cached_hash == current_hash:
                return data
    except Exception:
        pass
    # Rebuild and store
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cat = build_catalog()
    try:
        CACHE_PATH.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return cat

