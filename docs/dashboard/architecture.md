---
title: Arquitectura del Dashboard (Gateway)
---

# Arquitectura del Dashboard (Gateway)

```mermaid
flowchart LR
  subgraph UI[Web UI (React/Vite)]
    A[HTTP: REST]
    B[WS: /ws/events?projectId]
  end

  A -->|/api/v1/*| GW[(AI Gateway FastAPI)]
  B -->|Rooms por proyecto| GW

  subgraph GWINT[Gateway Interno]
    R[Routers: projects, agent, chat, timeline, tools, context]
    S[Services: AgentRunner, ChatService, ActionOrchestrator, MCPClient, ToolsRegistry, TimelineService]
    DB[(SQLite: projects, chat_messages, timeline_events)]
  end

  GW --> R
  R --> S
  S --> DB

  subgraph AGENT[Agente CLI por proyecto]
    CWD[cwd=projects/<id>]
    CLI[Agente CLI real]
  end

  S -.start/stop/send.-> CLI
  CLI -.stdout/stderr stream.-> S

  subgraph MCP[MCP Adapters]
    U[Unity MCP (WS)]
    BL[Blender Add-on (WS)]
  end

  S -->|run_tool / helpers| U
  S -->|run_tool / helpers| BL

  S -->|Envelope| B
```

Notas clave:
- WS usa salas por `projectId` y un Envelope unificado (`type`, `projectId`, `payload`, `correlationId`, `timestamp`).
- `AgentRunner` gestiona el proceso del agente con lectura incremental de `stdout/stderr` y correlación.
- `ActionOrchestrator` valida un plan y ejecuta herramientas (MCP) secuencialmente, emitiendo `timeline` y `update`.
- `TimelineService` persiste y soporta `revert` con acciones compensatorias.

