# MCP Blender Add-on — Arquitectura Modular (2.79)

> **Objetivo**: mantener un servidor WebSocket mínimo y estable, y mover la lógica a módulos
organizados por dominio (modelado, selección, topología, similitud, …) con un patrón de registro
de **comandos**. Esto facilita pruebas, escalabilidad y mantenibilidad sin cambiar el protocolo
JSON `{ "command": "...", "params": {...} }` que ya usa tu cliente MCP.

---

## 1) Principios de diseño

- **Servidor delgado**: `websocket_server.py` solo arranca WS, valida entradas y realiza **dispatch**
  a los comandos registrados.
- **Dominios separados**: cada grupo de herramientas vive en `commands/<dominio>.py`.
- **Estado explícito**: `SessionContext` agrega **SelectionStore**, **SnapshotStore** y futuros caches (imágenes, BVH).
- **Compat 2.79**: utilidades en `server/compat.py` (ej.: `Matrix.Diagonal` → `Matrix.Scale` compuesto).
- **Sin `bpy.ops` en herramientas “core”**: preferir **bmesh** para robustez; dejar `bpy.ops` en
  utilidades “de conveniencia” (`util.*`) aisladas.
- **Errores consistentes**: todas las tools devuelven `{status:"ok" | "error", ...}`; el decorador
  `@tool` captura excepciones y formatea el error.
- **Pruebas modulables**: `ws_blender_full_test.py` permite ejecutar **bloques** (`--only/--skip`).

---

## 2) Estructura de carpetas

```
mcp_blender_addon/
├─ __init__.py               # register()/unregister(): arranca/para servidor
├─ websocket_server.py       # DELGADO: loop WS + dispatch a comandos
├─ server/
│  ├─ __init__.py
│  ├─ registry.py            # registro global + decoradores @tool @command
│  ├─ context.py             # SessionContext, SelectionStore, SnapshotStore
│  ├─ utils.py               # helpers bmesh, bbox, normals, scale_matrix, remove_doubles...
│  ├─ compat.py              # compatibilidad 2.79 (wrappers y sustituciones)
│  └─ logging.py             # logger simple (opcional)
├─ io/
│  ├─ __init__.py
│  ├─ masks.py               # carga imagen, raster planos XY/XZ/YZ, IoU, gradiente
│  └─ images.py              # caché básica de imágenes (opcional)
└─ commands/
   ├─ __init__.py            # importa submódulos para que se registren
   ├─ selection.py           # faces_in_bbox, by_range, geodesic, edge_loop/ring
   ├─ edit.py                # move/extrude/sculpt, snap_to_silhouette, landmarks
   ├─ modeling.py            # create_base, mirror_x/plane, symmetry_radial, cleanup
   ├─ topology.py            # triangulate_beautify, join_quads, bridge_loops, fill_holes
   ├─ similarity.py          # iou_top/side/front/combo3, (futuro) chamfer_to_object
   ├─ snapshots.py           # snapshot/restore/blend
   ├─ normals.py             # normals_recalc, flip heurística
   ├─ export.py              # export_fbx preset, validate (pre-export checks)
   ├─ animation.py           # split_by_markers, bake_constraints, rootmotion, events (futuro)
   ├─ uv.py                  # unwrap, uv_lightmap/UV2 (futuro)
   ├─ materials.py           # assign_pbr, manifest (futuro)
   ├─ lod.py                 # generate LODs (futuro)
   └─ physics.py             # colliders, masa e inercia (futuro)
```

> Puedes empezar migrando **selection**, **edit**, **modeling**, **topology**, **similarity**, **snapshots**, **normals**.

---

## 3) Flujo de ejecución

1. **register()** del add-on: arranca el hilo del servidor WebSocket y llama a `_load_command_modules()`:
   importa `commands/*` (que registran funciones en `COMMANDS`).
2. **Conexión entrante**: se crea un `SessionContext(bpy)` (o uno global por servidor).
3. **Mensaje** `{command, params}`: el servidor busca `fn = COMMANDS[command]` y ejecuta
   `fn(ctx, **params)`.
