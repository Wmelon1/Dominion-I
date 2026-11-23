# Adds melee clips to the mechs in SourceArt/MechKit/MechKit.blend and re-exports the FBX files:
#   all mechs : Stomp       (right-leg ground pound, impact at 55 %)
#   Halberd   : Slash       (left arm-blade backhand, blade extends, impact at 42 %)
#   Aegis     : ShieldBash  (tower-shield ram with a lunge, impact at 38 %)
#   Thunderhead: Punch      (left jab-cross; the right arm is the gatling, impact at 42 %)
# Headless:  blender -b SourceArt/MechKit/MechKit.blend --python Tools/mech_melee_clips.py -- <SourceArtDir> <ArtMechsDir>
import bpy, sys, os, math, shutil
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
SA, OUT = argv[0], argv[1]
g = {'__name__': 'mk', 'KIT_DIR': os.path.join(SA, 'TankKit'), 'AIR_DIR': os.path.join(SA, 'AircraftKit'),
     'AS_DIR': os.path.join(SA, 'AirshipKit'), 'SD_DIR': os.path.join(SA, 'SoldierKit'), 'MK_DIR': os.path.join(SA, 'MechKit')}
for rel in ('TankKit/source/tk_core.py', 'TankKit/source/tk_tank.py', 'AircraftKit/source/ak_core.py',
            'AirshipKit/source/as_tex.py', 'AirshipKit/source/as_build.py', 'SoldierKit/source/sd_build.py',
            'MechKit/source/mk_build.py'):
    p = os.path.join(SA, rel)
    exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), g)

# Blender frame: mech faces -Y, its left is +X, up is +Z.  Arms are posed by direction (upper arm, forearm).
BASE_ARMS = {'Left': ((0.41, 0.0, -0.91), (0.40, -0.12, -0.91)), 'Right': ((-0.41, 0.0, -0.91), (-0.40, -0.12, -0.91))}


def key(t, body=None, hips=(0, 0, 0), arms=None, rolls=None, blade=0.0):
    a = dict(BASE_ARMS)
    a.update(arms or {})
    return dict(t=t, body=body or {}, hips=hips, arms=a, rolls=rolls or {}, blade=blade)


def base(t):
    return key(t)


