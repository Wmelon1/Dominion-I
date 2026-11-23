# Adds a looping "Dash" clip to the Aegis and Thunderhead in SourceArt/MechKit/MechKit.blend and re-exports their FBX
# files. The thruster dash is a low skating stance: torso leaning into the thrust, head up looking ahead, the front leg
# carrying the weight with the knee bent, the rear leg trailing off the ground, weapon arm forward and ready, the other
# arm (Aegis: shield) braced in front. A slight buffeting shake loops through it. Reuses the melee-clip pose helpers.
# Headless:  blender -b SourceArt/MechKit/MechKit.blend --python Tools/mech_dash_clip.py -- <SourceArtDir> <ArtMechsDir>
import bpy, sys, os, math, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:]
SA, OUT = argv[0], argv[1]
src = open(os.path.join(HERE, 'mech_melee_clips.py'), encoding='utf-8').read()
src = src[:src.index('class Holder:')]                  # helpers and pose machinery only, not its export loop
ns = {'__name__': 'melee'}
exec(compile(src, 'mech_melee_clips.py', 'exec'), ns)
key, pose_at, g = ns['key'], ns['pose_at'], ns['g']
TAU = math.tau

# Blender frame: the mech faces -Y, its left is +X, up is +Z. Arms are posed by direction (upper arm, forearm).
ARMS = {
    'Aegis': {'Right': ((-0.36, -0.42, -0.83), (-0.22, -0.86, -0.46)),       # cannon arm forward
              'Left': ((0.36, -0.5, -0.79), (-0.55, -0.78, -0.3))},          # shield across the front
    'Thunderhead': {'Right': ((-0.36, -0.42, -0.83), (-0.2, -0.88, -0.43)),  # gatling forward
                    'Left': ((0.4, 0.32, -0.86), (0.32, 0.5, -0.8))},        # swept back
}


def dash_key(mech, t):
    s = math.sin(TAU * t * 2)          # two buffeting cycles per loop
    c = math.cos(TAU * t)
    body = {'Spine': (15 + 1.2 * s, 0, 1.0 * c), 'Chest': (6, 0, 0), 'UpperChest': (3, 0, 0),
            'Neck': (-7, 0, 0), 'Head': (-13 - 1.2 * s, 0, 0),
            'LeftUpperLeg': (-21, 0, -3), 'LeftLowerLeg': (35 + 1.5 * s, 0, 0), 'LeftFoot': (-13, 0, 0),
            'RightUpperLeg': (19 + 1.5 * c, 0, 3), 'RightLowerLeg': (32, 0, 0), 'RightFoot': (10, 0, 0)}
    return key(t, body, (0.0, 0.05, -0.2 + 0.025 * s), ARMS[mech])


class Holder:
    pass


for mech in ('Aegis', 'Thunderhead'):
    rig = bpy.data.objects[f'{mech}_Rig']
    ad = rig.animation_data_create()
    ad.action = None
    for tr in list(ad.nla_tracks):
        if tr.name == 'Dash':
            ad.nla_tracks.remove(tr)
    old = bpy.data.actions.get(f'{mech}_Dash')
    if old:
        bpy.data.actions.remove(old)
    bones = [b.name for b in rig.data.bones if b.use_deform and not b.name.startswith(('Flag_', 'Flash', 'PodFlash'))
             and b.name != 'Root' and 'Muzzle' not in b.name]
    n = 24
    keys = [dash_key(mech, i / 6) for i in range(7)]
    act = bpy.data.actions.new(f'{mech}_Dash')
    act.use_fake_user = True
    ad.action = act
    for f in range(1, n + 2, 2):
        pose_at(rig, 'Dash', keys, (f - 1) / n, carry=mech != 'Thunderhead')
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
    tr.name = 'Dash'
    st = tr.strips.new('Dash', 1, act)
    if slot is not None and getattr(st, 'action_slot', None) is None:
        st.action_slot = slot
    tr.mute = True
    g['reset_pose'](rig)
    T = Holder()
    T.rig, T.name = rig, mech
    path = os.path.join(OUT, f'Mech_{mech}.fbx')
    g['export_mech_fbx'](T, path)
    shutil.copy2(path, os.path.join(SA, 'MechKit', 'fbx', f'Mech_{mech}.fbx'))
    print('DASH_CLIP', mech, [t.name for t in ad.nla_tracks])
bpy.ops.wm.save_mainfile()
