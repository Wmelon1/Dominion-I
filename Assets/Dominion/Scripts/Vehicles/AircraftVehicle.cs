using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Force-based flight model: lift from angle of attack (with stall), parasitic + induced drag, thrust,
    /// side-slip force, weather-vane stability and dynamic-pressure-scaled control authority. On the ground the
    /// aircraft sits on sprung landing gear with tyre friction, wheel brakes and nose / tail-wheel steering.
    /// Rig: control surfaces, propeller + blur, afterburners, retractable gear, canopy, wheels, guns.
    /// Keys: Shift/Ctrl throttle, W/S pitch (S = pull up), A/D roll (steer on the ground), Z/C rudder,
    /// LMB guns, G gear, F canopy, Space brakes.
    /// </summary>
    public class AircraftVehicle : Vehicle
    {
        [System.Serializable]
        public class Surface { public string bone; public string axis; public float max; [System.NonSerialized] public float sign = 1f, cur; [System.NonSerialized] public Transform t; }
        [System.Serializable]
        public class GearLeg { public string bone; public string axis; public float angle; [System.NonSerialized] public Transform t; [System.NonSerialized] public Vector3 local; }

        [Header("Rig")]
        public List<Surface> surfaces = new List<Surface>();
        public List<GearLeg> gears = new List<GearLeg>();
        public string[] wheelBones = new string[0];
        public float[] wheelRadii = new float[0];
        public string canopyMode = "";
        public float canopyTravel = 0.8f;
        public bool hasProp;
        public string[] muzzleBones = new string[0];
        public string[] afterburnerBones = new string[0];
        public float fireInterval = 0.06f;

        [Header("Flight (design figures)")]
        public float maxSpeed = 220f;            // level top speed at full throttle (m/s)
        public float takeoffSpeed = 60f;         // lift-off speed (m/s)
        public float thrustToWeight = 0.5f;
        public float pitchRate = 55f, rollRate = 150f, yawRate = 22f;   // steady rates at full deflection (deg/s)
        public float gearTravel = 0.22f;

        const float Rho = 1.225f, ClAlpha = 4.8f, AlphaStall = 0.26f, ClMax = 1.25f, InducedK = 0.045f;
        float wingArea, maxThrust, cd0, qRef;

        public float Throttle { get; private set; }
        bool gearDown = true, canopyOpen, grounded = true, stalled;
        float gearT, canopyT, propAngle, cooldown, crashT, alpha, airspeed;
        int nextGun;
        Transform prop, blur, canopy;
        float canopySign = 1f;
        Suspension susp;
        readonly List<(WheelContact w, Vector3 axis)> wheelVis = new List<(WheelContact, Vector3)>();
        readonly List<(Transform muzzle, Transform flash)> muzzles = new List<(Transform, Transform)>();
        readonly List<Transform> burners = new List<Transform>();
        float[] flashT;
        Emitter propSmoke, burning;
        int shotCount;

        public override float RestHeight => -localBounds.min.y;
        protected override Vector3 CenterOfMass => new Vector3(0f, -0.1f, 0f);   // the model origin is the CG
        public override bool CanExit => grounded && Body.linearVelocity.magnitude < 3f;
        public override float CameraDistance => Mathf.Clamp(localBounds.size.magnitude * 1.1f, 12f, 40f);
        public bool Grounded => grounded;
        /// <summary>Height above the ground directly below (terrain on the city maps).</summary>
        public float Altitude => transform.position.y - RestHeight - WorldGround.Height(transform.position.x, transform.position.z);
        public float Airspeed => airspeed;
        /// <summary>Angle of attack (radians).</summary>
        public float AoA => alpha;
        public bool Stalled => stalled;
        public bool GearDown => gearDown;
        public bool Jet => !hasProp;
        bool Cannon => fireInterval < 0.04f;
        public override float ProjectileSpeed => 650f + airspeed;
        bool shotDown, wrecked;
        float deathRoll;

        public override bool GetAim(out Vector3 origin, out Vector3 dir)
        {
            origin = muzzles.Count > 0 ? muzzles[0].muzzle.position : transform.position;
            dir = transform.forward;
            return muzzles.Count > 0;
        }

        /// <summary>Start in flight (War mode): gear up, at speed, engine at the given throttle.</summary>
        public void LaunchAirborne(float speed, float throttle)
        {
            Wake();
            gearDown = false;
            gearT = 1f;
            grounded = false;
            Throttle = throttle;
            foreach (var wc in susp.wheels) wc.enabled = false;
            Body.linearVelocity = transform.forward * speed;
            Body.angularVelocity = Vector3.zero;
            airspeed = speed;
        }

        protected override void OnDestroyed(DamageInfo d)
        {
            if (propSmoke) propSmoke.Rate = 0f;
            if (!grounded && Altitude > 3f)
            {
                // shot down: a burst, then the burning airframe falls out of the sky and blows up where it lands
                shotDown = true;
                deathRoll = Random.Range(-1f, 1f) > 0f ? 1f : -1f;
                Vfx.Explosion(transform.position, 0.9f, false);
                Burn(Vector3.zero);
                Wake();
                return;
            }
            Wreck();
        }

        void Wreck()
        {
            if (wrecked) return;
            wrecked = true;
            Vector3 c = transform.position;
            Vfx.Explosion(c, 1.8f, true);
            Effects.Blast(c, 10f, 5f, 0.6f, transform);
            Health.Splash(c, 11f, 260f, DamageType.HE, Team.None, health, health);
            Burn(Vector3.zero);
            Throttle = 0f;
        }

        public override string ControlsHelp =>
            "Shift/Ctrl  throttle     W/S  pitch (S = pull up)\nA/D  roll (steer on the ground)     Z/C  rudder\n" +
            "LMB  guns     G  gear     F  canopy     Space  brakes\nR  reset upright     E  exit (on the ground, stopped)" +
            (unitKey == "Aircraft_Wraith" ? "\nQ  air-to-air missile at the aircraft nearest the nose" : unitKey == "Aircraft_Saber" ? "\nQ  drop the fuel tanks" : "");

        public override string Status =>
            $"{airspeed * 3.6f:0} km/h   throttle {Throttle * 100f:0}%   alt {Mathf.Max(0f, Altitude):0} m   AoA {alpha * Mathf.Rad2Deg:0}°" +
            (gears.Count > 0 ? (gearDown ? "   gear DOWN" : "   gear UP") : "") + (stalled ? "   STALL" : "") + (crashT > 0f ? "   CRASHED" : "") + (unitKey == "Aircraft_Wraith" ? $"   AAM {MissilesLeft}" : "");

        // ------------------------------------------------------------------ underwing stores
        readonly System.Collections.Generic.List<Transform> stores = new System.Collections.Generic.List<Transform>();
        readonly System.Collections.Generic.List<(Transform t, Vector3 v, float age)> falling = new System.Collections.Generic.List<(Transform, Vector3, float)>();
        int storeNext;
        float missileCd;
        bool tanksGone;
        public static int AamFired, TanksDropped;
        public bool HasMissiles => unitKey == "Aircraft_Wraith" && storeNext < stores.Count && !Destroyed;
        public int MissilesLeft => unitKey == "Aircraft_Wraith" ? stores.Count - storeNext : 0;

        /// <summary>Wraith: launch the next air-to-air missile off its rail at 'target' (it homes).</summary>
        public bool FireMissile(Health target)
        {
            if (!HasMissiles || missileCd > 0f || target == null || !target.Alive) return false;
            var st = stores[storeNext++];
            Vector3 p = st.position - transform.up * 0.25f;
            rig.Scale(st, 0.001f);                               // off the rail
            Missile.Launch(p, transform.forward, target.Center, transform, health ? Armory.AirMissile : Armory.None, health, target, 1f, Velocity.magnitude);
            AamFired++;
            Vfx.Muzzle(p, -transform.forward, 0.45f);            // motor ignition smoke back over the wing
            missileCd = 1.2f;
            return true;
        }

        /// <summary>The enemy aircraft nearest the nose (within 25 deg, 2.5 km), for the player's missile.</summary>
        Health MissileTarget()
        {
            Health best = null;
            float ba = 25f;
            foreach (var h in Health.All)
            {
                if (!h.Alive || !h.Airborne || h.IsDrone || (team != Team.None && !Health.Enemies(h.team, team))) continue;
                Vector3 to = h.Center - transform.position;
                if (to.sqrMagnitude > 2500f * 2500f || h.transform == transform) continue;
                float a = Vector3.Angle(transform.forward, to);
                if (a < ba) { ba = a; best = h; }
            }
            return best;
        }

        /// <summary>Saber: drop the fuel tanks before a fight (they tumble away).</summary>
        public void JettisonTanks()
        {
            if (tanksGone || unitKey != "Aircraft_Saber") return;
            tanksGone = true;
            if (stores.Count > 0) TanksDropped++;
            foreach (var st in stores) falling.Add((st, Velocity, 0f));
        }

        void UpdateStores(float dt)
        {
            missileCd -= dt;
            if (Occupied && PlayerDriven && input.special)
            {
                if (unitKey == "Aircraft_Wraith") FireMissile(MissileTarget());
                else JettisonTanks();
            }
            for (int i = falling.Count - 1; i >= 0; i--)
            {
                var f = falling[i];
                f.age += dt;
                f.v += Physics.gravity * dt;
                f.v *= 1f - 0.25f * dt;
                f.t.position += f.v * dt;
                f.t.rotation *= Quaternion.Euler(25f * dt, 0f, 12f * dt);
                Vector3 fp = f.t.position;
                if (f.age > 4f || fp.y < WorldGround.Height(fp.x, fp.z))
                {
                    rig.Scale(f.t, 0.001f);
                    falling.RemoveAt(i);
                    continue;
                }
                falling[i] = f;
            }
        }

        protected override void Awake()
        {
            base.Awake();
            for (int i = 1; i <= 6; i++) { var st = rig[$"store_{i}"]; if (st) stores.Add(st); }
            float g = -Physics.gravity.y;
            float m = Body.mass;
            wingArea = 2f * m * g / (Rho * takeoffSpeed * takeoffSpeed * 1.05f);
            maxThrust = m * g * thrustToWeight;
            cd0 = 2f * maxThrust / (Rho * maxSpeed * maxSpeed * wingArea);
            qRef = 0.5f * Rho * takeoffSpeed * takeoffSpeed;

            Vector3 fwd = transform.forward, up = transform.up, right = transform.right;
            foreach (var s in surfaces)
            {
                s.t = rig[s.bone];
                if (s.t == null) continue;
                Vector3 hinge = s.t.rotation * Vector3.up;               // the bone runs along the hinge line
                Vector3 te = Vector3.Cross(hinge, -fwd);                 // trailing-edge motion for +angle
                if (s.axis == "pitch") s.sign = Vector3.Dot(te, up) >= 0f ? 1f : -1f;
                else if (s.axis == "yaw") s.sign = Vector3.Dot(te, right) >= 0f ? 1f : -1f;
                else
                {
                    float ted = Vector3.Dot(te, up) >= 0f ? 1f : -1f;
                    s.sign = s.bone.EndsWith("_L") ? -ted : ted;          // roll right: left TE down, right TE up
                }
            }
            foreach (var gl in gears)
            {
                gl.t = rig[gl.bone];
                if (gl.t == null) continue;
                gl.local = gl.axis == "x" ? Vector3.right : Vector3.up;
                Transform wheel = null;
                foreach (Transform c in gl.t) if (c.name.StartsWith("wheel")) wheel = c;
                if (wheel != null)
                {
                    Vector3 rel = wheel.position - gl.t.position;
                    Quaternion rot = gl.t.rotation * Quaternion.AngleAxis(gl.angle, gl.local) * Quaternion.Inverse(gl.t.rotation);
                    if (Vector3.Dot(rot * rel - rel, up) < 0f) gl.angle = -gl.angle;   // retracting must lift the wheel
                }
            }
            susp = new Suspension(Body, transform);
            for (int i = 0; i < wheelBones.Length; i++)
            {
                var b = rig[wheelBones[i]];
                if (b == null) continue;
                var w = susp.Add(b, Mathf.Max(0.05f, wheelRadii[i]));
                w.steered = wheelBones[i] == "wheel_N" || wheelBones[i] == "wheel_T";
                wheelVis.Add((w, RigBones.LocalAxis(b, right)));
            }
            susp.Tune(Body.mass, gearTravel, 0.5f);
            prop = rig["prop"];
            blur = rig["prop_blur"];
            canopy = rig["canopy"];
            if (canopy && canopyMode == "hinge")
                canopySign = RigBones.OpenSign(canopy, Vector3.right, canopyTravel, transform.TransformPoint(localBounds.center));
            foreach (var mz in muzzleBones)
                if (rig[mz]) muzzles.Add((rig[mz], rig[mz.Replace("muzzle", "flash")]));
            flashT = new float[muzzles.Count];
            for (int i = 0; i < flashT.Length; i++) flashT[i] = 99f;
            foreach (var a in afterburnerBones) if (rig[a]) burners.Add(rig[a]);
            if (prop)
                propSmoke = Vfx.Attach(Vfx.EmitterKind.PropSmoke, transform, transform.InverseTransformPoint(prop.position) + Vector3.back * 0.8f, Quaternion.identity);
        }

        public override void OnExit()
        {
            base.OnExit();
            Throttle = 0f;
        }

        protected override void OnImpact(Collision c)
        {
            if (c.contactCount == 0) return;
            float into = Mathf.Abs(Vector3.Dot(c.relativeVelocity, c.GetContact(0).normal));
            if (shotDown && !wrecked)
            {
                if (into > 2f || c.relativeVelocity.magnitude > 15f) Wreck();
                return;
            }
            // a crash is a hard hit INTO a surface; sliding contact (tail scrape on rotation, belly slide) is not
            if (!Occupied || crashT > 0f) return;
            if (into > 7f && health != null && !Destroyed)
            {
                // War mode: a crash is fatal
                health.Kill(new DamageInfo { point = transform.position, dir = c.relativeVelocity, attacker = health.LastAttacker });
                return;
            }
            if (into > 7f)
            {
                crashT = 3f;
                Throttle = 0f;
                Vfx.Explosion(transform.position, 1.8f, true);
                Effects.Blast(transform.position, 10f, 5f, 0.6f, transform);
                if (burning == null) burning = Vfx.Attach(Vfx.EmitterKind.Burning, transform, Vector3.zero, Quaternion.identity);
                if (burning) burning.Rate = 1f;
            }
        }

        public override void ResetUpright()
        {
            base.ResetUpright();
            if (burning) { burning.Release(8f); burning = null; }
            gearDown = true;
            gearT = 0f;
            crashT = 0f;
        }

        protected override void Simulate(float dt)
        {
            if (shotDown && !wrecked)
            {
                // no engine, wing shredded: little lift, the burning airframe rolls and noses over
                Vector3 vv = Body.linearVelocity;
                float sp = vv.magnitude;
                if (sp > 1f)
                {
                    float qq = 0.5f * Rho * sp * sp;
                    Body.AddForce(-vv / sp * (qq * wingArea * cd0 * 2.5f));
                    Body.AddForce(Vector3.Cross(vv / sp, transform.right).normalized * (qq * wingArea * 0.12f));
                }
                Body.AddRelativeTorque(new Vector3(0.5f, 0f, deathRoll * 2.2f), ForceMode.Acceleration);
                return;
            }
            if (Destroyed) return;
            if (crashT > 0f)
            {
                crashT -= dt;
                Throttle = 0f;
                if (crashT <= 0f) ResetUpright();
            }
            float th = (input.sprint ? 1f : 0f) - (input.crouch ? 1f : 0f);
            if (crashT <= 0f) Throttle = Mathf.Clamp01(Throttle + th * 0.45f * dt);

            Vector3 v = Body.linearVelocity;
            Vector3 lv = transform.InverseTransformDirection(v);
            airspeed = v.magnitude;
            float q = 0.5f * Rho * airspeed * airspeed;
            alpha = airspeed > 2f ? Mathf.Atan2(-lv.y, Mathf.Max(0.1f, lv.z)) : 0f;
            float beta = airspeed > 2f ? Mathf.Atan2(lv.x, Mathf.Max(0.1f, lv.z)) : 0f;

            // lift curve with stall
            float aa = Mathf.Abs(alpha);
            float cl;
            stalled = aa > AlphaStall && airspeed > takeoffSpeed * 0.4f;
            if (aa <= AlphaStall) cl = ClAlpha * alpha;
            else cl = Mathf.Sign(alpha) * Mathf.Lerp(ClMax, 0.55f, Mathf.Clamp01((aa - AlphaStall) / 0.35f));
            cl = Mathf.Clamp(cl, -ClMax, ClMax);
            float cd = cd0 + InducedK * cl * cl + (gearDown ? cd0 * 0.25f : 0f) + (stalled ? 0.25f : 0f);
            if (airspeed > 1f)
            {
                Vector3 vd = v / airspeed;
                Vector3 liftDir = Vector3.Cross(vd, transform.right).normalized;
                Body.AddForce(liftDir * (q * wingArea * cl));
                Body.AddForce(-vd * (q * wingArea * cd));
                Body.AddForce(-transform.right * (q * wingArea * 0.6f * beta));
            }
            // propeller thrust falls off gently with airspeed (a biplane still climbs a few m/s at full power)
            float thrust = maxThrust * Throttle * (hasProp ? Mathf.Clamp01(1.25f - 0.5f * airspeed / maxSpeed) : 1f);
            if (crashT <= 0f) Body.AddForce(transform.forward * thrust);

            // rotational dynamics in body axes (angular accelerations, rad/s^2)
            float qn = Mathf.Clamp(q / qRef, 0f, 3f);
            float eff = Mathf.Clamp01(qn);
            float damp = Mathf.Sqrt(Mathf.Max(qn, 0.05f));
            Vector3 w = transform.InverseTransformDirection(Body.angularVelocity);
            float pitchIn = -input.move.y, rollIn = input.move.x, yawIn = input.yaw;
            const float kPitch = 3f, kRoll = 4f, kYaw = 2f;
            // elevator authority grows with dynamic pressure (like the aerodynamic stability it fights), and a
            // g-limiter stops the pull at the airframe's structural limit (8 g jets, 5 g biplanes)
            float effP = Mathf.Min(qn, 2.2f);
            float nNow = q * wingArea * cl / (Body.mass * -Physics.gravity.y);
            float nLimit = hasProp ? 5f : 8f;
            if (pitchIn > 0f) pitchIn *= Mathf.Clamp01((nLimit - nNow) / 1.5f + 0.4f);
            float ax = -pitchIn * pitchRate * Mathf.Deg2Rad * kPitch * effP + alpha * 5f * qn - w.x * kPitch * damp;
            float ay = yawIn * yawRate * Mathf.Deg2Rad * kYaw * eff + beta * 4f * qn - w.y * kYaw * damp;
            float az = -rollIn * rollRate * Mathf.Deg2Rad * kRoll * eff - w.z * kRoll * damp;
            if (crashT <= 0f) Body.AddRelativeTorque(new Vector3(ax, ay, az), ForceMode.Acceleration);

            // landing gear on springs: wheel brakes, nose/tail-wheel steering
            bool gearOut = gearT < 0.3f;
            foreach (var wc in susp.wheels) wc.enabled = gearOut;
            float steerDeg = (rollIn + yawIn) * Mathf.Lerp(40f, 4f, Mathf.Clamp01(airspeed / 25f));
            Quaternion sq = Quaternion.AngleAxis(steerDeg, transform.up);
            Vector3 f = transform.forward, r = transform.right;
            float brake = input.jump || (!Occupied) ? 5f : 0f;
            int onGround = susp.Step(dt, wc => wc.steered
                ? susp.Tyre(wc, sq * f, sq * r, 0f, 0f, 0.9f, 9f, dt)
                : susp.Tyre(wc, f, r, 0f, brake, 0.9f, 9f, dt));
            grounded = onGround > 0;
        }

        protected override void Animate(float dt, float moved)
        {
            float k = 1f - Mathf.Exp(-6f * dt);
            Vector3 inp = Occupied ? new Vector3(-input.move.y, input.move.x, input.yaw) : Vector3.zero;
            foreach (var s in surfaces)
            {
                if (s.t == null || LodHidden) continue;
                float v = s.axis == "pitch" ? inp.x : s.axis == "yaw" ? inp.z : inp.y;
                s.cur = Mathf.Lerp(s.cur, v * s.max * s.sign, k);
                rig.Rotate(s.t, Vector3.up, s.cur);
            }
            if (propSmoke) propSmoke.Rate = Occupied ? 0.15f + 0.85f * Throttle : 0f;
            if (prop && !LodHidden)
            {
                float rps = Occupied ? 4f + 26f * Throttle : 0f;
                propAngle = Mathf.Repeat(propAngle + rps * 360f * dt, 360f);
                rig.Rotate(prop, Vector3.up, propAngle);
                if (blur) rig.Scale(blur, rps > 10f ? 1000f : 1f);
            }
            foreach (var b in burners)
            {
                float s = Occupied && Throttle > 0.85f ? 1000f * (0.6f + 0.4f * (Throttle - 0.85f) / 0.15f) * Random.Range(0.92f, 1.06f) : 1f;
                rig.Scale(b, s);
            }
            if (Occupied && input.action2Down && gears.Count > 0 && (!grounded || !gearDown)) gearDown = !gearDown;
            if (Occupied && input.action1Down && canopy) canopyOpen = !canopyOpen;
            gearT = Mathf.MoveTowards(gearT, gearDown ? 0f : 1f, dt / 3f);
            float ge = Mathf.SmoothStep(0f, 1f, gearT);
            foreach (var g in gears) if (g.t) rig.Rotate(g.t, g.local, g.angle * ge);
            canopyT = Mathf.MoveTowards(canopyT, canopyOpen ? 1f : 0f, dt / 2f);
            float ce = Mathf.SmoothStep(0f, 1f, canopyT);
            if (canopy)
            {
                if (canopyMode == "slide") rig.SlideY(canopy, -canopyTravel * ce);
                else if (canopyMode == "hinge") rig.Rotate(canopy, Vector3.right, canopySign * canopyTravel * ce);
            }
            if (!LodHidden)
            {
                if (gearT < 0.01f) susp.ApplyVisual();
                foreach (var (w, axis) in wheelVis) rig.Rotate(w.bone, axis, w.roll / w.radius * Mathf.Rad2Deg);
            }

            UpdateStores(dt);
            cooldown = Mathf.Max(0f, cooldown - dt);
            if (Occupied && input.fire && cooldown <= 0f && muzzles.Count > 0 && crashT <= 0f)
            {
                var m = muzzles[nextGun];
                bool cannon = Cannon;
                Tracers.Fire(m.muzzle.position, transform.forward, MakeShot(650f + airspeed, 0.09f, 7f, cannon ? 2500f : 900f,
                    cannon ? ImpactKind.Autocannon : ImpactKind.Bullet, cannon ? 0.6f : 0.45f));
                if (++shotCount % 3 == 0) Vfx.Muzzle(m.muzzle.position, transform.forward, 0.12f);
                flashT[nextGun] = 0f;
                nextGun = (nextGun + 1) % muzzles.Count;
                cooldown = fireInterval;
            }
            for (int i = 0; i < muzzles.Count; i++)
            {
                flashT[i] += dt;
                if (muzzles[i].flash) rig.Scale(muzzles[i].flash, flashT[i] < 0.045f ? 1000f : 1f);
            }
        }
    }
}
