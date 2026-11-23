# Dominion I - export a kit .blend to Unity FBX (+ JSON metadata), headless:
#   blender -b <Kit>.blend --python blender_export.py -- <KitName> <ArtOutDir> <KitSourceRoot>
# Vehicles are exported rig + meshes (blend shapes kept, no clips: they are driven by script in Unity).
# Soldiers get 16 new 8-direction strafe clips (Walk_*/Run_*) on top of Idle/Walk/Run/Crouch/Rifle_Aim.
import bpy, sys, os, json, math
from mathutils import Vector, Matrix, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:]
KIT, OUT, ROOT = argv[0], argv[1], argv[2]
TAU = math.tau
SUB = {'TankKit': 'Tanks', 'AircraftKit': 'Aircraft', 'TransportKit': 'Transports', 'SoldierKit': 'Soldiers', 'AirshipKit': 'Airships', 'SkyshipKit': 'Skyships'}[KIT]
PREFIX = {'TankKit': 'Tank_', 'AircraftKit': 'Aircraft_', 'TransportKit': 'Vehicle_', 'SoldierKit': 'Soldier_', 'AirshipKit': 'Airship_', 'SkyshipKit': 'Skyship_'}[KIT]
DST = os.path.join(OUT, SUB)
os.makedirs(DST, exist_ok=True)


def reset(rig):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def export_fbx(rig, path, anim, deform_only):
    vl = bpy.context.view_layer
    old = rig.location.copy()
    rig.location = (0, 0, 0)
    ad = rig.animation_data
    if ad:
        ad.action = None
    reset(rig)
    vl.update()
    for o in vl.objects:
        o.select_set(False)
    for o in [rig] + list(rig.children):
        o.hide_viewport = False
        o.hide_set(False)
        o.select_set(True)
    vl.objects.active = rig
    muted = []
    if anim and ad:
        for tr in ad.nla_tracks:
            muted.append((tr, tr.mute))
            tr.mute = False
    try:
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'}, apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_space_transform=False,
            use_mesh_modifiers=False, mesh_smooth_type='FACE', use_tspace=False,
            use_armature_deform_only=deform_only, add_leaf_bones=False, primary_bone_axis='Y',
            secondary_bone_axis='X', armature_nodetype='NULL', bake_anim=anim, bake_anim_use_all_bones=True,
            bake_anim_use_nla_strips=True, bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
            bake_anim_step=1.0, bake_anim_simplify_factor=0.0, path_mode='STRIP', embed_textures=False,
            use_custom_props=False)
    finally:
        for tr, m in muted:
            tr.mute = m
        rig.location = old


def rig_props(rig):
    out = {}
    for k in rig.keys():
        v = rig[k]
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                pass
        elif hasattr(v, 'to_dict'):
            v = v.to_dict()
        elif hasattr(v, 'to_list'):
            v = v.to_list()
        out[k] = v
    return out


def material_info(mats):
    info = {}
    for m in mats:
        if m is None or m.name in info:
            continue
        d = {'textures': {}}
        nt = m.node_tree
        if nt:
            for n in nt.nodes:
                if n.type == 'TEX_IMAGE' and n.image:
                    nm = n.image.name
                    role = 'ORM' if nm.endswith('_ORM') else 'Normal' if nm.endswith('_Normal') else \
                        'BaseColor' if nm.endswith('_BaseColor') else 'Image'
                    d['textures'][role] = nm
            b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if b:
                d['color'] = list(b.inputs['Base Color'].default_value)[:3]
                d['roughness'] = b.inputs['Roughness'].default_value
                d['metallic'] = b.inputs['Metallic'].default_value
                d['alpha'] = b.inputs['Alpha'].default_value
                d['emission'] = b.inputs['Emission Strength'].default_value
        d['blend'] = m.surface_render_method
        info[m.name] = d
    return info


# ------------------------------------------------------------------ soldier strafe clips
def load_soldier_lib():
    g = {'__name__': 'sd', 'KIT_DIR': os.path.join(ROOT, 'TankKit'), 'AIR_DIR': os.path.join(ROOT, 'AircraftKit'),
         'AS_DIR': os.path.join(ROOT, 'AirshipKit'), 'SD_DIR': os.path.join(ROOT, 'SoldierKit')}
    for rel in ('TankKit/source/tk_core.py', 'TankKit/source/tk_tank.py', 'AircraftKit/source/ak_core.py',
                'AirshipKit/source/as_tex.py', 'AirshipKit/source/as_build.py', 'SoldierKit/source/sd_build.py'):
        p = os.path.join(ROOT, rel)
        exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), g)
    return g


