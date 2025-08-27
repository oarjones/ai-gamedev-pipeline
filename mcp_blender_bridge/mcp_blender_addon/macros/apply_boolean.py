"""Aplica un modificador booleano entre dos objetos."""

try:  # pragma: no cover - dependencia de Blender
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None


def run(target_name, cutter_name, operation="UNION"):
    """Aplica un booleano del tipo ``operation``."""
    if bpy is None:  # pragma: no cover
        print("bpy no disponible: apply_boolean es un stub")
        return True
    target = bpy.data.objects.get(target_name)
    cutter = bpy.data.objects.get(cutter_name)
    if target is None or cutter is None:
        raise ValueError("Objetos especificados no encontrados")
    modifier = target.modifiers.new(name="Boolean", type="BOOLEAN")
    modifier.object = cutter
    modifier.operation = operation
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    return target.name
