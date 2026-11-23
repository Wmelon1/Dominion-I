# Dominion I - ProjectileKit (Blender 5.x): every round the game's weapons fire, at true size, plus ejected brass.
#   In Blender:  KIT_DIR = r'<project>\SourceArt\ProjectileKit'; exec(open(KIT_DIR + r'\source\pj_models.py').read()); build(); export(KIT_DIR + r'\fbx')
# Reuses the DroneKit geometry helpers. Metres; every projectile flies along -Y (Unity +Z) with its origin on the nose
# tip (the game draws it behind the tracer head); casings have their origin at their middle. Root empty 'Projectiles'.
import bpy, math, os, json
from mathutils import Vector, Matrix

KIT_DIR = globals().get('KIT_DIR')
DK = os.path.join(os.path.dirname(KIT_DIR), 'DroneKit')
ns = {'__name__': 'dk', 'KIT_DIR': DK}
_p = os.path.join(DK, 'source', 'dk_models.py')
exec(compile(open(_p, encoding='utf-8').read(), _p, 'exec'), ns)
Geo, to_object, get_coll, V = ns['Geo'], ns['to_object'], ns['get_coll'], ns['V']
MATS = ns['MATS']
# material -> (texture, tint, roughness, metallic, kind, uv)
PJ = {
    'PJ_Copper': ('PJCopper', 'ffffff', 0.3, 1.0, 'tex', 0.05),
    'PJ_Brass': ('PJBrass', 'ffffff', 0.3, 1.0, 'tex', 0.05),
    'PJ_Steel': ('PJMetal', 'a2a7ad', 0.35, 1.0, 'tex', 0.1),
    'PJ_Tungsten': ('PJMetal', '6a6e75', 0.3, 1.0, 'tex', 0.1),
    'PJ_Olive': ('PJPaint', '707a4a', 0.55, 0.0, 'tex', 0.22),
    'PJ_Grey': ('PJPaint', '9198a0', 0.5, 0.0, 'tex', 0.22),
    'PJ_Yellow': ('PJPaint', 'e8b52a', 0.5, 0.0, 'tex', 0.22),
    'PJ_Red': ('PJPaint', 'a32b25', 0.5, 0.0, 'tex', 0.22),
    'PJ_White': ('PJPaint', 'f2f3ee', 0.45, 0.0, 'tex', 0.22),
    'PJ_Black': ('PJPaint', '2c2d30', 0.6, 0.0, 'tex', 0.22),
    'PJ_Seeker': (None, '1a2028', 0.05, 0.5, 'flat', 1.0),
    'PJ_Tracer': (None, 'ff5a24', 0.3, 0.0, 'glow', 1.0),
    'PJ_RailGlow': (None, '5cf2ff', 0.3, 0.0, 'glow', 1.0),
}
MATS.update(PJ)
ns['TEX'] = os.path.join(KIT_DIR, 'textures')
for _m in list(PJ):
    _old = bpy.data.materials.get(_m)
    if _old: _old['dk'] = 0          # rebuild the material with its textures
AX = Matrix.Rotation(-math.pi / 2, 4, 'X')       # lathe axis (Z) -> along +Y: nose at y = 0, the body trailing behind


def shell(g, prof, mats, segs=24):
    g.lathe(prof, segs, mats[0], AX, mats=mats)


def fins(g, n, y0, chord, span, root_r, thick, mat, sweep=0.0, rot0=0.0):
    for k in range(n):
        a = rot0 + math.tau * k / n
        R = Matrix.Rotation(a, 4, 'Y')
        c = V(0, y0 + chord * 0.5, 0) + Vector((math.cos(a), 0, -math.sin(a))) * (root_r + span * 0.5)
        g.rbox((0, 0, 0), (span, chord, thick), mat, 0.0, 1,
               M=Matrix.Translation(c) @ R @ Matrix.Shear('XY', 4, (0, sweep)) if sweep else Matrix.Translation(c) @ R)


MODELS = {}


def model(fn):
    MODELS[fn.__name__] = fn
    return fn