4. **Respuesta**: siempre dict JSON con `status: "ok"` o `"error"` + datos/trace.

---

## 4) Registro de comandos

### `server/registry.py`
```python
COMMANDS = {}  # str -> callable(ctx, **params)

def tool(fn):
    name = getattr(fn, "_command_name", None) or fn.__name__
    def _wrap(ctx, **kwargs):
        import traceback
        try:
            return fn(ctx, **kwargs)
        except Exception as e:
            return {
                "status": "error",
                "tool": name,
                "message": "{}: {}".format(e.__class__.__name__, e),
                "trace": traceback.format_exc()
            }
    COMMANDS[name] = _wrap
    return _wrap

def command(name):
    def _decorator(fn):
        fn._command_name = name
        return fn
    return _decorator
```

### `websocket_server.py` (dispatch)
```python
from server.registry import COMMANDS
from server.context import SessionContext

# en handler():
ctx = SessionContext(bpy)
cmd = data.get("command")
params = data.get("params") or {}
fn = COMMANDS.get(cmd)
ack = fn(ctx, **params) if fn else {"status":"error","message":"unknown command"}
```

---

## 5) Contexto y estado

### `server/context.py`
- **SelectionStore**: guarda selecciones de **faces/verts/edges** por `selection_id`.
- **SnapshotStore**: guarda arrays de vértices/caras para `mesh.snapshot/restore/blend`.
- **SessionContext**: acceso a `bpy`, stores, y espacio para caches (imágenes, BVH).

Ventajas: los comandos son **puros** (reciben `ctx`), evitan globales frágiles y facilitan tests.

---

## 6) Utilidades clave

- `utils.bm_from_object` / `bm_to_object`: ida y vuelta entre `bmesh` y `Mesh` con `normal_update()`.
- `utils.remove_doubles(bm, dist)`.
- `utils.scale_matrix(sx,sy,sz)`: sustituto de `Matrix.Diagonal` (no existe en 2.79).
- `io.masks`: `load_mask_image(path, res, thr)`, `rasterize_mesh_plane_local(obj, plane, ...)`, `iou(maskA, maskB)`, `mask_grad`.

---

## 7) Convenciones de comandos

- Firma: `def tool_fn(ctx, **params) -> dict`
- Éxito: `{"status":"ok", ...}`. Error (capturado por `@tool`): `{"status":"error","tool":"name","message":"...", "trace":"..."}`.
- No lanzar excepciones sin capturar; dejar que `@tool` las formatee.
- Nombres **establecidos** por `@command("namespace.action")`.

**Ejemplo mínimo:**
```python
@tool
@command("mesh.normals_recalc")
def normals_recalc(ctx, object=None, ensure_outside=True):
    obj = ctx.bpy.data.objects.get(object)
    if obj is None:
        return {"status":"error","message":"objeto no encontrado"}
    me = obj.data
    me.calc_normals()
    if ensure_outside:
        # heurística para orientar hacia fuera (si aplica)
        pass
    return {"status":"ok","flipped":0}
```

---

## 8) Plan de migración (fases pequeñas)

**Fase 0 – Estabilizar**  
- Corregir errores de tools actuales (p.ej. `Matrix.Diagonal` → `scale_matrix`).  
- Confirmar que **todas** devuelven errores bien formateados.

**Fase 1 – Infraestructura**  
- Añadir `server/registry.py`, `server/context.py`, `server/utils.py`, `io/masks.py`.  
- Mantener `websocket_server.py` actual pero **usar registro** para nuevas tools.

**Fase 2 – Mover comandos por dominio**  
- Crear `commands/selection.py`, `commands/edit.py`, `commands/modeling.py`, `commands/topology.py`, `commands/similarity.py`, etc.  
- Cada módulo importa `@tool`/`@command` y registra sus funciones.

