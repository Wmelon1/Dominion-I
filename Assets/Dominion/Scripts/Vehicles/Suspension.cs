using System.Collections.Generic;
using Unity.Collections;
using UnityEngine;

namespace Dominion
{
    /// <summary>One wheel / road wheel / landing-gear wheel on a raycast spring-damper.</summary>
    public class WheelContact
    {
        public Transform bone;
        public Vector3 restLocal;          // wheel centre in vehicle space (rest pose)
        public float radius;
        public bool left, steered, driven = true, enabled = true, moveVisual = true;
        public Vector3 boneRestPos, parentUp;
        // state
        public float len, prevLen, load, roll;
        public bool grounded;
        public Vector3 point;
    }

    /// <summary>
    /// Raycast suspension: each wheel is a spring-damper along the vehicle's up axis, tuned so the static
    /// equilibrium matches the modelled ride height. Tyre / track forces are applied at the contact patches,
    /// so acceleration squat, brake dive, body roll and firing rock all come out of the physics.
    /// </summary>
    public class Suspension
    {
        public readonly List<WheelContact> wheels = new List<WheelContact>();
        public float travel = 0.25f;
        public float sag;
        public float k, c;
        readonly Rigidbody rb;
        readonly Transform tr;
        readonly RaycastHit[] hits = new RaycastHit[8];

        public Suspension(Rigidbody rb, Transform tr)
        {
            this.rb = rb;
            this.tr = tr;
            registry.Add(this);
            if (batcher == null) batcher = new GameObject("Suspension Batch").AddComponent<SuspensionBatcher>();
        }

        // ------------------------------------------------------------------ batched wheel raycasts
        // Every wheel ray of every vehicle is cast together once per physics step as one multithreaded RaycastCommand job
        // (same rays, same results as casting them one by one in Step).
        static readonly List<Suspension> registry = new List<Suspension>();
        static SuspensionBatcher batcher;
        static NativeArray<RaycastCommand> cmds;
        static NativeArray<RaycastHit> results;
        const int MaxHits = 3;
        int batchBase = -1;
        float batchStamp = -1f;

        bool Active => rb != null && !rb.isKinematic && rb.gameObject.activeInHierarchy;

        public static void BatchCast()
        {
            registry.RemoveAll(x => x.rb == null);
            int total = 0;
            foreach (var su in registry) if (su.Active) total += su.wheels.Count;
            if (total == 0) return;
            if (!cmds.IsCreated || cmds.Length < total)
            {
                DisposeBatch();
                int cap = Mathf.NextPowerOfTwo(total + 64);
                cmds = new NativeArray<RaycastCommand>(cap, Allocator.Persistent);
                results = new NativeArray<RaycastHit>(cap * MaxHits, Allocator.Persistent);
            }
            var qp = new QueryParameters(~0, false, QueryTriggerInteraction.Ignore, false);
            int k = 0;
            float stamp = Time.fixedTime;
            foreach (var su in registry)
            {
                if (!su.Active) { su.batchBase = -1; continue; }
                su.batchBase = k;
                su.batchStamp = stamp;
                Vector3 up = su.tr.up;
                foreach (var w in su.wheels)
                    cmds[k++] = new RaycastCommand(su.tr.TransformPoint(w.restLocal) + up * su.sag, -up, qp, su.travel + w.radius);
            }
            RaycastCommand.ScheduleBatch(cmds.GetSubArray(0, k), results.GetSubArray(0, k * MaxHits), 8, MaxHits).Complete();
        }

        public static void DisposeBatch()
        {
            if (cmds.IsCreated) cmds.Dispose();
            if (results.IsCreated) results.Dispose();
        }

        public WheelContact Add(Transform bone, float radius)
        {
            var w = new WheelContact
            {
                bone = bone,
                radius = radius,
                restLocal = tr.InverseTransformPoint(bone.position),
                boneRestPos = bone.localPosition,
                parentUp = bone.parent ? (Quaternion.Inverse(bone.parent.rotation) * tr.up).normalized : Vector3.up,
            };
            w.left = w.restLocal.x < 0f;
            wheels.Add(w);
            return w;
        }

        /// <summary>Average wheel position in vehicle space (balance point for the centre of mass).</summary>
        public Vector3 WheelCentroid()
        {
            Vector3 c = Vector3.zero;
            foreach (var w in wheels) c += w.restLocal;
            return wheels.Count > 0 ? c / wheels.Count : Vector3.zero;
        }

        /// <summary>Spring rate so the static sag is 45 % of travel; damping ratio zeta.</summary>
        public void Tune(float mass, float travelM, float zeta)
        {
            travel = travelM;
            sag = travel * 0.45f;
            int n = Mathf.Max(1, wheels.Count);
            k = mass * -Physics.gravity.y / (n * (travel - sag));
            c = 2f * zeta * Mathf.Sqrt(k * mass / n);
            foreach (var w in wheels) w.len = w.prevLen = sag;
        }

