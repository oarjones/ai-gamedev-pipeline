"""Extrude una malla a lo largo del eje Z."""

try:  # pragma: no cover - dependencia de Blender
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None


def run(object_name, distance=1.0):
    """Extrude la malla ``object_name`` una distancia dada."""
    if bpy is None:  # pragma: no cover
        print("bpy no disponible: extrude_mesh es un stub")
        return True
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError("Objeto '{0}' no encontrado".format(object_name))
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, 0, distance)}
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj.name
