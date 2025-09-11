from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover - fuera de Blender
    bpy = None  # type: ignore

from ..server.logging import get_logger
from ..server.registry import command, tool
from ..server.context import SessionContext


log = get_logger(__name__)


def _read_file_text(path: str) -> str:
    """Lee el contenido de un archivo de texto como UTF-8.

    Nota: No se realizan comprobaciones de seguridad aquí; se añadirán más adelante.
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _build_exec_globals(ctx: SessionContext, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Construye un espacio de nombres global para `exec`.

    - Expone `bpy` (si disponible) y `ctx` para que el script pueda interactuar
      con el contexto y la API de Blender.
    - Usa `__name__ = "__main__"` para comportamientos esperados de script.
    """
    g: Dict[str, Any] = {
        "__name__": "__main__",
        "bpy": bpy,
        "ctx": ctx,
    }
    if extra:
        g.update(extra)
    return g


@command("helpers.exec_python")
@tool
def exec_python(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta código Python dentro del entorno de Python de Blender.

    Uso pensado para que el agente IA pueda generar y ejecutar scripts
    rápidamente. De momento NO se añaden comprobaciones de seguridad
    (p. ej. sandboxing o validaciones de rutas). Estas se implementarán más adelante.

    Parámetros:
      - code: string opcional con el código Python a ejecutar.
      - path: string opcional con la ruta a un archivo .py a ejecutar.
      - return_variable: string opcional; si se proporciona, se devolverá el valor
        de la variable global con ese nombre tras la ejecución (si existe).
      - globals: dict opcional; variables adicionales a inyectar en el espacio global
        antes de ejecutar el script (útil para pasar datos al script).

    Reglas:
      - Debe proporcionarse exactamente uno de `code` o `path`.
      - La ejecución se realiza con `exec` en un espacio de nombres aislado que
        expone `bpy` y `ctx` por conveniencia.

    Devuelve (result):
      {
        "mode": "code" | "path",
        "filename": str,              # "<inline>" o la ruta del script
        "executed": bool,             # True si no hubo excepciones
        "return_value": Any | null,   # Valor de `return_variable` si existe
        "defined_names": list[str],   # Nombres globales definidos por el script
      }
    """
    if bpy is None:
        # Mantenemos consistencia con otras herramientas que requieren Blender
        raise RuntimeError("Blender API not available")

    code_param = params.get("code")
    path_param = params.get("path")
    ret_var = params.get("return_variable")
    extra_globals = params.get("globals") or {}

    # Validaciones básicas de tipos
    has_code = isinstance(code_param, str) and len(code_param) > 0
    has_path = isinstance(path_param, str) and len(path_param) > 0
    if has_code == has_path:
        # Ambos o ninguno -> error para evitar ambigüedad
        raise ValueError("debe especificarse exactamente uno de 'code' o 'path'")
    if ret_var is not None and not isinstance(ret_var, str):
        raise ValueError("return_variable debe ser un string si se proporciona")
    if extra_globals is not None and not isinstance(extra_globals, dict):
        raise ValueError("globals debe ser un diccionario si se proporciona")

    # Preparar código y metadatos
    if has_code:
        code_text = code_param  # type: ignore[assignment]
        filename = "<inline>"
        mode = "code"
    else:
        filename = str(path_param)
        code_text = _read_file_text(filename)
        mode = "path"

    # Construir espacio global para la ejecución
    g = _build_exec_globals(ctx, extra=extra_globals)

    log.info("helpers.exec_python mode=%s file=%s bytes=%d", mode, filename, len(code_text))

    # Ejecutar el script; cualquier excepción será capturada por @tool
    exec(compile(code_text, filename, "exec"), g, g)

    # Extraer valor de retorno opcional
    rv = None
    if isinstance(ret_var, str) and ret_var:
        rv = g.get(ret_var)

    # Nombres definidos (excluyendo builtins típicos)
    defined = sorted([
        k for k in g.keys()
        if k not in {"__name__", "__builtins__", "bpy", "ctx"}
    ])

    return {
        "mode": mode,
        "filename": filename,
        "executed": True,
        "return_value": rv,
        "defined_names": defined,
    }


# Alias opcional bajo el sub-nombre helpers.python.exec para mayor ergonomía
@command("helpers.python.exec")
@tool
def exec_python_alias(ctx: SessionContext, params: Dict[str, Any]) -> Dict[str, Any]:
    """Alias de `helpers.exec_python` para permitir la invocación bajo otro namespace."""
    return exec_python(ctx, params)