        /// <summary>Springs + tyre forces. tyre(w) returns the contact-patch force (world) for a grounded wheel.</summary>
        public int Step(float dt, System.Func<WheelContact, Vector3> tyre)
        {
            int grounded = 0;
            Vector3 up = tr.up;
            bool batched = batchBase >= 0 && batchStamp == Time.fixedTime && results.IsCreated;
            for (int wi = 0; wi < wheels.Count; wi++)
            {
                var w = wheels[wi];
                w.grounded = false;
                if (!w.enabled)
                {
                    w.len = w.prevLen = travel;
                    w.load = 0f;
                    continue;
                }
                float best = float.MaxValue;
                if (batched)
                {
                    int b0 = (batchBase + wi) * MaxHits;
                    for (int i = 0; i < MaxHits; i++)
                    {
                        var h = results[b0 + i];
                        if (h.collider == null) break;
                        if (h.rigidbody == rb) continue;
                        if (h.distance < best) { best = h.distance; w.point = h.point; }
                    }
                }
                else
                {
                    Vector3 origin = tr.TransformPoint(w.restLocal) + up * sag;
                    float maxLen = travel + w.radius;
                    int n = Physics.RaycastNonAlloc(origin, -up, hits, maxLen, ~0, QueryTriggerInteraction.Ignore);
                    for (int i = 0; i < n; i++)
                    {
                        if (hits[i].rigidbody == rb) continue;
                        if (hits[i].distance < best)
                        {
                            best = hits[i].distance;
                            w.point = hits[i].point;
                        }
                    }
                }
                if (best < float.MaxValue)
                {
                    w.len = Mathf.Clamp(best - w.radius, 0f, travel);
                    w.grounded = true;
                }
                else w.len = travel;
                float f = k * (travel - w.len) + c * (w.prevLen - w.len) / dt;
                w.prevLen = w.len;
                w.load = w.grounded ? Mathf.Max(0f, f) : 0f;
                if (!w.grounded) continue;
                grounded++;
                rb.AddForceAtPosition(up * w.load, w.point);
                rb.AddForceAtPosition(tyre(w), w.point);
            }
            // anti-roll bars: each axle's left and right wheels resist differing compression
            if (antiRoll > 0f)
                foreach (var (l, r) in axles)
                {
                    float f = (l.len - r.len) * antiRoll;
                    if (l.grounded) rb.AddForceAtPosition(-up * f, l.point);
                    if (r.grounded) rb.AddForceAtPosition(up * f, r.point);
                }
            return grounded;
        }

        float antiRoll;
        readonly List<(WheelContact l, WheelContact r)> axles = new List<(WheelContact, WheelContact)>();

        /// <summary>Pair left/right wheels at the same station into axles and fit anti-roll bars (stiffness = factor * spring rate).</summary>
        public void AddAntiRollBars(float factor)
        {
            axles.Clear();
            foreach (var l in wheels)
            {
                if (l.restLocal.x >= 0f) continue;
                WheelContact best = null;
                foreach (var r in wheels)
                    if (r.restLocal.x > 0f && Mathf.Abs(r.restLocal.z - l.restLocal.z) < 0.35f &&
                        (best == null || Mathf.Abs(r.restLocal.z - l.restLocal.z) < Mathf.Abs(best.restLocal.z - l.restLocal.z)))
                        best = r;
                if (best != null) axles.Add((l, best));
            }
            antiRoll = k * factor;
        }

        /// <summary>Move wheel bones with the suspension (wheel centre follows the ground).</summary>
        public void ApplyVisual()
        {
            foreach (var w in wheels)
                if (w.bone && w.moveVisual) w.bone.localPosition = w.boneRestPos + w.parentUp * (sag - w.len);
        }

        /// <summary>
        /// Standard tyre model: lateral grip proportional to slip velocity, longitudinal drive / brake force,
        /// rolling resistance, all limited by the friction circle (mu * load).
        /// </summary>
        public Vector3 Tyre(WheelContact w, Vector3 fwd, Vector3 right, float drive, float brake, float mu, float latStiff, float dt)
        {
            Vector3 v = rb.GetPointVelocity(w.point);
            float vLong = Vector3.Dot(v, fwd);
            float vLat = Vector3.Dot(v, right);
            float share = rb.mass / Mathf.Max(1, wheels.Count);
            float fLat = -vLat * latStiff * share;
            float fLong = drive - Mathf.Clamp(vLong, -1f, 1f) * 0.02f * w.load;
            if (brake > 0f)
                fLong -= Mathf.Sign(vLong) * Mathf.Min(brake * share, Mathf.Abs(vLong) * share / dt * 0.5f);
            float limit = mu * w.load;
            Vector2 f = new Vector2(fLong, fLat);
            if (f.magnitude > limit) f = f.normalized * limit;
            w.roll += vLong * dt;
            return fwd * f.x + right * f.y;
        }
    }
}

namespace Dominion
{
    /// <summary>Runs the batched wheel raycasts at the start of every physics step, before any vehicle simulates.</summary>
    [DefaultExecutionOrder(-1000)]
    public class SuspensionBatcher : MonoBehaviour
    {
        void FixedUpdate() => Suspension.BatchCast();
        void OnDestroy() => Suspension.DisposeBatch();
    }
}
