from __future__ import annotations

try:
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

from mcp_blender_addon.helpers import project as proj


def _setup_empty_image(name: str, w: int = 100, h: int = 100):
    img = bpy.data.images.new(name=name + "_img", width=w, height=h, alpha=True, float_buffer=False)
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = 'IMAGE'
    obj.empty_display_size = 1.0
    try:
        obj.empty_image_offset = (0.5, 0.5)
    except Exception:
        pass
    try:
        obj.data = img
    except Exception:
        pass
    (bpy.context.collection or bpy.context.scene.collection).objects.link(obj)
    return obj, img


def run() -> int:
    if bpy is None:
        print("test_projection must run inside Blender")
        return 0
    obj, img = _setup_empty_image("TestBP", 200, 100)

    # Center point should map to (w*0.5, h*0.5)
    center_world = obj.matrix_world @ Vector((0.0, 0.0, 0.0))
    u, v = proj.to_blueprint_plane(center_world, "front", obj)
    assert abs(u - 100.0) < 1e-4 and abs(v - 50.0) < 1e-4

    # Map back
    world_back = proj.from_blueprint_plane(u, v, "front", obj)
    assert (world_back - center_world).length < 1e-6

    print("test_projection OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

