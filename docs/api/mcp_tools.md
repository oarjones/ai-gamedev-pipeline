# Herramientas MCP

Esta página se genera parcialmente desde docstrings y comentarios XML. Ejecuta `python scripts/generate_docs.py` para actualizar.

## Catálogo (resumen)

> La tabla siguiente se actualizará automáticamente.

| Nombre | Origen | Descripción |
|-------|--------|-------------|
| __init__._server_list_commands | Blender | Lista los nombres de todos los comandos registrados. |
| __init__._server_ping | Blender | Ping del servidor: útil para comprobación de salud. |
| analysis_metrics.mesh_stats | Blender | Compute mesh metrics: counts, bbox, surface/volume, quality, symmetry. |
| analysis_metrics.non_manifold_edges | Blender | Return the count of non-manifold edges for a mesh object. |
| mesh.from_points | Blender | Create a mesh object from raw vertices and optional faces/edges. |
| mesh.poly_extrude_from_outline | Blender | Create an extruded mesh from a 2D outline projected on a cardinal plane. |
| mesh.validate_and_heal | Blender | Validate mesh data, weld near-duplicate vertices, optionally fix normals, and dissolve degenerate geometry. |
| modeling.create_primitive | Blender | Create a mesh primitive without bpy.ops and link it to a collection. |
| modeling.echo | Blender | Echo parameters back to the caller. |
| modeling.get_version | Blender | Get Blender version, if available. |
| modeling_edit.bevel_edges | Blender | Bevel a set of edges using bmesh.ops.bevel. |
| modeling_edit.extrude_normal | Blender | Extrude selected faces along their normals by an amount. |
| modeling_edit.inset_region | Blender | Inset region for a set of faces using bmesh.ops.inset_region. |
| modifiers_core.add_boolean | Blender | Añade un modificador Boolean y configura su operand (objeto o colección). |
| modifiers_core.add_mirror | Blender | Añade un modificador Mirror al objeto de malla indicado. |
| modifiers_core.add_subsurf | Blender | Añade un modificador Subsurf al objeto con el nivel indicado. |
| modifiers_core.apply_all | Blender | Aplica todos los modificadores del objeto evaluando la malla resultante. |
| modifiers_core.apply_modifier | Blender | Apply a single modifier by name using evaluated mesh; avoids bpy.ops. |
| normals.recalc_normals | Blender | Recalculate normals outward or inward. |
| normals.recalc_selected | Blender | Recalcula normales para todos los objetos MESH seleccionados. |
| proc_arch.building | Blender | Procedurally generate a simple building shell with window cutouts. |
| proc_character._build_skeleton_mesh | Blender | Create a stick-figure skeleton as a graph of edges in +X half (mirror will complete). |
| proc_character.character_base | Blender | Generate a base character mesh from a seeded edge skeleton using Skin+Mirror+Subsurf. |
| proc_terrain.terrain | Blender | Procedurally generate a terrain as a grid displaced by fBm noise. |
| project.from_blueprint_plane_cmd | Blender | Map blueprint pixel coordinates (u,v) on an Empty Image back to a world-space point on the plane. |
| project.to_blueprint_plane_cmd | Blender | Project a world-space point to a blueprint plane (Empty Image) and return pixel coordinates. |
| reference._auto_otsu_threshold | Blender | Umbral automático (Otsu) sobre array normalizado [0..1]. |
| reference._compose_delta_world | Blender | Build world-space delta matrix that scales in empty-local XY by (sx,sy) around object's projected center and translates to image center. |
| reference._extract_binary_mask_any | Blender | Devuelve una máscara binaria uint8 (0/1) a partir de: |
| reference._extract_points2d | Blender | Toma una respuesta de outline_* y devuelve una lista válida de points2d o []. |
| reference._image_plane_dimensions | Blender | Compute plane dimensions (width,height) in empty local units based on display size and image aspect. |
| reference._outline_from_binary_mask | Blender | Reutiliza el pipeline existente: convertimos la máscara binaria en borde. |
| reference._project_bbox_on_empty_plane | Blender | Project object's mesh to empty local XY plane and return bbox (minx,miny,maxx,maxy) in empty local units. |
| reference._silhouette_bbox_from_image | Blender | Compute 2D bbox (u_min, v_min, u_max, v_max) in normalized [0,1] space for opaque pixels. |
| reference._sort_points_into_path | Blender | Ordena una nube de puntos 2D en un camino continuo usando el vecino más cercano. |
| reference.fit_bbox_to_blueprint | Blender | Fit object's projected 2D bbox to blueprint image silhouette bbox for the given view. |
| reference.outline_from_alpha | Blender | Extract main silhouette outline from image alpha via marching squares and simplify. |
| reference.outline_from_image | Blender | Generate outline from image, tolerant of missing alpha. |
| reference.reconstruct_from_alpha | Blender | Reconstruct an extruded mesh from an image's silhouette. |
| reference.reconstruct_from_image | Blender | NUEVO: igual que reconstruct_from_alpha pero tolerante a imágenes sin alpha. |
| reference.snap_silhouette_to_blueprint | Blender | Iteratively snap object's projected silhouette to the blueprint image edge for the given view. |
| reference_blueprints.blueprints_remove | Blender | Elimina los empties de referencia configurados y limpia el estado en escena. |
| reference_blueprints.blueprints_setup | Blender | Crea y configura tres imágenes de referencia (front/left/top) como empties. |
| reference_blueprints.blueprints_update | Blender | Actualiza una imagen de referencia existente (imagen, opacidad, visibilidad). |
| scene.clear | Blender | Clear the scene: remove all objects and purge orphaned meshes, images, materials and other data. |
| scene.remove_object | Blender | Remove a single object by name from the scene and purge its datablocks if orphaned. |
| selection_sets.selection_by_angle | Blender | Compute a face region grown by normal angle from seed faces and store it. |
| selection_sets.selection_restore | Blender | Restore a stored selection on the given object. |
| selection_sets.selection_store | Blender | Serialize current selection of the given object and domain into an object-local store. |
| topology.bevel_edges | Blender | Bevel selected edges using bmesh.ops.bevel. |
| topology.count_mesh_objects | Blender | Cuenta cuántos objetos de tipo MESH hay en la escena. |
| topology.ensure_object_mode | Blender | Garantiza que el modo activo sea OBJECT y lo devuelve. |
| topology.merge_by_distance | Blender | Remove doubles (merge by distance) across all verts. |
| topology.touch_active | Blender | Toca (escribe sin cambios efectivos) la malla activa para forzar actualización segura. |
| topology_cleanup.cleanup_basic | Blender | Topology cleanup: merge by distance, limited dissolve by angle, optional triangulate, and recalc normals. |
| CSharpRunner.(miembro) | Unity | Intenta compilar con referencias esenciales y reintenta con todas si falla. |
| CSharpRunner.(miembro) | Unity | Compila el código con el conjunto de ensamblados proporcionado. |
| CSharpRunner.BuildSourceTemplate | Unity | Envuelve el código del agente en una clase contenedora con método Run(). Devuelve el código final y el desplazamiento de línea para mapear errores. |
| CSharpRunner.Execute | Unity | Compila y ejecuta el código C# proporcionado, devolviendo el resultado o errores. |
| CommandDispatcher.EnqueueAction | Unity | Encola una acción para ejecutarse en el ciclo de actualización del Editor. |
| CommandDispatcher.EnsureCameraAndLight | Unity | Garantiza la existencia de una cámara principal y una luz direccional. |
| CommandDispatcher.OnEditorUpdate | Unity | Drena la cola y ejecuta la siguiente acción, si existe. |
| CommandDispatcher.ProcessCommand | Unity | Ejecuta un comando de mutación (ImportFBX, EnsureCameraAndLight o código C# dinámico). |
| CommandDispatcher.ProcessIncomingMessage | Unity | Procesa un mensaje JSON entrante y emite la respuesta correspondiente. |
| CommandDispatcher.ProcessQuery | Unity | Resuelve consultas de solo lectura del entorno (jerarquía, screenshot, detalles, archivos). |
| CommandDispatcher.ProcessToolAction | Unity | Invoca un método público estático de <see cref="MCPToolbox"/> mapeándolo desde 'action'. |
| CommandExecutionResult.(miembro) | Unity | Clase genérica para envolver listas y objetos. Originalmente para JsonUtility, se mantiene por ahora para compatibilidad con EnvironmentScanner. |
| DynamicExecutor.GetAllAssemblies | Unity | Devuelve ubicaciones de todos los ensamblados cargados estáticamente más los esenciales. |
| DynamicExecutor.GetAssemblyLocation | Unity | Resuelve la ubicación de un ensamblado por nombre (sin extensión) o ruta. |
| DynamicExecutor.GetEssentialAssemblies | Unity | Conjunto mínimo de ensamblados comunes para la mayoría de scripts del Editor. |
| DynamicExecutor.SerializeReturnValue | Unity | Serializa el valor de retorno intentando usar JSON y con fallback a ToString(). |
| EnvironmentScanner.(miembro) | Unity | (NUEVO MÉTODO) Extrae de forma segura las propiedades serializables de un componente de Unity. Extrae de forma segura propiedades serializables de un componente de Unity, filtrando tipos complejos y propiedades problemáticas. |
| EnvironmentScanner.BuildGameObjectData | Unity | Construye recursivamente un árbol de GameObjectData para un GameObject dado. |
| EnvironmentScanner.GetGameObjectDetails | Unity | Devuelve detalles serializados de un GameObject por InstanceID. |
| EnvironmentScanner.GetProjectFiles | Unity | Lista directorios y archivos (sin .meta) bajo Assets/ respetando seguridad de ruta. |
| EnvironmentScanner.GetSceneHierarchy | Unity | Serializa la jerarquía de la escena activa a un modelo ligero. |
| EnvironmentScanner.TakeScreenshot | Unity | Captura una imagen de la vista de escena o cámara principal en PNG base64. |
| LogBuffer.(miembro) | Unity | Crea un buffer con capacidad máxima configurable. |
| LogBuffer.Drain | Unity | Drena y devuelve las entradas encoladas en orden FIFO. |
| LogBuffer.Enqueue | Unity | Encola una entrada y trunca si excede la capacidad. |
| LogWebSocketClient.(miembro) | Unity | Construye el cliente apuntando a la URL del servidor de logs. |
| LogWebSocketClient.(miembro) | Unity | Envía un mensaje JSON por WebSocket, gestionando reconexión y fallos. |
| LogWebSocketClient.CanSend | Unity | Indica si se puede intentar enviar en este momento (no en cooldown). |
| MCPLogger.Configure | Unity | Configura nivel mínimo, componente y URL de WebSocket opcional para envío. |
| MCPLogger.Log | Unity | Registra un evento con nivel, mensaje y metadatos opcionales. |
| MCPLogger.LogPerformance | Unity | Registra una métrica de rendimiento con etiqueta y duración en ms. |
| MCPLogger.SetCategory | Unity | Establece una categoría opcional para agrupar eventos. |
| MCPWebSocketClient.Disconnect | Unity | Cierra la conexión WebSocket de forma ordenada al salir del Editor. |
| MCPWebSocketClient.Initialize | Unity | Inicializa el cliente y establece la conexión WebSocket. Se invoca en el primer ciclo del Editor tras cargar scripts. |
| MCPWebSocketClient.OnMessageReceived | Unity | Callback de recepción de mensajes desde el Bridge. Encola el procesamiento en el hilo del Editor. |
| MCPWebSocketClient.SendResponse | Unity | Envía una respuesta de Unity al Bridge por WebSocket. |
| ScreenshotData.(miembro) | Unity | ContractResolver personalizado para ignorar propiedades que causan problemas con Unity. |
| UnityMessage.(miembro) | Unity | Modelo principal para las respuestas que se envían de vuelta al servidor MCP. |
| ValidationError.(miembro) | Unity | Human-readable message describing the issue. |
| ValidationError.(miembro) | Unity | Optional 1-based line number where the issue occurs. |
| ValidationError.(miembro) | Unity | Optional 1-based column number where the issue occurs. |
| ValidationError.(miembro) | Unity | Severity classification for this finding. |
| ValidationError.(miembro) | Unity | Optional code or identifier for the rule. |
| ValidationError.(miembro) | Unity | Constructs a new instance. |


| __init__._server_list_commands | Blender | Lista los nombres de todos los comandos registrados. |
| __init__._server_ping | Blender | Ping del servidor: útil para comprobación de salud. |
| analysis_metrics.mesh_stats | Blender | Compute mesh metrics: counts, bbox, surface/volume, quality, symmetry. |
| analysis_metrics.non_manifold_edges | Blender | Return the count of non-manifold edges for a mesh object. |
| mesh.from_points | Blender | Create a mesh object from raw vertices and optional faces/edges. |
| mesh.poly_extrude_from_outline | Blender | Create an extruded mesh from a 2D outline projected on a cardinal plane. |
| mesh.validate_and_heal | Blender | Validate mesh data, weld near-duplicate vertices, optionally fix normals, and dissolve degenerate geometry. |
| modeling.create_primitive | Blender | Create a mesh primitive without bpy.ops and link it to a collection. |
| modeling.echo | Blender | Echo parameters back to the caller. |
| modeling.get_version | Blender | Get Blender version, if available. |
| modeling_edit.bevel_edges | Blender | Bevel a set of edges using bmesh.ops.bevel. |
| modeling_edit.extrude_normal | Blender | Extrude selected faces along their normals by an amount. |
| modeling_edit.inset_region | Blender | Inset region for a set of faces using bmesh.ops.inset_region. |
| modifiers_core.add_boolean | Blender | Añade un modificador Boolean y configura su operand (objeto o colección). |
| modifiers_core.add_mirror | Blender | Añade un modificador Mirror al objeto de malla indicado. |
| modifiers_core.add_subsurf | Blender | Añade un modificador Subsurf al objeto con el nivel indicado. |
| modifiers_core.apply_all | Blender | Aplica todos los modificadores del objeto evaluando la malla resultante. |
| modifiers_core.apply_modifier | Blender | Apply a single modifier by name using evaluated mesh; avoids bpy.ops. |
| normals.recalc_normals | Blender | Recalculate normals outward or inward. |
| normals.recalc_selected | Blender | Recalcula normales para todos los objetos MESH seleccionados. |
| proc_arch.building | Blender | Procedurally generate a simple building shell with window cutouts. |
| proc_character._build_skeleton_mesh | Blender | Create a stick-figure skeleton as a graph of edges in +X half (mirror will complete). |
| proc_character.character_base | Blender | Generate a base character mesh from a seeded edge skeleton using Skin+Mirror+Subsurf. |
| proc_terrain.terrain | Blender | Procedurally generate a terrain as a grid displaced by fBm noise. |
| project.from_blueprint_plane_cmd | Blender | Map blueprint pixel coordinates (u,v) on an Empty Image back to a world-space point on the plane. |
| project.to_blueprint_plane_cmd | Blender | Project a world-space point to a blueprint plane (Empty Image) and return pixel coordinates. |
| reference._auto_otsu_threshold | Blender | Umbral automático (Otsu) sobre array normalizado [0..1]. |
| reference._compose_delta_world | Blender | Build world-space delta matrix that scales in empty-local XY by (sx,sy) around object's projected center and translates to image center. |
| reference._extract_binary_mask_any | Blender | Devuelve una máscara binaria uint8 (0/1) a partir de: |
| reference._extract_points2d | Blender | Toma una respuesta de outline_* y devuelve una lista válida de points2d o []. |
| reference._image_plane_dimensions | Blender | Compute plane dimensions (width,height) in empty local units based on display size and image aspect. |
| reference._outline_from_binary_mask | Blender | Reutiliza el pipeline existente: convertimos la máscara binaria en borde. |
| reference._project_bbox_on_empty_plane | Blender | Project object's mesh to empty local XY plane and return bbox (minx,miny,maxx,maxy) in empty local units. |
| reference._silhouette_bbox_from_image | Blender | Compute 2D bbox (u_min, v_min, u_max, v_max) in normalized [0,1] space for opaque pixels. |
| reference._sort_points_into_path | Blender | Ordena una nube de puntos 2D en un camino continuo usando el vecino más cercano. |
| reference.fit_bbox_to_blueprint | Blender | Fit object's projected 2D bbox to blueprint image silhouette bbox for the given view. |
| reference.outline_from_alpha | Blender | Extract main silhouette outline from image alpha via marching squares and simplify. |
| reference.outline_from_image | Blender | Generate outline from image, tolerant of missing alpha. |
| reference.reconstruct_from_alpha | Blender | Reconstruct an extruded mesh from an image's silhouette. |
| reference.reconstruct_from_image | Blender | NUEVO: igual que reconstruct_from_alpha pero tolerante a imágenes sin alpha. |
| reference.snap_silhouette_to_blueprint | Blender | Iteratively snap object's projected silhouette to the blueprint image edge for the given view. |
| reference_blueprints.blueprints_remove | Blender | Elimina los empties de referencia configurados y limpia el estado en escena. |
| reference_blueprints.blueprints_setup | Blender | Crea y configura tres imágenes de referencia (front/left/top) como empties. |
| reference_blueprints.blueprints_update | Blender | Actualiza una imagen de referencia existente (imagen, opacidad, visibilidad). |
| scene.clear | Blender | Clear the scene: remove all objects and purge orphaned meshes, images, materials and other data. |
| scene.remove_object | Blender | Remove a single object by name from the scene and purge its datablocks if orphaned. |
| selection_sets.selection_by_angle | Blender | Compute a face region grown by normal angle from seed faces and store it. |
| selection_sets.selection_restore | Blender | Restore a stored selection on the given object. |
| selection_sets.selection_store | Blender | Serialize current selection of the given object and domain into an object-local store. |
| topology.bevel_edges | Blender | Bevel selected edges using bmesh.ops.bevel. |
| topology.count_mesh_objects | Blender | Cuenta cuántos objetos de tipo MESH hay en la escena. |
| topology.ensure_object_mode | Blender | Garantiza que el modo activo sea OBJECT y lo devuelve. |
| topology.merge_by_distance | Blender | Remove doubles (merge by distance) across all verts. |
| topology.touch_active | Blender | Toca (escribe sin cambios efectivos) la malla activa para forzar actualización segura. |
| topology_cleanup.cleanup_basic | Blender | Topology cleanup: merge by distance, limited dissolve by angle, optional triangulate, and recalc normals. |
| CommandExecutionResult.(miembro) | Unity | Clase genérica para envolver listas y objetos. Originalmente para JsonUtility, se mantiene por ahora para compatibilidad con EnvironmentScanner. |
| EnvironmentScanner.(miembro) | Unity | (NUEVO MÉTODO) Extrae de forma segura las propiedades serializables de un componente de Unity. |
| ScreenshotData.(miembro) | Unity | ContractResolver personalizado para ignorar propiedades que causan problemas con Unity. |
| UnityMessage.(miembro) | Unity | Modelo principal para las respuestas que se envían de vuelta al servidor MCP. |
| ValidationError.(miembro) | Unity | Human-readable message describing the issue. |
| ValidationError.(miembro) | Unity | Optional 1-based line number where the issue occurs. |
| ValidationError.(miembro) | Unity | Optional 1-based column number where the issue occurs. |
| ValidationError.(miembro) | Unity | Severity classification for this finding. |
| ValidationError.(miembro) | Unity | Optional code or identifier for the rule. |
| ValidationError.(miembro) | Unity | Constructs a new instance. |


| (autogen) | Bridge | (autogen) |

## Detalle por herramienta

<!-- Secciones autogeneradas a continuación -->

