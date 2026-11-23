using System;
using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    public enum Team { None = 0, Blue = 1, Red = 2 }
    public enum DamageType { SmallArms, Cannon, AP, HE, Melee, Crush }
    public enum UnitClass { Soldier, Ground, Air, Mech }
    /// <summary>How well a hull resists each damage type (see Armory.Multiplier).</summary>
    public enum ArmorClass { Infantry, Soft, Light, Armored, Air, Mech, Drone, Airship }

    /// <summary>One round: what it looks like and what it does when it lands.</summary>
    public struct Shot
    {
        public float speed, width, length, impulse, impactScale, gravity, life;
        public ImpactKind kind;
        public float damage, splash, splashRadius, proximity;
        public DamageType type;
        public Team team;
        public Health attacker;
        public Transform source;
        /// <summary>ProjectileKit model drawn behind the tracer head.</summary>
        public ProjectileModel model;
        /// <summary>Where the round left the muzzle (set by Tracers).</summary>
        public Vector3 origin;
        /// <summary>
        /// Range falloff (airship guns): full damage out to falloffStart metres of flight, then easing down to falloffMin x
        /// the damage at falloffEnd and beyond. falloffEnd = 0 means no falloff.
        /// </summary>
        public float falloffStart, falloffEnd, falloffMin;

        /// <summary>Damage multiplier for a round landing at p.</summary>
        public float RangeFactor(Vector3 p)
        {
            if (falloffEnd <= falloffStart) return 1f;
            float t = Mathf.Clamp01((Vector3.Distance(origin, p) - falloffStart) / (falloffEnd - falloffStart));
            t = 1f - (1f - t) * (1f - t);          // drops off quickly past full-damage range, flattening toward the floor
            return Mathf.Lerp(1f, falloffMin, t);
        }

        public static Shot Visual(float speed, float width, float length, float impulse, ImpactKind kind, float impactScale) =>
            new Shot { speed = speed, width = width, length = length, impulse = impulse, kind = kind, impactScale = impactScale, gravity = 0.15f, life = 2.5f };
    }

    public struct WeaponStats
    {
        public float damage, splash, splashRadius, proximity;
        public DamageType type;

        public WeaponStats(float damage, DamageType type, float splash = 0f, float splashRadius = 0f, float proximity = 0f)
        {
            this.damage = damage;
            this.type = type;
            this.splash = splash;
            this.splashRadius = splashRadius;
            this.proximity = proximity;
        }

        public void Apply(ref Shot s, Health attacker, Transform source)
        {
            s.damage = damage;
            s.type = type;
            s.splash = splash;
            s.splashRadius = splashRadius;
            s.proximity = proximity;
            s.attacker = attacker;
            s.team = attacker ? attacker.team : Team.None;
            s.source = source;
        }
    }

    public struct DamageInfo
    {
        public float amount;
        public DamageType type;
        public Team team;
        public Vector3 point, dir;
        public Health attacker;
    }

    /// <summary>Hit points, armour and weapons for every unit (keyed by prefab name), in one place for balancing.</summary>
    public static class Armory
    {
        //                                        SmallArms Cannon  AP    HE    Melee  Crush
        static readonly float[,] Mult =
        {
            /* Infantry */ { 1f,      1f,     1f,   1f,   1f,    1f },
            /* Soft     */ { 0.35f,   0.8f,   1f,   1f,   1f,    0.2f },
            /* Light    */ { 0.12f,   0.6f,   1f,   0.9f, 1f,    0.1f },
            /* Armored  */ { 0.02f,   0.3f,   1f,   0.6f, 1f,    0.05f },
            /* Air      */ { 1f,      1f,     1f,   1f,   1f,    1f },
            /* Mech     */ { 0.03f,   0.22f,  0.55f, 0.45f, 0.6f, 0.02f },
            /* Drone    */ { 0.45f,   0.6f,   0.8f, 0.6f,  1f,   1f },      // armoured composite shell, small target for splash
            /* Airship  */ { 0.08f,   0.5f,   0.8f, 1f,    1f,   0f },      // rifle rounds just hole the gas cells
        };

        public static float Multiplier(ArmorClass a, DamageType t) => Mult[(int)a, (int)t];

        public static float Hp(string key) => key switch
        {
            "Tank_Scout" => 2200f, "Tank_Medium" => 4800f, "Tank_Heavy" => 6400f, "Tank_Artillery" => 3200f, "Tank_AntiAir" => 3000f,
            "Vehicle_Mule" => 650f, "Vehicle_Bastion" => 1000f, "Vehicle_Carrier" => 1400f,
            "Aircraft_Kestrel" => 220f, "Aircraft_Falcon" => 300f, "Aircraft_Lancer" => 450f, "Aircraft_Saber" => 500f, "Aircraft_Wraith" => 700f,
            "Mech_Aegis" => 20000f, "Mech_Halberd" => 17000f, "Mech_Thunderhead" => 19000f,
            "Drone_Wasp" => 280f, "Drone_Mender" => 480f, "Drone_Kite" => 320f,
            "Airship_Leviathan" => 200000f, "Skyship_Sentinel" => 60000f,
            _ => 100f,
        };

        public static ArmorClass Armor(string key)
        {
            if (key.StartsWith("Drone_")) return ArmorClass.Drone;
            if (key.StartsWith("Airship_") || key.StartsWith("Skyship_")) return ArmorClass.Airship;
            if (key.StartsWith("Aircraft_")) return ArmorClass.Air;
            if (key.StartsWith("Mech_")) return ArmorClass.Mech;
            switch (key)
            {
                case "Vehicle_Mule": return ArmorClass.Soft;
                case "Vehicle_Bastion": case "Vehicle_Carrier": case "Tank_Scout": return ArmorClass.Light;
                case "Tank_Medium": case "Tank_Heavy": case "Tank_Artillery": case "Tank_AntiAir": return ArmorClass.Armored;
            }
            return ArmorClass.Infantry;
        }

        public static UnitClass Class(string key) =>
            key.StartsWith("Aircraft_") || key.StartsWith("Drone_") || key.StartsWith("Airship_") || key.StartsWith("Skyship_") ? UnitClass.Air : key.StartsWith("Mech_") ? UnitClass.Mech : key.StartsWith("Soldier") ? UnitClass.Soldier : UnitClass.Ground;

        public static readonly WeaponStats Rifle = new WeaponStats(18f, DamageType.SmallArms);
        public static readonly WeaponStats RifleGrenade = new WeaponStats(320f, DamageType.AP, 170f, 5f);
        public static readonly WeaponStats MechMissile = new WeaponStats(420f, DamageType.AP, 300f, 9f);
        /// <summary>Wraith air-to-air missile (proximity-fuzed blast-fragmentation warhead).</summary>
        public static readonly WeaponStats AirMissile = new WeaponStats(480f, DamageType.AP, 220f, 7f, 6f);
        /// <summary>Tank roof machine gun (cupola gun / remote weapon station).</summary>
        public static readonly WeaponStats TankMG = new WeaponStats(22f, DamageType.SmallArms);
        public static readonly WeaponStats None = default;

        /// <summary>Main weapon of a vehicle / mech.</summary>
        public static WeaponStats Weapon(string key) => key switch
        {
            "Tank_Scout" => new WeaponStats(60f, DamageType.Cannon, 22f, 2.5f),
            "Tank_Medium" => new WeaponStats(650f, DamageType.AP, 260f, 6f),
            "Tank_Heavy" => new WeaponStats(900f, DamageType.AP, 320f, 7f),
            "Tank_Artillery" => new WeaponStats(600f, DamageType.AP, 520f, 12f),
            "Tank_AntiAir" => new WeaponStats(70f, DamageType.Cannon, 45f, 5f, 8f),      // proximity-fuzed flak
            "Vehicle_Carrier" => new WeaponStats(26f, DamageType.SmallArms),
            "Vehicle_Bastion" => new WeaponStats(28f, DamageType.SmallArms),
            "Aircraft_Kestrel" => new WeaponStats(30f, DamageType.SmallArms),
            "Aircraft_Falcon" => new WeaponStats(30f, DamageType.SmallArms),
            "Aircraft_Lancer" => new WeaponStats(32f, DamageType.SmallArms),
            "Aircraft_Saber" => new WeaponStats(32f, DamageType.SmallArms),
            "Aircraft_Wraith" => new WeaponStats(45f, DamageType.Cannon, 12f, 2f),
            "Mech_Aegis" => new WeaponStats(170f, DamageType.AP, 90f, 4f),
            "Mech_Halberd" => new WeaponStats(1100f, DamageType.AP, 150f, 4f),
            "Mech_Thunderhead" => new WeaponStats(30f, DamageType.Cannon),
            _ => None,
        };
    }

    /// <summary>
    /// Hit points, team and armour of a unit in War mode (Sandbox units have none and are invulnerable).
    /// Every alive unit is listed in Health.All; Died fires once.
    /// </summary>
    public class Health : MonoBehaviour
    {
        public static readonly List<Health> All = new List<Health>();
        /// <summary>Any unit died (victim, killing blow).</summary>
        public static event Action<Health, DamageInfo> AnyDeath;
        /// <summary>Any unit took damage (victim, hit, damage dealt).</summary>
        public static event Action<Health, DamageInfo, float> AnyDamage;

        public Team team;
        public UnitClass cls;
        public ArmorClass armor;
        public string unitName = "Unit";
        public string key = "";
        public float maxHp = 100f, hp = 100f;
        public event Action<DamageInfo> Died;

        public Vehicle Vehicle { get; private set; }
        public SoldierController Soldier { get; private set; }
        /// <summary>Support drone (counted apart from the armies: it can be shot down, but doesn't decide the battle).</summary>
        public DroneUnit Drone { get; private set; }
        public bool IsDrone => Drone != null;
        /// <summary>A flying structure (airship): huge, always in the sky, not counted in the armies.</summary>
        public Airship Ship { get; private set; }
        public bool IsAirship => Ship != null;
        /// <summary>Hit points restored by repair drones over the whole battle (all units).</summary>
        public static float TotalHealed;
        public bool Alive => hp > 0f;
        public float Fraction => maxHp > 0f ? hp / maxHp : 0f;
        public float LastHitTime { get; private set; } = -99f;
        public Vector3 LastHitFrom { get; private set; }
        public Health LastAttacker { get; private set; }
        public float Radius { get; private set; } = 0.5f;
        /// <summary>
        /// Simulation LOD, set by UnitLOD: 1 = every frame (seen, or within 200 m); 2 or 4 = far and unseen units update
        /// their AI and movement every 2nd / 4th frame with the time accumulated, so they move and fight the same, just
        /// in coarser steps. Aircraft, mechs and airships always run every frame.
        /// </summary>
        [NonSerialized] public int SimStride = 1;
        int simPhase;

        /// <summary>Advance a per-component clock; false on frames this unit skips (dt then holds the accumulated time).</summary>
        public bool SimTick(ref float acc, out float dt)
        {
            acc += Time.deltaTime;
            if (SimStride > 1 && (Time.frameCount + simPhase) % SimStride != 0) { dt = 0f; return false; }
            dt = acc;
            acc = 0f;
            return true;
        }
        Vector3 centerLocal;
        static readonly Dictionary<Collider, Health> lookup = new Dictionary<Collider, Health>();

        public void Init(Team t, string unitKey, string displayName)
        {
            team = t;
            key = unitKey;
            unitName = displayName;
            cls = Armory.Class(unitKey);
            armor = Armory.Armor(unitKey);
            maxHp = hp = Armory.Hp(unitKey);
            simPhase = UnityEngine.Random.Range(0, 4);
            Vehicle = GetComponent<Vehicle>();
            Soldier = GetComponent<SoldierController>();
            Drone = GetComponent<DroneUnit>();
            Ship = GetComponent<Airship>();
            if (Ship)
            {
                centerLocal = Ship.centerLocal;
                Radius = Ship.radius;
            }
            else if (Drone)
            {
                centerLocal = Drone.centerLocal;
                Radius = Drone.radius;
            }
            else if (Vehicle)
            {
                centerLocal = Vehicle.localBounds.center;
                Radius = Mathf.Max(1f, Mathf.Min(Vehicle.localBounds.extents.x, Vehicle.localBounds.extents.z) * 1.1f);
            }
            else
            {
                centerLocal = new Vector3(0f, 1.1f, 0f);
                Radius = 0.45f;
            }
        }

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        public Vector3 Center => transform.TransformPoint(centerLocal);
        public Vector3 Velocity => Vehicle ? Vehicle.Velocity : Soldier ? Soldier.Velocity : Drone ? Drone.Velocity : Ship ? Ship.Velocity : Vector3.zero;
        /// <summary>In the air right now (aircraft, or a mech on its jets).</summary>
        public bool Airborne => cls == UnitClass.Air ? !(Vehicle is AircraftVehicle a && a.Grounded) : Vehicle is MechVehicle m && m.Flying;
        public bool IsPlayer => Vehicle ? Vehicle.PlayerDriven : Soldier && Soldier.Controlled;

        /// <summary>Forget cached collider lookups (scene change).</summary>
        public static void ClearCache() => lookup.Clear();

        public static Health Of(Collider c)
        {
            if (c == null) return null;
            if (lookup.TryGetValue(c, out var h) && h) return h;
            h = c.GetComponentInParent<Health>();
            lookup[c] = h;
            return h;
        }

        public static bool Enemies(Team a, Team b) => a != Team.None && b != Team.None && a != b;

        /// <summary>Apply a hit. Same-team damage is ignored (no friendly fire); Team.None hurts everyone.</summary>
        public float TakeDamage(DamageInfo d)
        {
            if (!Alive || (d.team != Team.None && d.team == team)) return 0f;
            float dmg = d.amount * Armory.Multiplier(armor, d.type);
            if (dmg <= 0f) return 0f;
            hp -= dmg;
            LastHitTime = Time.time;
            LastHitFrom = d.attacker ? d.attacker.Center : d.point - d.dir.normalized * 20f;
            if (d.attacker && d.attacker != this) LastAttacker = d.attacker;
            AnyDamage?.Invoke(this, d, dmg);
            if (hp <= 0f)
            {
                hp = 0f;
                Died?.Invoke(d);
                AnyDeath?.Invoke(this, d);
            }
            return dmg;
        }

        /// <summary>Repair (drones): restores up to 'amount' hit points, never past full. Returns what was restored.</summary>
        public float Heal(float amount)
        {
            if (!Alive || amount <= 0f) return 0f;
            float a = Mathf.Min(amount, maxHp - hp);
            hp += a;
            TotalHealed += a;
            return a;
        }

        public void Kill(DamageInfo d)
        {
            if (!Alive) return;
            d.amount = 1e6f;
            d.type = DamageType.AP;
            d.team = Team.None;
            float a = Armory.Multiplier(armor, DamageType.AP);
            d.amount /= Mathf.Max(a, 0.01f);
            TakeDamage(d);
        }

        /// <summary>Explosion damage to every unit in range, falling off linearly from the centre.</summary>
        public static void Splash(Vector3 pos, float radius, float damage, DamageType type, Team team, Health attacker, Health exclude = null)
        {
            if (radius <= 0f || damage <= 0f) return;
            for (int i = All.Count - 1; i >= 0; i--)
            {
                var h = All[i];
                if (h == null || h == exclude || !h.Alive) continue;
                if (team != Team.None && h.team == team) continue;
                float d = Mathf.Max(0f, Vector3.Distance(pos, h.Center) - h.Radius);
                if (d >= radius) continue;
                h.TakeDamage(new DamageInfo { amount = damage * (1f - d / radius), type = type, team = team, point = pos, dir = h.Center - pos, attacker = attacker });
            }
        }
    }

    /// <summary>Team colours: soldiers get a tinted uniform, vehicles a faint tint, for telling the sides apart.</summary>
    public static class TeamPaint
    {
        public static readonly Color Blue = new Color(0.35f, 0.62f, 1f);
        public static readonly Color Red = new Color(1f, 0.36f, 0.3f);
        static readonly Dictionary<(Material, Team), Material> cache = new Dictionary<(Material, Team), Material>();

        public static Color Of(Team t) => t == Team.Blue ? Blue : t == Team.Red ? Red : Color.white;

        public static void Apply(GameObject go, Team team, bool soldier)
        {
            if (team == Team.None) return;
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                bool changed = false;
                for (int i = 0; i < mats.Length; i++)
                {
                    var m = mats[i];
                    if (m == null || !m.HasProperty("_BaseColor")) continue;
                    string n = m.name;
                    if (n.Contains("Glass") || n.Contains("Flash") || n.Contains("Burner") || n.Contains("Blur") || n.Contains("Banner") ||
                        n.Contains("Glow") || n.Contains("Lens") || n.Contains("Emblem")) continue;
                    Color tint;
                    if (soldier)
                    {
                        if (n.Contains("Mannequin") && !n.Contains("Joint")) tint = team == Team.Blue ? new Color(0.42f, 0.6f, 1f) : new Color(1f, 0.46f, 0.4f);
                        else if (n.Contains("Camo")) tint = team == Team.Blue ? new Color(0.72f, 0.82f, 1f) : new Color(1f, 0.78f, 0.72f);
                        else if (n.Contains("RedPaint")) tint = team == Team.Blue ? new Color(0.25f, 0.55f, 2.2f) : new Color(1.3f, 0.9f, 0.9f);
                        else continue;
                    }
                    else tint = team == Team.Blue ? new Color(0.9f, 0.95f, 1.07f) : new Color(1.07f, 0.93f, 0.9f);
                    if (!cache.TryGetValue((m, team), out var tm) || tm == null)
                    {
                        tm = new Material(m) { name = m.name + "_" + team };
                        tm.SetColor("_BaseColor", m.GetColor("_BaseColor") * tint);
                        cache[(m, team)] = tm;
                    }
                    mats[i] = tm;
                    changed = true;
                }
                if (changed) r.sharedMaterials = mats;
            }
        }

        static readonly Dictionary<Material, Material> burnt = new Dictionary<Material, Material>();

        /// <summary>Scorch a destroyed vehicle: every paint darkened to burnt metal.</summary>
        public static void Burn(GameObject go)
        {
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++)
                {
                    var m = mats[i];
                    if (m == null || !m.HasProperty("_BaseColor")) continue;
                    if (m.name.Contains("Flash") || m.name.Contains("Burner") || m.name.Contains("Banner")) continue;
                    if (!burnt.TryGetValue(m, out var bm) || bm == null)
                    {
                        bm = new Material(m) { name = m.name + "_Burnt" };
                        Color c = m.GetColor("_BaseColor");
                        bm.SetColor("_BaseColor", new Color(c.r * 0.16f + 0.02f, c.g * 0.15f + 0.018f, c.b * 0.14f + 0.016f, c.a));
                        if (bm.HasProperty("_Smoothness")) bm.SetFloat("_Smoothness", 0.15f);
                        if (bm.HasProperty("_SmoothnessRemapMax")) bm.SetFloat("_SmoothnessRemapMax", 0.25f);
                        burnt[m] = bm;
                    }
                    mats[i] = bm;
                }
                r.sharedMaterials = mats;
            }
        }
    }
}
