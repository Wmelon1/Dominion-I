using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Wheeled transports (Mule 6x6 truck, Bastion 4x4 MRAP). Independent spring-damper per wheel (the wheels
    /// visibly travel with the suspension), all-wheel drive, front-axle steering with tyre slip and grip limits,
    /// so the body squats, dives and leans in corners. Roof gun and doors.
    /// </summary>
    public class WheeledVehicle : Vehicle
    {
        [Header("Wheels")]
        public string[] wheelBones = new string[0];
        public float[] wheelRadii = new float[0];
        public string[] steerBones = new string[0];
        public float maxSteer = 30f;

        [Header("Roof gun (optional)")]
        public string turretBone = "";
        public string gunBone = "gun";
        public string barrelBone = "barrel";
        public string muzzleBone = "muzzle";
        public string flashBone = "flash";
        public float gunMin = -10f, gunMax = 60f;
        public float fireInterval = 0.1f;

        [Header("Door (optional)")]
        public string doorBone = "";
        public string doorAxis = "x";
        public float doorAngle = 95f;

        [Header("Driving")]
        public float maxSpeed = 24f;
        public float maxReverse = 7f;
        public float engineAccel = 6.5f;
        public float suspensionTravel = 0.3f;

        Suspension susp;
        float steer, cooldown, doorT, doorSign = 1f;
        bool doorOpen;
        public override void SetDoor(bool open) { if (door) doorOpen = open; }
        protected override bool CanProxy => true;
        protected override float ProxyTopSpeed => maxSpeed;
        protected override float ProxyTurnRate => 22f;
        readonly List<(Transform bone, Vector3 axis)> steers = new List<(Transform, Vector3)>();
        readonly List<(WheelContact w, Vector3 axis)> wheelVis = new List<(WheelContact, Vector3)>();
        Turret turret;
        Gun gun;
        Transform door;
        Vector3 doorLocalAxis;

        public override string ControlsHelp =>
            "W/S  throttle / reverse     A/D  steer     Space  brake" +
            (turret != null ? "\nMouse  aim roof gun     LMB  fire" : "\nMouse  look around") +
            (door ? "\nF  door / tailgate" : "") + "\nR  reset upright     E  exit";

        protected override void Awake()
        {
            base.Awake();
            susp = new Suspension(Body, transform);
            foreach (var s in steerBones)
                if (rig[s]) steers.Add((rig[s], RigBones.LocalAxis(rig[s], transform.up)));
            for (int i = 0; i < wheelBones.Length; i++)
            {
                var b = rig[wheelBones[i]];
                if (b == null) continue;
                var w = susp.Add(b, Mathf.Max(0.1f, wheelRadii[i]));
                w.steered = b.parent && b.parent.name.StartsWith("steer");
                wheelVis.Add((w, RigBones.LocalAxis(b, transform.right)));
            }
            susp.Tune(Body.mass, suspensionTravel, 0.38f);
            susp.AddAntiRollBars(2.2f);
            Vector3 wc = susp.WheelCentroid();
            Body.centerOfMass = new Vector3(wc.x, CenterOfMass.y, wc.z);
            if (!string.IsNullOrEmpty(turretBone) && rig[turretBone])
            {
                turret = Turret.Create(rig, transform, turretBone, gunBone, muzzleBone, gunMin, gunMax, 90f, 60f);
                gun = new Gun { barrel = rig[barrelBone], muzzle = rig[muzzleBone], flash = rig[flashBone], recoilDist = 0.05f,
                    muzzleScale = muzzleScale, impact = impactKind, impactScale = impactScale };
            }
            // side exhaust low on the right, blowing out and back
            SetupGroundEffects(new Vector3(localBounds.center.x + localBounds.extents.x * 0.95f, 0.75f, localBounds.center.z - localBounds.extents.z * 0.2f),
                (Vector3.right + Vector3.back * 0.6f).normalized);
            door = rig[doorBone];
            if (door)
            {
                doorLocalAxis = RigBones.LocalAxis(door, doorAxis == "x" ? transform.right : transform.up);
                doorSign = RigBones.OpenSign(door, doorLocalAxis, doorAngle, transform.TransformPoint(localBounds.center));
            }
        }

        public override float ProjectileSpeed => 520f;
        public override bool Reloaded => cooldown <= 0f;

        public override bool GetAim(out Vector3 origin, out Vector3 dir)
        {
            origin = gun != null && gun.muzzle ? gun.muzzle.position : transform.position;
            dir = gun != null ? gun.Direction : transform.forward;
            return gun != null && gun.muzzle;
        }

        protected override void Simulate(float dt)
        {
            float throttle = input.move.y;
            Vector3 fwd = transform.forward, right = transform.right, up = transform.up;
            float vFwd = Vector3.Dot(Body.linearVelocity, fwd);
            // steering lock reduces with speed (as a driver would), steering rate is limited
            // modest steering lock (large turning circle), reduced further at speed
            float wantSteer = input.move.x * maxSteer * Mathf.Lerp(1f, 0.35f, Mathf.Clamp01(Mathf.Abs(vFwd) / maxSpeed));
            steer = Mathf.MoveTowards(steer, wantSteer, 60f * dt);
            bool reversingInput = throttle * vFwd < -0.5f;
            float brake = !Occupied ? 6f : input.jump ? 8f : reversingInput ? 6f : Mathf.Abs(throttle) < 0.05f ? 0.8f : 0f;   // parked: handbrake
            float top = throttle >= 0f ? maxSpeed : maxReverse;
            float rr = vFwd / top;
            float lim = Mathf.Sign(throttle) == Mathf.Sign(vFwd) ? Mathf.Clamp01(1f - rr * rr * rr * rr) : 1f;
            float drive = reversingInput ? 0f : throttle * Body.mass * engineAccel * lim / Mathf.Max(1, susp.wheels.Count);
            Quaternion steerRot = Quaternion.AngleAxis(steer, up);
            Vector3 sf = steerRot * fwd, sr = steerRot * right;
            susp.Step(dt, w => w.steered
                ? susp.Tyre(w, sf, sr, drive, brake, 1.0f, 11f, dt)
                : susp.Tyre(w, fwd, right, drive, brake, 1.0f, 11f, dt));
        }

        protected override void Animate(float dt, float moved)
        {
            UpdateGroundEffects(input.move.y);
            if (!LodHidden)
            {
                foreach (var s in steers) rig.Rotate(s.bone, s.axis, steer);
                susp.ApplyVisual();
                foreach (var (w, axis) in wheelVis) rig.Rotate(w.bone, axis, w.roll / w.radius * Mathf.Rad2Deg);
            }

            cooldown = Mathf.Max(0f, cooldown - dt);
            if (Occupied)
            {
                if (turret != null)
                {
                    turret.AimAt(rig, transform, input.aimPoint, dt);
                    if (input.fire && cooldown <= 0f)
                    {
                        gun.Shoot(MakeShot(520f, 0.07f, 4.2f, 600f, impactKind, impactScale));
                        cooldown = fireInterval;
                    }
                }
                if (input.action1Down && door) doorOpen = !doorOpen;
            }
            gun?.Animate(rig, dt);
            if (door)
            {
                doorT = Mathf.MoveTowards(doorT, doorOpen ? 1f : 0f, dt / 1.5f);
                rig.Rotate(door, doorLocalAxis, doorSign * doorAngle * Mathf.SmoothStep(0f, 1f, doorT));
            }
        }
    }
}
