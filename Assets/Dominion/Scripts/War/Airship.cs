using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// A flying structure (AirshipKit "Leviathan" flagship, SkyshipKit "Sentinel" escort): a huge lighter-than-air hull
    /// that hangs over the battle at about skyscraper height, always drawn and always simulated.
    ///  - Floating physics (integrated here, applied to a kinematic body so its walkable decks can carry people):
    ///    gas lift trimmed by slow valves/ballast around the wanted altitude, engine thrust along the heading against
    ///    quadratic drag relative to a gusting wind, rudder yaw with lag, and pendulum pitch/roll (the gas sits above the
    ///    gondola) stirred by gusts, so the ship drifts, sways and corrects like a real airship.
    ///  - Helm: picks a vicinity where its turrets can reach a lot of known enemies (its side's Intel), stands off a little
    ///    toward its own side, keeps above every rooftop under it and moves only slowly and rarely. Escorts hold station
    ///    off the flagship's beams.
    ///  - Turrets (4 twin mounts): each picks air or ground targets in range with a clear line of fire past its own hull
    ///    (and no friendlies in the line), leads them and fires alternate barrels. A player standing at a deck turret can
    ///    man it (E).
    ///  - Crew: a fixed complement of soldiers stationed through the decks (bridge, turrets, posts, walkers). They are
    ///    light-weight (no controllers, animators culled when unseen) and only drawn near the ship.
    ///  - Damage: hull fires as it is hurt; destroyed, it loses lift, burns, noses down and crashes in a huge blast,
    ///    leaving a burning wreck.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    [DefaultExecutionOrder(-60)]
    public class Airship : MonoBehaviour
    {
        public string displayName = "Leviathan";
        public string unitKey = "Airship_Leviathan";
        public bool flagship = true;
        public int crewSize = 100;
        [Tooltip("Unused: paratroopers are the ship's own crew (see Jumpers).")]
        public int paraReserve = 0;

        [Header("Flight")]
        public float maxSpeed = 6f;
        public float cruiseAlt = 150f;          // keel above the ground
        public float roofClearance = 45f;       // keel above the highest roof under the ship
        public float maxTurnRate = 3.5f;        // deg/s
        public float thrustAccel = 0.12f;       // m/s^2 at full throttle

        [Header("Turrets")]
        public float gunDamage = 380f;
        public float gunSplash = 160f;
        public float gunSplashRadius = 6f;
        public float gunProximity = 10f;
        public DamageType gunType = DamageType.AP;
        public float gunInterval = 0.9f;
        public float gunSpeed = 650f;
        public float gunGravity = 0.3f;
        public float gunRange = 1500f;
        public float gunSpreadDeg = 0.35f;
        [Tooltip("Range falloff: full damage out to this many metres of flight, easing down to falloffMin x at gunRange and beyond.")]
        public float falloffStart = 300f;
        [Range(0f, 1f)] public float falloffMin = 0.2f;
        public float minElevation = -10f, maxElevation = 85f;
        public ImpactKind impactKind = ImpactKind.Shell;
        public float impactScale = 1.6f, muzzleScale = 1.1f, tracerWidth = 0.22f;

        [Header("Shape (filled by the editor setup)")]
        public Vector3 centerLocal = new Vector3(0f, 20f, 0f);
        public float radius = 14f;
        public Bounds hullBounds = new Bounds(new Vector3(0f, 20f, 0f), new Vector3(30f, 45f, 160f));
        public Bounds deckBounds = new Bounds(new Vector3(0f, 3f, 0f), new Vector3(11f, 8f, 63f));

        public static readonly List<Airship> All = new List<Airship>();
        [System.NonSerialized] public Team team;
        [System.NonSerialized] public Health health;
        [System.NonSerialized] public Airship leader;       // escorts: the flagship they guard
        [System.NonSerialized] public Vector3 stationOffset; // escorts: where off the flagship (flagship space)
        public bool Destroyed { get; private set; }
        public bool Crashed { get; private set; }
        public Vector3 Velocity => vel;
        public string State { get; private set; } = "";
        public int ShotsFired { get; private set; }
        public Vector3 Goal => goal;

        Rigidbody body;
        RigBones rig;
        Collider[] hullCols;
        MeshCollider deckCol;
        Vector3 vel, goal;
        float yaw, yawRate, pitch, pitchRate, roll, rollRate, trim, altGoal, helmT, altT, spin, gustSeed, listRoll, sinkT, boomT;
        Vector3 wind;
        Matrix4x4 prevMatrix, curMatrix, prevInverse;
        bool hasPrev;
        readonly List<Transform> props = new List<Transform>();
        Transform elevL, elevR, rudU, rudD;
        readonly List<(Transform t, Vector3 axis, int i)> flagBones = new List<(Transform, Vector3, int)>();
        readonly List<Renderer> interior = new List<Renderer>();
        readonly List<Emitter> fires = new List<Emitter>();
        static readonly RaycastHit[] hitBuf = new RaycastHit[16];

        public class Turret
        {
            public Transform yawBone, pitchBone;
            public Transform[] muzzles, flashes;
            public Vector3 yawAxis, pitchAxis;
            public Quaternion mountLocal;                     // mount frame in ship space (ventral mounts are upside down)
            public float restYaw, restPitch, yaw, pitch, cooldown, thinkT, errT;
            public float[] flashT = { 9f, 9f };
            public int barrel;
            public Health target;
            public bool visible, manned, playerFire;
            public Vector3 aimPoint, aimErr;
            public CrewMember gunner;
            // deck guns (the Sentinel's sponsons) are worked by a gunner sitting behind them
            public bool deck, seated;
            public Vector3 seatShip, seatYawLocal;
            public Quaternion seatRotYawLocal;
        }
        public readonly List<Turret> turrets = new List<Turret>();

        public class CrewMember
        {
            public Transform t;
            public Animator anim;
            public Renderer[] rends;
            public Vector3 a, b;                // ship-space stations (walkers pace between them)
            public bool walker, exposed, gunner, shown = true;
            public float u, dir = 1f, wait;
            public Turret toSeat;
            public bool seated;
        }
        readonly List<CrewMember> crew = new List<CrewMember>();
        float crewT;
        static readonly int VelZ = Animator.StringToHash("VelZ");

        // ------------------------------------------------------------------ setup
        void Awake()
        {
            body = GetComponent<Rigidbody>();
            body.isKinematic = true;
            body.useGravity = false;
            body.interpolation = RigidbodyInterpolation.Interpolate;
            rig = new RigBones(transform);
            hullCols = GetComponentsInChildren<Collider>(true);
            deckCol = GetComponentInChildren<MeshCollider>(true);
            yaw = transform.eulerAngles.y;
            gustSeed = Random.Range(0f, 100f);
            float wa = Random.Range(0f, 360f) * Mathf.Deg2Rad;
            wind = new Vector3(Mathf.Cos(wa), 0f, Mathf.Sin(wa)) * Random.Range(1f, 2.5f);
            goal = transform.position;
            altGoal = transform.position.y;

            for (int i = 1; i <= 8; i++) if (rig[$"prop_{i}"]) props.Add(rig[$"prop_{i}"]);
            elevL = rig["elevator_L"]; elevR = rig["elevator_R"]; rudU = rig["rudder_U"]; rudD = rig["rudder_D"];
            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                if (r.name.Contains("Interior")) interior.Add(r);
                if (r.name.Contains("MuzzleFlash")) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }
            // turrets: mount frame up = away from the hull (ventral mounts hang upside down under the gondola)
            for (int i = 1; i <= 8; i++)
            {
                var ty = rig[$"turret_{i}"];
                var tp = rig[$"gun_{i}"];
                if (ty == null || tp == null) continue;
                var tu = new Turret { yawBone = ty, pitchBone = tp };
                tu.muzzles = new[] { rig[$"muzzle_{i}L"], rig[$"muzzle_{i}R"] };
                tu.flashes = new[] { rig[$"flash_{i}L"], rig[$"flash_{i}R"] };
                bool ventral = transform.InverseTransformPoint(ty.position).y < 0f;
                tu.mountLocal = ventral ? Quaternion.AngleAxis(180f, Vector3.forward) : Quaternion.identity;
                Quaternion mountW = transform.rotation * tu.mountLocal;
                tu.yawAxis = RigBones.LocalAxis(ty, mountW * Vector3.up);
                Vector3 bd = Quaternion.Inverse(mountW) * (MuzzleMid(tu) - tp.position);
                if (bd.sqrMagnitude < 1e-4f) bd = Vector3.forward;
                // the gun elevates about the horizontal axis at right angles to where it points at rest (the Sentinel's
                // sponson mounts rest facing outboard, so this is not the ship's own left / right axis)
                Vector3 flatRest = new Vector3(bd.x, 0f, bd.z);
                flatRest = flatRest.sqrMagnitude > 1e-4f ? flatRest.normalized : Vector3.forward;
                tu.pitchAxis = RigBones.LocalAxis(tp, mountW * -Vector3.Cross(Vector3.up, flatRest));   // + = elevate
                tu.restYaw = Mathf.Atan2(bd.x, bd.z) * Mathf.Rad2Deg;
                tu.restPitch = Mathf.Atan2(bd.y, new Vector2(bd.x, bd.z).magnitude) * Mathf.Rad2Deg;
                tu.thinkT = Random.Range(0f, 0.5f);
                turrets.Add(tu);
            }
        }

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        /// <summary>Called by WarManager after Health and team are set: flags, crew.</summary>
        public void Init(Team t, GameObject[] crewPrefabs)
        {
            team = t;
            // flags: the side's own colours, the other designs hidden
            string keep = t == Team.Blue ? "SkyLegion" : "StormCorsairs";
            foreach (var r in GetComponentsInChildren<Renderer>(true))
                if (r.name.Contains("_Flag_")) r.enabled = r.name.Contains(keep);
            foreach (var b in rig.All)
            {
                if (!b.name.StartsWith("flag_")) continue;
                int seg = 0;
                int.TryParse(b.name.Substring(b.name.LastIndexOf('_') + 1), out seg);
                flagBones.Add((b, RigBones.LocalAxis(b, transform.up), seg));
            }
            SpawnCrew(crewPrefabs);
            prevMatrix = curMatrix = transform.localToWorldMatrix;
        }

        // ------------------------------------------------------------------ crew
        /// <summary>Walkable floor points inside the decks (raycast against the ship's own collision mesh).</summary>
        List<(Vector3 p, bool exposed)> DeckPoints()
        {
            var pts = new List<(Vector3, bool)>();
            if (deckCol == null) return pts;
            bool back = Physics.queriesHitBackfaces;
            Physics.queriesHitBackfaces = true;
            var b = deckBounds;
            for (float z = b.min.z + 1f; z < b.max.z - 1f; z += 2.1f)
                for (float x = b.min.x + 0.8f; x < b.max.x - 0.8f; x += 1.5f)
                {
                    Vector3 from = transform.TransformPoint(new Vector3(x, b.max.y + 4f, z));
                    float budget = b.size.y + 6f;
                    for (int k = 0; k < 4 && budget > 0.5f; k++)
                    {
                        if (!deckCol.Raycast(new Ray(from, -transform.up), out RaycastHit h, budget)) break;
                        budget -= h.distance + 0.25f;
                        from = h.point - transform.up * 0.25f;
                        if (Vector3.Dot(h.normal, transform.up) < 0.8f) continue;
                        Vector3 p = h.point + transform.up * 0.02f;
                        // standing room: nothing overhead for 1.9 m, no wall within 0.4 m at chest height
                        bool roof = deckCol.Raycast(new Ray(p + transform.up * 0.1f, transform.up), out _, 1.9f);
                        bool cramped = false;
                        foreach (var d in new[] { transform.right, -transform.right, transform.forward, -transform.forward })
                            if (deckCol.Raycast(new Ray(p + transform.up * 1.1f, d), out _, 0.45f)) { cramped = true; break; }
                        if (roof && !deckCol.Raycast(new Ray(p + transform.up * 0.1f, transform.up), out _, 1.85f)) roof = false;
                        if (cramped) continue;
                        if (deckCol.Raycast(new Ray(p + transform.up * 0.1f, transform.up), out RaycastHit up, 3f) && up.distance < 1.85f) continue;
                        bool exposed = !deckCol.Raycast(new Ray(p + transform.up * 0.1f, transform.up), out _, 60f);
                        pts.Add((transform.InverseTransformPoint(p), exposed));
                    }
                }
            Physics.queriesHitBackfaces = back;
            return pts;
        }

        void SpawnCrew(GameObject[] prefabs)
        {
            if (prefabs == null || prefabs.Length == 0 || crewSize <= 0) return;
            var pts = DeckPoints();
            if (pts.Count == 0) return;
            // spread them out: shuffle, then keep points at least 1.2 m apart
            for (int i = pts.Count - 1; i > 0; i--) { int j = Random.Range(0, i + 1); (pts[i], pts[j]) = (pts[j], pts[i]); }
            var chosen = new List<(Vector3 p, bool exposed)>();
            // deck guns (the Sentinel's sponson mounts): a seat behind each, on the deck, turning with the mount
            foreach (var tu in turrets)
            {
                Vector3 tl = transform.InverseTransformPoint(tu.yawBone.position);
                if (tl.y < 0f || tl.y > deckBounds.max.y + 2f) continue;
                Vector3 rest = transform.InverseTransformDirection(MuzzleMid(tu) - tu.pitchBone.position);
                rest.y = 0f;
                rest = rest.sqrMagnitude > 1e-4f ? rest.normalized : Vector3.forward;
                Vector3 seat = tl - rest * 1.25f;
                Vector3 wSeat = transform.TransformPoint(seat + Vector3.up * 2f);
                if (deckCol && deckCol.Raycast(new Ray(wSeat, -transform.up), out RaycastHit fh, 4f)) seat = transform.InverseTransformPoint(fh.point);
                else seat.y = tl.y - 1f;
                tu.deck = true;
                tu.seatShip = seat;
                tu.seatYawLocal = tu.yawBone.InverseTransformPoint(transform.TransformPoint(seat));
                tu.seatRotYawLocal = Quaternion.Inverse(tu.yawBone.rotation) * (transform.rotation * Quaternion.LookRotation(rest));
            }
            foreach (var pt in pts)
            {
                if (crew.Count >= crewSize) break;
                bool close = false;
                foreach (var c in chosen) if ((c.p - pt.p).sqrMagnitude < 1.44f) { close = true; break; }
                if (close) continue;
                chosen.Add(pt);
                var cm = MakeCrew(prefabs, pt.p, pt.p + new Vector3(Random.Range(-1f, 1f), 0f, Random.Range(-1f, 1f)), pt.exposed);
                // a fifth of them pace between two posts on the same deck
                if (Random.value < 0.2f)
                    foreach (var o in pts)
                    {
                        Vector3 d = o.p - pt.p;
                        if (Mathf.Abs(d.y) > 0.3f || d.magnitude < 4f || d.magnitude > 14f) continue;
                        Vector3 w0 = transform.TransformPoint(pt.p + Vector3.up), w1 = transform.TransformPoint(o.p + Vector3.up);
                        if (deckCol.Raycast(new Ray(w0, (w1 - w0).normalized), out _, (w1 - w0).magnitude)) continue;
                        cm.walker = true;
                        cm.b = o.p;
                        break;
                    }
            }
            // the nearest hands go to the deck guns and take their seats
            foreach (var tu in turrets)
            {
                if (!tu.deck) continue;
                CrewMember best = null;
                float bd2 = float.MaxValue;
                foreach (var c in crew)
                {
                    if (c.gunner || c.toSeat != null) continue;
                    float d = (c.a - tu.seatShip).sqrMagnitude;
                    if (d < bd2) { bd2 = d; best = c; }
                }
                if (best == null) continue;
                best.walker = false;
                best.toSeat = tu;
                best.gunner = true;
                best.exposed = true;
                tu.gunner = best;
            }
        }

        /// <summary>A gunner walking across the deck to his gun, then sitting down behind it (he turns with the mount).</summary>
        void WalkToSeat(CrewMember c, float dt)
        {
            var tu = c.toSeat;
            Vector3 lp = c.t.localPosition, to = tu.seatShip - lp;
            to.y = 0f;
            if (to.magnitude < 0.3f)
            {
                c.t.SetPositionAndRotation(tu.yawBone.TransformPoint(tu.seatYawLocal), tu.yawBone.rotation * tu.seatRotYawLocal);
                c.t.SetParent(tu.yawBone, true);
                c.seated = tu.seated = true;
                if (c.anim && c.anim.isActiveAndEnabled) { c.anim.SetFloat(VelZ, 0f); c.anim.Play("Crouch", 0, 0f); }
                return;
            }
            c.t.localPosition = lp + to.normalized * Mathf.Min(to.magnitude, 1.6f * dt) + Vector3.up * ((tu.seatShip.y - lp.y) * Mathf.Min(1f, dt * 3f));
            c.t.localRotation = Quaternion.Slerp(c.t.localRotation, Quaternion.LookRotation(to), dt * 5f);
            if (c.anim && c.anim.isActiveAndEnabled) c.anim.SetFloat(VelZ, 1.5f, 0.1f, dt);
        }

        CrewMember MakeCrew(GameObject[] prefabs, Vector3 local, Vector3 face, bool exposed)
        {
            var go = Instantiate(prefabs[crew.Count % prefabs.Length], transform);
            go.name = $"{displayName} crew {crew.Count + 1}";
            foreach (var sc in go.GetComponentsInChildren<SoldierController>(true)) DestroyImmediate(sc);
            foreach (var cc in go.GetComponentsInChildren<CharacterController>(true)) DestroyImmediate(cc);
            foreach (var col in go.GetComponentsInChildren<Collider>(true)) DestroyImmediate(col);
            TeamPaint.Apply(go, team, true);
            Vector3 f = face - local;
            f.y = 0f;
            go.transform.localPosition = local;
            go.transform.localRotation = f.sqrMagnitude > 0.01f ? Quaternion.LookRotation(f) : Quaternion.Euler(0f, Random.Range(0f, 360f), 0f);
            var cm = new CrewMember { t = go.transform, anim = go.GetComponentInChildren<Animator>(), rends = go.GetComponentsInChildren<Renderer>(true),
                                      a = local, b = local, exposed = exposed, u = Random.value };
            if (cm.anim)
            {
                cm.anim.cullingMode = AnimatorCullingMode.CullCompletely;
                cm.anim.Play(0, 0, Random.value);
            }
            crew.Add(cm);
            return cm;
        }

        public int CrewCount => crew.Count;

        /// <summary>Crew are only drawn (and animated) near the ship: interior hands up close, deck hands a bit further.</summary>
        void UpdateCrew(float dt)
        {
            var cam = Camera.main;
            if (cam == null || crew.Count == 0) return;
            crewT -= dt;
            bool refresh = crewT <= 0f;
            if (refresh) crewT = 0.25f;
            Vector3 cp = transform.InverseTransformPoint(cam.transform.position);
            float dist = Vector3.Distance(cam.transform.position, transform.TransformPoint(deckBounds.center));
            bool inside = deckBounds.Contains(cp);
            for (int i = 0; i < crew.Count; i++)
            {
                var c = crew[i];
                if (refresh)
                {
                    bool show = !Crashed && (inside || dist < (c.exposed ? 420f : 140f));
                    if (show != c.shown)
                    {
                        c.shown = show;
                        c.t.gameObject.SetActive(show);
                        if (show && c.seated && c.anim) c.anim.Play("Crouch", 0, 0f);
                    }
                    if (c.anim && c.gunner) c.anim.SetLayerWeight(c.anim.GetLayerIndex("UpperBody"), 1f);
                }
                if (c.toSeat != null && !c.seated) { WalkToSeat(c, dt); continue; }
                if (!c.shown || !c.walker || !c.anim) continue;
                // walkers pace between their two posts, pausing at each end
                if (c.wait > 0f) { c.wait -= dt; c.anim.SetFloat(VelZ, 0f, 0.15f, dt); continue; }
                float len = Vector3.Distance(c.a, c.b);
                c.u += c.dir * dt * 1.35f / Mathf.Max(len, 0.1f);
                if (c.u >= 1f || c.u <= 0f) { c.u = Mathf.Clamp01(c.u); c.dir = -c.dir; c.wait = Random.Range(1.5f, 4f); }
                Vector3 from = c.dir > 0f ? c.a : c.b, to = c.dir > 0f ? c.b : c.a;
                c.t.localPosition = Vector3.Lerp(c.a, c.b, c.u);
                Vector3 f = to - from;
                if (f.sqrMagnitude > 0.01f) c.t.localRotation = Quaternion.Slerp(c.t.localRotation, Quaternion.LookRotation(f), dt * 4f);
                c.anim.SetFloat(VelZ, 1.4f, 0.15f, dt);
            }
        }

        // ------------------------------------------------------------------ platform (people standing on the decks)
        /// <summary>
        /// How far the deck under a point moved since last frame (and the yaw it turned): for a character standing on
        /// one of the ships. False when the point isn't aboard any ship.
        /// </summary>
        public static bool Carry(Vector3 worldPos, out Vector3 delta, out float yawDelta)
        {
            delta = Vector3.zero;
            yawDelta = 0f;
            foreach (var s in All)
            {
                if (!s.hasPrev || s.Crashed) continue;
                Vector3 lp = s.prevInverse.MultiplyPoint3x4(worldPos);
                var b = s.deckBounds;
                b.Expand(new Vector3(3f, 6f, 6f));
                if (!b.Contains(lp)) continue;
                Vector3 now = s.curMatrix.MultiplyPoint3x4(lp);
                delta = now - worldPos;
                yawDelta = Mathf.DeltaAngle(s.prevMatrix.rotation.eulerAngles.y, s.curMatrix.rotation.eulerAngles.y);
                return true;
            }
            return false;
        }

        /// <summary>A deck spawn point for a player joining this ship (world space).</summary>
        public Vector3 SpawnPoint()
        {
            // prefer an open deck (the Sentinel's top deck), else anywhere aboard
            var pts = DeckPoints();
            (Vector3 p, bool exposed) pick = default;
            bool found = false;
            foreach (var p in pts) if (p.exposed && Vector3.Distance(p.p, deckBounds.center) < deckBounds.extents.z * 0.6f) { pick = p; found = true; break; }
            if (!found && pts.Count > 0) { pick = pts[Random.Range(0, pts.Count)]; found = true; }
            return found ? transform.TransformPoint(pick.p) + transform.up * 0.15f : transform.TransformPoint(deckBounds.center);
        }

        /// <summary>Index of a deck turret within reach of a point (a player can man it), or -1.</summary>
        public int TurretNear(Vector3 worldPos, float reach)
        {
            for (int i = 0; i < turrets.Count; i++)
                if (Vector3.Distance(turrets[i].yawBone.position, worldPos) < reach) return i;
            return -1;
        }

        public void Man(int i, bool on)
        {
            if (i < 0 || i >= turrets.Count) return;
            turrets[i].manned = on;
            turrets[i].playerFire = false;
        }

        /// <summary>A player on the gun: aim at 'point', fire if asked.</summary>
        public void PlayerGun(int i, Vector3 point, bool fire)
        {
            if (i < 0 || i >= turrets.Count) return;
            turrets[i].aimPoint = point;
            turrets[i].playerFire = fire;
        }

        /// <summary>Put the ship over a spot at its safe altitude, facing yawDeg (spawning).</summary>
        public void Place(Vector3 xz, float yawDeg)
        {
            yaw = yawDeg;
            goal = new Vector3(xz.x, 0f, xz.z);
            altGoal = SafeAltitude(goal, goal);
            Vector3 p = new Vector3(xz.x, altGoal, xz.z);
            transform.SetPositionAndRotation(p, Quaternion.Euler(0f, yaw, 0f));
            body.position = p;
            body.rotation = transform.rotation;
            prevMatrix = curMatrix = transform.localToWorldMatrix;
        }

        public float AltitudeAboveGround => transform.position.y + hullBounds.min.y - WorldGround.Height(transform.position.x, transform.position.z);

        int paraQueue, paraSide;
        float paraT;
        Vector3 paraTarget;
        public bool Dropping => paraQueue > 0;

        /// <summary>
        /// Crew who can be spared to jump: everyone but the seated deck gunners (and those walking to their guns) and a
        /// skeleton crew of a tenth who stay aboard to fly and fight the ship.
        /// </summary>
        public int Jumpers
        {
            get
            {
                int n = 0;
                foreach (var c in crew) if (!c.gunner && c.toSeat == null) n++;
                return Mathf.Max(0, n - Mathf.CeilToInt(crewSize * 0.1f) - paraQueue);
            }
        }

        /// <summary>Send up to n of the crew out of the side doors as paratroopers, steering for 'target'. Returns how many go.</summary>
        public int OrderDrop(int n, Vector3 target)
        {
            n = Mathf.Clamp(n, 0, Jumpers);
            paraQueue += n;
            paraTarget = target;
            return n;
        }

        void DropUpdate(WarManager war, float dt)
        {
            if (paraQueue <= 0 || Destroyed || war == null) return;
            paraT -= dt;
            if (paraT > 0f) return;
            paraT = 0.6f;
            paraQueue--;
            // one of the crew leaves his post and goes out of the door
            CrewMember jumper = null;
            for (int i = crew.Count - 1; i >= 0; i--)
                if (!crew[i].gunner && crew[i].toSeat == null) { jumper = crew[i]; crew.RemoveAt(i); break; }
            if (jumper == null) { paraQueue = 0; return; }
            if (jumper.t) Destroy(jumper.t.gameObject);
            paraSide = 1 - paraSide;
            Vector3 door = new Vector3((paraSide == 0 ? -1f : 1f) * (deckBounds.extents.x + 1.5f), deckBounds.min.y + 0.5f,
                                       deckBounds.center.z + Random.Range(-0.3f, 0.3f) * deckBounds.extents.z);
            war.SpawnParatrooper(this, transform.TransformPoint(door), paraTarget);
        }

        public Vector3 TurretPosition(int i) => i >= 0 && i < turrets.Count ? turrets[i].yawBone.position : transform.position;

        // ------------------------------------------------------------------ simulation
        void FixedUpdate()
        {
            long perfT0 = Perf.Now;
            FixedUpdateTimed();
            Perf.Add(Perf.Ships, perfT0);
        }

        void FixedUpdateTimed()
        {
            if (Crashed) return;
            float dt = Time.fixedDeltaTime;
            var war = WarManager.Instance;
            bool fighting = war == null || war.Fighting;
            Vector3 pos = body.position;

            if (!Destroyed && fighting)
            {
                helmT -= dt;
                if (helmT <= 0f) { helmT = 3f; Helm(war, pos); }
                altT -= dt;
                if (altT <= 0f) { altT = 1.5f; altGoal = SafeAltitude(goal, pos); }
            }

            // wind with gusts
            float t = Time.time * 0.11f + gustSeed;
            Vector3 gust = new Vector3(Mathf.PerlinNoise(t, 0.3f) - 0.5f, 0f, Mathf.PerlinNoise(0.7f, t) - 0.5f) * 2.4f;
            Vector3 vRel = vel - (wind + gust);

            // engines along the heading, toward where the helm wants to be
            Vector3 fwd = Quaternion.Euler(0f, yaw, 0f) * Vector3.forward;
            Vector3 to = goal - pos;
            to.y = 0f;
            float dist = to.magnitude;
            Vector3 wantV = dist > 1f ? to / dist * Mathf.Min(maxSpeed, dist * 0.035f) : Vector3.zero;
            float throttle = Destroyed ? 0f : Mathf.Clamp(Vector3.Dot(wantV - new Vector3(vel.x, 0f, vel.z), fwd) * 0.6f + Vector3.Dot(wantV, fwd) / maxSpeed * 0.35f, -0.5f, 1f);
            float dragK = thrustAccel / (maxSpeed * maxSpeed);
            Vector3 a = fwd * (throttle * thrustAccel) - new Vector3(vRel.x, 0f, vRel.z) * (dragK * new Vector2(vRel.x, vRel.z).magnitude);

            // heading: turn toward the way we want to go while moving; hold it on station
            float wantYaw = yaw;
            if (!Destroyed && dist > 90f) wantYaw = Mathf.Atan2(to.x, to.z) * Mathf.Rad2Deg;
            float yawErr = Mathf.DeltaAngle(yaw, wantYaw);
            float wantRate = Mathf.Clamp(yawErr * 0.15f, -maxTurnRate, maxTurnRate) * (Destroyed ? 0.2f : 1f);
            yawRate = Mathf.MoveTowards(yawRate, wantRate, dt * 0.6f);
            yaw += yawRate * dt;

            // lift: valves and ballast trim the buoyancy slowly toward the wanted altitude
            float altErr = altGoal - pos.y;
            float wantTrim = Mathf.Clamp(altErr * 0.0012f - vel.y * 0.012f, -0.012f, 0.012f);
            if (health && health.Fraction < 0.25f) wantTrim -= 0.004f;                 // holed gas cells: sagging
            if (Destroyed) wantTrim = -0.35f;
            trim = Mathf.MoveTowards(trim, wantTrim, dt * (Destroyed ? 0.05f : 0.0025f));
            a.y = 9.81f * trim - vel.y * Mathf.Abs(vel.y) * 0.02f - vel.y * 0.05f;
            vel += a * dt;

            // pitch and roll: a pendulum under the gas (period ~11 s), stirred by gusts, the turns and the climb
            float w = Mathf.PI * 2f / 11f, z = 0.25f;
            float gP = (Mathf.PerlinNoise(t * 3.1f, 4.2f) - 0.5f) * 0.006f, gR = (Mathf.PerlinNoise(9.1f, t * 2.7f) - 0.5f) * 0.008f;
            float pitchTarget = Mathf.Clamp(-vel.y * 1.2f, -6f, 6f) * Mathf.Deg2Rad + (Destroyed ? 14f * Mathf.Deg2Rad * Mathf.Clamp01(sinkT / 8f) : 0f);
            float rollTarget = (-yawRate * 0.8f + listRoll) * Mathf.Deg2Rad;
            pitchRate += (-w * w * (pitch - pitchTarget) - 2f * z * w * pitchRate + gP) * dt;
            rollRate += (-w * w * (roll - rollTarget) - 2f * z * w * rollRate + gR) * dt;
            pitch += pitchRate * dt;
            roll += rollRate * dt;
            listRoll = health && health.Fraction < 0.4f ? Mathf.MoveTowards(listRoll, 4f, dt * 0.2f) : listRoll;

            pos += vel * dt;
            body.MovePosition(pos);
            body.MoveRotation(Quaternion.Euler(0f, yaw, 0f) * Quaternion.Euler(pitch * Mathf.Rad2Deg, 0f, roll * Mathf.Rad2Deg));

            if (Destroyed)
            {
                sinkT += dt;
                float floor = WorldGround.Top(pos.x, pos.z);
                Vector3 keel = transform.TransformPoint(new Vector3(0f, hullBounds.min.y, hullBounds.center.z));
                if (keel.y <= floor + 1f || sinkT > 90f) Crash();
            }
        }

        /// <summary>Keel height over the highest roof in the footprint (looked up around the goal and the ship).</summary>
        float SafeAltitude(Vector3 g, Vector3 pos)
        {
            float top = 0f, ground = WorldGround.Height(g.x, g.z);
            float r = hullBounds.extents.z;
            for (int i = 0; i < 9; i++)
            {
                Vector3 p = i == 0 ? g : g + Quaternion.Euler(0f, i * 45f, 0f) * Vector3.forward * r;
                top = Mathf.Max(top, WorldGround.Top(p.x, p.z));
                Vector3 q = i == 0 ? pos : pos + Quaternion.Euler(0f, i * 45f, 0f) * Vector3.forward * r;
                top = Mathf.Max(top, WorldGround.Top(q.x, q.z));
            }
            return Mathf.Max(ground + cruiseAlt, top + roofClearance) - hullBounds.min.y;
        }

        /// <summary>Where to hang: escorts off the flagship's beams; the flagship where its guns reach the most enemies.</summary>
        void Helm(WarManager war, Vector3 pos)
        {
            if (leader && !leader.Destroyed)
            {
                goal = leader.transform.position + Quaternion.Euler(0f, leader.yaw, 0f) * stationOffset;
                State = "escort";
                return;
            }
            if (war == null) return;
            var hots = Intel.Hots(team);
            Vector3 sum = Vector3.zero;
            float wsum = 0f;
            foreach (var h in hots)
            {
                float d = AIUtil.Flat(h.pos - pos).magnitude;
                if (d > 2200f) continue;
                float wgt = h.weight * (h.battle ? 1.5f : 1f) / (1f + d / 900f);
                sum += h.pos * wgt;
                wsum += wgt;
            }
            Vector3 want;
            if (wsum > 0f)
            {
                // over the edge of the enemy concentration, a little back toward our own side, guns in reach
                Vector3 c = sum / wsum;
                Vector3 home = war.OwnBase(team);
                Vector3 back = AIUtil.Flat(home - c);
                want = c + (back.sqrMagnitude > 1f ? back.normalized : Vector3.zero) * Mathf.Min(gunRange * 0.35f, 450f);
                State = "on station";
            }
            else
            {
                // nothing known: hang over our own front line
                Vector3 fwd = war.Forward(team);
                want = war.OwnBase(team) + fwd * Mathf.Max(0f, war.FrontLine(team) - Vector3.Dot(war.OwnBase(team), fwd));
                State = "holding";
            }
            // keep clear of the other ships
            foreach (var o in All)
                if (o != this && !o.Crashed)
                {
                    Vector3 d = AIUtil.Flat(want - o.transform.position);
                    if (d.magnitude < 260f) want += (d.sqrMagnitude > 1f ? d.normalized : Vector3.right) * (260f - d.magnitude);
                }
            float lim = CityGenerator.MapRange * 0.9f;
            want.x = Mathf.Clamp(want.x, -lim, lim);
            want.z = Mathf.Clamp(want.z, -lim, lim);
            want.y = 0f;
            // big ships don't fidget: only move when the wanted spot has really shifted
            if (AIUtil.Flat(want - goal).magnitude > 220f || goal == Vector3.zero) goal = want;
        }

        void Update()
        {
            long perfT0 = Perf.Now;
            UpdateTimed();
            Perf.Add(Perf.Ships, perfT0);
        }

        void UpdateTimed()
        {
            float dt = Time.deltaTime;
            prevMatrix = curMatrix;
            curMatrix = transform.localToWorldMatrix;
            prevInverse = prevMatrix.inverse;
            hasPrev = true;
            if (Crashed) { UpdateCrew(dt); return; }
            var war = WarManager.Instance;
            bool fighting = war == null || war.Fighting;
            // props, control surfaces, flags
            spin += dt * (Destroyed ? 90f : 900f);
            foreach (var p in props) rig.Rotate(p, Vector3.up, spin);
            float elev = Mathf.Clamp(-vel.y * 6f, -18f, 18f), rud = Mathf.Clamp(yawRate * 5f, -20f, 20f);
            if (elevL) rig.Rotate(elevL, Vector3.up, elev);
            if (elevR) rig.Rotate(elevR, Vector3.up, elev);
            if (rudU) rig.Rotate(rudU, Vector3.up, rud);
            if (rudD) rig.Rotate(rudD, Vector3.up, rud);
            float ft = Time.time;
            foreach (var (b, axis, seg) in flagBones)
                rig.Rotate(b, axis, Mathf.Sin(ft * 2.3f - seg * 0.9f + gustSeed) * (6f + seg * 4f));
            // interiors only drawn up close (the decks are seen through windows and doors from nearby)
            var cam = Camera.main;
            if (cam)
            {
                bool near = Vector3.Distance(cam.transform.position, transform.TransformPoint(deckBounds.center)) < 260f;
                foreach (var r in interior) if (r && r.enabled != near) r.enabled = near;
            }
            if (!Destroyed && fighting) Guns(dt);
            if (fighting) DropUpdate(war, dt);
            foreach (var tu in turrets)
                for (int k = 0; k < 2; k++)
                {
                    tu.flashT[k] += dt;
                    if (tu.flashes[k]) rig.Scale(tu.flashes[k], tu.flashT[k] < 0.07f ? 1000f : 1f);
                }
            UpdateCrew(dt);
            DamageEffects(dt);
        }

        // ------------------------------------------------------------------ gunnery
        float Pref(Health h, float dist)
        {
            if (h.IsAirship) return 0.9f;
            if (h.IsDrone) return dist < 700f ? 0.5f : 0f;
            if (h.Airborne) return 1.1f;
            switch (h.cls)
            {
                case UnitClass.Mech: return 1.3f;
                case UnitClass.Soldier: return 0.45f;
                case UnitClass.Ground: return h.armor == ArmorClass.Armored ? 1f : 0.85f;
            }
            return 0.3f;
        }

        void Guns(float dt)
        {
            for (int i = 0; i < turrets.Count; i++)
            {
                var tu = turrets[i];
                tu.cooldown -= dt;
                Transform m0 = tu.muzzles[0] ? tu.muzzles[0] : tu.pitchBone;
                if (tu.manned)
                {
                    Aim(tu, tu.aimPoint, dt);
                    if (tu.playerFire && tu.cooldown <= 0f) Fire(tu);
                    continue;
                }
                if (tu.deck && !tu.seated) continue;
                tu.thinkT -= dt;
                if (tu.thinkT <= 0f)
                {
                    tu.thinkT = Random.Range(0.35f, 0.5f);
                    PickTarget(tu, m0.position);
                }
                if (tu.target == null || !tu.target.Alive)
                {
                    // idle: sweep slowly
                    Aim(tu, m0.position + (transform.rotation * tu.mountLocal) * (Quaternion.Euler(-8f, Mathf.Sin(Time.time * 0.2f + i) * 120f, 0f) * Vector3.forward) * 200f, dt);
                    continue;
                }
                if ((tu.errT -= dt) <= 0f)
                {
                    tu.errT = 0.6f;
                    tu.aimErr = AIUtil.AimError(Vector3.Distance(m0.position, tu.target.Center), gunSpreadDeg + (tu.target.Airborne ? 0.4f : 0f));
                }
                Vector3 aim = AIUtil.Lead(m0.position, tu.target, gunSpeed, gunGravity) + tu.aimErr;
                float off = Aim(tu, aim, dt);
                float dist = Vector3.Distance(m0.position, tu.target.Center);
                float tol = (tu.target.Airborne ? 2f : 3.5f) + Mathf.Atan2(tu.target.Radius, Mathf.Max(dist, 1f)) * Mathf.Rad2Deg;
                if (tu.visible && off < tol && tu.cooldown <= 0f && dist < gunRange)
                {
                    Vector3 dir = (aim - m0.position).normalized;
                    if (!AIUtil.FriendlyInLine(m0.position + dir * 4f, dir, dist - tu.target.Radius - 6f, team, transform)) Fire(tu);
                }
            }
        }

        static readonly Health[] candH = new Health[4];
        static readonly float[] candS = new float[4];

        /// <summary>Best few targets in reach of this mount by preference and range; the first with a clear line of fire wins.</summary>
        void PickTarget(Turret tu, Vector3 eye)
        {
            for (int k = 0; k < 4; k++) { candH[k] = null; candS[k] = 0f; }
            var all = Health.All;
            Quaternion inv = Quaternion.Inverse(transform.rotation * tu.mountLocal);
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (!h.Alive || !Health.Enemies(h.team, team)) continue;
                float d = Vector3.Distance(eye, h.Center);
                if (d > gunRange) continue;
                float p = Pref(h, d);
                if (p <= 0f) continue;
                Vector3 dm = inv * (h.Center - eye);
                float el = Mathf.Atan2(dm.y, new Vector2(dm.x, dm.z).magnitude) * Mathf.Rad2Deg;
                if (el < minElevation - 2f || el > maxElevation + 2f) continue;
                float sc = p / (1f + d / 500f) * (h == tu.target ? 1.4f : 1f);
                for (int k = 0; k < 4; k++)
                {
                    if (candH[k] != null && sc <= candS[k]) continue;
                    for (int j = 3; j > k; j--) { candH[j] = candH[j - 1]; candS[j] = candS[j - 1]; }
                    candH[k] = h;
                    candS[k] = sc;
                    break;
                }
            }
            for (int k = 0; k < 4 && candH[k] != null; k++)
                if (LineOfFire(eye, candH[k])) { tu.target = candH[k]; tu.visible = true; return; }
            tu.target = candH[0];
            tu.visible = false;
            tu.thinkT = 0.2f;                       // masked for now: look again soon
        }

        /// <summary>
        /// A shot past our own hull to the target. Units never block; buildings and terrain do, except right next to a
        /// ground target, where the shell's blast still reaches it.
        /// </summary>
        bool LineOfFire(Vector3 from, Health target)
        {
            Vector3 aim = target.Center + Vector3.up * (target.Airborne ? 0f : target.Radius * 0.5f);
            Vector3 d = aim - from;
            float len = d.magnitude;
            int n = Physics.RaycastNonAlloc(from, d / len, hitBuf, len - target.Radius, ~0, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var c = hitBuf[i].collider;
                if (c == null) continue;
                var h = Health.Of(c);
                if (h == target) continue;
                if (c.transform.IsChildOf(transform)) { if (hitBuf[i].distance > 1.5f) return false; continue; }
                if (h != null) continue;
                if (!target.Airborne && (hitBuf[i].point - target.Center).sqrMagnitude < 49f) continue;
                return false;
            }
            return true;
        }

        /// <summary>Traverse and elevate toward a point; returns the remaining angle off (deg).</summary>
        float Aim(Turret tu, Vector3 point, float dt)
        {
            Quaternion mountW = transform.rotation * tu.mountLocal;
            Vector3 d = Quaternion.Inverse(mountW) * (point - tu.pitchBone.position);
            float wantYaw = Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg - tu.restYaw;
            float wantPitch = Mathf.Clamp(Mathf.Atan2(d.y, new Vector2(d.x, d.z).magnitude) * Mathf.Rad2Deg - tu.restPitch, minElevation, maxElevation);
            tu.yaw += Mathf.Clamp(Mathf.DeltaAngle(tu.yaw, wantYaw), -55f * dt, 55f * dt);
            tu.pitch = Mathf.MoveTowards(tu.pitch, wantPitch, 40f * dt);
            rig.Rotate(tu.yawBone, tu.yawAxis, tu.yaw);
            rig.Rotate(tu.pitchBone, tu.pitchAxis, tu.pitch);
            Vector3 mid = MuzzleMid(tu);
            Vector3 barrel = mid - tu.pitchBone.position;
            return barrel.sqrMagnitude > 1e-4f ? Vector3.Angle(barrel, point - mid) : 0f;
        }

        /// <summary>
        /// Centre line of a twin mount: midway between its muzzles. (Measured to one muzzle, the line from the trunnion
        /// is several degrees off the barrels, which made the guns point and shoot wide.)
        /// </summary>
        static Vector3 MuzzleMid(Turret tu)
        {
            Vector3 sum = Vector3.zero;
            int n = 0;
            foreach (var m in tu.muzzles) if (m) { sum += m.position; n++; }
            return n > 0 ? sum / n : tu.pitchBone.position + tu.pitchBone.up;
        }

        void Fire(Turret tu)
        {
            Transform m = tu.muzzles[tu.barrel] ? tu.muzzles[tu.barrel] : tu.pitchBone;
            Vector3 dir = (MuzzleMid(tu) - tu.pitchBone.position).normalized;      // both barrels fire parallel to the centre line
            if (tu.manned) dir = (tu.aimPoint - m.position).normalized;      // fire-control: the player's crosshair
            var s = Shot.Visual(gunSpeed, tracerWidth, tracerWidth * 30f, 1500f, impactKind, impactScale);
            s.gravity = gunGravity;
            s.life = gunRange / gunSpeed + 0.5f;
            new WeaponStats(gunDamage, gunType, gunSplash, gunSplashRadius, gunProximity).Apply(ref s, health, transform);
            s.model = flagship ? ProjectileModel.ShipShell : ProjectileModel.Autocannon;
            s.falloffStart = falloffStart;       // the base damage holds close in and fades with range
            s.falloffEnd = gunRange;
            s.falloffMin = falloffMin;
            Tracers.Fire(m.position + dir * 1.5f, dir, s);
            Vfx.Muzzle(m.position, dir, muzzleScale);
            tu.flashT[tu.barrel] = 0f;
            tu.barrel = 1 - tu.barrel;
            tu.cooldown = gunInterval * 0.5f;
            ShotsFired++;
        }

        // ------------------------------------------------------------------ damage and destruction
        void DamageEffects(float dt)
        {
            if (health == null) return;
            float f = health.Fraction;
            int want = Destroyed ? 7 : f < 0.25f ? 5 : f < 0.5f ? 3 : f < 0.75f ? 1 : 0;
            while (fires.Count < want)
            {
                // a fire breaks out somewhere on the hull
                Vector3 c = hullBounds.center + Vector3.Scale(hullBounds.extents, new Vector3(Random.Range(-0.6f, 0.6f), Random.Range(-0.2f, 0.7f), Random.Range(-0.8f, 0.8f)));
                var e = Vfx.Attach(Vfx.EmitterKind.Burning, transform, c, Quaternion.identity);
                if (e == null) break;
                e.Rate = 1f;
                fires.Add(e);
            }
            if (Destroyed && !Crashed)
            {
                boomT -= dt;
                if (boomT <= 0f)
                {
                    boomT = Random.Range(0.8f, 2f);
                    Vector3 c = transform.TransformPoint(hullBounds.center + Vector3.Scale(hullBounds.extents, new Vector3(Random.Range(-0.7f, 0.7f), Random.Range(-0.5f, 0.8f), Random.Range(-0.9f, 0.9f))));
                    Vfx.Explosion(c, Random.Range(1.6f, 2.6f), false);
                }
            }
        }

        public void Die(DamageInfo d)
        {
            if (Destroyed) return;
            Destroyed = true;
            State = "going down";
            foreach (var tu in turrets) tu.target = null;
            TeamPaint.Burn(gameObject);
            for (int i = 0; i < 3; i++)
                Vfx.Explosion(transform.TransformPoint(hullBounds.center + Vector3.Scale(hullBounds.extents, new Vector3(Random.Range(-0.6f, 0.6f), Random.Range(-0.3f, 0.6f), Random.Range(-0.8f, 0.8f)))), 3f, false);
        }

        void Crash()
        {
            if (Crashed) return;
            Crashed = true;
            vel = Vector3.zero;
            State = "wreck";
            // the gas cells go up as the hull hits: a string of huge blasts along the keel
            StartCoroutine(CrashBlasts());
            foreach (var c in crew) if (c.t) c.t.gameObject.SetActive(false);
            if (CameraRig.Main) CameraRig.Main.Shake(1f);
        }

        IEnumerator CrashBlasts()
        {
            for (int i = 0; i < 6; i++)
            {
                float u = (i / 5f - 0.5f) * 1.6f;
                Vector3 p = transform.TransformPoint(new Vector3(0f, hullBounds.min.y + 2f, hullBounds.center.z + hullBounds.extents.z * u));
                Vfx.Explosion(p, 3.5f, true);
                Vector3 g = p;
                g.y = WorldGround.Height(g.x, g.z) + 0.05f;
                Vfx.Stomp(g, 30f);
                Health.Splash(p, 35f, 1800f, DamageType.HE, Team.None, health, health);
                yield return new WaitForSeconds(0.25f);
            }
        }
    }
}
