---
title: Estado de Procesos del Sistema
---

# /api/v1/system/status

Devuelve una lista con el estado de cada proceso gestionado por el gateway.

Formato de respuesta:

```
[
  {
    name: string,
    pid: string | null,
    running: boolean,
    startedAt: string | null,
    lastStdout: string,
    lastStderr: string,   # NUEVO: cola de stderr (hasta ~1KB)
    lastError: string | null
  },
  ...
]
```

Notas:
- `lastStdout` y `lastStderr` contienen un buffer circular (tail) para ayudar a diagnóstico rápido.
- `lastError` refleja el último error de arranque/parada o, si el proceso terminó, puede incluir el tail de stderr.
- Orden recomendado de gestión: start → Unity → Unity Bridge → Blender → Blender Bridge; stop en orden inverso.

