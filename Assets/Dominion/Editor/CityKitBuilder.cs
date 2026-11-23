// Dominion I - CityKit import: textures, HDRP materials (roads, facades, foliage, car paints), terrain layers, prefabs for
// trees / cars / wrecks / street furniture / barricades, colour variants of the BuildingKit buildings, and the CityKit
// asset the War-scene city generator reads. Menu: Dominion > 7. Set Up City Kit. Runs from DominionBuilder.SetupAssets.
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
    public static class CityKitBuilder
    {
        const string Dir = "Assets/Dominion/Art/City";
        const string TexDir = Dir + "/Textures";
        const string Gen = "Assets/Dominion/Generated";
        const string MatDir = Gen + "/Materials/City";
        const string BldMatDir = Gen + "/Materials/Buildings";
        const string PrefabDir = Gen + "/Prefabs/City";
        const string BldPrefabDir = Gen + "/Prefabs/Buildings";
        const string KitPath = Gen + "/CityKit.asset";
        static Dictionary<string, Texture2D> tex;

        [MenuItem("Dominion/7. Set Up City Kit")]
        public static void SetupMenu() => Setup();

        public static void BatchCity()
        {
            int code = 0;
            try { Setup(); }
            catch (Exception e) { Debug.LogError("[City] FAILED: " + e); code = 1; }
            EditorApplication.Exit(code);
        }

        public static CityKit Setup()
        {
            if (!AssetDatabase.IsValidFolder(Dir)) return null;
            foreach (var f in new[] { MatDir, PrefabDir, PrefabDir + "/Cars", BldPrefabDir + "/Variants", Gen + "/TerrainLayers" }) EnsureFolder(f);
            ConfigureTextures();
            var kit = AssetDatabase.LoadAssetAtPath<CityKit>(KitPath);
            if (kit == null)
            {
                kit = ScriptableObject.CreateInstance<CityKit>();
                AssetDatabase.CreateAsset(kit, KitPath);
            }
            var mats = ModelMaterials();
            BuildModels(kit, mats);
            CityMaterials(kit);
            TerrainLayers(kit);
            BuildingVariants(kit);
            EditorUtility.SetDirty(kit);
            AssetDatabase.SaveAssets();
            Debug.Log($"[City] kit ready: {kit.buildings.Count} building variants, {kit.cars.Length} cars, {kit.wrecks.Length} wrecks, {kit.trees.Length} trees, {kit.layers.Length} terrain layers");
            return kit;
        }

        // ------------------------------------------------------------------ textures
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
                    bool alpha = n.StartsWith("T_Leaves") || n.StartsWith("T_Crosswalk");
                    var type = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                    if (ti.textureType == type && ti.sRGBTexture == !linear && ti.alphaIsTransparency == alpha && ti.anisoLevel == 8 &&
                        ti.maxTextureSize == 2048 && ti.mipmapEnabled) continue;
                    ti.textureType = type;
                    ti.sRGBTexture = !linear;
                    ti.alphaIsTransparency = alpha;
                    ti.alphaSource = alpha ? TextureImporterAlphaSource.FromInput : TextureImporterAlphaSource.None;
                    ti.mipMapsPreserveCoverage = alpha;
                    ti.alphaTestReferenceValue = 0.5f;
                    ti.maxTextureSize = 2048;
                    ti.wrapMode = TextureWrapMode.Repeat;
                    ti.anisoLevel = 8;
                    ti.mipmapEnabled = true;
                    ti.SaveAndReimport();
                }
            }
            finally { AssetDatabase.StopAssetEditing(); }
            tex = new Dictionary<string, Texture2D>();
            foreach (var path in paths) tex[Path.GetFileNameWithoutExtension(path)] = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        static Texture2D T(string n) => tex.TryGetValue(n, out var t) ? t : null;

        static Material Mat(string path)
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

        static Material Textured(string name, string stem, Color tint, bool clip = false, bool twoSided = false)
        {
            var m = Mat($"{MatDir}/M_{name}.mat");
            Lit(m, T($"T_{stem}_BaseColor"), T($"T_{stem}_Mask"), T($"T_{stem}_Normal"), tint, 1f, 1f);
            HDMaterial.SetAlphaClipping(m, clip);
            if (clip) HDMaterial.SetAlphaCutoff(m, 0.5f);
            m.SetFloat("_DoubleSidedEnable", twoSided ? 1f : 0f);
            if (twoSided) m.SetFloat("_DoubleSidedNormalMode", 2f);     // keep the bent foliage normals on both sides
            HDMaterial.ValidateMaterial(m);
            m.enableInstancing = true;                                  // terrain trees are drawn instanced
            EditorUtility.SetDirty(m);
            return m;
        }

        /// <summary>A copy of a BuildingKit material with a different tint (same textures).</summary>
        static Material Tinted(string name, string bld, Color tint)
        {
            var src = Bld(bld);
            var m = Mat($"{MatDir}/M_{name}.mat");
            if (src)
            {
                m.CopyPropertiesFromMaterial(src);
                m.SetColor("_BaseColor", tint);
                HDMaterial.ValidateMaterial(m);
            }
            EditorUtility.SetDirty(m);
            return m;
        }

        static Color Hex(string h) =>
            new Color(Convert.ToInt32(h.Substring(0, 2), 16) / 255f, Convert.ToInt32(h.Substring(2, 2), 16) / 255f, Convert.ToInt32(h.Substring(4, 2), 16) / 255f, 1f);

        static Material Bld(string name) => AssetDatabase.LoadAssetAtPath<Material>($"{BldMatDir}/M_{name}.mat");

        // ------------------------------------------------------------------ model materials (from the Blender kit)
        static Dictionary<string, Material> ModelMaterials()
        {
            var res = new Dictionary<string, Material>();
            foreach (var kv in Obj(Parse(File.ReadAllText(Dir + "/materials.json"))))
            {
                if (kv.Key.StartsWith("BLD_")) { res[kv.Key] = Bld(kv.Key); continue; }
                var d = Obj(kv.Value);
                string stem = S(Get(d, "stem"));
                Color tint = Hex(S(Get(d, "tint"), "ffffff"));
                bool clip = Get(d, "clip") is bool b && b;
                if (stem.Length > 0) res[kv.Key] = Textured(kv.Key, stem, tint, clip, clip);
                else
                {
                    var flat = Arr(Get(d, "flat"));
                    var m = Mat($"{MatDir}/M_{kv.Key}.mat");
                    Lit(m, null, null, null, tint, flat.Count > 1 ? F(flat[1]) : 0f, 1f - (flat.Count > 0 ? F(flat[0]) : 0.5f));
                    HDMaterial.ValidateMaterial(m);
                    EditorUtility.SetDirty(m);
                    res[kv.Key] = m;
                }
            }
            return res;
        }

        // ------------------------------------------------------------------ prefabs
        static GameObject Import(string fbx, Dictionary<string, Material> mats)
        {
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
            imp.isReadable = true;                       // the city generator merges street furniture into chunk meshes
            imp.addCollider = false;
            imp.generateSecondaryUV = false;
            foreach (var kv in mats)
                if (kv.Value) imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key), kv.Value);
            imp.SaveAndReimport();
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
            var go = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            return go;
        }

        static void Lods(GameObject go, float lod1, float cull)
        {
            string n = go.name;
            var r0 = go.transform.Find(n + "_LOD0")?.GetComponent<Renderer>();
            var r1 = go.transform.Find(n + "_LOD1")?.GetComponent<Renderer>();
            var lg = go.GetComponent<LODGroup>();
            if (lg == null) lg = go.AddComponent<LODGroup>();
            lg.fadeMode = LODFadeMode.None;
            if (r0 && r1) lg.SetLODs(new[] { new LOD(lod1, new[] { r0 }), new LOD(cull, new[] { r1 }) });
            else if (r0) lg.SetLODs(new[] { new LOD(cull, new[] { r0 }) });
            lg.RecalculateBounds();
        }

        static Bounds MeshBounds(GameObject go)
        {
            var t = go.transform.Find(go.name + "_LOD0");
            MeshFilter mf = t != null ? t.GetComponent<MeshFilter>() : null;
            if (mf == null) mf = go.GetComponentInChildren<MeshFilter>();
            return mf ? mf.sharedMesh.bounds : new Bounds(Vector3.up, Vector3.one);
        }

        static GameObject Save(GameObject go, string path)
        {
            var p = PrefabUtility.SaveAsPrefabAsset(go, path);
            Object.DestroyImmediate(go);
            return p;
        }

        static readonly (string name, string hex)[] Paints =
        {
            ("White", "e8e8e6"), ("Black", "1e2022"), ("Silver", "9ea3a8"), ("Red", "8e1e1a"), ("Blue", "1f3a66"), ("Green", "2f4a36"),
            ("Beige", "b8a88a"), ("Yellow", "d8a420"),
        };

        static void BuildModels(CityKit kit, Dictionary<string, Material> mats)
        {
            var paint = new Dictionary<string, Material>();
            foreach (var (name, hex) in Paints)
            {
                var m = Mat($"{MatDir}/M_CK_CarPaint_{name}.mat");
                Lit(m, T("T_CarPaint_BaseColor"), T("T_CarPaint_Mask"), T("T_CarPaint_Normal"), Hex(hex), 1f, 1f);
                HDMaterial.ValidateMaterial(m);
                EditorUtility.SetDirty(m);
                paint[name] = m;
            }
            var cars = new List<GameObject>();
            var wrecks = new List<GameObject>();
            var trees = new GameObject[5];
            string[] treeOrder = { "Tree_Oak", "Tree_Maple", "Tree_Street", "Tree_Pine", "Tree_PineTall" };
            var info = Obj(Parse(File.ReadAllText(Dir + "/models.json")));
            foreach (var fbx in Directory.GetFiles(Dir, "*.fbx").Select(p => p.Replace('\\', '/')).OrderBy(p => p))
            {
                string name = Path.GetFileNameWithoutExtension(fbx);
                var meta = Obj(Get(info, name));
                string kind = S(Get(meta, "kind"));
                var go = Import(fbx, mats);
                go.name = name;
                var b = MeshBounds(go);
                switch (kind)
                {
                    case "tree":
                    {
                        Lods(go, 0.22f, 0.015f);
                        var cap = go.AddComponent<CapsuleCollider>();
                        cap.radius = Mathf.Max(0.2f, F(Get(meta, "radius"), 0.3f));
                        cap.height = 5f;
                        cap.center = new Vector3(0f, 2.5f, 0f);
                        foreach (var r in go.GetComponentsInChildren<MeshRenderer>()) r.shadowCastingMode = ShadowCastingMode.On;
                        int ti = Array.IndexOf(treeOrder, name);
                        var p = Save(go, $"{PrefabDir}/{name}.prefab");
                        if (ti >= 0) trees[ti] = p;
                        break;
                    }
                    case "car":
                    case "wreck":
                    {
                        Lods(go, 0.12f, 0.012f);
                        var bc = go.AddComponent<BoxCollider>();
                        bc.center = b.center;
                        bc.size = b.size;
                        go.AddComponent<CarProp>();
                        if (kind == "wreck")
                        {
                            var p = Save(go, $"{PrefabDir}/{name}.prefab");
                            if (name == "Wreck_Bus") kit.busWreck = p; else wrecks.Add(p);
                            break;
                        }
                        // colour variants share the mesh; each swaps the paint material
                        var basePath = $"{PrefabDir}/{name}.prefab";
                        var basePrefab = Save(go, basePath);
                        var colours = name == "Car_Bus" ? new[] { "White", "Yellow", "Blue" } : Paints.Select(p => p.name).ToArray();
                        foreach (var c in colours)
                        {
                            var v = (GameObject)PrefabUtility.InstantiatePrefab(basePrefab);
                            PrefabUtility.UnpackPrefabInstance(v, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
                            foreach (var r in v.GetComponentsInChildren<MeshRenderer>())
                                r.sharedMaterials = r.sharedMaterials.Select(m => m && m.name == "M_CK_CarPaint" ? paint[c] : m).ToArray();
                            v.name = $"{name}_{c}";
                            var p = Save(v, $"{PrefabDir}/Cars/{name}_{c}.prefab");
                            if (name == "Car_Bus") { if (c == "White") kit.bus = p; }
                            else cars.Add(p);
                        }
                        break;
                    }
                    case "barrier":
                    case "twall":
                    {
                        Lods(go, 0.05f, 0.008f);
                        var bc = go.AddComponent<BoxCollider>();
                        bc.center = b.center;
                        bc.size = b.size;
                        if (kind == "twall") go.AddComponent<CoverObject>();
                        var p = Save(go, $"{PrefabDir}/{name}.prefab");
                        if (kind == "twall") kit.twall = p; else kit.jersey = p;
                        break;
                    }
                    default:
                    {
                        Lods(go, 0.1f, 0.01f);
                        var p = Save(go, $"{PrefabDir}/{name}.prefab");
                        if (name == "Prop_StreetLamp") kit.streetLamp = p;
                        else if (name == "Prop_TrafficLight") kit.trafficLight = p;
                        else if (name == "Prop_Bench") kit.bench = p;
                        break;
                    }
                }
            }
            kit.cars = cars.ToArray();
            kit.wrecks = wrecks.ToArray();
            kit.trees = trees.Where(t => t).ToArray();
        }

        // ------------------------------------------------------------------ roads, facades, terrain
        static void CityMaterials(CityKit kit)
        {
            kit.roadLocal = Textured("CK_RoadLocal", "RoadLocal", Color.white);
            kit.roadArterial = Textured("CK_RoadArterial", "RoadArterial", Color.white);
            kit.roadHighway = Textured("CK_RoadHighway", "RoadHighway", Color.white);
            kit.asphalt = Textured("CK_Asphalt", "Asphalt", Color.white);
            kit.sidewalk = Textured("CK_Sidewalk", "Sidewalk", Color.white);
            kit.crosswalk = Textured("CK_Crosswalk", "Crosswalk", Color.white, true);
            kit.curb = Bld("BLD_Concrete");
            kit.concrete = Bld("BLD_Concrete");
            kit.curtainWall = Bld("BLD_CurtainWall");
            kit.gravel = Bld("BLD_Gravel");
            kit.stone = Bld("BLD_Stone");
            kit.metalDark = Bld("BLD_MetalDark");
            kit.galvanized = Bld("BLD_Galvanized");
            kit.corrugated = Bld("BLD_Corrugated");
            kit.corrugatedRed = Bld("BLD_Corrugated_Red");
            kit.runway = AssetDatabase.LoadAssetAtPath<Material>(Gen + "/Materials/M_Runway.mat");
            kit.brick = new[] { Textured("CK_FacadeBrick", "FacadeBrick", Color.white), Textured("CK_FacadeBrick_Dark", "FacadeBrick", Hex("a49a96")),
                                Textured("CK_FacadeBrick_Warm", "FacadeBrick", Hex("e6c2a8")) };
            kit.plaster = new[] { Textured("CK_FacadePlaster_Cream", "FacadePlaster", Hex("efe0c0")), Textured("CK_FacadePlaster_Sage", "FacadePlaster", Hex("c6d0b6")),
                                  Textured("CK_FacadePlaster_Terracotta", "FacadePlaster", Hex("dca684")), Textured("CK_FacadePlaster_White", "FacadePlaster", Color.white),
                                  Textured("CK_FacadePlaster_Blue", "FacadePlaster", Hex("bccad8")) };
            kit.facadeConcrete = new[] { Textured("CK_FacadeConcrete", "FacadeConcrete", Color.white), Textured("CK_FacadeConcrete_Warm", "FacadeConcrete", Hex("e2d8c6")),
                                         Textured("CK_FacadeConcrete_Dark", "FacadeConcrete", Hex("a6a8aa")) };
            kit.storefront = new[] { Textured("CK_Storefront_Red", "Storefront", Hex("e6b0a8")), Textured("CK_Storefront_Green", "Storefront", Hex("b8d4b8")),
                                     Textured("CK_Storefront_Blue", "Storefront", Hex("b4c6e0")), Textured("CK_Storefront_Cream", "Storefront", Color.white) };
            var terrain = AssetDatabase.LoadAssetAtPath<Material>($"{MatDir}/M_Terrain.mat");
            var tsh = Shader.Find("HDRP/TerrainLit");
            if (terrain == null && tsh != null)
            {
                terrain = new Material(tsh) { name = "M_Terrain" };
                AssetDatabase.CreateAsset(terrain, $"{MatDir}/M_Terrain.mat");
            }
            if (terrain != null)
            {
                // the runtime-built terrain needs these variants compiled into the player (shader_feature keywords)
                terrain.EnableKeyword("_TERRAIN_8_LAYERS");
                terrain.EnableKeyword("_NORMALMAP");
                terrain.EnableKeyword("_MASKMAP");
                terrain.enableInstancing = true;
                EditorUtility.SetDirty(terrain);
            }
            kit.terrainMaterial = terrain;
            kit.curtain = new[]
            {
                Bld("BLD_CurtainWall"), Tinted("CK_Curtain_Blue", "BLD_CurtainWall", Hex("a8c4ec")), Tinted("CK_Curtain_Green", "BLD_CurtainWall", Hex("b4dcc8")),
                Tinted("CK_Curtain_Bronze", "BLD_CurtainWall", Hex("e8c8a0")), Tinted("CK_Curtain_Silver", "BLD_CurtainWall", Hex("e8eef2")),
            };
        }

        static void TerrainLayers(CityKit kit)
        {
            var defs = new (string stem, float tile, float smooth)[]
            {
                ("Grass", 6f, 0.1f), ("Meadow", 8f, 0.1f), ("Dirt", 5f, 0.15f), ("Rock", 12f, 0.25f), ("Paving", 4f, 0.2f), ("LotGravel", 6f, 0.12f),
            };
            var layers = new List<TerrainLayer>();
            foreach (var (stem, tile, smooth) in defs)
            {
                string path = $"{Gen}/TerrainLayers/TL_{stem}.terrainlayer";
                var tl = AssetDatabase.LoadAssetAtPath<TerrainLayer>(path);
                if (tl == null)
                {
                    tl = new TerrainLayer();
                    AssetDatabase.CreateAsset(tl, path);
                }
                tl.diffuseTexture = T($"T_{stem}_BaseColor");
                tl.normalMapTexture = T($"T_{stem}_Normal");
                tl.maskMapTexture = T($"T_{stem}_Mask");
                tl.tileSize = new Vector2(tile, tile);
                tl.normalScale = 1f;
                tl.smoothness = smooth;
                tl.metallic = 0f;
                tl.maskMapRemapMin = Vector4.zero;
                tl.maskMapRemapMax = Vector4.one;
                EditorUtility.SetDirty(tl);
                layers.Add(tl);
            }
            kit.layers = layers.ToArray();
        }

        // ------------------------------------------------------------------ building variants
        static readonly (string type, (string from, string to)[][] swaps)[] Variants =
        {
            ("Building_Cottage", new[] { new[] { ("BLD_Siding_Blue", "BLD_Siding_Yellow") }, new[] { ("BLD_Siding_Blue", "BLD_Siding_White"), ("BLD_Shingle", "BLD_Shingle_Red") },
                                         new[] { ("BLD_Shingle", "BLD_Shingle_Red"), ("BLD_TrimGreen", "BLD_TrimRed") } }),
            ("Building_House", new[] { new[] { ("BLD_Brick", "BLD_BrickDark"), ("BLD_Siding_White", "BLD_Siding_Blue") }, new[] { ("BLD_Siding_White", "BLD_Siding_Yellow"), ("BLD_Shingle", "BLD_Shingle_Red") } }),
            ("Building_Shop", new[] { new[] { ("BLD_Brick", "BLD_BrickDark"), ("BLD_Fabric_Red", "BLD_Fabric") } }),
            ("Building_Apartment", new[] { new[] { ("BLD_Concrete", "BLD_Plaster_Cream"), ("BLD_Plaster_Terracotta", "BLD_Plaster_Sage") },
                                           new[] { ("BLD_Concrete", "BLD_Plaster_Sage"), ("BLD_Plaster_Terracotta", "BLD_Plaster_White") } }),
            ("Building_Office", new[] { new[] { ("BLD_Stone", "BLD_ConcreteDark") } }),
            ("Building_Warehouse", new[] { new[] { ("BLD_Corrugated", "BLD_Corrugated_Red"), ("BLD_Corrugated_Red", "BLD_Galvanized") } }),
            ("Building_Skyscraper", new (string, string)[0][]),
        };

        static void BuildingVariants(CityKit kit)
        {
            kit.buildings.Clear();
            foreach (var (type, swaps) in Variants)
            {
                var basePrefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{BldPrefabDir}/{type}.prefab");
                if (basePrefab == null) { Debug.LogWarning("[City] missing building prefab " + type); continue; }
                AddDef(kit, type, type, basePrefab);
                for (int k = 0; k < swaps.Length; k++)
                {
                    var go = (GameObject)PrefabUtility.InstantiatePrefab(basePrefab);
                    PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
                    foreach (var r in go.GetComponentsInChildren<MeshRenderer>(true))
                        r.sharedMaterials = r.sharedMaterials.Select(m =>
                        {
                            if (m == null) return m;
                            foreach (var (from, to) in swaps[k])
                                if (m.name == "M_" + from) { var t = Bld(to); return t ? t : m; }
                            return m;
                        }).ToArray();
                    string vn = $"{type}_v{k + 1}";
                    go.name = vn;
                    var p = Save(go, $"{BldPrefabDir}/Variants/{vn}.prefab");
                    AddDef(kit, vn, type, p);
                }
            }
        }

        static void AddDef(CityKit kit, string name, string type, GameObject prefab)
        {
            var mf = prefab.transform.Find(type + "_LOD0")?.GetComponent<MeshFilter>();
            var b = mf ? mf.sharedMesh.bounds : new Bounds(Vector3.zero, Vector3.one * 10f);
            kit.buildings.Add(new CityKit.BuildingDef
            {
                name = name, type = type, prefab = prefab,
                min = new Vector2(b.min.x, b.min.z), max = new Vector2(b.max.x, b.max.z), height = b.max.y,
            });
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
