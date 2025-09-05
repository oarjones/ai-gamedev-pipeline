#!/usr/bin/env python3
"""
Generador de documentación para AI GameDev Pipeline.

Funciones:
- Extrae docstrings de Python (ast) para módulos, clases y funciones.
- Parsea comentarios XML estilo C# (///) en scripts de Unity para obtener summary/params.
- Genera/actualiza referencias de API en docs/api/* reemplazando bloques AUTO.
- Actualiza una tabla de herramientas disponibles (mezcla Unity/Blender) en mcp_tools.md.
- Opcional: genera diagramas Mermaid básicos en arquitectura basados en inventario.

Uso:
  python scripts/generate_docs.py
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


@dataclass
class PyFunctionDoc:
    module: str
    name: str
    summary: str = ""
    doc: str = ""


@dataclass
class CsMemberDoc:
    file: Path
    class_name: str
    member_name: str
    summary: str = ""
    params: List[Tuple[str, str]] = field(default_factory=list)
    returns: Optional[str] = None


def _first_line(text: str) -> str:
    return (text or "").strip().splitlines()[0] if text else ""


def extract_python_functions(package_dir: Path) -> List[PyFunctionDoc]:
    results: List[PyFunctionDoc] = []
    for py in package_dir.rglob("*.py"):
        try:
            src = py.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        module_name = str(py.relative_to(package_dir).with_suffix("")).replace("\\", ".").replace("/", ".")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node) or ""
                if not doc:
                    continue
                results.append(
                    PyFunctionDoc(module=module_name, name=node.name, summary=_first_line(doc), doc=doc)
                )
    return results


CS_CLASS_RE = re.compile(r"\b(class)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)")
CS_METHOD_RE = re.compile(r"\b(public|internal|protected|private)\s+(static\s+)?[A-Za-z0-9_<>,\[\]]+\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")


def parse_csharp_xml_comments(cs_file: Path) -> List[CsMemberDoc]:
    docs: List[CsMemberDoc] = []
    try:
        lines = cs_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return docs

    current_xml: List[str] = []
    current_class: Optional[str] = None

    def parse_block(xml_lines: List[str], decl_line: str) -> Tuple[str, str, List[Tuple[str, str]], Optional[str]]:
        xml = "\n".join(xml_lines)
        # Extraer summary/param/returns de comentarios tipo /// <summary>...
        def extract(tag: str) -> List[str]:
            return re.findall(fr"<\s*{tag}[^>]*>(.*?)</\s*{tag}\s*>", xml, flags=re.I | re.S)

        summary = " ".join([re.sub(r"\s+", " ", s.strip()) for s in extract("summary")])
        params: List[Tuple[str, str]] = []
        for name, text in re.findall(r"<\s*param\s+name=\"(.*?)\"\s*>(.*?)</\s*param\s*>", xml, flags=re.I | re.S):
            params.append((name, re.sub(r"\s+", " ", text.strip())))
        returns_list = extract("returns")
        returns = re.sub(r"\s+", " ", returns_list[0].strip()) if returns_list else None

        # Nombre del miembro por la declaración detectada
        m_name = CS_METHOD_RE.search(decl_line)
        member_name = m_name.group("name") if m_name else "(miembro)"
        return summary, member_name, params, returns

    i = 0
    while i < len(lines):
        line = lines[i]
        csm = CS_CLASS_RE.search(line)
        if csm:
            current_class = csm.group("name")
        if line.strip().startswith("///"):
            # Acumular bloque XML consecutivo
            current_xml = [line.strip().lstrip("/").strip()]
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("///"):
                current_xml.append(lines[j].strip().lstrip("/").strip())
                j += 1
            # La siguiente línea no-XML debería ser la declaración
            decl = lines[j] if j < len(lines) else ""
            if current_class and decl.strip():
                summary, member_name, params, returns = parse_block(current_xml, decl)
                docs.append(CsMemberDoc(
                    file=cs_file, class_name=current_class, member_name=member_name,
                    summary=summary, params=params, returns=returns
                ))
            i = j
            continue
        i += 1
    return docs


def replace_auto_block(md_path: Path, marker: str, new_content: str) -> None:
    start = f"<!-- {marker} -->"
    end = f"<!-- {marker}:END -->"
    text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    if start in text and end in text:
        pre = text.split(start)[0]
        post = text.split(end)[-1]
        md_path.write_text(pre + start + "\n" + new_content.rstrip() + "\n" + end + post, encoding="utf-8")
    else:
        # Si no existen marcadores, añádelos al final
        with md_path.open("a", encoding="utf-8") as f:
            if text and not text.endswith("\n\n"):
                f.write("\n\n")
            f.write(f"\n{start}\n{new_content.rstrip()}\n{end}\n")


def generate_blender_commands() -> List[PyFunctionDoc]:
    base = ROOT / "mcp_blender_addon" / "commands"
    if not base.exists():
        return []
    funcs = extract_python_functions(base)
    # Tabla
    rows = ["| Módulo | Función | Resumen |", "|--------|---------|---------|"]
    for f in sorted(funcs, key=lambda x: (x.module, x.name)):
        rows.append(f"| {f.module} | {f.name} | {f.summary} |")
    table = "\n".join(rows)
    # Detalle
    details_parts = []
    for f in sorted(funcs, key=lambda x: (x.module, x.name)):
        details_parts.append(f"### {f.module}.{f.name}\n\n{f.doc}\n")
    details = "\n".join(details_parts) if details_parts else "*(no se detectaron funciones con docstring)*"
    replace_auto_block(DOCS / "api" / "blender_commands.md", "AUTO:BLENDER_COMMANDS", table + "\n\n" + details)
    return funcs


def generate_unity_commands() -> List[CsMemberDoc]:
    base = ROOT / "unity_project" / "Assets" / "Editor" / "MCP"
    members: List[CsMemberDoc] = []
    if base.exists():
        for cs in base.rglob("*.cs"):
            members.extend(parse_csharp_xml_comments(cs))
    # Construir Markdown
    if not members:
        content = "*(no se detectaron comentarios XML en comandos)*"
    else:
        lines = []
        current_class = None
        for m in sorted(members, key=lambda x: (x.class_name, x.member_name)):
            if m.class_name != current_class:
                current_class = m.class_name
                lines.append(f"\n## {current_class}\n")
            lines.append(f"### {m.member_name}\n\n{m.summary or '(sin summary)'}\n")
            if m.params:
                lines.append("**Parámetros:**")
                for p, desc in m.params:
                    lines.append(f"- `{p}`: {desc}")
            if m.returns:
                lines.append(f"**Devuelve:** {m.returns}")
        content = "\n".join(lines)
    replace_auto_block(DOCS / "api" / "unity_commands.md", "AUTO:UNITY_COMMANDS", content)
    return members


def generate_mcp_tools(blender_funcs: List[PyFunctionDoc], unity_members: List[CsMemberDoc]) -> None:
    md = DOCS / "api" / "mcp_tools.md"
    text = md.read_text(encoding="utf-8") if md.exists() else ""
    # Tabla simple combinada
    rows = ["| Nombre | Origen | Descripción |", "|-------|--------|-------------|"]
    for f in sorted(blender_funcs, key=lambda x: (x.module, x.name)):
        rows.append(f"| {f.module}.{f.name} | Blender | {f.summary} |")
    for m in sorted(unity_members, key=lambda x: (x.class_name, x.member_name)):
        rows.append(f"| {m.class_name}.{m.member_name} | Unity | {m.summary} |")
    table = "\n".join(rows) if len(rows) > 2 else "*(sin herramientas detectadas)*"
    # Insertar debajo del subtítulo Catálogo
    if "## Catálogo" in text:
        new = re.sub(r"\| .*?\|\n\|[-| ]+\|[\s\S]*?(\n\n|$)", table + "\n\n", text, count=1, flags=re.M)
        md.write_text(new, encoding="utf-8")
    else:
        md.write_text((text + "\n\n" + table).strip() + "\n", encoding="utf-8")


def generate_arch_mermaid_inventory() -> None:
    # Dibuja un diagrama en función de los directorios presentes
    have_unity = (ROOT / "unity_project").exists()
    have_blender = (ROOT / "mcp_blender_addon").exists()
    have_bridge = (ROOT / "mcp_unity_bridge").exists()
    mermaid = ["```mermaid", "flowchart LR"]
    if have_unity:
        mermaid.append("  U[Unity Editor]")
    if have_bridge:
        mermaid.append("  B{{MCP Bridge}}")
    if have_blender:
        mermaid.append("  L[Blender Addon]")
    if have_unity and have_bridge:
        mermaid.append("  U <-->|WS| B")
    if have_blender and have_bridge:
        mermaid.append("  L <-->|WS| B")
    mermaid.append("```")
    content = "\n".join(mermaid)
    # Append a bloque AUTO en overview
    replace_auto_block(DOCS / "architecture" / "overview.md", "AUTO:ARCH_INVENTORY", content)


def main() -> None:
    blender_funcs = generate_blender_commands()
    unity_members = generate_unity_commands()
    generate_mcp_tools(blender_funcs, unity_members)
    generate_arch_mermaid_inventory()
    print("Documentación generada/actualizada correctamente.")


if __name__ == "__main__":
    main()

