"""Asigna un material a un objeto."""

try:  # pragma: no cover - dependencia de Blender
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None


def run(object_name, material_name):
    """Asigna ``material_name`` a ``object_name``."""
    if bpy is None:  # pragma: no cover
        print("bpy no disponible: assign_material es un stub")
        return True
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError("Objeto '{0}' no encontrado".format(object_name))
    mat = bpy.data.materials.get(material_name)
    if mat is None:
        mat = bpy.data.materials.new(material_name)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return mat.name
