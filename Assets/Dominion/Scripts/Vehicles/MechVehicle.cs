using System.Collections;
using MechKit;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Pilotable MechKit mech.
    /// W/S walk, A/D turn, Shift run, RMB brace + aim, LMB main weapon, F melee strike, G stomp,
    /// Q missile pods (Thunderhead). Halberd: hold Space to fly toward the mouse in a head-first dive. Aegis and
    /// Thunderhead: hold Space to dash along the ground toward the mouse on back thrusters (Shift boosts), at about the
    /// Halberd's flight speed, burning the same 14 s charge that recharges on the ground.
    /// Melee strike per loadout: Halberd arm-blade Slash, Aegis Shield Bash, Thunderhead Punch. Strikes work while
    /// walking / running (upper-body animation layer); standing still they use the full-body version with a step-in.
    /// </summary>
    [RequireComponent(typeof(MechController))]
    public class MechVehicle : Vehicle
    {
        public float walkSpeed = 2.5f;
        public float runSpeed = 6.1f;
        public float turnRate = 55f;
        public float fireInterval = 0.4f;
        public float tracerWidth = 0.18f;
        public float shotImpulse = 12000f;
        public float podInterval = 0.35f;
        public bool hasJets;
        public bool hasPods;

        [Header("Melee")]
        public string strikeClip = "Punch";
        public float strikeLength = 1f;
        public float strikeHitAt = 0.42f;
        public float strikeReach = 6f;
        public float strikeRadius = 3.5f;
        public float strikeDv = 6f;
        public bool strikeLunge;
        public float stompLength = 1.333f;
        public float stompHitAt = 0.733f;
        public float stompRadius = 16f;

        [Header("Jet flight")]
        public float flySpeed = 26f;
        public float boostSpeed = 46f;
        public float flyAccel = 28f;
        public float jetFuelMax = 14f;

        [Header("Thruster dash (mechs without jets)")]
        public float dashSpeed = 26f;
        public float dashBoost = 40f;
        public float dashAccel = 20f;
        bool dashing, dashAnim, hasDashState;
        float dashDustT;
        int dashFoot;
        readonly System.Collections.Generic.List<Emitter> thrusters = new System.Collections.Generic.List<Emitter>();
        /// <summary>Aegis and Thunderhead: Space dashes along the ground instead of flying.</summary>
        public bool CanDash => !hasJets;
        public bool Dashing => dashing;
        /// <summary>Dashes started by any mech (auto-test stats).</summary>
        public static int Dashes;

        MechController mech;
        Animator anim;
        int upperLayer = -1;
        float speed, cooldown, podCooldown, aimHold, jetFuel, heading, tilt;
        bool flying, flyAnim, grounded = true;
        // melee state
        string melee;            // clip name while a strike / stomp is playing
        bool meleeUpper, meleeHit, meleeStomp;
        float meleeT, meleeLen, meleeHitAt, upperW;

        public override float CameraDistance => 19f;
        public override Vector3 CameraPivot => transform.TransformPoint(0f, 4.7f, 0f) + Vector3.up * 3f;
        public override bool CanExit => grounded && !flying && Body.linearVelocity.magnitude < 3f;
        public bool Flying => flying;
        public float Tilt => tilt;
        public bool Attacking => melee != null;
        public bool Grounded => grounded;
        public float JetFuel => jetFuel;
        public MechController Controller => mech;
        /// <summary>Unit the missile pods home on (set by the AI); otherwise they fly to the aim point.</summary>
        [System.NonSerialized] public Health lockTarget;
        public override float ProjectileSpeed => fireInterval < 0.2f ? 600f : 420f;
        public override bool Reloaded => cooldown <= 0f;

        public override bool GetAim(out Vector3 origin, out Vector3 dir)
        {
            var m = mech ? mech.GetMuzzle(0) : null;
            origin = m ? m.position : transform.position + Vector3.up * 5f;
            dir = m ? m.up : transform.forward;
            return m != null;
        }

        string StrikeName => strikeClip == "Slash" ? "arm-blade slash" : strikeClip == "ShieldBash" ? "shield bash" : "punch";

        public override string ControlsHelp =>
            "W/S  walk     A/D  turn     Shift  run\nRMB  brace + aim     LMB  fire" + (hasPods ? "     Q  missile pods" : "") +
            $"\nF  {StrikeName} (also on the move)     G  stomp" +
            (hasJets ? "\nSpace (hold)  fly toward the mouse, Shift boost" : "\nSpace (hold)  thruster dash toward the mouse, Shift boost") +
            "\nR  reset upright     E  exit";

        public override string Status =>
            (flying || !grounded ? $"{Body.linearVelocity.magnitude * 3.6f:0} km/h" : base.Status) +
            (hasJets ? $"   jets {jetFuel / jetFuelMax * 100f:0}%" + (flying ? $"   FLYING  alt {transform.position.y - WorldGround.Height(transform.position.x, transform.position.z):0} m" : "")
                     : $"   dash {jetFuel / jetFuelMax * 100f:0}%" + (dashing ? "   DASHING" : ""));

        protected override void Awake()
        {
            base.Awake();
            mech = GetComponent<MechController>();
            anim = GetComponent<Animator>();
            if (anim) upperLayer = anim.GetLayerIndex("UpperBody");
            mech.Fired += OnFired;
            jetFuel = jetFuelMax;
            heading = transform.eulerAngles.y;
            if (hasJets)
                foreach (var jn in new[] { "Jet_L", "Jet_R" })
                    if (rig[jn]) jets.Add(Vfx.Attach(Vfx.EmitterKind.JetSmoke, rig[jn], Vector3.zero, Quaternion.Euler(-90f, 0f, 0f)));
            foreach (var fn in new[] { "LeftFoot", "RightFoot" })
                if (rig[fn]) feet.Add((rig[fn], transform.InverseTransformPoint(rig[fn].position).y, false));
            if (CanDash)
            {
                // twin back thrusters, angled down and back
                foreach (float sx in new[] { -1f, 1f })
                    thrusters.Add(Vfx.Attach(Vfx.EmitterKind.JetSmoke, transform, new Vector3(sx * 0.8f, 5.3f, -1.35f),
                        Quaternion.LookRotation(new Vector3(sx * 0.15f, -0.6f, -1f))));
                hasDashState = anim && anim.HasState(0, Animator.StringToHash("Dash"));
            }
        }

        readonly System.Collections.Generic.List<Emitter> jets = new System.Collections.Generic.List<Emitter>();
        readonly System.Collections.Generic.List<(Transform foot, float restH, bool up)> feet =
            new System.Collections.Generic.List<(Transform, float, bool)>();
        float fallSpeed;
        int shotCount;

        /// <summary>Dust kicked up each time a foot plants (bigger when running).</summary>
        void Footsteps()
        {
            bool moving = grounded && !flying && Mathf.Abs(ForwardSpeed) > 0.6f;
            for (int i = 0; i < feet.Count; i++)
            {
                var f = feet[i];
                float h = transform.InverseTransformPoint(f.foot.position).y - f.restH;
                if (!f.up && h > 0.3f) f.up = true;
                else if (f.up && h < 0.08f)
                {
                    f.up = false;
                    if (moving)
                    {
                        Vector3 p = f.foot.position;
                        p.y = WorldGround.Height(p.x, p.z) + 0.05f;
                        Vfx.DustPuff(p, Mathf.Abs(ForwardSpeed) > walkSpeed + 0.5f ? 1.5f : 1f);
                    }
                }
                feet[i] = f;
            }
        }

        void OnFired(Transform muzzle, int index)
        {
            if (index == 0)
            {
                float extra = flying ? Body.linearVelocity.magnitude : 0f;
                // fire-control computer: rounds go to the aim point when the arm is roughly on it
                Vector3 dir = muzzle.up;
                Vector3 want = (input.aimPoint - muzzle.position).normalized;
                if (Occupied && input.aimPoint != Vector3.zero && Vector3.Angle(dir, want) < 9f) dir = want;
                Tracers.Fire(muzzle.position, dir, MakeShot(ProjectileSpeed + extra, tracerWidth, tracerWidth * 50f, shotImpulse, impactKind, impactScale));
                if (fireInterval >= 0.2f || ++shotCount % 2 == 0) Vfx.Muzzle(muzzle.position, dir, muzzleScale);
            }
            else
            {
                Health lockOn = lockTarget && lockTarget.Alive ? lockTarget : null;
                Missile.Launch(muzzle.position, muzzle.up + Vector3.up * 0.15f, input.aimPoint, transform,
                    health ? Armory.MechMissile : Armory.None, health, lockOn, 1f);
            }
        }

        public override void OnEnter()
        {
            base.OnEnter();
            heading = transform.eulerAngles.y;
        }

        public override void OnExit()
        {
            base.OnExit();
            mech.SetAiming(false);
            mech.ClearAimTarget();
            mech.SetJets(false);
            flying = false;
            dashing = false;
        }

        /// <summary>Place the mech upright at a point facing yaw (used by the auto-test).</summary>
        public void Teleport(Vector3 pos, float yaw)
        {
            flying = false;
            tilt = 0f;
            heading = yaw;
            speed = 0f;
            Body.linearVelocity = Vector3.zero;
            Body.position = pos;
            Body.rotation = Quaternion.Euler(0f, yaw, 0f);
            transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
        }

        public override void ResetUpright()
        {
            flying = false;
            tilt = 0f;
            base.ResetUpright();
            Body.rotation = Quaternion.Euler(0f, heading, 0f);
        }

        // ------------------------------------------------------------------ physics
        protected override void Simulate(float dt)
        {
            if (!grounded) fallSpeed = Mathf.Max(fallSpeed, -Body.linearVelocity.y);
            grounded = Physics.Raycast(transform.position + Vector3.up * 0.6f, Vector3.down, 1.0f, ~0, QueryTriggerInteraction.Ignore)
                       && tilt < 30f;
            if (hasJets && Occupied && input.jump && jetFuel > 0.2f && melee == null)
            {
                if (!flying && grounded) Body.linearVelocity += Vector3.up * 9f;   // jump-jet launch
                flying = true;
            }
            else flying = false;
            // thruster dash: on the ground (or skimming over a bump), not during a planted strike or stomp
            bool wantDash = CanDash && Occupied && input.jump && jetFuel > 0.2f && (melee == null || meleeUpper) &&
                            (grounded || (dashing && transform.position.y - WorldGround.Height(transform.position.x, transform.position.z) < 2.5f));
            if (wantDash && !dashing) Dashes++;
            dashing = wantDash;
            jetFuel = flying || dashing ? Mathf.Max(0f, jetFuel - dt) : Mathf.Min(jetFuelMax, jetFuel + dt * (grounded ? 1.6f : 0.3f));

            if (flying)
            {
                Body.useGravity = false;
                Vector3 dir = Quaternion.Euler(input.lookPitch, input.lookYaw, 0f) * Vector3.forward;
                float spd = input.sprint ? boostSpeed : flySpeed;
                if (input.move.y < -0.1f) spd *= 0.35f;
                Body.linearVelocity = Vector3.MoveTowards(Body.linearVelocity, dir * spd, flyAccel * dt);
                heading = Mathf.MoveTowardsAngle(heading, input.lookYaw, 140f * dt);
                float elevation = -input.lookPitch;
                float speedK = Mathf.Clamp01(Body.linearVelocity.magnitude / 12f);
                tilt = Mathf.MoveTowards(tilt, Mathf.Clamp(90f - elevation, 0f, 170f) * speedK, 110f * dt);
                Body.MoveRotation(Quaternion.Euler(0f, heading, 0f) * Quaternion.Euler(tilt, 0f, 0f));
                return;
            }

            Body.useGravity = true;
            float lean = dashing ? Mathf.Lerp(4f, 11f, Mathf.Clamp01(speed / dashBoost)) : 0f;     // lean into the dash
            tilt = Mathf.MoveTowards(tilt, lean, (grounded ? 240f : 90f) * dt);
            bool aiming = mech.IsAiming;
            bool planted = melee != null && !meleeUpper;               // full-body strike or stomp: feet planted
            float max = input.sprint ? runSpeed : walkSpeed;
            float target = aiming || !grounded || planted ? 0f : input.move.y * (input.move.y >= 0f ? max : walkSpeed * 0.7f);
            if (melee != null && strikeLunge && !meleeStomp)
            {
                float k = meleeT / meleeLen;                          // shield bash: drive forward into the hit
                if (k > 0.22f && k < 0.42f) target = Mathf.Max(target, 7f);
            }
            if (dashing)
            {
                // full thrust toward where the mouse points; S brakes; turns widen with speed
                float want = input.sprint ? dashBoost : dashSpeed;
                if (input.move.y < -0.1f) want *= 0.35f;
                speed = Mathf.MoveTowards(speed, want, dashAccel * dt);
                heading = Mathf.MoveTowardsAngle(heading, input.lookYaw, Mathf.Lerp(110f, 50f, Mathf.Clamp01(speed / dashBoost)) * dt);
            }
            else
            {
                // after a dash the mech skids down to walking pace quickly
                float decel = Mathf.Abs(target) > Mathf.Abs(speed) ? 3f : Mathf.Abs(speed) > runSpeed + 0.5f ? 16f : 6f;
                speed = Mathf.MoveTowards(speed, target, decel * dt);
                heading += input.move.x * turnRate * (aiming ? 0.6f : planted ? 0.3f : 1f) * dt;
            }
            Body.MoveRotation(Quaternion.Euler(0f, heading, 0f) * Quaternion.Euler(tilt, 0f, 0f));
            Vector3 v = Body.linearVelocity;
            if (grounded)
            {
                Vector3 fwd = Quaternion.Euler(0f, heading, 0f) * Vector3.forward;
                Body.linearVelocity = fwd * speed + Vector3.up * v.y;
            }
            else Body.linearVelocity = new Vector3(v.x * (1f - 0.4f * dt), v.y, v.z * (1f - 0.4f * dt));
        }

        // ------------------------------------------------------------------ animation, weapons, melee
        protected override void Animate(float dt, float moved)
        {
            if (Destroyed) return;
            cooldown = Mathf.Max(0f, cooldown - dt);
            podCooldown = Mathf.Max(0f, podCooldown - dt);
            mech.SetJets(flying);
            foreach (var j in jets) if (j) j.Rate = flying ? (input.sprint ? 1f : 0.65f) : 0f;
            foreach (var j in thrusters) if (j) j.Rate = dashing ? (input.sprint ? 1f : 0.7f) : 0f;
            Footsteps();
            DashEffects(dt);
            bool airborne = flying || !grounded;
            if (airborne != flyAnim)
            {
                if (!airborne)
                {
                    // touchdown: dust ring, and a cratering shockwave on a hard landing
                    Vector3 p = transform.position;
                    p.y = WorldGround.Height(p.x, p.z) + 0.05f;
                    if (fallSpeed > 13f)
                    {
                        Vfx.Stomp(p, 12f);
                        Effects.Blast(p, 12f, 6f, 0.8f, transform);
                        if (health) Health.Splash(p, 12f, 300f, DamageType.HE, team, health, health);
                    }
                    else if (fallSpeed > 4f) Vfx.DustPuff(p, 3f);
                    fallSpeed = 0f;
                }
                flyAnim = airborne;
                if (airborne)
                {
                    if (mech.IsAiming) mech.SetAiming(false);
                    EndMelee();
                }
                mech.PlayState(airborne ? "Fly" : "Idle", 0.35f);
            }
            UpdateMelee(dt);
            if (upperLayer >= 0) anim.SetLayerWeight(upperLayer, upperW);
            if (!Occupied)
            {
                if (!flyAnim && melee == null) mech.SetLocomotion(0f);
                return;
            }
            if (flyAnim)
            {
                mech.ClearAimTarget();
                if (input.fire && cooldown <= 0f)
                {
                    mech.Fire(0);
                    cooldown = fireInterval;
                }
                return;
            }
            // start a strike (F) or stomp (G)
            if (melee == null && input.action1Down) StartMelee(false);
            else if (melee == null && input.action2Down) StartMelee(true);
            if (melee != null && !meleeUpper) return;                   // planted full-body move owns the animator

            bool wantsFire = input.fire || (hasPods && input.special);
            if ((input.aim || wantsFire) && melee == null && !dashing) aimHold = 1.2f;
            aimHold = Mathf.Max(0f, aimHold - dt);
            bool aim = aimHold > 0f && melee == null && !dashing;
            if (aim != mech.IsAiming) mech.SetAiming(aim);
            if (aim) mech.AimAt(input.aimPoint);
            else mech.ClearAimTarget();
            if (dashing && hasDashState && melee == null)
            {
                if (!dashAnim) { anim.speed = 1f; mech.PlayState("Dash", 0.2f); dashAnim = true; }
            }
            else
            {
                if (dashAnim) { dashAnim = false; mech.PlayState("Idle", 0.25f); }
                if (!aim) mech.SetLocomotion(Mathf.Abs(ForwardSpeed));
            }
            if (aim && input.fire && cooldown <= 0f)
            {
                mech.Fire(0);
                cooldown = fireInterval;
            }
            if (aim && hasPods && input.special && podCooldown <= 0f)
            {
                mech.FirePods();
                podCooldown = podInterval;
            }
        }

        /// <summary>Thruster wash: dust kicked up behind the feet while dashing, a light camera rumble for the pilot.</summary>
        void DashEffects(float dt)
        {
            if (!dashing || LodHidden || feet.Count == 0) return;
            dashDustT -= dt;
            if (dashDustT > 0f) return;
            dashDustT = Mathf.Lerp(0.16f, 0.07f, Mathf.Clamp01(speed / dashBoost));
            var f = feet[dashFoot++ % feet.Count].foot;
            Vector3 p = f.position - transform.forward * 1.2f;
            p.y = WorldGround.Height(p.x, p.z) + 0.05f;
            Vfx.DustPuff(p, 1.4f + speed / dashBoost);
            if (PlayerDriven && CameraRig.Main) CameraRig.Main.Shake(0.06f);
        }

        void StartMelee(bool stomp)
        {
            if (mech.IsAiming) mech.SetAiming(false);
            aimHold = 0f;
            mech.ClearAimTarget();
            meleeStomp = stomp;
            melee = stomp ? "Stomp" : strikeClip;
            meleeLen = stomp ? stompLength : strikeLength;
            meleeHitAt = stomp ? stompHitAt : strikeHitAt;
            meleeT = 0f;
            meleeHit = false;
            // strikes on the move play on the upper-body layer so the legs keep walking / running
            meleeUpper = !stomp && upperLayer >= 0 && Mathf.Abs(ForwardSpeed) > 0.6f;
            if (meleeUpper)
            {
                anim.CrossFadeInFixedTime(melee, 0.08f, upperLayer, 0f);
                upperW = 1f;
            }
            else mech.PlayState(melee, 0.12f);
        }

        void EndMelee()
        {
            if (melee == null) return;
            if (meleeUpper) anim.CrossFadeInFixedTime("Empty", 0.15f, upperLayer, 0f);
            else mech.PlayState("Idle", 0.2f);
            melee = null;
            meleeUpper = false;
        }

        void UpdateMelee(float dt)
        {
            if (melee == null)
            {
                upperW = Mathf.MoveTowards(upperW, 0f, dt * 5f);
                return;
            }
            meleeT += dt;
            if (!meleeHit && meleeT >= meleeHitAt)
            {
                meleeHit = true;
                if (meleeStomp) Stomp();
                else Strike();
            }
            if (meleeT >= meleeLen) EndMelee();
        }

        void Strike()
        {
            Vector3 center = transform.TransformPoint(0f, 5.2f, strikeReach);
            Vector3 push = (transform.forward + Vector3.up * 0.35f).normalized;
            if (strikeClip == "Slash") push = (transform.forward - transform.right * 0.6f + Vector3.up * 0.25f).normalized;   // backhand sweeps left
            int hits = 0;
            struck.Clear();
            foreach (var col in Physics.OverlapSphere(center, strikeRadius, ~0, QueryTriggerInteraction.Ignore))
            {
                var h = Health.Of(col);
                if (health && h && h != health && struck.Add(h) && h.TakeDamage(new DamageInfo { amount = 700f, type = DamageType.Melee, team = team,
                        point = center, dir = push, attacker = health }) > 0f && col is CharacterController) hits++;
                var rb = col.attachedRigidbody;
                if (rb == null || rb == Body) continue;
                var v = rb.GetComponent<Vehicle>();
                if (v) v.Wake();
                if (rb.isKinematic) continue;
                float massScale = Mathf.Clamp(11000f / rb.mass, 0.2f, 1f);   // heavier targets budge less
                rb.AddForceAtPosition(push * strikeDv * massScale * rb.mass, col.ClosestPoint(center), ForceMode.Impulse);
                hits++;
            }
            if (hits > 0) Vfx.MeleeImpact(center, strikeClip == "ShieldBash" ? 1.5f : 1.1f);
            if (CameraRig.Main) CameraRig.Main.Shake(hits > 0 ? 0.45f : 0.15f);
            LastStrikeHits = hits;
        }

        readonly System.Collections.Generic.HashSet<Health> struck = new System.Collections.Generic.HashSet<Health>();

        void Stomp()
        {
            Vector3 p = transform.TransformPoint(-0.75f, 0f, 0.6f);
            p.y = WorldGround.Height(p.x, p.z) + 0.05f;
            Vfx.Stomp(p, stompRadius);
            if (health) Health.Splash(p, stompRadius, 450f, DamageType.HE, team, health, health);
            LastStrikeHits = Effects.Blast(p, stompRadius, 9f, 0.9f, transform);
            if (CameraRig.Main) CameraRig.Main.Shake(0.8f);
        }

        /// <summary>Bodies moved by the last strike or stomp (for the auto-test log).</summary>
        public int LastStrikeHits { get; private set; }

        // ------------------------------------------------------------------ destruction
        protected override void OnDestroyed(DamageInfo d)
        {
            EndMelee();
            flying = false;
            mech.SetJets(false);
            mech.SetAiming(false);
            mech.ClearAimTarget();
            dashing = false;
            foreach (var j in jets) if (j) j.Rate = 0f;
            foreach (var j in thrusters) if (j) j.Rate = 0f;
            Vector3 c = transform.TransformPoint(0f, 5.5f, 0f);
            Vfx.Explosion(c, 2.2f, false);
            Health.Splash(c, 10f, 200f, DamageType.HE, Team.None, health, health);
            Burn(new Vector3(0f, 6f, 0f));
            StartCoroutine(Topple());
        }

        /// <summary>The dead mech keels over, pivoting on its feet, and slams into the ground.</summary>
        IEnumerator Topple()
        {
            Body.interpolation = RigidbodyInterpolation.None;
            Body.isKinematic = true;
            if (anim) anim.speed = 0.25f;
            // airborne when killed: drop to the ground first
            float floorY = WorldGround.Height(transform.position.x, transform.position.z);
            while (transform.position.y > floorY + 0.05f)
            {
                Vector3 p = transform.position;
                fallSpeed += 9.81f * Time.deltaTime;
                p.y = Mathf.Max(floorY, p.y - fallSpeed * Time.deltaTime);
                transform.position = p;
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.Euler(0f, transform.eulerAngles.y, 0f), Time.deltaTime * 3f);
                yield return null;
            }
            float side = Random.value < 0.5f ? 1f : -1f;
            Vector3 axis = Quaternion.AngleAxis(Random.Range(-25f, 25f), Vector3.up) * transform.right * side;
            Vector3 pivot = transform.position;
            Quaternion r0 = transform.rotation;
            float t = 0f, T = 1.8f;
            while (t < T)
            {
                t = Mathf.Min(T, t + Time.deltaTime);
                float k = t / T;
                Quaternion q = Quaternion.AngleAxis(84f * k * k, axis);
                transform.SetPositionAndRotation(pivot + Vector3.up * (1.1f * Mathf.SmoothStep(0f, 1f, k)), q * r0);
                yield return null;
            }
            if (anim) anim.speed = 0f;
            Vector3 hit = transform.TransformPoint(0f, 5f, 0f);
            hit.y = WorldGround.Height(hit.x, hit.z) + 0.05f;
            Vfx.Stomp(hit, 14f);
            Vfx.Explosion(transform.TransformPoint(0f, 6f, 0f), 1.2f, false);
            Effects.Blast(hit, 12f, 4f, 0.6f, transform);
        }
    }
}