DIRS = [('F', 0), ('FR', 45), ('R', 90), ('BR', 135), ('B', 180), ('BL', 225), ('L', 270), ('FL', 315)]
WALK_N, RUN_N, FPS = 26, 16, 24.0


def strafe_pose(g, t, phi, run):
    """8-direction locomotion. phi: 0 = forward, 90 = right. Legs never cross on side steps (step-together)."""
    ph = TAU * t
    s = math.sin(ph)
    c = math.cos(ph)
    f = math.radians(phi)
    fwd, lat = math.cos(f), math.sin(f)
    if abs(fwd) < 1e-6:
        fwd = 0.0
    if abs(lat) < 1e-6:
        lat = 0.0
    sg = 1.0 if fwd >= 0 else -1.0
    As = (45.0 if run else 30.0) * abs(fwd) * (0.8 if fwd < 0 else 1.0)
    Al = (40.0 if run else 32.0) * abs(lat)
    K = 75.0 if run else 40.0
    p = g['base_pose'](70 if run else 76, 85 if run else 15)
    spread = 0.0 if lat == 0 else ((1 - s) / 2 if lat > 0 else (1 + s) / 2)
    p['LeftUpperLeg'] = [('x', -sg * As * s), ('y', -Al * spread)]
    p['RightUpperLeg'] = [('x', sg * As * s), ('y', Al * spread)]
    kl = 6 + K * max(0.0, math.sin(ph + 1.9)) ** 1.5
    kr = 6 + K * max(0.0, math.sin(ph + 1.9 + math.pi)) ** 1.5
    p['LeftLowerLeg'] = [('x', kl)]
    p['RightLowerLeg'] = [('x', kr)]
    toe = (10 if run else 4) * (0.5 + 0.5 * abs(fwd))
    p['LeftFoot'] = [('x', -8 * s * fwd - 0.25 * kl + toe), ('y', Al * spread)]
    p['RightFoot'] = [('x', 8 * s * fwd - 0.25 * kr + toe), ('y', -Al * spread)]
    sw = (38 if run else 18) * abs(fwd) * (0.45 if fwd < 0 else 1.0)
    p['LeftUpperArm'] = [('y', 70 if run else 76), ('x', sw * s * sg)]
    p['RightUpperArm'] = [('y', -(70 if run else 76)), ('x', -sw * s * sg)]
    lean = (12 if run else 3) * fwd
    lean_l = (5 if run else 2) * lat
    p['Spine'] = [('x', lean * 0.5), ('y', -lean_l * 0.5), ('z', -(6 if run else 4) * s * abs(fwd))]
    p['Chest'] = [('x', lean * 0.5), ('y', -lean_l * 0.5), ('z', -(4 if run else 2) * s * abs(fwd))]
    p['Hips'] = [('z', (7 if run else 5) * s * abs(fwd)), ('y', (3 if run else 2) * c * abs(fwd) + 3 * (spread - 0.5) * lat)]
    p['Head'] = [('x', -lean * 0.6), ('y', lean_l * 0.8)]
    bob = (0.05 if run else 0.025)
    p['_hips'] = (0.012 * c * abs(fwd) - 0.02 * lat * (spread - 0.5), 0, -bob * (0.5 - 0.5 * math.cos(2 * ph)))
    return p, As * (1 if sg > 0 else -1), Al * (1 if lat >= 0 else -1)


