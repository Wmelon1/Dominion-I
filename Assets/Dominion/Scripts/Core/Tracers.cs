using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Pooled glowing rounds with ballistic drop. Each round sweeps from where its tip was last frame to where it is now,
    /// so nothing is skipped at point-blank range; the shooter's own colliders are ignored. On a hit: impact effect,
    /// push, and (War mode) damage + splash. Proximity-fuzed rounds (anti-air flak) burst next to enemy aircraft.
    /// </summary>
    public class Tracers : MonoBehaviour
    {
        class Round { public Transform t; public Vector3 vel, head; public float life; public Shot shot; }

        static Tracers inst;
        readonly List<Round> active = new List<Round>();
        readonly Stack<Round> free = new Stack<Round>();
        readonly RaycastHit[] hits = new RaycastHit[12];
        Material mat;
        Mesh cube;

        /// <summary>Visual-only round (Sandbox props, effects).</summary>
        public static void Fire(Vector3 origin, Vector3 dir, float speed = 420f, float width = 0.08f, float length = 6f, float impulse = 0f,
            ImpactKind kind = ImpactKind.Bullet, float impactScale = 0.5f)
            => Fire(origin, dir, Shot.Visual(speed, width, length, impulse, kind, impactScale));

        public static void Fire(Vector3 origin, Vector3 dir, Shot s)
        {
            if (inst == null)
            {
                var go = new GameObject("Tracers");
                inst = go.AddComponent<Tracers>();
            }
            inst.Spawn(origin, dir.normalized, s);
        }

        void Awake()
        {
            mat = Resources.Load<Material>("Dominion/M_Tracer");
            cube = Streak();
        }

        /// <summary>
        /// The tracer's glow: a unit-length spindle along +Z, fattest just behind its head (the burning tracer compound in the
        /// base of the round) and tapering away to a point at the tail, where the eye's / camera's persistence fades.
        /// </summary>
        static Mesh Streak()
        {
            const int sides = 8;
            float[] zs = { 0.5f, 0.485f, 0.45f, 0.3f, -0.1f, -0.5f };
            float[] rs = { 0f, 0.4f, 0.5f, 0.36f, 0.16f, 0f };
            var v = new List<Vector3>();
            var tri = new List<int>();
            for (int i = 0; i < zs.Length; i++)
                for (int k = 0; k < sides; k++)
                {
                    float a = k * Mathf.PI * 2f / sides;
                    v.Add(new Vector3(Mathf.Cos(a) * rs[i], Mathf.Sin(a) * rs[i], zs[i]));
                }
            for (int i = 0; i < zs.Length - 1; i++)
                for (int k = 0; k < sides; k++)
                {
                    int a = i * sides + k, b = i * sides + (k + 1) % sides, c = a + sides, d = b + sides;
                    tri.Add(a); tri.Add(c); tri.Add(b);
                    tri.Add(b); tri.Add(c); tri.Add(d);
                }
            var m = new Mesh { name = "TracerStreak" };
            m.SetVertices(v);
            m.SetTriangles(tri, 0);
            m.RecalculateNormals();
            m.RecalculateBounds();
            return m;
        }

        void Spawn(Vector3 origin, Vector3 dir, Shot s)
        {
            Round r = free.Count > 0 ? free.Pop() : null;
            if (r == null)
            {
                var go = new GameObject("Tracer");
                go.transform.SetParent(transform, false);
                go.AddComponent<MeshFilter>().sharedMesh = cube;
                var mr = go.AddComponent<MeshRenderer>();
                mr.sharedMaterial = mat;
                mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                r = new Round { t = go.transform };
            }
            if (s.life <= 0f) s.life = 2.5f;
            s.origin = origin;
            r.shot = s;
            r.life = s.life;
            r.vel = dir * s.speed;
            // brass out of the breech for rifles, machine guns and autocannons
            if (s.model == ProjectileModel.Rifle || s.model == ProjectileModel.MG || s.model == ProjectileModel.Autocannon)
                Projectiles.EjectCasing(origin - dir * (s.model == ProjectileModel.Rifle ? 0.45f : 1.1f), dir,
                    s.attacker ? s.attacker.Velocity : Vector3.zero, s.model == ProjectileModel.Autocannon);
            r.head = origin;
            r.t.gameObject.SetActive(true);
            r.t.position = origin + dir * (s.length * 0.5f);
            r.t.rotation = Quaternion.LookRotation(dir);
            r.t.localScale = new Vector3(s.width, s.width, s.length);
            active.Add(r);
        }

        /// <summary>First hit along a segment that is not part of the shooter.</summary>
        bool Cast(Vector3 from, Vector3 dir, float dist, Transform ignore, out RaycastHit best)
        {
            best = default;
            int n = Physics.RaycastNonAlloc(from, dir, hits, dist, ~0, QueryTriggerInteraction.Ignore);
            float bd = float.MaxValue;
            bool found = false;
            for (int i = 0; i < n; i++)
            {
                var h = hits[i];
                if (ignore && h.collider.transform.IsChildOf(ignore)) continue;
                if (h.distance < bd)
                {
                    bd = h.distance;
                    best = h;
                    found = true;
                }
            }
            return found;
        }

        void LateUpdate()
        {
            Projectiles.Tick(Time.deltaTime);
            Projectiles.Flush();
        }

        void Update()
        {
            long perfT0 = Perf.Now;
            UpdateTimed();
            Perf.Add(Perf.Tracers, perfT0);
        }

        void UpdateTimed()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f)
            {
                foreach (var r in active)
                    if (r.shot.model != ProjectileModel.None)
                        Projectiles.Draw(r.shot.model, r.head + r.vel.normalized * Projectiles.LengthOf(r.shot.model), r.vel);
                return;
            }
            for (int i = active.Count - 1; i >= 0; i--)
            {
                var r = active[i];
                r.life -= dt;
                r.vel += Physics.gravity * (r.shot.gravity * dt);
                Vector3 dir = r.vel.normalized;
                Vector3 center = r.t.position + r.vel * dt;
                Vector3 newHead = center + dir * (r.shot.length * 0.5f);
                Vector3 seg = newHead - r.head;
                float len = seg.magnitude;
                bool done = r.life <= 0f;
                if (len > 1e-4f)
                {
                    Vector3 sd = seg / len;
                    if (Cast(r.head, sd, len, r.shot.source, out RaycastHit h))
                    {
                        Land(r, h.point, h.normal, h.collider, h.rigidbody, sd);
                        done = true;
                    }
                    else if (r.shot.proximity > 0f && Proximity(r, r.head, sd, len, out Vector3 burst))
                    {
                        Flak(r, burst);
                        done = true;
                    }
                }
                if (done)
                {
                    r.t.gameObject.SetActive(false);
                    active.RemoveAt(i);
                    free.Push(r);
                    continue;
                }
                r.head = newHead;
                r.t.position = center;
                if (r.shot.model != ProjectileModel.None) Projectiles.Draw(r.shot.model, newHead + dir * Projectiles.LengthOf(r.shot.model), r.vel);
                r.t.rotation = Quaternion.LookRotation(dir);
            }
        }

        void Land(Round r, Vector3 point, Vector3 normal, Collider col, Rigidbody rb, Vector3 dir)
        {
            var s = r.shot;
            if (s.impulse > 0f) Effects.Hit(rb, point, dir, s.impulse);
            Vfx.Impact(s.kind, s.impactScale, point, normal, rb != null);
            if (s.damage <= 0f && s.splash <= 0f) return;
            float f = s.RangeFactor(point);
            CountFalloff(s, point, f);
            var target = Health.Of(col);
            if (target && s.damage > 0f)
                target.TakeDamage(new DamageInfo { amount = s.damage * f, type = s.type, team = s.team, point = point, dir = dir, attacker = s.attacker });
            if (s.splash > 0f) Health.Splash(point, s.splashRadius, s.splash * f, DamageType.HE, s.team, s.attacker, target);
        }

        /// <summary>Rounds with range falloff (airship guns) that landed: count, summed damage factor, weakest factor, longest flight.</summary>
        public static int FalloffHits;
        public static float FalloffSum, FalloffLowest = 1f, FalloffFarthest;

        static void CountFalloff(in Shot s, Vector3 p, float f)
        {
            if (s.falloffEnd <= 0f) return;
            FalloffHits++;
            FalloffSum += f;
            FalloffLowest = Mathf.Min(FalloffLowest, f);
            FalloffFarthest = Mathf.Max(FalloffFarthest, Vector3.Distance(s.origin, p));
        }

        /// <summary>Did the segment pass within the fuze distance of an enemy aircraft?</summary>
        static bool Proximity(Round r, Vector3 from, Vector3 dir, float len, out Vector3 burst)
        {
            burst = default;
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (h.cls != UnitClass.Air || !h.Alive || !Health.Enemies(h.team, r.shot.team) || !h.Airborne) continue;
                Vector3 c = h.Center;
                float t = Mathf.Clamp(Vector3.Dot(c - from, dir), 0f, len);
                Vector3 p = from + dir * t;
                if ((p - c).sqrMagnitude < (r.shot.proximity + h.Radius) * (r.shot.proximity + h.Radius))
                {
                    burst = p;
                    return true;
                }
            }
            return false;
        }

        static void Flak(Round r, Vector3 p)
        {
            var s = r.shot;
            Vfx.Explosion(p, 0.35f, false);
            float f = s.RangeFactor(p);
            CountFalloff(s, p, f);
            Health.Splash(p, Mathf.Max(s.splashRadius, s.proximity + 2f), (s.damage * 0.6f + s.splash) * f, DamageType.Cannon, s.team, s.attacker);
        }
    }
}
