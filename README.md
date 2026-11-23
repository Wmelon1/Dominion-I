# Dominion I

A Unity 6 (6000.6) project using HDRP (High Definition Render Pipeline). The game opens on a **title screen**
with two modes:

- **Sandbox:** a 2 km concrete baseplate with an airstrip, where every vehicle from the kits (except the
  airships) and both mannequin soldiers wait for you to try them out.
- **War:** after a 5-second countdown, two armies of up to 200 each fight through a procedurally generated city
  ringed by soft hills. Every map is different. Every unit is driven by combat AI except the one you control, and
  you can take command of any friendly unit.

**Play:** `Build\Dominion I.exe` (windowed 1600×900, resizable).
**Edit:** open this folder in Unity Hub (*Add ▸ Add project from disk*) with Unity 6000.6.0f1. The scenes are
`Assets/Dominion/Scenes/Title.unity`, `Baseplate.unity` (Sandbox) and `War.unity`.

## War mode
**Choosing a battle (title screen):**
- **Map seed:** type a number (up to 7 digits) to replay a map, or leave it empty for a new random city every
  battle. **NEW** rolls a seed. The map's name appears as you type.
- **Army size:** 50, 100 or **200** per side (the default).

Each seed always gives the same city and the same name, drawn from a list of about 240 town names. The countdown
shows "BATTLE OF <NAME>" with the seed so a good map can be shared. After a battle, **Play Again** replays the
same map, **New Map** rolls a new one and **Main Menu** goes back.

**Armies:** each side fields battalions of 50:

| Per battalion | Units |
|---|---|
| Infantry (25) | 5 squads of 5 (squad leader, riflemen, one anti-tank rifleman each), mixed male / female |
| Tanks and transports (12) | 3 Medium, 2 Heavy, 2 Scout, Artillery SPG, Anti-Air SPAAG, Carrier APC, Bastion MRAP, Mule truck |
| Aircraft (12) | 10 already flying (Kestrel, 2 Falcon, 2 Lancer, 3 Saber, 2 Wraith); a Kestrel and a Lancer start parked on the side's airfield and take off on their own |
| Mech (1, first two battalions only) | Aegis, Halberd or Thunderhead, flying the side's banner |

| Army size | Battalions | Per side |
|---|---|---|
| 50 | 1 | 25 infantry, 12 ground vehicles, 12 aircraft, 1 mech |
| 100 | 2 | 50 infantry, 24 ground vehicles, 24 aircraft, 2 mechs |
| 200 | 4 | 100 infantry, 49 ground vehicles, 49 aircraft, 2 mechs (an extra Medium tank and Saber fill the two mech slots) |

There are **never more than 2 mechs per side**, and a side's two mechs are always different types. Soldiers wear
team-tinted uniforms, and every unit has a blue or red marker. Blue starts in a park on the south side of the city,
Red in the mirror-image park on the north side, each with its own airfield in the hills behind it.

**Starting positions:** the infantry, their transports and the mechs start on the staging fields. The tanks (Scout,
Medium, Heavy, Artillery and Anti-Air) start scattered along the streets of their own half of the city, never on the
hills, fields, airfields or highways, with a no-man's-land strip in the middle. Every tank's spot is checked against
the navigation grid, the physics world and the units already placed, so none starts inside a building or another
unit. Aircraft start in the air or parked at their airfield.

**Victory:** a side loses when all of its soldiers, ground vehicles, mechs and airships are destroyed. The time limit
is 20 minutes; after that, the side with more units left wins.

### The city maps
Each map is generated from its seed in about 5 s when the battle loads. Everything below varies from seed to seed:

- **Size:** an 8 × 8 km world. The city is 2.9–3.4 km across, built in a flat basin surrounded by rolling, partly
  wooded hills.
- **Districts:** the city is split into 70–80 districts (downtown, midtown, residential, suburbs, industrial,
  parks). Each district has its own street-grid angle and block size, so the street pattern shifts from district
  to district the way real cities do. Downtown sits near the middle with skyscrapers, and density falls off toward
  the edge.
- **Roads (about 160 km):**
  - Arterials run along the district borders, with local street grids inside each district.
  - Highways run out through the hills, graded to at most 7%.
  - Roads are proper intersections with lane markings, curbs, sidewalks, zebra crossings and cul-de-sacs.
- **A mid-developed city:** mostly mid-rise blocks with only a few modest towers downtown (capped at about 115 m),
  wider gaps between buildings, and 10–30% of the lots left empty as yards and waste ground. The streets are clear
  of cars; car parks keep theirs.
- **Buildings (about 4,000):**
  - Lots line every street frontage.
  - Near the battle line, the seven enterable BuildingKit buildings (cottage to skyscraper) are placed with full
    interiors and colour variants.
  - Further out, the same buildings appear as merged low-detail shells.
  - Between them stand procedural towers, offices, mid-rises, terraced rows and sheds with tiled facades.
