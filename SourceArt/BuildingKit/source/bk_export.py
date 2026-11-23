# Dominion I - BuildingKit FBX export (run inside Blender after bk_geo + bk_buildings have built the scene).
# One FBX per building: an empty root <Name> with children <Name>_LOD0, <Name>_LOD1 (Unity builds the LODGroup from
# the _LODn suffixes) and <Name>_Collider (turned into a MeshCollider by the Unity builder). Axis conversion is baked
# into the meshes (Unity +Z = Blender -Y = the building front), 1 unit = 1 m, origin on the ground.
import bpy, os, json


def export_building(root, path):
    vl = bpy.context.view_layer
    old = root.location.copy()
    root.location = (0, 0, 0)
    vl.update()
    for o in vl.objects:
        o.select_set(False)
    objs = [root] + list(root.children)
    state = [(o, o.hide_get(), o.hide_viewport) for o in objs]
    for o in objs:
        o.hide_viewport = False
        o.hide_set(False)
        o.select_set(True)
    vl.objects.active = root
    try:
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True, object_types={'EMPTY', 'MESH'}, apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_space_transform=True,
            use_mesh_modifiers=False, mesh_smooth_type='FACE', use_tspace=False, use_triangles=True,
            add_leaf_bones=False, bake_anim=False, path_mode='STRIP', embed_textures=False, use_custom_props=False)
    finally:
        for o, h, hv in state:
            o.hide_viewport = hv
            o.hide_set(h)
        root.location = old


def export_all(fbx_dir, art_dir, names):
    os.makedirs(fbx_dir, exist_ok=True)
    os.makedirs(art_dir, exist_ok=True)
    report = {}
    for n in names:
        root = bpy.data.objects[n]
        p = os.path.join(fbx_dir, n + '.fbx')
        export_building(root, p)
        report[n] = json.loads(root['bk_stats'])
        report[n].update(json.loads(root.get('bk_info', '{}')))
        report[n]['fbx_kb'] = round(os.path.getsize(p) / 1024)
    mats = {}
    for name, (stem, tint, tile, kind) in MATS.items():
        mats[name] = {'stem': stem, 'tint': tint, 'kind': kind,
                      'tile_m': list(tile_of(name)) if tile_of(name) else None}
    for d in (fbx_dir, art_dir):
        with open(os.path.join(d, 'materials.json'), 'w', encoding='utf-8') as f:
            json.dump(mats, f, indent=1)
    with open(os.path.join(fbx_dir, 'buildings.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1)
    return report