**Fase 3 – Reducir `websocket_server.py`**  
- Reemplazar `if/elif` gigante por el **dispatch** del registro.  
- Mantener utilidades no-modulares (p.ej. `execute_python`, `export_fbx`) como “builtin”.

**Fase 4 – Validación completa**  
- Ejecutar `ws_blender_full_test.py` con `--only/--skip` en CI local.  
- Medir tiempo por bloque y revisar logs/errores.

---

## 9) Pruebas y CI local

- **Archivo de pruebas**: `ws_blender_full_test.py` modular (con `error_probe` al inicio).  
- Flags: `--only similarity_3views,symmetries` o `--skip merge_and_export`.  
- Validar que **cada respuesta** tiene `status` y, si es `error`, contiene `tool/message/trace`.

**Sugerencia**: Guardar logs por bloque en `Generated/logs/YYYYMMDD_HHMM/test_<block>.json`.

---

## 10) Protocolo y compatibilidad

- **Handshake** `identify`: devolver `{"blender_version":[2,79,0], "websockets_version":"7.0", "module_file": ...}`.
- Blender 2.79 + Python 3.5 (interno); el **cliente** puede ser 3.10+.
- Evitar `Matrix.Diagonal` (no existe); usar `Matrix.Scale` o helpers (`scale_matrix`).  
- Preferir **bmesh.ops** a `bpy.ops` por contexto y robustez.  
- `export_fbx`: mantener “wrapper” al final del pipeline (no mezclar con edición).

---

## 11) Módulos futuros (esqueleto)

- **animation**: `split_by_markers`, `bake_constraints`, `rootmotion_extract`, `events_add`.  
- **uv**: `uv_lightmap` (UV2), `unwrap_auto`, densidad por área.  
- **materials**: `assign_pbr`, `export_manifest`.  
- **lod**: `generate` (decimate/remesh), naming `_LOD0..3`.  
- **physics**: `make_collider` (box/capsule/convex), `estimate_mass_inertia`.  
- **export**: `validate` (pre-flight checks), `fbx_preset` (ejes, escalas, nombres).

Cada módulo con sus tests dedicados en el cliente y ejemplos JSON para el agente IA.

---

## 12) Checklist “pre-export”

- [ ] Escala aplicada (1,1,1) y transform congelado.  
- [ ] Normales coherentes, sin **ngons**/no-manifold.  
- [ ] UV0 y, si lightmap: UV2 sin solapes.  
- [ ] Número de materiales <= presupuesto.  
- [ ] LODs (si procede) y colliders definidos.  
- [ ] Animación horneada (sin constraints), root motion correcto.  
- [ ] `export.validate` OK → `export.fbx_preset`.

---

## 13) Añadir una tool nueva (plantilla)

1. Crea función en `commands/<dominio>.py`:
```python
from server.registry import tool, command

@tool
@command("my.namespace_action")
def my_action(ctx, object=None, strength=1.0):
    obj = ctx.bpy.data.objects.get(object)
    if obj is None:
        return {"status":"error","message":"objeto no encontrado"}
    # ... lógica ...
    return {"status":"ok","changed": 42}
```
2. Asegúrate de que `commands/__init__.py` importa tu módulo para registrar.  
3. Prueba desde el cliente con un bloque en `ws_blender_full_test.py`.

---

## 14) Glosario rápido

- **ctx**: `SessionContext` con acceso a `bpy`, `sel`, `snap`, caches.  
- **selection_id**: handle que referencia índices (faces/verts/edges) guardados.  
- **snapshot**: copia ligera de vértices/caras para deshacer/restaurar.  
- **mask/raster**: imagen binaria de silueta en un plano (XY/XZ/YZ) para IoU/snap.

---

### Notas finales
- Mantén el **protocolo JSON** estable: eso permite cambiar internals sin tocar el cliente.  
- Documenta cada tool en docstring y con un **ejemplo JSON** (como ya haces en `mcp_adapter.py`).  
- Si en el futuro migras de 2.79, encierra diferencias en `server/compat.py`.

¡Listo para llevar a otra conversación y seguir iterando! 🚀
