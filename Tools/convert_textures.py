# Copies kit textures into the Unity project; ORM (R=AO, G=rough, B=metal) -> HDRP mask map (R=metal, G=AO, B=detail, A=smooth)
#   python convert_textures.py                 -> every kit
#   python convert_textures.py BuildingKit     -> just the named kit(s)
import os, shutil, sys
import numpy as np
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KITS = {'TankKit': 'Tanks', 'AircraftKit': 'Aircraft', 'TransportKit': 'Transports', 'SoldierKit': 'Soldiers', 'MechKit': 'Mechs',
        'BuildingKit': 'Buildings', 'CityKit': 'City', 'DroneKit': 'Drones', 'AirshipKit': 'Airships', 'SkyshipKit': 'Skyships', 'ParachuteKit': 'Parachutes', 'ProjectileKit': 'Projectiles'}
only = sys.argv[1:]
for kit, sub in KITS.items():
    if only and kit not in only:
        continue
    src = os.path.join(ROOT, 'SourceArt', kit, 'textures')
    dst = os.path.join(ROOT, 'Assets', 'Dominion', 'Art', sub, 'Textures')
    os.makedirs(dst, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(src)):
        if not f.lower().endswith('.png'):
            continue
        if kit == 'MechKit' and f.startswith('T_Mech_'):
            continue                                   # Unity-URP repacks, not needed for HDRP
        p = os.path.join(src, f)
        if f.endswith('_ORM.png'):
            a = np.asarray(Image.open(p).convert('RGB'), dtype=np.uint8)
            m = np.empty(a.shape[:2] + (4,), np.uint8)
            m[..., 0] = a[..., 2]
            m[..., 1] = a[..., 0]
            m[..., 2] = 255
            m[..., 3] = 255 - a[..., 1]
            Image.fromarray(m, 'RGBA').save(os.path.join(dst, f.replace('_ORM.png', '_Mask.png')))
        else:
            shutil.copy2(p, os.path.join(dst, f))
        n += 1
    print(kit, '->', sub, n, 'textures')
if not only or 'MechKit' in only:
    mech_dst = os.path.join(ROOT, 'Assets', 'Dominion', 'Art', 'Mechs')
    for f in os.listdir(os.path.join(ROOT, 'SourceArt', 'MechKit', 'fbx')):
        shutil.copy2(os.path.join(ROOT, 'SourceArt', 'MechKit', 'fbx', f), os.path.join(mech_dst, f))
    print('mech fbx', os.listdir(mech_dst))
if not only or 'CityKit' in only:
    cdst = os.path.join(ROOT, 'Assets', 'Dominion', 'Art', 'City')
    os.makedirs(cdst, exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, 'SourceArt', 'CityKit', 'fbx')):
        if f.endswith('.fbx') or f.endswith('.json'):
            shutil.copy2(os.path.join(ROOT, 'SourceArt', 'CityKit', 'fbx', f), os.path.join(cdst, f))
    print('city fbx', len(os.listdir(cdst)))
if not only or 'BuildingKit' in only:
    bdst = os.path.join(ROOT, 'Assets', 'Dominion', 'Art', 'Buildings')
    os.makedirs(bdst, exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, 'SourceArt', 'BuildingKit', 'fbx')):
        if f.endswith('.fbx') or f == 'materials.json':
            shutil.copy2(os.path.join(ROOT, 'SourceArt', 'BuildingKit', 'fbx', f), os.path.join(bdst, f))
    print('building fbx', sorted(os.listdir(bdst)))
if not only or 'DroneKit' in only:
    ddst = os.path.join(ROOT, 'Assets', 'Dominion', 'Art', 'Drones')
    os.makedirs(ddst, exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, 'SourceArt', 'DroneKit', 'fbx')):
        if f.endswith('.fbx') or f.endswith('.json'):
            shutil.copy2(os.path.join(ROOT, 'SourceArt', 'DroneKit', 'fbx', f), os.path.join(ddst, f))
    print('drone fbx', sorted(os.listdir(ddst)))
if not only or 'ParachuteKit' in only:
    pdst = os.path.join(ROOT, 'Assets', 'Dominion', 'Art', 'Parachutes')
    os.makedirs(pdst, exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, 'SourceArt', 'ParachuteKit', 'fbx')):
        if f.endswith('.fbx') or f.endswith('.json'):
            shutil.copy2(os.path.join(ROOT, 'SourceArt', 'ParachuteKit', 'fbx', f), os.path.join(pdst, f))
    print('parachute fbx', sorted(os.listdir(pdst)))
if not only or 'ProjectileKit' in only:
    jdst = os.path.join(ROOT, 'Assets', 'Dominion', 'Art', 'Projectiles')
    os.makedirs(jdst, exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, 'SourceArt', 'ProjectileKit', 'fbx')):
        if f.endswith('.fbx') or f.endswith('.json'):
            shutil.copy2(os.path.join(ROOT, 'SourceArt', 'ProjectileKit', 'fbx', f), os.path.join(jdst, f))
    print('projectile fbx', sorted(os.listdir(jdst)))
