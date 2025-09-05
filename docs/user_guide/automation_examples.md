# Ejemplos de automatización

## Generar malla y exportar a Unity

1. Blender: generar malla procedural (p. ej., `proc_terrain`).
2. Guardar/Exportar FBX a `unity_project/Assets/Generated/`.
3. Unity detecta el asset y lo importa.

## Pipeline de validación

- Bridge ejecuta validadores tras cada comando (normales, topología, etc.).
- Si falla, retorna error con código y sugerencias.

