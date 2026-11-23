using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Third-person mannequin soldier with 8-direction strafing. The body always faces the camera yaw;
    /// WASD picks the direction, Shift runs. Movement speed per direction matches the strafe clips
    /// (no foot sliding): the speed envelope comes from the clip velocities measured at export.
    /// RMB raises the rifle (upper-body layer), LMB fires tracers, G launches an anti-tank rifle grenade.
    /// The same input struct is written by the player (Controlled) or by SoldierAI (aiDriven) in War mode.
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class SoldierController : MonoBehaviour
    {
        public string displayName = "Soldier";
        [Tooltip("Walk_F, Walk_FR, Walk_R, Walk_BR, Walk_B, Walk_BL, Walk_L, Walk_FL velocities (x = right, y = forward) in m/s.")]
        public Vector2[] walkVel = new Vector2[8];
        public Vector2[] runVel = new Vector2[8];
        public float turnSharpness = 14f;
        public float accel = 14f;
        [Tooltip("Movement and animation speed multiplier for walking (clips were authored at ~1.6 m/s).")]
        public float walkScale = 1.4f;
        [Tooltip("Movement and animation speed multiplier for sprinting (clips were authored at ~3.6 m/s).")]
        public float runScale = 1.55f;

        [System.NonSerialized] public ControlInput input;
        public bool Controlled { get; set; }
        /// <summary>SoldierAI is driving this soldier (War mode).</summary>
        [System.NonSerialized] public bool aiDriven;
        [System.NonSerialized] public Health health;
        public float grenadeInterval = 9f;
        public bool Dead { get; private set; }
        public Team Team => health ? health.team : Team.None;
        public Vector3 Velocity => Dead ? Vector3.zero : velocity;
        public Transform Muzzle => muzzle;
        public bool AimReady => aimW > 0.8f;
        public float GrenadeCooldown => grenadeCooldown;
        float grenadeCooldown, deadT;

        CharacterController cc;
        Animator anim;
        Transform muzzle;
        Vector3 velocity;
        float vy, aimW, cooldown, runBlend;
        int upperLayer = -1;
        static readonly int VelX = Animator.StringToHash("VelX");
        static readonly int VelZ = Animator.StringToHash("VelZ");

        public Vector3 CameraPivot => transform.position + Vector3.up * 1.62f;
        public float Speed => new Vector2(velocity.x, velocity.z).magnitude;

        void Awake()
        {
            cc = GetComponent<CharacterController>();
            anim = GetComponentInChildren<Animator>();
            if (anim) upperLayer = anim.GetLayerIndex("UpperBody");
            foreach (var t in GetComponentsInChildren<Transform>(true))
                if (t.name == "Muzzle") muzzle = t;
        }

        /// <summary>Max speed along a local direction (x = right, y = forward), interpolated between the 8 clips.</summary>
        static float Envelope(Vector2[] vel, Vector2 dir)
        {
            if (dir.sqrMagnitude < 1e-6f) return 0f;
            float a = Mathf.Atan2(dir.x, dir.y) * Mathf.Rad2Deg;
            float best = 0f;
            for (int i = 0; i < 8; i++)
            {
                Vector2 v0 = vel[i], v1 = vel[(i + 1) % 8];
                float a0 = Mathf.Atan2(v0.x, v0.y) * Mathf.Rad2Deg;
                float a1 = Mathf.Atan2(v1.x, v1.y) * Mathf.Rad2Deg;
                float span = Mathf.DeltaAngle(a0, a1);
                float off = Mathf.DeltaAngle(a0, a);
                if (span > 0f && off >= -0.01f && off <= span + 0.01f)
                {
                    best = Mathf.Lerp(v0.magnitude, v1.magnitude, Mathf.Clamp01(off / span));
                    break;
                }
            }
            return best > 0f ? best : vel[0].magnitude;
        }

        float simAcc, simDt;

        void Update()
        {
            long perfT0 = Perf.Now;
            float dt = Time.deltaTime;
            if (health == null || Controlled || Dead || health.SimTick(ref simAcc, out dt))
            {
                simDt = dt;
                UpdateTimed();
            }
            Perf.Add(Perf.Soldiers, perfT0);
        }

        void UpdateTimed()
        {
            float dt = simDt;
            if (Dead)
            {
                // the body stays a while, then sinks away
                deadT += dt;
                if (deadT > 30f) transform.position += Vector3.down * (0.35f * dt);
                if (deadT > 34f) gameObject.SetActive(false);
                return;
            }
            bool driven = Controlled || aiDriven;
            Vector2 m = driven ? input.move : Vector2.zero;
            if (driven)
            {
                Quaternion want = Quaternion.Euler(0f, input.lookYaw, 0f);
                transform.rotation = Quaternion.Slerp(transform.rotation, want, 1f - Mathf.Exp(-turnSharpness * dt));
            }
            bool aiming = driven && input.aim;
            bool run = driven && input.sprint && !aiming;
            float mag = Mathf.Clamp01(m.magnitude);
            // faster than the authored clips: speed and animation playback are scaled by the same factor
            runBlend = Mathf.MoveTowards(runBlend, run ? 1f : 0f, dt * 4f);
            float scale = Mathf.Lerp(walkScale, runScale, runBlend);
            Vector2 local = m.sqrMagnitude > 1e-4f ? m.normalized * (Envelope(run ? runVel : walkVel, m) * mag * (run ? runScale : walkScale)) : Vector2.zero;
            if (aiming) local *= 0.7f;
            Vector3 wantVel = transform.TransformDirection(new Vector3(local.x, 0f, local.y));
            velocity = Vector3.MoveTowards(velocity, wantVel, accel * dt);
            if (cc.isGrounded) vy = -1f;
            else vy -= 9.81f * dt;
            bool carried = false;
            if (Airship.All.Count > 0 && Airship.Carry(transform.position, out Vector3 carry, out float carryYaw))
            {
                cc.Move(carry);
                carried = true;
                if (Mathf.Abs(carryYaw) > 1e-5f) transform.Rotate(0f, carryYaw, 0f, Space.World);
            }
            // standing still on solid ground (hiding, peeking, aiming): nothing to sweep this frame
            bool still = !carried && velocity.sqrMagnitude < 1e-4f && wantVel.sqrMagnitude < 1e-4f && cc.isGrounded && !Controlled;
            if (!still) cc.Move((velocity + Vector3.up * vy) * dt);

            if (anim)
            {
                // the blend tree is laid out in the clips' own speeds, so feed it the de-scaled velocity
                Vector3 lv = transform.InverseTransformDirection(cc.velocity) / scale;
                if (aiming) lv /= 0.7f;              // aim-walk plays the walk clips slower instead of picking smaller ones
                anim.SetFloat(VelX, lv.x, 0.08f, dt);
                anim.SetFloat(VelZ, lv.z, 0.08f, dt);
                bool moving = lv.sqrMagnitude > 0.01f;
                anim.speed = moving ? scale * (aiming ? 0.7f : 1f) : 1f;
                aimW = Mathf.MoveTowards(aimW, aiming ? 1f : 0f, dt * 5f);
                if (upperLayer >= 0) anim.SetLayerWeight(upperLayer, aimW);
            }
            cooldown = Mathf.Max(0f, cooldown - dt);
            grenadeCooldown = Mathf.Max(0f, grenadeCooldown - dt);
            if (driven && aiming && input.fire && cooldown <= 0f && muzzle && aimW > 0.8f)
            {
                Vector3 dir = (input.aimPoint - muzzle.position).normalized;
                var shot = Shot.Visual(700f, 0.03f, 2.5f, 60f, ImpactKind.Bullet, 0.35f);
                Armory.Rifle.Apply(ref shot, health, transform);
                shot.model = ProjectileModel.Rifle;
                Tracers.Fire(muzzle.position, dir, shot);
                Vfx.Muzzle(muzzle.position, dir, 0.06f);
                cooldown = 0.11f;
            }
            if (driven && input.action2Down && grenadeCooldown <= 0f && muzzle && aimW > 0.8f)
            {
                // rifle grenade: a small rocket-assisted anti-armour round that flies to the aim point
                Vector3 dir = (input.aimPoint - muzzle.position).normalized;
                Missile.Launch(muzzle.position + dir * 0.4f, dir + Vector3.up * 0.04f, input.aimPoint, transform,
                    health ? Armory.RifleGrenade : Armory.None, health, null, 0.5f);
                grenadeCooldown = grenadeInterval;
            }
        }

        /// <summary>Killed: collapse (Death clip), drop the collider so rounds and vehicles pass, stop all control.</summary>
        public void Die()
        {
            if (Dead) return;
            Dead = true;
            Controlled = false;
            aiDriven = false;
            velocity = Vector3.zero;
            input = default;
            if (anim && anim.isActiveAndEnabled)
            {
                anim.speed = 1f;
                if (upperLayer >= 0) anim.SetLayerWeight(upperLayer, 0f);
                anim.CrossFadeInFixedTime("Death", 0.12f, 0);
            }
            if (cc) cc.enabled = false;
        }

        /// <summary>Teleport (CharacterController-safe).</summary>
        public void Place(Vector3 pos, float yaw)
        {
            cc.enabled = false;
            transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            cc.enabled = true;
            velocity = Vector3.zero;
        }
    }
}
