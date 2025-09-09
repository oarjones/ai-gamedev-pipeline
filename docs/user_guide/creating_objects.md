# Creación de objetos (Unity/Blender)

## Desde Unity

- Usa `MCPToolbox` para invocar `CreatePrimitive` u otros comandos registrados.
- Revisa la respuesta y logs en consola.

## Desde Blender

- En el panel del addon, selecciona `Modeling > Create > Cube/Sphere`.
- Usa docstrings de cada comando para entender parámetros disponibles.

## Mejores prácticas

- Prefiere comandos idempotentes y con validaciones de entrada.
- Define límites de tamaño/complejidad al generar mallas.

