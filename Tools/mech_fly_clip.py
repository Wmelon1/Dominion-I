# Adds a looping "Fly" clip (superman dive pose) to the three mechs in SourceArt/MechKit/MechKit.blend and
# re-exports their FBX files. Headless:
#   blender -b SourceArt/MechKit/MechKit.blend --python Tools/mech_fly_clip.py -- <SourceArtDir> <ArtMechsDir>
# Pose is in the mech's own frame: Unity tilts the whole mech forward so the head leads along the flight path,
# so here the weapon arm points "up" the body (= forward in flight), legs trail, head tilts back to look ahead.
import bpy, sys, os, math, shutil
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
SA, OUT = argv[0], argv[1]
g = {'__name__': 'mk', 'KIT_DIR': os.path.join(SA, 'TankKit'), 'AIR_DIR': os.path.join(SA, 'AircraftKit'),
     'AS_DIR': os.path.join(SA, 'AirshipKit'), 'SD_DIR': os.path.join(SA, 'SoldierKit'), 'MK_DIR': os.path.join(SA, 'MechKit')}
for rel in ('TankKit/source/tk_core.py', 'TankKit/source/tk_tank.py', 'AircraftKit/source/ak_core.py',
            'AirshipKit/source/as_tex.py', 'AirshipKit/source/as_build.py', 'SoldierKit/source/sd_build.py',
            'MechKit/source/mk_build.py'):
    p = os.path.join(SA, rel)
    exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), g)

TAU = math.tau


def fly_pose(rig, name, t):
    D = g['MECH_P']
    ph = TAU * t
    s = math.sin(ph)
    g['reset_pose'](rig)
    p = {'Spine': [('x', -6 + 1.0 * s)], 'Chest': [('x', -4)], 'UpperChest': [('x', -3)],
         'Neck': [('x', -22)], 'Head': [('x', -36 + 1.5 * s)],
         'LeftUpperLeg': [('x', 12 + 5 * s), ('y', -5)], 'RightUpperLeg': [('x', 6 - 5 * s), ('y', 5)],
         'LeftLowerLeg': [('x', 26 + 8 * s)], 'RightLowerLeg': [('x', 38 - 8 * s)],
         'LeftFoot': [('x', 38)], 'RightFoot': [('x', 38)], 'LeftToes': [('x', 10)], 'RightToes': [('x', 10)]}
    g['finger_curl'](p, 'Right', 70, 65, 40, 25)
    g['finger_curl'](p, 'Left', 40, 40, 30, 15)
    g['apply_pose'](rig, p)
    bpy.context.view_layer.update()
    ua, fa = D['ua'], D['fa']
    sway = 0.04 * s

    def arm(side, d_up, d_fore):
        S = rig.pose.bones[f'{side}UpperArm'].head.copy()
        E = S + Vector(d_up).normalized() * ua
        g['set_bone_dir'](rig, f'{side}UpperArm', E)
        g['set_bone_dir'](rig, f'{side}LowerArm', E + Vector(d_fore).normalized() * fa)

    # weapon arm straight along the flight path; the gun / gatling top faces the mech's back (= the sky in flight)
    if name == 'Thunderhead':
        arm('Right', (-0.3, -0.2 + sway, 1.0), (-0.1, -0.15, 1.0))
        g['roll_bone_to'](rig, 'RightLowerArm', (1, 0, 0), (0, 1, 0))
    else:
        arm('Right', (-0.28, -0.2 + sway, 1.0), (-0.12, -0.12, 1.0))
        g['roll_bone_to'](rig, 'RightHand', (1, 0, 0), (0, 1, 0))
    if name == 'Aegis':
        # shield arm across the front, shield facing the flight direction like a battering ram
        arm('Left', (0.25, -0.65, 0.7), (-1.0, -0.25, 0.2))
        g['roll_bone_to'](rig, 'LeftLowerArm', (-1, 0, 0), (0, 0, 1))
    else:
        arm('Left', (0.4, 0.15 - sway, -1.0), (0.2, 0.25, -1.0))      # swept back along the body


class Holder:
    pass


for name in ('Aegis', 'Halberd', 'Thunderhead'):
    rig = bpy.data.objects[f'{name}_Rig']
    ad = rig.animation_data_create()
    ad.action = None
    for tr in list(ad.nla_tracks):
        if tr.name == 'Fly':
            ad.nla_tracks.remove(tr)
    old = bpy.data.actions.get(f'{name}_Fly')
    if old:
        bpy.data.actions.remove(old)
    bones = [b.name for b in rig.data.bones if b.use_deform and not b.name.startswith(('Flag_', 'Flash', 'PodFlash'))
             and b.name != 'Root' and 'Muzzle' not in b.name]
    act = bpy.data.actions.new(f'{name}_Fly')
    act.use_fake_user = True
    ad.action = act
    n = 48
    for f in range(1, n + 2, 4):
        fly_pose(rig, name, (f - 1) / n)
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
    tr.name = 'Fly'
    st = tr.strips.new('Fly', 1, act)
    if slot is not None and getattr(st, 'action_slot', None) is None:
        st.action_slot = slot
    tr.mute = True
    g['reset_pose'](rig)
    T = Holder()
    T.rig, T.name = rig, name
    path = os.path.join(OUT, f'Mech_{name}.fbx')
    g['export_mech_fbx'](T, path)
    shutil.copy2(path, os.path.join(SA, 'MechKit', 'fbx', f'Mech_{name}.fbx'))
    print('FLY_CLIP', name, [t.name for t in ad.nla_tracks])
bpy.ops.wm.save_mainfile()
