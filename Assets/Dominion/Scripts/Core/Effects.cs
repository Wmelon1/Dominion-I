using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>Short-lived visual effects (shockwave ring, impact flash) and physical blasts / hits.</summary>
    public static class Effects
    {
        static Material shockMat, flashMat;
        static Mesh cylinder, sphere;
        static readonly HashSet<Rigidbody> seen = new HashSet<Rigidbody>();

        static void Init()
        {
            if (cylinder != null) return;
            shockMat = Resources.Load<Material>("Dominion/M_Shockwave");
            flashMat = Resources.Load<Material>("Dominion/M_Tracer");
            var c = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            cylinder = c.GetComponent<MeshFilter>().sharedMesh;
            Object.Destroy(c);
            var s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            sphere = s.GetComponent<MeshFilter>().sharedMesh;
            Object.Destroy(s);
        }

        static void Spawn(Mesh mesh, Material src, Vector3 pos, Vector3 s0, Vector3 s1, float life, float glow)
        {
            Init();
            if (src == null) return;
            var go = new GameObject("FX");
            go.transform.position = pos;
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            var m = new Material(src);
            mr.sharedMaterial = m;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var fx = go.AddComponent<FxAnim>();
            fx.Setup(m, s0, s1, life, glow);
        }

        /// <summary>Expanding dust ring on the ground.</summary>
        public static void Shockwave(Vector3 pos, float radius)
        {
            pos.y = Mathf.Max(pos.y, 0.08f);
            Spawn(cylinder, shockMat, pos, new Vector3(3f, 0.02f, 3f), new Vector3(radius * 2f, 0.25f, radius * 2f), 0.7f, 1f);
        }

        /// <summary>Bright expanding ball (muzzle blast, missile detonation, melee impact).</summary>
        public static void Flash(Vector3 pos, float size)
        {
            Spawn(sphere, flashMat, pos, Vector3.one * size * 0.3f, Vector3.one * size, 0.18f, 1f);
        }

        /// <summary>Hit one body: wakes parked vehicles and applies an impulse (N s) at the point.</summary>
        public static void Hit(Rigidbody rb, Vector3 point, Vector3 dir, float impulse)
        {
            if (rb == null) return;
            var v = rb.GetComponent<Vehicle>();
            if (v) v.Wake();
            if (!rb.isKinematic) rb.AddForceAtPosition(dir.normalized * impulse, point, ForceMode.Impulse);
        }

        /// <summary>
        /// Radial blast: every rigid body within radius gets up to maxDv m/s (scaled down for heavy vehicles),
        /// pushed outward and upward. 'ignore' is the body that caused it.
        /// </summary>
        public static int Blast(Vector3 pos, float radius, float maxDv, float upward, Transform ignore)
        {
            seen.Clear();
            int n = 0;
            foreach (var col in Physics.OverlapSphere(pos, radius, ~0, QueryTriggerInteraction.Ignore))
            {
                var rb = col.attachedRigidbody;
                if (rb == null || !seen.Add(rb) || (ignore && rb.transform == ignore)) continue;
                var v = rb.GetComponent<Vehicle>();
                if (v) v.Wake();
                if (rb.isKinematic) continue;
                Vector3 d = rb.worldCenterOfMass - pos;
                float k = Mathf.Clamp01(1f - d.magnitude / radius);
                Vector3 dir = (new Vector3(d.x, 0f, d.z).normalized + Vector3.up * upward).normalized;
                float massScale = Mathf.Clamp(11000f / rb.mass, 0.2f, 1f);
                rb.AddForce(dir * (maxDv * k * massScale), ForceMode.VelocityChange);
                rb.AddTorque(Random.onUnitSphere * (maxDv * 0.08f * k * massScale), ForceMode.VelocityChange);
                n++;
            }
            if (CameraRig.Main) CameraRig.Main.Shake(Mathf.Clamp01(maxDv / 10f) * Mathf.Clamp01(1f - Vector3.Distance(CameraRig.Main.transform.position, pos) / (radius * 6f)));
            return n;
        }
    }

    /// <summary>Scales and fades a one-shot effect, then removes it.</summary>
    public class FxAnim : MonoBehaviour
    {
        Material mat;
        Vector3 s0, s1;
        float life, t;
        Color c0;

        public void Setup(Material m, Vector3 from, Vector3 to, float duration, float glow)
        {
            mat = m;
            s0 = from;
            s1 = to;
            life = duration;
            c0 = m.HasProperty("_EmissiveColor") ? m.GetColor("_EmissiveColor") * glow : Color.white;
            transform.localScale = from;
        }

        void Update()
        {
            t += Time.deltaTime;
            float k = Mathf.Clamp01(t / life);
            float e = 1f - (1f - k) * (1f - k);
            transform.localScale = Vector3.Lerp(s0, s1, e);
            if (mat.HasProperty("_EmissiveColor")) mat.SetColor("_EmissiveColor", c0 * (1f - k) * (1f - k));
            if (k >= 1f)
            {
                Destroy(mat);
                Destroy(gameObject);
            }
        }
    }
}
