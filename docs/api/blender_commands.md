# Comandos Blender

Referencia de comandos del addon `mcp_blender_addon`.

> Ejecuta `python scripts/generate_docs.py` para extraer docstrings y generar la tabla.

## Módulos de comandos

- `commands/modeling.py`
- `commands/topology.py`
- `commands/scene.py`
- etc.

## Tabla (autogenerada)

| Módulo | Función | Resumen |
|--------|---------|---------|
| (autogen) | (autogen) | (autogen) |

## Detalle (autogenerado)

<!-- AUTO:BLENDER_COMMANDS -->
| Módulo | Función | Resumen |
|--------|---------|---------|
| __init__ | _server_list_commands | Lista los nombres de todos los comandos registrados. |
| __init__ | _server_ping | Ping del servidor: útil para comprobación de salud. |
| analysis_metrics | mesh_stats | Compute mesh metrics: counts, bbox, surface/volume, quality, symmetry. |
| analysis_metrics | non_manifold_edges | Return the count of non-manifold edges for a mesh object. |
| mesh | from_points | Create a mesh object from raw vertices and optional faces/edges. |
| mesh | poly_extrude_from_outline | Create an extruded mesh from a 2D outline projected on a cardinal plane. |
| mesh | validate_and_heal | Validate mesh data, weld near-duplicate vertices, optionally fix normals, and dissolve degenerate geometry. |
| modeling | create_primitive | Create a mesh primitive without bpy.ops and link it to a collection. |
| modeling | echo | Echo parameters back to the caller. |
| modeling | get_version | Get Blender version, if available. |
| modeling_edit | bevel_edges | Bevel a set of edges using bmesh.ops.bevel. |
| modeling_edit | extrude_normal | Extrude selected faces along their normals by an amount. |
| modeling_edit | inset_region | Inset region for a set of faces using bmesh.ops.inset_region. |
| modifiers_core | add_boolean | Añade un modificador Boolean y configura su operand (objeto o colección). |
| modifiers_core | add_mirror | Añade un modificador Mirror al objeto de malla indicado. |
| modifiers_core | add_subsurf | Añade un modificador Subsurf al objeto con el nivel indicado. |
| modifiers_core | apply_all | Aplica todos los modificadores del objeto evaluando la malla resultante. |
| modifiers_core | apply_modifier | Apply a single modifier by name using evaluated mesh; avoids bpy.ops. |
| normals | recalc_normals | Recalculate normals outward or inward. |
| normals | recalc_selected | Recalcula normales para todos los objetos MESH seleccionados. |
| proc_arch | building | Procedurally generate a simple building shell with window cutouts. |
| proc_character | _build_skeleton_mesh | Create a stick-figure skeleton as a graph of edges in +X half (mirror will complete). |
| proc_character | character_base | Generate a base character mesh from a seeded edge skeleton using Skin+Mirror+Subsurf. |
| proc_terrain | terrain | Procedurally generate a terrain as a grid displaced by fBm noise. |
| project | from_blueprint_plane_cmd | Map blueprint pixel coordinates (u,v) on an Empty Image back to a world-space point on the plane. |
| project | to_blueprint_plane_cmd | Project a world-space point to a blueprint plane (Empty Image) and return pixel coordinates. |
| reference | _auto_otsu_threshold | Umbral automático (Otsu) sobre array normalizado [0..1]. |
| reference | _compose_delta_world | Build world-space delta matrix that scales in empty-local XY by (sx,sy) around object's projected center and translates to image center. |
| reference | _extract_binary_mask_any | Devuelve una máscara binaria uint8 (0/1) a partir de: |
| reference | _extract_points2d | Toma una respuesta de outline_* y devuelve una lista válida de points2d o []. |
| reference | _image_plane_dimensions | Compute plane dimensions (width,height) in empty local units based on display size and image aspect. |
| reference | _outline_from_binary_mask | Reutiliza el pipeline existente: convertimos la máscara binaria en borde. |
| reference | _project_bbox_on_empty_plane | Project object's mesh to empty local XY plane and return bbox (minx,miny,maxx,maxy) in empty local units. |
| reference | _silhouette_bbox_from_image | Compute 2D bbox (u_min, v_min, u_max, v_max) in normalized [0,1] space for opaque pixels. |
| reference | _sort_points_into_path | Ordena una nube de puntos 2D en un camino continuo usando el vecino más cercano. |
| reference | fit_bbox_to_blueprint | Fit object's projected 2D bbox to blueprint image silhouette bbox for the given view. |
| reference | outline_from_alpha | Extract main silhouette outline from image alpha via marching squares and simplify. |
| reference | outline_from_image | Generate outline from image, tolerant of missing alpha. |
| reference | reconstruct_from_alpha | Reconstruct an extruded mesh from an image's silhouette. |
| reference | reconstruct_from_image | NUEVO: igual que reconstruct_from_alpha pero tolerante a imágenes sin alpha. |
| reference | snap_silhouette_to_blueprint | Iteratively snap object's projected silhouette to the blueprint image edge for the given view. |
| reference_blueprints | blueprints_remove | Elimina los empties de referencia configurados y limpia el estado en escena. |
| reference_blueprints | blueprints_setup | Crea y configura tres imágenes de referencia (front/left/top) como empties. |
| reference_blueprints | blueprints_update | Actualiza una imagen de referencia existente (imagen, opacidad, visibilidad). |
| scene | clear | Clear the scene: remove all objects and purge orphaned meshes, images, materials and other data. |
| scene | remove_object | Remove a single object by name from the scene and purge its datablocks if orphaned. |
| selection_sets | selection_by_angle | Compute a face region grown by normal angle from seed faces and store it. |
| selection_sets | selection_restore | Restore a stored selection on the given object. |
| selection_sets | selection_store | Serialize current selection of the given object and domain into an object-local store. |
| topology | bevel_edges | Bevel selected edges using bmesh.ops.bevel. |
| topology | count_mesh_objects | Cuenta cuántos objetos de tipo MESH hay en la escena. |
| topology | ensure_object_mode | Garantiza que el modo activo sea OBJECT y lo devuelve. |
| topology | merge_by_distance | Remove doubles (merge by distance) across all verts. |
| topology | touch_active | Toca (escribe sin cambios efectivos) la malla activa para forzar actualización segura. |
| topology_cleanup | cleanup_basic | Topology cleanup: merge by distance, limited dissolve by angle, optional triangulate, and recalc normals. |

