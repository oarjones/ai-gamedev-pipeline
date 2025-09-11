---
title: Ejecutar tareas con confirmación
---

# Ejecutar tareas con confirmación (human-in-the-loop)

1) Ve a “Tasks” y pulsa “Import from Plan” para traer tareas del `plan_of_record.yaml`.
2) Selecciona una tarea para ver descripción y aceptación.
3) “Propose Steps” → el agente sugiere sub-pasos en Chat (no ejecuta).
4) Ejecuta herramientas desde el panel (tool + args JSON). Para acciones sensibles (export/delete/rename) debes marcar “Confirm sensitive action”.
5) Al finalizar, adjunta evidencia (paths/artifacts/logs) y marca “Mark as Done” si cumple aceptación.

Consejos:
- Usa rutas dentro de `unity_project/Assets/Generated` para exportaciones.
- Reintenta con feedback si no se cumple aceptación a la primera.

