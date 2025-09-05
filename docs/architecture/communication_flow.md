# Flujo de comunicación

```mermaid
sequenceDiagram
  participant Unity
  participant Bridge
  participant Blender

  Unity->>Bridge: CommandRequest(cmd, payload)
  Bridge-->>Unity: Ack (requestId)
  Bridge->>Blender: ToolInvoke(tool, args)
  Blender-->>Bridge: ToolResult(result)
  Bridge-->>Unity: CommandResponse(requestId, result)
```

- Protocolos: WebSocket (JSON) para comandos, HTTP opcional para recursos.
- Trazabilidad: cada request posee `requestId` para correlación.
- Manejo de errores: códigos y descripciones estandarizadas.

