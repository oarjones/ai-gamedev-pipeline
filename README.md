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

Quickstart
----------
- Guía paso a paso: `docs/dashboard/quickstart.md`
- Arranque rápido en Windows: `scripts/dev_up.bat` (abre backend y webapp). Para parar: `scripts/dev_down.bat`.

Documentación (MkDocs)
----------------------
- Índice: `docs/index.md`.
- API: `docs/api/` (actualiza con `python scripts/generate_docs.py`).
- Arquitectura: `docs/architecture/`.
- Guía de usuario: `docs/user_guide/`.
- Desarrollo: `docs/developer/`.
- Problemas comunes: `docs/troubleshooting/`.

Dashboard (Gateway)
-------------------
- Arquitectura: `docs/dashboard/architecture.md`
- Eventos (Envelope/Rooms): `docs/dashboard/events.md`
- API (system, config, deps, agent, health, projects, chat, tools, context): `docs/dashboard/api.md`
- Configuración (project.json/env): `docs/dashboard/config.md`

Contribución
------------
Por favor, lee `CONTRIBUTING.md`. Mantén docstrings actualizados y ejecuta el generador de docs antes de subir cambios.

Auditoría y Limpieza (DX)
-------------------------
- Inventario y auditoría: ejecuta `python tools/cleanup/inventory.py` y `python tools/cleanup/audit_runner.py` (salida en `reports/`).
- Verificación post-limpieza: `python tools/cleanup/verify_cleanup.py` (guardar logs en `reports/cleanup_runlogs/`).
- Informe: consulta `reports/cleanup_audit.md` y `reports/cleanup_audit.json`.

Bootstrapper de Juegos (nuevo)
------------------------------
- Ubicación: `mcp_unity_bridge/src/bootstrapper/`
- Clases clave: `GameBootstrapper`, `SpecificationParser`, `UnityHubCLI`, `ProjectStructureGenerator`.
- Uso básico (Python):
  - `from mcp_unity_bridge.src.bootstrapper.game_bootstrapper import GameBootstrapper`
  - `bootstrapper = GameBootstrapper()`
  - `await bootstrapper.create_game("Crea un juego 3D tipo plataforma para PC")`
- El wrapper de Unity Hub intenta usar `UNITY_HUB_CLI` si está disponible; si no, simula la creación del proyecto para flujos offline.