- **Street life:** car parks with cars in 8 paint colours, street lamps, traffic lights, benches, barricades
  (T-walls and jersey barriers) and about 60,000 trees.
- **Minimap:** a 1024 px top-down render of each map.

Tanks, APCs, trucks and mechs **crush parked cars** they drive over, so cars slow armour down without trapping it.

### Intel, the all-out push and transports
**Intel** (`Scripts/War/Intel.cs`): each side builds up a picture of where the enemy is.
- **Aircraft** in flight spot every enemy ground unit within 750 m of their track.
- **Drones** spot what their camera can see (needs a clear line of sight; 230–420 m depending on the drone).
- **Fighting:** every exchange of fire tells both sides where the other one is, and units report what they see.
- Contacts fade after 45 s unless seen again. Once a second they are grouped into **hotspots** (150 m cells,
  weighted by what is there and by whether a fight is going on). The minimap shows your side's hotspots as amber
  squares (orange while a fight is on).

**Everybody pushes:** a ground unit with nothing to shoot at heads for its side's **objective**. In order of
preference, that is:
1. The best intel hotspot (bigger, fresher and nearer fights first).
2. The enemy's staging area.
3. Once the staging area is taken, the nearest enemy anywhere.

No unit stops at the middle of the map or waits for the line any more. Infantry still bound from cover to cover,
but toward the objective, and only stay with the line while they are in contact. Mechs lead the push, artillery
moves its firing area up behind the army, and when a side is down to its last eighth the other side hunts them
down. Battles reach contact in about 60 s and keep moving to the end.

**Transports** (Carrier APC 8 seats, Bastion MRAP 5, Mule truck 10):
1. They find idle infantry that are still more than 400 m from the fight and close by, drive to them and wait
   with the rear door or ramp open while the riders climb in.
2. They drive them to the nearest real fight their side knows about and unload them about 150 m short, out of
   the back, with an assault order. They unload early if they come under fire or close to any known enemy.
3. Then they go back for more. Soldiers just dropped off fight their way to the objective and aren't picked
   up again for 75 s.
4. If a transport is destroyed with riders aboard, they bail out of the burning hull and some of them don't make it.

The armed ones (APC, MRAP) shoot while they drive. If you take command of a transport, its riders hop out at
your first stop.

### Repair drones
Each transport carries a limited rack of drones:
- **Carrier:** Mender, Wasp, Wasp.
- **Bastion:** Kite, Wasp.
- **Mule:** 2 Menders, Kite, Wasp.

At 200 per side that is 36 drones a side.

| Drone | Look | Speed | Repair charge | Camera range |
|---|---|---|---|---|
| **Wasp** | light X-quadcopter, khaki with an orange band | 30 m/s | 900 hp at 180 hp/s | 280 m |
| **Mender** | heavy hexacopter medic: white, glowing cyan rings, underslung repair pod with two arms | 21 m/s | 2,600 hp at 320 hp/s | 230 m |
| **Kite** | twin ducted-fan recon drone with V-tail and sensor mast | 38 m/s | 500 hp at 140 hp/s | 420 m |

- **Launch:** a transport launches one out of its roof hatch, every few seconds, whenever a **strong unit**
  nearby (a mech, a tank or an armoured transport) is below 80% health. The Mender goes to the biggest jobs.
- **Repair:** the drone flies over the rooftops, drops into the street behind its patient (on the side away
  from the threat) and plays a cyan **repair beam** on it, throwing sparks, until its charge is spent. If charge
  is left over, it moves on to the next damaged unit.
- **Recon:** with its charge used up, it becomes a **recon drone**. It orbits 50–80 m up, short of where the enemy
  is thought to be, its camera gimbal sweeping the ground, and everything it sees goes into its side's intel.
- **Getting shot down:** drones can be shot down by flak, machine guns, mech gatlings and rifles. They have a tough
  composite shell (a drone armour class that resists small arms) and fall spinning when killed. Planes leave them
  alone. The HUD counts them separately ("drn"), and they don't decide the battle.
- **Look:** soldier-sized, about 1.9–2.4 m across and 0.85–0.95 m tall. They have spinning rotors with blur discs,
  red, green and white navigation lights, and a two-axis camera gimbal that tracks the patient or sweeps the ground.

A typical 200 vs 200 battle repairs 25,000–30,000 hp in its first 2.5 minutes.

### Mech thruster dash
The **Aegis** and **Thunderhead** have a ground **dash**:
- **Controls:** hold **Space** to dash wherever the mouse points, **Shift** boosts, **S** brakes.
- **Speed:** about the Halberd's flight speed, 26 m/s, or 40 m/s (144 km/h) boosted.
- **Charge:** the same capacity as the Halberd's flight, 14 s, recharging on the ground. The HUD shows "dash %".
- **Look:** the mech leans into it on twin back thrusters, kicking up dust, in a new **Dash** pose (a low skating
  stance, weapon forward, Aegis shield braced in front). It can strike on the move during a dash, and enemy
  infantry in the way get run down.
