using System.Collections;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// A soldier jumping from an airship (ParachuteKit canopy): a second of free fall, the canopy blossoms open, then a
    /// ~5 m/s descent steering toward the drop point, swaying under the canopy. Enemies can shoot him on the way down. On
    /// landing the canopy collapses and is left behind, and the soldier's own AI takes over with an assault order. A
    /// landing on a rooftop is moved down to the nearest open ground.
    /// </summary>
    public class Paratrooper : MonoBehaviour
    {
        SoldierController sc;
        SoldierAI ai;
        Health h;
        Transform chute;
        Vector3 target, vel;
        float t, sway;
        bool landed;
        static readonly Vector3 Packed = new Vector3(0.06f, 0.03f, 0.06f);
        const float OpenAt = 1.1f, OpenTime = 1.4f, Sink = 5f;

        public static int Jumped, Landed;
        public static void ResetStats() => Jumped = Landed = 0;
        public bool Descending => !landed;

        public void Init(GameObject parachutePrefab, Vector3 landTarget, Vector3 shipVelocity)
        {
            sc = GetComponent<SoldierController>();
            ai = GetComponent<SoldierAI>();
            h = GetComponent<Health>();
            if (ai) ai.enabled = false;
            if (sc) sc.enabled = false;              // the controller collider stays: he can be shot on the way down
            target = landTarget;
            vel = shipVelocity + AIUtil.Flat(transform.right) * Random.Range(-2f, 2f);
            sway = Random.Range(0f, 10f);
            if (parachutePrefab)
            {
                chute = Instantiate(parachutePrefab, transform).transform;
                chute.localPosition = new Vector3(0f, 1.42f, -0.1f);
                chute.localRotation = Quaternion.identity;
                chute.localScale = Packed;
                if (h) TeamPaint.Apply(chute.gameObject, h.team, false);
            }
            Jumped++;
        }

        void Update()
        {
            if (landed) return;
            float dt = Time.deltaTime;
            t += dt;
            bool alive = h != null && h.Alive;
            float open = alive ? Mathf.Clamp01((t - OpenAt) / OpenTime) : 0f;
            if (!alive && chute) ReleaseChute();
            // falling: free fall, then the canopy brakes the drop to a steady sink
            if (open < 0.05f) vel.y = Mathf.Max(vel.y - 9.81f * dt, -40f);
            else vel.y = Mathf.MoveTowards(vel.y, -Sink, 18f * dt);
            Vector3 flat = AIUtil.Flat(vel);
            if (open > 0.6f)
            {
                Vector3 to = AIUtil.Flat(target - transform.position);
                Vector3 want = to.magnitude > 2f ? to.normalized * Mathf.Min(3.5f, to.magnitude * 0.15f) : Vector3.zero;
                flat = Vector3.MoveTowards(flat, want, 1.2f * dt);
            }
            else flat = Vector3.MoveTowards(flat, Vector3.zero, 0.6f * dt);
            vel = new Vector3(flat.x, vel.y, flat.z);
            Vector3 pos = transform.position;
            // the ground (or a roof) under his boots
            if (AIUtil.Cast(pos + Vector3.up * 0.6f, Vector3.down, 0.6f + Mathf.Abs(vel.y) * dt + 0.05f, transform, out RaycastHit hit) && hit.normal.y > 0.5f)
            {
                Land(hit.point, alive);
                return;
            }
            pos += vel * dt;
            if (pos.y < WorldGround.Height(pos.x, pos.z)) { Land(new Vector3(pos.x, WorldGround.Height(pos.x, pos.z), pos.z), alive); return; }
            transform.position = pos;
            if (alive && flat.sqrMagnitude > 0.05f)
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(flat), dt * 1.5f);
            if (chute)
            {
                float k = open * open * (3f - 2f * open);
                float breathe = 1f + 0.03f * Mathf.Sin(t * 2.1f + sway) * k;
                chute.localScale = Vector3.Lerp(Packed, new Vector3(1f, breathe, 1f), k);
                chute.localRotation = Quaternion.Euler(Mathf.Sin(t * 0.9f + sway) * 6f * k, 0f, Mathf.Sin(t * 0.7f + sway * 1.3f) * 5f * k);
            }
        }

        void Land(Vector3 at, bool alive)
        {
            landed = true;
            // a rooftop landing: climb down to the nearest open ground
            float ground = WorldGround.Height(at.x, at.z);
            if (at.y > ground + 2.5f && CityNav.Active)
            {
                var q = CityNav.NearestFree(new Vector2(at.x, at.z), 0.6f, false, 40f);
                at = new Vector3(q.x, WorldGround.Height(q.x, q.y), q.y);
            }
            transform.position = at + Vector3.up * 0.05f;
            if (chute) ReleaseChute();
            if (!alive) return;
            Landed++;
            if (sc)
            {
                sc.enabled = true;
                sc.Place(transform.position, transform.eulerAngles.y);
            }
            if (ai)
            {
                ai.enabled = true;
                ai.Dismounted(target);
            }
        }

        /// <summary>The canopy collapses and settles where it lands (or drifts off if he was shot).</summary>
        void ReleaseChute()
        {
            var c = chute;
            chute = null;
            if (c == null) return;
            c.SetParent(null, true);
            StartCoroutine(Collapse(c));
        }

        IEnumerator Collapse(Transform c)
        {
            Vector3 s0 = c.localScale;
            Quaternion r0 = c.rotation;
            Quaternion r1 = r0 * Quaternion.Euler(Random.Range(60f, 80f), 0f, Random.Range(-15f, 15f));
            for (float k = 0f; k < 1f && c; k += Time.deltaTime / 2.2f)
            {
                float e = k * k;
                c.localScale = new Vector3(s0.x * (1f + 0.2f * e), s0.y * (1f - 0.9f * e), s0.z * (1f + 0.2f * e));
                c.rotation = Quaternion.Slerp(r0, r1, e);
                c.position += Vector3.down * (Time.deltaTime * 3f * e);
                yield return null;
            }
            if (c) Destroy(c.gameObject, 25f);
        }
    }
}
