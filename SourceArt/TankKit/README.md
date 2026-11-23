# TankKit — 5 rigged tanks for Godot 4

| Tank | Role | Triangles (body + tracks) | Bones | Gun limits | Notes |
|---|---|---|---|---|---|
| `Tank_Scout` | Light recon, 30 mm autocannon | ~12.1k | 21 | −10° / +35° | Christie-style big wheels, ATGM pod, desert camo |
| `Tank_Medium` | Main battle tank, 120 mm | ~18.8k | 31 | −8° / +20° | Side skirts, bustle rack, woodland camo |
| `Tank_Heavy` | Heavy tank, 140 mm | ~20.9k | 33 | −6° / +15° | ERA skirts + glacis blocks, RWS, urban splinter |
| `Tank_Artillery` | 155 mm self-propelled gun | ~16.4k | 33 | −3° / +70° | Front sprocket, rear turret, winter camo |
| `Tank_AntiAir` | Twin 35 mm SPAAG | ~15.8k | 35 | −5° / +85° | Twin barrels, spinning search radar, stripe camo |

Each tank = **4 draw calls**: one skinned body mesh (one material, 2048² BaseColor / ORM / Normal),
two track meshes (shared 512² track material), one muzzle-flash mesh (additive-looking alpha + emission).
Godot auto-generates LODs on import, so distant tanks get cheaper automatically.

## Files
- `glb/Tank_*.glb` — drop into your Godot project (textures embedded).
- `TankKit.blend` — source scene with all five rigs, actions and NLA clips (textures in `textures/`).
- `godot/tank_rig.gd` — runtime controller (`class_name TankRig`).
- `source/*.py` — the Blender build scripts that generated everything.

Orientation: tanks face Godot **+Z** (`Vector3.MODEL_FRONT`), Y up, 1 unit = 1 m, origin on the ground at the tank centre.

## Rig (same bone names on every tank)
| Bone | Purpose |
|---|---|
| `root` | whole vehicle |
| `hull` | hull body (use for suspension bob / firing rock) |
| `turret` | traverse — rotate about local **+Y** (positive = turn left) |
| `gun` | elevation — rotate about local **+X** (positive = up) |
| `barrel` (`barrel_L`/`barrel_R` on AntiAir) | recoil — translate along local **−Y** |
| `muzzle` (`muzzle_L`/`_R`) | socket for projectiles/VFX (attach a `BoneAttachment3D`) |
| `flash` (`flash_L`/`_R`) | muzzle flash — rest scale hides it, scale ×1000 shows it |
| `wheel_*`, `sprocket_*`, `idler_*`, `roller_*` | spin about local +Y (positive = rolling forward) |
| `track_L` / `track_R` | Blender-side track control (move along local Y to drive that track) |
| `radar` (AntiAir only) | search radar spin about local +Y |

**Tracks:** each `*_Track_L/R` mesh has a `track_cycle` blend shape that moves every link one pitch
forward. Set it to `fposmod(distance / pitch, 1.0)` for continuous, seamless track motion; wheels turn
`distance / radius`. `tank_rig.gd` does all of this for you. In Blender, sliding the `track_L/R` control
bones drives the wheels and blend shapes through drivers.

## Animation clips (in each GLB)
`Drive_Forward`, `Drive_Reverse`, `Pivot_Left`, `Pivot_Right` (loop, one track link per cycle —
set loop mode to *Linear* in the import dock; base speed ≈ 0.32–0.40 m/s, scale with `speed_scale`),
`Fire`, `Turret_Traverse` (loop), `Gun_Elevate`, and `Radar_Spin` (AntiAir, loop).
The Fire / turret / gun clips only touch their own bones, so they layer over script-driven tracks.

## Quick start (script)
```gdscript
# Scene: Node3D (tank_rig.gd)  └─ Tank_Medium.glb instance
@onready var tank: TankRig = $Tank

func _process(delta):
    var fwd := Input.get_axis("ui_down", "ui_up") * 6.0
    var turn := Input.get_axis("ui_right", "ui_left") * 3.0
    tank.drive(fwd - turn, fwd + turn, delta)   # per-track speed, m/s
    tank.aim_at(target_position)                # slews turret + gun within limits
    if Input.is_action_just_pressed("ui_accept"):
        tank.fire()                             # recoil + flash, emits fired(muzzle_transform, barrel)
```
`drive()` only animates the rig; move the vehicle body itself with your own physics/movement code.
