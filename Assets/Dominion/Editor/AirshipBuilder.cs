// Dominion I - airship import (AirshipKit "Leviathan", SkyshipKit "Sentinel"): kit-local HDRP materials, model import
// with the rig kept as transforms (turrets, props, control surfaces, flags driven by script), the walkable collision
// mesh as a MeshCollider on a kinematic body, hull / deck bounds, and the Airship component with per-ship stats.
// Menu: Dominion > 9. Set Up Airships. Runs from DominionBuilder.SetupAssets.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using static Dominion.EditorTools.MiniJson;
using Object = UnityEngine.Object;

namespace Dominion.EditorTools
{
    public static class AirshipBuilder
    {
        const string Art = "Assets/Dominion/Art";
        const string Gen = "Assets/Dominion/Generated";
        const string MatDir = Gen + "/Materials/Airships";

        [MenuItem("Dominion/9. Set Up Airships")]
        public static void SetupMenu() => Setup();

        public static void Setup()
        {
            EnsureFolder(MatDir);
            Build("Airships", "Airship_Leviathan", a =>
            {
                a.displayName = "Leviathan"; a.flagship = true; a.crewSize = 100;
                a.maxSpeed = 6f; a.cruiseAlt = 150f; a.roofClearance = 45f; a.maxTurnRate = 3f; a.thrustAccel = 0.1f;
                a.gunDamage = 380f; a.gunType = DamageType.AP; a.gunSplash = 160f; a.gunSplashRadius = 6f; a.gunProximity = 10f;
                a.gunInterval = 2f; a.gunSpeed = 650f; a.gunGravity = 0.3f; a.gunRange = 1500f; a.gunSpreadDeg = 0.35f;
                a.falloffStart = 300f; a.falloffMin = 0.2f;
                a.minElevation = -30f; a.maxElevation = 85f; a.impactKind = ImpactKind.Shell; a.impactScale = 1.15f; a.muzzleScale = 1.2f; a.tracerWidth = 0.22f;
            });
            Build("Skyships", "Skyship_Sentinel", a =>
            {
                a.displayName = "Sentinel"; a.flagship = false; a.crewSize = 50;
                a.maxSpeed = 8f; a.cruiseAlt = 125f; a.roofClearance = 40f; a.maxTurnRate = 4.5f; a.thrustAccel = 0.14f;
                a.gunDamage = 70f; a.gunType = DamageType.Cannon; a.gunSplash = 30f; a.gunSplashRadius = 3f; a.gunProximity = 7f;
                a.gunInterval = 0.8f; a.gunSpeed = 900f; a.gunGravity = 0.15f; a.gunRange = 1300f; a.gunSpreadDeg = 0.45f;
                a.falloffStart = 250f; a.falloffMin = 0.2f;
                a.minElevation = -40f; a.maxElevation = 85f; a.impactKind = ImpactKind.Autocannon; a.impactScale = 0.7f; a.muzzleScale = 0.5f; a.tracerWidth = 0.1f;
            });
            BuildParachute();
            BuildProjectiles();
            AssetDatabase.SaveAssets();
        }