- **AI:** both mechs dash down long straight stretches of road, drop out of it before corners and walls, and
  dash out of trouble when badly hurt.

### Pathfinding
Units plan routes through the city with `Scripts/World/CityNav.cs`:
- **Clearance grids:** two 2 m clearance grids are built from every building and prop.
  - One treats parked cars as obstacles (infantry).
  - The other ignores them, since heavy vehicles crush cars.
- **Long routes** use A* over the road graph. Each street knows how wide a vehicle fits through it, so tanks and
  mechs only take streets they fit down.
- **Short legs and off-road stretches** use a windowed grid A* on the clearance grid, smoothed by string pulling.
- **Following a path:** vehicles use pure pursuit with a speed-scaled lookahead, slow down for corners, and replan
  when they are blocked or knocked off the path.
- **Cost:** path searches are spread over frames (at most 6 paths and 2 ms per frame).

### Unit LOD (big battles)
A unit is drawn in full only when the player can actually see it:
- **When it's drawn:** it must be on screen, with a clear line of sight from the camera (buildings and terrain
  block it), and within range for its type (420 m for infantry, 1.5 km for vehicles, 2.5 km for mechs, 3.5 km for
  aircraft). Anything within 45 m, and the unit you control, is always drawn.
- **When it isn't:** the unit stops rendering, which also skips its skinning and animation. Vehicles also skip
  cosmetic work (track and wheel spin, dust, exhaust).
- **Simulation LOD:** units near the camera, or on screen, run every frame.
  - **Unseen units:** soldiers, ground vehicles and drones step their AI and movement every 2nd frame (200–600 m
    away) or every 4th frame (beyond 600 m), with the time accumulated, so they move and fight the same, only in
    coarser steps. Unseen aircraft beyond 600 m run their AI at half rate; their flight physics always runs at the
    full rate.
  - **Visible soldiers beyond 220 m:** they step at half rate (they are about 15 px tall).
  - **Far physics proxy:** an unseen ground vehicle more than 200 m away leaves the rigid-body simulation and drives
    kinematically along its crew's inputs at its real top speed and turn rate. It is handed back to the full
    physics the moment it comes into view.
  - **Airships** are always drawn and simulated in full.
- **No popping:** units are re-checked several times a second and stay drawn for 1.2 s after leaving view.

**Other optimizations:**
- Idle particle emitters stop.
- Effects too far away to be seen aren't spawned.
- Hidden airship crew are switched off.
- Unit markers and the minimap are drawn in one batched pass.
- Physics runs at 66.7 Hz instead of 100 Hz. The Sandbox self-test shows the same suspension, track, tyre and
  flight results.
- Trees are drawn out to 1.2 km on Max (beyond that they are a few pixels in the haze).

**Frame rate:** with the armies staged on the fields, a 200 vs 200 battle with all six airships on Max ran at a median of
about 72 fps (150 s self-test). With only the tanks scattered through the city the same test measures a median of
about 61 fps over the first 50 s. It sits at 70–90 fps outside the biggest firefights and dips to about 50–60 fps in
the heaviest ones. The game runs with VSync off and the frame rate capped to the monitor's refresh rate; start with
`-vsync` to turn VSync back on.

### Settings
**Settings** on the title screen and in the pause menu switches the graphics mode (saved between sessions).
Airships are always drawn and simulated in full, in every mode.

| Mode | What changes |
|---|---|
| **Max** | Everything as authored: High Fidelity pipeline, full shadow distance, volumetric fog, ambient occlusion, contact shadows, motion blur, full level of detail |
| **High** | Shadows to 700 m, no motion blur, slightly nearer level of detail, trees to 1 km |
| **Medium** | Balanced pipeline, shadows to 500 m, no contact shadows, SMAA, trees to 700 m |
| **Low** | Performant pipeline, shadows to 300 m, no volumetric fog, ambient occlusion or contact shadows, FXAA, nearer level of detail, trees to 450 m, coarser distant terrain |

### Airships
Each side has an air fleet: the **Leviathan** flagship (AirshipKit: a 162 m rigid airship) and two **Sentinel**
escorts (SkyshipKit: 89 m sky-ships with an open top deck).
- **Altitude:** they hang over the battle at about skyscraper height. The Leviathan's keel sits 150 m up and the
  Sentinels' at 125 m, always clear of the roofs below.
- **Health and crew:**

  | Ship | Health | Crew |
  |---|---|---|
  | Leviathan | 200,000 | 100 |
  | Sentinel | 60,000 | 50 |

  Rifles barely scratch them; shells, flak and missiles do the damage.
- **Victory:** they count toward victory, so a side isn't beaten while it still has a ship in the air. When only
  ships are left, the enemy's ground units move under them so their guns can reach. The HUD lists them as "ship".
