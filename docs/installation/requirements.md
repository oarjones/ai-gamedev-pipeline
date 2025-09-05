# Requisitos

- Sistema operativo: Windows 10/11 o macOS 12+ (Linux soportado para Bridge/Blender).
- Unity: 2022.3 LTS+ con .NET SDK adecuado y Editor instalado.
- Blender: 3.6+ con permisos para instalar addons.
- Python: 3.10–3.12 con `pip` y entorno virtual recomendado.
- Node/WS opcional si usas herramientas externas.
- Permisos de red local para WebSocket entre procesos.

## Dependencias de Python (Bridge)

Consulta `mcp_unity_bridge/requirements.txt` y `requirements-agent.txt`. Se recomienda un entorno virtual.

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r mcp_unity_bridge/requirements.txt
```

## Versiones probadas

- Unity 2022.3 LTS
- Blender 4.x
- Python 3.12

