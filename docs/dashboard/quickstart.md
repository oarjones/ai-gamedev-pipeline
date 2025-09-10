---
title: Quickstart (Dashboard)
---

# Quickstart

Sigue estos pasos para levantar el Dashboard (Gateway + Webapp) y verificar tu entorno.

1) Requisitos
- Python 3.12+ en PATH
- Node.js 18+ (para el frontend)
- Unity y Blender instalados (si vas a usar los Bridges)

2) Crear venv e instalar dependencias (gateway)
- En Windows (PowerShell):
  - `cd gateway`
  - `python -m venv .venv`
  - `.venv\Scripts\activate`
  - `pip install -e .`

3) Configuración mínima
- Edita `config/settings.yaml` y revisa la sección `gateway.config`:
```yaml
gateway:
  config:
    executables:
      unityExecutablePath: "C:\\Program Files\\Unity\\Hub\\Editor\\<version>\\Editor\\Unity.exe"
      blenderExecutablePath: "C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe"
      unityProjectRoot: "projects"
    bridges:
      unityBridgePort: 8001
      blenderBridgePort: 8002
    integrations:
      openai: { apiKey: "****", defaultModel: "gpt-4o" }
      anthropic: { apiKey: "****", defaultModel: "claude-3-haiku-20240307" }
      gemini: { apiKey: "****", defaultModel: "gemini-1.5-pro" }
    projects: { root: "projects" }
```
- Las API keys se enmascaran en respuestas. No uses secretos reales en repos públicos.

4) Arranque rápido
- Usa los scripts: `scripts/dev_up.bat` (Windows)
  - Abre dos ventanas: backend FastAPI (Uvicorn) y frontend Vite.
  - Backend en `http://127.0.0.1:8000`, Frontend en `http://127.0.0.1:5173`.

5) Verifica salud
- `GET http://127.0.0.1:8000/api/v1/health` debe devolver `ok: true` si los Bridges están activos.
- En el Dashboard, pulsa “Run Self-Test” para un diagnóstico guiado.

6) Primer uso
- Crea o selecciona un proyecto (panel izquierdo).
- En “Agent”, elige `Gemini` (MCP) o `OpenAI/Claude` y pulsa `Re/Start`.
- Envía un mensaje en el chat. Observa eventos en el Timeline.

Troubleshooting rápido
- Puertos ocupados: cambia `unityBridgePort/blenderBridgePort` en `settings.yaml` y reinicia.
- Ejecutables no encontrados: corrige `unityExecutablePath/blenderExecutablePath`.
- API keys faltantes: actualiza `Dashboard → Settings → Agents` y guarda.
- `pip install` falla: usa la página `Dependencies` para (re)crear venv e instalar requirements.

Notas
- Más detalles en `docs/dashboard/api.md`, `docs/dashboard/config.md` y `docs/troubleshooting/*`.
---