        /// <summary>ProjectileKit: every round in one prefab under Resources (Projectiles.cs draws them instanced).</summary>
        static void BuildProjectiles()
        {
            const string dir = "Projectiles";
            string fbx = $"{Art}/{dir}/Projectiles.fbx";
            if (!File.Exists(fbx)) return;
            var mats = new Dictionary<string, Material>();
            foreach (var kv in Obj(Parse(File.ReadAllText($"{Art}/{dir}/materials.json"))))
            {
                var d = Obj(kv.Value);
                string stem = S(Get(d, "stem")), kind = S(Get(d, "kind"), "flat");
                string hx = S(Get(d, "tint"), "ffffff");
                Color tint = new Color(Convert.ToInt32(hx.Substring(0, 2), 16) / 255f, Convert.ToInt32(hx.Substring(2, 2), 16) / 255f, Convert.ToInt32(hx.Substring(4, 2), 16) / 255f);
                var m = Mat($"{MatDir}/M_{kv.Key}.mat", "HDRP/Lit");
                HDMaterial.SetEmissiveColor(m, Color.black);
                if (stem.Length > 0) Lit(m, Tex(dir, $"T_{stem}_BaseColor"), Tex(dir, $"T_{stem}_Mask"), Tex(dir, $"T_{stem}_Normal"), tint, 1f, 1f);
                else Lit(m, null, null, null, tint, F(Get(d, "metal")), 1f - F(Get(d, "rough"), 0.5f));
                if (kind == "glow")
                {
                    HDMaterial.SetEmissiveColor(m, tint * 6f);
                    m.SetFloat("_EmissiveExposureWeight", 0f);
                }
                m.enableInstancing = true;
                HDMaterial.ValidateMaterial(m);
                EditorUtility.SetDirty(m);
                mats[kv.Key] = m;
            }
            var imp = (ModelImporter)AssetImporter.GetAtPath(fbx);
            imp.globalScale = 1f;
            imp.animationType = ModelImporterAnimationType.None;
            imp.importAnimation = false;
            imp.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            imp.importNormals = ModelImporterNormals.Import;
            foreach (var kv in mats) imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key), kv.Value);
            imp.SaveAndReimport();
            var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(fbx));
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            go.name = "Projectiles";
            foreach (var c in go.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
            PrefabUtility.SaveAsPrefabAsset(go, "Assets/Dominion/Resources/Dominion/Projectiles.prefab");
            Object.DestroyImmediate(go);
            Debug.Log("[Airships] projectile prefab ready");
        }

        /// <summary>ParachuteKit: ripstop canopy (seen from inside and out), lines, webbing; prefab "Parachute" (no colliders).</summary>
        static void BuildParachute()
        {
            const string dir = "Parachutes";
            string fbx = $"{Art}/{dir}/Parachute.fbx";
            if (!File.Exists(fbx)) return;
            var mats = new Dictionary<string, Material>();
            foreach (var kv in Obj(Parse(File.ReadAllText($"{Art}/{dir}/materials.json"))))
            {
                var d = Obj(kv.Value);
                string stem = S(Get(d, "stem"));
                string hx = S(Get(d, "tint"), "ffffff");
                Color tint = new Color(Convert.ToInt32(hx.Substring(0, 2), 16) / 255f, Convert.ToInt32(hx.Substring(2, 2), 16) / 255f, Convert.ToInt32(hx.Substring(4, 2), 16) / 255f);
                var m = Mat($"{MatDir}/M_{kv.Key}.mat", "HDRP/Lit");
                if (stem.Length > 0) Lit(m, Tex(dir, $"T_{stem}_BaseColor"), Tex(dir, $"T_{stem}_Mask"), Tex(dir, $"T_{stem}_Normal"), tint, 1f, 1f);
                else Lit(m, null, null, null, tint, F(Get(d, "metal")), 1f - F(Get(d, "rough"), 0.5f));
                m.SetFloat("_DoubleSidedEnable", kv.Key.StartsWith("PK_Canopy") ? 1f : 0f);
                HDMaterial.ValidateMaterial(m);
                EditorUtility.SetDirty(m);
                mats[kv.Key] = m;
            }
            var imp = (ModelImporter)AssetImporter.GetAtPath(fbx);
            imp.globalScale = 1f;
            imp.animationType = ModelImporterAnimationType.None;
            imp.importAnimation = false;
            imp.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            imp.importNormals = ModelImporterNormals.Import;
            foreach (var kv in mats) imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key), kv.Value);
            imp.SaveAndReimport();
            var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(fbx));
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            go.name = "Parachute";
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            foreach (var c in go.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
            PrefabUtility.SaveAsPrefabAsset(go, $"{Gen}/Prefabs/Parachute.prefab");
            Object.DestroyImmediate(go);
            Debug.Log("[Airships] parachute prefab ready");
        }

        // ------------------------------------------------------------------ materials (kit-local: texture names repeat across kits)
        static Texture2D Tex(string dir, string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            return AssetDatabase.LoadAssetAtPath<Texture2D>($"{Art}/{dir}/Textures/{name}.png");
        }

        static Material Mat(string path, string shader)
        {
            var sh = Shader.Find(shader);
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                m = new Material(sh) { name = Path.GetFileNameWithoutExtension(path) };
                AssetDatabase.CreateAsset(m, path);
            }
            else if (m.shader != sh) m.shader = sh;
            return m;
        }

        static void Lit(Material m, Texture2D baseMap, Texture2D mask, Texture2D normal, Color color, float metal, float smooth)
        {
            m.SetTexture("_BaseColorMap", baseMap);
            m.SetColor("_BaseColor", color);
            m.SetTexture("_MaskMap", mask);
            m.SetFloat("_Metallic", metal);
            m.SetFloat("_Smoothness", smooth);
            m.SetFloat("_MetallicRemapMin", 0f);
            m.SetFloat("_MetallicRemapMax", 1f);
            m.SetFloat("_SmoothnessRemapMin", 0f);
            m.SetFloat("_SmoothnessRemapMax", 1f);
            m.SetFloat("_AORemapMin", 0f);
            m.SetFloat("_AORemapMax", 1f);
            m.SetTexture("_NormalMap", normal);
            m.SetFloat("_NormalScale", 1f);
        }

        static Color Lin(List<object> c, float a = 1f) => c != null && c.Count >= 3 ? new Color(F(c[0]), F(c[1]), F(c[2]), a).gamma : Color.white;

        static Dictionary<string, Material> Materials(string dir)
        {
            var res = new Dictionary<string, Material>();
            string json = $"{Art}/{dir}/materials.json";
            if (!File.Exists(json)) return res;
            foreach (var kv in Obj(Parse(File.ReadAllText(json))))
            {
                var info = Obj(kv.Value);
                var texs = Obj(Get(info, "textures"));
                string n = kv.Key.Replace("MAT_", "");
                string path = $"{MatDir}/M_{dir}_{n}.mat";
                Material m;
                if (n == "MuzzleFlash")
                {
                    m = Mat(path, "HDRP/Unlit");
                    m.SetColor("_UnlitColor", new Color(0f, 0f, 0f, 1f));
                    m.SetTexture("_UnlitColorMap", null);
                    m.SetTexture("_EmissiveColorMap", Tex(dir, "T_MuzzleFlash"));
                    HDMaterial.SetEmissiveColor(m, new Color(1f, 0.85f, 0.6f) * 4f);
                    m.SetFloat("_EmissiveExposureWeight", 0f);
                    m.SetFloat("_SurfaceType", 1f);
                    m.SetFloat("_BlendMode", 1f);
                    m.SetFloat("_DoubleSidedEnable", 1f);
                }
                else
                {
                    m = Mat(path, "HDRP/Lit");
                    HDMaterial.SetEmissiveColor(m, Color.black);
                    HDMaterial.SetSurfaceType(m, false);
                    HDMaterial.SetAlphaClipping(m, false);
                    m.SetFloat("_DoubleSidedEnable", 0f);
                    string bc = S(Get(texs, "BaseColor")), img = S(Get(texs, "Image"));
                    if (bc.Length > 0)
                    {
                        string stem = bc.Substring(0, bc.Length - "_BaseColor".Length);
                        Lit(m, Tex(dir, stem + "_BaseColor"), Tex(dir, stem + "_Mask"), Tex(dir, stem + "_Normal"), Color.white, 1f, 1f);
                    }
                    else if (img.Length > 0)
                    {
                        // emblems and flags: painted cloth / decal, alpha-cut, seen from both sides
                        Lit(m, Tex(dir, img), null, null, Color.white, 0f, 0.3f);
                        HDMaterial.SetAlphaClipping(m, true);
                        HDMaterial.SetAlphaCutoff(m, 0.5f);
                        m.SetFloat("_DoubleSidedEnable", 1f);
                    }
                    else if (n == "Glass")
                    {
                        Lit(m, null, null, null, Lin(Arr(Get(info, "color")), 0.35f), 0f, 0.95f);
                        HDMaterial.SetSurfaceType(m, true);
                        m.SetFloat("_DoubleSidedEnable", 1f);
                    }
                    else
                    {
                        Color c = Lin(Arr(Get(info, "color")));
                        Lit(m, null, null, null, c, F(Get(info, "metallic")), 1f - F(Get(info, "roughness"), 0.5f));
                        if (F(Get(info, "emission")) > 0.5f)
                        {
                            HDMaterial.SetEmissiveColor(m, c * 3f);
                            m.SetFloat("_EmissiveExposureWeight", 0f);
                        }
                    }
                }
                HDMaterial.ValidateMaterial(m);
                EditorUtility.SetDirty(m);
                res[kv.Key] = m;
            }
            return res;
        }

        // ------------------------------------------------------------------ prefab
        static void Build(string dir, string name, Action<Airship> configure)
        {
            string fbx = $"{Art}/{dir}/{name}.fbx";
            if (!File.Exists(fbx)) { Debug.LogWarning("[Airships] missing " + fbx); return; }
            var mats = Materials(dir);
            var imp = (ModelImporter)AssetImporter.GetAtPath(fbx);
            imp.useFileScale = true;
            imp.globalScale = 1f;
            imp.importBlendShapes = false;
            imp.importVisibility = false;
            imp.importCameras = false;
            imp.importLights = false;
            imp.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            imp.animationType = ModelImporterAnimationType.Generic;
            imp.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            imp.optimizeGameObjects = false;
            imp.importAnimation = false;
            imp.importNormals = ModelImporterNormals.Import;
            imp.importTangents = ModelImporterTangents.CalculateMikk;
            imp.meshCompression = ModelImporterMeshCompression.Off;
            imp.isReadable = true;                                  // the collision mesh is cooked at runtime
            foreach (var kv in mats) imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key), kv.Value);
            imp.SaveAndReimport();

            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
            var go = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            go.name = name;
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            var anim = go.GetComponent<Animator>();
            if (anim) Object.DestroyImmediate(anim);

            // walkable collision shell -> MeshCollider (kinematic body, so it may be concave)
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true).ToArray())
            {
                if (!mf.name.Contains("Collision")) continue;
                var mc = mf.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
                mc.convex = false;
                var mr = mf.GetComponent<MeshRenderer>();
                if (mr) Object.DestroyImmediate(mr);
                Object.DestroyImmediate(mf);
            }
            Bounds hull = default, deck = default;
            bool h0 = false, d0 = false;
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                string n = r.name;
                if (r is SkinnedMeshRenderer smr)
                {
                    smr.updateWhenOffscreen = false;
                    smr.skinnedMotionVectors = true;
                }
                r.shadowCastingMode = n.Contains("MuzzleFlash") ? ShadowCastingMode.Off : ShadowCastingMode.On;
                if (n.Contains("MuzzleFlash") || n.Contains("_Flag_") || n.Contains("Decals")) continue;
                Mesh mesh = null;
                if (r is SkinnedMeshRenderer s2) mesh = s2.sharedMesh;
                else
                {
                    var rf = r.GetComponent<MeshFilter>();
                    if (rf != null) mesh = rf.sharedMesh;
                }
                if (mesh == null) continue;
                foreach (var c in Corners(mesh.bounds))
                {
                    Vector3 p = go.transform.InverseTransformPoint(r.transform.TransformPoint(c));
                    if (!h0) { hull = new Bounds(p, Vector3.zero); h0 = true; } else hull.Encapsulate(p);
                    if (n.Contains("Interior"))
                    {
                        if (!d0) { deck = new Bounds(p, Vector3.zero); d0 = true; } else deck.Encapsulate(p);
                    }
                }
            }
            // the open top deck / roof walkway sits above the interiors
            deck.max += new Vector3(0f, 4.5f, 0f);

            var rb = go.GetComponent<Rigidbody>();
            if (rb == null) rb = go.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            var a = go.AddComponent<Airship>();
            a.unitKey = name;
            a.hullBounds = hull;
            a.deckBounds = deck;
            // the gas envelope is the big target: aim points at its middle
            a.centerLocal = new Vector3(hull.center.x, hull.max.y - Mathf.Min(hull.size.x, hull.size.y) * 0.45f, hull.center.z);
            a.radius = Mathf.Min(hull.extents.x, hull.extents.y) * 0.8f;
            configure(a);
            PrefabUtility.SaveAsPrefabAsset(go, $"{Gen}/Prefabs/{name}.prefab");
            Object.DestroyImmediate(go);
            Debug.Log($"[Airships] {name}: hull {hull.size.x:0} x {hull.size.y:0} x {hull.size.z:0} m (min y {hull.min.y:0.0}), decks {deck.size.x:0.0} x {deck.size.y:0.0} x {deck.size.z:0.0} at {deck.center}");
        }

        static IEnumerable<Vector3> Corners(Bounds b)
        {
            for (int i = 0; i < 8; i++)
                yield return b.center + Vector3.Scale(b.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
        }

        static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }
    }
}