- **Floating physics:**
  - **Lift:** valves and ballast trim the lift slowly toward the wanted altitude.
  - **Movement:** engines push along the heading against drag, in a gusting wind, and the rudder turns the ship
    with a lag.
  - **Sway:** the hull swings in pitch and roll like a pendulum under its gas cells (about an 11 s period).
  - The ships move slowly (6–8 m/s at most) and rarely.
- **Helm:** the flagship stations itself where its guns can reach the most enemies its side knows about (intel),
  standing off a little toward its own side. The escorts hold station off its beams.
- **Turrets:** four twin turrets on each ship engage aircraft, armour, mechs, infantry, drones and enemy airships.
  They need a clear line of fire past their own hull and hold fire when a friendly is in the way.
  - **Leviathan:** heavy shells, out to 1.5 km.
  - **Sentinels:** autocannons with flak fuzes, out to 1.3 km.
  - **Range falloff:** the base damage holds close in, then fades with the distance the round has flown, so units
    far off aren't wiped out from out of nowhere. It applies to direct hits, splash and flak bursts alike.

    | Flight | Leviathan | Sentinel |
    |---|---|---|
    | up to 300 m / 250 m | 100% | 100% |
    | 600 m | 65% | 56% |
    | 900 m | 40% | 32% |
    | 1,200 m | 25% | 21% |
    | max range (1.5 km / 1.3 km) | 20% | 20% |
- **Crew:** stationed through the decks: bridge, posts, and walkers pacing between posts. On the Sentinels, the
  nearest hands walk to the deck guns and sit behind them, turning with the mount. A deck gun only fires while its
  gunner is seated. Crew are drawn only near the ship.
- **Gunnery:** the guns aim along the centre line of each twin mount and elevate about their own axis. Each turret
  takes the best target it has a clear shot at (a building right beside a ground target doesn't stop the shell's
  blast).
- **Paratroopers:** the armies start with their normal forces; no soldiers are added. When a side is down to under 45%
  of the ground forces it started with, its ships' own crew jump, in sticks of six out of the side doors, and the
  ship's crew count drops as they go. The seated deck gunners and a skeleton crew of a tenth always stay aboard. Each jumper free-falls for a second,
  then the canopy (ParachuteKit) blossoms and he steers down at about 5 m/s toward our side of the nearest fight.
  He can be shot on the way down. On landing the canopy collapses where it falls and he joins the assault (a
  rooftop landing climbs down to the street).
- **Damage and destruction:** fires break out across the hull as it is damaged, and it lists when badly hurt. When
  destroyed it loses lift, burns and noses down, and crashes in a string of huge blasts that hurt anything
  underneath, leaving a burning wreck.

### Deploy screen
When the battle starts and every time you die, you choose where to fight:
- **Ground:** take over a soldier in the city.
- **Any of your airships:** you spawn as a deck gunner on its deck and ride along as it moves.

Press **J** to open the deploy screen at any time. On a Sentinel's deck, walk up to a deck gun and press **E** to
man it: it follows your crosshair and **LMB** fires. **E** leaves the gun.

**Damage:**
- Every unit has hit points and armour matched to the weapon types (small arms, cannon, armour-piercing, high
  explosive, melee, crush). Rifles can't hurt a tank, but shells, missiles, rifle grenades and mech strikes can.
- Tanks are tough: Scout 2,200 HP, Medium 4,800, Heavy 6,400, Artillery 3,200, Anti-Air 3,000. Transports
  (Carrier, Bastion) are not armoured to that level.
- Mechs are tougher still: Aegis 20,000 HP, Halberd 17,000, Thunderhead 19,000.
- Explosions deal splash damage. There is no friendly fire.
- Vehicles running over enemy infantry crush them.

**Secondary weapons:** every weapon modelled on a unit now works.
- **Tank roof machine guns:** the Medium and Artillery have a cupola MG and the Heavy has a remote weapon station.
  They turn with the turret and fire bursts at enemy infantry and soft vehicles within 300 m and 40° of where the
  turret points, when the gunner can see them and no friendly is in the line of fire. The player fires it with **Q**
  toward the crosshair.
- **Wraith air-to-air missiles:** the four missiles on the Wraith's wing rails. The AI fires one at an enemy aircraft
  250–2,200 m ahead (within 22° of the nose); the player presses **Q** to fire at the enemy aircraft nearest the nose
  within 2.5 km. A missile leaves the rail at the jet's own speed, accelerates to about 680 m/s, homes, and bursts
  by proximity fuse beside its target. The rail is empty afterwards.
- **Saber drop tanks:** the Saber's two fuel tanks fall away and tumble to the ground when it goes into a dogfight
  or attack run (**Q** for the player).

**Projectiles:** every round in flight is a real model (ProjectileKit) drawn at the head of its tracer, GPU-instanced
per type so hundreds cost about a millisecond. They are all textured: worn military paint, machined steel, cartridge
brass and copper driving bands.

