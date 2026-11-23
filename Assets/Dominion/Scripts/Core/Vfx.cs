using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Dominion
{
    /// <summary>What a round does when it lands.</summary>
    public enum ImpactKind { None, Bullet, Autocannon, Shell, Rail }

    /// <summary>
    /// Particle effects built in code and pooled: muzzle blasts, explosions (fireball, smoke plume, sparks,
    /// debris, dust ring, ground + air shockwave rings, cracked / scorched ground decal), bullet impacts, stomps,
    /// melee hits, footstep dust, and continuous emitters (dust trails, exhaust, missile trails, jet smoke, fires).
    /// Scale 1 = a 120 mm tank shell; everything else is sized relative to that.
    /// </summary>
    public static class Vfx
    {
        static Material smoke, fire, spark, ring, dustRing, debris, cracks;
        static Transform root;
        static readonly Dictionary<string, Stack<FxInstance>> pools = new Dictionary<string, Stack<FxInstance>>();
        static readonly List<DecalProjector> decals = new List<DecalProjector>();
        static int decalNext;
        public static readonly Color Dust = new Color(0.66f, 0.58f, 0.47f);
        public static readonly Color SmokeGray = new Color(0.78f, 0.77f, 0.75f);

        static bool Init()
        {
            if (root != null) return smoke != null;
            root = new GameObject("VFX").transform;
            Object.DontDestroyOnLoad(root.gameObject);
            smoke = Resources.Load<Material>("Dominion/VFX/M_FX_Smoke");
            fire = Resources.Load<Material>("Dominion/VFX/M_FX_Fire");
            spark = Resources.Load<Material>("Dominion/VFX/M_FX_Spark");
            ring = Resources.Load<Material>("Dominion/VFX/M_FX_Ring");
            dustRing = Resources.Load<Material>("Dominion/VFX/M_FX_DustRing");
            debris = Resources.Load<Material>("Dominion/VFX/M_FX_Debris");
            cracks = Resources.Load<Material>("Dominion/VFX/M_FX_Cracks");
            if (smoke == null) Debug.LogWarning("[Vfx] materials missing from Resources/Dominion/VFX");
            return smoke != null;
        }

        // ================================================================ public one-shot effects
        public static void Muzzle(Vector3 pos, Vector3 dir, float s)
        {
            if (!Init() || dir.sqrMagnitude < 1e-6f) return;
            Spawn("muzzle", Q(s), pos, Quaternion.LookRotation(dir), BuildMuzzle);
            if (s >= 0.7f && Physics.Raycast(pos, Vector3.down, out var hit, 4.5f, ~0, QueryTriggerInteraction.Ignore) && hit.rigidbody == null)
                Spawn("blastdust", Q(s), hit.point, Quaternion.identity, BuildBlastDust);   // muzzle blast kicks up the ground
        }

        static Transform camT;

        /// <summary>Too far from the camera to be seen: skip the effect.</summary>
        static bool Unseen(Vector3 pos, float range)
        {
            if (camT == null) { var c = Camera.main; if (c == null) return false; camT = c.transform; }
            return (pos - camT.position).sqrMagnitude > range * range;
        }

        public static void Explosion(Vector3 pos, float s, bool scorch)
        {
            if (!Init() || Unseen(pos, 1600f)) return;
            bool ground = Physics.Raycast(pos + Vector3.up * 1.5f, Vector3.down, out var hit, 2.5f + s, ~0, QueryTriggerInteraction.Ignore);
            Spawn("explosion", Q(s), pos, Quaternion.identity, BuildExplosion);
            if (ground)
            {
                Spawn("groundshock", Q(s), hit.point + Vector3.up * 0.05f, Quaternion.identity, BuildGroundShock);
                if (scorch) Cracks(hit.point, 2.5f + 3.2f * s, 30f);
            }
            Shake(pos, 0.5f * s, 60f * Mathf.Max(0.5f, s));
        }

        public static void Impact(ImpactKind kind, float s, Vector3 pos, Vector3 normal, bool metal)
        {
            switch (kind)
            {
                case ImpactKind.Bullet: SmallImpact(pos, normal, metal, s); break;
                case ImpactKind.Autocannon:
                    SmallImpact(pos, normal, metal, s * 1.6f);
                    Explosion(pos + normal * 0.2f, 0.22f * s, false);
                    break;
                case ImpactKind.Shell: Explosion(pos + normal * 0.3f, s, true); break;
                case ImpactKind.Rail:
                    Explosion(pos + normal * 0.3f, s, true);
                    Spawn("airshock", Q(s * 1.6f), pos, Quaternion.identity, BuildAirShock);
                    break;
            }
        }

        public static void SmallImpact(Vector3 pos, Vector3 normal, bool metal, float s = 1f)
        {
            if (!Init() || Unseen(pos, 700f * Mathf.Clamp(s, 0.5f, 2f))) return;
            Spawn(metal ? "hitmetal" : "hitground", Q(s), pos, Quaternion.LookRotation(normal.sqrMagnitude > 0 ? normal : Vector3.up),
                metal ? (System.Func<float, GameObject>)BuildHitMetal : BuildHitGround);
        }

        /// <summary>Mech stomp: shockwave ring racing across the ground, dust wall, debris, cracked ground.</summary>
        public static void Stomp(Vector3 pos, float radius)
        {
            if (!Init()) return;
            float s = radius / 16f;
            Spawn("stomp", Q(s), pos, Quaternion.identity, BuildStomp);
            Cracks(pos, radius * 0.5f, 40f);
            Shake(pos, 0.8f, radius * 5f);
        }

        public static void MeleeImpact(Vector3 pos, float s)
        {
            if (!Init()) return;
            Spawn("melee", Q(s), pos, Quaternion.identity, BuildMelee);
        }

        /// <summary>Footsteps, landings: a low puff of dust.</summary>
        public static void DustPuff(Vector3 pos, float s)
        {
            if (!Init()) return;
            Spawn("puff", Q(s), pos, Quaternion.identity, BuildPuff);
        }

        /// <summary>Cracked, scorched ground decal (fades out after 'life' seconds).</summary>
        public static void Cracks(Vector3 pos, float size, float life)
        {
            if (!Init() || cracks == null) return;
            DecalProjector dp;
            if (decals.Count < 32)
            {
                var go = new GameObject("Cracks");
                go.SetActive(false);                       // material first, then enable (no null-material warning)
                go.transform.SetParent(root, false);
                dp = go.AddComponent<DecalProjector>();
                dp.material = cracks;
                go.AddComponent<DecalFade>();
                decals.Add(dp);
            }
            else
            {
                dp = decals[decalNext];
                decalNext = (decalNext + 1) % decals.Count;
            }
            dp.transform.SetPositionAndRotation(pos + Vector3.up * 0.5f, Quaternion.Euler(90f, Random.Range(0f, 360f), 0f));
            dp.size = new Vector3(size, size, 2.5f);
            dp.pivot = Vector3.zero;
            dp.GetComponent<DecalFade>().Begin(life);
            dp.gameObject.SetActive(true);
        }

        static void Shake(Vector3 pos, float amount, float range)
        {
            if (CameraRig.Main == null) return;
            float d = Vector3.Distance(CameraRig.Main.transform.position, pos);
            CameraRig.Main.Shake(amount * Mathf.Clamp01(1f - d / range));
        }

        // ================================================================ continuous emitters
        public enum EmitterKind { DustTrail, Exhaust, MissileTrail, JetSmoke, Burning, PropSmoke }

        /// <summary>Attach a looping emitter; drive it with Emitter.Rate (0..1 of its full rate).</summary>
        public static Emitter Attach(EmitterKind kind, Transform parent, Vector3 localPos, Quaternion localRot)
        {
            if (!Init()) return null;
            var go = new GameObject("Emitter_" + kind);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = localRot;
            switch (kind)
            {
                case EmitterKind.DustTrail:
                {
                    var p = Sys(go.transform, smoke, 300, true);
                    Life(p, 1.6f, 3.2f); Size(p, 1.2f, 2.2f); Speed(p, 0.3f, 1.2f); Rot(p);
                    Col(p, Grad(Dust, 0f, 0.38f, 0.18f, 0f)); Grow(p, 1f, 2.6f); Drag(p, 1.2f); Rise(p, 0.35f); Noise(p, 0.4f, 0.4f); Sheet(p);
                    Shape(p, ParticleSystemShapeType.Sphere, 0.5f);
                    Rate(p, 30f);
                    break;
                }
                case EmitterKind.Exhaust:
                {
                    var p = Sys(go.transform, smoke, 200, true);
                    // diesel exhaust: a thin grey haze, thickening a little under throttle (not a burning-vehicle plume)
                    Life(p, 1.0f, 2.2f); Size(p, 0.35f, 0.6f); Speed(p, 1.5f, 3f); Rot(p);
                    Col(p, Grad(new Color(0.52f, 0.51f, 0.5f), 0f, 0.26f, 0.1f, 0f)); Grow(p, 1f, 5f); Drag(p, 1.5f); Rise(p, 0.9f); Noise(p, 0.6f, 0.6f); Sheet(p);
                    Shape(p, ParticleSystemShapeType.Cone, 0.08f, 14f);
                    Rate(p, 16f);
                    break;
                }
                case EmitterKind.MissileTrail:
                {
                    var p = Sys(go.transform, smoke, 400, true);
                    Life(p, 1.6f, 3.2f); Size(p, 0.45f, 0.75f); Speed(p, 0.2f, 0.8f); Rot(p);
                    Col(p, Grad(SmokeGray, 0.1f, 0.7f, 0.35f, 0f)); Grow(p, 1f, 4.5f); Drag(p, 1f); Rise(p, 0.3f); Noise(p, 0.5f, 0.5f); Sheet(p);
                    Shape(p, ParticleSystemShapeType.Sphere, 0.1f);
                    var em = p.emission; em.rateOverTime = 0f; em.rateOverDistance = 5f;
                    var f = Sys(go.transform, fire, 100, true);
                    Life(f, 0.06f, 0.12f); Size(f, 0.7f, 1.1f); Col(f, Grad(new Color(1f, 0.8f, 0.5f), 1f, 1f, 0.6f, 0f)); Bright(f, 4f);
                    var ef = f.emission; ef.rateOverTime = 0f; ef.rateOverDistance = 8f;
                    break;
                }
                case EmitterKind.JetSmoke:
                {
                    var p = Sys(go.transform, smoke, 300, true);
                    Life(p, 0.7f, 1.5f); Size(p, 0.9f, 1.4f); Speed(p, 8f, 14f); Rot(p);
                    Col(p, Grad(new Color(0.72f, 0.71f, 0.7f), 0.15f, 0.5f, 0.2f, 0f)); Grow(p, 1f, 3.5f); Drag(p, 2.2f); Noise(p, 0.6f, 0.5f); Sheet(p);
                    Shape(p, ParticleSystemShapeType.Cone, 0.25f, 10f);
                    Rate(p, 45f);
                    var f = Sys(go.transform, fire, 120, true);
                    Life(f, 0.08f, 0.16f); Size(f, 1.0f, 1.6f); Speed(f, 10f, 16f); Col(f, Grad(new Color(0.9f, 0.85f, 1f), 1f, 1f, 0.5f, 0f)); Bright(f, 4f); Sheet(f);
                    Shape(f, ParticleSystemShapeType.Cone, 0.15f, 6f);
                    Rate(f, 60f);
                    break;
                }
                case EmitterKind.PropSmoke:
                {
                    var p = Sys(go.transform, smoke, 120, true);
                    Life(p, 0.8f, 1.6f); Size(p, 0.25f, 0.45f); Speed(p, 0.5f, 1.5f); Rot(p);
                    Col(p, Grad(new Color(0.45f, 0.44f, 0.43f), 0f, 0.35f, 0.15f, 0f)); Grow(p, 1f, 3f); Drag(p, 1f); Sheet(p);
                    Shape(p, ParticleSystemShapeType.Sphere, 0.2f);
                    Rate(p, 18f);
                    break;
                }
                case EmitterKind.Burning:
                {
                    var p = Sys(go.transform, smoke, 300, true);
                    Life(p, 4f, 7f); Size(p, 2f, 3.2f); Speed(p, 0.5f, 1.5f); Rot(p);
                    Col(p, Grad(new Color(0.16f, 0.15f, 0.14f), 0.2f, 0.8f, 0.45f, 0f)); Grow(p, 1f, 3.5f); Rise(p, 3.5f); Noise(p, 0.8f, 0.3f); Sheet(p);
                    Shape(p, ParticleSystemShapeType.Sphere, 1.2f);
                    Rate(p, 14f);
                    var f = Sys(go.transform, fire, 200, true);
                    Life(f, 0.4f, 0.9f); Size(f, 1.4f, 2.6f); Rise(f, 2.2f); Col(f, Grad(new Color(1f, 0.7f, 0.35f), 0.9f, 1f, 0.6f, 0f)); Bright(f, 3.5f); Sheet(f); Rot(f);
                    Shape(f, ParticleSystemShapeType.Sphere, 1f);
                    Rate(f, 20f);
                    break;
                }
            }
            var e = go.AddComponent<Emitter>();
            e.Collect();
            e.Rate = 0f;
            return e;
        }

        // ================================================================ recipes
        static GameObject BuildMuzzle(float s)
        {
            var go = Root("Muzzle");
            var flash = Sys(go.transform, fire, 8, false);
            Burst(flash, 3); Life(flash, 0.06f, 0.1f); Size(flash, 1.1f * s, 2.0f * s); Speed(flash, 1f * s, 4f * s); Bright(flash, 5f); Sheet(flash); Rot(flash);
            Shape(flash, ParticleSystemShapeType.Cone, 0.05f, 8f);
            Col(flash, Grad(new Color(1f, 0.85f, 0.6f), 1f, 1f, 0.5f, 0f));
            var sm = Sys(go.transform, smoke, 80, false);
            bool small = s < 0.5f;     // MGs / autocannons: a quick grey wisp, not big round puffs
            Burst(sm, small ? 3 : Mathf.RoundToInt(6 + 12 * s)); Life(sm, 0.8f * (0.5f + 0.5f * s), 2.4f * (0.5f + 0.5f * s));
            Size(sm, (small ? 0.7f : 0.45f) * s, (small ? 1.2f : 0.9f) * s); Speed(sm, 4f * Mathf.Sqrt(s), 13f * Mathf.Sqrt(s)); Rot(sm);
            Col(sm, Grad(SmokeGray, small ? 0.25f : 0.6f, small ? 0.25f : 0.6f, small ? 0.1f : 0.3f, 0f)); Grow(sm, 1f, small ? 5f : 3.5f);
            Drag(sm, 3f); Rise(sm, 0.4f); Noise(sm, small ? 0.8f : 0.4f, 0.6f); Sheet(sm);
            Shape(sm, ParticleSystemShapeType.Cone, 0.08f * s, 13f);
            if (s >= 0.7f)
            {
                var ball = Sys(go.transform, fire, 12, false);      // propellant gases igniting in the air ahead of the muzzle
                Burst(ball, 5); Life(ball, 0.08f, 0.16f); Size(ball, 1.3f * s, 2.6f * s); Speed(ball, 6f * s, 22f * s); Rot(ball); Sheet(ball);
                Grow(ball, 0.7f, 1.9f); Drag(ball, 6f);
                Col(ball, Grad3(new Color(1f, 0.92f, 0.7f), new Color(1f, 0.55f, 0.2f), new Color(0.4f, 0.14f, 0.05f)));
                Shape(ball, ParticleSystemShapeType.Cone, 0.1f * s, 10f);
                var em = Sys(go.transform, spark, 40, false);       // burning propellant grains
                Burst(em, Mathf.RoundToInt(10 + 10 * s)); Life(em, 0.15f, 0.5f); Size(em, 0.05f, 0.12f); Speed(em, 25f, 60f);
                Col(em, Grad(new Color(1f, 0.7f, 0.35f), 1f, 1f, 0.6f, 0f)); Gravity(em, 0.5f); Stretch(em, 0.02f);
                Shape(em, ParticleSystemShapeType.Cone, 0.1f * s, 7f);
                var side = Sys(go.transform, smoke, 30, false);    // muzzle-brake side jets
                Burst(side, 10); Life(side, 0.8f, 1.8f); Size(side, 0.6f * s, 1.0f * s); Speed(side, 5f, 9f); Rot(side);
                Col(side, Grad(SmokeGray, 0.55f, 0.55f, 0.25f, 0f)); Grow(side, 1f, 3f); Drag(side, 3f); Sheet(side);
                Shape(side, ParticleSystemShapeType.Circle, 0.15f);
            }
            return go;
        }

        static GameObject BuildBlastDust(float s)
        {
            var go = Root("BlastDust");
            var d = Sys(go.transform, smoke, 40, false);
            Burst(d, Mathf.RoundToInt(10 + 8 * s)); Life(d, 1.2f, 2.6f); Size(d, 1.4f * s, 2.4f * s); Speed(d, 4f * s, 9f * s); Rot(d);
            Col(d, Grad(Dust, 0f, 0.55f, 0.25f, 0f)); Grow(d, 1f, 2.4f); Drag(d, 2.5f); Rise(d, 0.3f); Sheet(d);
            Shape(d, ParticleSystemShapeType.Circle, 0.8f * s, 0f, new Vector3(-90f, 0f, 0f));
            return go;
        }

        static GameObject BuildExplosion(float s)
        {
            var go = Root("Explosion");
            float r = Mathf.Sqrt(s);
            var flash = Sys(go.transform, fire, 4, false);
            Burst(flash, 1); Life(flash, 0.09f, 0.12f); Size(flash, 7f * s, 7f * s); Bright(flash, 6f); Grow(flash, 0.6f, 1f);
            Col(flash, Grad(new Color(1f, 0.95f, 0.85f), 1f, 1f, 0.8f, 0f));
            var fb = Sys(go.transform, fire, 40, false);
            Burst(fb, Mathf.RoundToInt(8 + 8 * s)); Life(fb, 0.35f * (0.7f + 0.3f * s), 0.8f * (0.7f + 0.3f * s));
            Size(fb, 2.2f * s, 3.8f * s); Speed(fb, 1.5f * s, 6f * s); Rot(fb); Sheet(fb); Grow(fb, 1f, 1.9f); Drag(fb, 3f); Bright(fb, 4f);
            Col(fb, Grad3(new Color(1f, 0.92f, 0.7f), new Color(1f, 0.5f, 0.15f), new Color(0.35f, 0.1f, 0.03f)));
            Shape(fb, ParticleSystemShapeType.Sphere, 0.5f * s);
            var sm = Sys(go.transform, smoke, 80, false);
            Burst(sm, Mathf.RoundToInt(12 + 10 * s)); Life(sm, 3f * (0.6f + 0.4f * s), 7f * (0.6f + 0.4f * s));
            Size(sm, 2.2f * s, 4.2f * s); Speed(sm, 1f * s, 4.5f * s); Rot(sm); Sheet(sm); Grow(sm, 1f, 3.2f); Drag(sm, 1.6f);
            Rise(sm, 1.6f * r); Noise(sm, 0.7f * r, 0.25f);
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(new Color(0.35f, 0.22f, 0.14f), 0f), new GradientColorKey(new Color(0.24f, 0.23f, 0.22f), 0.12f),
                              new GradientColorKey(new Color(0.42f, 0.41f, 0.4f), 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.85f, 0.07f), new GradientAlphaKey(0.5f, 0.5f), new GradientAlphaKey(0f, 1f) });
            var col = sm.colorOverLifetime; col.enabled = true; col.color = new ParticleSystem.MinMaxGradient(g);
            Shape(sm, ParticleSystemShapeType.Sphere, 0.9f * s);
            var sp = Sys(go.transform, spark, 120, false);
            Burst(sp, Mathf.RoundToInt(20 + 25 * s)); Life(sp, 0.3f, 1.1f); Size(sp, 0.1f, 0.22f); Speed(sp, 12f * r, 34f * r); Bright(sp, 7f);
            Col(sp, Grad(new Color(1f, 0.75f, 0.4f), 1f, 1f, 0.7f, 0f)); Gravity(sp, 0.8f); Collide(sp);
            Stretch(sp, 0.035f);
            Shape(sp, ParticleSystemShapeType.Hemisphere, 0.3f * s, 0f, new Vector3(-90f, 0f, 0f));
            var db = Sys(go.transform, debris, 60, false);
            Burst(db, Mathf.RoundToInt(10 + 12 * s)); Life(db, 1.2f, 2.8f); Size(db, 0.2f * r, 0.6f * r); Speed(db, 7f * r, 20f * r); Gravity(db, 1f);
            Collide(db); Sheet(db, false); var dr = db.rotationOverLifetime; dr.enabled = true; dr.z = new ParticleSystem.MinMaxCurve(-8f, 8f);
            Col(db, Grad(Color.white, 1f, 1f, 1f, 0f));
            Shape(db, ParticleSystemShapeType.Hemisphere, 0.3f * s, 0f, new Vector3(-90f, 0f, 0f));
            return go;
        }

        static GameObject BuildGroundShock(float s)
        {
            var go = Root("GroundShock");
            var ringP = Sys(go.transform, dustRing, 2, false);
            Burst(ringP, 1); Life(ringP, 0.55f + 0.2f * s, 0.55f + 0.2f * s); Size(ringP, 16f * s + 4f, 16f * s + 4f);
            Grow(ringP, 0.08f, 1f, true); Col(ringP, Grad(Color.white, 0.95f, 0.8f, 0.4f, 0f)); Horizontal(ringP);
            var d = Sys(go.transform, smoke, 60, false);
            Burst(d, Mathf.RoundToInt(16 + 12 * s)); Life(d, 1.4f, 3.2f); Size(d, 1.6f * s + 0.6f, 3f * s + 0.8f); Speed(d, 6f * s + 2f, 13f * s + 3f);
            Rot(d); Sheet(d); Col(d, Grad(Dust, 0f, 0.6f, 0.3f, 0f)); Grow(d, 1f, 2.4f); Drag(d, 2.5f); Rise(d, 0.4f);
            Shape(d, ParticleSystemShapeType.Circle, 0.6f * s, 0f, new Vector3(-90f, 0f, 0f));
            return go;
        }

        static GameObject BuildAirShock(float s)
        {
            var go = Root("AirShock");
            var p = Sys(go.transform, ring, 2, false);
            Burst(p, 1); Life(p, 0.22f, 0.22f); Size(p, 12f * s, 12f * s); Grow(p, 0.05f, 1f, true); Bright(p, 2.5f);
            Col(p, Grad(new Color(1f, 0.95f, 0.85f), 1f, 0.8f, 0.3f, 0f));
            return go;
        }

        static GameObject BuildHitGround(float s)
        {
            var go = Root("HitGround");
            var d = Sys(go.transform, smoke, 12, false);
            Burst(d, 4); Life(d, 0.6f, 1.4f); Size(d, 0.35f * s, 0.7f * s); Speed(d, 1.5f * s, 4.5f * s); Rot(d); Sheet(d);
            Col(d, Grad(Dust, 0f, 0.7f, 0.3f, 0f)); Grow(d, 1f, 2.6f); Drag(d, 3f);
            Shape(d, ParticleSystemShapeType.Cone, 0.05f, 30f);
            var sp = Sys(go.transform, spark, 12, false);
            Burst(sp, 5); Life(sp, 0.15f, 0.4f); Size(sp, 0.05f, 0.1f); Speed(sp, 5f, 14f); Bright(sp, 5f); Gravity(sp, 0.6f); Stretch(sp, 0.03f);
            Col(sp, Grad(new Color(1f, 0.8f, 0.5f), 1f, 1f, 0.5f, 0f));
            Shape(sp, ParticleSystemShapeType.Cone, 0.02f, 35f);
            return go;
        }

        static GameObject BuildHitMetal(float s)
        {
            var go = Root("HitMetal");
            var sp = Sys(go.transform, spark, 30, false);
            Burst(sp, Mathf.RoundToInt(10 + 6 * s)); Life(sp, 0.2f, 0.6f); Size(sp, 0.06f * s, 0.14f * s); Speed(sp, 8f, 22f); Bright(sp, 7f);
            Gravity(sp, 0.7f); Stretch(sp, 0.03f); Collide(sp); Col(sp, Grad(new Color(1f, 0.85f, 0.55f), 1f, 1f, 0.6f, 0f));
            Shape(sp, ParticleSystemShapeType.Cone, 0.02f, 45f);
            var fl = Sys(go.transform, fire, 2, false);
            Burst(fl, 1); Life(fl, 0.05f, 0.07f); Size(fl, 0.6f * s, 0.9f * s); Bright(fl, 5f); Sheet(fl);
            var d = Sys(go.transform, smoke, 6, false);
            Burst(d, 2); Life(d, 0.6f, 1.2f); Size(d, 0.3f * s, 0.5f * s); Speed(d, 0.5f, 2f); Rot(d); Sheet(d);
            Col(d, Grad(new Color(0.4f, 0.4f, 0.4f), 0f, 0.5f, 0.2f, 0f)); Grow(d, 1f, 3f);
            return go;
        }

        static GameObject BuildStomp(float s)
        {
            var go = Root("Stomp");
            var ringP = Sys(go.transform, dustRing, 2, false);
            Burst(ringP, 1); Life(ringP, 0.75f, 0.75f); Size(ringP, 34f * s, 34f * s); Grow(ringP, 0.06f, 1f, true);
            Col(ringP, Grad(Color.white, 1f, 0.85f, 0.4f, 0f)); Horizontal(ringP);
            var ringA = Sys(go.transform, ring, 2, false);          // air shock low over the ground
            Burst(ringA, 1); Life(ringA, 0.3f, 0.3f); Size(ringA, 18f * s, 18f * s); Grow(ringA, 0.1f, 1f, true); Bright(ringA, 1.6f);
            Col(ringA, Grad(new Color(1f, 0.95f, 0.85f), 0.8f, 0.6f, 0.2f, 0f)); Horizontal(ringA);
            var wall = Sys(go.transform, smoke, 80, false);         // dust wall rolling outward
            Burst(wall, Mathf.RoundToInt(36 * s + 10)); Life(wall, 1.4f, 3f); Size(wall, 2.2f * s, 4f * s); Speed(wall, 10f * s, 20f * s); Rot(wall); Sheet(wall);
            Col(wall, Grad(Dust, 0f, 0.65f, 0.3f, 0f)); Grow(wall, 1f, 2.2f); Drag(wall, 3f); Rise(wall, 0.6f); Noise(wall, 0.5f, 0.4f);
            Shape(wall, ParticleSystemShapeType.Circle, 1.5f, 0f, new Vector3(-90f, 0f, 0f));
            var db = Sys(go.transform, debris, 40, false);          // chunks of concrete hop out of the impact
            Burst(db, 18); Life(db, 1f, 2f); Size(db, 0.25f, 0.55f); Speed(db, 5f, 12f); Gravity(db, 1f); Collide(db); Sheet(db, false);
            var dr = db.rotationOverLifetime; dr.enabled = true; dr.z = new ParticleSystem.MinMaxCurve(-8f, 8f);
            Shape(db, ParticleSystemShapeType.Hemisphere, 1.2f, 0f, new Vector3(-90f, 0f, 0f));
            return go;
        }

        static GameObject BuildMelee(float s)
        {
            var go = Root("Melee");
            var sp = Sys(go.transform, spark, 60, false);
            Burst(sp, 35); Life(sp, 0.25f, 0.8f); Size(sp, 0.1f * s, 0.2f * s); Speed(sp, 8f * s, 22f * s); Bright(sp, 7f);
            Gravity(sp, 0.6f); Stretch(sp, 0.035f); Collide(sp); Col(sp, Grad(new Color(1f, 0.85f, 0.55f), 1f, 1f, 0.6f, 0f));
            Shape(sp, ParticleSystemShapeType.Sphere, 0.5f);
            var fl = Sys(go.transform, fire, 3, false);
            Burst(fl, 1); Life(fl, 0.07f, 0.09f); Size(fl, 3f * s, 3f * s); Bright(fl, 4f); Sheet(fl);
            var d = Sys(go.transform, smoke, 20, false);
            Burst(d, 8); Life(d, 0.8f, 1.8f); Size(d, 1f * s, 1.8f * s); Speed(d, 2f, 6f); Rot(d); Sheet(d);
            Col(d, Grad(new Color(0.55f, 0.52f, 0.48f), 0f, 0.55f, 0.25f, 0f)); Grow(d, 1f, 2.5f); Drag(d, 2.5f);
            Shape(d, ParticleSystemShapeType.Sphere, 0.8f);
            return go;
        }

        static GameObject BuildPuff(float s)
        {
            var go = Root("Puff");
            var d = Sys(go.transform, smoke, 20, false);
            Burst(d, Mathf.RoundToInt(5 + 4 * s)); Life(d, 0.9f, 2f); Size(d, 0.7f * s, 1.4f * s); Speed(d, 1.5f * s, 4f * s); Rot(d); Sheet(d);
            Col(d, Grad(Dust, 0f, 0.5f, 0.22f, 0f)); Grow(d, 1f, 2.2f); Drag(d, 2.5f); Rise(d, 0.25f);
            Shape(d, ParticleSystemShapeType.Circle, 0.4f * s, 0f, new Vector3(-90f, 0f, 0f));
            return go;
        }

        // ================================================================ pooling
        static float Q(float s) => Mathf.Max(0.05f, Mathf.Round(s * 8f) / 8f);

        static void Spawn(string kind, float s, Vector3 pos, Quaternion rot, System.Func<float, GameObject> build)
        {
            string key = kind + ":" + s.ToString("0.000");
            if (!pools.TryGetValue(key, out var stack)) pools[key] = stack = new Stack<FxInstance>();
            FxInstance fx = null;
            while (stack.Count > 0 && fx == null) fx = stack.Pop();
            if (fx == null)
            {
                var go = build(s);
                go.transform.SetParent(root, false);
                fx = go.AddComponent<FxInstance>();
                fx.Init(stack);
            }
            fx.transform.SetPositionAndRotation(pos, rot);
            fx.Play();
        }

        // ================================================================ particle helpers
        static GameObject Root(string name) => new GameObject("FX_" + name);

        static ParticleSystem Sys(Transform parent, Material mat, int max, bool loop)
        {
            var go = new GameObject("ps");
            go.transform.SetParent(parent, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var m = ps.main;
            m.playOnAwake = false;
            m.loop = loop;
            m.duration = loop ? 1f : 0.5f;
            m.simulationSpace = ParticleSystemSimulationSpace.World;
            m.scalingMode = ParticleSystemScalingMode.Local;
            m.maxParticles = max;
            m.startSpeed = 0f;
            m.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            var em = ps.emission;
            em.rateOverTime = 0f;
            var sh = ps.shape;
            sh.enabled = false;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            r.sortMode = ParticleSystemSortMode.Distance;
            r.maxParticleSize = 5f;
            return ps;
        }

        static void Burst(ParticleSystem p, int n) { var em = p.emission; em.SetBursts(new[] { new ParticleSystem.Burst(0f, (short)Mathf.Max(1, n)) }); }
        static void Rate(ParticleSystem p, float r) { var em = p.emission; em.rateOverTime = r; }
        static void Life(ParticleSystem p, float a, float b) { var m = p.main; m.startLifetime = new ParticleSystem.MinMaxCurve(a, b); }
        static void Size(ParticleSystem p, float a, float b) { var m = p.main; m.startSize = new ParticleSystem.MinMaxCurve(a, b); }
        static void Speed(ParticleSystem p, float a, float b) { var m = p.main; m.startSpeed = new ParticleSystem.MinMaxCurve(a, b); }
        static void Gravity(ParticleSystem p, float g) { var m = p.main; m.gravityModifier = g; }
        // HDR intensity lives on the shared fire / spark / ring materials (vertex colours cap at 1); kept for readability
        static void Bright(ParticleSystem p, float b) { }
        static void Rot(ParticleSystem p) { var ro = p.rotationOverLifetime; ro.enabled = true; ro.z = new ParticleSystem.MinMaxCurve(-0.6f, 0.6f); }

        static void Shape(ParticleSystem p, ParticleSystemShapeType t, float radius, float angle = 25f, Vector3? rot = null)
        {
            var sh = p.shape;
            sh.enabled = true;
            sh.shapeType = t;
            sh.radius = Mathf.Max(0.001f, radius);
            sh.angle = angle;
            if (t == ParticleSystemShapeType.Circle) sh.radiusThickness = 1f;
            if (rot.HasValue) sh.rotation = rot.Value;
        }

        static void Col(ParticleSystem p, Gradient g) { var c = p.colorOverLifetime; c.enabled = true; c.color = new ParticleSystem.MinMaxGradient(g); }

        static void Grow(ParticleSystem p, float from, float to, bool fastOut = false)
        {
            var sz = p.sizeOverLifetime;
            sz.enabled = true;
            // ease-out growth (fast at first, settling); fastOut makes shock rings burst outward even harder
            float slope = (to - from) * (fastOut ? 4f : 2.2f);
            var curve = new AnimationCurve(new Keyframe(0f, from, 0f, slope), new Keyframe(1f, to, 0f, 0f));
            sz.size = new ParticleSystem.MinMaxCurve(1f, curve);
        }

        static void Drag(ParticleSystem p, float d)
        {
            var lv = p.limitVelocityOverLifetime;
            lv.enabled = true;
            lv.limit = 1000f;
            lv.dampen = 0f;
            lv.drag = d;
            lv.multiplyDragByParticleSize = false;
            lv.multiplyDragByParticleVelocity = false;
        }

        static void Rise(ParticleSystem p, float up)
        {
            var v = p.velocityOverLifetime;
            v.enabled = true;
            v.space = ParticleSystemSimulationSpace.World;
            v.x = new ParticleSystem.MinMaxCurve(0f);
            v.y = new ParticleSystem.MinMaxCurve(up);
            v.z = new ParticleSystem.MinMaxCurve(0f);
        }

        static void Noise(ParticleSystem p, float strength, float freq)
        {
            var n = p.noise;
            n.enabled = true;
            n.strength = strength;
            n.frequency = freq;
            n.scrollSpeed = 0.25f;
            n.quality = ParticleSystemNoiseQuality.Low;
        }

        static void Sheet(ParticleSystem p, bool grid2x2 = true)
        {
            if (!grid2x2) return;
            var t = p.textureSheetAnimation;
            t.enabled = true;
            t.mode = ParticleSystemAnimationMode.Grid;
            t.numTilesX = 2;
            t.numTilesY = 2;
            t.animation = ParticleSystemAnimationType.WholeSheet;
            t.frameOverTime = new ParticleSystem.MinMaxCurve(0f);
            t.startFrame = new ParticleSystem.MinMaxCurve(0f, 3.99f);
        }

        static void Collide(ParticleSystem p)
        {
            var c = p.collision;
            c.enabled = true;
            c.type = ParticleSystemCollisionType.World;
            c.mode = ParticleSystemCollisionMode.Collision3D;
            c.dampen = 0.45f;
            c.bounce = 0.3f;
            c.lifetimeLoss = 0.05f;
            c.quality = ParticleSystemCollisionQuality.Medium;
        }

        static void Stretch(ParticleSystem p, float velocityScale)
        {
            var r = p.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Stretch;
            r.velocityScale = velocityScale;
            r.lengthScale = 1f;
        }

        static void Horizontal(ParticleSystem p)
        {
            var r = p.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.HorizontalBillboard;
            r.maxParticleSize = 50f;
            var m = p.main;
            m.startRotation = 0f;
        }

        /// <summary>Colour fixed, alpha: start -> peak (early) -> mid -> end.</summary>
        static Gradient Grad(Color c, float a0, float aPeak, float aMid, float aEnd)
        {
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(c, 0f), new GradientColorKey(c, 1f) },
                      new[] { new GradientAlphaKey(a0, 0f), new GradientAlphaKey(aPeak, 0.08f), new GradientAlphaKey(aMid, 0.5f), new GradientAlphaKey(aEnd, 1f) });
            return g;
        }

        static Gradient Grad3(Color a, Color b, Color c)
        {
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(a, 0f), new GradientColorKey(b, 0.35f), new GradientColorKey(c, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0.9f, 0.4f), new GradientAlphaKey(0f, 1f) });
            return g;
        }
    }

    /// <summary>A pooled one-shot effect: plays all child systems, returns itself to the pool when they finish.</summary>
    public class FxInstance : MonoBehaviour
    {
        ParticleSystem[] systems;
        Stack<FxInstance> home;
        float check;

        public void Init(Stack<FxInstance> pool)
        {
            home = pool;
            systems = GetComponentsInChildren<ParticleSystem>(true);
        }

        public void Play()
        {
            gameObject.SetActive(true);
            foreach (var s in systems)
            {
                s.Clear(true);
                s.Play(false);
            }
            check = 0.5f;
        }

        void Update()
        {
            check -= Time.deltaTime;
            if (check > 0f) return;
            check = 0.5f;
            foreach (var s in systems)
                if (s.IsAlive(false)) return;
            gameObject.SetActive(false);
            home.Push(this);
        }
    }

    /// <summary>Looping attached emitter; Rate (0..1) scales every child system's base emission.</summary>
    public class Emitter : MonoBehaviour
    {
        ParticleSystem[] systems;
        float[] baseTime, baseDist;
        float rate = -1f;
        bool playing = true;

        public void Collect()
        {
            systems = GetComponentsInChildren<ParticleSystem>(true);
            baseTime = new float[systems.Length];
            baseDist = new float[systems.Length];
            for (int i = 0; i < systems.Length; i++)
            {
                baseTime[i] = systems[i].emission.rateOverTimeMultiplier;
                baseDist[i] = systems[i].emission.rateOverDistanceMultiplier;
                systems[i].Play(false);
            }
        }

        public float Rate
        {
            get => rate;
            set
            {
                value = Mathf.Max(0f, value);
                if (Mathf.Abs(value - rate) < 0.01f) return;
                rate = value;
                for (int i = 0; i < systems.Length; i++)
                {
                    var em = systems[i].emission;
                    em.rateOverTimeMultiplier = baseTime[i] * value;
                    em.rateOverDistanceMultiplier = baseDist[i] * value;
                }
                // an idle emitter costs a particle update every frame: stop it (smoke already out drifts on) and restart on demand
                if (value <= 0f && playing)
                {
                    playing = false;
                    for (int i = 0; i < systems.Length; i++) systems[i].Stop(false, ParticleSystemStopBehavior.StopEmitting);
                }
                else if (value > 0f && !playing)
                {
                    playing = true;
                    for (int i = 0; i < systems.Length; i++) systems[i].Play(false);
                }
            }
        }

        /// <summary>Stop emitting, let the existing smoke drift away, then remove the emitter.</summary>
        public void Release(float after = 6f)
        {
            Rate = 0f;
            transform.SetParent(null, true);
            Destroy(gameObject, after);
        }
    }

    /// <summary>Fades a crack decal out at the end of its life.</summary>
    public class DecalFade : MonoBehaviour
    {
        DecalProjector dp;
        float life, t;

        public void Begin(float seconds)
        {
            dp = GetComponent<DecalProjector>();
            life = seconds;
            t = 0f;
            dp.fadeFactor = 1f;
        }

        void Update()
        {
            t += Time.deltaTime;
            float fadeStart = life - 4f;
            if (t > fadeStart) dp.fadeFactor = Mathf.Clamp01(1f - (t - fadeStart) / 4f);
            if (t >= life) gameObject.SetActive(false);
        }
    }
}