def add_strafe_clips(g, rig, tname, P):
    reset_pose, apply_pose = g['reset_pose'], g['apply_pose']
    ad = rig.animation_data_create()
    for tr in list(ad.nla_tracks):
        if tr.name.startswith(('Walk_', 'Run_')):
            ad.nla_tracks.remove(tr)
    deform = [b.name for b in rig.data.bones if b.use_deform and b.name not in ('Root', 'Muzzle')]
    d = Vector((0.0, -0.55, -0.83)).normalized()
    up = Vector((0, 0, 1))
    zax = (up - d * up.dot(d)).normalized()
    R = Matrix((d.cross(zax), d, zax)).transposed().to_4x4()
    L = P['hip_z'] - P['ankle']
    vel = {}
    for run in (False, True):
        n = RUN_N if run else WALK_N
        for tag, phi in DIRS:
            name = f"{'Run' if run else 'Walk'}_{tag}"
            old_act = bpy.data.actions.get(f'{tname}_{name}')
            if old_act:
                bpy.data.actions.remove(old_act)
            act = bpy.data.actions.new(f'{tname}_{name}')
            act.use_fake_user = True
            ad.action = act
            As = Al = 0.0
            for fr in range(1, n + 2, 2):
                reset_pose(rig)
                pose, As, Al = strafe_pose(g, (fr - 1) / n, phi, run)
                apply_pose(rig, pose)
                bpy.context.view_layer.update()
                wbp = rig.pose.bones['WeaponR']
                wbp.matrix = Matrix.Translation(wbp.matrix.translation) @ R
                bpy.context.view_layer.update()
                for bn in deform:
                    pb = rig.pose.bones[bn]
                    pb.keyframe_insert('rotation_quaternion', frame=fr)
                    if bn in ('Hips', 'WeaponR'):
                        pb.keyframe_insert('location', frame=fr)
            act.use_frame_range = True
            act.frame_start, act.frame_end = 1, n + 1
            slot = ad.action_slot
            ad.action = None
            tr = ad.nla_tracks.new()
            tr.name = name
            st = tr.strips.new(name, 1, act)
            if slot is not None and getattr(st, 'action_slot', None) is None:
                st.action_slot = slot
            tr.mute = True
            T = n / FPS
            vz = math.copysign(4 * L * math.sin(math.radians(abs(As))), As) / T
            vx = math.copysign(2 * L * math.sin(math.radians(abs(Al))), Al) / T
            vel[name] = [round(vx, 4), round(vz, 4)]
    reset_pose(rig)
    return vel


# ------------------------------------------------------------------ soldier death clip
DEATH_KEYS = [  # (t, {bone: {axis: deg}}, hips offset)
    (0.0, {'LeftUpperArm': {'y': 76}, 'RightUpperArm': {'y': -76}, 'LeftLowerArm': {'z': -12}, 'RightLowerArm': {'z': 12}}, (0, 0, 0)),
    (0.22, {'Spine': {'x': 18}, 'Chest': {'x': 10}, 'Head': {'x': 18}, 'LeftUpperLeg': {'x': -20}, 'RightUpperLeg': {'x': -28},
            'LeftLowerLeg': {'x': 50}, 'RightLowerLeg': {'x': 62}, 'LeftFoot': {'x': -22}, 'RightFoot': {'x': -25},
            'LeftUpperArm': {'y': 60, 'x': -25}, 'RightUpperArm': {'y': -60, 'x': -20}, 'LeftLowerArm': {'z': -30}, 'RightLowerArm': {'z': 30}},
     (0, 0.05, -0.28)),
    (0.5, {'Hips': {'x': -40}, 'Spine': {'x': 8}, 'Head': {'x': 6}, 'LeftUpperLeg': {'x': -45}, 'RightUpperLeg': {'x': -35},
           'LeftLowerLeg': {'x': 70}, 'RightLowerLeg': {'x': 55}, 'LeftFoot': {'x': -10}, 'RightFoot': {'x': -10},
           'LeftUpperArm': {'y': 30, 'x': -50}, 'RightUpperArm': {'y': -35, 'x': -45}, 'LeftLowerArm': {'z': -40}, 'RightLowerArm': {'z': 35}},
     (0.02, 0.25, -0.55)),
    (0.78, {'Hips': {'x': -86}, 'Spine': {'x': -4}, 'Head': {'x': -8, 'z': 12}, 'LeftUpperLeg': {'x': -30}, 'RightUpperLeg': {'x': -12},
            'LeftLowerLeg': {'x': 45}, 'RightLowerLeg': {'x': 18}, 'LeftFoot': {'x': 15}, 'RightFoot': {'x': 20},
            'LeftUpperArm': {'y': 20, 'x': -10}, 'RightUpperArm': {'y': -15, 'x': -5}, 'LeftLowerArm': {'z': -25}, 'RightLowerArm': {'z': 25}},
     (0.03, 0.55, -0.80)),
    (1.0, {'Hips': {'x': -88}, 'Spine': {'x': -2}, 'Head': {'x': -6, 'z': 16}, 'LeftUpperLeg': {'x': -24}, 'RightUpperLeg': {'x': -8},
           'LeftLowerLeg': {'x': 38}, 'RightLowerLeg': {'x': 12}, 'LeftFoot': {'x': 18}, 'RightFoot': {'x': 22},
           'LeftUpperArm': {'y': 14, 'x': -8}, 'RightUpperArm': {'y': -10, 'x': -4}, 'LeftLowerArm': {'z': -20}, 'RightLowerArm': {'z': 20}},
     (0.03, 0.56, -0.84)),
]