### __init__._server_list_commands

Lista los nombres de todos los comandos registrados.

Parámetros: {}
Devuelve: { commands: list[str] }

### __init__._server_ping

Ping del servidor: útil para comprobación de salud.

Parámetros: {}
Devuelve: { pong: true }

### analysis_metrics.mesh_stats

Compute mesh metrics: counts, bbox, surface/volume, quality, symmetry.

Returns a stable dict suitable for telemetry and UI.

### analysis_metrics.non_manifold_edges

Return the count of non-manifold edges for a mesh object.

Params:
  - object: str (mesh object name)

Returns: { count: int }

Example:
  analysis.non_manifold_edges({"object":"Cube"}) -> {"status":"ok","result":{"count":0}}

### mesh.from_points

Create a mesh object from raw vertices and optional faces/edges.

Params:
  - name: str
  - vertices: list[list[float]] size N x 3
  - faces: optional list[list[int]] (each len>=3)
  - edges: optional list[list[int]] (pairs)
  - collection: optional target collection name to link to
  - recalc_normals: bool (default True)

Returns: { object_name, counts: { verts, edges, faces } }

### mesh.poly_extrude_from_outline

Create an extruded mesh from a 2D outline projected on a cardinal plane.

Params:
  - name: str
  - points2d: list[[x,y], ...] CCW simple polygon
  - view: 'front'|'left'|'top' (plane mapping)
  - thickness: float (extrude amount along plane normal, default 0.2)
  - triangulate: bool (triangulate caps via ear clipping)
  - collection: optional collection name

Returns: { object_name, counts: { verts, edges, faces } }

### mesh.validate_and_heal

Validate mesh data, weld near-duplicate vertices, optionally fix normals, and dissolve degenerate geometry.

Params:
  - object: str (mesh object name)
  - weld_distance: float (merge by distance threshold, default 1e-5)
  - fix_normals: bool (recalculate normals, default True)
  - dissolve_threshold: float (degenerate dissolve distance, default 0.01)

Returns: { merged_verts: int, dissolved_edges: int }

### modeling.create_primitive

Create a mesh primitive without bpy.ops and link it to a collection.

