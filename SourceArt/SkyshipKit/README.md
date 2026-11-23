# SkyshipKit: "Sentinel" sky-ship for Godot 4

The smaller sister of the Leviathan, at roughly half its size: an 88 m envelope (18 m diameter) above a
45 m wooden, boat-shaped hull slung on rigging. It has an **open top deck** with four anti-glider turrets
and a full interior for **100 seated soldiers** plus crew. About 57k triangles in total.

## Layout (origin = keel line at the hull centre; bow toward Godot +Z)
**Top deck (exposed, z = 6 m)**
- **4 twin-autocannon turrets** on railed sponsons (fore and aft, port and starboard). They rest facing
  outboard, traverse 360° and elevate −10° to +85°, enough to engage gliders diving from above.
- Bridge deckhouse aft: wheel, engine telegraphs, binnacle, gauges, chart table, voice tubes; roof
  searchlights, rail and antenna.
- Fore and aft companionway stairs down to the troop deck (with railings), capstan, bow searchlight,
  bowsprit, rope coils, cowl ventilators, ammo lockers, fire-bucket racks, lashed crates.
- Suspension cables, girder struts and a ladder up to the keel catwalk under the envelope.

**Troop deck (z = 3.2 m)**
- Bow armory: 22 racked rifles and crates.
- **Troop bay: 4 bench rows × 25 seats = 100 seats**, hand straps, static-line cables, duct, lamps.
- Mess and galley, plus **sliding boarding doors** port and starboard.
- Stern crew quarters: double bunks, captain's desk and lockers.

**Hold (z = 0.6 m)**: cargo (crates, barrels, shell racks), ladder up, and an engine room with two
V-engines, flywheels, drive shafts, gearboxes, fuel tanks and a gauge panel.

**Exterior**: tarred plank hull with nails, metal rub strakes, portholes, a khaki gored envelope with
red nose bands and valve hoods, a cruciform plated tail with elevators and rudders, 4 outrigger engine
pods with 3-blade pusher props, and stern lanterns.

## The three flags
Three flagpoles sit on the balloon (a 9 × 5.4 m stern ensign and two 6 × 3.6 m bow flags). Each design
is its own mesh on the same waving bones, so you can switch them in Godot:

| `flag_type` | Mesh | Design |
|---|---|---|
| 0 | `Skyship_Flag_SkyLegion` | navy field, gold pinstripes, winged-star badge |
| 1 | `Skyship_Flag_IronRepublic` | olive field, gold diagonal band, black cog |
| 2 | `Skyship_Flag_StormCorsairs` | crimson swallowtail, black border, white lightning bolt |

`Flags_Wave` is a seamless loop; `skyship_rig.gd` plays it automatically and shows only the selected flag.

## Performance
Static meshes (`Skyship_Envelope`, `Skyship_Exterior`, `Skyship_Interior_Hold`,
`Skyship_Interior_TroopDeck`) are not skinned. Only `Skyship_Moving` (turrets, props, control surfaces,
doors), the flags and the muzzle flash are skinned. Textures are tileable world-scale sets:
SkyEnvelope, HullWood, DeckPlanks, InteriorWall, DarkMetal, MetalPlating, Brass and Canvas, plus
glass, lamp and red paint. Interior meshes switch off beyond 120 m.

## Collision
`Skyship_Collision-colonly` becomes a `StaticBody3D` with a trimesh shape on import. It covers the hull
shell with door openings, all three decks with the stair and hatch holes, stair slopes, bulkheads with
doorways, the deckhouse, the sponsons and the envelope.

## Godot quick start
```gdscript
@onready var ship: SkyshipRig = $Sentinel      # Node3D with skyship_rig.gd + the GLB as child

func _ready():
    ship.flag_type = 2                          # Storm Corsairs
    ship.throttle = 0.7
    for i in ship.seat_count():                 # 100 seats
        spawn_soldier(ship.get_seat_transform(i))

func _process(delta):
    ship.aim_turrets(glider.global_position)    # turrets track; each turret limited to -10..85 deg
    ship.fire_all()                             # emits fired(muzzle_transform, turret_index)
    ship.doors_open = boarding
```
Bones: `turret_1..4`, `gun_1..4`, `muzzle_/flash_<n><L/R>`, `prop_1..4`, `elevator_L/R`, `rudder_U/D`,
`door_L/R`, `flag_<stern|bow_L|bow_R>_0..3`. Clips: `Props_Spin`, `Controls_Demo`, `Doors_Open`,
`Turrets_Sweep`, `Fire`, `Flags_Wave`.
