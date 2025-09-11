---
title: Quickstart (Windows)
---

# Quickstart (Windows 10/11 Pro)

Requisitos:
- Python 3.11+, Node 18+, Git
- Unity Editor y Blender instalados

## 1) Configuración básica

Edita `config/settings.yaml`:

```yaml
executables:
  unityExecutablePath: "C:/Program Files/Unity/Hub/Editor/....../Editor/Unity.exe"
  blenderExecutablePath: "C:/Program Files/Blender Foundation/Blender 4.1/blender.exe"
  unityProjectRoot: "projects"
bridges:
  unityBridgePort: 8001
  blenderBridgePort: 8002
providers:
  geminiCli: { command: "gemini" }
```

## 2) Levantar entorno

En la raíz del repo:

```bat
scripts\dev_up.bat
```

Esto instala dependencias mínimas, prepara la base y arranca el Dashboard.

## 3) Self-Test

En la UI (Dashboard → Self-Test) ejecuta “Run Self-Test”.
- Verifica puentes (Unity/Blender)
- Inicia el agente Gemini CLI
- Ejecuta shim `ping` y espera `{ "mcp_ping": "pong" }`

## 4) Primer proyecto

1. Crea proyecto (panel izquierdo)
2. Ve a “Wizard” y completa el `project_manifest.yaml`
3. “Generate Plan (via Agent)” — revisa propuesta en Chat
4. Pega JSON en “Plan of Record” y guarda
5. Ve a “Tasks” → “Import from Plan”, selecciona y ejecuta tareas con confirmación cuando aplique

Siguientes pasos: consulta `docs/guides`.

