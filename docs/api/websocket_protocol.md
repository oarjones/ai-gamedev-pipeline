# Protocolo WebSocket

Mensajes JSON intercambiados entre Unity y el Bridge (y Blender cuando aplique).

## Mensajes básicos

```json
{
  "type": "CommandRequest",
  "requestId": "uuid",
  "command": "CreatePrimitive",
  "payload": { "shape": "Cube", "size": 1.0 }
}
```

```json
{
  "type": "CommandResponse",
  "requestId": "uuid",
  "status": "OK",
  "result": { "assetPath": "Assets/Generated/cube.fbx" }
}
```

## Códigos de estado

- `OK`: completado
- `INVALID_ARGUMENT`: parámetros incorrectos
- `UNAVAILABLE`: dependencia/servicio no disponible
- `INTERNAL`: error interno

