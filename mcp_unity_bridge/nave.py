# Blender 2.79 — Single mesh spaceship (human-like flow, bmesh only, mirrored X)
import bpy, bmesh, math
from mathutils import Vector

# ---------- helpers (no operators) ----------
def link_obj(obj):
    scn = bpy.context.scene
    if obj.name not in scn.objects:
        scn.objects.link(obj)

def new_mesh_obj(name, bm, loc=(0,0,0)):
    me = bpy.data.meshes.new(name + "Mesh")
    bm.to_mesh(me); me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    link_obj(ob)
    return ob

def set_smooth(obj, on=True):
    for p in obj.data.polygons:
        p.use_smooth = bool(on)

def width_profile(v):
    """
    Ancho medio-vista (0=cola, 1=nariz). Estrecha en la nariz, ensancha en zona de pods,
    parecido a la nave del sprite.
    """
    base = 0.42 + 0.55*(1.0 - v**1.4)           # afila al frente
    wing = 1.0 + 0.75*math.exp(-((v-0.42)/0.18)**2)  # barriga/alas laterales
    return base * wing

def remove_doubles(bm, dist=0.0005):
    try:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    except Exception:
        pass

# ---------- main build ----------
def build_spaceship_single_mesh():
    # limpia escena mínima (sin operators)
    scn = bpy.context.scene
    for o in list(scn.objects):
        try: scn.objects.unlink(o)
        except: pass
    for o in list(bpy.data.objects):
        try: bpy.data.objects.remove(o)
        except: pass
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)

    bm = bmesh.new()

    # 1) BASE: media malla (X >= 0) tipo “rejilla” con grosor
    nx, ny = 12, 30           # densidad: sube si quieres más detalle
    y_min, y_max = -0.95, 1.05
    half_thick = 0.12

    top = [[None]*(nx+1) for _ in range(ny+1)]
    bot = [[None]*(nx+1) for _ in range(ny+1)]

    for j in range(ny+1):
        v = j/float(ny)                      # 0..1 (cola→nariz)
        y = y_min + (y_max-y_min)*v
        w = width_profile(v)                 # semiancho local
        for i in range(nx+1):
            # malla SOLO en X >= 0
            u = (i/float(nx))                # 0..1 => 0..w
            x = u * w
            top[j][i] = bm.verts.new((x, y,  half_thick))
            bot[j][i] = bm.verts.new((x, y, -half_thick))

    # caras top/bottom (trianguladas)
    for j in range(ny):
        for i in range(nx):
            v00 = top[j][i];   v10 = top[j][i+1]
            v01 = top[j+1][i]; v11 = top[j+1][i+1]
            bm.faces.new((v00, v10, v11)); bm.faces.new((v00, v11, v01))
            v00 = bot[j][i];   v10 = bot[j][i+1]
            v01 = bot[j+1][i]; v11 = bot[j+1][i+1]
            bm.faces.new((v00, v11, v10)); bm.faces.new((v00, v01, v11))

    # costados exteriores (X = w) y trasera/delantera de la media malla
    # x = w (lateral derecho)
    for j in range(ny):
        a = top[j][nx]; b = top[j+1][nx]; c = bot[j+1][nx]; d = bot[j][nx]
        bm.faces.new((a, c, b)); bm.faces.new((a, d, c))
    # y = y_min (cola media-malla)
    for i in range(nx):
        a = top[0][i]; b = top[0][i+1]; c = bot[0][i+1]; d = bot[0][i]
        bm.faces.new((a, b, c)); bm.faces.new((a, c, d))
    # y = y_max (nariz media-malla)
    for i in range(nx):
        a = top[ny][i]; b = top[ny][i+1]; c = bot[ny][i+1]; d = bot[ny][i]
        bm.faces.new((a, c, b)); bm.faces.new((a, d, c))

    bm.normal_update()

    # 2) REFINO LOCAL — extrusiones y desplazamientos “a mano” en mitad de malla
    bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()

    # 2.a) Nariz afilada: extruye anillo delantero hacia +Y y estrecha X progresivamente
    front = [f for f in bm.faces if f.calc_center_bounds().y > 0.85]
    if front:
        ext = bmesh.ops.extrude_face_region(bm, geom=front)
        nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=nv, vec=(0.0, 0.18, 0.0))
        for v in nv:
            k = max(0.0, min(1.0, (v.co.y-0.85)/0.18))
            v.co.x *= (1.0 - 0.35*k)         # afila

    # 2.b) Pods laterales (zona media): extruye caras exteriores en +X y aplasta ligeramente en Z
    mid_side = [f for f in bm.faces
                if 0.15 < f.calc_center_bounds().y < 0.65 and f.calc_center_bounds().x > 0.30]
    if mid_side:
        ext = bmesh.ops.extrude_face_region(bm, geom=mid_side)
        nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=nv, vec=(0.18, 0.0, 0.0))
        for v in nv: v.co.z *= 0.88

    # 2.c) Toberas traseras: extruye parte trasera en -Y y crea hundido (inset + translate)
    tail = [f for f in bm.faces if f.calc_center_bounds().y < -0.80]
    if tail:
        ext = bmesh.ops.extrude_face_region(bm, geom=tail)
        nv  = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
        nf  = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMFace)]
        bmesh.ops.translate(bm, verts=nv, vec=(0.0, -0.16, 0.0))
        ins = bmesh.ops.inset_region(bm, faces=nf, thickness=0.02, depth=0.0)
        for fi in ins.get("faces", []):
            bmesh.ops.translate(bm, verts=fi.verts, vec=(0.0, -0.035, 0.0))

    # 2.d) Cabina integrada: levanta vértices en franja central superior
    canopy_verts = [v for v in bm.verts
                    if (v.co.y > 0.10 and v.co.y < 0.70 and v.co.x < 0.22 and v.co.z > 0.0)]
    for v in canopy_verts:
        t = max(0.0, 1.0 - abs((v.co.y - 0.38)/0.30))
        v.co.z += 0.16 * t

    # 2.e) Perfilado de fuselaje delantero (reduce X desde y=0.6 hasta nariz)
    for v in bm.verts:
        if v.co.y > 0.60:
            k = (v.co.y - 0.60) / (1.10 - 0.60)
            k = max(0.0, min(1.0, k))
            v.co.x *= (1.0 - 0.22*k)

    # 3) SIMETRÍA: duplica toda la malla y escálala con X=-1; suelda el costado en X≈0
    #   (queda un único objeto, una sola malla)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    dup = bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))
    new_verts = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.scale(bm, verts=new_verts, vec=(-1.0, 1.0, 1.0))
    remove_doubles(bm, dist=0.0008)
    bm.normal_update()

    # 4) OBJETO final (una sola malla) + suavizado
    ship = new_mesh_obj("Ship_Player_SingleMesh", bm)
    set_smooth(ship, True)

    print(">>> Ship single mesh (mirrored) built.")
    return {"object": ship.name}

res = build_spaceship_single_mesh()
print("RESULT:", res)
