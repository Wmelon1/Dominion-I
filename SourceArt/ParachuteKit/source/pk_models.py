# Dominion I - ParachuteKit (Blender 5.x): a round military troop parachute, sized for the soldiers.
#   In Blender:  KIT_DIR = r'<project>\SourceArt\ParachuteKit'; exec(open(KIT_DIR + r'\source\pk_models.py').read()); build(); export(KIT_DIR + r'\fbx')
# Reuses the DroneKit geometry helpers (lofts, lathes, tubes, rounded boxes, box-projected UVs).
# Metres, Z up, the jumper faces -Y (Unity +Z). Origin = the harness at the jumper's shoulders: Unity parents the
# parachute to the soldier at shoulder height. Root empty 'Parachute' with:
#   Parachute_Canopy   24-gore canopy (scalloped between the lines), hem band, apex vent, vent lines   (inflates in Unity)
#   Parachute_Rigging  24 suspension lines to 4 risers, riser webbing, connector links, harness pack
import bpy, math, os, json
from mathutils import Vector, Matrix

KIT_DIR = globals().get('KIT_DIR')
DK = os.path.join(os.path.dirname(KIT_DIR), 'DroneKit')
ns = {'__name__': 'dk', 'KIT_DIR': DK}
_p = os.path.join(DK, 'source', 'dk_models.py')
exec(compile(open(_p, encoding='utf-8').read(), _p, 'exec'), ns)
Geo, to_object, get_coll, V = ns['Geo'], ns['to_object'], ns['get_coll'], ns['V']
MATS = ns['MATS']
TEX = os.path.join(KIT_DIR, 'textures')
ns['TEX'] = TEX
TAU = math.tau
# material -> (texture stem, tint, roughness, metallic, kind, uv metres per tile)
PK = {
    'PK_Canopy': ('Ripstop', 'a7ad86', 0.6, 0.0, 'tex', 2.0),
    'PK_CanopyHem': ('Ripstop', '6b7154', 0.6, 0.0, 'tex', 2.0),
    'PK_Lines': (None, 'd8d6cc', 0.7, 0.0, 'flat', 1.0),
    'PK_Webbing': ('Webbing', '7a7d5c', 0.8, 0.0, 'tex', 0.25),
    'PK_Pack': ('Webbing', '585c40', 0.85, 0.0, 'tex', 0.35),
    'PK_Metal': (None, '8e9196', 0.35, 1.0, 'flat', 1.0),
}
MATS.update(PK)

GORES = 24
R_SKIRT, Z_SKIRT, Z_APEX = 3.7, 5.2, 7.6


def canopy_point(theta, u):
    """u: 0 = vent edge, 1 = skirt. Inflated profile, each gore bulging outward between its two lines."""
    phi = 0.12 + u * (math.pi * 0.5 - 0.12) * 0.98
    r = 3.9 * math.sin(phi)
    z = Z_SKIRT + (Z_APEX - Z_SKIRT) * math.cos(phi) * 1.05 - 0.25 * u * u
    g = abs(math.sin(theta * GORES / 2))                    # 0 on a line, 1 mid-gore
    r *= 1.0 + 0.045 * g * (0.4 + 0.6 * u)
    z += 0.12 * g * (1 - u)                                 # the cloth domes up between lines near the top
    if u > 0.97:
        r -= 0.08 * g                                       # scalloped hem
    return V(r * math.cos(theta), r * math.sin(theta), z)


