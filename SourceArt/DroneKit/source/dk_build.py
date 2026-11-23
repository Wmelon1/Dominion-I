# Dominion I - DroneKit driver (headless rebuild + export):
#   blender -b SourceArt/DroneKit/DroneKit.blend --python SourceArt/DroneKit/source/dk_build.py
# Rebuilds the three drones from dk_models.py, exports their FBX files + materials.json + models.json to <KIT>/fbx and
# saves the .blend. Then: python Tools/convert_textures.py DroneKit, and Dominion > 8. Set Up Drone Kit in Unity.
import bpy, os

KIT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ns = {'__name__': 'dk', 'KIT_DIR': KIT_DIR}
p = os.path.join(KIT_DIR, 'source', 'dk_models.py')
exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), ns)
ns['build_all']()
info = ns['export_all'](os.path.join(KIT_DIR, 'fbx'))
for n in ('Wasp', 'Mender', 'Kite'):
    o = bpy.data.objects[n + '_GimbalCam']
    print('DK', n, 'cam parent', o.parent.name, 'world', tuple(round(v, 3) for v in o.matrix_world.translation))
print('DK_INFO', info)
bpy.ops.wm.save_mainfile()
