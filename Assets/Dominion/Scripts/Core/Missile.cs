using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Guided rocket (Thunderhead missile pods, soldiers' rifle grenades): boosts out of the tube, then steers toward
    /// the aim point (or a tracked unit) and detonates on contact or next to it: fireball, dust ring, a radial blast
    /// that shoves vehicles and, in War mode, direct + splash damage.
    /// </summary>
    public class Missile : MonoBehaviour
    {
        static readonly List<Missile> pool = new List<Missile>();
        static Mesh cube;
        Vector3 vel, target;
        float age, speed, maxSpeed, blastScale, accel = 160f, turn = 2.2f;
        Transform owner;
        Health homing;
        Emitter trail;
        WeaponStats weapon;
        Health attacker;
        readonly RaycastHit[] hits = new RaycastHit[8];

        public static void Launch(Vector3 pos, Vector3 dir, Vector3 target, Transform owner) =>
            Launch(pos, dir, target, owner, Armory.None, null, null, 1f);

        float modelLen;
        bool useModel;

        /// <param name="inherit">Launch speed carried over from the launcher (an aircraft's airspeed).</param>
        public static void Launch(Vector3 pos, Vector3 dir, Vector3 target, Transform owner, WeaponStats weapon, Health attacker, Health homing, float size, float inherit = 0f)
        {
            Missile m = pool.Find(x => x && !x.gameObject.activeSelf);
            if (m == null)
            {
                if (cube == null)
                {
                    var tmp = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    cube = tmp.GetComponent<MeshFilter>().sharedMesh;
                    Destroy(tmp);
                }
                var go = new GameObject("Missile");
                go.AddComponent<MeshFilter>().sharedMesh = cube;
                var mr = go.AddComponent<MeshRenderer>();
                mr.sharedMaterial = Resources.Load<Material>("Dominion/M_Tracer");
                mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                m = go.AddComponent<Missile>();
                pool.Add(m);
            }
            m.gameObject.SetActive(true);
            var model = size < 0.8f ? ProjectileModel.Grenade : weapon.damage >= 450f ? ProjectileModel.AAM : ProjectileModel.Pod;
            m.useModel = Projectiles.Get(model, out Mesh pm, out Material[] pmats);
            if (m.useModel)
            {
                m.GetComponent<MeshFilter>().sharedMesh = pm;
                var pr = m.GetComponent<MeshRenderer>();
                pr.sharedMaterials = pmats;
                pr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                m.modelLen = Projectiles.LengthOf(model);
            }
            m.transform.localScale = m.useModel ? Vector3.one : new Vector3(0.28f, 0.28f, 1.8f) * size;
            m.transform.position = pos;
            bool aam = model == ProjectileModel.AAM;
            m.speed = Mathf.Max(55f * Mathf.Lerp(0.8f, 1f, size), inherit);
            m.maxSpeed = aam ? Mathf.Max(680f, inherit + 300f) : size < 0.8f ? 150f : 230f;
            m.accel = aam ? 320f : 160f;
            m.turn = aam ? 3.2f : 2.2f;
            m.blastScale = size < 0.8f ? 0.7f : 1.1f;
            m.vel = dir.normalized * m.speed;
            m.target = target;
            m.age = 0f;
            m.owner = owner;
            m.weapon = weapon;
            m.attacker = attacker;
            m.homing = homing;
            m.trail = Vfx.Attach(Vfx.EmitterKind.MissileTrail, m.transform, new Vector3(0f, 0f, m.useModel ? -m.modelLen : -0.6f), Quaternion.identity);
            if (m.trail) m.trail.Rate = 1f;
            Vfx.Muzzle(pos, dir, 0.35f * size);
            m.transform.rotation = Quaternion.LookRotation(dir);
        }

        void Update()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;
            age += dt;
            speed = Mathf.Min(maxSpeed, speed + accel * dt);
            if (homing && homing.Alive) target = homing.Center + homing.Velocity * (Vector3.Distance(transform.position, homing.Center) / Mathf.Max(speed, 1f));
            Vector3 want = (target - transform.position).normalized;
            Vector3 dir = vel.normalized;
            if (age > 0.25f) dir = Vector3.RotateTowards(dir, want, turn * dt, 0f);
            vel = dir * speed;
            Vector3 step = vel * dt;
            int n = Physics.RaycastNonAlloc(transform.position, dir, hits, step.magnitude + 0.9f, ~0, QueryTriggerInteraction.Ignore);
            float best = float.MaxValue;
            int bi = -1;
            for (int i = 0; i < n; i++)
            {
                if (owner && hits[i].collider.transform.IsChildOf(owner)) continue;
                if (hits[i].distance < best) { best = hits[i].distance; bi = i; }
            }
            if (bi >= 0)
            {
                Explode(hits[bi].point, hits[bi].collider);
                return;
            }
            // proximity fuse: burst beside a homing target the missile would otherwise fly past between frames
            if (weapon.proximity > 0f && homing && homing.Alive && age > 0.4f)
            {
                Vector3 hc = homing.Center, p0 = transform.position;
                float k = Mathf.Clamp01(Vector3.Dot(hc - p0, step) / Mathf.Max(step.sqrMagnitude, 1e-4f));
                Vector3 near = p0 + step * k;
                if ((hc - near).sqrMagnitude < weapon.proximity * weapon.proximity)
                {
                    Explode(near, null, homing);
                    return;
                }
            }
            transform.position += step;
            transform.rotation = Quaternion.LookRotation(dir);
            if (age > 7f || (age > 0.5f && Vector3.Distance(transform.position, target) < 2.5f) || transform.position.y < -1f)
                Explode(transform.position, null);
        }

        void Explode(Vector3 p, Collider hitCol, Health fuzed = null)
        {
            if (trail) { trail.Release(5f); trail = null; }
            Vfx.Explosion(p, blastScale, true);
            Effects.Blast(p, 11f * blastScale, 8f * blastScale, 0.7f, owner);
            Team team = attacker ? attacker.team : Team.None;
            Health direct = fuzed ? fuzed : Health.Of(hitCol);
            if (weapon.damage > 0f && direct)
                direct.TakeDamage(new DamageInfo { amount = weapon.damage, type = weapon.type, team = team, point = p, dir = vel, attacker = attacker });
            if (weapon.splash > 0f) Health.Splash(p, weapon.splashRadius, weapon.splash, DamageType.HE, team, attacker, direct);
            gameObject.SetActive(false);
        }
    }
}
