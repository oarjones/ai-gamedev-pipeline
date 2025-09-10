---
title: API del Dashboard (REST)
---

# API del Dashboard

Base: `/api/v1`

## Pipeline
- `POST /pipeline/start` — `{ projectId, agentType? }` valida config, asegura venv/deps mínimas, arranca procesos, corre self-test y arranca el agente por defecto. Respuesta: `{ ok, steps[], health, selftest }`.
- `POST /pipeline/cancel` — cancela la secuencia y detiene procesos. Respuesta: `{ cancelled: true }`.

## Health
- `GET /health` — comprueba Unity, Bridges y MCP Adapter (TCP/HTTP/WS). Respuesta: `{ ok, components: [{ name, running, endpoint_ok, detail }] }`.
- `POST /health/selftest` — `{ projectId? }` intenta arrancar la secuencia, verifica endpoints y envía `ping` al agente (Gemini). Respuesta: `{ passed, steps: [{ name, ok, detail? }] }`.

## System
- `POST /system/start` — body: `{ projectId? }`; arranca Unity → Unity Bridge → Blender → Blender Bridge → MCP Adapter. Respuesta: `{ ok, statuses[] }`.
- `POST /system/stop` — body opcional, detiene todos los procesos gestionados. Respuesta: `{ ok }`.
- `GET /system/status` — estados por proceso: `[{ name, pid, running, lastStdout, lastError, startedAt }]`.

## Config
- `GET /config` — retorna configuración centralizada (claves enmascaradas).
- `POST /config` — actualiza y valida configuración; persiste en `config/settings.yaml` (backup `.bak`).

## Dependencies
- `POST /venv/create` — `{ path, projectId? }` crea un entorno virtual en la ruta dada (relativa al repo). Respuestas: 201/409/400.
- `POST /deps/install` — `{ venvPath, requirementsPath? , packages?, projectId? }` instala dependencias desde `requirements.txt` o lista de paquetes permitidos; emite logs por WS (`type=log`, `payload.source='deps'`).
- `POST /deps/check` — `{ venvPath, packages }` devuelve `[{ name, installed, version? }]`.

## Projects
- `GET /projects` — lista
- `GET /projects/{id}` — detalle
- `POST /projects` — crea (body CreateProject)
- `PATCH /projects/{id}/select` — activa proyecto (detiene runner anterior y arranca nuevo; emite `type=project`)
- `GET /projects/active/current` — activo

## Agent
- `POST /agent/start` — body: `{ projectId, agentType: 'gemini'|'openai'|'claude' }`
- `POST /agent/stop` — detiene runner
- `GET /agent/status` — `{ running, pid?, cwd?, agentType?, lastError? }`
- `POST /agent/send` — `{ text }` (stream por WS)

## Chat
- `POST /chat/send?projectId` — `{ text }` (persistencia + stream)
- `GET /chat/history?projectId&limit` — historial

## Timeline
- `GET /timeline?projectId&limit` — eventos
- `POST /timeline/{event_id}/revert` — acciones compensatorias

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
