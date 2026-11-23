import bpy, sys, os, math
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x, sc.render.resolution_y = 360, 360
sc.display.shading.color_type = 'TEXTURE'
cam = bpy.data.objects.get('Camera')
sc.camera = cam
jobs = [('Halberd', 'Slash', (0.0, 0.3, 0.45, 0.7)), ('Aegis', 'ShieldBash', (0.0, 0.25, 0.38, 0.7)),
        ('Thunderhead', 'Punch', (0.0, 0.3, 0.42, 0.7)), ('Halberd', 'Stomp', (0.0, 0.35, 0.45, 0.55))]
for mech, clip, ts in jobs:
    rig = bpy.data.objects[f'{mech}_Rig']
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.hide_render = not (o.parent is rig and ('_Banner_' not in o.name or o.name.endswith('SkyLegion')))
    ad = rig.animation_data
    for tr in ad.nla_tracks: tr.mute = True
    act = bpy.data.actions[f'{mech}_{clip}']
    ad.action = act
    try: ad.action_slot = act.slots[0]
    except Exception: pass
    n = act.frame_range[1] - 1
    for i, t in enumerate(ts):
        sc.frame_set(int(round(1 + t * n)))
        c = rig.matrix_world @ Vector((0, 0, 4.8))
        cam.location = c + Vector((14, -16, 3))
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f'melee_{mech}_{clip}_{i}.png')
        bpy.ops.render.render(write_still=True)
    ad.action = None
