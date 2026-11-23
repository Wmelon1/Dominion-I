using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Support drone (DroneKit: Wasp quad, Mender hexacopter, Kite ducted-fan recon). Carried in limited numbers by the
    /// troop transports and launched from their roof hatch. Its job, in order:
    ///  1. Repair: fly to the most valuable damaged strong unit nearby (mechs first, then heavy and medium armour), hover
    ///     behind it away from the threat and play a repair beam on it until its repair charge is spent, moving on to
    ///     the next damaged unit if the charge outlasts the patient.
    ///  2. Recon: once the charge is used up, climb to altitude and orbit points ahead of its own side, its camera gimbal
    ///     sweeping the ground. Everything it sees goes into its side's Intel (Intel.Tick checks Sensing drones).
    /// Flight is kinematic: it accelerates toward where it wants to be, climbs over rooftops (the city's roof-height grid,
    /// looked up ahead along its track), banks and pitches with its acceleration like a real multirotor. Enemies can
    /// shoot it down (flak, machine guns, mech gatlings); it falls spinning and bursts on impact.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class DroneUnit : MonoBehaviour
    {
        public string displayName = "Drone";
        public string unitKey = "Drone_Wasp";
        [Header("Flight")]
        public float cruiseSpeed = 28f;
        public float accel = 14f;
        public float cruiseAlt = 32f;
        [Header("Repair")]
        public float healPool = 900f;
        public float healRate = 180f;
        public float beamRange = 26f;
        [Header("Recon")]
        public float sensorRange = 280f;
        [Header("Shape (filled by the editor setup)")]
        public Vector3 centerLocal = new Vector3(0f, 0.5f, 0f);
        public float radius = 0.9f;

        public enum Mode { Stowed, Launch, ToPatient, Repair, Recon, Down }
        public Mode State { get; private set; } = Mode.Stowed;
        [System.NonSerialized] public Team team;
        [System.NonSerialized] public Health health;
        /// <summary>Set by UnitLOD when the player can't see it: rotors, gimbal and sparks are skipped (flight is not).</summary>
        [System.NonSerialized] public bool LodHidden;
        public Vector3 Velocity => vel;
        public float HealLeft { get; private set; }
        public float Healed { get; private set; }
        public Health Patient => patient;
        /// <summary>Camera up and watching the ground (the side's Intel sweeps it).</summary>
        public bool Sensing => State == Mode.Recon || State == Mode.ToPatient || State == Mode.Repair;

        public static int Launched, Downed;
        static readonly Dictionary<Health, int> assigned = new Dictionary<Health, int>();

        public static void ResetStats()
        {
            Launched = Downed = 0;
            assigned.Clear();
        }

        Transform gimbal, cam, emitter;
        Vector3 gimbalAxis, camAxis;
        readonly List<(Transform t, Vector3 axis, float dir)> rotors = new List<(Transform, Vector3, float)>();
        readonly List<Renderer> blurs = new List<Renderer>();
        RigBones rig;
        LineRenderer beam;
        Health patient;
        Vector3 vel, reconPoint, launchDrift;
        float yaw, pitch, roll, spin, thinkT, reconT, reconAlt, orbitA, orbitDir = 1f, launchY, launchT, sparkT, findT, gYaw, gPitch, downT, bob;
        bool beamOn;
        float simAcc;

        void Awake()
        {
            var rb = GetComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
            rb.interpolation = RigidbodyInterpolation.None;
            // the camera ball is exported beside its yoke: hang it on the yoke so it turns with it
            Transform yoke = null, ball = null;
            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                if (t.name.EndsWith("_GimbalCam")) ball = t;
                else if (t.name.EndsWith("_Gimbal")) yoke = t;
            }
            if (yoke && ball && ball.parent != yoke) ball.SetParent(yoke, true);
            rig = new RigBones(transform);
            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                string n = t.name;
                if (n.Contains("_Rotor_"))
                {
                    int idx = 0;
                    int.TryParse(n.Substring(n.LastIndexOf('_') + 1), out idx);
                    rotors.Add((t, RigBones.LocalAxis(t, transform.up), idx % 2 == 0 ? 1f : -1f));
                }
                else if (n.Contains("_Blur_")) { var r = t.GetComponent<Renderer>(); if (r) blurs.Add(r); }
                else if (n.EndsWith("_GimbalCam")) cam = t;
                else if (n.EndsWith("_Gimbal")) gimbal = t;
                else if (n.EndsWith("_Emitter")) emitter = t;
            }
            if (gimbal) gimbalAxis = RigBones.LocalAxis(gimbal, transform.up);
            if (cam) camAxis = RigBones.LocalAxis(cam, transform.right);
            yaw = transform.eulerAngles.y;
            orbitDir = Random.value < 0.5f ? -1f : 1f;
            bob = Random.Range(0f, 10f);

            var go = new GameObject("Repair Beam");
            go.transform.SetParent(transform, false);
            beam = go.AddComponent<LineRenderer>();
            beam.useWorldSpace = true;
            beam.positionCount = 2;
            beam.numCapVertices = 4;
            beam.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            beam.receiveShadows = false;
            beam.sharedMaterial = Resources.Load<Material>("Dominion/M_RepairBeam");
            beam.enabled = false;
        }

        void OnDisable() => SetPatient(null);

        // ------------------------------------------------------------------ orders
        /// <summary>Out of the carrier's hatch: climb clear, then go to work on 'firstPatient' (or find one).</summary>
        public void Launch(Vector3 from, Vector3 carrierVelocity, Health firstPatient)
        {
            transform.position = from;
            vel = carrierVelocity * 0.8f + Vector3.up * 5f;
            launchY = from.y + 9f;
            launchT = 0f;
            launchDrift = AIUtil.Flat(Random.insideUnitSphere).normalized * 3f;
            HealLeft = healPool;
            State = Mode.Launch;
            SetPatient(firstPatient);
            Launched++;
        }

        /// <summary>Tanks, armoured transports and mechs: what the drones are sent to keep in the fight.</summary>
        public static bool Strong(Health h) =>
            h.cls == UnitClass.Mech || (h.cls == UnitClass.Ground && (h.armor == ArmorClass.Armored || h.armor == ArmorClass.Light));

        /// <summary>Most valuable damaged strong unit of 'team' within range that isn't already being looked after.</summary>
        public static Health PickPatient(Team team, Vector3 from, float range, Health exclude = null, float below = 0.85f)
        {
            Health best = null;
            float bs = 0f;
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (!h.Alive || h.team != team || h == exclude || !Strong(h) || h.Airborne) continue;
                float f = h.Fraction;
                if (f > below) continue;
                float dist = Vector3.Distance(from, h.Center);
                if (dist > range) continue;
                assigned.TryGetValue(h, out int n);
                if (n >= (h.cls == UnitClass.Mech ? 2 : 1)) continue;
                float value = h.cls == UnitClass.Mech ? 3f : h.key == "Tank_Heavy" ? 2f : h.armor == ArmorClass.Armored ? 1.6f : 1f;
                float s = (1f - f) * value / (1f + dist / 500f);
                if (s > bs) { bs = s; best = h; }
            }
            return best;
        }

        void SetPatient(Health p)
        {
            if (patient && assigned.TryGetValue(patient, out int n)) assigned[patient] = Mathf.Max(0, n - 1);
            patient = p;
            if (p) { assigned.TryGetValue(p, out int m); assigned[p] = m + 1; }
        }

        // ------------------------------------------------------------------ death
        public void Die(DamageInfo d)
        {
            if (State == Mode.Down) return;
            State = Mode.Down;
            SetPatient(null);
            beam.enabled = false;
            downT = 0f;
            Downed++;
            vel += AIUtil.Flat(d.dir).normalized * 3f;
            TeamPaint.Burn(gameObject);
            Vfx.SmallImpact(transform.TransformPoint(centerLocal), Vector3.up, true, 1.6f);
        }

        // ------------------------------------------------------------------ per frame
        void Update()
        {
            long perfT0 = Perf.Now;
            UpdateTimed();
            Perf.Add(Perf.Drones, perfT0);
        }

        void UpdateTimed()
        {
            if (State == Mode.Stowed) return;
            float dt = Time.deltaTime;
            if (State != Mode.Down && health != null && !health.SimTick(ref simAcc, out dt)) return;
            if (State == Mode.Down) { Fall(dt); return; }
            thinkT -= dt;
            if (thinkT <= 0f)
            {
                thinkT = 0.4f;
                Think();
            }
            Fly(dt);
            Repair(dt);
            Animate(dt);
        }

        void Think()
        {
            Vector3 pos = transform.position;
            switch (State)
            {
                case Mode.Launch:
                    if (pos.y > launchY - 0.6f || launchT > 3.5f) NextJob(pos);
                    break;
                case Mode.ToPatient:
                case Mode.Repair:
                    if (patient == null || !patient.Alive || patient.Fraction > 0.995f || !patient.gameObject.activeInHierarchy || patient.Airborne)
                    {
                        if (patient && patient.Airborne && patient.Alive) break;          // a Halberd on its jets: wait for it to land
                        NextJob(pos);
                    }
                    else if (health && health.Fraction < 0.45f && Time.time - health.LastHitTime < 2f) GoRecon(pos);   // getting shot to pieces
                    break;
                case Mode.Recon:
                    reconT -= 0.4f;
                    if (reconT <= 0f) PickRecon(pos);
                    findT -= 0.4f;
                    if (HealLeft > 20f && findT <= 0f)
                    {
                        findT = 3f;
                        var p = PickPatient(team, pos, 900f);
                        if (p) { SetPatient(p); State = Mode.ToPatient; }
                    }
                    break;
            }
        }

        void NextJob(Vector3 pos)
        {
            var next = HealLeft > 20f ? PickPatient(team, pos, 700f, patient) : null;
            SetPatient(next);
            if (next) State = Mode.ToPatient;
            else GoRecon(pos);
        }

        void GoRecon(Vector3 pos)
        {
            SetPatient(null);
            State = Mode.Recon;
            PickRecon(pos);
        }

        /// <summary>Orbit a point ahead of our own side, short of where the enemy is thought to be, a little off to one side.</summary>
        void PickRecon(Vector3 pos)
        {
            var war = WarManager.Instance;
            Vector3 obj = war ? war.Objective(team, pos) : pos + transform.forward * 300f;
            Vector3 dir = AIUtil.Flat(obj - pos);
            dir = dir.sqrMagnitude > 1f ? dir.normalized : transform.forward;
            Vector3 side = Vector3.Cross(Vector3.up, dir);
            // stand off on our side of the enemy: the camera reaches, most guns don't bother
            reconPoint = obj - dir * Random.Range(sensorRange * 0.45f, sensorRange * 0.8f) + side * Random.Range(-180f, 180f);
            reconPoint.y = 0f;
            reconT = Random.Range(18f, 32f);
            reconAlt = Random.Range(50f, 80f);
            orbitA = Mathf.Atan2(pos.z - reconPoint.z, pos.x - reconPoint.x);
        }

        Vector3 HoverPoint()
        {
            Vector3 c = patient.Center;
            Vector3 away;
            if (Time.time - patient.LastHitTime < 12f) away = AIUtil.Flat(c - patient.LastHitFrom);
            else away = -AIUtil.Flat(patient.transform.forward);
            away = away.sqrMagnitude > 0.01f ? away.normalized : Vector3.back;
            float r = patient.Radius;
            return c + away * (r + 3.2f) + Vector3.up * (r * 0.55f + 4.5f + 0.4f * Mathf.Sin(Time.time * 1.3f + bob));
        }

        static float Top(float x, float z) => WorldGround.Top(x, z);

        void Fly(float dt)
        {
            Vector3 pos = transform.position;
            Vector3 goal;
            float cap = cruiseSpeed;
            bool low = false;
            switch (State)
            {
                case Mode.Launch:
                    launchT += dt;
                    goal = new Vector3(pos.x, launchY + 1f, pos.z) + launchDrift;
                    cap = 7f;
                    low = true;
                    break;
                case Mode.ToPatient:
                case Mode.Repair:
                    goal = patient ? HoverPoint() : pos;
                    if (State == Mode.Repair && patient) cap = Mathf.Max(8f, patient.Velocity.magnitude + 7f);
                    break;
                default:
                {
                    // orbit the recon point
                    float r = 75f;
                    orbitA += orbitDir * dt * Mathf.Min(cruiseSpeed * 0.55f, 16f) / r;
                    goal = reconPoint + new Vector3(Mathf.Cos(orbitA), 0f, Mathf.Sin(orbitA)) * r;
                    goal.y = Mathf.Max(WorldGround.Height(goal.x, goal.z) + reconAlt, Top(goal.x, goal.z) + 22f);
                    cap = cruiseSpeed * 0.8f;
                    break;
                }
            }
            // getting shot at: jink sideways and climb
            if (health && Time.time - health.LastHitTime < 1.2f && State != Mode.Launch)
                goal += Vector3.Cross(Vector3.up, vel.sqrMagnitude > 1f ? vel.normalized : transform.forward) * (Mathf.Sin(Time.time * 3f + bob) * 12f) + Vector3.up * 8f;

            // altitude: cruise high over the rooftops while travelling, descend onto the job only when close to it
            Vector3 flatTo = AIUtil.Flat(goal - pos);
            float flatDist = flatTo.magnitude;
            Vector3 fv = AIUtil.Flat(vel);
            float roofAhead = Mathf.Max(Top(pos.x, pos.z), Top(pos.x + fv.x * 1.2f, pos.z + fv.z * 1.2f), Top(pos.x + fv.x * 2.6f, pos.z + fv.z * 2.6f));
            // over the patient the roof grid (16 m cells) is too coarse for a street: drop straight down onto the job
            bool overJob = (State == Mode.ToPatient || State == Mode.Repair) && patient && flatDist < 22f;
            if (!low && flatDist > 45f)
                goal.y = Mathf.Max(goal.y, WorldGround.Height(pos.x, pos.z) + cruiseAlt, roofAhead + 12f);
            else if (overJob)
                goal.y = Mathf.Max(goal.y, WorldGround.Height(goal.x, goal.z) + 2.5f);
            else
                goal.y = Mathf.Max(goal.y, roofAhead + 2.5f);

            Vector3 to = goal - pos;
            float dist = to.magnitude;
            Vector3 want = dist > 0.05f ? to / dist * Mathf.Min(cap, dist * 1.3f) : Vector3.zero;
            // a little more authority vertically (props pull straight up) than sideways
            Vector3 dv = want - vel;
            float a = accel * dt;
            dv = new Vector3(Mathf.Clamp(dv.x, -a, a), Mathf.Clamp(dv.y, -a * 1.4f, a * 1.4f), Mathf.Clamp(dv.z, -a, a));
            Vector3 acc = dv / Mathf.Max(dt, 1e-4f);
            vel += dv;
            pos += vel * dt;
            float floor = (overJob ? WorldGround.Height(pos.x, pos.z) : Top(pos.x, pos.z)) + 1.6f;
            if (pos.y < floor) { pos.y = floor; if (vel.y < 0f) vel.y = 0f; }
            transform.position = pos;

            // attitude: nose along the track (or at the patient while repairing), pitch and bank with the acceleration
            Vector3 face = State == Mode.Repair && patient ? AIUtil.Flat(patient.Center - pos) : fv;
            if (face.sqrMagnitude > 0.5f) yaw = Mathf.MoveTowardsAngle(yaw, Mathf.Atan2(face.x, face.z) * Mathf.Rad2Deg, 140f * dt);
            Quaternion yq = Quaternion.Euler(0f, yaw, 0f);
            Vector3 lv = Quaternion.Inverse(yq) * (vel * 0.85f + acc * 0.35f);
            pitch = Mathf.Lerp(pitch, Mathf.Clamp(lv.z * 0.9f, -24f, 24f), 1f - Mathf.Exp(-4f * dt));
            roll = Mathf.Lerp(roll, Mathf.Clamp(-lv.x * 0.9f, -24f, 24f), 1f - Mathf.Exp(-4f * dt));
            transform.rotation = yq * Quaternion.Euler(pitch, 0f, roll);
        }

        void Repair(float dt)
        {
            beamOn = false;
            if ((State != Mode.ToPatient && State != Mode.Repair) || patient == null) { if (beam.enabled) beam.enabled = false; return; }
            Vector3 c = patient.Center;
            Vector3 from = emitter ? emitter.position : transform.TransformPoint(centerLocal);
            float d = Vector3.Distance(from, c) - patient.Radius;
            if (State == Mode.ToPatient && d < beamRange) State = Mode.Repair;
            if (State == Mode.Repair && d < beamRange * 1.15f && HealLeft > 0f)
            {
                beamOn = true;
                float h = patient.Heal(Mathf.Min(healRate * dt, HealLeft));
                HealLeft -= h;
                Healed += h;
                if (HealLeft <= 0.5f)
                {
                    GoRecon(transform.position);
                    if (beam.enabled) beam.enabled = false;
                    return;
                }
            }
            if (!beamOn || LodHidden) { if (beam.enabled) beam.enabled = false; return; }
            // beam lands on the hull surface facing the drone, flickering a little
            Vector3 hit = c + (from - c).normalized * patient.Radius * 0.7f + Random.insideUnitSphere * 0.25f;
            beam.enabled = true;
            beam.SetPosition(0, from);
            beam.SetPosition(1, hit);
            float w = 0.07f + 0.035f * Mathf.Sin(Time.time * 31f);
            beam.startWidth = w * 0.6f;
            beam.endWidth = w * 1.4f;
            sparkT -= dt;
            if (sparkT <= 0f)
            {
                sparkT = Random.Range(0.18f, 0.35f);
                Vfx.SmallImpact(hit, (from - hit).normalized, true, 0.55f);
            }
        }

        void Animate(float dt)
        {
            spin += dt * 2300f;
            if (LodHidden) return;
            foreach (var (t, axis, dir) in rotors) rig.Rotate(t, axis, spin * dir + (dir > 0f ? 0f : 45f));
            // camera gimbal: on the patient, or sweeping the ground ahead while on recon
            Vector3 look;
            if (patient && (State == Mode.ToPatient || State == Mode.Repair)) look = patient.Center;
            else
            {
                float sweep = Mathf.Sin(Time.time * 0.35f + bob) * 50f;
                Vector3 ahead = Quaternion.Euler(0f, yaw + sweep, 0f) * Vector3.forward * 60f;
                look = transform.position + ahead;
                look.y = WorldGround.Height(look.x, look.z);
            }
            Vector3 lp = transform.InverseTransformPoint(look);
            float wantYaw = Mathf.Clamp(Mathf.Atan2(lp.x, lp.z) * Mathf.Rad2Deg, -170f, 170f);
            float wantPitch = Mathf.Clamp(Mathf.Atan2(-lp.y, new Vector2(lp.x, lp.z).magnitude) * Mathf.Rad2Deg, -20f, 88f);
            gYaw = Mathf.MoveTowardsAngle(gYaw, wantYaw, 160f * dt);
            gPitch = Mathf.MoveTowards(gPitch, wantPitch, 110f * dt);
            if (gimbal) rig.Rotate(gimbal, gimbalAxis, gYaw);
            if (cam) rig.Rotate(cam, camAxis, gPitch);
        }

        void Fall(float dt)
        {
            downT += dt;
            vel += Vector3.down * 9.81f * dt;
            vel *= 1f - 0.15f * dt;
            Vector3 pos = transform.position + vel * dt;
            yaw += dt * 540f;
            spin += dt * 600f;
            foreach (var (t, axis, dir) in rotors) rig.Rotate(t, axis, spin * dir);
            transform.rotation = Quaternion.Euler(0f, yaw, 0f) * Quaternion.Euler(Mathf.Min(downT * 30f, 35f), 0f, Mathf.Min(downT * 45f, 50f));
            float floor = Top(pos.x, pos.z) + 0.2f;
            if (pos.y <= floor || downT > 12f)
            {
                pos.y = Mathf.Max(pos.y, floor);
                transform.position = pos;
                Vfx.Explosion(pos + Vector3.up * 0.3f, 0.55f, false);
                gameObject.SetActive(false);
                return;
            }
            transform.position = pos;
        }
    }
}
