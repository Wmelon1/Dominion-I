# SoldierKit: male and female mannequin soldiers (player models) for Godot 4

| Model | Height (with helmet and boots) | Triangles | Deform bones |
|---|---|---|---|
| `Soldier_Male.glb` | 1.82 m | ~10.3k | 55 |
| `Soldier_Female.glb` | 1.73 m | ~10.9k | 55 |

Both are stylised, segmented mannequins with ball joints. Each segment is rigidly skinned, so joints
never collapse or candy-wrap at any bend angle. The female variant has narrower shoulders, wider hips,
a shaped bust (with a vest cut to fit), slimmer limbs and a hair bun under the helmet.

## Kit (separate meshes, toggleable)
| Mesh | Contents |
|---|---|
| `*_Body` | mannequin, gloves with knuckle guards, laced combat boots, faction shoulder patch |
| `*_Helmet` | camo-covered helmet, goggles on the band, NVG mount, side rails, chin strap, strobe |
| `*_Vest` | plate carrier, 3 magazine pouches, admin pouch with name tape and IFF patch, radio with antenna and PTT, 2 grenade pouches, hydration carrier, drag handle, MOLLE |
| `*_Belt` | battle belt, buckle, canteen, dump pouch, first-aid pouch, knife, magazine pouch, drop-leg pistol holster |
| `*_Backpack` | assault pack, lid, side pockets, compression straps, bedroll |
| `*_Pads` | knee and elbow pads with straps |
| `*_Rifle` | scoped rifle on the `WeaponR` socket |

Materials are tileable and shared by both soldiers: Mannequin, joint, camo fabric, webbing, leather,
polymer, dark metal, lens, emblem and red. Each soldier is about 10 draw calls with all gear on.

## Skeleton (Godot humanoid names)
`Root, Hips, Spine, Chest, UpperChest, Neck, Head`, and `Left/Right` × `Shoulder, UpperArm, LowerArm, Hand,
Thumb(Metacarpal/Proximal/Distal), Index/Middle/Ring/Little(Proximal/Intermediate/Distal), UpperLeg,
LowerLeg, Foot, Toes`. That covers 53 of the 56 `SkeletonProfileHumanoid` bones; only the optional
eyes and jaw are absent. Extra sockets: `WeaponR` (rifle grip, child of RightHand) and `Muzzle`.

To use humanoid animation libraries (Mixamo, Godot asset library, your own), select the GLB, then
Import dock → Skeleton3D → Retarget → Bone Map → new `BoneMap` with `SkeletonProfileHumanoid`. The names
already match, so it maps automatically. Import your animation library with the same profile.

## Built-in clips
| Clip | Notes |
|---|---|
| `Idle` | breathing, rifle at low ready |
| `Walk` | ≈1.05 m/s at speed_scale 1 |
| `Run` | ≈2.7 m/s at speed_scale 1, forward lean, bent arms |
| `Crouch` | low squat, rifle low |
| `Rifle_Aim` | rifle shouldered, support hand on the handguard (two-bone IK solved), head over the sights |

Every clip keys every bone, so blending between them in an `AnimationPlayer` or `AnimationTree` is clean.

## Blender rig
The `IK` bone collection has foot, knee-pole, hand and elbow-pole controls, with IK constraints already
set up and pole angles matched to the rest pose. They ship at **influence 0** (FK); raise the
influence on the LowerLeg / LowerArm IK constraints to animate with IK. IK bones are not exported.

## Godot quick start
```gdscript
# Player.tscn: CharacterBody3D > Model (Node3D + soldier_rig.gd) > Soldier_Female.glb
@onready var model: SoldierRig = $Model

func _physics_process(delta):
    # ... your movement code ...
    model.update_locomotion(Vector3(velocity.x, 0, velocity.z).length(), is_crouching, is_aiming)
    if shooting:
        spawn_bullet(model.muzzle_transform())

func _ready():
    model.show_backpack = false     # gear toggles: helmet / vest / belt / backpack / pads / rifle
```
Attach other weapons with a `BoneAttachment3D` on `WeaponR` (+Z / forward = muzzle direction).

`source/sd_build.py` is the Blender build script; it reuses `TankKit/source` and `AirshipKit/source`.
