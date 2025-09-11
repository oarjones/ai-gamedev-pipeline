---
title: API del Dashboard (REST)
---

# API del Dashboard

Base: `/api/v1`

## Pipeline
- `POST /pipeline/start` — `{ projectId, agentType? }` valida config, arranca procesos base, corre self-test y arranca el agente por defecto. Respuesta: `{ ok, steps[], health, selftest }`.
- `POST /pipeline/cancel` — cancela y detiene procesos. `{ cancelled: true }`.

## System
- `POST /system/start` — `{ projectId? }` arranca Unity → Unity Bridge → Blender → Blender Bridge. `{ ok, statuses[] }`.
- `POST /system/stop` — detiene procesos gestionados. `{ ok }`.
- `GET /system/status` — `[{ name, pid, running, lastStdout, lastStderr, lastError, startedAt }]`.

## Health
- `GET /health` — comprueba Unity/Bridges/Adapter (TCP/HTTP/WS). `{ ok, components: [{ name, running, endpoint_ok, detail }] }`.
- `POST /health/selftest` — `{ projectId? }` usa solo el agente (shim `ping` determinista). `{ passed, steps: [...] }`.

## Config
- `GET /config` — config central (enmascara secrets).
- `POST /config` — actualiza/valida config y persiste en `config/settings.yaml`.

## Projects
- `GET /projects` — lista
- `GET /projects/{id}` — detalle
- `POST /projects` — crea (body CreateProject)
- `PATCH /projects/{id}/select` — activa proyecto (detiene runner anterior y arranca nuevo)
- `GET /projects/active/current` — proyecto activo

## Project Manifest / Plan
- `GET /projects/{id}/manifest` — obtiene `project_manifest.yaml`
- `POST /projects/{id}/manifest` — guarda manifest (valida campos clave)
- `POST /projects/{id}/plan/propose` — construye prompt inicial y lo envía al agente (respuesta propuesta en Chat)
- `POST /projects/{id}/plan` — guarda `plan_of_record.yaml` (acepta JSON plan y lo serializa a YAML)

## Agent
- `POST /agent/start` — `{ projectId, provider: 'gemini_cli' }`
- `POST /agent/stop` — detiene runner y, si corresponde, el MCP Adapter propio del runner
- `GET /agent/status` — `{ running, pid?, cwd?, agentType?, provider?, lastError?, adapter: { running, pid?, startedAt? } }`
- `POST /agent/send` — `{ text }` (salida vía WS)

## Chat
- `POST /chat/send?projectId` — `{ text }` (persistencia + stream)
- `GET /chat/history?projectId&limit` — historial

## Sessions
- `GET /sessions?projectId&limit` — lista de sesiones del proyecto.
- `GET /sessions/{id}?recent=10` — detalle (resumen, últimos mensajes, artifacts).
- `POST /sessions/{id}/resume` — inicia Runner usando el Context Pack de esa sesión.

## Tasks
- `GET /tasks?projectId` — lista tareas persistidas.
- `POST /tasks/import?projectId` — importa desde `plan_of_record.yaml`.
- `POST /tasks/{id}/propose_steps` — agente sugiere sub-pasos (sin ejecutar).
- `POST /tasks/{id}/execute_tool` — ejecuta tool `{ tool, args, confirmed? }` y adjunta evidencia.
- `POST /tasks/{id}/verify` — verificación de aceptación (respuesta en Chat).
- `POST /tasks/{id}/complete` — marca como `done` si el usuario confirma aceptación.

## Tools
- `GET /tools` — metadatos (schemas JSON)
- `POST /actions/execute?projectId` — `{ toolId, input }` (valida y delega al orquestador)

## Context
- `GET /context/state?projectId` — `{ scene, screenshot }` (urls, etags)
- `GET /context/screenshot?projectId` — metadata screenshot
- `GET /context/screenshot/file?projectId` — PNG
- `GET /context/scene/file?projectId` — JSON
- `POST /context/screenshot?projectId` — solicita captura y actualiza archivos

Ver también: `docs/api/websocket_protocol.md` y `docs/api/events.md`.

