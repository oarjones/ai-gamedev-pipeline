---
title: API del Dashboard (REST)
---

# API del Dashboard

Base: `/api/v1`

## Projects
- `GET /projects` → lista
- `GET /projects/{id}` → detalle
- `POST /projects` → crea (body CreateProject)
- `PATCH /projects/{id}/select` → activa proyecto (detiene runner anterior y arranca nuevo; emite `type=project`)
- `GET /projects/active/current` → activo

## Agent
- `POST /agent/start?projectId` → inicia runner (normalmente automático al seleccionar)
- `POST /agent/stop` → detiene runner
- `GET /agent/status` → estado
- `POST /agent/send` → `{ text }` (stream por WS)

## Chat
- `POST /chat/send?projectId` → `{ text }` (persistencia + stream)
- `GET /chat/history?projectId&limit` → historial

## Timeline
- `GET /timeline?projectId&limit` → eventos
- `POST /timeline/{event_id}/revert` → acciones compensatorias

## Tools
- `GET /tools` → metadatos (schemas JSON)
- `POST /actions/execute?projectId` → `{ toolId, input }` (valida y delega al orquestador)

## Context
- `GET /context/state?projectId` → `{ scene, screenshot }` (urls, etags)
- `GET /context/screenshot?projectId` → metadata screenshot
- `GET /context/screenshot/file?projectId` → PNG
- `GET /context/scene/file?projectId` → JSON
- `POST /context/screenshot?projectId` → solicita captura y actualiza archivos

Ver también: `docs/api/websocket_protocol.md` y `docs/api/events.md`.

