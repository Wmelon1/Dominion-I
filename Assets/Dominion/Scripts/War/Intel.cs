using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// What each side knows about where the enemy is. Contacts come from:
    ///  - aircraft in flight (wide view of the ground below them, no line of sight needed from altitude),
    ///  - drones (camera gimbal: shorter range, needs a clear line of sight),
    ///  - fighting (any exchange of fire tells both sides where the other one is, and units that see an enemy report it).
    /// Contacts fade after ~45 s unless seen again. Once a second they are clustered into hotspots (150 m cells, weighted
    /// by what is there: a mech counts for more than a rifleman) that the ground forces and the transports head for.
    /// </summary>
    public static class Intel
    {
        public struct Hot
        {
            public Vector3 pos;          // centroid of the contacts in the cell
            public float weight;         // how much is there (soldier 1, vehicle 2.5, mech 6)
            public int count;
            public bool battle;          // fighting going on there
            public float age;            // seconds since the freshest contact in it was seen
        }

        class Contact
        {
            public Vector3 pos;
            public float time;
            public bool battle;
            public bool air;
        }

        const float MaxAge = 45f, Cell = 150f, AirRange = 750f;
        static readonly Dictionary<Health, Contact>[] seen = { null, new Dictionary<Health, Contact>(), new Dictionary<Health, Contact>() };
        static readonly List<Hot>[] hots = { null, new List<Hot>(), new List<Hot>() };
        static readonly Dictionary<long, int> cellIndex = new Dictionary<long, int>();
        static readonly List<(Vector3 sum, float w, int n, bool battle, float newest)> cells = new List<(Vector3, float, int, bool, float)>();
        static readonly List<Health> drop = new List<Health>();
        static readonly RaycastHit[] rayBuf = new RaycastHit[8];
        static bool hooked;

        /// <summary>Contacts reported by aircraft and drones over the battle (for the auto-test log).</summary>
        public static int AirReports, DroneReports, BattleReports;

        public static IReadOnlyList<Hot> Hots(Team t) => hots[(int)t];
        public static int Known(Team t) => seen[(int)t].Count;

        public static void Reset()
        {
            for (int t = 1; t <= 2; t++) { seen[t].Clear(); hots[t].Clear(); }
            AirReports = DroneReports = BattleReports = 0;
            if (!hooked)
            {
                Health.AnyDamage += OnDamage;
                hooked = true;
            }
        }

        static Team Other(Team t) => t == Team.Blue ? Team.Red : Team.Blue;

        /// <summary>'observer' now knows where 'enemy' is.</summary>
        public static void Report(Team observer, Health enemy, bool battle, bool fromAir = false)
        {
            if (observer == Team.None || enemy == null || !enemy.Alive || enemy.team == observer || enemy.IsDrone) return;
            if (enemy.cls == UnitClass.Air && enemy.Airborne) return;          // planes in the sky are not a ground objective
            var d = seen[(int)observer];
            if (!d.TryGetValue(enemy, out var c)) d[enemy] = c = new Contact();
            bool stillFighting = c.battle && Time.time - c.time < 10f;
            c.pos = enemy.transform.position;
            c.battle = battle || stillFighting;
            c.time = Time.time;
            c.air |= fromAir;
        }

        static void OnDamage(Health victim, DamageInfo d, float dmg)
        {
            var a = d.attacker;
            if (a == null || victim == null || !Health.Enemies(a.team, victim.team)) return;
            Report(victim.team, a, true);
            Report(a.team, victim, true);
            BattleReports++;
        }

        static float Weight(Health h) => h.cls == UnitClass.Mech ? 6f : h.cls == UnitClass.Ground ? 2.5f : h.cls == UnitClass.Air ? 0.5f : 1f;

        /// <summary>Once a second: aircraft and drone sensors sweep, stale contacts fade, hotspots are rebuilt.</summary>
        public static void Tick()
        {
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var u = all[i];
                if (!u.Alive || u.team == Team.None) continue;
                if (u.IsDrone)
                {
                    if (u.Drone.Sensing) DroneSweep(u);
                }
                else if (u.cls == UnitClass.Air && u.Airborne) AirSweep(u);
            }
            for (int t = 1; t <= 2; t++) Rebuild((Team)t);
        }

        static void AirSweep(Health plane)
        {
            Vector3 p = plane.transform.position;
            var all = Health.All;
            float r2 = AirRange * AirRange;
            for (int i = 0; i < all.Count; i++)
            {
                var e = all[i];
                if (!e.Alive || !Health.Enemies(e.team, plane.team) || e.IsDrone || e.Airborne) continue;
                Vector3 q = e.transform.position;
                float dx = q.x - p.x, dz = q.z - p.z;
                if (dx * dx + dz * dz > r2) continue;
                Report(plane.team, e, false, true);
                AirReports++;
            }
        }

        static void DroneSweep(Health drone)
        {
            Vector3 eye = drone.Center + Vector3.down * 0.3f;
            float range = drone.Drone.sensorRange;
            var all = Health.All;
            int rays = 0;
            for (int i = 0; i < all.Count && rays < 14; i++)
            {
                var e = all[i];
                if (!e.Alive || !Health.Enemies(e.team, drone.team) || e.IsDrone || e.Airborne) continue;
                Vector3 c = e.Center;
                Vector3 d = c - eye;
                float dist = d.magnitude;
                if (dist > range) continue;
                // already fresh in our picture: no need to spend a ray on it
                if (seen[(int)drone.team].TryGetValue(e, out var known) && Time.time - known.time < 2f) continue;
                rays++;
                if (!Clear(eye, d / dist, dist - e.Radius - 0.5f)) continue;
                Report(drone.team, e, false, true);
                DroneReports++;
            }
        }

        static bool Clear(Vector3 from, Vector3 dir, float len)
        {
            if (len <= 0.5f) return true;
            int n = Physics.RaycastNonAlloc(from, dir, rayBuf, len, ~0, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var h = Health.Of(rayBuf[i].collider);
                if (h != null) continue;                // units don't block the view
                return false;
            }
            return true;
        }

        static void Rebuild(Team t)
        {
            var d = seen[(int)t];
            drop.Clear();
            float now = Time.time;
            foreach (var kv in d)
                if (kv.Key == null || !kv.Key.Alive || now - kv.Value.time > MaxAge) drop.Add(kv.Key);
            foreach (var h in drop) d.Remove(h);

            cellIndex.Clear();
            cells.Clear();
            foreach (var kv in d)
            {
                var c = kv.Value;
                long key = ((long)Mathf.FloorToInt(c.pos.x / Cell) << 32) ^ (uint)Mathf.FloorToInt(c.pos.z / Cell);
                float fresh = 1f - (now - c.time) / MaxAge;
                float w = Weight(kv.Key) * (0.35f + 0.65f * fresh);
                if (!cellIndex.TryGetValue(key, out int idx))
                {
                    cellIndex[key] = idx = cells.Count;
                    cells.Add((Vector3.zero, 0f, 0, false, -999f));
                }
                var e = cells[idx];
                e.sum += c.pos * w;
                e.w += w;
                e.n++;
                e.battle |= c.battle && now - c.time < 12f;
                e.newest = Mathf.Max(e.newest, c.time);
                cells[idx] = e;
            }
            var list = hots[(int)t];
            list.Clear();
            foreach (var e in cells)
                if (e.w > 0f)
                    list.Add(new Hot { pos = e.sum / e.w, weight = e.w, count = e.n, battle = e.battle, age = now - e.newest });
            list.Sort((a, b) => b.weight.CompareTo(a.weight));
        }

        /// <summary>
        /// Best place for a unit at 'from' to go and fight: big, fresh, ongoing fights score higher, far ones lower.
        /// minWeight skips lone stragglers (a transport wants a real objective, not one wounded rifleman).
        /// </summary>
        public static bool Best(Team t, Vector3 from, out Hot best, float minWeight = 0f, float distScale = 700f)
        {
            best = default;
            float bs = 0f;
            var list = hots[(int)t];
            for (int i = 0; i < list.Count; i++)
            {
                var h = list[i];
                if (h.weight < minWeight) continue;
                float dist = AIUtil.Flat(h.pos - from).magnitude;
                float s = h.weight * (h.battle ? 1.6f : 1f) * (1f - 0.6f * h.age / MaxAge) / (1f + dist / distScale);
                if (s > bs) { bs = s; best = h; }
            }
            return bs > 0f;
        }

        /// <summary>Nearest known enemy position (any weight), for units that just want the closest fight.</summary>
        public static bool Nearest(Team t, Vector3 from, out Hot near)
        {
            near = default;
            float bd = float.MaxValue;
            var list = hots[(int)t];
            for (int i = 0; i < list.Count; i++)
            {
                float d = AIUtil.Flat(list[i].pos - from).sqrMagnitude;
                if (d < bd) { bd = d; near = list[i]; }
            }
            return bd < float.MaxValue;
        }
    }
}