CLIPS = {
    'Stomp': (32, [
        base(0.0),
        key(0.35, {'RightUpperLeg': (-75, 0, 0), 'RightLowerLeg': (85, 0, 0), 'RightFoot': (-5, 0, 0),
                   'LeftUpperLeg': (-8, 0, 0), 'LeftLowerLeg': (14, 0, 0), 'LeftFoot': (-6, 0, 0),
                   'Spine': (-4, 0, 0), 'Hips': (0, 4, 0), 'Head': (6, 0, 0)}, (0.08, 0.05, 0.0),
            {'Left': ((0.8, -0.1, -0.55), (0.85, -0.25, -0.45)), 'Right': ((-0.8, -0.1, -0.55), (-0.85, -0.25, -0.45))}),
        key(0.45, {'RightUpperLeg': (-84, 0, 0), 'RightLowerLeg': (88, 0, 0), 'RightFoot': (-5, 0, 0),
                   'LeftUpperLeg': (-8, 0, 0), 'LeftLowerLeg': (16, 0, 0), 'LeftFoot': (-7, 0, 0),
                   'Spine': (-6, 0, 0), 'Hips': (0, 5, 0), 'Head': (8, 0, 0)}, (0.1, 0.05, 0.05),
            {'Left': ((0.85, -0.1, -0.45), (0.9, -0.25, -0.35)), 'Right': ((-0.85, -0.1, -0.45), (-0.9, -0.25, -0.35))}),
        key(0.55, {'RightUpperLeg': (-14, 0, 0), 'RightLowerLeg': (22, 0, 0), 'RightFoot': (-6, 0, 0),
                   'LeftUpperLeg': (-16, 0, 0), 'LeftLowerLeg': (34, 0, 0), 'LeftFoot': (-16, 0, 0),
                   'Spine': (14, 0, 0), 'Chest': (6, 0, 0), 'Head': (-10, 0, 0)}, (0.0, 0.0, -0.45),
            {'Left': ((0.5, -0.4, -0.78), (0.45, -0.55, -0.7)), 'Right': ((-0.5, -0.4, -0.78), (-0.45, -0.55, -0.7))}),
        key(0.7, {'RightUpperLeg': (-14, 0, 0), 'RightLowerLeg': (22, 0, 0), 'RightFoot': (-6, 0, 0),
                  'LeftUpperLeg': (-16, 0, 0), 'LeftLowerLeg': (34, 0, 0), 'LeftFoot': (-16, 0, 0),
                  'Spine': (12, 0, 0), 'Chest': (5, 0, 0), 'Head': (-8, 0, 0)}, (0.0, 0.0, -0.42),
            {'Left': ((0.5, -0.4, -0.78), (0.45, -0.55, -0.7)), 'Right': ((-0.5, -0.4, -0.78), (-0.45, -0.55, -0.7))}),
        base(1.0),
    ]),
    'Punch': (24, [
        base(0.0),
        key(0.3, {'Spine': (2, 0, 14), 'Chest': (0, 0, 8), 'Hips': (0, 0, 6),
                  'LeftUpperLeg': (8, 0, 0), 'RightUpperLeg': (-10, 0, 0), 'LeftLowerLeg': (12, 0, 0), 'RightLowerLeg': (12, 0, 0)},
            (0, 0.15, -0.12),
            {'Left': ((0.3, 0.6, -0.75), (-0.1, -0.6, 0.8)), 'Right': ((-0.5, 0.15, -0.85), (-0.45, -0.2, -0.85))}),
        key(0.42, {'Spine': (8, 0, -16), 'Chest': (2, 0, -10), 'Hips': (0, 0, -8),
                   'LeftUpperLeg': (-14, 0, 0), 'RightUpperLeg': (10, 0, 0), 'LeftLowerLeg': (16, 0, 0), 'RightLowerLeg': (8, 0, 0)},
            (0, -0.35, -0.1),
            {'Left': ((-0.15, -1.0, 0.05), (-0.1, -1.0, 0.02)), 'Right': ((-0.45, 0.35, -0.8), (-0.4, 0.2, -0.88))}),
        key(0.55, {'Spine': (8, 0, -16), 'Chest': (2, 0, -10), 'Hips': (0, 0, -8),
                   'LeftUpperLeg': (-14, 0, 0), 'RightUpperLeg': (10, 0, 0), 'LeftLowerLeg': (16, 0, 0), 'RightLowerLeg': (8, 0, 0)},
            (0, -0.35, -0.1),
            {'Left': ((-0.15, -1.0, 0.05), (-0.1, -1.0, 0.02)), 'Right': ((-0.45, 0.35, -0.8), (-0.4, 0.2, -0.88))}),
        base(1.0),
    ]),
    'Slash': (24, [
        base(0.0),
        key(0.3, {'Spine': (0, 0, -14), 'Chest': (0, 0, -10), 'Hips': (0, 0, -5), 'Head': (0, 0, 8),
                  'LeftUpperLeg': (-6, 0, 0), 'RightUpperLeg': (6, 0, 0), 'LeftLowerLeg': (12, 0, 0), 'RightLowerLeg': (12, 0, 0)},
            (0, 0.1, -0.1), {'Left': ((-0.35, -0.25, 0.9), (-0.75, 0.05, 0.65))},
            {'LeftLowerArm': ((-1, 0, 0), (0, -1, 0))}, 0.2),
        key(0.45, {'Spine': (8, 0, 16), 'Chest': (2, 0, 10), 'Hips': (0, 0, 6), 'Head': (0, 0, -6),
                   'LeftUpperLeg': (-16, 0, 0), 'RightUpperLeg': (12, 0, 0), 'LeftLowerLeg': (18, 0, 0), 'RightLowerLeg': (8, 0, 0)},
            (0, -0.3, -0.14), {'Left': ((0.75, -0.55, -0.35), (0.55, -0.8, -0.25))},
            {'LeftLowerArm': ((-1, 0, 0), (0, -0.4, 1))}, 0.7),
        key(0.6, {'Spine': (8, 0, 16), 'Chest': (2, 0, 10), 'Hips': (0, 0, 6), 'Head': (0, 0, -6),
                  'LeftUpperLeg': (-16, 0, 0), 'RightUpperLeg': (12, 0, 0), 'LeftLowerLeg': (18, 0, 0), 'RightLowerLeg': (8, 0, 0)},
            (0, -0.3, -0.14), {'Left': ((0.75, -0.55, -0.35), (0.55, -0.8, -0.25))},
            {'LeftLowerArm': ((-1, 0, 0), (0, -0.4, 1))}, 0.7),
        base(1.0),
    ]),
    'ShieldBash': (24, [
        base(0.0),
        key(0.25, {'Spine': (2, 0, 12), 'Chest': (0, 0, 6), 'LeftUpperLeg': (-6, 0, 0), 'RightUpperLeg': (8, 0, 0),
                   'LeftLowerLeg': (16, 0, 0), 'RightLowerLeg': (16, 0, 0)},
            (0, 0.15, -0.22), {'Left': ((0.45, 0.35, -0.8), (-0.6, -0.75, 0.25))},
            {'LeftLowerArm': ((-1, 0, 0), (0, -1, 0.1))}),
        key(0.38, {'Spine': (10, 0, -14), 'Chest': (4, 0, -6), 'LeftUpperLeg': (-18, 0, 0), 'RightUpperLeg': (14, 0, 0),
                   'LeftLowerLeg': (14, 0, 0), 'RightLowerLeg': (6, 0, 0)},
            (0, -0.6, -0.1), {'Left': ((0.1, -0.95, -0.25), (-0.95, -0.25, 0.15))},
            {'LeftLowerArm': ((-1, 0, 0), (0, -1, 0.1))}),
        key(0.55, {'Spine': (10, 0, -14), 'Chest': (4, 0, -6), 'LeftUpperLeg': (-18, 0, 0), 'RightUpperLeg': (14, 0, 0),
                   'LeftLowerLeg': (14, 0, 0), 'RightLowerLeg': (6, 0, 0)},
            (0, -0.6, -0.1), {'Left': ((0.1, -0.95, -0.25), (-0.95, -0.25, 0.15))},
            {'LeftLowerArm': ((-1, 0, 0), (0, -1, 0.1))}),
        base(1.0),
    ]),
}
PER_MECH = {'Aegis': ['Stomp', 'ShieldBash'], 'Halberd': ['Stomp', 'Slash'], 'Thunderhead': ['Stomp', 'Punch']}


