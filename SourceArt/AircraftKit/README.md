# AircraftKit: 5 rigged fighters for Godot 4

| Aircraft | Era / type | Triangles | Bones | Features |
|---|---|---|---|---|
| `Aircraft_Kestrel` | WWI biplane | ~7.9k | 15 | rotary engine spins with the 2-blade wooden prop, twin cowl guns, rigging wires, fabric ribs |
| `Aircraft_Falcon` | 1930s biplane | ~9.5k | 21 | radial engine + NACA cowl, 3-blade prop, wheel spats, sliding hood, 4 guns |
| `Aircraft_Lancer` | early straight-wing jet | ~6.0k | 23 | natural-metal panels, tip tanks, 4 nose guns, retractable gear, sliding canopy |
| `Aircraft_Saber` | swept-wing jet | ~5.7k | 29 | two-tone camo, 6 guns, 2 droppable tanks, retractable gear, sliding canopy |
| `Aircraft_Wraith` | modern twin-engine | ~6.4k | 23 | twin canted tails, all-moving stabilators, 4 missiles, internal cannon, twin afterburners, hinged canopy |

Each aircraft uses **one 2048² baked material** (BaseColor / ORM / Normal) for the airframe, plus small
shared materials for canopy glass, muzzle flash, prop blur and afterburner (about 4 draw calls per plane).
Godot generates LODs on import.

Orientation: nose toward Godot **+Z** (`MODEL_FRONT`), Y up, metres. The origin is the aircraft's
reference point (roughly the centre of gravity), not the ground. Models are in flight attitude.

## Rig (shared bone names)
| Bone | Motion |
|---|---|
| `root`, `body` | whole aircraft |
| `aileron_L/R` | rotate local +Y; **+ on both = roll left** (the script inverts this for you) |
| `elevator_L/R` | rotate local +Y; **+ = nose up** (whole stabilator on the Wraith) |
| `rudder` (`rudder_L/R` on the Wraith) | rotate local +Y; **+ = yaw right** |
| `prop` | spin about local +Y (biplanes) |
| `prop_blur` | blur disc, hidden at rest; scale ×1000 to show |
| `gear_N`, `gear_L`, `gear_R` | retract: nose +95° about local X, mains −88° / +88° about local Y (jets) |
| `wheel_*` | spin about local +Y |
| `canopy` | slide back along local −Y (Falcon, Lancer, Saber) or rotate +X to open (Wraith) |
| `muzzle_N` / `flash_N` | gun sockets / muzzle flash (scale ×1000 to show) |
| `afterburner` (`_L/_R`) | flame, hidden at rest; scale ×1000 to show |
| `store_N` | drop tanks / missiles; use the bone as the launch socket and scale it to 0.001 to hide |

## Animation clips
`Controls_Demo`, `Fire`, `Prop_Spin` (loop, biplanes), `Canopy_Open`, `Gear_Retract` and
`Afterburner` (loop) on the jets.

## Quick start
```gdscript
# Node3D with aircraft_rig.gd, child: Aircraft_Saber.glb instance
@onready var plane: AircraftRig = $Plane

func _process(delta):
    plane.set_controls(Input.get_axis("ui_down", "ui_up"),       # pitch
                       Input.get_axis("ui_left", "ui_right"),    # roll
                       0.0)                                      # yaw
    plane.throttle = 1.0                       # prop rpm / afterburner above 0.85
    plane.gear_down = false                    # animated retraction
    if Input.is_action_pressed("ui_accept"):
        plane.fire()                           # emits fired(muzzle_transform, gun_index)
```
`release_store(i)` hides a tank or missile and emits `store_released(transform, i)` so you can spawn
the projectile there; `rearm()` brings them back. The script animates the rig only; flight physics are yours.

`source/` holds the Blender build scripts. They reuse `TankKit/source/tk_core.py` and `tk_tank.py`.
