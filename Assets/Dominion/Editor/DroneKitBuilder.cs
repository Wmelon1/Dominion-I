// Dominion I - DroneKit import: textures, HDRP materials (painted composites, carbon, anodised metal, emissive nav and
// repair lights, translucent rotor-blur discs), the repair-beam material, and the three drone prefabs (Wasp, Mender,
// Kite) with their DroneUnit stats. Menu: Dominion > 8. Set Up Drone Kit. Runs from DominionBuilder.SetupAssets.
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
    public static class DroneKitBuilder
    {
        const string Dir = "Assets/Dominion/Art/Drones";
        const string TexDir = Dir + "/Textures";
        const string Gen = "Assets/Dominion/Generated";
        const string MatDir = Gen + "/Materials/Drones";
        const string PrefabDir = Gen + "/Prefabs";
        const string BeamPath = "Assets/Dominion/Resources/Dominion/M_RepairBeam.mat";
        /// <summary>The Blender kit is modelled a touch small: imported 1.2x so the drones are soldier-sized (~2 m across).</summary>
        const float Scale = 1.2f;
        static Dictionary<string, Texture2D> tex;

        struct Stats
        {
            public string name;
            public float cruise, accel, alt, pool, rate, beam, sensor;
        }

        static readonly Dictionary<string, Stats> Drones = new Dictionary<string, Stats>
        {
            ["Drone_Wasp"] = new Stats { name = "Wasp Drone", cruise = 30f, accel = 16f, alt = 32f, pool = 900f, rate = 180f, beam = 26f, sensor = 280f },
            ["Drone_Mender"] = new Stats { name = "Mender Drone", cruise = 21f, accel = 11f, alt = 28f, pool = 2600f, rate = 320f, beam = 30f, sensor = 230f },
            ["Drone_Kite"] = new Stats { name = "Kite Recon Drone", cruise = 38f, accel = 18f, alt = 45f, pool = 500f, rate = 140f, beam = 26f, sensor = 420f },
        };

        [MenuItem("Dominion/8. Set Up Drone Kit")]
        public static void SetupMenu() => Setup();

        public static void Setup()
        {
            if (!AssetDatabase.IsValidFolder(Dir)) return;
            foreach (var f in new[] { MatDir, PrefabDir, "Assets/Dominion/Resources/Dominion" }) EnsureFolder(f);
            ConfigureTextures();
            var mats = Materials();
            BeamMaterial();
            int n = 0;
            foreach (var fbx in Directory.GetFiles(Dir, "*.fbx").Select(p => p.Replace('\\', '/')).OrderBy(p => p))
            {
                string name = Path.GetFileNameWithoutExtension(fbx);
                if (!Drones.TryGetValue(name, out var st)) continue;
                BuildPrefab(fbx, name, st, mats);
                n++;
            }
            AssetDatabase.SaveAssets();
            Debug.Log($"[Drones] {n} drone prefabs ready");
        }

        // ------------------------------------------------------------------ textures and materials
        static void ConfigureTextures()
        {
            var paths = AssetDatabase.FindAssets("t:Texture2D", new[] { TexDir }).Select(AssetDatabase.GUIDToAssetPath).ToList();
            AssetDatabase.StartAssetEditing();
            try
            {
                foreach (var path in paths)
                {
                    if (!(AssetImporter.GetAtPath(path) is TextureImporter ti)) continue;
                    string n = Path.GetFileNameWithoutExtension(path);
                    bool normal = n.EndsWith("_Normal");
                    bool linear = normal || n.EndsWith("_Mask");
                    bool alpha = n.StartsWith("T_RotorBlur");
                    var type = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                    if (ti.textureType == type && ti.sRGBTexture == !linear && ti.alphaIsTransparency == alpha && ti.anisoLevel == 8 &&
                        ti.maxTextureSize == 1024 && ti.mipmapEnabled) continue;
                    ti.textureType = type;
                    ti.sRGBTexture = !linear;
                    ti.alphaIsTransparency = alpha;
                    ti.alphaSource = alpha ? TextureImporterAlphaSource.FromInput : TextureImporterAlphaSource.None;
                    ti.maxTextureSize = 1024;
                    ti.wrapMode = alpha ? TextureWrapMode.Clamp : TextureWrapMode.Repeat;
                    ti.anisoLevel = 8;
                    ti.mipmapEnabled = true;
                    ti.SaveAndReimport();
                }
            }
            finally { AssetDatabase.StopAssetEditing(); }
            tex = new Dictionary<string, Texture2D>();
            foreach (var path in paths) tex[Path.GetFileNameWithoutExtension(path)] = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        static Texture2D T(string n) => n != null && tex.TryGetValue(n, out var t) ? t : null;

        static Material Mat(string path, string shader = "HDRP/Lit")
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

        static Color Hex(string h) =>
            new Color(Convert.ToInt32(h.Substring(0, 2), 16) / 255f, Convert.ToInt32(h.Substring(2, 2), 16) / 255f, Convert.ToInt32(h.Substring(4, 2), 16) / 255f, 1f);

        static Dictionary<string, Material> Materials()
        {
            var res = new Dictionary<string, Material>();
            foreach (var kv in Obj(Parse(File.ReadAllText(Dir + "/materials.json"))))
            {
                var d = Obj(kv.Value);
                string stem = S(Get(d, "stem"));
                string kind = S(Get(d, "kind"), "tex");
                Color tint = Hex(S(Get(d, "tint"), "ffffff"));
                float rough = F(Get(d, "rough"), 0.5f), metal = F(Get(d, "metal"));
                var m = Mat($"{MatDir}/M_{kv.Key}.mat");
                HDMaterial.SetEmissiveColor(m, Color.black);
                switch (kind)
                {
                    case "tex":
                        Lit(m, T($"T_{stem}_BaseColor"), T($"T_{stem}_Mask"), T($"T_{stem}_Normal"), tint, 1f, 1f);
                        HDMaterial.SetSurfaceType(m, false);
                        break;
                    case "glow":
                        // nav lights and repair emitters: glow regardless of the scene's exposure
                        Lit(m, null, null, null, tint * 0.6f, 0f, 0.7f);
                        HDMaterial.SetEmissiveColor(m, tint * 5f);
                        m.SetFloat("_EmissiveExposureWeight", 0f);
                        HDMaterial.SetSurfaceType(m, false);
                        break;
                    case "blur":
                        // translucent spinning-prop disc, seen from above and below
                        Lit(m, T($"T_{stem}_BaseColor"), null, null, Color.white, 0f, 0.4f);
                        HDMaterial.SetSurfaceType(m, true);
                        m.SetFloat("_DoubleSidedEnable", 1f);
                        break;
                    default:
                        Lit(m, null, null, null, tint, metal, 1f - rough);
                        HDMaterial.SetSurfaceType(m, false);
                        break;
                }
                HDMaterial.ValidateMaterial(m);
                EditorUtility.SetDirty(m);
                res[kv.Key] = m;
            }
            return res;
        }

        /// <summary>Additive, exposure-independent cyan beam the drones play on what they repair (LineRenderer).</summary>
        static void BeamMaterial()
        {
            var m = Mat(BeamPath, "HDRP/Unlit");
            m.SetColor("_UnlitColor", new Color(0f, 0f, 0f, 1f));
            m.SetTexture("_UnlitColorMap", null);
            HDMaterial.SetEmissiveColor(m, new Color(0.25f, 1f, 0.92f) * 6f);
            m.SetFloat("_EmissiveExposureWeight", 0f);
            m.SetFloat("_SurfaceType", 1f);
            m.SetFloat("_BlendMode", 1f);
            m.SetFloat("_DoubleSidedEnable", 1f);
            HDMaterial.ValidateMaterial(m);
            EditorUtility.SetDirty(m);
        }

        // ------------------------------------------------------------------ prefabs
        static void BuildPrefab(string fbx, string name, Stats st, Dictionary<string, Material> mats)
        {
            var imp = (ModelImporter)AssetImporter.GetAtPath(fbx);
            imp.useFileScale = true;
            imp.globalScale = Scale;
            imp.importBlendShapes = false;
            imp.importVisibility = false;
            imp.importCameras = false;
            imp.importLights = false;
            imp.animationType = ModelImporterAnimationType.None;
            imp.importAnimation = false;
            imp.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            imp.importNormals = ModelImporterNormals.Import;
            imp.importTangents = ModelImporterTangents.CalculateMikk;
            imp.meshCompression = ModelImporterMeshCompression.Off;
            imp.isReadable = false;
            imp.addCollider = false;
            foreach (var kv in mats)
                if (kv.Value) imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key), kv.Value);
            imp.SaveAndReimport();
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
            var go = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            go.name = name;

            // bounds of everything visible, in the drone's own frame
            var rends = go.GetComponentsInChildren<MeshRenderer>(true);
            var b = new Bounds();
            bool first = true;
            foreach (var r in rends)
            {
                var mf = r.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                var mb = mf.sharedMesh.bounds;
                foreach (var c in Corners(mb))
                {
                    Vector3 w = go.transform.InverseTransformPoint(r.transform.TransformPoint(c));
                    if (first) { b = new Bounds(w, Vector3.zero); first = false; }
                    else b.Encapsulate(w);
                }
                bool blur = r.name.Contains("_Blur_");
                r.shadowCastingMode = blur ? ShadowCastingMode.Off : ShadowCastingMode.On;
                r.receiveShadows = !blur;
            }

            var du = go.AddComponent<DroneUnit>();
            du.displayName = st.name;
            du.unitKey = name;
            du.cruiseSpeed = st.cruise;
            du.accel = st.accel;
            du.cruiseAlt = st.alt;
            du.healPool = st.pool;
            du.healRate = st.rate;
            du.beamRange = st.beam;
            du.sensorRange = st.sensor;
            du.centerLocal = new Vector3(0f, b.center.y, 0f);
            du.radius = Mathf.Max(0.6f, Mathf.Min(b.extents.x, b.extents.z) * 0.8f);

            var rb = go.GetComponent<Rigidbody>();
            if (rb == null) rb = go.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
            rb.interpolation = RigidbodyInterpolation.None;
            // hit box: the body and rotor disc, so rifles and flak can bring it down
            var col = go.AddComponent<BoxCollider>();
            col.center = b.center;
            col.size = new Vector3(b.size.x * 0.85f, Mathf.Max(0.5f, b.size.y * 0.8f), b.size.z * 0.85f);

            var lg = go.AddComponent<LODGroup>();
            lg.fadeMode = LODFadeMode.None;
            lg.SetLODs(new[] { new LOD(0.006f, rends.Cast<Renderer>().ToArray()) });
            lg.RecalculateBounds();

            PrefabUtility.SaveAsPrefabAsset(go, $"{PrefabDir}/{name}.prefab");
            Object.DestroyImmediate(go);
            Debug.Log($"[Drones] {name}: {b.size.x:0.00} x {b.size.y:0.00} x {b.size.z:0.00} m, radius {du.radius:0.00}");
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
