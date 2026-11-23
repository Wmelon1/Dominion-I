using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Tanks and the tracked APC. Every road wheel is a sprung contact; the two tracks push independently
    /// (skid steering: pivot in place, or one track faster in a turn). Squat, dive, roll and gun-blast rock
    /// come from the physics. Seamless track blend shapes, spinning wheels, turret, gun(s), radar, ramp.
    /// </summary>
    public class TrackedVehicle : Vehicle
    {
        [Header("Tracks")]
        public float trackPitch = 0.17f;
        public string[] wheelBones = new string[0];
        public float[] wheelRadii = new float[0];
        public SkinnedMeshRenderer trackLeft, trackRight;

        [Header("Turret / guns")]
        public string turretBone = "turret";
        public string gunBone = "gun";
        public float gunMin = -8f, gunMax = 20f;
        public string[] barrelBones = new string[0];
        public string[] muzzleBones = new string[0];
        public string[] flashBones = new string[0];
        public float[] recoils = new float[0];
        public float fireInterval = 4f;
        public float tracerWidth = 0.25f;
        public string radarBone = "";
        public float turretYawSpeed = 36f, turretPitchSpeed = 20f;
        [Tooltip("Artillery: shells fly a true ballistic arc and the gun elevates to land them on the aim point.")]
        public bool ballistic;
        public float shellSpeed = 110f;

        [Header("Door / ramp (optional)")]
        public string doorBone = "";
        public string doorAxis = "x";
        public float doorAngle = 100f;

        [Header("Driving")]
        public float maxSpeed = 15f;
        public float maxReverse = 6f;
        public float maxTurn = 46f;
        public float engineAccel = 5.5f;
        public float suspensionTravel = 0.15f;

        Suspension susp;
        float distL, distR, cooldown, radarAngle, doorT, doorSign = 1f;
        bool doorOpen;
        public override void SetDoor(bool open) { if (door) doorOpen = open; }
        protected override bool CanProxy => true;
        protected override float ProxyTopSpeed => maxSpeed;
        protected override float ProxyTurnRate => 32f;
        int trackShapeL = -1, trackShapeR = -1, nextGun, contactsL, contactsR;
        readonly List<(Transform bone, Vector3 axis, float radius, bool left)> spinners = new List<(Transform, Vector3, float, bool)>();
        readonly List<Gun> guns = new List<Gun>();
        Turret turret;
        Transform radar, door;
        Vector3 radarAxis, doorLocalAxis;

        public override string ControlsHelp =>
            "W/S  drive     A/D  steer (pivot when stopped)     Space  brake\nMouse  aim turret     LMB  fire" +
            (door ? "     F  ramp" : "") + "\nR  reset upright     E  exit";

        public override string Status
        {
            get
            {
                string s = base.Status;
                if (guns.Count > 0) s += cooldown > 0.3f ? $"   reloading {cooldown:0.0}s" : "   ready";
                return s;
            }
        }

        protected override void Awake()
        {
            base.Awake();
            susp = new Suspension(Body, transform);
            for (int i = 0; i < wheelBones.Length; i++)
            {
                var b = rig[wheelBones[i]];
                if (b == null) continue;
                float r = Mathf.Max(0.05f, wheelRadii[i]);
                bool left = wheelBones[i].Contains("_L");
                spinners.Add((b, RigBones.LocalAxis(b, transform.right), r, left));
                if (wheelBones[i].StartsWith("wheel"))
                {
                    var w = susp.Add(b, r);
                    w.moveVisual = false;              // the track belt is rigid: the whole hull rides the springs instead
                    w.left = left;
                    if (left) contactsL++; else contactsR++;
                }
            }
            susp.Tune(Body.mass, suspensionTravel, 0.65f);
            susp.AddAntiRollBars(0.6f);
            // balance the hull over the road wheels (long gun barrels used to drag the centre of mass forward)
            Vector3 wc = susp.WheelCentroid();
            Body.centerOfMass = new Vector3(wc.x, CenterOfMass.y, wc.z);
            if (trackLeft && trackLeft.sharedMesh) trackShapeL = trackLeft.sharedMesh.GetBlendShapeIndex("track_cycle");
            if (trackRight && trackRight.sharedMesh) trackShapeR = trackRight.sharedMesh.GetBlendShapeIndex("track_cycle");
            string firstMuzzle = muzzleBones.Length > 0 ? muzzleBones[0] : gunBone;
            turret = Turret.Create(rig, transform, turretBone, gunBone, firstMuzzle, gunMin, gunMax, turretYawSpeed, turretPitchSpeed);
            // the roof machine gun's muzzle, carried on the turret (vehicle space at rest, from the TankKit build)
            Vector3 mgVeh = unitKey == "Tank_Medium" ? new Vector3(0.55f, 2.66f, 1.59f) : unitKey == "Tank_Heavy" ? new Vector3(0.62f, 2.85f, 0.8f)
                          : unitKey == "Tank_Artillery" ? new Vector3(0.8f, 3.32f, -0.16f) : Vector3.zero;
            if (mgVeh != Vector3.zero && turret != null)
            {
                hasMg = true;
                mgLocal = turret.turret.InverseTransformPoint(transform.TransformPoint(mgVeh));
                mgFwdLocal = turret.turret.InverseTransformDirection(transform.forward);
            }
            for (int i = 0; i < barrelBones.Length; i++)
                guns.Add(new Gun { barrel = rig[barrelBones[i]], muzzle = rig[muzzleBones[i]], flash = rig[flashBones[i]], recoilDist = recoils[i],
                    muzzleScale = muzzleScale, impact = impactKind, impactScale = impactScale });
            radar = rig[radarBone];
            if (radar) radarAxis = RigBones.LocalAxis(radar, transform.up);
            // exhaust on the engine deck, rear right, puffing up and back
            SetupGroundEffects(new Vector3(localBounds.center.x + localBounds.extents.x * 0.45f, localBounds.min.y + localBounds.size.y * 0.55f,
                localBounds.min.z + 0.6f), (Vector3.up + Vector3.back * 0.5f).normalized);
            door = rig[doorBone];
            if (door)
            {
                doorLocalAxis = RigBones.LocalAxis(door, doorAxis == "x" ? transform.right : transform.up);
                doorSign = RigBones.OpenSign(door, doorLocalAxis, doorAngle, transform.TransformPoint(localBounds.center));
            }
        }

        bool Autocannon => fireInterval < 0.5f;
        public override float ProjectileSpeed => ballistic ? shellSpeed : Autocannon ? 520f : 320f;
        public override float ProjectileGravity => ballistic ? 1f : 0.15f;
        public override bool Reloaded => cooldown <= 0f;

        public override bool GetAim(out Vector3 origin, out Vector3 dir)
        {
            var g = guns.Count > 0 ? guns[nextGun] : null;
            origin = g != null && g.muzzle ? g.muzzle.position : transform.position;
            dir = g != null ? g.Direction : transform.forward;
            return g != null && g.muzzle;
        }

        protected override void OnDestroyed(DamageInfo d)
        {
            base.OnDestroyed(d);
            // the ammunition cooks off: the turret is knocked askew on its ring
            if (turret != null)
            {
                turret.yaw += Random.Range(-40f, 40f);
                turret.pitch = Random.Range(turret.minPitch, turret.minPitch * 0.3f);
                rig.Rotate(turret.turret, turret.yawAxis, turret.yaw);
                rig.Rotate(turret.gun, turret.pitchAxis, turret.pitch);
            }
        }

        protected override void Simulate(float dt)
        {
            float throttle = input.move.y;
            float steer = input.move.x;
            Vector3 fwd = transform.forward, right = transform.right;
            float vFwd = Vector3.Dot(Body.linearVelocity, fwd);
            // skid steering: left track = throttle + steer, right = throttle - steer
            float tl = Mathf.Clamp(throttle + steer * 0.8f, -1f, 1f);
            float tr = Mathf.Clamp(throttle - steer * 0.8f, -1f, 1f);
            float engine = Body.mass * engineAccel;
            bool coasting = Mathf.Abs(throttle) < 0.05f && Mathf.Abs(steer) < 0.05f;
            bool reversingInput = throttle * vFwd < -0.5f;
            float brake = !Occupied ? 6f : input.jump ? 7f : reversingInput ? 4.5f : coasting ? 1.6f : 0f;   // parked: brakes on
            float latStiff = Mathf.Abs(steer) > 0.1f ? 2.5f : 7f;     // tracks slip sideways while skid-turning

            int grounded = susp.Step(dt, w =>
            {
                float t = w.left ? tl : tr;
                int n = w.left ? contactsL : contactsR;
                float top = t >= 0f ? maxSpeed : maxReverse;
                float rr = vFwd / top;
                float lim = Mathf.Sign(t) == Mathf.Sign(vFwd) ? Mathf.Clamp01(1f - rr * rr * rr * rr) : 1f;   // full pull until near top speed
                float drive = reversingInput ? 0f : t * engine * 0.5f / Mathf.Max(1, n) * lim;
                return susp.Tyre(w, fwd, right, drive, brake, 0.95f, latStiff, dt);
            });

            if (grounded > 0)
            {
                // yaw rate controller standing in for the steering clutch / differential
                float wantYaw = steer * maxTurn * Mathf.Lerp(1f, 0.55f, Mathf.Abs(vFwd) / maxSpeed) * (vFwd < -0.5f ? -1f : 1f);
                float yawNow = Vector3.Dot(Body.angularVelocity, transform.up) * Mathf.Rad2Deg;
                Body.AddTorque(transform.up * ((wantYaw - yawNow) * Mathf.Deg2Rad * 3.5f), ForceMode.Acceleration);
            }
        }

        // ------------------------------------------------------------------ roof machine gun
        bool hasMg;
        Vector3 mgLocal, mgFwdLocal;
        float mgCd, mgThink;
        int mgBurst = 10;
        Health mgTarget;
        public static int MgRounds;

        /// <summary>
        /// The commander's roof MG: engages infantry and soft vehicles within 300 m in a +-40 deg arc of where the gun points,
        /// in bursts (AI and player alike; the player can also hold Q to fire it at the crosshair).
        /// </summary>
        void RoofGun(float dt)
        {
            if (!hasMg || Destroyed || turret == null) return;
            Vector3 muzzle = turret.turret.TransformPoint(mgLocal);
            Vector3 fwd = turret.turret.TransformDirection(mgFwdLocal);
            mgCd -= dt;
            if (PlayerDriven && Occupied)
            {
                Vector3 to = input.aimPoint - muzzle;
                if (input.special && mgCd <= 0f && Vector3.Angle(AIUtil.Flat(fwd), AIUtil.Flat(to)) < 45f) FireMg(muzzle, to.normalized);
                return;
            }
            if (health == null || !Occupied) return;
            mgThink -= dt;
            if (mgThink <= 0f)
            {
                mgThink = 0.5f;
                mgTarget = null;
                float bd = 300f;
                foreach (var h in Health.All)
                {
                    if (!h.Alive || !Health.Enemies(h.team, team) || h.Airborne) continue;
                    if (h.cls != UnitClass.Soldier && h.armor != ArmorClass.Soft) continue;
                    Vector3 to = h.Center - muzzle;
                    float d = to.magnitude;
                    if (d > bd || Vector3.Angle(AIUtil.Flat(fwd), AIUtil.Flat(to)) > 40f) continue;
                    if (!AIUtil.Visible(muzzle, h, transform)) continue;
                    if (AIUtil.FriendlyInLine(muzzle, to / d, d - 1f, team, transform)) continue;
                    bd = d;
                    mgTarget = h;
                }
            }
            if (mgTarget == null || !mgTarget.Alive || mgCd > 0f) return;
            float dist = Vector3.Distance(muzzle, mgTarget.Center);
            Vector3 aim = AIUtil.Lead(muzzle, mgTarget, 600f, 0.15f) + AIUtil.AimError(dist, 1.1f);
            FireMg(muzzle, (aim - muzzle).normalized);
            if (--mgBurst <= 0) { mgBurst = Random.Range(8, 16); mgCd = Random.Range(0.6f, 1.1f); }
        }

        void FireMg(Vector3 muzzle, Vector3 dir)
        {
            var s = Shot.Visual(600f, 0.035f, 2.6f, 50f, ImpactKind.Bullet, 0.35f);
            Armory.TankMG.Apply(ref s, health, transform);
            s.model = ProjectileModel.MG;
            Tracers.Fire(muzzle, dir, s);
            Vfx.Muzzle(muzzle, dir, 0.07f);
            mgCd = Mathf.Max(mgCd, 0.09f);
            MgRounds++;
        }

        protected override void Animate(float dt, float moved)
        {
            RoofGun(dt);
            UpdateGroundEffects(input.move.y + input.move.x * 0.6f);
            float half = Mathf.Max(0.8f, localBounds.extents.x * 0.8f);
            float turn = YawRate * Mathf.Deg2Rad * dt * half;
            distL += moved + turn;
            distR += moved - turn;
            if (!LodHidden)
            {
                foreach (var w in spinners)
                    rig.Rotate(w.bone, w.axis, (w.left ? distL : distR) / w.radius * Mathf.Rad2Deg);
                if (trackShapeL >= 0) trackLeft.SetBlendShapeWeight(trackShapeL, Mathf.Repeat(distL / trackPitch, 1f) * 100f);
                if (trackShapeR >= 0) trackRight.SetBlendShapeWeight(trackShapeR, Mathf.Repeat(distR / trackPitch, 1f) * 100f);
            }

            cooldown = Mathf.Max(0f, cooldown - dt);
            if (Occupied)
            {
                if (turret != null) turret.AimAt(rig, transform, input.aimPoint, dt, ballistic ? shellSpeed : 0f);
                if (input.fire && cooldown <= 0f && guns.Count > 0)
                {
                    var g = guns[nextGun];
                    var shot = MakeShot(ProjectileSpeed, tracerWidth, ballistic ? 4.5f : tracerWidth * 60f, Autocannon ? 2500f : 60000f, impactKind, impactScale);
                    shot.gravity = ProjectileGravity;
                    if (ballistic) shot.life = 16f;
                    g.Shoot(shot);
                    if (!Body.isKinematic && g.muzzle)
                    {
                        // gun blast rocks the hull on its springs (big guns) or shudders it (autocannons)
                        float impulse = Body.mass * (fireInterval >= 1f ? 0.16f : 0.004f);
                        Body.AddForceAtPosition(-g.Direction * impulse, g.muzzle.position, ForceMode.Impulse);
                    }
                    nextGun = (nextGun + 1) % guns.Count;
                    cooldown = fireInterval;
                }
                if (input.action1Down && door) doorOpen = !doorOpen;
            }
            foreach (var g in guns) g.Animate(rig, dt);
            if (radar)
            {
                radarAngle = Mathf.Repeat(radarAngle + 120f * dt, 360f);
                if (!LodHidden) rig.Rotate(radar, radarAxis, radarAngle);
            }
            if (door)
            {
                doorT = Mathf.MoveTowards(doorT, doorOpen ? 1f : 0f, dt / 1.5f);
                rig.Rotate(door, doorLocalAxis, doorSign * doorAngle * Mathf.SmoothStep(0f, 1f, doorT));
            }
        }
    }
}
