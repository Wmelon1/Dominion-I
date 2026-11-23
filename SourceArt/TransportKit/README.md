# TransportKit: 3 rigged military transports for Godot 4

| Vehicle | Type | Triangles | Bones | Features |
|---|---|---|---|---|
| `Vehicle_Mule` | 6×6 cargo truck | ~9.6k | 11 | canvas-covered bed on bows, drop tailgate, steering front axle, lugged tyres, fuel tank, exhaust stack |
| `Vehicle_Bastion` | 4×4 armoured carrier (MRAP) | ~6.8k | 14 | V-hull, armoured glass, brush guard + winch, roof MG turret with shield, swing-out rear door |
| `Vehicle_Carrier` | tracked APC | ~12k (incl. tracks) | 24 | sloped glacis + trim vane, commander cupola with heavy MG, rear ramp, seamless track rig (same as TankKit) |

Each vehicle uses **one 2048² baked material** (BaseColor / ORM / Normal). The tracked APC adds the shared
track material, and gun vehicles add a muzzle-flash mesh, so each vehicle is 1 to 4 draw calls.
Godot generates LODs on import.

Orientation: front toward Godot **+Z** (`MODEL_FRONT`), Y up, metres, origin on the ground at the vehicle centre.

## Rig
| Bone | Motion |
|---|---|
| `root`, `body` (`hull` on the Carrier) | whole vehicle / body (bob, lean) |
| `wheel_<axle>_<L/R>` | spin about local +Y (positive = rolling forward) |
| `steer_1_L/R` | yaw about local +Y (**+ = left**); the wheel bones are children |
| `turret` / `gun` / `barrel` | MG traverse (+Y) / elevation (+X) / recoil (−Y) |
| `muzzle` / `flash` | gun socket / muzzle flash (scale ×1000 to show) |
| `tailgate`, `ramp` | rotate +X to lower; `door_rear` rotates +Y to swing open |
| Carrier tracks | `track_L/R` meshes with a `track_cycle` blend shape, plus wheel/sprocket/idler bones (see TankKit) |

## Animation clips
Mule: `Drive_Forward`, `Drive_Reverse` (loop, one wheel revolution), `Steer_Demo`, `Tailgate_Open`.
Bastion: the same, plus `Turret_Traverse`, `Gun_Elevate`, `Fire`, `DoorRear_Open`.
Carrier: `Drive_Forward/Reverse`, `Pivot_Left/Right` (seamless loops), `Fire`, `Turret_Traverse`, `Gun_Elevate`, `Ramp_Open`.

## Quick start
```gdscript
# Node3D with vehicle_rig.gd, child: Vehicle_Bastion.glb instance
@onready var mrap: VehicleRig = $Mrap

func _process(delta):
    mrap.drive(speed, steer_input, delta)    # m/s, -1..1 (+ = right). Tracked: steer splits track speeds
    mrap.aim_at(target_position)             # turret + gun within limits
    if Input.is_action_pressed("ui_accept"):
        mrap.fire()                          # emits fired(muzzle_transform)
    mrap.set_door("door_rear", true)         # "tailgate" / "door_rear" / "ramp"
```
The script animates the rig only; vehicle physics (`VehicleBody3D` etc.) are yours.
The builder scripts in `source/` reuse `TankKit/source/`.
