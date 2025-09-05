# Instalación — Guía paso a paso

Esta guía cubre requisitos, instalación y verificación de Unity, Blender y el MCP Bridge. Consulta también capturas en `Screenshot/`.

## 1) Requisitos

- Windows 10/11, macOS 12+ o Linux (Bridge/Blender)
- Unity 2022.3 LTS+
- Blender 3.6+
- Python 3.10–3.12

## 2) MCP Bridge

```bash
python -m venv .venv
.venv\\Scripts\\activate  # Windows
pip install -r mcp_unity_bridge/requirements.txt
pip install -r mcp_unity_bridge/requirements-agent.txt  # opcional
python mcp_unity_bridge/src/mcp_unity_server/main.py
```

## 3) Unity

1. Abre `unity_project/` con Unity Hub (2022.3 LTS).
2. Espera importación inicial y verifica scripts en `Assets/Editor/MCP`.
3. Ajusta host/puerto si difieren del Bridge.

## 4) Blender

1. `Edit > Preferences > Add-ons > Install...` y selecciona `mcp_blender_addon/`.
2. Activa el addon y reinicia si se solicita.

## 5) Verificación

- Unity debe conectar al Bridge (mensajes en consola).
- Desde Blender, ejecuta un comando de prueba (crear cubo) y verifica la respuesta.

## Screenshots

- Ver `Screenshot/` para pasos con imágenes: instalación de addon, consola de Unity, Bridge en ejecución.