Params (JSON object):
  - kind: "cube" | "uv_sphere" | "ico_sphere" | "cylinder" | "cone" | "torus" | "plane"
  - params: dict of shape parameters (see below)
  - collection: optional collection name to link object (created if missing)
  - name: optional object name; if omitted, a deterministic unique name is chosen

Common transform params (applied to object):
  - location: [x, y, z] (default [0,0,0])
  - rotation: [rx, ry, rz] radians (default [0,0,0])
  - scale: [sx, sy, sz] (default [1,1,1])

Shape params by kind (defaults in parentheses):
  - cube: size (2.0)
  - plane: size (2.0)
  - uv_sphere: radius (1.0), segments (32), rings (16)
  - ico_sphere: radius (1.0), subdivisions (2)
  - cylinder: radius (1.0), depth (2.0), segments (32), cap_ends (True)
  - cone: radius_bottom (1.0), radius_top (0.0), depth (2.0), segments (32), cap_ends (True)
  - torus: major_radius (1.0), minor_radius (0.25), segments (32), ring_segments (16)

Returns: { object_name, vertices, edges, faces, bbox }
  - bbox: [minx, miny, minz, maxx, maxy, maxz] in world space

### modeling.echo

Echo parameters back to the caller.

Params: any JSON-serializable object
Returns: { echo: <params> }

### modeling.get_version

Get Blender version, if available.

Returns: { blender: [major, minor, patch] | null }

### modeling_edit.bevel_edges

Bevel a set of edges using bmesh.ops.bevel.

Params: { object: str, edge_indices: list[int], offset: float, segments: int=2, clamp_overlap: bool=True }
Returns: { object, before: {...}, after: {...}, non_manifold: int }

### modeling_edit.extrude_normal

Extrude selected faces along their normals by an amount.

Params: { object: str, face_indices: list[int], amount: float }
Returns: { object, before: {...}, after: {...}, non_manifold: int, created_faces: int }

### modeling_edit.inset_region

Inset region for a set of faces using bmesh.ops.inset_region.

Params: { object: str, face_indices: list[int], thickness: float, depth: float=0.0 }
Returns: { object, before: {...}, after: {...}, non_manifold: int }

### modifiers_core.add_boolean

Añade un modificador Boolean y configura su operand (objeto o colección).

Parámetros: { object: str, operation?: 'DIFFERENCE'|'UNION'|'INTERSECT'='DIFFERENCE', operand_object?: str, operand_collection?: str }
Devuelve: { object, modifier, type, index }

### modifiers_core.add_mirror

Añade un modificador Mirror al objeto de malla indicado.

Parámetros: { object: str, axis?: 'X'|'Y'|'Z'='X', use_clip?: bool=true, merge_threshold?: float=1e-4 }
Devuelve: { object, modifier, type, index }

### modifiers_core.add_subsurf

Añade un modificador Subsurf al objeto con el nivel indicado.

Parámetros: { object: str, levels?: int=2 }
Devuelve: { object, modifier, type, index }

### modifiers_core.apply_all

Aplica todos los modificadores del objeto evaluando la malla resultante.

Parámetros: { object: str }
Devuelve: { object, applied: list[str], remaining: list[str] }

### modifiers_core.apply_modifier

Apply a single modifier by name using evaluated mesh; avoids bpy.ops.

Emulates Blender behavior: applying a modifier removes that modifier and all
those above it (earlier in the stack). Remaining modifiers stay and will
evaluate on the baked mesh.

### normals.recalc_normals

Recalculate normals outward or inward.

Params: { object: str, outside?: bool=true }
Returns: { object: str, outside: bool, faces: int }

### normals.recalc_selected

Recalcula normales para todos los objetos MESH seleccionados.

Parámetros: {}
Devuelve: { updated: int }  # número de objetos actualizados

### proc_arch.building

Procedurally generate a simple building shell with window cutouts.

Strategy: base parallelepiped -> Solidify (walls) -> Boolean difference with window cutters.
Window placement is pseudo-random but seeded and reproducible.

### proc_character._build_skeleton_mesh

Create a stick-figure skeleton as a graph of edges in +X half (mirror will complete).

### proc_character.character_base

Generate a base character mesh from a seeded edge skeleton using Skin+Mirror+Subsurf.

Modifier order: Mirror → Skin → Subsurf (Mirror first so Skin operates on welded, mirrored skeleton).
Proportions keys accepted: torso_len, head_len, arm_len, leg_len, body_width, body_depth.
Values are scale multipliers relative to defaults and are clamped to [0.5, 2.0].

