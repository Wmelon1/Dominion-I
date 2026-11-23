import bpy, sys, os
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
rig = bpy.data.objects['Male_Rig']
for o in bpy.data.objects:
    if o.type == 'MESH' and o.parent and o.parent.name == 'Female_Rig':
        o.hide_render = True
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x, sc.render.resolution_y = 500, 500
cam = bpy.data.objects.get('Camera')
sc.camera = cam
ad = rig.animation_data
for tr in ad.nla_tracks: tr.mute = True
for clip in ('Walk', 'Walk_F', 'Run_B', 'Idle'):
    act = bpy.data.actions['Male_' + clip]
    ad.action = act
    try: ad.action_slot = act.slots[0]
    except Exception: pass
    sc.frame_set(5)
    tgt = Vector((-0.6, 0, 0.9))
    cam.location = tgt + Vector((3.0, -0.6, 0.4))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    wb = rig.pose.bones['WeaponR']
    print('WEAPON', clip, tuple(round(v, 2) for v in (rig.matrix_world @ wb.matrix).col[1].xyz))
    sc.render.filepath = os.path.join(out, f'cmp_{clip}.png')
    bpy.ops.render.render(write_still=True)