| Round | Fired by |
|---|---|
| 5.56 mm rifle bullet (copper jacket) | soldiers |
| 12.7 mm MG round | Carrier and Bastion MGs, biplane and jet guns, Thunderhead gatling, tank roof MGs |
| 30 mm autocannon round (yellow HE body, copper band) | Scout, Anti-Air SPAAG, Wraith cannon, Sentinel deck guns |
| 120 mm tank shell (olive, copper driving band) | Medium and Heavy tanks, Aegis cannon |
| 155 mm artillery shell (olive, yellow HE band) | Artillery SPG |
| 75 mm airship shell (grey, red nose band) | Leviathan guns |
| Rail-gun slug (glowing core) | Halberd |
| Rifle grenade, rocket pod round, air-to-air missile | soldiers' grenades, Thunderhead pods, Wraith rails |

- **Tracers** are a tapered glow: brightest just behind the round, where the tracer compound burns in its base, and
  fading to a point down the trail.
- **Brass:** rifles, machine guns and autocannons eject spent casings out of the breech. The casings carry the
  shooter's own velocity, tumble, bounce once and lie on the ground for a few seconds (near the camera only).
- **Big guns** throw a fireball of igniting propellant gas several metres ahead of the muzzle, with burning grains,
  muzzle-brake side jets and dust kicked up off the ground.
- Rockets and missiles fly as their own models with the motor's smoke trail behind the nozzle.

**Deaths:**
- Soldiers collapse with a death animation.
- Vehicles explode and leave blackened, burning wrecks that serve as cover.
- Aircraft that are shot down burn, fall and blow up on impact.
- Mechs explode and topple over.

**The AI:**
- **Infantry:**
  - Squads advance from cover to cover toward the objective, ride the transports when they come to pick them up,
    and assault where they are dropped.
  - They hide behind walls and lean out at the wall's end to fire aimed bursts, leading moving targets and
    aiming more tightly the longer they track one.
  - They duck back into cover when hit and fight from the open with evasive strafing when there is no cover.
  - Badly wounded soldiers fall back.
  - They step out of the way of vehicles and hold fire when a friendly is in the line.
  - Anti-tank riflemen launch rifle grenades at armour.
- **Tanks:**
  - They close to their gun's best range, then shoot and reposition sideways.
  - They back off when rushed, keep their front armour toward the enemy, and lead their shots, firing only
    when the gun is on target.
  - **Scouts** flank on the wings.
  - **Artillery** follows the army forward and fires real ballistic arcs at anything its side can see, out to about 1.1 km.
  - **Anti-air** escorts the armour and hunts aircraft with proximity-fused flak.
  - **Transports** ferry infantry to the fight and launch repair drones (see above).
  - All of them steer around obstacles, reverse out when stuck and right themselves after a rollover.
- **Pilots:**
  - They roll and pull toward their target, dogfight with lead pursuit, and make diving gun runs on ground
    targets before climbing away for the next pass.
  - When an enemy gets on their tail they break hard, and they avoid head-on collisions.
  - They manage speed with the throttle and never pull into a stall.
  - Dive angle is limited by altitude, and recovery is planned from the real turn radius.
  - Fighters prioritise enemy aircraft; the Wraith and Kestrel prioritise ground targets.
- **Mechs:**
  - They lead the push and alternate braced firing with repositioning; the Aegis and Thunderhead dash between fights.
  - The Thunderhead fires homing missile salvoes at armour.
  - Any enemy at arm's length gets the melee strike, and a crowd around the feet gets stomped.
  - The Halberd jets across the field to strike distant targets, firing on the way down, and jets out of trouble.
- When a side is down to its last few ground units, the other side hunts them down.

**You:** you start as the leader of the Blue centre squad.
- **E** boards a nearby friendly vehicle.
- **T** takes command of the friendly unit under the crosshair (soldier, tank, aircraft in flight or mech).
  Its AI stands down and resumes when you leave.
- **Tab** jumps to the nearest friendly soldier.
- If you die, you take over another friendly soldier after 3 s.

A soldier you leave aboard a vehicle that can't stop (an aircraft in flight) stays on as its crew.

**HUD:** team strength bars and battle clock, kill feed, unit markers with health bars, a minimap of the city,
your health, hit markers, the countdown with the map's name and seed, and the victory screen (Play Again / New
Map / Main Menu). **Esc** opens the pause menu
(Resume / Restart / Main Menu / Quit) in both modes.

## What's on the baseplate
| Row | Contents |
|---|---|
| Spawn | Soldier (Male) and Soldier (Female). `Tab` switches between them |
| Tanks | Scout, Medium, Heavy, Artillery SPG, Anti-Air SPAAG |
| Transports | Mule 6×6 cargo truck, Bastion 4×4 MRAP, Carrier tracked APC |
| Mechs | W/S walk, A/D turn, Shift run, RMB brace and aim, LMB fire, **F melee strike** (Halberd arm-blade slash, Aegis shield bash with a lunge, Thunderhead punch; works while walking or running), **G stomp** (ground-pound shockwave), Q guided missiles (Thunderhead). **Halberd flight:** hold Space to fly wherever the mouse points in a head-first dive pose, Shift boosts, S air-brakes, LMB fires; let go to drop and land |
| Airstrip (to the right) | Kestrel and Falcon biplanes, Lancer and Saber jets, Wraith fighter |