@model
def Bullet_Rifle(g):          # 5.56 mm tracer bullet
    shell(g, [(0, 0.023), (0.0026, 0.023), (0.0028, 0.021), (0.0028, 0.012), (0.0022, 0.006), (0.0011, 0.002), (0, 0.0)],
          ['PJ_Tracer', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper'], 12)


@model
def Bullet_MG(g):             # 12.7 mm tracer round
    shell(g, [(0, 0.058), (0.0058, 0.058), (0.0065, 0.054), (0.0065, 0.03), (0.0052, 0.016), (0.0028, 0.005), (0, 0.0)],
          ['PJ_Tracer', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper', 'PJ_Red'], 14)


@model
def Shell_Autocannon(g):      # 30 mm HE-T: tracer base, copper driving band, yellow HE body, steel fuze
    shell(g, [(0, 0.17), (0.012, 0.17), (0.015, 0.165), (0.015, 0.125), (0.0158, 0.12), (0.0158, 0.105), (0.015, 0.1),
              (0.015, 0.05), (0.011, 0.026), (0.006, 0.01), (0.0035, 0.004), (0, 0.0)],
          ['PJ_Tracer', 'PJ_Steel', 'PJ_Steel', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper', 'PJ_Yellow', 'PJ_Yellow', 'PJ_Yellow', 'PJ_Steel', 'PJ_Steel'], 18)


@model
def Shell_Tank(g):            # 120 mm multipurpose round: tracer, steel base, driving band, olive body, ballistic cap
    shell(g, [(0, 0.95), (0.05, 0.95), (0.06, 0.93), (0.06, 0.82), (0.062, 0.8), (0.062, 0.76), (0.06, 0.75), (0.06, 0.38),
              (0.061, 0.37), (0.061, 0.34), (0.058, 0.32), (0.045, 0.2), (0.026, 0.09), (0.012, 0.025), (0, 0.0)],
          ['PJ_Tracer', 'PJ_Steel', 'PJ_Steel', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper', 'PJ_Olive', 'PJ_Yellow', 'PJ_Yellow',
           'PJ_Yellow', 'PJ_Olive', 'PJ_Olive', 'PJ_Black', 'PJ_Black'], 28)


@model
def Shell_Artillery(g):       # 155 mm HE: boat tail, driving band, olive body with the yellow HE ring, fuze
    shell(g, [(0, 0.7), (0.066, 0.7), (0.0775, 0.66), (0.0775, 0.62), (0.0792, 0.615), (0.0792, 0.585), (0.0775, 0.58),
              (0.0775, 0.33), (0.0778, 0.33), (0.0778, 0.29), (0.0775, 0.29), (0.062, 0.16), (0.04, 0.075), (0.022, 0.035),
              (0.018, 0.03), (0.016, 0.006), (0, 0.0)],
          ['PJ_Steel', 'PJ_Steel', 'PJ_Olive', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper', 'PJ_Olive', 'PJ_Yellow', 'PJ_Yellow',
           'PJ_Yellow', 'PJ_Olive', 'PJ_Olive', 'PJ_Olive', 'PJ_Steel', 'PJ_Steel', 'PJ_Steel'], 28)


@model
def Shell_Ship(g):            # 75 mm airship HE: grey with a red nose band, tracer
    shell(g, [(0, 0.42), (0.03, 0.42), (0.0375, 0.4), (0.0375, 0.36), (0.0385, 0.355), (0.0385, 0.33), (0.0375, 0.325),
              (0.0375, 0.17), (0.0378, 0.17), (0.0378, 0.14), (0.034, 0.1), (0.02, 0.04), (0.008, 0.01), (0, 0.0)],
          ['PJ_Tracer', 'PJ_Steel', 'PJ_Steel', 'PJ_Copper', 'PJ_Copper', 'PJ_Copper', 'PJ_Grey', 'PJ_Red', 'PJ_Red',
           'PJ_Grey', 'PJ_Grey', 'PJ_Steel', 'PJ_Steel'], 22)


@model
def Rail_Slug(g):             # Halberd rail-gun penetrator: tungsten rod, glowing armature rings, sharp tip
    shell(g, [(0, 0.55), (0.016, 0.55), (0.02, 0.54), (0.02, 0.06), (0.012, 0.025), (0, 0.0)],
          ['PJ_RailGlow', 'PJ_Tungsten', 'PJ_Tungsten', 'PJ_Tungsten', 'PJ_Tungsten'], 16)
    for y in (0.15, 0.3, 0.45):
        g.lathe([(0.0205, y), (0.026, y), (0.026, y + 0.02), (0.0205, y + 0.02)], 16, 'PJ_RailGlow', AX, closed=True)


@model
def Grenade_Rifle(g):         # anti-tank rifle grenade: shaped-charge head, tail tube, four fins
    shell(g, [(0, 0.36), (0.011, 0.36), (0.011, 0.19), (0.016, 0.175), (0.03, 0.15), (0.031, 0.08), (0.024, 0.04),
              (0.012, 0.012), (0.006, 0.004), (0, 0.0)],
          ['PJ_Olive', 'PJ_Black', 'PJ_Olive', 'PJ_Olive', 'PJ_Olive', 'PJ_Yellow', 'PJ_Olive', 'PJ_Steel', 'PJ_Steel'], 16)
    fins(g, 4, 0.28, 0.07, 0.022, 0.011, 0.0016, 'PJ_Black')


@model
def Missile_Pod(g):           # Thunderhead pod rocket: nozzle, olive motor, warhead, four tail fins
    shell(g, [(0, 1.3), (0.04, 1.3), (0.05, 1.27), (0.065, 1.24), (0.065, 0.5), (0.066, 0.49), (0.066, 0.46), (0.065, 0.45),
              (0.05, 0.22), (0.03, 0.08), (0.012, 0.02), (0, 0.0)],
          ['PJ_Black', 'PJ_Steel', 'PJ_Olive', 'PJ_Olive', 'PJ_Yellow', 'PJ_Yellow', 'PJ_Yellow', 'PJ_Olive', 'PJ_Olive', 'PJ_Steel', 'PJ_Steel'], 22)
    fins(g, 4, 1.06, 0.2, 0.1, 0.06, 0.004, 'PJ_Black', rot0=math.pi / 4)


@model
def Missile_AAM(g):           # Wraith air-to-air missile: white body, seeker dome, canards, delta tail fins
    shell(g, [(0, 2.9), (0.045, 2.9), (0.055, 2.86), (0.064, 2.82), (0.064, 0.3), (0.06, 0.2), (0.045, 0.1), (0.03, 0.05),
              (0, 0.035)],
          ['PJ_Black', 'PJ_Steel', 'PJ_White', 'PJ_White', 'PJ_White', 'PJ_White', 'PJ_Seeker', 'PJ_Seeker'], 24)
    g.lathe([(0.0645, 2.2), (0.066, 2.2), (0.066, 2.25), (0.0645, 2.25)], 24, 'PJ_Yellow', AX, closed=True)
    fins(g, 4, 2.45, 0.38, 0.18, 0.06, 0.005, 'PJ_White')
    fins(g, 4, 0.42, 0.16, 0.09, 0.06, 0.004, 'PJ_White')


@model
def Casing_Small(g):          # rifle / machine-gun brass (origin in the middle, mouth toward -Y)
    g.lathe([(0, 0.0225), (0.0048, 0.0225), (0.0048, 0.019), (0.0042, 0.018), (0.0048, 0.016), (0.0046, -0.012),
             (0.0032, -0.0175), (0.0032, -0.0225), (0.0025, -0.0225), (0.0025, -0.012)], 12, 'PJ_Brass', AX)


@model
def Casing_Medium(g):         # 30 mm autocannon brass
    g.lathe([(0, 0.085), (0.017, 0.085), (0.017, 0.078), (0.0155, 0.075), (0.0165, 0.07), (0.016, -0.06), (0.0145, -0.075),
             (0.0145, -0.085), (0.012, -0.085), (0.012, -0.06)], 18, 'PJ_Brass', AX)


def build():
    coll = get_coll('ProjectileKit')
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    root = bpy.data.objects.new('Projectiles', None)
    coll.objects.link(root)
    info = {}
    x = 0.0
    for name, fn in MODELS.items():
        g = Geo()
        fn(g)
        tris = g.tris()
        o = to_object(g, name, coll, root, (x, 0, 0.5))
        info[name] = tris
        x += 0.35
    root['pj_info'] = json.dumps(info)
    return info


def export(fbx_dir):
    os.makedirs(fbx_dir, exist_ok=True)
    vl = bpy.context.view_layer
    root = bpy.data.objects['Projectiles']
    for o in vl.objects:
        o.select_set(False)
    for o in [root] + list(root.children):
        o.hide_set(False)
        o.select_set(True)
    vl.objects.active = root
    bpy.ops.export_scene.fbx(filepath=os.path.join(fbx_dir, 'Projectiles.fbx'), use_selection=True, object_types={'EMPTY', 'MESH'},
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
                             bake_space_transform=True, use_mesh_modifiers=False, mesh_smooth_type='FACE', use_tspace=False,
                             use_triangles=True, add_leaf_bones=False, bake_anim=False, path_mode='STRIP', embed_textures=False,
                             use_custom_props=False)
    mats = {k: {'stem': v[0], 'tint': v[1], 'rough': v[2], 'metal': v[3], 'kind': v[4]} for k, v in PJ.items()}
    with open(os.path.join(fbx_dir, 'materials.json'), 'w') as f:
        json.dump(mats, f, indent=1)