def ease(k):
    return k * k * (3 - 2 * k)


def nlerp(a, b, k):
    v = Vector(a).lerp(Vector(b), k)
    return v.normalized() if v.length > 1e-6 else Vector(b).normalized()


def roll_partial(rig, name, local_axis, target, w):
    """spin a bone about its own axis by fraction w of the angle that points local_axis at target."""
    pb = rig.pose.bones[name]
    bpy.context.view_layer.update()
    M = pb.matrix.copy()
    yax = M.col[1].xyz.normalized()
    cur = (M.to_3x3() @ Vector(local_axis)).normalized()
    tgt = Vector(target)
    cur_p = (cur - yax * cur.dot(yax)).normalized()
    tgt_p = (tgt - yax * tgt.dot(yax)).normalized()
    ang = math.atan2(yax.dot(cur_p.cross(tgt_p)), cur_p.dot(tgt_p)) * w
    pb.matrix = Matrix.Translation(M.translation) @ Matrix.Rotation(ang, 4, yax) @ M.to_3x3().to_4x4()
    bpy.context.view_layer.update()


def pose_at(rig, name, keys, t, carry):
    i = 0
    while i < len(keys) - 2 and t > keys[i + 1]['t']:
        i += 1
    k0, k1 = keys[i], keys[i + 1]
    k = ease(min(1.0, max(0.0, (t - k0['t']) / max(1e-6, k1['t'] - k0['t']))))
    g['reset_pose'](rig)
    p = {}
    for bn in set(k0['body']) | set(k1['body']):
        a = k0['body'].get(bn, (0, 0, 0))
        b = k1['body'].get(bn, (0, 0, 0))
        x, y, z = (a[j] + (b[j] - a[j]) * k for j in range(3))
        p[bn] = [('x', x), ('y', y), ('z', z)]
    p['_hips'] = tuple(k0['hips'][j] + (k1['hips'][j] - k0['hips'][j]) * k for j in range(3))
    grip = 90 if name in ('Punch', 'ShieldBash') else 35
    g['finger_curl'](p, 'Left', grip, grip, grip * 0.7, 25)
    g['finger_curl'](p, 'Right', 70, 65, 40, 25)
    g['apply_pose'](rig, p)
    bpy.context.view_layer.update()
    D = g['MECH_P']
    for side in ('Left', 'Right'):
        ua = nlerp(k0['arms'][side][0], k1['arms'][side][0], k)
        fa = nlerp(k0['arms'][side][1], k1['arms'][side][1], k)
        S = rig.pose.bones[f'{side}UpperArm'].head.copy()
        E = S + ua * D['ua']
        g['set_bone_dir'](rig, f'{side}UpperArm', E)
        g['set_bone_dir'](rig, f'{side}LowerArm', E + fa * D['fa'])
    for bn in set(k0['rolls']) | set(k1['rolls']):
        r0, r1 = k0['rolls'].get(bn), k1['rolls'].get(bn)
        if r0 and r1:
            axis, target, w = r0[0], nlerp(r0[1], r1[1], k), 1.0
        elif r1:
            axis, target, w = r1[0], Vector(r1[1]), k
        else:
            axis, target, w = r0[0], Vector(r0[1]), 1.0 - k
        roll_partial(rig, bn, axis, target, w)
    blade = k0['blade'] + (k1['blade'] - k0['blade']) * k
    if 'BladeL' in rig.pose.bones:
        rig.pose.bones['BladeL'].location = (0.0, blade, 0.0)
    if carry:
        bpy.context.view_layer.update()
        wb = rig.pose.bones['WeaponR']
        wb.matrix = Matrix.Translation(wb.matrix.translation) @ g['carry_matrix']()
    bpy.context.view_layer.update()