Walk up to any vehicle and press **E** to take control. Press **E** again to get out, once the vehicle is
stopped (and has landed).

## Controls
| | Keys |
|---|---|
| Soldier | WASD 8-direction strafe (the body faces the camera; walk ≈2.1 m/s, sprint ≈5.2 m/s, animations sped up to match), Shift sprint, mouse look, RMB raise rifle, LMB fire while aiming, G rifle grenade (anti-armour, while aiming), E enter vehicle, Tab switch soldier |
| Tanks / APC | W/S drive, A/D steer (pivots on the spot when stopped), Space brake, mouse aims the turret, LMB fire, Q roof machine gun (Medium, Heavy, Artillery), F ramp (APC) |
| Trucks / MRAP | W/S throttle and reverse, A/D steer, Space brake, mouse aims the roof gun (MRAP), LMB fire, F door / tailgate |
| Aircraft | Shift/Ctrl throttle, W/S pitch (S pulls up), A/D roll (steers on the ground), Z/C rudder, Space wheel brakes, LMB guns, Q air-to-air missile (Wraith) / drop the fuel tanks (Saber), G gear, F canopy |
| Mechs | W/S walk, A/D turn, Shift run, RMB brace and aim, LMB fire, Q missile pods (Thunderhead). **Halberd flight:** hold Space to fly wherever the mouse points in a head-first dive pose, Shift boosts, S air-brakes, LMB fires; let go to drop and land. **Aegis / Thunderhead dash:** hold Space to dash wherever the mouse points, Shift boosts, S brakes |
| Any vehicle | R puts it back upright (after a rollover or crash) |
| War | T take command of the friendly unit under the crosshair, Tab nearest friendly soldier, J deploy screen (ground or an airship), E man a deck gun on an airship |
| General | F1 hide help, Esc pause menu, mouse wheel camera distance |

## Vehicle physics
- **Wheeled vehicles:**
  - Each wheel has its own spring-damper on a raycast, tuned so the static ride height matches the model.
  - The wheels visibly ride the suspension.
  - The tyre model handles slip grip, drive, brakes, rolling resistance and a friction limit.
  - Steering is on the front axle, with the steering lock reduced at speed.
  - The body squats under power, dives under braking and leans in corners.
- **Tracked vehicles:**
  - Every road wheel is sprung and the hull rides on them.
  - The left and right tracks drive independently (skid steering), so they can pivot in place.
  - Firing the main gun rocks the hull on its springs.
  - The track links and wheels move with the vehicle's real ground speed.
- **Aircraft:**
  - Lift depends on angle of attack, up to a stall.
  - Drag combines parasitic and induced drag, which sets the top speed.
  - Propeller thrust falls off with speed.
  - Side-slip and weather-vane stability are modelled.
  - Control authority scales with airspeed.
  - On the ground the aircraft rolls on sprung gear with wheel brakes and nose- or tail-wheel steering.
  - The elevator's authority grows with airspeed and is capped by a g-limiter (8 g for jets, 5 g for biplanes).
  - Hard impacts count as a crash. In Sandbox the aircraft resets after 3 s; in War a crash destroys it.
- **Mechs:** have weight and inertia. The Halberd's jets give 14 s of flight (they recharge on the ground) at 26 m/s, or 46 m/s when boosting. The mech tilts so its head leads along the flight path: level flight is horizontal, steep dives are head-down. It plays the **Fly** clip, which was added to all three mechs in `SourceArt/MechKit/MechKit.blend` by `Tools/mech_fly_clip.py`. The Stomp, Slash, ShieldBash and Punch clips come from `Tools/mech_melee_clips.py`.
- **Performance:**
  - **Tanks:** 0–40 km/h in about 2–4 s, with top speeds of 61–90 km/h.
  - **Trucks:** 0–40 km/h in about 2 s, with a deliberately modest steering lock (19–22°, reduced at speed) for a wide, truck-like turning circle.
