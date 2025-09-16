---
title: Eventos (Envelope y Rooms)
---

# Eventos (Envelope y Rooms)

Los eventos del Gateway se envían por WebSocket segmentados por proyecto.

- Endpoint: `/ws/events?project_id=<id>` (obligatorio)
- Formato Envelope:
  - `id: string (uuid)`
  - `type: chat | action | update | scene | timeline | log | error | project`
  - `project_id: string`
  - `payload: object` (dependiente del tipo)
  - `correlationId?: string`
  - `timestamp: ISO-8601`

Ejemplos y detalles se encuentran también en `docs/api/events.md`.

Tipos habituales:
- `chat`: `{ role: user|agent, content, msgId }`
- `action`: inicio de herramienta o tool-call del agente
- `timeline`: estado por paso (`running|success|error|reverted|cannot`)
- `update`: datos del resultado del paso
- `scene`: actualizaciones de contexto (e.g., screenshot)
- `log`: stderr del agente o diagnósticos (`level`)
- `project`: cambios de selección de proyecto (`status: active-changed`)

