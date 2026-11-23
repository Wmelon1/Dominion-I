using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Base for every enterable vehicle. Parked vehicles are kinematic (rock solid, cheap); the driven vehicle and
    /// anything it bumps into are fully simulated rigid bodies. Subclasses implement Simulate (physics, FixedUpdate)
    /// and Animate (rig, Update).
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public abstract class Vehicle : MonoBehaviour
    {
        public string displayName = "Vehicle";
        [Tooltip("Prefab name (Tank_Heavy, Aircraft_Saber...): keys the armour / weapon tables.")]
        public string unitKey = "";
        [Tooltip("Model-space bounds of the visible meshes (filled by the editor setup).")]
        public Bounds localBounds = new Bounds(Vector3.up, new Vector3(3, 2, 6));

        [System.NonSerialized] public ControlInput input;
        public bool Occupied { get; private set; }
        public Rigidbody Body { get; private set; }
        protected RigBones rig;
        protected Vector3 lastPos;
        protected float lastYaw;
        float parkT;
        /// <summary>Signed forward ground speed (m/s), measured from real motion.</summary>
        public float ForwardSpeed { get; protected set; }
        public float YawRate { get; protected set; }

        // ------------------------------------------------------------------ War mode
        [System.NonSerialized] public Team team;
        [System.NonSerialized] public Health health;       // null in Sandbox (invulnerable)
        [System.NonSerialized] public bool PlayerDriven;    // the player is at the controls (AI stands down)
        /// <summary>Set by UnitLOD when the player can't see this unit: cosmetic rig work (tracks, wheels, dust) is skipped.
        /// Physics, AI, aiming and weapons are never affected.</summary>
        [System.NonSerialized] public bool LodHidden;
        public bool Destroyed { get; private set; }
        public Vector3 Velocity => Body == null || Body.isKinematic ? Vector3.zero : Body.linearVelocity;
        protected WeaponStats weapon;
        Emitter wreckFire;
        float wreckT, crushT;

        /// <summary>Main weapon muzzle and barrel direction (false for unarmed vehicles).</summary>
        public virtual bool GetAim(out Vector3 origin, out Vector3 dir)
        {
            origin = transform.position;
            dir = transform.forward;
            return false;
        }
        /// <summary>Muzzle velocity of the main weapon (m/s), for target leading.</summary>
        public virtual float ProjectileSpeed => 400f;
        /// <summary>Fraction of gravity acting on the rounds (0.15 = flat tracers, 1 = artillery).</summary>
        public virtual float ProjectileGravity => 0.15f;
        public virtual bool Reloaded => true;
        /// <summary>Open / close the rear door, ramp or tailgate (troop transports; AI riders use it).</summary>
        public virtual void SetDoor(bool open) { }

        /// <summary>A round from the main weapon carrying this vehicle's damage and team.</summary>
        protected Shot MakeShot(float speed, float width, float length, float impulse, ImpactKind kind, float scale)
        {
            var s = Shot.Visual(speed, width, length, impulse, kind, scale);
            weapon.Apply(ref s, health, transform);
            s.model = Projectiles.For(unitKey);
            return s;
        }

        public abstract string ControlsHelp { get; }
        public virtual string Status => $"{Mathf.Abs(ForwardSpeed) * 3.6f:0} km/h";
        public virtual bool CanExit => Body == null || Body.linearVelocity.magnitude < 3f;
        public virtual float CameraDistance => Mathf.Clamp(localBounds.size.magnitude * 1.05f, 7f, 40f);
        public virtual Vector3 CameraPivot => transform.TransformPoint(localBounds.center + Vector3.up * localBounds.extents.y * 0.9f);
        /// <summary>Height of the vehicle origin above the ground when parked.</summary>
        public virtual float RestHeight => 0f;
        /// <summary>Centre of mass in vehicle space (low, so the suspension pitches and rolls the body believably).</summary>
        protected virtual Vector3 CenterOfMass =>
            new Vector3(localBounds.center.x, localBounds.min.y + localBounds.size.y * 0.33f, localBounds.center.z);

        /// <summary>Where the soldier steps out (left side, on the ground).</summary>
        public Vector3 ExitPoint
        {
            get
            {
                var p = transform.TransformPoint(new Vector3(localBounds.min.x - 1.4f, 0f, localBounds.center.z));
                p.y = 0.05f;
                return p;
            }
        }

        [Header("Effects")]
        public float muzzleScale = 0.3f;
        public ImpactKind impactKind = ImpactKind.Bullet;
        public float impactScale = 0.5f;
        protected Emitter dustL, dustR, exhaust;

        /// <summary>Dust trails behind the running gear and a diesel exhaust (wheeled / tracked vehicles).</summary>
        protected void SetupGroundEffects(Vector3 exhaustLocal, Vector3 exhaustDir)
        {
            float x = localBounds.extents.x * 0.72f;
            float z = localBounds.min.z + 0.9f;
            dustL = Vfx.Attach(Vfx.EmitterKind.DustTrail, transform, new Vector3(localBounds.center.x - x, 0.3f, z), Quaternion.identity);
            dustR = Vfx.Attach(Vfx.EmitterKind.DustTrail, transform, new Vector3(localBounds.center.x + x, 0.3f, z), Quaternion.identity);
            exhaust = Vfx.Attach(Vfx.EmitterKind.Exhaust, transform, exhaustLocal, Quaternion.LookRotation(exhaustDir));
        }

        /// <summary>Drive the dust / exhaust from real ground speed and the driver's throttle.</summary>
        protected void UpdateGroundEffects(float throttle)
        {
            float v = Mathf.Abs(ForwardSpeed);
            float turnDust = Mathf.Clamp01(Mathf.Abs(YawRate) / 70f) * 0.4f;
            Vector3 pp = transform.position;
            bool onGround = pp.y < WorldGround.Height(pp.x, pp.z) + RestHeight + 1.2f;
            float dust = onGround && !LodHidden ? Mathf.Clamp01(v / 14f) + turnDust : 0f;
            if (dustL) dustL.Rate = dust;
            if (dustR) dustR.Rate = dust;
            if (exhaust) exhaust.Rate = Occupied && !LodHidden ? 0.12f + 0.88f * Mathf.Clamp01(Mathf.Abs(throttle)) * (v < 2f ? 1f : 0.6f) : 0f;
        }

        protected virtual void Awake()
        {
            Body = GetComponent<Rigidbody>();
            Body.isKinematic = true;
            Body.interpolation = RigidbodyInterpolation.Interpolate;
            Body.centerOfMass = CenterOfMass;
            rig = new RigBones(transform);
            lastPos = transform.position;
            lastYaw = transform.eulerAngles.y;
            weapon = Armory.Weapon(unitKey);
        }

        public virtual void OnEnter()
        {
            if (Destroyed) return;
            Occupied = true;
            Wake();
        }

        public virtual void OnExit()
        {
            Occupied = false;
            input = default;
        }

        /// <summary>Switch from parked (kinematic) to simulated.</summary>
        public void Wake()
        {
            parkT = 0f;
            if (!Body.isKinematic) return;
            Body.isKinematic = false;
            Body.linearVelocity = Vector3.zero;
            Body.angularVelocity = Vector3.zero;
        }

        /// <summary>Distance from a world point to this vehicle's bounding box (for the "Press E" prompt).</summary>
        public float DistanceTo(Vector3 worldPoint)
        {
            Vector3 lp = transform.InverseTransformPoint(worldPoint);
            return Vector3.Distance(transform.TransformPoint(localBounds.ClosestPoint(lp)), worldPoint);
        }

        float simAcc;

        protected virtual void Update()
        {
            long perfT0 = Perf.Now;
            UpdateTimed();
            Perf.Add(Perf.VehicleRig, perfT0);
        }

        void UpdateTimed()
        {
            // simulation LOD: far, unseen ground vehicles run their rig / gun bookkeeping every Nth frame
            float dt0 = Time.deltaTime;
            if (health != null && !PlayerDriven && !health.SimTick(ref simAcc, out dt0)) return;
            float dt = Mathf.Max(dt0, 1e-4f);
            Vector3 d = transform.position - lastPos;
            float moved = Vector3.Dot(d, transform.forward);
            ForwardSpeed = Mathf.Lerp(ForwardSpeed, moved / dt, 1f - Mathf.Exp(-12f * dt));
            YawRate = Mathf.DeltaAngle(lastYaw, transform.eulerAngles.y) / dt;
            lastPos = transform.position;
            lastYaw = transform.eulerAngles.y;
            if (Occupied && input.resetDown) ResetUpright();
            Animate(dt, moved);
            if (Destroyed && wreckFire)
            {
                wreckT += dt;
                if (wreckT > 30f && wreckT - dt <= 30f) wreckFire.Rate = 0.35f;      // dies down to a smoulder
                if (wreckT > 120f) { wreckFire.Release(10f); wreckFire = null; }
            }
        }

        // ------------------------------------------------------------------ destruction
        /// <summary>Health reached zero: blow up and leave a burning, blackened wreck.</summary>
        public void Die(DamageInfo d)
        {
            if (Destroyed) return;
            Destroyed = true;
            if (Occupied) OnExit();
            PlayerDriven = false;
            OnDestroyed(d);
        }

        protected virtual void OnDestroyed(DamageInfo d)
        {
            Vector3 c = transform.TransformPoint(localBounds.center);
            float s = Mathf.Clamp(localBounds.size.magnitude / 5f, 1.2f, 2.6f);
            Vfx.Explosion(c, s, true);
            Health.Splash(c, 4f + 2f * s, 160f, DamageType.HE, Team.None, health, health);
            if (dustL) dustL.Rate = 0f;
            if (dustR) dustR.Rate = 0f;
            if (exhaust) exhaust.Rate = 0f;
            Wake();
            // the blast heaves the hull up and twists it
            Body.AddForce(Vector3.up * Random.Range(2.5f, 4.5f), ForceMode.VelocityChange);
            Body.AddTorque(Random.onUnitSphere * 0.5f, ForceMode.VelocityChange);
            Burn(localBounds.center + Vector3.up * localBounds.extents.y * 0.5f);
        }

        protected void Burn(Vector3 local)
        {
            TeamPaint.Burn(gameObject);
            if (wreckFire == null) wreckFire = Vfx.Attach(Vfx.EmitterKind.Burning, transform, local, Quaternion.identity);
            if (wreckFire) wreckFire.Rate = 1f;
            wreckT = 0f;
        }

        /// <summary>Running over soldiers (War mode): crush anyone of the other side the hull touches at speed.</summary>
        protected void CrushCheck(float dt, float minSpeed)
        {
            if (health == null || Destroyed) return;
            crushT -= dt;
            if (crushT > 0f) return;
            crushT = 0.1f;
            float v = Velocity.magnitude;
            bool driving = Mathf.Abs(input.move.y) > 0.1f || Mathf.Abs(input.move.x) > 0.3f;
            if (v < minSpeed && !(driving && !(this is AircraftVehicle))) return;
            Vector3 c = transform.TransformPoint(localBounds.center);
            var cols = Physics.OverlapBox(c, localBounds.extents + new Vector3(0.35f, 0f, 0.6f), transform.rotation, ~0, QueryTriggerInteraction.Ignore);
            foreach (var col in cols)
            {
                if (!(this is AircraftVehicle))
                {
                    var car = col.GetComponentInParent<CarProp>();
                    if (car != null) { car.Crush(transform.position); continue; }
                }
                if (v < minSpeed) continue;
                if (!(col is CharacterController)) continue;
                var h = Health.Of(col);
                if (h == null || !Health.Enemies(h.team, team)) continue;
                h.TakeDamage(new DamageInfo { amount = 60f * v, type = DamageType.Crush, team = team, point = col.transform.position, dir = Velocity, attacker = health });
            }
        }

        /// <summary>R: lift the vehicle and set it back on its wheels (after a rollover or crash).</summary>
        public virtual void ResetUpright()
        {
            Vector3 p = Body.position;
            p.y = RestHeight + 0.6f;
            Body.position = p;
            Body.rotation = Quaternion.Euler(0f, transform.eulerAngles.y, 0f);
            Body.linearVelocity = Vector3.zero;
            Body.angularVelocity = Vector3.zero;
        }

        /// <summary>Per-frame rig animation (wheels, tracks, turrets, flashes...). moved = forward metres this frame.</summary>
        protected abstract void Animate(float dt, float moved);

        void FixedUpdate()
        {
            long perfT0 = Perf.Now;
            FixedUpdateTimed();
            Perf.Add(Perf.Vehicles, perfT0);
        }

        // ------------------------------------------------------------------ far physics proxy
        // A ground vehicle nobody can see, far from the camera, leaves the rigid-body simulation: it drives kinematically
        // along its crew's inputs (its real top speed and turn rate), hugging the ground. The moment it comes into view or
        // the camera gets near, it is handed back to the full suspension physics with its current speed.
        protected virtual bool CanProxy => false;
        protected virtual float ProxyTopSpeed => 15f;
        protected virtual float ProxyTurnRate => 30f;
        bool proxy;
        float proxySpeed, proxyGroundT, proxyGroundY;
        Vector3 proxyUp = Vector3.up;
        public bool Proxied => proxy;

        bool WantProxy() => CanProxy && health != null && Occupied && !PlayerDriven && !Destroyed && LodHidden && health.SimStride >= 2 &&
                            transform.up.y > 0.75f;

        void ProxyStep(float dt)
        {
            if (!proxy)
            {
                proxy = true;
                Perf.Proxied++;
                proxySpeed = Vector3.Dot(Body.linearVelocity, transform.forward);
                proxyGroundY = transform.position.y - RestHeight;
                proxyUp = transform.up;
            }
            if (!Body.isKinematic) Body.isKinematic = true;
            float target = input.jump ? 0f : Mathf.Clamp(input.move.y, -0.5f, 1f) * ProxyTopSpeed * 0.85f;
            proxySpeed = Mathf.MoveTowards(proxySpeed, target, (Mathf.Abs(target) > Mathf.Abs(proxySpeed) ? 2.5f : 5f) * dt);
            float turn = input.move.x * ProxyTurnRate * (this is TrackedVehicle ? 1f : Mathf.Clamp01(Mathf.Abs(proxySpeed) / 4f)) * (proxySpeed < -0.2f ? -1f : 1f);
            Vector3 fwd = Vector3.ProjectOnPlane(transform.forward, Vector3.up).normalized;
            float yaw = Mathf.Atan2(fwd.x, fwd.z) * Mathf.Rad2Deg + turn * dt;
            Vector3 pos = Body.position + fwd * (proxySpeed * dt);
            proxyGroundT -= dt;
            if (proxyGroundT <= 0f)
            {
                proxyGroundT = 0.2f;
                if (AIUtil.Cast(pos + Vector3.up * 5f, Vector3.down, 14f, transform, out RaycastHit h) && Health.Of(h.collider) == null)
                {
                    proxyGroundY = h.point.y;
                    proxyUp = h.normal.y > 0.6f ? h.normal : Vector3.up;
                }
                else proxyGroundY = WorldGround.Height(pos.x, pos.z);
            }
            pos.y = Mathf.MoveTowards(pos.y, proxyGroundY + RestHeight, 3f * dt);
            Quaternion up = Quaternion.Slerp(Quaternion.FromToRotation(Vector3.up, transform.up), Quaternion.FromToRotation(Vector3.up, proxyUp), 4f * dt);
            Body.MovePosition(pos);
            Body.MoveRotation(up * Quaternion.Euler(0f, yaw, 0f));
        }

        void ExitProxy()
        {
            if (!proxy) return;
            proxy = false;
            Perf.Proxied--;
            Body.isKinematic = false;
            Body.linearVelocity = transform.forward * proxySpeed;
            Body.angularVelocity = Vector3.zero;
        }

        void FixedUpdateTimed()
        {
            if (WantProxy()) { ProxyStep(Time.fixedDeltaTime); return; }
            if (proxy) ExitProxy();
            if (Body.isKinematic) return;
            Simulate(Time.fixedDeltaTime);
            CrushCheck(Time.fixedDeltaTime, this is MechVehicle ? 1.2f : 3.5f);
            if (Occupied) return;
            bool still = Body.linearVelocity.sqrMagnitude < 0.01f && Body.angularVelocity.sqrMagnitude < 0.004f;
            parkT = still ? parkT + Time.fixedDeltaTime : 0f;
            if (parkT > 1.5f) Body.isKinematic = true;
        }

        /// <summary>Physics step. input is all-zero while nobody is driving (vehicle brakes to a stop).</summary>
        protected abstract void Simulate(float dt);

        void OnCollisionEnter(Collision c)
        {
            // a simulated vehicle shoves a parked one instead of bouncing off an immovable wall
            if (Body.isKinematic) return;
            var other = c.rigidbody ? c.rigidbody.GetComponent<Vehicle>() : null;
            if (other && other.Body.isKinematic) other.Wake();
            OnImpact(c);
        }

        protected virtual void OnImpact(Collision c) { }

        // -------------------------------------------------------------- shared turret helper
        protected class Turret
        {
            public Transform turret, gun;
            public Vector3 yawAxis, pitchAxis;
            public float yaw, pitch, minPitch, maxPitch, yawSpeed, pitchSpeed;
            public float restYaw, restPitch;
            public Transform aimRef;

            public static Turret Create(RigBones rig, Transform vehicle, string turretBone, string gunBone, string muzzleBone,
                float minPitch, float maxPitch, float yawSpeed, float pitchSpeed)
            {
                var t = new Turret { turret = rig[turretBone], gun = rig[gunBone], aimRef = rig[muzzleBone] ?? rig[gunBone] };
                if (t.turret == null || t.gun == null) return null;
                t.yawAxis = RigBones.LocalAxis(t.turret, vehicle.up);
                t.pitchAxis = RigBones.LocalAxis(t.gun, -vehicle.right);   // + = elevate (Unity is left-handed)
                t.minPitch = minPitch;
                t.maxPitch = maxPitch;
                t.yawSpeed = yawSpeed;
                t.pitchSpeed = pitchSpeed;
                // rest direction along the barrel itself (barrel bone -> muzzle), not pivot -> muzzle: on side-by-side
                // twin barrels (the flak tank) the pivot line is ~13 deg off the real line of fire
                Transform barrelRef = t.aimRef.parent != null && t.aimRef.parent != t.gun ? t.aimRef.parent : t.gun;
                Vector3 bd = vehicle.InverseTransformDirection(t.aimRef.position - barrelRef.position);
                if (bd.sqrMagnitude < 0.01f) bd = vehicle.InverseTransformDirection(t.aimRef.position - t.gun.position);
                if (bd.sqrMagnitude < 1e-4f) bd = Vector3.forward;
                t.restYaw = Mathf.Atan2(bd.x, bd.z) * Mathf.Rad2Deg;
                t.restPitch = Mathf.Atan2(bd.y, new Vector2(bd.x, bd.z).magnitude) * Mathf.Rad2Deg;
                return t;
            }

            /// <param name="ballisticSpeed">if > 0, elevate for a low-arc ballistic shot at this muzzle velocity (artillery)</param>
            public void AimAt(RigBones rig, Transform vehicle, Vector3 target, float dt, float ballisticSpeed = 0f)
            {
                Vector3 d = vehicle.InverseTransformPoint(target) - vehicle.InverseTransformPoint(gun.position);
                float wantYaw = Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg - restYaw;
                float elev = Mathf.Atan2(d.y, new Vector2(d.x, d.z).magnitude) * Mathf.Rad2Deg;
                if (ballisticSpeed > 0f)
                {
                    // the solution is relative to the horizon: build the world launch direction, then express it in hull space
                    Vector3 flat = target - gun.position;
                    flat.y = 0f;
                    float e = BallisticElevation(gun.position, target, ballisticSpeed) * Mathf.Deg2Rad;
                    Vector3 ll = vehicle.InverseTransformDirection(flat.normalized * Mathf.Cos(e) + Vector3.up * Mathf.Sin(e));
                    elev = Mathf.Atan2(ll.y, new Vector2(ll.x, ll.z).magnitude) * Mathf.Rad2Deg;
                }
                float wantPitch = elev - restPitch;
                wantPitch = Mathf.Clamp(wantPitch, minPitch, maxPitch);
                yaw += Mathf.Clamp(Mathf.DeltaAngle(yaw, wantYaw), -yawSpeed * dt, yawSpeed * dt);
                pitch = Mathf.MoveTowards(pitch, wantPitch, pitchSpeed * dt);
                rig.Rotate(turret, yawAxis, yaw);
                rig.Rotate(gun, pitchAxis, pitch);
            }
        }

        /// <summary>Low-arc elevation (degrees above horizontal) that lands a shell of speed v on the target; 45 deg if out of range.</summary>
        public static float BallisticElevation(Vector3 from, Vector3 to, float v)
        {
            Vector3 d = to - from;
            float x = new Vector2(d.x, d.z).magnitude, y = d.y, g = -Physics.gravity.y;
            float v2 = v * v;
            float disc = v2 * v2 - g * (g * x * x + 2f * y * v2);
            if (disc < 0f || x < 1f) return 45f;
            return Mathf.Atan((v2 - Mathf.Sqrt(disc)) / (g * x)) * Mathf.Rad2Deg;
        }

        // -------------------------------------------------------------- shared gun helper
        protected class Gun
        {
            public Transform barrel, muzzle, flash;
            public float recoilDist, recoil, flashT = 99f;
            public float muzzleScale = 0.3f, impactScale = 0.5f;
            public ImpactKind impact = ImpactKind.Bullet;

            public Vector3 Direction => muzzle && barrel ? (muzzle.position - barrel.position).normalized : (muzzle ? muzzle.up : Vector3.forward);

            public void Shoot(Shot s)
            {
                recoil = 1f;
                flashT = 0f;
                if (!muzzle) return;
                Tracers.Fire(muzzle.position, Direction, s);
                Vfx.Muzzle(muzzle.position, Direction, muzzleScale);
            }

            public void Animate(RigBones rig, float dt)
            {
                recoil = Mathf.MoveTowards(recoil, 0f, dt * 2.2f);
                if (barrel && recoilDist > 0f) rig.SlideY(barrel, -recoilDist * recoil * recoil);
                flashT += dt;
                if (flash) rig.Scale(flash, flashT < 0.06f ? 1000f * Random.Range(0.8f, 1.15f) : 1f);
            }
        }
    }
}
