# AirshipKit: "Leviathan" troop airship for Godot 4

A 160 m rigid military airship (30 m envelope diameter, 47 m tall overall) with a 64 m two-deck
gondola and a fully built, walkable interior sized for **200 seated soldiers** plus crew.

## Layout (origin = lower-deck floor at the gondola centre; nose toward Godot +Z)
**Lower deck (troop deck, 3.1 m ceiling)**
- Radio / navigation room (nose): radio desks with dials, chairs, map table, stair to the upper deck.
- **Troop bay (34 m)**: 4 bench rows × 50 seats = **200 seats** (two wall rows facing in, two
  back-to-back centre rows), seat backs, rifle clips, hand straps, static-line cables, ventilation
  duct, jump lights, fire extinguishers, 18 lamps, sliding troop doors port and starboard.
- Cargo bay (rear): crate stacks, barrels, tie-down rails, stair up, **rear cargo ramp**.

**Upper deck**
- Bridge: faceted panoramic windows, ship's wheel, engine telegraphs, binnacle, voice tubes,
  instrument consoles, captain's chair.
- Chart room / officers: chart table, bookshelves, desk, officer bunks, stair landing.
- Crew quarters: 16 triple bunks (48 berths) and central locker rows.
- Mess hall and galley: two long tables set with plates and mugs, benches, stove, pot shelves.
- Armory: 36 rifles in racks, ammunition crates, workbench, stair landing.

**Exterior**: gored envelope with seam tapes and ring-frame tapes, nose mooring cone, red nose bands,
emblem decals, dorsal catwalk with rails and valve hoods, cruciform tail with elevators and rudders,
6 engine nacelles with radiators, exhausts and 4-blade props, roof walkway, pylons, searchlights,
nav lights, ladders, riveted lapped hull plating, and 4 twin-gun turrets (2 dorsal, 2 ventral).

## Performance
- About 75k triangles in total for the whole ship, interior included.
- **Tileable world-scale texture sets** (BaseColor / ORM / Normal): Envelope, HullPlating, DeckPlanks,
  InteriorWall, DarkMetal, Brass and Canvas, plus Glass, Lamp, RedPaint, Emblem and MuzzleFlash.
  Texture detail stays sharp everywhere, unlike one baked atlas stretched over 160 m.
- Static meshes are **not skinned**: `Airship_Envelope`, `Airship_Exterior`, `Airship_Interior_Lower`
  and `Airship_Interior_Upper`. Only `Airship_Moving` (props, control surfaces, ramp, doors, turrets) is skinned.
- `airship_rig.gd` sets `visibility_range_end` (160 m) on the interior meshes so they are skipped when far away.
- Godot generates LODs on import.

## Collision
`Airship_Collision-colonly` imports automatically as a `StaticBody3D` with a concave (trimesh) shape.
It covers floors, outer walls with door and ramp openings, bulkheads with doorways, stair slopes, the
roof and the envelope hull. To move the ship as a physics object, re-parent that shape under an
`AnimatableBody3D`.

## Rig
| Bones | Motion |
|---|---|
| `prop_1`…`prop_6` | spin about local +Y |
| `elevator_L/R`, `rudder_U/D` | local +Y (+ elevator = nose up, + rudder = yaw right) |
| `ramp` | rotate +X to lower (105°) |
| `door_L/R` | slide along local −Y by 2.35 m |
| `turret_1…4` / `gun_1…4` | traverse (+Y) / elevation (+X); 1–2 ventral, 3–4 dorsal |
| `muzzle_<n><L/R>` / `flash_<n><L/R>` | gun sockets / muzzle flashes (scale ×1000 to show) |

Clips: `Props_Spin` (loop), `Controls_Demo`, `Ramp_Open`, `Doors_Open`, `Turrets_Traverse`, `Fire`.

## Godot quick start
```gdscript
# Node3D with airship_rig.gd, child: Airship_Leviathan.glb instance
@onready var ship: AirshipRig = $Ship

func _ready():
    ship.throttle = 0.6
    for i in ship.seat_count():              # 200 seats
        var soldier = soldier_scene.instantiate()
        add_child(soldier)
        soldier.global_transform = ship.get_seat_transform(i)   # +Z faces the way the seat faces

func _process(delta):
    ship.set_controls(pitch_input, yaw_input)
    ship.aim_turrets(enemy.global_position)
    ship.fire_all()                          # emits fired(muzzle_transform, turret_index)
    ship.ramp_open = landed
    ship.doors_open = deploying
```
On ready, the script spawns a warm `OmniLight3D` (7 m range, no shadows) at each of the 42
`LightSocket_##` nodes. Set `spawn_interior_lights = false` to light the interior yourself.

`source/` contains the Blender build scripts (they reuse `TankKit/source` and `AircraftKit/source`).
In `AirshipKit.blend`, the `Preview_Lights` collection lights the interior for viewing in Blender only.