class Holder:
    pass


for mech, clips in PER_MECH.items():
    rig = bpy.data.objects[f'{mech}_Rig']
    ad = rig.animation_data_create()
    ad.action = None
    bones = [b.name for b in rig.data.bones if b.use_deform and not b.name.startswith(('Flag_', 'Flash', 'PodFlash'))
             and b.name != 'Root' and 'Muzzle' not in b.name]
    for cname in clips:
        for tr in list(ad.nla_tracks):
            if tr.name == cname:
                ad.nla_tracks.remove(tr)
        old = bpy.data.actions.get(f'{mech}_{cname}')
        if old:
            bpy.data.actions.remove(old)
        n, keys = CLIPS[cname]
        act = bpy.data.actions.new(f'{mech}_{cname}')
        act.use_fake_user = True
        ad.action = act
        for f in range(1, n + 2):
            pose_at(rig, cname, keys, (f - 1) / n, carry=mech != 'Thunderhead')
            for bn in bones:
                pb = rig.pose.bones[bn]
                pb.keyframe_insert('rotation_quaternion', frame=f)
                pb.keyframe_insert('location', frame=f)
                pb.keyframe_insert('scale', frame=f)
        act.use_frame_range = True
        act.frame_start, act.frame_end = 1, n + 1
        slot = ad.action_slot
        ad.action = None
        tr = ad.nla_tracks.new()
        tr.name = cname
        st = tr.strips.new(cname, 1, act)
        if slot is not None and getattr(st, 'action_slot', None) is None:
            st.action_slot = slot
        tr.mute = True
    g['reset_pose'](rig)
    T = Holder()
    T.rig, T.name = rig, mech
    path = os.path.join(OUT, f'Mech_{mech}.fbx')
    g['export_mech_fbx'](T, path)
    shutil.copy2(path, os.path.join(SA, 'MechKit', 'fbx', f'Mech_{mech}.fbx'))
    print('MELEE_CLIPS', mech, [t.name for t in ad.nla_tracks])
bpy.ops.wm.save_mainfile()
