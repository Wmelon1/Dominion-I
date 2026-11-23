using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Dominion
{
    public enum ProjectileModel : byte { None, Rifle, MG, Autocannon, TankShell, Artillery, ShipShell, Rail, Grenade, Pod, AAM, CasingSmall, CasingMedium }

    /// <summary>
    /// ProjectileKit models for every round in flight (drawn behind each tracer head, nose first, instanced per model) and
    /// the brass that rifles, machine guns and autocannons eject: casings fly out of the breech, tumble, bounce once and lie
    /// on the ground for a few seconds. Only spawned near the camera, where they can be seen.
    /// </summary>
    public static class Projectiles
    {
        static readonly string[] Names = { null, "Bullet_Rifle", "Bullet_MG", "Shell_Autocannon", "Shell_Tank", "Shell_Artillery", "Shell_Ship",
                                           "Rail_Slug", "Grenade_Rifle", "Missile_Pod", "Missile_AAM", "Casing_Small", "Casing_Medium" };
        /// <summary>Small arms are drawn a little oversize so a round is readable at a glance; shells and missiles are true size.</summary>
        static readonly float[] Scale = { 0f, 3f, 2.2f, 1.6f, 1f, 1f, 1.2f, 1f, 1f, 1f, 1f, 2f, 1.4f };
        static readonly float[] Length = { 0f, 0.023f, 0.058f, 0.17f, 0.95f, 0.7f, 0.42f, 0.55f, 0.36f, 1.3f, 2.9f, 0.045f, 0.17f };
        static Mesh[] meshes;
        static Material[][] mats;
        static bool loaded, failed;
        static readonly List<Matrix4x4>[] batch = new List<Matrix4x4>[Names.Length];

        struct Casing { public Vector3 p, v, spin; public Quaternion r; public float life; public bool rested, big; }
        static readonly List<Casing> casings = new List<Casing>();
        static Transform camT;

        /// <summary>Instances drawn last frame, and casings currently flying or lying about.</summary>
        public static int Drawn;
        public static int CasingCount => casings.Count;

        public static float LengthOf(ProjectileModel m) => Length[(int)m] * Scale[(int)m];

        static bool Load()
        {
            if (loaded) return true;
            if (failed) return false;
            var root = Resources.Load<GameObject>("Dominion/Projectiles");
            if (root == null) { failed = true; return false; }
            meshes = new Mesh[Names.Length];
            mats = new Material[Names.Length][];
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                int i = System.Array.IndexOf(Names, mf.name);
                if (i <= 0) continue;
                meshes[i] = mf.sharedMesh;
                mats[i] = mf.GetComponent<MeshRenderer>().sharedMaterials;
            }
            for (int i = 0; i < batch.Length; i++) batch[i] = new List<Matrix4x4>(64);
            loaded = true;
            return true;
        }

        /// <summary>Mesh and materials of a model (missiles use them on their own pooled objects).</summary>
        public static bool Get(ProjectileModel m, out Mesh mesh, out Material[] materials)
        {
            mesh = null;
            materials = null;
            if (!Load() || m == ProjectileModel.None) return false;
            mesh = meshes[(int)m];
            materials = mats[(int)m];
            return mesh != null;
        }

        /// <summary>Which round a vehicle or mech main weapon fires (keyed by prefab name).</summary>
        public static ProjectileModel For(string unitKey) => unitKey switch
        {
            "Tank_Medium" or "Tank_Heavy" or "Mech_Aegis" => ProjectileModel.TankShell,
            "Tank_Artillery" => ProjectileModel.Artillery,
            "Tank_Scout" or "Tank_AntiAir" or "Aircraft_Wraith" => ProjectileModel.Autocannon,
            "Mech_Halberd" => ProjectileModel.Rail,
            "Vehicle_Carrier" or "Vehicle_Bastion" or "Mech_Thunderhead" or "Aircraft_Kestrel" or "Aircraft_Falcon" or "Aircraft_Lancer" or "Aircraft_Saber" => ProjectileModel.MG,
            _ => ProjectileModel.None,
        };

        /// <summary>Queue a round for drawing this frame: nose at 'nose', flying along 'vel'.</summary>
        public static void Draw(ProjectileModel m, Vector3 nose, Vector3 vel)
        {
            if (m == ProjectileModel.None || !Load() || meshes[(int)m] == null || vel.sqrMagnitude < 1e-4f) return;
            if (!Near(nose, m >= ProjectileModel.TankShell ? 1500f : 600f)) return;
            float s = Scale[(int)m];
            batch[(int)m].Add(Matrix4x4.TRS(nose, Quaternion.LookRotation(vel), new Vector3(s, s, s)));
        }

        static bool Near(Vector3 p, float range)
        {
            if (camT == null) { var c = Camera.main; if (c == null) return false; camT = c.transform; }
            return (p - camT.position).sqrMagnitude < range * range;
        }

        /// <summary>Brass out of the breech: up and to the right of the gun, carrying the shooter's own velocity.</summary>
        public static void EjectCasing(Vector3 breech, Vector3 dir, Vector3 shooterVel, bool big)
        {
            if (!Load() || !Near(breech, 90f)) return;
            if (casings.Count > 500) casings.RemoveAt(0);
            Vector3 right = Vector3.Cross(Vector3.up, dir);
            if (right.sqrMagnitude < 0.01f) right = Vector3.right;
            right.Normalize();
            casings.Add(new Casing
            {
                p = breech,
                v = shooterVel + right * Random.Range(2.5f, 4.5f) + Vector3.up * Random.Range(1.2f, 2.8f) - dir * Random.Range(0.2f, 1f),
                spin = Random.onUnitSphere * Random.Range(600f, 1400f),
                r = Quaternion.LookRotation(right),
                life = Random.Range(3.5f, 5f),
                big = big,
            });
        }

        /// <summary>Casings fly, bounce once and settle (once a frame, from Tracers).</summary>
        public static void Tick(float dt)
        {
            if (!loaded) return;
            for (int i = casings.Count - 1; i >= 0; i--)
            {
                var c = casings[i];
                c.life -= dt;
                if (c.life <= 0f) { casings.RemoveAt(i); continue; }
                if (!c.rested)
                {
                    c.v += Physics.gravity * dt;
                    c.p += c.v * dt;
                    c.r = Quaternion.Euler(c.spin * dt) * c.r;
                    float floor = WorldGround.Height(c.p.x, c.p.z) + 0.02f;
                    if (c.p.y < floor)
                    {
                        c.p.y = floor;
                        if (c.v.y < -1.5f) { c.v = new Vector3(c.v.x * 0.35f, -c.v.y * 0.3f, c.v.z * 0.35f); c.spin *= 0.4f; }
                        else { c.rested = true; c.r = Quaternion.Euler(0f, c.r.eulerAngles.y, 90f); }
                    }
                }
                casings[i] = c;
                var m = c.big ? ProjectileModel.CasingMedium : ProjectileModel.CasingSmall;
                float s = Scale[(int)m];
                batch[(int)m].Add(Matrix4x4.TRS(c.p, c.r, new Vector3(s, s, s)));
            }
        }

        /// <summary>Draw everything queued this frame, one instanced call per model and sub-mesh.</summary>
        public static void Flush()
        {
            if (!loaded) return;
            int drawn = 0;
            for (int i = 1; i < batch.Length; i++)
            {
                var list = batch[i];
                if (list.Count == 0) continue;
                drawn += list.Count;
                var mesh = meshes[i];
                if (mesh != null)
                {
                    bool big = i >= (int)ProjectileModel.TankShell && i <= (int)ProjectileModel.AAM;
                    for (int sm = 0; sm < mesh.subMeshCount && sm < mats[i].Length; sm++)
                    {
                        var rp = new RenderParams(mats[i][sm]) { shadowCastingMode = big ? ShadowCastingMode.On : ShadowCastingMode.Off, receiveShadows = true };
                        for (int k = 0; k < list.Count; k += 1023)
                            Graphics.RenderMeshInstanced(rp, mesh, sm, list, Mathf.Min(1023, list.Count - k), k);
                    }
                }
                list.Clear();
            }
            Drawn = drawn;
        }
    }
}
