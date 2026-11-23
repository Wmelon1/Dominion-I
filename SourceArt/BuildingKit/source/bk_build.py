# Dominion I - BuildingKit driver.
#   In Blender's Text editor / console:  KIT_DIR = r'<KIT>'; RUN_BK = True; exec(open(KIT_DIR + r'\source\bk_build.py').read())
#   Headless:  blender -b BuildingKit.blend --python source/bk_build.py -- export
# Builds every building into the 'BuildingKit' collection, lays them out in a row, runs the gameplay checks on the
# collision meshes, and with 'export' writes the FBX files + materials.json to <KIT>/fbx and into the Unity project
# (Assets/Dominion/Art/Buildings).
import bpy, os, sys, json

KIT_DIR = globals().get('KIT_DIR') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(os.path.dirname(os.path.dirname(KIT_DIR)), 'Assets', 'Dominion', 'Art', 'Buildings')
NS = {'__name__': 'bk', 'KIT_DIR': KIT_DIR}
for f in ('bk_geo.py', 'bk_buildings.py', 'bk_validate.py', 'bk_export.py'):
    p = os.path.join(KIT_DIR, 'source', f)
    exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), NS)

LAYOUT = {'Building_Cottage': (0, 0), 'Building_House': (22, 0), 'Building_Shop': (46, 0), 'Building_Apartment': (80, 0),
          'Building_Office': (125, 0), 'Building_Skyscraper': (185, 0), 'Building_Warehouse': (250, 0)}


def build_all(only=None):
    kit = NS['get_coll']('BuildingKit')
    out = {}
    for name, fn in NS['BUILDINGS'].items():
        if only and name not in only:
            continue
        B, info = fn()
        check = NS['validate'](name, B)
        root, stats = NS['finish'](B, name, kit, info)
        root.location = (*LAYOUT.get(name, (0, 0)), 0)
        stats['door_problems'] = check['n_door_problems']
        stats['route_problems'] = sum(r['n'] for r in check['routes'])
        out[name] = stats
        print(name, stats)
    return out


if __name__ == '__main__' or globals().get('RUN_BK'):
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    build_all()
    if 'export' in argv or globals().get('EXPORT_BK'):
        NS['export_all'](os.path.join(KIT_DIR, 'fbx'), ART_DIR, list(NS['BUILDINGS']))
    if bpy.data.filepath:
        bpy.ops.wm.save_mainfile()
