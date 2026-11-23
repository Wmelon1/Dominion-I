# MechKit: three line-holding mechs for Unity 6

All three mechs share one 9.1 m frame and one skeleton, so they are the same size: 5× the 1.82 m
SoldierKit mannequin. The helmet top is about 9.1 m and the banner tip about 13.7 m. Each mech carries
a back banner in three faction designs (9 banners in total).

| Mech | Role | Loadout | Paint | Body tris | Exported bones |
|---|---|---|---|---|---|
| `Mech_Aegis` | shield wall | 3.5 m tower shield on the left forearm, heavy autocannon, domed pauldrons, knight helm with T-visor, smoke launchers | olive camo, yellow/black hazard trim | 14.4k | 60 |
| `Mech_Halberd` | duelist / skirmisher | long rail rifle, forearm blade (`BladeL` bone), twin jump jets with flames, angular pauldrons, mono-eye head | gunmetal splinter, red trim | 14.2k | 63 |
| `Mech_Thunderhead` | fire support | forearm gatling with a spinning barrel bone, twin 9-tube missile pods that pitch, ammo drum, radar | desert tan, orange hazard trim | 15.5k | 67 |

Shared frame details: chamfered armour shells, V-shaped breast plates, hydraulic pistons on the waist,
thighs, shins and neck, knee and elbow actuators, louvred vents, chest lamps, a back reactor with exhaust
stacks, articulated fingers, and toe/heel foot sections.

## Banners (3 per mech)
| Faction | Design |
|---|---|
| `SkyLegion` | navy field, gold border and fringe, winged-star badge |
| `IronRepublic` | olive field, gold border and fringe, black cog badge |
| `StormCorsairs` | crimson swallowtail, black border, white lightning bolt |

Each banner also carries its mech's class sigil: a shield and cross (Aegis), a halberd (Halberd) or
triple chevrons (Thunderhead). The three designs are separate two-sided meshes (`*_Banner_<Faction>`)
on the same 4-bone chain (`Flag_0..3`). `MechController.Faction` shows one at a time.

## Textures (per mech, 4096²)
`T_Mech_<Name>_BaseColor`, `_Normal` (OpenGL/Unity convention), `_MetallicSmoothness` (R = metal,
A = smoothness), `_Occlusion`, plus `T_Banner_<Name>_<Faction>` (512×1024, alpha cut-out),
`T_MuzzleFlash` and `T_Afterburner`. Baked with panel lines, edge wear, chips, grime, dust and
per-part ambient occlusion, so limbs don't carry each other's shadows when they move. One atlas
material per mech, plus a small emissive "glow" material for visors and eyes. That is about
3–4 draw calls per mech.

## Clips
| Clip | Length | Notes |
|---|---|---|
| `Idle` | 2.5 s loop | breathing sway, weapon held low |
| `Walk` | 2.0 s loop | ≈2.5 m/s ground speed at animator speed 1 |
| `Run` | 1.33 s loop | ≈6.1 m/s, forward lean, arm pump |
| `Aim` | 2.0 s loop | combat stance: weapon arm forward, shield / blade / radar arm in guard, pods raised |
| `Fire` | 1.0 s | Aegis 3-round burst, Halberd single rail shot with heavy recoil, Thunderhead gatling + both pods |
| `Flag_Wave` | 1.0 s loop | banner only (used by the optional "Banner" animator layer) |
| `Jets_On` | 0.5 s loop | Halberd only: jump-jet flames lit |

Every body clip keys every body bone, so cross-fades are clean.

## Unity setup
1. Copy `unity/Assets/MechKit` into your project's `Assets` folder.
2. Run **Tools ▸ MechKit ▸ Set Up Materials, Animators and Prefabs**. It configures the texture
   imports and creates the materials (URP Lit if URP is active, otherwise Standard). It also sets the
   FBX imports (Generic rig, looping clips, material remaps) and creates one Animator Controller and one
   prefab per mech in `Assets/MechKit/Prefabs`.
3. Drag `Mech_Aegis` / `Mech_Halberd` / `Mech_Thunderhead` into the scene. Each mech faces +Z.

```csharp
using MechKit;

MechController mech = GetComponent<MechController>();
mech.Faction = MechFaction.StormCorsairs;     // banner design
mech.SetLocomotion(groundSpeed);              // every frame: picks Idle / Walk / Run and matches speed
mech.SetAiming(true);                         // combat stance
mech.AimAt(target.position);                  // torso yaw ±50°, pitch ±25°, pods follow
mech.Fired += (muzzle, i) => SpawnShell(muzzle.position, muzzle.up);   // muzzle.up = barrel direction
mech.Fire();                                  // main gun: flash, recoil, gatling spin-up
mech.FirePods();                              // Thunderhead: alternate left / right pods
mech.SetJets(true);                           // Halberd: jump-jet flames
```
The banner sways procedurally. It trails backward as the mech walks and swings out on turns. To use the
`Flag_Wave` clip instead, raise the animator's "Banner" layer weight and switch `proceduralBanner` off.

**Sockets:** `WeaponR` (hand weapon grip), `Muzzle`, `PodMuzzle_L/R`. For any socket, +Y points out of
the barrel. Attach effects with a child transform, or read `MechController.GetMuzzle(i)` /
`MuzzleRay(i)`.

**Skeleton:** `Root`, `Hips`, `Spine`, `Chest`, `UpperChest`, `Neck`, `Head`, plus `Left/Right` ×
`Shoulder`, `UpperArm`, `LowerArm`, `Hand`, the finger chains, `UpperLeg`, `LowerLeg`, `Foot` and
`Toes`. These are the same names Unity's Humanoid auto-mapper looks for. The kit ships as Generic because
the weapon, pod, flash and banner bones are animated too. Variant bones are `BladeL`, `Jet_L/R`
(Halberd) and `Pod_L/R`, `Gatling`, `PodFlash_L/R` (Thunderhead). Flash and flame geometry is stored at
1/1000 scale; its bone is scaled ×1000 to show it.

**Batch check:** `MechKit.EditorTools.MechKitSetup.ValidateBatch` (run with `-executeMethod`) runs the
setup and writes `MechKitValidation.txt` with bone, clip, size, aim-direction and banner-switch checks.

## Blender file
`MechKit.blend` holds the three mechs side by side in their combat stance, each showing a different
banner. Every rig has IK foot, knee, hand and elbow controls in the `IK` bone collection (influence 0 =
FK by default, not exported). The clips live on muted NLA tracks named after each clip. Rigs are scaled
1.09 at object level; that is the 5× mannequin size. `source/mk_build.py` is the build script; it reuses
the TankKit, AircraftKit, AirshipKit and SoldierKit sources.
