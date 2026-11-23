// MechKit runtime controller (Unity 6, Built-in RP or URP).
// Works on all three mech prefabs (Aegis, Halberd, Thunderhead); bones are looked up by name.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace MechKit
{
    public enum MechFaction { SkyLegion = 0, IronRepublic = 1, StormCorsairs = 2 }

    /// <summary>
    /// Drives a MechKit mech: picks Idle / Walk / Run / Aim clips, turns the torso toward an aim point,
    /// fires weapons (muzzle flash, recoil, gatling spin), switches the back banner between the three
    /// faction designs and sways the banner procedurally (wind + movement).
    /// </summary>
    [DisallowMultipleComponent]
    public class MechController : MonoBehaviour
    {
        [Header("Banner")]
        [SerializeField] MechFaction faction = MechFaction.SkyLegion;
        [Tooltip("Sway the banner from code (wind + movement). Turn off to use the 'Banner' animator layer instead.")]
        public bool proceduralBanner = true;
        [Range(0f, 2f)] public float windStrength = 1f;
        public float windFrequency = 0.55f;

        [Header("Locomotion")]
        [Tooltip("Ground speed (m/s) of the Walk clip at animator speed 1.")]
        public float walkSpeedRef = 2.5f;
        [Tooltip("Ground speed (m/s) of the Run clip at animator speed 1.")]
        public float runSpeedRef = 6.1f;
        public float runThreshold = 3.9f;
        public float crossFade = 0.25f;

        [Header("Aiming (applied on top of the Aim clip)")]
        public float maxYaw = 50f;
        public float maxPitch = 25f;
        public float aimSharpness = 8f;

        [Header("Weapons")]
        public float flashDuration = 0.06f;
        public float recoilDistance = 0.35f;
        public float recoilRecovery = 9f;
        [Tooltip("Thunderhead only: barrel spin speed (deg/s) while firing.")]
        public float gatlingSpinRate = 1440f;

        /// <summary>Raised on every shot with the muzzle transform (fire along muzzle.up) and the weapon index.</summary>
        public event Action<Transform, int> Fired;

        const float FlashScale = 1000f;   // flash / flame geometry is stored at 1/1000 size on its bone

        Animator animator;
        readonly Dictionary<string, Transform> bones = new Dictionary<string, Transform>();
        readonly List<Transform> muzzles = new List<Transform>();
        readonly List<Transform> flashes = new List<Transform>();
        readonly List<SkinnedMeshRenderer> banners = new List<SkinnedMeshRenderer>();
        Transform chest, upperChest, weapon, gatling, podL, podR;
        Transform[] jets = new Transform[0];
        Transform[] flags = new Transform[0];
        Quaternion[] flagRest;
        Vector3[] flagPitchAxis, flagRollAxis;
        Quaternion[] flashRest;
        Quaternion gatlingRest;
        float[] flashTimer;
        float[] flashRoll;
        bool cached;
        string state = "";
        float recoil, gatlingSpeed, gatlingAngle, curYaw, curPitch, lastShot = -10f, yawRate;
        bool jetsOn, hasAimTarget;
        Vector3 aimTarget, lastPos, localVel;
        Quaternion lastRot;
        int podToggle;

        public MechFaction Faction { get => faction; set { faction = value; ApplyFaction(); } }
        public bool IsAiming { get; private set; }
        public float AimYaw => curYaw;
        public float AimPitch => curPitch;
        public int WeaponCount { get { Cache(); return muzzles.Count; } }

        /// <summary>Muzzle socket for weapon index (0 = main weapon, 1/2 = Thunderhead missile pods L/R).</summary>
        public Transform GetMuzzle(int index = 0) { Cache(); return index >= 0 && index < muzzles.Count ? muzzles[index] : null; }

        /// <summary>World-space ray along the barrel (bone +Y) of weapon index.</summary>
        public Ray MuzzleRay(int index = 0)
        {
            var m = GetMuzzle(index);
            return m ? new Ray(m.position, m.up) : new Ray(transform.position, transform.forward);
        }

        public Transform Bone(string boneName) { Cache(); bones.TryGetValue(boneName, out var t); return t; }

        void Awake()
        {
            Cache();
            ApplyFaction();
            lastPos = transform.position;
            lastRot = transform.rotation;
            Play("Idle", 0f);
        }

        void OnValidate() { if (cached || !Application.isPlaying) ApplyFaction(); }

        void Cache()
        {
            if (cached) return;
            cached = true;
            animator = GetComponentInChildren<Animator>();
            foreach (var t in GetComponentsInChildren<Transform>(true))
                if (!bones.ContainsKey(t.name)) bones[t.name] = t;
            chest = Get("Chest");
            upperChest = Get("UpperChest");
            weapon = Get("WeaponR");
            gatling = Get("Gatling");
            if (gatling) gatlingRest = gatling.localRotation;
            podL = Get("Pod_L");
            podR = Get("Pod_R");
            foreach (var n in new[] { "Muzzle", "PodMuzzle_L", "PodMuzzle_R" })
            {
                var m = Get(n);
                if (!m) continue;
                muzzles.Add(m);
                flashes.Add(Get(n.Replace("Muzzle", "Flash")));
            }
            flashTimer = new float[flashes.Count];
            flashRoll = new float[flashes.Count];
            flashRest = new Quaternion[flashes.Count];
            for (int i = 0; i < flashes.Count; i++)
                if (flashes[i]) flashRest[i] = flashes[i].localRotation;
            var jl = new List<Transform>();
            foreach (var n in new[] { "Jet_L", "Jet_R" }) { var j = Get(n); if (j) jl.Add(j); }
            jets = jl.ToArray();
            var fl = new List<Transform>();
            for (int k = 0; k < 8; k++) { var f = Get($"Flag_{k}"); if (!f) break; fl.Add(f); }
            flags = fl.ToArray();
            flagRest = new Quaternion[flags.Length];
            flagPitchAxis = new Vector3[flags.Length];
            flagRollAxis = new Vector3[flags.Length];
            for (int k = 0; k < flags.Length; k++)
            {
                flagRest[k] = flags[k].localRotation;
                // character right / forward expressed in each flag bone's own frame (rest pose)
                flagPitchAxis[k] = Quaternion.Inverse(flags[k].rotation) * transform.right;
                flagRollAxis[k] = Quaternion.Inverse(flags[k].rotation) * transform.forward;
            }
            banners.Clear();
            foreach (var r in GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                if (r.name.Contains("_Banner_")) banners.Add(r);
                // flash / flame bones scale up x1000 when shown; keep their renderers from being culled
                if (r.name.EndsWith("_MuzzleFlash") || r.name.EndsWith("_JetFlame")) r.updateWhenOffscreen = true;
            }
        }

        Transform Get(string n) => bones.TryGetValue(n, out var t) ? t : null;

        void ApplyFaction()
        {
            if (!cached)
            {
                // edit-mode preview without a full cache
                foreach (var r in GetComponentsInChildren<SkinnedMeshRenderer>(true))
                    if (r.name.Contains("_Banner_")) r.enabled = r.name.EndsWith("_" + faction);
                return;
            }
            foreach (var r in banners)
                if (r) r.enabled = r.name.EndsWith("_" + faction);
        }

        // ---------------------------------------------------------------- public control API

        /// <summary>Call every frame with the mech's ground speed (m/s). Ignored while aiming.</summary>
        public void SetLocomotion(float speed)
        {
            if (IsAiming || animator == null) return;
            if (speed > runThreshold) { Play("Run"); animator.speed = Mathf.Clamp(speed / runSpeedRef, 0.5f, 1.8f); }
            else if (speed > 0.15f) { Play("Walk"); animator.speed = Mathf.Clamp(speed / walkSpeedRef, 0.4f, 1.8f); }
            else { Play("Idle"); animator.speed = 1f; }
        }

        /// <summary>Enter / leave the combat stance (Aim clip).</summary>
        public void SetAiming(bool aiming)
        {
            IsAiming = aiming;
            if (animator) animator.speed = 1f;
            Play(aiming ? "Aim" : "Idle");
        }

        /// <summary>Turn the torso (and Thunderhead's missile pods) toward a world point, within maxYaw / maxPitch.</summary>
        public void AimAt(Vector3 worldPoint) { hasAimTarget = true; aimTarget = worldPoint; }
        public void ClearAimTarget() => hasAimTarget = false;

        /// <summary>Fire weapon index (0 = main gun, 1/2 = missile pods). Shows the flash, kicks recoil, raises Fired.</summary>
        public void Fire(int index = 0)
        {
            Cache();
            if (index < 0 || index >= muzzles.Count) return;
            flashTimer[index] = flashDuration;
            flashRoll[index] = UnityEngine.Random.Range(0f, 360f);
            if (index == 0) { recoil = 1f; lastShot = Time.time; }
            Fired?.Invoke(muzzles[index], index);
        }

        /// <summary>Thunderhead: fires the left and right missile pods alternately.</summary>
        public void FirePods()
        {
            if (muzzles.Count < 3) return;
            Fire(1 + podToggle);
            podToggle ^= 1;
        }

        /// <summary>Halberd: jump-jet flames on/off.</summary>
        public void SetJets(bool on) => jetsOn = on;

        /// <summary>Cross-fade to any animator state by name (e.g. "Fly" for jet flight).</summary>
        public void PlayState(string stateName, float fade = -1f)
        {
            Cache();
            if (animator) animator.speed = 1f;
            Play(stateName, fade);
        }

        void Play(string s, float fade = -1f)
        {
            if (animator == null || animator.runtimeAnimatorController == null || state == s) return;
            int h = Animator.StringToHash(s);
            if (!animator.HasState(0, h)) return;
            animator.CrossFadeInFixedTime(h, fade < 0f ? crossFade : fade, 0);
            state = s;
        }

        // ---------------------------------------------------------------- procedural layer (after the Animator)
        void LateUpdate()
        {
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);
            Vector3 vel = (transform.position - lastPos) / dt;
            localVel = Vector3.Lerp(localVel, transform.InverseTransformDirection(vel), 1f - Mathf.Exp(-6f * dt));
            float dYaw = Mathf.DeltaAngle(lastRot.eulerAngles.y, transform.rotation.eulerAngles.y) / dt;
            yawRate = Mathf.Lerp(yawRate, dYaw, 1f - Mathf.Exp(-6f * dt));
            lastPos = transform.position;
            lastRot = transform.rotation;

            AimTorso(dt);
            Weapons(dt);
            if (proceduralBanner) Banner();
        }

        void AimTorso(float dt)
        {
            float yaw = 0f, pitch = 0f;
            if (hasAimTarget && upperChest)
            {
                Vector3 d = transform.InverseTransformDirection(aimTarget - upperChest.position);
                yaw = Mathf.Clamp(Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg, -maxYaw, maxYaw);
                pitch = Mathf.Clamp(Mathf.Atan2(d.y, new Vector2(d.x, d.z).magnitude) * Mathf.Rad2Deg, -maxPitch, maxPitch);
            }
            float k = 1f - Mathf.Exp(-aimSharpness * dt);
            curYaw = Mathf.Lerp(curYaw, yaw, k);
            curPitch = Mathf.Lerp(curPitch, pitch, k);
            if (Mathf.Abs(curYaw) < 1e-3f && Mathf.Abs(curPitch) < 1e-3f) return;
            Vector3 up = transform.up;
            if (chest) chest.rotation = Quaternion.AngleAxis(curYaw, up) * chest.rotation;
            Vector3 right = Quaternion.AngleAxis(curYaw, up) * transform.right;
            if (upperChest) upperChest.rotation = Quaternion.AngleAxis(-curPitch, right) * upperChest.rotation;
            foreach (var pod in new[] { podL, podR })
                if (pod) pod.rotation = Quaternion.AngleAxis(-curPitch * 0.6f, right) * pod.rotation;
        }

        void Weapons(float dt)
        {
            // recoil: slide the hand weapon back along its barrel (the Animator re-keys WeaponR every frame)
            if (weapon && recoil > 0f)
                weapon.position -= weapon.up * (recoil * recoil * recoilDistance);
            recoil = Mathf.MoveTowards(recoil, 0f, dt * recoilRecovery);

            for (int i = 0; i < flashes.Count; i++)
            {
                var f = flashes[i];
                if (!f) continue;
                if (flashTimer[i] > 0f)
                {
                    f.localScale = Vector3.one * (FlashScale * UnityEngine.Random.Range(0.85f, 1.15f));
                    f.localRotation = flashRest[i] * Quaternion.AngleAxis(flashRoll[i], Vector3.up);
                    flashTimer[i] -= dt;
                }
                else f.localScale = Vector3.one;
            }

            if (gatling)
            {
                float target = Time.time - lastShot < 0.25f ? gatlingSpinRate : 0f;
                gatlingSpeed = Mathf.MoveTowards(gatlingSpeed, target, gatlingSpinRate * 1.5f * dt);
                gatlingAngle = Mathf.Repeat(gatlingAngle + gatlingSpeed * dt, 360f);
                gatling.localRotation = gatlingRest * Quaternion.AngleAxis(gatlingAngle, Vector3.up);
            }

            foreach (var j in jets)
            {
                float s = jetsOn ? FlashScale * (1f + 0.07f * Mathf.Sin(Time.time * 47f) + 0.04f * Mathf.Sin(Time.time * 83f)) : 1f;
                j.localScale = Vector3.one * s;
            }
        }

        void Banner()
        {
            float t = Time.time * windFrequency * Mathf.PI * 2f;
            float trail = Mathf.Clamp(localVel.z * 3f, -8f, 24f);
            float side = Mathf.Clamp(-localVel.x * 2.5f - yawRate * 0.04f, -12f, 12f);
            for (int k = 0; k < flags.Length; k++)
            {
                float amp = 5f + 2.8f * k;
                float pitch = (k == 0 ? 4f : 1.5f) + trail * (0.55f + 0.15f * k) + windStrength * amp * Mathf.Sin(t - 1.05f * k);
                float roll = windStrength * 3f * Mathf.Sin(2f * t + 0.8f * k) + side * (0.5f + 0.2f * k);
                flags[k].localRotation = flagRest[k] * Quaternion.AngleAxis(pitch, flagPitchAxis[k]) *
                                         Quaternion.AngleAxis(roll, flagRollAxis[k]);
            }
        }
    }
}