- **Parked vehicles:** stay frozen until you drive one or bump into one. Once shoved, they skid to a stop on their parking brakes.
- **Weapons hit things:** rounds push whatever they hit (tank main guns and the Halberd's rail gun hit hard and flash on impact). Thunderhead pods fire guided missiles that explode with a blast and dust ring. Mech strikes and stomps shove vehicles in proportion to their weight.
- **Tank balance:** the centre of mass sits over the road wheels, so long-barrelled tanks rest level. Brake dive is about 2–4°.

## Effects (smoke, explosions, shockwaves, cracks)
Every effect is a pooled Unity particle system built in code (`Scripts/Core/Vfx.cs`). It renders with a small HDRP
particle shader (`Shaders/DominionParticle.shader`) that supports per-particle fades, soft edges against the
ground, and bright fire that blooms. Effects are sized per weapon:

| Source | Muzzle | Impact |
|---|---|---|
| Rifle, Bastion and Carrier MGs, aircraft guns, Thunderhead gatling | grey wisp | sparks off metal, dust off the ground |
| Scout and Anti-Air 30–35 mm, Wraith 20 mm cannon | small blast | small high-explosive pop with sparks |
| Medium and Heavy tank guns, Aegis cannon | propellant fireball rolling out ahead of the muzzle, burning grains, muzzle-brake side jets, and ground dust kicked up under the barrel | fireball, sparks, bouncing debris, rising smoke plume, dust ring, ground shockwave, scorched crater with cracks |
| Artillery SPG (155 mm) | huge blast | the same at 1.8× size |
| Halberd rail gun | sharp blast | explosion plus a bright air-shock ring |
| Thunderhead missiles | launch flash, smoke trail, rocket flame | explosion, cracks, physical blast |
| Mech stomp, hard landing from flight | — | racing shockwave ring, dust wall, concrete debris, cracked ground |
| Mech strikes | — | sparks, flash and dust on contact |
| Aircraft crash | — | large explosion and a burning wreck that smokes until it resets |

Continuous effects:
- **Tanks, APC and trucks:** dust trails from the tracks and wheels that scale with speed and cornering, plus diesel exhaust haze that thickens with throttle.
- **Biplanes:** engine smoke.
- **Halberd:** jet smoke while flying.
- **Mechs:** dust puffs at every footstep, bigger when running.

Crack and scorch decals fade out after 30–40 s (at most 32 at once).

## Project layout
| Path | Contents |
|---|---|
| `Assets/Dominion/Art/` | FBX models and HDRP textures (mask maps converted from the kits' ORM maps), plus `.json` rig data |
| `Assets/Dominion/Scripts/` | gameplay: `Player/` (GameDirector, SoldierController, CameraRig, AutoTest), `Vehicles/` (Suspension, Tracked, Wheeled, Aircraft, Mech), `Combat/` (Health, teams, armour and weapon tables), `AI/` (SoldierAI, GroundAI, PlaneAI, MechAI), `War/` (WarManager, cover, UnitLOD), `World/` (city generator, CityNav pathfinding, map seeds and names), `UI/` (title screen, shared UI style), `Core/`, `Mech/` (MechController) |
| `Assets/Dominion/Scripts/World/` | `CityPlan.cs` (districts, road graph, staging parks, airfields, highways), `CityGenerator*.cs` (terrain, roads, buildings, props, trees, minimap, lighting), `CityMesh.cs` (chunked mesh merging), `CityNav.cs`, `MapInfo.cs` (seed, army size, name list), `CarProp.cs` (crushable cars) |
| `Assets/Dominion/Editor/` | `DominionBuilder.cs` rebuilds materials, prefabs, animators and the Title / Baseplate / War scenes, and builds the exe (**Dominion** menu). `BuildingKitBuilder.cs` and `CityKitBuilder.cs` set up the building and city-prop prefabs, colour variants, terrain layers and `Generated/CityKit.asset`. `DroneKitBuilder.cs` sets up the drone materials, the repair-beam material and the three drone prefabs |
| `Assets/Dominion/Scripts/War/`, `Drones/` | `Intel.cs` (what each side knows), `TransportBay.cs` (riders and drone rack), `DroneUnit.cs` (drone flight, repair and recon) |
| `Assets/Dominion/Generated/` | generated materials, prefabs and animator controllers |
| `Assets/Dominion/Scripts/War/Airship.cs`, `Editor/AirshipBuilder.cs` | airship physics, helm, turrets, crew and destruction; airship import (**Dominion ▸ 9. Set Up Airships**) |
| `Assets/Dominion/Scripts/Core/GraphicsMode.cs` | graphics modes and the settings panel |
| `SourceArt/` | all Blender kits (`.blend`, build scripts, textures, the earlier Godot exports), including the airships (exported with `Tools/blender_export.py -- AirshipKit` / `SkyshipKit`), the **BuildingKit** (7 enterable buildings), the **CityKit** (trees, cars, wrecks, street furniture, terrain and road textures) and the **DroneKit** (Wasp, Mender, Kite) |
| `Tools/` | `blender_export.py` (kit → FBX + strafe clips), `convert_textures.py`, `make_vfx_textures.py`, `mech_*_clips.py`, build logs |

## Rebuilding after changing the art
1. Run the export for a kit (the soldier export also regenerates the 16 strafe clips):
   `blender -b SourceArt\TankKit\TankKit.blend --python Tools\blender_export.py -- TankKit "<project>\Assets\Dominion\Art" "<project>\SourceArt"`
2. `python Tools\convert_textures.py`
3. In Unity: **Dominion ▸ 1. Set Up Assets**, **2. Build Baseplate Scene**, **4. Build War Scene**,
   **5. Build Title Scene**, then **3. Build Windows Player**. From the command line, run
   `-executeMethod Dominion.EditorTools.DominionBuilder.BatchAll` to do all of it.

**BuildingKit:**
`blender -b SourceArt\BuildingKit\BuildingKit.blend --python SourceArt\BuildingKit\source\bk_build.py -- export`
builds the 7 buildings, checks every door and stair route, and exports the FBX files. Then run
`python Tools\convert_textures.py BuildingKit` and step 3.

**CityKit:**
1. `python SourceArt\CityKit\source\ck_textures.py` regenerates the textures.
2. In Blender, with `SourceArt\CityKit\CityKit.blend` open, run:
   `KIT_DIR = r'<project>\SourceArt\CityKit'; exec(open(KIT_DIR + r'\source\ck_models.py').read()); build_all(); export_all(KIT_DIR + r'\fbx')`
3. Run `python Tools\convert_textures.py CityKit`, then step 3 above.

**ProjectileKit:** `python SourceArt\ProjectileKit\source\pj_textures.py`, then in Blender with
`SourceArt\ProjectileKit\ProjectileKit.blend` open run
`KIT_DIR = r'<project>\SourceArt\ProjectileKit'; exec(open(KIT_DIR + r'\source\pj_models.py').read()); build(); export(KIT_DIR + r'\fbx')`,
then `python Tools\convert_textures.py ProjectileKit` and step 3 (the editor builds `Resources/Dominion/Projectiles.prefab`).

**ParachuteKit:** `python SourceArt\ParachuteKit\source\pk_textures.py`, then in Blender with
`SourceArt\ParachuteKit\ParachuteKit.blend` open run
`KIT_DIR = r'<project>\SourceArt\ParachuteKit'; exec(open(KIT_DIR + r'\source\pk_models.py').read()); build(); export(KIT_DIR + r'\fbx')`,
then `python Tools\convert_textures.py ParachuteKit` and step 3.

**DroneKit:**
1. `python SourceArt\DroneKit\source\dk_textures.py` regenerates the textures.
2. `blender -b SourceArt\DroneKit\DroneKit.blend --python SourceArt\DroneKit\source\dk_build.py` rebuilds and
   exports the drones.
3. Run `python Tools\convert_textures.py DroneKit`, then step 3 above (or **Dominion ▸ 8. Set Up Drone Kit**).

The mech **Dash** clip comes from
`blender -b SourceArt\MechKit\MechKit.blend --python Tools\mech_dash_clip.py -- "<project>\SourceArt" "<project>\Assets\Dominion\Art\Mechs"`.

The city itself has no asset to rebuild: it is generated from the seed every time War mode loads.

To run the automated self-test, start the game with `"Dominion I.exe" -autotest`. It walks the soldier in all
8 directions, enters and drives or flies every vehicle, writes screenshots and `autotest.log` to `AutoTest\`
next to the exe, then quits. `-vfxonly` runs just the effects showcase (about 20 s).

`-wartest` (with optional `-wartime <seconds>`, default 150) runs a whole AI battle in War mode:
- It first checks the player controls (T on a tank, T on a soldier, death and respawn), then spectates.
- It logs unit counts, every kill and its weapon, AI states, per-vehicle gunnery, frame rate and errors.
- It records 6 s of flight data for any aircraft that crashes on its own.
- It saves a screenshot every 9 s.

`-warswap` puts Blue in the north, to check the AI has no side bias. `-titleshot <file.png>` captures the title
screen.

War-mode test options:
- `-seed <n>` picks the map and `-army 50|100|200` the army size. These also work when you just play.
- The war test also logs map statistics, pathfinding counts (paths, failures, time), stuck vehicles, cars crushed
  and how many units are drawn or hidden by the unit LOD. Every 10 s it also logs intel (contacts, hotspots,
  reports by source), transports (boarded, dropped, trips, bail-outs), drones (launched, flying, shot down, hp
  repaired) and mech dashes. Every other screenshot is a drone repairing (a side close-up) or a transport loading
  or unloading.
- The Sandbox test also dashes the Aegis and Thunderhead and logs distance, top speed, lean and charge used.
- `-citytest` (with `-wartest`) skips the battle. It photographs the generated city instead: overview, downtown
  from the air, hills, top-down, street level in each district type, staging, airfield and highway.
- `-autotestdir <folder>` writes the screenshots and log somewhere other than `AutoTest\`.
- `-notrees` leaves out the forest, for performance comparisons.
- `-vsync` turns VSync back on.
- `-noships` leaves the air fleets out, for performance comparisons.
- `-physhz <n>` sets the physics rate (the default is 66.7).
- The war test also:
  - logs each airship (health, state, altitude, speed, shots, crew) and how many vehicles are on the physics proxy;
  - photographs each Blue airship from outside and from its deck;
  - deploys onto a Sentinel, checks the soldier rides along, and fires a deck gun.
