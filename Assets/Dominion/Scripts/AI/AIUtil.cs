using System;
using UnityEngine;

namespace Dominion
{
    /// <summary>A place to hide behind a wall, and the spot at the wall's end to lean out and shoot from.</summary>
    public class CoverSpot
    {
        public Vector3 hide, peek;
        /// <summary>Points from the wall toward the hiding side.</summary>
        public Vector3 normal;
        public Vector3 wall;
        public SoldierAI occupant;

        /// <summary>Is the wall between this spot and a threat at 'threat'?</summary>
        public bool Protects(Vector3 threat)
        {
            Vector3 d = threat - hide;
            d.y = 0f;
            float m = d.magnitude;
            return m > 4f && Vector3.Dot(d / m, normal) < -0.4f;
        }
    }

    /// <summary>Shared combat-AI helpers: target scoring, line of sight, firing solutions, friendly-fire checks.</summary>
    public static class AIUtil
    {
        static readonly RaycastHit[] buf = new RaycastHit[24];
        static readonly Health[] topH = new Health[4];
        static readonly float[] topS = new float[4];

        public static Vector3 Flat(Vector3 v) { v.y = 0f; return v; }

        public static float YawTo(Vector3 from, Vector3 to) => Mathf.Atan2(to.x - from.x, to.z - from.z) * Mathf.Rad2Deg;

        /// <summary>Signed angle (deg) from a transform's flat forward to a world point, + = to the right.</summary>
        public static float AngleTo(Transform t, Vector3 p)
        {
            Vector3 l = t.InverseTransformDirection(Flat(p - t.position));
            return Mathf.Atan2(l.x, l.z) * Mathf.Rad2Deg;
        }

        /// <summary>Intercept point for a round of the given speed and gravity fraction (lead + drop compensation).</summary>
        public static Vector3 Lead(Vector3 from, Health target, float speed, float gravity, float leadFactor = 1f)
        {
            Vector3 c = target.Center, v = target.Velocity, p = c;
            float t = 0f;
            for (int i = 0; i < 3; i++)
            {
                t = Vector3.Distance(from, p) / Mathf.Max(speed, 1f);
                p = c + v * (t * leadFactor);
            }
            p.y += 0.5f * 9.81f * gravity * t * t;
            return p;
        }

        /// <summary>Nearest hit along a ray that is not part of 'self'.</summary>
        public static bool Cast(Vector3 from, Vector3 dir, float dist, Transform self, out RaycastHit hit)
        {
            hit = default;
            int n = Physics.RaycastNonAlloc(from, dir, buf, dist, ~0, QueryTriggerInteraction.Ignore);
            float best = float.MaxValue;
            bool any = false;
            for (int i = 0; i < n; i++)
            {
                if (self && buf[i].collider.transform.IsChildOf(self)) continue;
                if (buf[i].distance < best)
                {
                    best = buf[i].distance;
                    hit = buf[i];
                    any = true;
                }
            }
            return any;
        }

        /// <summary>Clear line of sight from an eye point to the target's centre.</summary>
        public static bool Visible(Vector3 eye, Health target, Transform self)
        {
            Vector3 d = target.Center - eye;
            float dist = d.magnitude;
            if (dist < 0.5f) return true;
            if (!Cast(eye, d / dist, dist, self, out RaycastHit h)) return true;
            if (Health.Of(h.collider) == target) return true;
            return h.distance > dist - target.Radius - 0.6f;
        }

        /// <summary>Would a shot along dir hit a friendly unit before 'dist'?</summary>
        public static bool FriendlyInLine(Vector3 from, Vector3 dir, float dist, Team team, Transform self)
        {
            int n = Physics.SphereCastNonAlloc(from, 0.5f, dir, buf, Mathf.Min(dist, 400f), ~0, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                if (self && buf[i].collider.transform.IsChildOf(self)) continue;
                var h = Health.Of(buf[i].collider);
                if (h && h.Alive && h.team == team) return true;
            }
            return false;
        }

        /// <summary>
        /// Best enemy by preference / distance / threat (whoever shot us last scores higher, the current target is
        /// sticky, badly damaged units get finished off). The top few are checked for line of sight; returns the best
        /// visible one, or the best overall (visible = false) so the unit can move to engage it.
        /// </summary>
        public static Health PickTarget(Health self, Vector3 eye, float range, Func<Health, float, float> preference, Health current,
            Transform selfT, bool needSight, out bool visible)
        {
            visible = false;
            int count = 0;
            for (int k = 0; k < topH.Length; k++) { topH[k] = null; topS[k] = 0f; }
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (!h.Alive || !Health.Enemies(h.team, self.team)) continue;
                float dist = Vector3.Distance(eye, h.Center);
                if (dist > range) continue;
                float p = preference(h, dist);
                if (p <= 0f) continue;
                float score = p / (1f + dist / 140f);
                if (h == current) score *= 1.4f;
                if (h == self.LastAttacker && Time.time - self.LastHitTime < 6f) score *= 1.7f;
                if (h.Fraction < 0.35f) score *= 1.2f;
                // insert into the top list
                for (int k = 0; k < topH.Length; k++)
                {
                    if (topH[k] == null || score > topS[k])
                    {
                        for (int j = topH.Length - 1; j > k; j--) { topH[j] = topH[j - 1]; topS[j] = topS[j - 1]; }
                        topH[k] = h;
                        topS[k] = score;
                        count++;
                        break;
                    }
                }
            }
            if (topH[0] == null) return null;
            if (!needSight)
            {
                visible = true;
                return topH[0];
            }
            for (int k = 0; k < topH.Length; k++)
            {
                if (topH[k] == null) break;
                if (Visible(eye, topH[k], selfT))
                {
                    visible = true;
                    return topH[k];
                }
            }
            return topH[0];
        }

        /// <summary>Random aim error: a point offset perpendicular-ish to the line of fire, sized by angle (deg) and range.</summary>
        public static Vector3 AimError(float dist, float deg)
        {
            return UnityEngine.Random.insideUnitSphere * (dist * Mathf.Tan(deg * Mathf.Deg2Rad));
        }

        public static bool IsVehicle(Health h) => h.cls == UnitClass.Ground || h.cls == UnitClass.Mech;
    }
}
