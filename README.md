AI GameDev Pipeline — Documentación Unificada
============================================

AI GameDev Pipeline conecta Unity, Blender y un puente MCP en Python para habilitar flujos de trabajo asistidos por IA en desarrollo de videojuegos. Esta README ofrece una visión general, características y un arranque rápido. La documentación completa está publicada bajo `docs/` (MkDocs) y organizada por instalación, arquitectura, guía de usuario, API y desarrollo.

Características
---------------
- Integración Unity ↔ MCP por WebSocket y comandos de Editor.
- Addon de Blender con comandos de modelado y automatización.
- Bridge en Python con servidor, validación y logging centralizado.
- Documentación autogenerada desde docstrings (Python) y comentarios XML (C#).
- Diagramas de arquitectura Mermaid y soporte de exportación a PDF.

Quick Start
-----------
1) Requisitos y setup: ver `docs/installation/requirements.md`.
2) MCP Bridge: crea entorno, instala requisitos y ejecuta `mcp_unity_server/main.py` (ver `docs/installation/mcp_bridge_setup.md`).
3) Unity: abre `unity_project/` y verifica conexión (ver `docs/installation/unity_setup.md`).
4) Blender: instala y activa `mcp_blender_addon` (ver `docs/installation/blender_setup.md`).
5) Prueba un comando básico desde Unity o Blender (ver `docs/user_guide/basic_usage.md`).

Documentación (MkDocs)
----------------------
- Índice: `docs/index.md`.
- API: `docs/api/` (actualiza con `python scripts/generate_docs.py`).
- Arquitectura: `docs/architecture/`.
- Guía de usuario: `docs/user_guide/`.
- Desarrollo: `docs/developer/`.
- Problemas comunes: `docs/troubleshooting/`.

Contribución
------------
Por favor, lee `CONTRIBUTING.md`. Mantén docstrings actualizados y ejecuta el generador de docs antes de subir cambios.
