using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Dominion
{
    /// <summary>
    /// War mode: spawns two armies of 50, 100 or 200 per side (half infantry, a quarter tanks and transports, a quarter
    /// aircraft, up to 2 mechs) in the generated city's staging parks, runs the countdown, tracks the front lines, cover
    /// and kills, decides the winner and draws the battle HUD (team strength, kill feed, unit markers, city minimap,
    /// countdown with the map's name and the victory screen). Every unit is AI-controlled except whatever the player is in.
    /// </summary>
    [DefaultExecutionOrder(-150)]
    public class WarManager : MonoBehaviour
    {
        [System.Serializable]
        public class PrefabEntry
        {
            public string key;
            public GameObject prefab;
        }

        public static WarManager Instance { get; private set; }
        public List<PrefabEntry> prefabs = new List<PrefabEntry>();
        public float countdown = 5f;
        public Team playerTeam = Team.Blue;
        public float timeLimit = 20f * 60f;
        public float airBound = 1500f;

        enum Phase { Countdown, Fighting, Over }
        Phase phase = Phase.Countdown;
        float clock, fightT, statsT, fightFlash, intelT;
        public bool Fighting => phase != Phase.Countdown;
        public bool Over => phase == Phase.Over;
        public float CountdownLeft => Mathf.Max(0f, countdown - clock);
        public Team Winner { get; private set; }
        public float BattleTime => fightT;

        public readonly List<CoverSpot> Cover = new List<CoverSpot>();
        public readonly List<Health> Units = new List<Health>();
        readonly List<SoldierController> blueSoldiers = new List<SoldierController>();
        readonly List<(AircraftVehicle plane, float speed)> airborne = new List<(AircraftVehicle, float)>();
        readonly float[] front = new float[3];
        readonly Dictionary<Team, int> kills = new Dictionary<Team, int> { { Team.Blue, 0 }, { Team.Red, 0 } };
        struct FeedLine { public string text; public float time; }
        readonly List<FeedLine> feed = new List<FeedLine>();
        public int PlayerKills { get; private set; }
        GameDirector director;
        Camera cam;
        CityGenerator city;
        /// <summary>Units each side started with.</summary>
        public int ArmySize { get; private set; } = 50;
        readonly Dictionary<long, List<CoverSpot>> coverGrid = new Dictionary<long, List<CoverSpot>>();
        const float CoverCell = 40f;

        // ------------------------------------------------------------------ geometry helpers (Blue attacks +z)
        /// <summary>Spawn Blue in the north instead (-warswap: checks the AI has no side bias).</summary>
        [System.NonSerialized] public bool swapSides;
        bool North(Team t) => (t == Team.Red) != swapSides;
        public Vector3 Forward(Team t) => North(t) ? Vector3.back : Vector3.forward;
        public Vector3 OwnBase(Team t)
        {
            float z = city ? -city.Plan.StagingS.center.y : 330f;
            return North(t) ? new Vector3(0f, 0f, z) : new Vector3(0f, 0f, -z);
        }
        public Vector3 EnemyBase(Team t) => OwnBase(t == Team.Red ? Team.Blue : Team.Red);
        /// <summary>How far forward the team's infantry line is (along its attack direction).</summary>
        public float FrontLine(Team t) => front[(int)t];
        Vector3 Mirror(Vector3 p, Team t) => North(t) ? new Vector3(-p.x, p.y, -p.z) : p;
        float Yaw(Team t) => North(t) ? 180f : 0f;

        // ------------------------------------------------------------------ setup
        void Awake()
        {
            Instance = this;
            Time.timeScale = 1f;
            director = FindFirstObjectByType<GameDirector>();
            city = CityGenerator.Instance;
            if (city) airBound = 3700f;
            Health.ClearCache();
            Intel.Reset();
            DroneUnit.ResetStats();
            TransportBay.ResetStats();
            Health.TotalHealed = 0f;
            swapSides = System.Array.IndexOf(System.Environment.GetCommandLineArgs(), "-warswap") >= 0;
            // mechs: up to two per side, never two of a kind on one side
            string[] mechs = { "Mech_Aegis", "Mech_Halberd", "Mech_Thunderhead" };
            int ma = Random.Range(0, 3), mb = (ma + Random.Range(1, 3)) % 3;
            blueMech = new[] { mechs[ma], mechs[(ma + 1) % 3] };
            redMech = new[] { mechs[mb], mechs[(mb + 2) % 3] };
            BuildCover();
            SpawnArmy(Team.Blue);
            SpawnArmy(Team.Red);
            if (city && System.Array.IndexOf(System.Environment.GetCommandLineArgs(), "-noships") < 0)
            {
                SpawnAirships(Team.Blue);
                SpawnAirships(Team.Red);
            }
            for (int t = 1; t <= 2; t++)
            {
                var c0 = Count((Team)t);
                groundStart[t] = c0.soldiers + c0.ground + c0.mech;
            }
            Paratrooper.ResetStats();
            if (director)
            {
                director.warMode = true;
                director.playerTeam = playerTeam;
                director.soldiers = blueSoldiers.ToArray();
            }
            Health.AnyDeath += OnDeath;
            UpdateFront();
            // draw (and animate) only the units the player can actually see
            if (GetComponent<UnitLOD>() == null) gameObject.AddComponent<UnitLOD>();
        }

        void OnDestroy()
        {
            Health.AnyDeath -= OnDeath;
            if (Instance == this) Instance = null;
        }

        public GameObject PrefabFor(string key) => Prefab(key);

        GameObject Prefab(string key)
        {
            foreach (var e in prefabs) if (e.key == key) return e.prefab;
            Debug.LogError("[War] missing prefab " + key);
            return null;
        }

        void BuildCover()
        {
            Cover.Clear();
            coverGrid.Clear();
            foreach (var co in FindObjectsByType<CoverObject>(FindObjectsSortMode.InstanceID))
            {
                var bc = co.GetComponent<BoxCollider>();
                if (bc == null) continue;
                Transform t = co.transform;
                BoxCover(t.TransformPoint(bc.center), Vector3.Scale(bc.size, t.lossyScale), t.rotation);
            }
            if (city)
                foreach (var (c, size, yaw) in city.CoverBoxes)
                    BoxCover(c, size, Quaternion.Euler(0f, yaw, 0f));
        }

        /// <summary>Hide spots along both long faces of a box (near each end) and the peek spot just past each end.</summary>
        void BoxCover(Vector3 c, Vector3 size, Quaternion rot)
        {
            if (size.y < 1.6f) return;                              // too low to hide a standing soldier
            bool alongX = size.x >= size.z;
            float halfLen = (alongX ? size.x : size.z) * 0.5f, halfDepth = (alongX ? size.z : size.x) * 0.5f;
            Vector3 ax = rot * (alongX ? Vector3.right : Vector3.forward);
            Vector3 nz = rot * (alongX ? Vector3.forward : Vector3.right);
            foreach (float face in new[] { -1f, 1f })
            {
                Vector3 n = AIUtil.Flat(nz * face).normalized;
                Vector3 basePos = AIUtil.Flat(c) + n * (halfDepth + 0.75f);
                foreach (float end in new[] { -1f, 1f })
                {
                    Vector3 hide = basePos + ax * end * Mathf.Max(0f, halfLen - 0.7f);
                    Vector3 peek = basePos + ax * end * (halfLen + 0.95f);
                    TryAddSpot(hide, peek, n, c);
                }
            }
            // big buildings: extra spots along the long faces
            if (halfLen > 12f)
                foreach (float face in new[] { -1f, 1f })
                {
                    Vector3 n = AIUtil.Flat(nz * face).normalized;
                    Vector3 basePos = AIUtil.Flat(c) + n * (halfDepth + 0.75f);
                    for (float u = -halfLen + 8f; u < halfLen - 7f; u += 9f)
                        TryAddSpot(basePos + ax * u, basePos + ax * (Mathf.Sign(u) * (halfLen + 0.95f)), n, c);
                }
        }

        void TryAddSpot(Vector3 hide, Vector3 peek, Vector3 n, Vector3 wall)
        {
            hide.y = WorldGround.Height(hide.x, hide.z);
            peek.y = WorldGround.Height(peek.x, peek.z);
            // not inside another wall
            if (Physics.CheckSphere(hide + Vector3.up * 1.1f, 0.45f, ~0, QueryTriggerInteraction.Ignore)) return;
            if (Physics.CheckSphere(peek + Vector3.up * 1.1f, 0.45f, ~0, QueryTriggerInteraction.Ignore)) return;
            if (CityNav.Active && CityNav.Clearance(new Vector2(hide.x, hide.z)) < 0.3f) return;
            var spot = new CoverSpot { hide = hide, peek = peek, normal = n, wall = wall };
            Cover.Add(spot);
            long k = CKey(hide);
            if (!coverGrid.TryGetValue(k, out var l)) coverGrid[k] = l = new List<CoverSpot>();
            l.Add(spot);
        }

        static long CKey(Vector3 p) => ((long)Mathf.FloorToInt(p.x / CoverCell) << 32) ^ (uint)Mathf.FloorToInt(p.z / CoverCell);

        /// <summary>Cover spots whose hide point lies within 'radius' of p (grid lookup; the list is reused by the caller).</summary>
        public void CoverNear(Vector3 p, float radius, List<CoverSpot> into)
        {
            into.Clear();
            int x0 = Mathf.FloorToInt((p.x - radius) / CoverCell), x1 = Mathf.FloorToInt((p.x + radius) / CoverCell);
            int z0 = Mathf.FloorToInt((p.z - radius) / CoverCell), z1 = Mathf.FloorToInt((p.z + radius) / CoverCell);
            float r2 = radius * radius;
            for (int z = z0; z <= z1; z++)
                for (int x = x0; x <= x1; x++)
                    if (coverGrid.TryGetValue(((long)x << 32) ^ (uint)z, out var l))
                        foreach (var c in l)
                        {
                            float dx = c.hide.x - p.x, dz = c.hide.z - p.z;
                            if (dx * dx + dz * dz <= r2) into.Add(c);
                        }
        }

        Health Spawn(string key, Vector3 pos, float yaw, Team team)
        {
            var prefab = Prefab(key);
            if (prefab == null) return null;
            var go = Instantiate(prefab, pos, Quaternion.Euler(0f, yaw, 0f));
            go.name = $"{team} {key}";
            var v = go.GetComponent<Vehicle>();
            var sc = go.GetComponent<SoldierController>();
            var dr = go.GetComponent<DroneUnit>();
            var ship = go.GetComponent<Airship>();
            var h = go.AddComponent<Health>();
            string label = v ? v.displayName : dr ? dr.displayName : ship ? ship.displayName : "Rifleman";
            h.Init(team, key, label);
            if (ship)
            {
                ship.team = team;
                ship.health = h;
                h.Died += d => ship.Die(d);
            }
            if (dr)
            {
                dr.team = team;
                dr.health = h;
                h.Died += d => dr.Die(d);
            }
            if (v)
            {
                v.team = team;
                v.health = h;
                h.Died += d => v.Die(d);
            }
            if (sc)
            {
                sc.health = h;
                h.Died += _ => sc.Die();
            }
            TeamPaint.Apply(go, team, sc != null);
            var mc = go.GetComponent<MechKit.MechController>();
            if (mc) mc.Faction = team == Team.Blue ? MechKit.MechFaction.SkyLegion : MechKit.MechFaction.StormCorsairs;
            Units.Add(h);
            return h;
        }

        float GroundY(string key)
        {
            var p = Prefab(key);
            var v = p ? p.GetComponent<Vehicle>() : null;
            return v ? v.RestHeight + 0.02f : 0.02f;
        }

        /// <summary>Lift a spawn point onto the ground (terrain or flat baseplate).</summary>
        static Vector3 OnGround(Vector3 p, float lift) => new Vector3(p.x, WorldGround.Height(p.x, p.z) + lift, p.z);

        void SpawnArmy(Team team)
        {
            if (city == null) { SpawnBattalion(team, Vector2.zero, 1f, 0, 0, true, true, null); return; }
            var scatter = new Scatter(this, team, city.Seed * 7 + (int)team);
            int k = city.Battalions;
            ArmySize = k * 50;
            // battalions of 50 side by side (and two rows for the largest armies), all in the side's staging park
            float front = city.Plan.StagingS.yMax;            // south frame: the park's edge toward the city
            float dz = front - 30f - (-235f);
            Vector2[] offs = k == 1 ? new[] { Vector2.zero } : k == 2 ? new[] { new Vector2(-215f, 0f), new Vector2(215f, 0f) }
                : new[] { new Vector2(-215f, 0f), new Vector2(215f, 0f), new Vector2(-215f, -245f), new Vector2(215f, -245f) };
            float sx = k == 1 ? 1f : 0.85f;
            for (int b = 0; b < offs.Length; b++)
                SpawnBattalion(team, new Vector2(offs[b].x, offs[b].y + dz), sx, b, b, b < 2, b == 0, scatter);
            if (k == 4)
            {
                // 4 x 49 + 2 mechs = 198: one more tank and one more fighter make 200
                Vector3 p = Mirror(new Vector3(0f, 0f, -292f + dz - 245f), team);
                float ty = Yaw(team);
                if (scatter.Vehicle(VehicleExtents("Tank_Medium"), GroundY("Tank_Medium"), out Vector3 sp, out float sy)) { p = sp; ty = sy; }
                else p = OnGround(p, GroundY("Tank_Medium"));
                var h = Spawn("Tank_Medium", p, ty, team);
                if (h) h.gameObject.AddComponent<GroundAI>().Init(h, GroundAI.Role.Tank, p.x);
                SpawnAirborne(team, "Aircraft_Saber", airIndex++);
            }
        }

        int airIndex;

        void SpawnAirborne(Team team, string key, int i)
        {
            var prefab = Prefab(key);
            bool prop = prefab && prefab.GetComponent<AircraftVehicle>().hasProp;
            Vector3 p;
            if (city)
            {
                float alt = prop ? 240f + (i % 2) * 40f : 340f + (i % 3) * 60f;
                p = new Vector3(-1250f + (i % 12) * 225f, 0f, -(1900f + (i / 12) * 180f));
                p = Mirror(p, team);
                p.y = WorldGround.Top(p.x, p.z) + alt;
            }
            else
            {
                float alt = prop ? 220f + (i % 2) * 40f : 300f + (i % 3) * 60f;
                p = Mirror(new Vector3(-450f + i * 100f, alt, -900f - (i % 2) * 140f), team);
            }
            var h = Spawn(key, p, Yaw(team), team);
            if (h == null) return;
            var av = (AircraftVehicle)h.Vehicle;
            airborne.Add((av, prop ? av.maxSpeed * 0.85f : 160f));
            h.gameObject.AddComponent<PlaneAI>().Init(h, false, 0f);
        }

        int parkedIndex;

        /// <summary>One battalion of 50 (minus its mech): 25 infantry, 12 ground vehicles, 10 aircraft in the air and 2 on
        /// the airfield; 'mech' adds one of the side's (at most two) mechs. Laid out in the south frame and mirrored north.</summary>
        Vector3 VehicleExtents(string key)
        {
            var pf = Prefab(key);
            var v = pf ? pf.GetComponent<Vehicle>() : null;
            return v ? v.localBounds.extents : new Vector3(1.6f, 1.2f, 3.5f);
        }

        /// <summary>
        /// Spawn spots for one side: along the streets of its own half of the city (not the hills, fields, airfields or
        /// highways; a no-man's-land strip in the middle), shuffled. Every spot is checked against the navigation
        /// clearance grid, the physics world (no building, prop or unit overlapping it) and the units already placed.
        /// </summary>
        class Scatter
        {
            readonly List<(Vector3 p, Vector3 dir, Vector3 side, float hw)> spots = new List<(Vector3, Vector3, Vector3, float)>();
            readonly List<Vector3> taken = new List<Vector3>();
            int next;

            public Scatter(WarManager w, Team team, int seed)
            {
                var plan = w.city.Plan;
                bool north = w.North(team);
                Vector3 fw = w.Forward(team);
                float lim = plan.CityR * 0.97f;
                foreach (var e in plan.Edges)
                {
                    if (e.zone == Zone.Staging || e.zone == Zone.Rural || e.zone == Zone.Airfield || e.cls == RoadClass.Highway) continue;
                    Vector2 a = plan.Nodes[e.a].p, b = plan.Nodes[e.b].p, d = b - a;
                    float L = d.magnitude;
                    if (L < 26f) continue;
                    d /= L;
                    for (float t = 13f; t < L - 13f; t += 34f)
                    {
                        Vector2 p = a + d * t;
                        if (p.magnitude > lim) continue;
                        if (north ? p.y < 140f : p.y > -140f) continue;
                        Vector3 dir = new Vector3(d.x, 0f, d.y);
                        if (Vector3.Dot(dir, fw) < 0f) dir = -dir;
                        spots.Add((new Vector3(p.x, 0f, p.y), dir, Vector3.Cross(Vector3.up, dir), e.halfWidth));
                    }
                }
                var rng = new System.Random(seed);
                for (int i = spots.Count - 1; i > 0; i--) { int j = rng.Next(i + 1); (spots[i], spots[j]) = (spots[j], spots[i]); }
            }

            bool Free(Vector3 p, float r)
            {
                foreach (var q in taken) if ((q - p).sqrMagnitude < r * r) return false;
                return true;
            }

            static float Ground(Vector3 p) =>
                AIUtil.Cast(p + Vector3.up * 8f, Vector3.down, 20f, null, out RaycastHit h) && Health.Of(h.collider) == null ? h.point.y : WorldGround.Height(p.x, p.z);

            /// <summary>A lane of a street with room for a vehicle of these half-extents.</summary>
            public bool Vehicle(Vector3 ext, float lift, out Vector3 pos, out float yaw)
            {
                while (next < spots.Count)
                {
                    var s = spots[next++];
                    Vector3 p = s.p + s.side * Mathf.Min(s.hw * 0.45f, 2.5f);
                    if (!Free(p, 14f)) continue;
                    if (CityNav.Active && CityNav.Clearance(new Vector2(p.x, p.z), true) < ext.x + 0.4f) continue;
                    p.y = Ground(p);
                    if (Physics.CheckBox(p + Vector3.up * (lift + ext.y + 0.45f), new Vector3(ext.x + 0.2f, ext.y, ext.z + 0.3f),
                            Quaternion.LookRotation(s.dir), ~0, QueryTriggerInteraction.Ignore)) continue;
                    taken.Add(p);
                    pos = p + Vector3.up * lift;
                    yaw = Mathf.Atan2(s.dir.x, s.dir.z) * Mathf.Rad2Deg;
                    return true;
                }
                pos = default;
                yaw = 0f;
                return false;
            }

            /// <summary>A sidewalk spot for a squad.</summary>
            public bool NextSquad(out Vector3 center, out Vector3 dir)
            {
                while (next < spots.Count)
                {
                    var s = spots[next++];
                    Vector3 p = s.p + s.side * (s.hw + 1.6f) * (next % 2 == 0 ? 1f : -1f);
                    if (!Free(p, 18f)) continue;
                    if (CityNav.Active && CityNav.Clearance(new Vector2(p.x, p.z)) < 0.8f) continue;
                    center = p;
                    dir = s.dir;
                    return true;
                }
                center = default;
                dir = Vector3.forward;
                return false;
            }

            /// <summary>One squad member's spot in the wedge, nudged clear of walls, props and other soldiers.</summary>
            public Vector3 Soldier(Vector3 center, Vector3 dir, Vector2 offset)
            {
                Vector3 side = Vector3.Cross(Vector3.up, dir);
                for (int tries = 0; tries < 8; tries++)
                {
                    Vector3 p = center + side * offset.x + dir * offset.y;
                    if (tries > 0) p += new Vector3(Random.Range(-1f, 1f), 0f, Random.Range(-1f, 1f)) * (0.8f * tries);
                    if (CityNav.Active && CityNav.Clearance(new Vector2(p.x, p.z)) < 0.5f) continue;
                    p.y = Ground(p);
                    if (Physics.CheckCapsule(p + Vector3.up * 0.5f, p + Vector3.up * 1.6f, 0.36f, ~0, QueryTriggerInteraction.Ignore)) continue;
                    if (!Free(p, 1.1f)) continue;
                    taken.Add(p);
                    return p + Vector3.up * 0.02f;
                }
                center.y = Ground(center);
                taken.Add(center);
                return center + Vector3.up * 0.02f;
            }
        }

        void SpawnBattalion(Team team, Vector2 off, float sx, int index, int mechIndex, bool mech, bool playerSquad, Scatter scatter)
        {
            float yaw = Yaw(team);
            Vector3 Pt(float x, float z) => Mirror(new Vector3(off.x + x * sx, 0f, off.y + z), team);
            // ---- infantry: 5 squads of 5 on lanes across the front; the middle of each squad's wedge carries rifle grenades
            float[] lanes = { -160f, -80f, 0f, 80f, 160f };
            Vector2[] wedge = { new Vector2(0f, 0f), new Vector2(-3f, -2.5f), new Vector2(3f, -2.5f), new Vector2(-6f, -5f), new Vector2(6f, -5f) };
            int order = index * 25;
            // the player's squad (centre lane of the first battalion) spawns first so the player starts as its leader
            int[] laneOrder = { 2, 1, 3, 0, 4 };
            _ = playerSquad;
            foreach (int li in laneOrder)
            {
                Vector3 sqC = default, sqD = Forward(team);
                bool scattered = false;               // infantry start on the staging fields
                for (int k = 0; k < wedge.Length; k++)
                {
                    string key = (order++ % 2 == 0) ? "Soldier_Male" : "Soldier_Female";
                    Vector3 p = scattered ? scatter.Soldier(sqC, sqD, wedge[k]) : OnGround(Pt(lanes[li] + wedge[k].x, -235f + wedge[k].y), 0.02f);
                    var h = Spawn(key, p, yaw, team);
                    if (h == null) continue;
                    var sc = h.Soldier;
                    sc.displayName = k == 2 ? "AT Rifleman" : k == 0 ? "Squad Leader" : "Rifleman";
                    h.unitName = sc.displayName;
                    var ai = h.gameObject.AddComponent<SoldierAI>();
                    ai.Init(h, p.x, k == 2);
                    soldierAIs.Add(ai);
                    if (team == Team.Blue) blueSoldiers.Add(sc);
                }
            }
            // ---- ground vehicles (12)
            var ground = new (string key, float x, float z, GroundAI.Role role)[]
            {
                ("Tank_Medium", -110f, -285f, GroundAI.Role.Tank), ("Tank_Medium", 0f, -292f, GroundAI.Role.Tank), ("Tank_Medium", 110f, -285f, GroundAI.Role.Tank),
                ("Tank_Heavy", -55f, -298f, GroundAI.Role.Tank), ("Tank_Heavy", 55f, -298f, GroundAI.Role.Tank),
                ("Tank_Scout", -235f, -270f, GroundAI.Role.Scout), ("Tank_Scout", 235f, -270f, GroundAI.Role.Scout),
                ("Vehicle_Carrier", -32f, -266f, GroundAI.Role.APC), ("Vehicle_Bastion", 32f, -266f, GroundAI.Role.APC),
                ("Vehicle_Mule", 0f, -335f, GroundAI.Role.Transport),
                ("Tank_AntiAir", -75f, -338f, GroundAI.Role.AntiAir), ("Tank_Artillery", 75f, -362f, GroundAI.Role.Artillery),
            };
            foreach (var g in ground)
            {
                Vector3 p;
                float vyaw = yaw;
                // tanks scatter through their half of the city; transports stay on the fields with the infantry
                if (scatter == null || !g.key.StartsWith("Tank_") || !scatter.Vehicle(VehicleExtents(g.key), GroundY(g.key), out p, out vyaw))
                    p = OnGround(Pt(g.x, g.z), GroundY(g.key));
                var h = Spawn(g.key, p, vyaw, team);
                if (h == null) continue;
                // troop transports: seats for a squad or two and a rack of repair drones
                if (city && TransportLoad(g.key, out int seats, out string[] droneKeys))
                    h.gameObject.AddComponent<TransportBay>().Init(h.Vehicle, h, seats, droneKeys);
                h.gameObject.AddComponent<GroundAI>().Init(h, g.role, p.x);
            }
            // ---- mech (at most two per side, different types)
            if (mech)
            {
                string key = (team == Team.Blue ? blueMech : redMech)[mechIndex % 2];
                Vector3 p = OnGround(Pt(0f, -255f), 0.02f);
                var h = Spawn(key, p, yaw, team);
                if (h) h.gameObject.AddComponent<MechAI>().Init(h);
            }
            // ---- aircraft: 10 airborne in the stack over their own side, 2 parked on the airfield (they take off later)
            string[] air = { "Aircraft_Kestrel", "Aircraft_Falcon", "Aircraft_Falcon", "Aircraft_Lancer", "Aircraft_Lancer",
                             "Aircraft_Saber", "Aircraft_Saber", "Aircraft_Saber", "Aircraft_Wraith", "Aircraft_Wraith" };
            for (int i = 0; i < air.Length; i++) SpawnAirborne(team, air[i], airIndex++);
            string[] parked = { "Aircraft_Kestrel", "Aircraft_Lancer" };
            for (int i = 0; i < parked.Length; i++)
            {
                int j = parkedIndex++;
                Vector3 p;
                if (city)
                {
                    // two columns at the runway's near end, one row behind another; the front row goes first
                    Vector2 air0 = city.Plan.AirS;
                    p = new Vector3(air0.x - 14f + (j % 2) * 28f, 0f, air0.y - CityPlan.AirHalfLen + 170f - (j / 2) * 45f);
                    p = Mirror(p, team);
                    p.y = city.AirfieldHeight(North(team)) + GroundY(parked[i]);
                }
                else p = Mirror(new Vector3(440f + i * 22f, GroundY(parked[i]), -1240f), team);
                var h = Spawn(parked[i], p, yaw, team);
                if (h == null) continue;
                h.gameObject.AddComponent<PlaneAI>().Init(h, true, 25f + j * 14f + (team == Team.Red ? 4f : 0f));
            }
        }

        string[] blueMech, redMech;
        readonly List<SoldierAI> soldierAIs = new List<SoldierAI>();
        readonly List<SoldierAI> riderPool = new List<SoldierAI>();

        /// <summary>Seats and drone supply of each transport type.</summary>
        static bool TransportLoad(string key, out int seats, out string[] droneKeys)
        {
            switch (key)
            {
                case "Vehicle_Carrier": seats = 8; droneKeys = new[] { "Drone_Mender", "Drone_Wasp", "Drone_Wasp" }; return true;
                case "Vehicle_Bastion": seats = 5; droneKeys = new[] { "Drone_Kite", "Drone_Wasp" }; return true;
                case "Vehicle_Mule": seats = 10; droneKeys = new[] { "Drone_Mender", "Drone_Kite", "Drone_Wasp", "Drone_Mender" }; return true;
            }
            seats = 0;
            droneKeys = null;
            return false;
        }

        /// <summary>Each side's air fleet: the Leviathan flagship over its staging area and two Sentinels guarding its beams.</summary>
        void SpawnAirships(Team team)
        {
            Vector3 b = OwnBase(team), f = Forward(team), side = Vector3.Cross(Vector3.up, f);
            var lead = SpawnShip("Airship_Leviathan", b + f * 150f, team, null, default, "Leviathan");
            if (lead == null) return;
            SpawnShip("Skyship_Sentinel", b + f * 70f + side * 270f, team, lead, new Vector3(270f, 0f, -80f), "Sentinel I");
            SpawnShip("Skyship_Sentinel", b + f * 70f - side * 270f, team, lead, new Vector3(-270f, 0f, -80f), "Sentinel II");
        }

        Airship SpawnShip(string key, Vector3 pos, Team team, Airship leader, Vector3 offset, string name)
        {
            var h = Spawn(key, pos, Yaw(team), team);
            if (h == null || h.Ship == null) return null;
            var a = h.Ship;
            a.displayName = name;
            h.unitName = name;
            a.leader = leader;
            a.stationOffset = offset;
            a.Place(pos, Yaw(team));
            a.Init(team, new[] { Prefab("Soldier_Male"), Prefab("Soldier_Female") });
            return a;
        }

        public IEnumerable<Airship> Ships(Team team)
        {
            foreach (var a in Airship.All) if (a && a.team == team && !a.Destroyed) yield return a;
        }

        public int ShipCount(Team team)
        {
            int n = 0;
            foreach (var a in Airship.All) if (a && a.team == team && !a.Destroyed) n++;
            return n;
        }

        /// <summary>A soldier for the player on one of the side's airships (deck spawn).</summary>
        public SoldierController SpawnPlayerOnShip(Airship ship)
        {
            if (ship == null || ship.Destroyed) return null;
            var h = Spawn("Soldier_Male", ship.SpawnPoint(), ship.transform.eulerAngles.y, ship.team);
            if (h == null || h.Soldier == null) return null;
            h.unitName = h.Soldier.displayName = "Deck Gunner";
            if (ship.team == Team.Blue) blueSoldiers.Add(h.Soldier);
            return h.Soldier;
        }

        /// <summary>A drone of 'team' at pos (launched from a transport's hatch).</summary>
        public Health SpawnDrone(string key, Vector3 pos, float yaw, Team team) => Spawn(key, pos, yaw, team);

        /// <summary>
        /// Where a unit of 'team' at 'pos' should push to when it has nothing to shoot at: the best place its side knows
        /// the enemy to be (Intel: aircraft, drones and fighting), else the enemy's staging area, and once that is taken,
        /// the nearest enemy anywhere. Units never stop advancing while the enemy has anything left.
        /// </summary>
        public Vector3 Objective(Team team, Vector3 pos)
        {
            if (Intel.Best(team, pos, out var hot)) return hot.pos;
            Vector3 eb = EnemyBase(team);
            if (AIUtil.Flat(eb - pos).magnitude > 120f) return eb;
            var n = NearestEnemy(team, pos);
            if (n) return n.transform.position;
            // only their airships left: get under the nearest one so the guns can reach it
            Airship best = null;
            float bd = float.MaxValue;
            foreach (var a in Airship.All)
                if (a && !a.Destroyed && Health.Enemies(a.team, team))
                {
                    float d = AIUtil.Flat(a.transform.position - pos).sqrMagnitude;
                    if (d < bd) { bd = d; best = a; }
                }
            if (best) { Vector3 p = best.transform.position; p.y = 0f; return p; }
            return eb;
        }

        // ------------------------------------------------------------------ paratroopers
        readonly int[] groundStart = new int[3];
        float paraCheckT;

        /// <summary>A soldier out of an airship's side door, under a ParachuteKit canopy, steering for 'target'.</summary>
        public void SpawnParatrooper(Airship ship, Vector3 pos, Vector3 target)
        {
            string key = Random.value < 0.5f ? "Soldier_Male" : "Soldier_Female";
            var h = Spawn(key, pos, ship.transform.eulerAngles.y + 90f, ship.team);
            if (h == null || h.Soldier == null) return;
            bool at = Random.value < 0.2f;
            h.unitName = h.Soldier.displayName = at ? "AT Paratrooper" : "Paratrooper";
            var ai = h.gameObject.AddComponent<SoldierAI>();
            ai.Init(h, pos.x, at);
            soldierAIs.Add(ai);
            if (ship.team == Team.Blue)
            {
                blueSoldiers.Add(h.Soldier);
                if (director) director.AddSoldier(h.Soldier);
            }
            h.gameObject.AddComponent<Paratrooper>().Init(Prefab("Parachute"), target, ship.Velocity);
        }

        /// <summary>
        /// A side short of ground forces (under 45% of what it started with): the crews of its airships jump to reinforce it
        /// (they leave the ship's complement; no soldiers are added from nowhere).
        /// </summary>
        void Paradrops()
        {
            for (int t = 1; t <= 2; t++)
            {
                Team team = (Team)t;
                var c = Count(team);
                int ground = c.soldiers + c.ground + c.mech;
                if (ground >= groundStart[t] * 0.45f) continue;
                foreach (var a in Ships(team))
                {
                    if (a.Jumpers <= 0 || a.Dropping) continue;
                    // drop under the ship, nudged toward the nearest known fight but short of it
                    Vector3 p = a.transform.position;
                    p.y = 0f;
                    Vector3 tgt = p;
                    if (Intel.Best(team, p, out var hot, 2f, 400f))
                    {
                        Vector3 back = AIUtil.Flat(OwnBase(team) - hot.pos);
                        Vector3 stand = hot.pos + (back.sqrMagnitude > 1f ? back.normalized : Vector3.zero) * 150f;
                        tgt = Vector3.MoveTowards(p, stand, 110f);
                    }
                    a.OrderDrop(6, tgt);
                }
            }
        }

        /// <summary>
        /// Book riders for a transport: idle soldiers (not fighting, not wounded, not the player) that are still far from
        /// the fighting, the densest group nearest the transport first. Returns false if nobody is worth the trip.
        /// </summary>
        public bool FindRiders(Team team, Vector3 from, TransportBay bay, out Vector3 center)
        {
            center = from;
            riderPool.Clear();
            foreach (var ai in soldierAIs)
            {
                if (ai == null || !ai.Available || ai.Team != team) continue;
                Vector3 p = ai.transform.position;
                if (AIUtil.Flat(p - from).magnitude > 350f) continue;                   // fetch from nearby only
                if (AIUtil.Flat(Objective(team, p) - p).magnitude < 400f) continue;     // within a short walk of the fight: walk
                riderPool.Add(ai);
            }
            if (riderPool.Count == 0) return false;
            SoldierAI seed = null;
            float bs = 0f;
            foreach (var a in riderPool)
            {
                Vector3 p = a.transform.position;
                int n = 0;
                foreach (var b in riderPool) if ((b.transform.position - p).sqrMagnitude < 60f * 60f) n++;
                float sc = Mathf.Min(n, bay.Free) / (1f + AIUtil.Flat(p - from).magnitude / 350f);
                if (sc > bs) { bs = sc; seed = a; }
            }
            if (seed == null) return false;
            center = seed.transform.position;
            Vector3 c = center;
            riderPool.Sort((a, b) => (a.transform.position - c).sqrMagnitude.CompareTo((b.transform.position - c).sqrMagnitude));
            int want = bay.Free, got = 0;
            foreach (var a in riderPool)
            {
                if (got >= want || (a.transform.position - c).sqrMagnitude > 85f * 85f) break;
                a.BoardTransport(bay);
                got++;
            }
            if (got == 1 && AIUtil.Flat(c - from).magnitude > 200f)
            {
                riderPool[0].CancelRide();                  // a lone rifleman is not worth a long drive
                return false;
            }
            return got > 0;
        }

        public int DroneCount(Team team)
        {
            int n = 0;
            foreach (var h in Units) if (h && h.Alive && h.team == team && h.IsDrone) n++;
            return n;
        }

        // ------------------------------------------------------------------ battle loop
        void Update()
        {
            float dt = Time.deltaTime;
            if (cam == null) cam = Camera.main;
            if (phase == Phase.Countdown)
            {
                clock += dt;
                // aircraft hold their places in the sky until the start
                foreach (var (plane, _) in airborne) if (plane) plane.Body.isKinematic = true;
                if (clock >= countdown)
                {
                    phase = Phase.Fighting;
                    fightFlash = 1.4f;
                    foreach (var (plane, speed) in airborne) if (plane && !plane.Destroyed) plane.LaunchAirborne(speed, 0.85f);
                }
                return;
            }
            fightFlash -= dt;
            if (phase == Phase.Fighting) fightT += dt;
            statsT -= dt;
            if (statsT <= 0f)
            {
                statsT = 0.5f;
                UpdateFront();
                if (phase == Phase.Fighting) CheckVictory();
            }
            intelT -= dt;
            if (intelT <= 0f)
            {
                intelT = 1f;
                Intel.Tick();
            }
            paraCheckT -= dt;
            if (paraCheckT <= 0f && phase == Phase.Fighting && city)
            {
                paraCheckT = 4f;
                Paradrops();
            }
        }

        void UpdateFront()
        {
            for (int t = 1; t <= 2; t++)
            {
                Team team = (Team)t;
                Vector3 f = Forward(team);
                float sum = 0f;
                int n = 0;
                foreach (var h in Units)
                    if (h && h.Alive && h.team == team && h.cls == UnitClass.Soldier && h.gameObject.activeInHierarchy)
                    {
                        sum += Vector3.Dot(h.transform.position, f);
                        n++;
                    }
                front[t] = n > 0 ? sum / n : Vector3.Dot(EnemyBase(team), f);
                var c = Count(team);
                groundLeft[t] = c.soldiers + c.ground + c.mech;
            }
        }

        readonly int[] groundLeft = { 0, 50, 50 };

        /// <summary>The enemy of 'team' is down to its last few ground units: hunt them down wherever they are.</summary>
        public bool Endgame(Team team) => Fighting && groundLeft[team == Team.Red ? 1 : 2] <= Mathf.Max(8, ArmySize / 8);

        /// <summary>Closest living enemy ground unit (soldier, vehicle or mech), at any range.</summary>
        public Health NearestEnemy(Team team, Vector3 pos)
        {
            Health best = null;
            float bd = float.MaxValue;
            foreach (var h in Units)
            {
                if (!h || !h.Alive || !Health.Enemies(h.team, team) || h.cls == UnitClass.Air || !h.gameObject.activeInHierarchy) continue;
                float d = (h.transform.position - pos).sqrMagnitude;
                if (d < bd) { bd = d; best = h; }
            }
            return best;
        }

        public Vector3 SoldierCentroid(Team team, float laneX)
        {
            Vector3 sum = Vector3.zero, all = Vector3.zero;
            int n = 0, na = 0;
            foreach (var h in Units)
            {
                if (!h || !h.Alive || h.team != team || h.cls != UnitClass.Soldier || !h.gameObject.activeInHierarchy) continue;
                Vector3 p = h.transform.position;
                all += p;
                na++;
                if (Mathf.Abs(p.x - laneX) < 90f) { sum += p; n++; }
            }
            if (n > 0) return sum / n;
            if (na > 0) return all / na;
            return OwnBase(team);
        }

        public Vector3 ArmorCentroid(Team team)
        {
            Vector3 sum = Vector3.zero;
            int n = 0;
            foreach (var h in Units)
            {
                if (!h || !h.Alive || h.team != team || h.cls != UnitClass.Ground || h.armor != ArmorClass.Armored) continue;
                if (h.key == "Tank_Artillery" || h.key == "Tank_AntiAir") continue;
                sum += h.transform.position;
                n++;
            }
            return n > 0 ? sum / n : SoldierCentroid(team, 0f);
        }

        /// <summary>Can any unit of 'team' see this target (for artillery fire missions)?</summary>
        public bool Spotted(Health target, Team team)
        {
            Vector3 p = target.Center;
            foreach (var h in Units)
            {
                if (!h || !h.Alive || h.team != team || h.key == "Tank_Artillery") continue;
                float r = h.cls == UnitClass.Air ? 900f : 450f;
                if ((h.Center - p).sqrMagnitude < r * r) return true;
            }
            return false;
        }

        public (int soldiers, int ground, int air, int mech) Count(Team team)
        {
            int s = 0, g = 0, a = 0, m = 0;
            foreach (var h in Units)
            {
                if (!h || !h.Alive || h.team != team || h.IsDrone || h.IsAirship) continue;
                switch (h.cls)
                {
                    case UnitClass.Soldier: s++; break;
                    case UnitClass.Ground: g++; break;
                    case UnitClass.Air: a++; break;
                    case UnitClass.Mech: m++; break;
                }
            }
            return (s, g, a, m);
        }

        void CheckVictory()
        {
            var b = Count(Team.Blue);
            var r = Count(Team.Red);
            int bg = b.soldiers + b.ground + b.mech + ShipCount(Team.Blue), rg = r.soldiers + r.ground + r.mech + ShipCount(Team.Red);
            Team w = Team.None;
            if (bg == 0 && rg == 0) w = b.air >= r.air ? Team.Blue : Team.Red;
            else if (rg == 0) w = Team.Blue;
            else if (bg == 0) w = Team.Red;
            else if (fightT > timeLimit) w = bg + b.air >= rg + r.air ? Team.Blue : Team.Red;
            if (w == Team.None) return;
            Winner = w;
            phase = Phase.Over;
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            AddFeed($"<b><color=#{Ui.Hex(TeamPaint.Of(w))}>{w.ToString().ToUpper()} VICTORY</color></b>");
        }

        void OnDeath(Health victim, DamageInfo d)
        {
            var killer = d.attacker;
            if (killer && killer != victim && Health.Enemies(killer.team, victim.team))
            {
                kills[killer.team]++;
                if (killer.IsPlayer || (director && killer == director.PlayerUnit)) PlayerKills++;
            }
            string v = $"<color=#{Ui.Hex(TeamPaint.Of(victim.team))}>{victim.unitName}</color>";
            string text;
            if (killer && killer != victim) text = $"<color=#{Ui.Hex(TeamPaint.Of(killer.team))}>{killer.unitName}</color>  ›  {v}";
            else text = victim.cls == UnitClass.Air ? $"{v}  crashed" : $"{v}  destroyed";
            AddFeed(text);
        }

        void AddFeed(string text)
        {
            feed.Add(new FeedLine { text = text, time = Time.time });
            if (feed.Count > 6) feed.RemoveAt(0);
        }

        // ------------------------------------------------------------------ HUD
        void OnGUI()
        {
            long perfT0 = Perf.Now;
            OnGUITimed();
            Perf.Add(Perf.Hud, perfT0);
        }

        void OnGUITimed()
        {
            if (director && director.Paused) return;
            Ui.Begin();
            float s = Ui.S;
            float W = Screen.width, H = Screen.height;
            if (Event.current.type == EventType.Repaint)
            {
                if (cam) DrawMarkers(s);
                DrawStrength(s, W);
                DrawFeed(s, W);
                DrawMinimap(s, W, H);
            }

            if (phase == Phase.Countdown)
            {
                int n = Mathf.CeilToInt(CountdownLeft);
                if (city)
                {
                    var name = new GUIStyle(Ui.Title) { fontSize = Mathf.RoundToInt(64 * s) };
                    Ui.ShadowLabel(new Rect(0, H * 0.12f, W, 90 * s), $"BATTLE OF <color=#{Ui.Hex(Ui.Gold)}>{city.MapName.ToUpper()}</color>", name);
                    Ui.ShadowLabel(new Rect(0, H * 0.12f + 84 * s, W, 30 * s),
                        $"<color=#cfe0f2>Map seed {city.Seed}   ·   {ArmySize} vs {ArmySize}</color>", Ui.Center);
                }
                Ui.ShadowLabel(new Rect(0, H * 0.3f, W, 60 * s), "BATTLE BEGINS IN", Ui.Center);
                var big = new GUIStyle(Ui.Title) { fontSize = Mathf.RoundToInt(150 * s) };
                Ui.ShadowLabel(new Rect(0, H * 0.3f + 40 * s, W, 200 * s), $"<color=#{Ui.Hex(Ui.Gold)}>{n}</color>", big);
                Ui.ShadowLabel(new Rect(0, H * 0.3f + 230 * s, W, 40 * s), "Destroy every enemy soldier, vehicle, mech and airship", Ui.Center);
            }
            else if (fightFlash > 0f)
            {
                var big = new GUIStyle(Ui.Title) { fontSize = Mathf.RoundToInt(140 * s) };
                var c = GUI.color;
                GUI.color = new Color(1f, 1f, 1f, Mathf.Clamp01(fightFlash));
                Ui.ShadowLabel(new Rect(0, H * 0.3f, W, 200 * s), $"<color=#{Ui.Hex(Ui.Gold)}>FIGHT!</color>", big);
                GUI.color = c;
            }
            if (phase == Phase.Over) DrawVictory(s, W, H);
        }

        (int soldiers, int ground, int air, int mech) hudB, hudR;
        int hudDB, hudDR, hudSB, hudSR;
        float hudT;

        void DrawStrength(float s, float W)
        {
            // the counts change slowly: refresh them four times a second, not every frame
            if (Time.unscaledTime >= hudT)
            {
                hudT = Time.unscaledTime + 0.25f;
                hudB = Count(Team.Blue);
                hudR = Count(Team.Red);
                hudDB = DroneCount(Team.Blue);
                hudDR = DroneCount(Team.Red);
                hudSB = ShipCount(Team.Blue);
                hudSR = ShipCount(Team.Red);
            }
            var b = hudB;
            var r = hudR;
            int bt = b.soldiers + b.ground + b.air + b.mech, rt = r.soldiers + r.ground + r.air + r.mech;
            float w = 780 * s, h = 74 * s, x = (W - w) * 0.5f, y = 10 * s;
            Ui.Panel(new Rect(x, y, w, h));
            float bar = (w - 40 * s) * 0.5f;
            Ui.Rect(new Rect(x + 20 * s, y + 34 * s, bar, 8 * s), new Color(0.15f, 0.18f, 0.22f));
            float full = Mathf.Max(1f, ArmySize);
            Ui.Rect(new Rect(x + 20 * s + bar * (1f - bt / full), y + 34 * s, bar * bt / full, 8 * s), TeamPaint.Blue);
            Ui.Rect(new Rect(x + w * 0.5f, y + 34 * s, bar, 8 * s), new Color(0.15f, 0.18f, 0.22f));
            Ui.Rect(new Rect(x + w * 0.5f, y + 34 * s, bar * rt / full, 8 * s), TeamPaint.Red);
            GUI.Label(new Rect(x + 20 * s, y + 6 * s, bar, 28 * s), $"<b><color=#{Ui.Hex(TeamPaint.Blue)}>BLUE  {bt}</color></b>", Ui.Label);
            GUI.Label(new Rect(x + w * 0.5f, y + 6 * s, bar, 28 * s), $"<b><color=#{Ui.Hex(TeamPaint.Red)}>{rt}  RED</color></b>", Ui.Right);
            int mm = (int)(fightT / 60f), ss = (int)(fightT % 60f);
            GUI.Label(new Rect(x, y + 6 * s, w, 28 * s), $"{mm:00}:{ss:00}", Ui.Center);
            string line((int soldiers, int ground, int air, int mech) c, int drones) =>
                $"inf {c.soldiers} · arm {c.ground} · air {c.air} · mech {c.mech}" + (drones > 0 ? $" · drn {drones}" : "");
            GUI.Label(new Rect(x + 20 * s, y + 46 * s, bar, 24 * s), $"<color=#9fb4cc>{line(b, hudDB)} · ship {hudSB}</color>", Ui.Small);
            var sr = new GUIStyle(Ui.Small) { alignment = TextAnchor.UpperRight };
            GUI.Label(new Rect(x + w * 0.5f, y + 46 * s, bar, 24 * s), $"<color=#9fb4cc>{line(r, hudDR)} · ship {hudSR}</color>", sr);
        }

        void DrawFeed(float s, float W)
        {
            float y = 44 * s;
            for (int i = feed.Count - 1; i >= 0; i--)
            {
                float age = Time.time - feed[i].time;
                if (age > 9f && phase != Phase.Over) continue;
                var c = GUI.color;
                GUI.color = new Color(1f, 1f, 1f, Mathf.Clamp01(9f - age));
                GUI.Label(new Rect(W - 520 * s, y, 500 * s, 26 * s), feed[i].text, Ui.Right);
                GUI.color = c;
                y += 24 * s;
            }
        }

        void DrawMarkers(float s)
        {
            Vector3 cp = cam.transform.position;
            Health mine = director ? director.PlayerUnit : null;
            foreach (var h in Health.All)
            {
                if (!h.Alive || h == mine || h.team == Team.None) continue;
                Vector3 top = h.Center + Vector3.up * (h.cls == UnitClass.Soldier ? 1.1f : h.Radius + 1.5f);
                float dist = Vector3.Distance(cp, top);
                float lim = h.cls == UnitClass.Soldier ? 300f : h.IsDrone ? 600f : h.IsAirship ? 6000f : h.cls == UnitClass.Air ? 2600f : h.cls == UnitClass.Mech ? 1600f : 1000f;
                if (dist > lim) continue;
                Vector3 sp = cam.WorldToScreenPoint(top);
                if (sp.z <= 0f) continue;
                float x = sp.x, y = Screen.height - sp.y;
                float size = (h.cls == UnitClass.Soldier || h.IsDrone ? 6f : h.IsAirship ? 16f : h.cls == UnitClass.Mech ? 12f : 9f) * s;
                Color c = TeamPaint.Of(h.team);
                c.a = Mathf.Lerp(0.95f, 0.45f, dist / lim);
                Ui.QueueRect(new Rect(x - size * 0.5f, y - size * 0.5f, size, size), c);
                if (h.cls != UnitClass.Soldier && (dist < 350f || h.IsAirship))
                {
                    float bw = 34 * s;
                    Ui.QueueRect(new Rect(x - bw * 0.5f, y - size - 4 * s, bw, 3 * s), new Color(0f, 0f, 0f, 0.6f));
                    Ui.QueueRect(new Rect(x - bw * 0.5f, y - size - 4 * s, bw * h.Fraction, 3 * s), Color.Lerp(new Color(1f, 0.25f, 0.2f), new Color(0.4f, 1f, 0.45f), h.Fraction));
                }
            }
            Ui.FlushRects();
        }

        void DrawMinimap(float s, float W, float H)
        {
            float size = (city ? 300 : 230) * s, x = W - size - 16 * s, y = H - size - 16 * s;
            Ui.Panel(new Rect(x, y, size, size));
            float range = city ? CityGenerator.MapRange : 1400f;
            if (city && city.Minimap) GUI.DrawTexture(new Rect(x + 2, y + 2, size - 4, size - 4), city.Minimap, ScaleMode.StretchToFill, true);
            Vector2 Map(Vector3 p) => new Vector2(x + (p.x / range * 0.5f + 0.5f) * size, y + (0.5f - p.z / range * 0.5f) * size);
            // midline and bases
            Ui.QueueRect(new Rect(x, y + size * 0.5f, size, 1), new Color(1f, 1f, 1f, 0.15f));
            // what our side knows: amber squares where aircraft, drones and the fighting place the enemy
            foreach (var hot in Intel.Hots(playerTeam))
            {
                Vector2 m = Map(hot.pos);
                float d = Mathf.Clamp(5f + hot.weight * 0.9f, 6f, 22f) * s;
                Color c = hot.battle ? new Color(1f, 0.45f, 0.15f, 0.9f) : new Color(1f, 0.78f, 0.25f, 0.75f);
                c.a *= Mathf.Clamp01(1.2f - hot.age / 45f);
                float t = Mathf.Max(1f, 1.5f * s);
                Ui.QueueRect(new Rect(m.x - d * 0.5f, m.y - d * 0.5f, d, t), c);
                Ui.QueueRect(new Rect(m.x - d * 0.5f, m.y + d * 0.5f - t, d, t), c);
                Ui.QueueRect(new Rect(m.x - d * 0.5f, m.y - d * 0.5f, t, d), c);
                Ui.QueueRect(new Rect(m.x + d * 0.5f - t, m.y - d * 0.5f, t, d), c);
            }
            foreach (var h in Health.All)
            {
                if (!h.Alive || h.team == Team.None) continue;
                Vector3 p = h.transform.position;
                if (Mathf.Abs(p.x) > range || Mathf.Abs(p.z) > range) continue;
                Vector2 m = Map(p);
                float d = (h.cls == UnitClass.Soldier || h.IsDrone ? 2.5f : h.IsAirship ? 10f : h.cls == UnitClass.Mech ? 6f : h.cls == UnitClass.Air ? 4f : 4.5f) * s;
                Color c = TeamPaint.Of(h.team);
                if (h.cls == UnitClass.Air) c = Color.Lerp(c, Color.white, 0.35f);
                Ui.QueueRect(new Rect(m.x - d * 0.5f, m.y - d * 0.5f, d, d), c);
            }
            // the player
            Transform me = director && director.Current ? director.Current.transform : director && director.Soldier ? director.Soldier.transform : null;
            if (me)
            {
                Vector2 m = Map(me.position);
                float d = 7 * s;
                Ui.QueueRect(new Rect(m.x - d * 0.5f, m.y - d * 0.5f, d, d), Color.white);
            }
            Ui.FlushRects();
        }

        void DrawVictory(float s, float W, float H)
        {
            float w = 640 * s, h = 330 * s, x = (W - w) * 0.5f, y = H * 0.24f;
            Ui.Panel(new Rect(x, y, w, h));
            var big = new GUIStyle(Ui.Big) { fontSize = Mathf.RoundToInt(70 * s) };
            bool won = Winner == playerTeam;
            GUI.Label(new Rect(x, y + 20 * s, w, 90 * s), $"<color=#{Ui.Hex(TeamPaint.Of(Winner))}>{Winner.ToString().ToUpper()} VICTORY</color>", big);
            GUI.Label(new Rect(x, y + 105 * s, w, 30 * s), won ? "The enemy's ground forces are destroyed." : "Our ground forces have been wiped out.", Ui.Center);
            int mm = (int)(fightT / 60f), ss = (int)(fightT % 60f);
            GUI.Label(new Rect(x, y + 140 * s, w, 30 * s),
                $"Battle time {mm:00}:{ss:00}     Blue kills {kills[Team.Blue]}     Red kills {kills[Team.Red]}     Your kills {PlayerKills}", Ui.Center);
            float bw = 240 * s, bh = 62 * s, by = y + h - bh - 30 * s;
            bw = 190 * s;
            if (Ui.Btn(new Rect(x + w * 0.5f - bw * 1.5f - 16 * s, by, bw, bh), "PLAY AGAIN"))
            {
                MapInfo.Seed = city ? city.Seed : MapInfo.Seed;
                SceneManager.LoadScene(SceneManager.GetActiveScene().name);
            }
            if (Ui.Btn(new Rect(x + w * 0.5f - bw * 0.5f, by, bw, bh), "NEW MAP"))
            {
                MapInfo.Seed = 0;
                SceneManager.LoadScene(SceneManager.GetActiveScene().name);
            }
            if (Ui.Btn(new Rect(x + w * 0.5f + bw * 0.5f + 16 * s, by, bw, bh), "MAIN MENU")) SceneManager.LoadScene("Title");
        }
    }
}
