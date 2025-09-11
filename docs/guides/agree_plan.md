---
title: Acordar plan de desarrollo
---

# Acordar plan de desarrollo

1) Tras generar el plan (Wizard → Generate Plan), revisa la propuesta en Chat.
2) Ajusta el JSON si fuese necesario (identificadores, dependencias, criterios de aceptación).
3) Pega el JSON en “Plan of Record” y pulsa “Save Plan”.

Formato sugerido:

```json
{
  "version": "1.0",
  "phases": ["bootstrap", "vertical slice"],
  "tasks": [
    {"id": "T-001", "title": "Preparar escena", "desc": "", "deps": [], "acceptance": "Se abre escena base"}
  ],
  "risks": ["Versiones de editor"],
  "deliverables": ["Escena base", "FBX inicial"]
}
```

Buenas prácticas:
- Criterios de aceptación concretos y verificables.
- Identificadores estables (T-001, T-002, …).