### proc_terrain.terrain

Procedurally generate a terrain as a grid displaced by fBm noise.

Params:
  - width: float (default 50)
  - depth: float (default 50)
  - resolution: int quads per axis (default 128)
  - seed: int (default 0)
  - amplitude: float (default 5.0)
  - lacunarity: float (default 2.0)
  - gain: float (default 0.5)

LOD/tiling: splits into tiles if resolution is large to avoid a single huge mesh.

Returns: { object_name, tiles }

### project.from_blueprint_plane_cmd

Map blueprint pixel coordinates (u,v) on an Empty Image back to a world-space point on the plane.

Params:
  - u: float (pixel u or normalized if image is missing)
  - v: float (pixel v or normalized if image is missing)
  - view: "front|left|top"
  - empty: empty object name

Returns: { point: [x,y,z] }

### project.to_blueprint_plane_cmd

Project a world-space point to a blueprint plane (Empty Image) and return pixel coordinates.

Params:
  - point: [x,y,z] world-space
  - view: "front|left|top" (string; orientation is taken from empty's transform)
  - empty: empty object name (the reference blueprint Empty)

Returns: { u: float, v: float }

### reference._auto_otsu_threshold

Umbral automático (Otsu) sobre array normalizado [0..1].
Evita “threshold too high/low” cuando la imagen no trae alpha usable.

### reference._compose_delta_world

Build world-space delta matrix that scales in empty-local XY by (sx,sy) around object's projected center and translates to image center.

### reference._extract_binary_mask_any

Devuelve una máscara binaria uint8 (0/1) a partir de:
  - alpha real (si existe y varía)
  - distancia al color de fondo (bg key)
  - luma (grayscale) con umbral automático si no se indica threshold

### reference._extract_points2d

Toma una respuesta de outline_* y devuelve una lista válida de points2d o [].

### reference._image_plane_dimensions

Compute plane dimensions (width,height) in empty local units based on display size and image aspect.

### reference._outline_from_binary_mask

Reutiliza el pipeline existente: convertimos la máscara binaria en borde.
Si ya tienes una función equivalente, usa esa. Aquí hacemos borde por gradiente.

### reference._project_bbox_on_empty_plane

Project object's mesh to empty local XY plane and return bbox (minx,miny,maxx,maxy) in empty local units.

### reference._silhouette_bbox_from_image

Compute 2D bbox (u_min, v_min, u_max, v_max) in normalized [0,1] space for opaque pixels.

If alpha channel is uniform (no alpha), fallback to luminance threshold where ink = (1 - luminance) >= alpha_threshold.
Returns bbox and (width,height) in pixels.

### reference._sort_points_into_path

Ordena una nube de puntos 2D en un camino continuo usando el vecino más cercano.

### reference.fit_bbox_to_blueprint

Fit object's projected 2D bbox to blueprint image silhouette bbox for the given view.

- Uses existing Empty Image for the view (front|left|top) created by ref.blueprints_setup.
- If 'image' is provided, loads it (check_existing) and uses it instead of the Empty's assigned image.
- Computes silhouette bbox via alpha threshold (fallback to luminance if alpha is uniform).
- Projects object geometry into the Empty's local XY plane, computes bbox there,
  and applies a scale (uniform or per-axis) and translation so the bboxes match.
- Avoids bpy.ops; applies transforms via matrix multiplication.

### reference.outline_from_alpha

Extract main silhouette outline from image alpha via marching squares and simplify.

Returns: { points2d: [[x,y],...], width, height, scale_hint }

### reference.outline_from_image

Generate outline from image, tolerant of missing alpha.

Params:
  - image: path to image
  - mode: "auto" | "alpha" | "bg" | "luma"
  - threshold: None => auto (Otsu)
  - bg_color: optional [r,g,b]
  - invert_luma: bool
  - simplify_tol: optional tolerance for simplification

### reference.reconstruct_from_alpha

Reconstruct an extruded mesh from an image's silhouette.

Steps:
  1) Try outline via reference.outline_from_alpha (marching squares + simplify).
  2) If alpha is not useful or fails, fallback to reference.outline_from_image (auto).
  3) Build mesh via mesh.poly_extrude_from_outline using view/thickness.

### reference.reconstruct_from_image

