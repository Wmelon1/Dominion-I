import bpy, sys, math, os
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
rig = bpy.data.objects['Male_Rig']
rig.hide_set(False)
for o in bpy.data.objects:
    if o.type == 'MESH' and o.parent and o.parent.name == 'Female_Rig':
        o.hide_render = True
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x, sc.render.resolution_y = 360, 420
cam = bpy.data.objects.get('Camera') or bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
if cam.name not in sc.objects: sc.collection.objects.link(cam)
sc.camera = cam
ad = rig.animation_data
for tr in ad.nla_tracks: tr.mute = True
views = {'front': Vector((0, -1, 0.25)), 'side': Vector((1, 0, 0.2))}
for clip in ('Walk_R', 'Walk_FL', 'Run_L', 'Run_B'):
    act = bpy.data.actions['Male_' + clip]
    ad.action = act
    try: ad.action_slot = act.slots[0]
    except Exception: pass
    n = int(act.frame_range[1])
    for vname, vd in views.items():
        for i, fr in enumerate((1, 1 + (n - 1) // 4, 1 + (n - 1) // 2, 1 + 3 * (n - 1) // 4)):
            sc.frame_set(fr)
            tgt = rig.matrix_world.translation + Vector((0, 0, 0.9))
            cam.location = tgt + vd.normalized() * 3.2
            cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = os.path.join(out, f'{clip}_{vname}_{i}.png')
            bpy.ops.render.render(write_still=True)
