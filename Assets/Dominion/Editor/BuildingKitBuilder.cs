// Dominion I - BuildingKit import: HDRP materials from Art/Buildings/materials.json, FBX import settings and one prefab
// per building (LODGroup from the _LOD0/_LOD1 meshes, a MeshCollider from the _Collider mesh, static flags for GI and
// occlusion culling). Menu: Dominion > 6. Set Up Buildings.
// Batch: -executeMethod Dominion.EditorTools.BuildingKitBuilder.BatchBuildings (also runs from DominionBuilder.SetupAssets)
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
    public static class BuildingKitBuilder
    {
        const string Dir = "Assets/Dominion/Art/Buildings";
        const string TexDir = Dir + "/Textures";
        const string MatDir = "Assets/Dominion/Generated/Materials/Buildings";
        const string PrefabDir = "Assets/Dominion/Generated/Prefabs/Buildings";

        /// <summary>LOD0 (with interiors) until the building fills less than this fraction of the screen height.</summary>
        const float Lod1At = 0.2f;
        /// <summary>Culled below this fraction (a 9 m cottage disappears beyond ~2 km; the skyscraper never does on the map).</summary>
        const float CullAt = 0.004f;

        [MenuItem("Dominion/6. Set Up Buildings (materials, prefabs)")]
        public static void SetupMenu() => SetupBuildings();

        public static void BatchBuildings()
        {
            int code = 0;
            try
            {
                SetupBuildings();
                Report();
            }
            catch (Exception e)
            {
                Debug.LogError("[Buildings] FAILED: " + e);
                code = 1;
            }
            EditorApplication.Exit(code);
        }

        public static void SetupBuildings()
        {
            if (!File.Exists(Dir + "/materials.json")) return;
            EnsureFolder(MatDir);
            EnsureFolder(PrefabDir);
            var tex = ConfigureTextures();
            var mats = Materials(tex);
            foreach (var fbx in Directory.GetFiles(Dir, "Building_*.fbx").OrderBy(f => f))
                BuildPrefab(fbx.Replace('\\', '/'), mats);
            AssetDatabase.SaveAssets();
            Debug.Log("[Buildings] prefabs ready in " + PrefabDir);
        }

        // ------------------------------------------------------------------ textures + materials
        static Dictionary<string, Texture2D> ConfigureTextures()
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
                    var type = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                    if (ti.textureType == type && ti.sRGBTexture == !linear && ti.maxTextureSize == 2048 &&
                        ti.wrapMode == TextureWrapMode.Repeat && ti.anisoLevel == 8 && ti.mipmapEnabled) continue;
                    ti.textureType = type;
                    ti.sRGBTexture = !linear;
                    ti.alphaIsTransparency = false;
                    ti.maxTextureSize = 2048;
                    ti.wrapMode = TextureWrapMode.Repeat;
                    ti.anisoLevel = 8;                       // walls and floors are mostly seen at grazing angles
                    ti.mipmapEnabled = true;
                    ti.SaveAndReimport();
                }
            }
            finally { AssetDatabase.StopAssetEditing(); }
            var res = new Dictionary<string, Texture2D>();
            foreach (var path in paths)
                res[Path.GetFileNameWithoutExtension(path)] = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            return res;
        }

        static Texture2D T(Dictionary<string, Texture2D> tex, string n)
        {
            if (tex.TryGetValue(n, out var t)) return t;
            Debug.LogWarning("[Buildings] texture not found: " + n);
            return null;
        }

        static Dictionary<string, Material> Materials(Dictionary<string, Texture2D> tex)
        {
            var res = new Dictionary<string, Material>();
            foreach (var kv in Obj(Parse(File.ReadAllText(Dir + "/materials.json"))))
            {
                var d = Obj(kv.Value);
                string stem = S(Get(d, "stem"));
                string kind = S(Get(d, "kind"), "lit");
                Color tint = Hex(S(Get(d, "tint"), "ffffff"));
                var m = MaterialAt($"{MatDir}/M_{kv.Key}.mat");
                if (kind == "glass")
                {
                    SetLit(m, null, null, null, new Color(tint.r, tint.g, tint.b, 0.22f), 0f, 0.95f);
                    m.SetFloat("_DoubleSidedEnable", 1f);
                    HDMaterial.SetSurfaceType(m, true);
                    HDMaterial.ValidateMaterial(m);
                    m.SetShaderPassEnabled("ShadowCaster", false);      // windows let the sun into the rooms
                }
                else
                {
                    SetLit(m, T(tex, $"T_{stem}_BaseColor"), T(tex, $"T_{stem}_Mask"), T(tex, $"T_{stem}_Normal"), tint, 1f, 1f);
                    HDMaterial.ValidateMaterial(m);
                }
                EditorUtility.SetDirty(m);
                res[kv.Key] = m;
            }
            return res;
        }

        static Material MaterialAt(string path)
        {
            var sh = Shader.Find("HDRP/Lit");
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                m = new Material(sh) { name = Path.GetFileNameWithoutExtension(path) };
                AssetDatabase.CreateAsset(m, path);
            }
            else if (m.shader != sh) m.shader = sh;
            return m;
        }

        static void SetLit(Material m, Texture2D baseMap, Texture2D mask, Texture2D normal, Color color, float metal, float smooth)
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
            new Color(Convert.ToInt32(h.Substring(0, 2), 16) / 255f, Convert.ToInt32(h.Substring(2, 2), 16) / 255f,
                Convert.ToInt32(h.Substring(4, 2), 16) / 255f, 1f);

        // ------------------------------------------------------------------ model + prefab
        static void BuildPrefab(string fbx, Dictionary<string, Material> mats)
        {
            string name = Path.GetFileNameWithoutExtension(fbx);
            var imp = (ModelImporter)AssetImporter.GetAtPath(fbx);
            imp.useFileScale = true;
            imp.globalScale = 1f;
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
            imp.meshOptimizationFlags = MeshOptimizationFlags.Everything;
            imp.weldVertices = true;
            imp.isReadable = true;                           // the city generator merges distant copies into chunk meshes
            imp.addCollider = false;
            imp.generateSecondaryUV = true;                  // lightmap UVs (UV1) for baked GI / APV
            imp.secondaryUVHardAngle = 88f;
            imp.secondaryUVPackMargin = 4f;
            foreach (var kv in mats)
                imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key), kv.Value);
            imp.SaveAndReimport();

            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
            var go = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            go.name = name;
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);

            var colT = go.transform.Find(name + "_Collider");
            if (colT)
            {
                var mf = colT.GetComponent<MeshFilter>();
                var mesh = mf ? mf.sharedMesh : null;
                var mr = colT.GetComponent<MeshRenderer>();
                if (mr) Object.DestroyImmediate(mr);
                if (mf) Object.DestroyImmediate(mf);
                var mc = colT.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mesh;
                mc.convex = false;
            }
            else Debug.LogWarning("[Buildings] no collider mesh in " + name);

            var r0 = go.transform.Find(name + "_LOD0")?.GetComponent<Renderer>();
            var r1 = go.transform.Find(name + "_LOD1")?.GetComponent<Renderer>();
            var lg = go.GetComponent<LODGroup>();
            if (lg == null) lg = go.AddComponent<LODGroup>();
            lg.fadeMode = LODFadeMode.None;
            lg.SetLODs(new[] { new LOD(Lod1At, new[] { r0 }), new LOD(CullAt, new[] { r1 }) });
            lg.RecalculateBounds();
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>(true))
            {
                r.shadowCastingMode = ShadowCastingMode.On;
                r.receiveGI = ReceiveGI.Lightmaps;
            }
            // static for baked GI, occlusion culling and reflection probes. Not batching-static: the same building is
            // placed many times on a map and static batching would duplicate its vertices per copy (the SRP batcher
            // already keeps the draw calls cheap).
            const StaticEditorFlags flags = StaticEditorFlags.ContributeGI | StaticEditorFlags.OccluderStatic |
                                            StaticEditorFlags.OccludeeStatic | StaticEditorFlags.ReflectionProbeStatic;
            foreach (var t in go.GetComponentsInChildren<Transform>(true))
                GameObjectUtility.SetStaticEditorFlags(t.gameObject, flags);
            PrefabUtility.SaveAsPrefabAsset(go, $"{PrefabDir}/{name}.prefab");
            Object.DestroyImmediate(go);
        }

        static void Report()
        {
            foreach (var path in Directory.GetFiles(PrefabDir, "*.prefab").OrderBy(p => p))
            {
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(path.Replace('\\', '/'));
                var lg = go.GetComponent<LODGroup>();
                var lods = lg ? lg.GetLODs() : new LOD[0];
                string lodInfo = string.Join(" | ", lods.Select((l, i) =>
                {
                    var r = l.renderers.FirstOrDefault();
                    var mesh = r ? r.GetComponent<MeshFilter>().sharedMesh : null;
                    return mesh ? $"LOD{i} {mesh.triangles.Length / 3} tris {mesh.subMeshCount} mats uv2={mesh.uv2.Length > 0} " +
                                  $"min={mesh.bounds.min.ToString("F1")} max={mesh.bounds.max.ToString("F1")} >{l.screenRelativeTransitionHeight}" : $"LOD{i} missing";
                }));
                var mc = go.GetComponentInChildren<MeshCollider>();
                string col = mc && mc.sharedMesh ? $"collider {mc.sharedMesh.triangles.Length / 3} tris" : "NO COLLIDER";
                var rot = string.Join(",", go.GetComponentsInChildren<Transform>().Select(t => t.localEulerAngles.magnitude.ToString("F0")).Distinct());
                Debug.Log($"[Buildings] {go.name}: {lodInfo} | {col} | rotations {rot} | lodgroup size {(lg ? lg.size : 0):F1}");
            }
            var glass = AssetDatabase.LoadAssetAtPath<Material>($"{MatDir}/M_BLD_Glass.mat");
            if (glass) Debug.Log($"[Buildings] glass transparent={glass.renderQueue >= 2501} shadowcaster={glass.GetShaderPassEnabled("ShadowCaster")}");
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