def add_death_clip(g, rig, tname):
    reset_pose, apply_pose = g['reset_pose'], g['apply_pose']
    ad = rig.animation_data_create()
    for tr in list(ad.nla_tracks):
        if tr.name == 'Death':
            ad.nla_tracks.remove(tr)
    old = bpy.data.actions.get(f'{tname}_Death')
    if old:
        bpy.data.actions.remove(old)
    deform = [b.name for b in rig.data.bones if b.use_deform and b.name not in ('Root', 'Muzzle')]
    n = 36
    act = bpy.data.actions.new(f'{tname}_Death')
    act.use_fake_user = True
    ad.action = act
    for fr in range(1, n + 2):
        t = (fr - 1) / n
        i = 0
        while i < len(DEATH_KEYS) - 2 and t > DEATH_KEYS[i + 1][0]:
            i += 1
        (t0, b0, h0), (t1, b1, h1) = DEATH_KEYS[i], DEATH_KEYS[i + 1]
        k = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        k = k * k * (3 - 2 * k)
        pose = {}
        for bn in set(b0) | set(b1):
            a0, a1 = b0.get(bn, {}), b1.get(bn, {})
            rots = []
            for ax in ('x', 'y', 'z'):
                v0, v1 = a0.get(ax, 0.0), a1.get(ax, 0.0)
                if v0 or v1:
                    rots.append((ax, v0 + (v1 - v0) * k))
            pose[bn] = rots
        pose['_hips'] = tuple(h0[j] + (h1[j] - h0[j]) * k for j in range(3))
        g['finger_curl'](pose, 'Right', 45, 40, 25)
        reset_pose(rig)
        apply_pose(rig, pose)
        bpy.context.view_layer.update()
        for bn in deform:
            pb = rig.pose.bones[bn]
            pb.keyframe_insert('rotation_quaternion', frame=fr)
            if bn in ('Hips', 'WeaponR'):
                pb.keyframe_insert('location', frame=fr)
    act.use_frame_range = True
    act.frame_start, act.frame_end = 1, n + 1
    slot = ad.action_slot
    ad.action = None
    tr = ad.nla_tracks.new()
    tr.name = 'Death'
    st = tr.strips.new('Death', 1, act)
    if slot is not None and getattr(st, 'action_slot', None) is None:
        st.action_slot = slot
    tr.mute = True
    reset_pose(rig)


# ------------------------------------------------------------------ main
rigs = [o for o in bpy.data.objects if o.type == 'ARMATURE' and not o.name.startswith('WGT')]
report = {}
all_mats = []
lib = load_soldier_lib() if KIT == 'SoldierKit' else None
for rig in sorted(rigs, key=lambda r: r.name):
    base = rig.name[:-4] if rig.name.endswith('_Rig') else rig.name
    name = PREFIX + base
    meta = {'name': name, 'rig': rig.name, 'props': rig_props(rig),
            'meshes': [c.name for c in rig.children if c.type == 'MESH'],
            'bones': [[b.name, b.parent.name if b.parent else '', b.use_deform] for b in rig.data.bones]}
    for c in rig.children:
        if c.type == 'MESH':
            all_mats += list(c.data.materials)
    if KIT == 'SoldierKit':
        P = lib['MALE'] if base == 'Male' else lib['FEMALE']
        meta['clip_velocity'] = add_strafe_clips(lib, rig, base, P)
        add_death_clip(lib, rig, base)
        meta['clips'] = [t.name for t in rig.animation_data.nla_tracks]
        export_fbx(rig, os.path.join(DST, name + '.fbx'), True, True)
    else:
        export_fbx(rig, os.path.join(DST, name + '.fbx'), False, False)
    with open(os.path.join(DST, name + '.json'), 'w') as fh:
        json.dump(meta, fh, indent=1)
    report[name] = len(meta['bones'])
with open(os.path.join(DST, 'materials.json'), 'w') as fh:
    json.dump(material_info(all_mats), fh, indent=1)
if KIT == 'SoldierKit':
    bpy.ops.wm.save_mainfile()   # keep the new strafe clips in the source file
print('DOMINION_EXPORT', KIT, json.dumps(report))