NUEVO: igual que reconstruct_from_alpha pero tolerante a imágenes sin alpha.
Internamente llama a outline_from_image y sigue el pipeline existente.

### reference.snap_silhouette_to_blueprint

Iteratively snap object's projected silhouette to the blueprint image edge for the given view.

- Identifies candidate vertices from silhouette edges w.r.t. the view direction.
- Projects vertices to blueprint plane (Empty local XY) and nudges them towards the silhouette boundary
  by scanning along the radial direction from the object's projected centroid.
- Applies light Laplacian smoothing after each iteration to reduce jaggies.

### reference_blueprints.blueprints_remove

Elimina los empties de referencia configurados y limpia el estado en escena.

Parámetros: {}
Devuelve: { removed: list[str] }

### reference_blueprints.blueprints_setup

Crea y configura tres imágenes de referencia (front/left/top) como empties.

Parámetros:
  - front: ruta a imagen (str)
  - left: ruta a imagen (str)
  - top: ruta a imagen (str)
  - size: float tamaño base del empty (default 1.0)
  - opacity: float [0..1] opacidad (default 0.4)
  - lock: bool bloquear transformaciones (default True)

Devuelve: { ids: {front, left, top} } con los nombres de los empties creados.

### reference_blueprints.blueprints_update

Actualiza una imagen de referencia existente (imagen, opacidad, visibilidad).

Parámetros:
  - which: 'front'|'left'|'top'
  - image: ruta a nueva imagen (opcional)
  - opacity: float [0..1] (opcional)
  - visible: bool (opcional)

Devuelve: { updated: which }

### scene.clear

Clear the scene: remove all objects and purge orphaned meshes, images, materials and other data.

Params: {}

Returns: { objects_removed: int, meshes_purged: int, images_purged: int, materials_purged: int }

Example:
  scene.clear({}) -> {"status":"ok","result":{"objects_removed":3,...}}

### scene.remove_object

Remove a single object by name from the scene and purge its datablocks if orphaned.

Params:
  - name: object name (string)

Returns: { removed: bool }

Example:
  scene.remove_object({"name": "Cube"}) -> {"status":"ok","result":{"removed":true}}

### selection_sets.selection_by_angle

Compute a face region grown by normal angle from seed faces and store it.

Params: { object: str, seed_faces: list[int], max_angle: float }
Returns: { selection_id, count }

### selection_sets.selection_restore

Restore a stored selection on the given object.

Params: { object: str, selection_id: str }
Returns: { mode, count }

### selection_sets.selection_store

Serialize current selection of the given object and domain into an object-local store.

Params: { object: str, mode: "VERT"|"EDGE"|"FACE" }
Returns: { selection_id, mode, count }
Stored format (in Object custom property 'mw_sel' as JSON):
  { "sets": { id: { "mode": str, "v"|"e"|"f": range_str, "t": epoch } }, "counter": int }

### topology.bevel_edges

Bevel selected edges using bmesh.ops.bevel.

Params: { object: str, edge_indices: list[int], offset: float, segments?: int=2, clamp?: bool=true }
Returns: { created_edges: int, created_faces: int }

### topology.count_mesh_objects

Cuenta cuántos objetos de tipo MESH hay en la escena.

Parámetros: {}
Devuelve: { count: int }

### topology.ensure_object_mode

Garantiza que el modo activo sea OBJECT y lo devuelve.

Parámetros: {}
Devuelve: { mode: str }

### topology.merge_by_distance

Remove doubles (merge by distance) across all verts.

Params: { object: str, distance?: float=0.0001 }
Returns: { removed_verts: int }

### topology.touch_active

Toca (escribe sin cambios efectivos) la malla activa para forzar actualización segura.

Útil para probar acceso a BMesh y flujos de lectura/escritura sin modificar geometría.

Parámetros: {}
Devuelve: { touched: bool }

### topology_cleanup.cleanup_basic

Topology cleanup: merge by distance, limited dissolve by angle, optional triangulate, and recalc normals.

Params:
  - object: str (mesh name)
  - merge_distance: float (>=0, default 1e-4)
  - limited_angle: float (radians, [0..pi], default 0.349 ~ 20deg)
  - force_tris: bool (default False) — triangulate all faces if True

Returns: { removed_verts: int, dissolved_edges: int, tri_faces: int }
<!-- AUTO:BLENDER_COMMANDS:END -->