def build():
    coll = get_coll('ParachuteKit')
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    root = bpy.data.objects.new('Parachute', None)
    coll.objects.link(root)
    seg = GORES * 4
    # ---- canopy shell (a thin double layer so it shades right from below and above)
    c = Geo()
    us = [i / 14 for i in range(15)]
    rings = [[canopy_point(TAU * k / seg, u) for k in range(seg)] for u in us]
    mats = ['PK_Canopy'] * 12 + ['PK_CanopyHem'] * 2
    c.loft(rings, 'PK_Canopy', cap0=False, cap1=False, mats=mats)
    inner = [[p - Vector((p.x, p.y, 0)).normalized() * 0.02 + V(0, 0, -0.02) for p in ring] for ring in rings]
    c.loft(inner, 'PK_Canopy', cap0=False, cap1=False, mats=mats)
    # apex vent band and vent lines across the hole
    vent = [[canopy_point(TAU * k / seg, 0.0) + V(0, 0, dz) for k in range(seg)] for dz in (0.0, 0.06)]
    c.loft(vent, 'PK_CanopyHem', cap0=False, cap1=False)
    for k in range(0, GORES, 2):
        a = canopy_point(TAU * k / GORES, 0.0)
        b = canopy_point(TAU * (k + GORES // 2) / GORES, 0.0)
        c.tube([a, (a + b) * 0.5 + V(0, 0, -0.05), b], 0.008, 'PK_Lines', 4)
    to_object(c, 'Parachute_Canopy', coll, root)

    # ---- rigging: lines from each line attachment on the hem to the four risers, risers to the harness
    r = Geo()
    riser_tips = [V(sx * 0.22, sy * 0.12, 1.15) for sx in (-1, 1) for sy in (-1, 1)]
    for k in range(GORES):
        th = TAU * k / GORES
        top = canopy_point(th, 1.0)
        tip = min(riser_tips, key=lambda t: (Vector((t.x, t.y)) - Vector((math.cos(th), math.sin(th)))).length)
        # radial seam tape down the gore line
        r.tube([canopy_point(th, u) + Vector((math.cos(th), math.sin(th), 0)) * 0.012 for u in (0.0, 0.35, 0.7, 1.0)], 0.012, 'PK_CanopyHem', 4, cap=False)
        r.tube([top, top.lerp(tip, 0.5) + V(0, 0, 0.05), tip], 0.007, 'PK_Lines', 4)
    for t in riser_tips:
        sh = V(math.copysign(0.19, t.x), math.copysign(0.05, t.y), 0.02)
        d = (t - sh)
        mid = sh.lerp(t, 0.5)
        ang = math.atan2(d.x, d.z)
        r.rbox(tuple(mid), (0.045, 0.012, d.length), 'PK_Webbing', 0.003, 1,
               M=Matrix.Translation(mid) @ Matrix.Rotation(-ang, 4, 'Y') @ Matrix.Rotation(math.atan2(-d.y, math.hypot(d.x, d.z)), 4, 'X') @ Matrix.Translation(-mid))
        r.lathe([(0, -0.03), (0.022, -0.03), (0.024, 0.0), (0.022, 0.03), (0, 0.03)], 10, 'PK_Metal', Matrix.Translation(t))
    # harness: shoulder straps and the deployment-bag pack on the back (+Y), reserve on the chest
    for sx in (-1, 1):
        r.rbox((sx * 0.13, 0.0, -0.22), (0.05, 0.26, 0.5), 'PK_Webbing', 0.01, 1)
    r.rbox((0, 0.2, -0.3), (0.36, 0.16, 0.5), 'PK_Pack', 0.04, 2)
    r.rbox((0, -0.17, -0.42), (0.3, 0.1, 0.2), 'PK_Pack', 0.03, 2)
    to_object(r, 'Parachute_Rigging', coll, root)
    tris = sum(len(p.vertices) - 2 for o in root.children for p in o.data.polygons)
    root['pk_info'] = json.dumps({'tris': tris, 'diameter': 2 * R_SKIRT, 'height': Z_APEX})
    return root, tris


def export(fbx_dir):
    os.makedirs(fbx_dir, exist_ok=True)
    vl = bpy.context.view_layer
    root = bpy.data.objects['Parachute']
    for o in vl.objects:
        o.select_set(False)
    for o in [root] + list(root.children_recursive):
        o.hide_set(False)
        o.select_set(True)
    vl.objects.active = root
    bpy.ops.export_scene.fbx(filepath=os.path.join(fbx_dir, 'Parachute.fbx'), use_selection=True, object_types={'EMPTY', 'MESH'},
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
                             bake_space_transform=True, use_mesh_modifiers=False, mesh_smooth_type='FACE', use_tspace=False,
                             use_triangles=True, add_leaf_bones=False, bake_anim=False, path_mode='STRIP', embed_textures=False,
                             use_custom_props=False)
    mats = {k: {'stem': v[0], 'tint': v[1], 'rough': v[2], 'metal': v[3], 'kind': v[4]} for k, v in PK.items()}
    with open(os.path.join(fbx_dir, 'materials.json'), 'w') as f:
        json.dump(mats, f, indent=1)
