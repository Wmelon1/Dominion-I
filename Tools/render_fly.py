import bpy, sys, os, math
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x, sc.render.resolution_y = 640, 480
sc.display.shading.color_type = 'TEXTURE'
cam = bpy.data.objects.get('Camera')
if cam is None:
    cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera')); sc.collection.objects.link(cam)
sc.camera = cam
for name in ('Halberd', 'Aegis', 'Thunderhead'):
    rig = bpy.data.objects[f'{name}_Rig']
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.parent and o.parent.type == 'ARMATURE':
            o.hide_render = o.parent is not rig or ('_Banner_' in o.name and not o.name.endswith('SkyLegion'))
        elif o.type == 'MESH':
            o.hide_render = True
    ad = rig.animation_data
    for tr in ad.nla_tracks: tr.mute = True
    act = bpy.data.actions[f'{name}_Fly']
    ad.action = act
    try: ad.action_slot = act.slots[0]
    except Exception: pass
    rig.rotation_euler.x = math.radians(80)
    loc0 = rig.location.copy()
    rig.location = Vector((loc0.x, 0, 6))
    sc.frame_set(1)
    bpy.context.view_layer.update()
    c = rig.matrix_world @ Vector((0, 0, 4.5))
    for tag, off in (('side', Vector((22, 2, 3))), ('front', Vector((4, -20, 6)))):
        cam.location = c + off
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f'fly_{name}_{tag}.png')
        bpy.ops.render.render(write_still=True)
    rig.rotation_euler.x = 0; rig.location = loc0; ad.action = None
