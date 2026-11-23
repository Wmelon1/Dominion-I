// Dominion I project builder: texture settings, HDRP materials, FBX import settings, animator controllers,
// prefabs, the Title / Baseplate (Sandbox) / War scenes and the Windows player.
// Menu: Dominion > ...   Batch: -executeMethod Dominion.EditorTools.DominionBuilder.BatchAll
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using MechKit;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using static Dominion.EditorTools.MiniJson;
using Object = UnityEngine.Object;

namespace Dominion.EditorTools
{
    public static class DominionBuilder
    {
        const string Art = "Assets/Dominion/Art";
        const string Gen = "Assets/Dominion/Generated";
        const string ScenePath = "Assets/Dominion/Scenes/Baseplate.unity";
        const string WarScenePath = "Assets/Dominion/Scenes/War.unity";
        const string TitleScenePath = "Assets/Dominion/Scenes/Title.unity";
        static readonly string[] AllScenes = { TitleScenePath, ScenePath, WarScenePath };
        const string TemplateScene = "Assets/OutdoorsScene.unity";
        const string VfxDir = "Assets/Dominion/Resources/Dominion/VFX";
        static Dictionary<string, Texture2D> tex = new Dictionary<string, Texture2D>();
        static PhysicsMaterial noFriction;

        static readonly Dictionary<string, string> DisplayNames = new Dictionary<string, string>
        {
            { "Tank_Scout", "Scout Tank" }, { "Tank_Medium", "Medium Tank" }, { "Tank_Heavy", "Heavy Tank" },
            { "Tank_Artillery", "Artillery SPG" }, { "Tank_AntiAir", "Anti-Air SPAAG" },
            { "Vehicle_Mule", "Mule Cargo Truck" }, { "Vehicle_Bastion", "Bastion MRAP" }, { "Vehicle_Carrier", "Carrier APC" },
            { "Aircraft_Kestrel", "Kestrel Biplane" }, { "Aircraft_Falcon", "Falcon Biplane" }, { "Aircraft_Lancer", "Lancer Jet" },
            { "Aircraft_Saber", "Saber Jet" }, { "Aircraft_Wraith", "Wraith Fighter" },
            { "Mech_Aegis", "Aegis Mech" }, { "Mech_Halberd", "Halberd Mech" }, { "Mech_Thunderhead", "Thunderhead Mech" },
        };

        // ------------------------------------------------------------------ entry points
        [MenuItem("Dominion/1. Set Up Assets (materials, prefabs)")]
        public static void SetupAssets()
        {
            foreach (var f in new[] { Gen + "/Materials", Gen + "/Prefabs", Gen + "/Animation", Gen + "/Physics",
                         "Assets/Dominion/Resources/Dominion", "Assets/Dominion/Scenes" })
                EnsureFolder(f);
            ConfigureTextures();
            noFriction = AssetDatabase.LoadAssetAtPath<PhysicsMaterial>(Gen + "/Physics/NoFriction.asset");
            if (noFriction == null)
            {
                noFriction = new PhysicsMaterial("NoFriction")
                {
                    dynamicFriction = 0f, staticFriction = 0f, bounciness = 0f,
                    frictionCombine = PhysicsMaterialCombine.Minimum, bounceCombine = PhysicsMaterialCombine.Minimum
                };
                AssetDatabase.CreateAsset(noFriction, Gen + "/Physics/NoFriction.asset");
            }
            Unlit("Assets/Dominion/Resources/Dominion/M_Tracer.mat", null, new Color(1f, 0.72f, 0.32f) * 9f, false);
            Unlit("Assets/Dominion/Resources/Dominion/M_Shockwave.mat", null, new Color(0.78f, 0.62f, 0.42f) * 0.55f, true);
            FxMat("M_FX_Smoke", T("T_FX_Smoke"), false, 1f, 1.5f);
            FxMat("M_FX_Fire", T("T_FX_Fire"), true, 5f, 0.8f);
            FxMat("M_FX_Spark", T("T_FX_Spark"), true, 7f, 0.1f);
            FxMat("M_FX_Ring", T("T_FX_Ring"), true, 2.5f, 0.3f);
            FxMat("M_FX_DustRing", T("T_FX_DustRing"), false, 1f, 0.3f);
            FxMat("M_FX_Debris", T("T_FX_Debris"), false, 0.8f, 0.05f);
            var crackMat = MaterialAt($"{VfxDir}/M_FX_Cracks.mat", "HDRP/Decal");
            crackMat.SetTexture("_BaseColorMap", T("T_FX_Cracks"));
            crackMat.SetTexture("_NormalMap", T("T_FX_Cracks_Normal"));
            crackMat.SetFloat("_DecalBlend", 1f);
            crackMat.SetFloat("_NormalBlendSrc", 1f);
            // only colour + normal, both masked by the texture alpha: no square patch of changed shine around the cracks
            foreach (var (prop, v) in new[] { ("_AffectAlbedo", 1f), ("_AffectNormal", 1f), ("_AffectMetal", 0f), ("_AffectAO", 0f),
                         ("_AffectSmoothness", 0f), ("_AffectEmission", 0f), ("_MaskBlendSrc", 1f) })
                if (crackMat.HasProperty(prop)) crackMat.SetFloat(prop, v);
            HDMaterial.ValidateMaterial(crackMat);
            EditorUtility.SetDirty(crackMat);

            var vehicleMats = new Dictionary<string, Material>();
            foreach (var kit in new[] { "Tanks", "Transports", "Aircraft" })
                foreach (var kv in KitMaterials(kit)) vehicleMats[kv.Key] = kv.Value;
            foreach (var kit in new[] { "Tanks", "Transports", "Aircraft" })
                foreach (var fbx in Directory.GetFiles($"{Art}/{kit}", "*.fbx"))
                    BuildVehiclePrefab(fbx.Replace('\\', '/'), kit, vehicleMats);
            var soldierMats = KitMaterials("Soldiers");
            foreach (var fbx in Directory.GetFiles($"{Art}/Soldiers", "*.fbx"))
                BuildSoldierPrefab(fbx.Replace('\\', '/'), soldierMats);
            foreach (var m in new[] { "Aegis", "Halberd", "Thunderhead" })
                BuildMechPrefab(m);
            BuildingKitBuilder.SetupBuildings();
            CityKitBuilder.Setup();
            DroneKitBuilder.Setup();
            AirshipBuilder.Setup();
            AssetDatabase.SaveAssets();
            Debug.Log("[Dominion] assets ready");
        }

        /// <summary>The template's sun, sky, fog and camera, with everything else removed.</summary>
        static UnityEngine.SceneManagement.Scene EnvironmentScene()
        {
            var scene = EditorSceneManager.OpenScene(TemplateScene, OpenSceneMode.Single);
            var keep = new HashSet<string> { "Sun", "Sky and Fog Volume", "Main Camera", "StaticLightingSky" };
            foreach (var root in scene.GetRootGameObjects())
                if (!keep.Contains(root.name)) Object.DestroyImmediate(root);
            return scene;
        }

        /// <summary>Square concrete baseplate, 'size' metres across.</summary>
        static GameObject Ground(float size)
        {
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = $"Baseplate ({size / 1000f:0.#} km)";
            ground.transform.localScale = new Vector3(size / 10f, 1f, size / 10f);
            string matPath = size > 2500f ? Gen + "/Materials/M_Baseplate_Large.mat" : Gen + "/Materials/M_Baseplate.mat";
            var gm = Lit(matPath);
            SetLitMaps(gm, T("T_Baseplate_BaseColor"), null, T("T_Baseplate_Normal"), new Color(0.52f, 0.52f, 0.52f), 0f, 0.25f);
            gm.SetTextureScale("_BaseColorMap", new Vector2(size / 8f, size / 8f));
            HDMaterial.ValidateMaterial(gm);
            ground.GetComponent<Renderer>().sharedMaterial = gm;
            ground.isStatic = true;
            return ground;
        }

        static void Runway(Vector3 center, Vector3 scale, float yaw = 0f)
        {
            var runway = GameObject.CreatePrimitive(PrimitiveType.Plane);
            runway.name = "Airstrip";
            Object.DestroyImmediate(runway.GetComponent<Collider>());
            runway.transform.SetPositionAndRotation(center, Quaternion.Euler(0f, yaw, 0f));
            runway.transform.localScale = scale;
            var rm = Lit(Gen + "/Materials/M_Runway.mat");
            SetLitMaps(rm, T("T_Runway_BaseColor"), null, null, Color.white, 0f, 0.2f);
            rm.SetTextureScale("_BaseColorMap", new Vector2(1f, 15f));
            HDMaterial.ValidateMaterial(rm);
            runway.GetComponent<Renderer>().sharedMaterial = rm;
            runway.isStatic = true;
        }

        static GameObject PlacePrefab(string name, Transform parent, Vector3 pos, float yaw)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{Gen}/Prefabs/{name}.prefab");
            if (prefab == null) { Debug.LogError("[Dominion] missing prefab " + name); return null; }
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
            var v = go.GetComponent<Vehicle>();
            if (v != null) pos.y += v.RestHeight + 0.02f;
            else pos.y += 0.02f;
            go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            return go;
        }

        static void ApplyPlayerSettings()
        {
            EditorBuildSettings.scenes = AllScenes.Where(File.Exists).Select(p => new EditorBuildSettingsScene(p, true)).ToArray();
            PlayerSettings.productName = "Dominion I";
            PlayerSettings.companyName = "Dominion Studio";
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = 1600;
            PlayerSettings.defaultScreenHeight = 900;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;
        }

        [MenuItem("Dominion/2. Build Baseplate Scene")]
        public static void BuildScene()
        {
            var scene = EnvironmentScene();
            Ground(2000f);
            Runway(new Vector3(160f, 0.02f, 650f), new Vector3(10f, 1f, 150f));

            var vehicles = new GameObject("Vehicles").transform;
            void Place(string name, float x, float z, float yaw = 0f)
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{Gen}/Prefabs/{name}.prefab");
                if (prefab == null) { Debug.LogError("[Dominion] missing prefab " + name); return; }
                var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, vehicles);
                var v = go.GetComponent<Vehicle>();
                float y = v != null ? v.RestHeight + 0.02f : 0f;
                go.transform.SetPositionAndRotation(new Vector3(x, y, z), Quaternion.Euler(0f, yaw, 0f));
            }
            string[] tanks = { "Tank_Scout", "Tank_Medium", "Tank_Heavy", "Tank_Artillery", "Tank_AntiAir" };
            for (int i = 0; i < tanks.Length; i++) Place(tanks[i], -48f + i * 24f, 18f);
            Place("Vehicle_Mule", -30f, 44f);
            Place("Vehicle_Bastion", 0f, 44f);
            Place("Vehicle_Carrier", 30f, 44f);
            Place("Mech_Aegis", -26f, 74f);
            Place("Mech_Halberd", 0f, 74f);
            Place("Mech_Thunderhead", 26f, 74f);
            string[] planes = { "Aircraft_Kestrel", "Aircraft_Falcon", "Aircraft_Lancer", "Aircraft_Saber", "Aircraft_Wraith" };
            for (int i = 0; i < planes.Length; i++) Place(planes[i], 122f + i * 19f, -40f);

            var soldiers = new List<SoldierController>();
            foreach (var (name, x) in new[] { ("Soldier_Male", 0f), ("Soldier_Female", 2.5f) })
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{Gen}/Prefabs/{name}.prefab");
                var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                go.transform.SetPositionAndRotation(new Vector3(x, 0.02f, -12f), Quaternion.identity);
                soldiers.Add(go.GetComponent<SoldierController>());
            }

            var cam = GameObject.Find("Main Camera");
            cam.transform.SetPositionAndRotation(new Vector3(0f, 3f, -17f), Quaternion.Euler(12f, 0f, 0f));
            cam.GetComponent<Camera>().farClipPlane = 6000f;
            var rigCam = GetOrAdd<CameraRig>(cam);

            var game = new GameObject("Game");
            var director = game.AddComponent<GameDirector>();
            director.soldiers = soldiers.ToArray();
            director.cameraRig = rigCam;
            game.AddComponent<AutoTest>();

            EditorSceneManager.SaveScene(scene, ScenePath);
            ApplyPlayerSettings();
            AssetDatabase.SaveAssets();
            Debug.Log("[Dominion] scene saved: " + ScenePath);
        }

        // ------------------------------------------------------------------ War scene
        static readonly string[] WarKeys =
        {
            "Soldier_Male", "Soldier_Female", "Tank_Scout", "Tank_Medium", "Tank_Heavy", "Tank_Artillery", "Tank_AntiAir",
            "Vehicle_Mule", "Vehicle_Bastion", "Vehicle_Carrier", "Aircraft_Kestrel", "Aircraft_Falcon", "Aircraft_Lancer",
            "Aircraft_Saber", "Aircraft_Wraith", "Mech_Aegis", "Mech_Halberd", "Mech_Thunderhead",
            "Drone_Wasp", "Drone_Mender", "Drone_Kite", "Airship_Leviathan", "Skyship_Sentinel", "Parachute",
        };

        [MenuItem("Dominion/4. Build War Scene")]
        public static void BuildWarScene()
        {
            var scene = EnvironmentScene();
            // the battlefield is a new procedurally generated city every time (or the chosen seed's city)
            var gen = new GameObject("City Generator").AddComponent<CityGenerator>();
            gen.kit = AssetDatabase.LoadAssetAtPath<CityKit>(Gen + "/CityKit.asset");
            if (gen.kit == null) Debug.LogError("[Dominion] CityKit asset missing: run Dominion > 7. Set Up City Kit");

            var cam = GameObject.Find("Main Camera");
            cam.transform.SetPositionAndRotation(new Vector3(0f, 4f, -245f), Quaternion.Euler(10f, 0f, 0f));
            cam.GetComponent<Camera>().farClipPlane = 12000f;
            var rigCam = GetOrAdd<CameraRig>(cam);

            var game = new GameObject("Game");
            var director = game.AddComponent<GameDirector>();
            director.cameraRig = rigCam;
            var war = game.AddComponent<WarManager>();
            war.prefabs = WarKeys.Select(k => new WarManager.PrefabEntry
            {
                key = k, prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{Gen}/Prefabs/{k}.prefab")
            }).ToList();
            foreach (var e in war.prefabs) if (e.prefab == null) Debug.LogError("[Dominion] war prefab missing: " + e.key);
            game.AddComponent<AutoTest>();
            EditorSceneManager.SaveScene(scene, WarScenePath);
            ApplyPlayerSettings();
            Debug.Log("[Dominion] scene saved: " + WarScenePath);
        }

        /// <summary>
        /// (Previous War map, kept for reference) no-man's-land cover on the flat baseplate: T-wall lines, L-bunkers,
        /// shipping containers and jersey barriers, point-mirrored so both sides got the same cover.
        /// </summary>
        static void BuildCover()
        {
            var root = new GameObject("Cover").transform;
            var concrete = Lit(Gen + "/Materials/M_Concrete.mat");
            SetLitMaps(concrete, T("T_Baseplate_BaseColor"), null, T("T_Baseplate_Normal"), new Color(0.78f, 0.77f, 0.73f), 0f, 0.2f);
            concrete.SetTextureScale("_BaseColorMap", new Vector2(0.6f, 0.6f));
            HDMaterial.ValidateMaterial(concrete);
            var boxColors = new[] { new Color(0.55f, 0.16f, 0.1f), new Color(0.12f, 0.27f, 0.45f), new Color(0.2f, 0.36f, 0.22f), new Color(0.72f, 0.45f, 0.12f) };
            var boxes = new Material[boxColors.Length];
            for (int i = 0; i < boxColors.Length; i++)
            {
                boxes[i] = Lit($"{Gen}/Materials/M_Container_{i}.mat");
                SetLitMaps(boxes[i], null, null, T("T_Baseplate_Normal"), boxColors[i], 0.55f, 0.32f);
                boxes[i].SetTextureScale("_NormalMap", new Vector2(2f, 1f));
                HDMaterial.ValidateMaterial(boxes[i]);
            }
            var rng = new System.Random(1337);
            float R(float a, float b) => a + (float)rng.NextDouble() * (b - a);
            int count = 0;
            void Piece(Vector3 p, float yaw, Vector3 size, Material m, bool cover)
            {
                foreach (bool mirror in new[] { false, true })
                {
                    var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    go.name = cover ? "Cover" : "Block";
                    go.transform.SetParent(root, false);
                    Vector3 pos = mirror ? new Vector3(-p.x, p.y, -p.z) : p;
                    go.transform.SetPositionAndRotation(pos + Vector3.up * (size.y * 0.5f), Quaternion.Euler(0f, mirror ? yaw + 180f : yaw, 0f));
                    go.transform.localScale = size;
                    go.GetComponent<Renderer>().sharedMaterial = m;
                    go.isStatic = true;
                    if (cover) go.AddComponent<CoverObject>();
                    count++;
                }
            }
            var wall = new Vector3(3.2f, 2.7f, 0.75f);
            for (float z = -185f; z <= -25f; z += 40f)
                for (float x = -270f; x <= 270f; x += 45f)
                {
                    if (rng.NextDouble() < 0.3) continue;
                    Vector3 c = new Vector3(x + R(-14f, 14f), 0f, z + R(-12f, 12f));
                    double kind = rng.NextDouble();
                    if (kind < 0.45)
                    {
                        // T-wall line facing the enemy
                        int n = rng.Next(2, 5);
                        float yaw = R(-22f, 22f);
                        Quaternion q = Quaternion.Euler(0f, yaw, 0f);
                        float step = wall.x + R(0.3f, 1.6f);
                        for (int i = 0; i < n; i++)
                            Piece(c + q * new Vector3((i - (n - 1) * 0.5f) * step, 0f, 0f), yaw, wall, concrete, true);
                    }
                    else if (kind < 0.7)
                    {
                        // shipping container, sometimes a second one stacked or alongside
                        var size = new Vector3(6.06f, 2.6f, 2.44f);
                        float yaw = R(0f, 180f);
                        var m = boxes[rng.Next(boxes.Length)];
                        Piece(c, yaw, size, m, true);
                        double extra = rng.NextDouble();
                        if (extra < 0.25) Piece(c + Vector3.up * 2.6f, yaw + R(-8f, 8f), size, boxes[rng.Next(boxes.Length)], false);
                        else if (extra < 0.45) Piece(c + Quaternion.Euler(0f, yaw, 0f) * new Vector3(0f, 0f, 2.7f), yaw, size, boxes[rng.Next(boxes.Length)], true);
                    }
                    else if (kind < 0.85)
                    {
                        // L-shaped bunker
                        float yaw = R(0f, 360f);
                        Quaternion q = Quaternion.Euler(0f, yaw, 0f);
                        Piece(c, yaw, new Vector3(6.4f, 2.7f, 0.75f), concrete, true);
                        Piece(c + q * new Vector3(3.6f, 0f, -2.8f), yaw + 90f, new Vector3(5.2f, 2.7f, 0.75f), concrete, true);
                    }
                    else
                    {
                        // low jersey barriers: hull-down cover for vehicles
                        float yaw = R(-30f, 30f);
                        Quaternion q = Quaternion.Euler(0f, yaw, 0f);
                        int n = rng.Next(2, 4);
                        for (int i = 0; i < n; i++)
                            Piece(c + q * new Vector3((i - (n - 1) * 0.5f) * 3.9f, 0f, 0f), yaw, new Vector3(3.6f, 0.95f, 0.7f), concrete, false);
                    }
                }
            Debug.Log($"[Dominion] cover pieces: {count}");
        }

        // ------------------------------------------------------------------ Title scene
        [MenuItem("Dominion/5. Build Title Scene")]
        public static void BuildTitleScene()
        {
            var scene = EnvironmentScene();
            Ground(2000f);
            var units = new GameObject("Showcase").transform;
            var blue = new List<GameObject>();
            var red = new List<GameObject>();
            void B(string n, float x, float z, float yaw) { var g = PlacePrefab(n, units, new Vector3(x, 0f, z), yaw); if (g) blue.Add(g); }
            void Rd(string n, float x, float z, float yaw) { var g = PlacePrefab(n, units, new Vector3(x, 0f, z), yaw); if (g) red.Add(g); }
            // two lines squaring up across the plate
            B("Tank_Heavy", -22f, -6f, 72f);
            B("Mech_Halberd", -34f, 12f, 80f);
            B("Tank_AntiAir", -40f, -22f, 60f);
            B("Aircraft_Wraith", -12f, 34f, 150f);
            for (int i = 0; i < 4; i++) B(i % 2 == 0 ? "Soldier_Male" : "Soldier_Female", -10f - (i % 2) * 2.5f, -14f + i * 3.2f, 80f);
            Rd("Tank_Medium", 24f, 8f, -100f);
            Rd("Mech_Thunderhead", 36f, -10f, -95f);
            Rd("Vehicle_Bastion", 30f, 24f, -120f);
            Rd("Aircraft_Saber", 14f, -36f, -30f);
            for (int i = 0; i < 4; i++) Rd(i % 2 == 0 ? "Soldier_Female" : "Soldier_Male", 11f + (i % 2) * 2.5f, -6f + i * 3.2f, -100f);

            var focus = new GameObject("Focus").transform;
            focus.position = new Vector3(0f, 2f, 0f);
            var cam = GameObject.Find("Main Camera");
            cam.GetComponent<Camera>().farClipPlane = 4000f;
            var ts = GetOrAdd<TitleScreen>(cam);
            ts.focus = focus;
            ts.blueSide = blue.ToArray();
            ts.redSide = red.ToArray();
            EditorSceneManager.SaveScene(scene, TitleScenePath);
            ApplyPlayerSettings();
            Debug.Log("[Dominion] scene saved: " + TitleScenePath);
        }

        [MenuItem("Dominion/3. Build Windows Player")]
        public static void BuildPlayerMenu() => BuildPlayer();

        public static bool BuildPlayer()
        {
            string exe = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Build", "Dominion I.exe"));
            PlayerSettings.enableFrameTimingStats = true;
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = AllScenes,
                locationPathName = exe,
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.None,
            });
            var s = report.summary;
            Debug.Log($"[Dominion] build {s.result}: {s.totalSize / 1e6:0} MB, {s.totalErrors} errors, {s.totalTime} -> {exe}");
            return s.result == BuildResult.Succeeded;
        }

        static void BuildScenes()
        {
            BuildScene();
            BuildWarScene();
            BuildTitleScene();
            ApplyPlayerSettings();
            AssetDatabase.SaveAssets();
        }

        public static void BatchSetup() => Run(() => { SetupAssets(); BuildScenes(); });
        public static void BatchBuild() => Run(() => { if (!BuildPlayer()) throw new Exception("player build failed"); });
        public static void BatchAll() => Run(() =>
        {
            SetupAssets();
            BuildScenes();
            if (!BuildPlayer()) throw new Exception("player build failed");
        });

        static void Run(Action a)
        {
            int code = 0;
            try { a(); }
            catch (Exception e)
            {
                Debug.LogError("[Dominion] FAILED: " + e);
                code = 1;
            }
            EditorApplication.Exit(code);
        }

        // ------------------------------------------------------------------ helpers
        static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }

        static TC GetOrAdd<TC>(GameObject go) where TC : Component
        {
            var c = go.GetComponent<TC>();
            return c ? c : go.AddComponent<TC>();
        }

        static Texture2D T(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            if (tex.TryGetValue(name, out var t)) return t;
            Debug.LogWarning("[Dominion] texture not found: " + name);
            return null;
        }

        static void ConfigureTextures()
        {
            var paths = AssetDatabase.FindAssets("t:Texture2D", new[] { Art, VfxDir }).Select(AssetDatabase.GUIDToAssetPath).ToList();
            AssetDatabase.StartAssetEditing();
            try
            {
                foreach (var path in paths)
                {
                    if (!(AssetImporter.GetAtPath(path) is TextureImporter ti)) continue;
                    string n = Path.GetFileNameWithoutExtension(path);
                    bool normal = n.EndsWith("_Normal");
                    bool linear = normal || n.EndsWith("_Mask") || n.EndsWith("_PM");
                    bool fx = n.Contains("MuzzleFlash") || n.Contains("Afterburner") || n.Contains("Banner") || n.Contains("PropBlur") || n.StartsWith("T_FX_");
                    var type = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                    int size = path.Contains("/Mechs/") || n.StartsWith("T_Baseplate") || n.StartsWith("T_Runway") ? 4096 : 2048;
                    if (n.StartsWith("T_FX_")) size = n.StartsWith("T_FX_Cracks") ? 1024 : 512 * 2;
                    bool alpha = fx || n.Contains("Emblem");
                    if (ti.textureType == type && ti.sRGBTexture == !linear && ti.maxTextureSize == size && ti.alphaIsTransparency == alpha)
                        continue;
                    ti.textureType = type;
                    ti.sRGBTexture = !linear;
                    ti.alphaIsTransparency = alpha;
                    ti.maxTextureSize = size;
                    ti.wrapMode = fx ? TextureWrapMode.Clamp : TextureWrapMode.Repeat;
                    ti.anisoLevel = n.StartsWith("T_Baseplate") || n.StartsWith("T_Runway") ? 8 : 4;
                    ti.mipmapEnabled = true;
                    ti.SaveAndReimport();
                }
            }
            finally { AssetDatabase.StopAssetEditing(); }
            tex.Clear();
            foreach (var path in paths)
            {
                string n = Path.GetFileNameWithoutExtension(path);
                if (!tex.ContainsKey(n)) tex[n] = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            }
        }

        static Material MaterialAt(string path, string shader)
        {
            var sh = Shader.Find(shader);
            if (sh == null) throw new Exception("shader not found: " + shader);
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                m = new Material(sh) { name = Path.GetFileNameWithoutExtension(path) };
                AssetDatabase.CreateAsset(m, path);
            }
            else if (m.shader != sh) m.shader = sh;
            return m;
        }

        static Material Lit(string path) => MaterialAt(path, "HDRP/Lit");

        /// <summary>Particle material on the Dominion/Particle shader (alpha-blended or additive).</summary>
        static Material FxMat(string name, Texture2D t, bool additive, float brightness, float soft)
        {
            var m = MaterialAt($"{VfxDir}/{name}.mat", "Dominion/Particle");
            m.SetTexture("_MainTex", t);
            m.SetColor("_Tint", Color.white);
            m.SetFloat("_Brightness", brightness);
            m.SetFloat("_SoftDistance", soft);
            m.SetFloat("_SrcBlend", additive ? 1f : 5f);
            m.SetFloat("_DstBlend", additive ? 1f : 10f);
            m.renderQueue = 3000;
            EditorUtility.SetDirty(m);
            return m;
        }

        static void SetLitMaps(Material m, Texture2D baseMap, Texture2D mask, Texture2D normal, Color color, float metal, float smooth)
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
            HDMaterial.ValidateMaterial(m);
            EditorUtility.SetDirty(m);
        }

        /// <summary>Exposure-independent glowing material (tracers, flashes, afterburners).</summary>
        static Material Unlit(string path, Texture2D emissiveMap, Color emission, bool additive)
        {
            var m = MaterialAt(path, "HDRP/Unlit");
            m.SetColor("_UnlitColor", new Color(0f, 0f, 0f, 1f));
            m.SetTexture("_UnlitColorMap", null);
            m.SetTexture("_EmissiveColorMap", emissiveMap);
            HDMaterial.SetEmissiveColor(m, emission);
            m.SetFloat("_EmissiveExposureWeight", 0f);
            if (additive)
            {
                m.SetFloat("_SurfaceType", 1f);
                m.SetFloat("_BlendMode", 1f);
                m.SetFloat("_DoubleSidedEnable", 1f);
            }
            HDMaterial.ValidateMaterial(m);
            EditorUtility.SetDirty(m);
            return m;
        }

        static Color LinearToColor(List<object> c, float a = 1f) =>
            c != null && c.Count >= 3 ? new Color(F(c[0]), F(c[1]), F(c[2]), a).gamma : Color.white;

        static Dictionary<string, Material> KitMaterials(string kit)
        {
            var result = new Dictionary<string, Material>();
            string json = $"{Art}/{kit}/materials.json";
            if (!File.Exists(json)) return result;
            foreach (var kv in Obj(Parse(File.ReadAllText(json))))
                result[kv.Key] = MakeMaterial(kv.Key, Obj(kv.Value));
            return result;
        }

        static Material MakeMaterial(string name, Dictionary<string, object> info)
        {
            string path = $"{Gen}/Materials/M_{name.Replace("MAT_", "")}.mat";
            var texs = Obj(Get(info, "textures"));
            switch (name)
            {
                case "MAT_MuzzleFlash":
                    return Unlit(path, T("T_MuzzleFlash_PM"), new Color(1f, 0.9f, 0.7f) * 3.5f, true);
                case "MAT_Afterburner":
                    return Unlit(path, T("T_Afterburner_PM"), new Color(1f, 0.95f, 0.9f) * 3f, true);
                case "MAT_PropBlur":
                {
                    var m = Lit(path);
                    SetLitMaps(m, T("T_PropBlur"), null, null, new Color(1f, 1f, 1f, 0.8f), 0f, 0.3f);
                    m.SetFloat("_DoubleSidedEnable", 1f);
                    HDMaterial.SetSurfaceType(m, true);
                    return m;
                }
                case "MAT_CanopyGlass":
                {
                    var m = Lit(path);
                    SetLitMaps(m, null, null, null, LinearToColor(Arr(Get(info, "color")), 0.35f), 0f, 0.96f);
                    m.SetFloat("_DoubleSidedEnable", 1f);
                    HDMaterial.SetSurfaceType(m, true);
                    return m;
                }
                case "MAT_Emblem":
                {
                    var m = Lit(path);
                    SetLitMaps(m, T("T_Emblem"), null, null, Color.white, 0f, 0.35f);
                    HDMaterial.SetAlphaClipping(m, true);
                    HDMaterial.SetAlphaCutoff(m, 0.5f);
                    HDMaterial.ValidateMaterial(m);
                    return m;
                }
            }
            var mat = Lit(path);
            string baseTex = S(Get(texs, "BaseColor"));
            if (baseTex.Length > 0)
            {
                string stem = baseTex.Substring(0, baseTex.Length - "_BaseColor".Length);
                SetLitMaps(mat, T(stem + "_BaseColor"), T(stem + "_Mask"), T(stem + "_Normal"), Color.white, 1f, 1f);
            }
            else
            {
                SetLitMaps(mat, null, null, null, LinearToColor(Arr(Get(info, "color"))), F(Get(info, "metallic")),
                    1f - F(Get(info, "roughness"), 0.5f));
            }
            return mat;
        }

        // ------------------------------------------------------------------ model import
        static GameObject ImportModel(string path, Dictionary<string, Material> remap, bool anim, Func<string, bool> loop)
        {
            var imp = (ModelImporter)AssetImporter.GetAtPath(path);
            imp.useFileScale = true;
            imp.globalScale = 1f;
            imp.importBlendShapes = true;
            imp.importVisibility = false;
            imp.importCameras = false;
            imp.importLights = false;
            imp.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            imp.animationType = ModelImporterAnimationType.Generic;
            imp.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            imp.optimizeGameObjects = false;
            imp.importAnimation = anim;
            imp.importNormals = ModelImporterNormals.Import;
            imp.importTangents = ModelImporterTangents.CalculateMikk;
            imp.meshCompression = ModelImporterMeshCompression.Off;
            foreach (var kv in remap)
                imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key), kv.Value);
            imp.SaveAndReimport();
            if (anim)
            {
                var clips = imp.defaultClipAnimations;
                foreach (var c in clips)
                {
                    int k = c.takeName.LastIndexOf('|');
                    c.name = k >= 0 ? c.takeName.Substring(k + 1) : c.takeName;
                    c.loopTime = loop(c.name);
                    c.lockRootRotation = c.lockRootHeightY = c.lockRootPositionXZ = false;
                }
                imp.clipAnimations = clips;
                imp.SaveAndReimport();
            }
            return AssetDatabase.LoadAssetAtPath<GameObject>(path);
        }

        static Dictionary<string, AnimationClip> Clips(string path) =>
            AssetDatabase.LoadAllAssetsAtPath(path).OfType<AnimationClip>().Where(c => !c.name.StartsWith("__preview"))
                .GroupBy(c => c.name).ToDictionary(g => g.Key, g => g.First());

        /// <summary>Model-space bounds of the visible meshes in the rest pose (effects meshes excluded).</summary>
        static Bounds MeshBounds(GameObject go)
        {
            bool any = false;
            var b = new Bounds();
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                string n = r.name;
                if (n.Contains("MuzzleFlash") || n.Contains("PropBlur") || n.Contains("Afterburner") || n.Contains("JetFlame") ||
                    n.Contains("_Banner_")) continue;
                Mesh mesh = r is SkinnedMeshRenderer smr ? smr.sharedMesh : (r.GetComponent<MeshFilter>() ? r.GetComponent<MeshFilter>().sharedMesh : null);
                if (mesh == null) continue;
                var mb = mesh.bounds;
                for (int i = 0; i < 8; i++)
                {
                    var c = mb.center + Vector3.Scale(mb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                    var p = go.transform.InverseTransformPoint(r.transform.TransformPoint(c));
                    if (!any) { b = new Bounds(p, Vector3.zero); any = true; }
                    else b.Encapsulate(p);
                }
            }
            return b;
        }

        static GameObject Instance(GameObject model, string name)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(model);
            go.name = name;
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            return go;
        }

        static void SavePrefab(GameObject go, string name)
        {
            PrefabUtility.SaveAsPrefabAsset(go, $"{Gen}/Prefabs/{name}.prefab");
            Object.DestroyImmediate(go);
        }

        /// <summary>Dynamic rigid body; the hull box starts above the wheel centres so only the suspension touches the ground.</summary>
        static void AddBody(GameObject go, Bounds b, float mass, float clearance)
        {
            var rb = GetOrAdd<Rigidbody>(go);
            rb.mass = mass;
            rb.useGravity = true;
            rb.isKinematic = true;
            rb.freezeRotation = false;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            rb.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;
            rb.linearDamping = 0f;
            rb.angularDamping = 0.6f;
            float bottom = Mathf.Max(b.min.y, clearance);
            var bc = go.AddComponent<BoxCollider>();
            bc.center = new Vector3(b.center.x, (bottom + b.max.y) * 0.5f, b.center.z);
            bc.size = new Vector3(b.size.x, Mathf.Max(0.3f, b.max.y - bottom), b.size.z);
            bc.sharedMaterial = noFriction;
        }

        /// <summary>Highest wheel-centre height (vehicle space) among the named wheel bones, plus a margin.</summary>
        static float Clearance(GameObject go, IEnumerable<string> wheelBones, float margin)
        {
            float top = float.MinValue;
            var set = new HashSet<string>(wheelBones);
            foreach (var t in go.GetComponentsInChildren<Transform>(true))
                if (set.Contains(t.name)) top = Mathf.Max(top, go.transform.InverseTransformPoint(t.position).y);
            return top > float.MinValue ? top + margin : 0f;
        }

        static void BuildVehiclePrefab(string fbx, string kit, Dictionary<string, Material> mats)
        {
            string name = Path.GetFileNameWithoutExtension(fbx);
            var meta = Obj(Parse(File.ReadAllText(Path.ChangeExtension(fbx, ".json"))));
            var props = Obj(Get(meta, "props"));
            var bones = new HashSet<string>(Arr(Get(meta, "bones")).Select(o => S(Arr(o)[0])));
            var model = ImportModel(fbx, mats, false, _ => false);
            var go = Instance(model, name);
            var anim = go.GetComponent<Animator>();
            if (anim) Object.DestroyImmediate(anim);
            foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                smr.updateWhenOffscreen = smr.name.Contains("MuzzleFlash") || smr.name.Contains("PropBlur") || smr.name.Contains("Afterburner");
                smr.skinnedMotionVectors = true;
            }
            Bounds b = MeshBounds(go);
            string dn = DisplayNames.TryGetValue(name, out var d) ? d : name;
            string baseName = name.Substring(name.IndexOf('_') + 1);

            if (kit == "Aircraft")
            {
                var planeMass = new Dictionary<string, float> { { "Kestrel", 700f }, { "Falcon", 1900f }, { "Lancer", 7000f }, { "Saber", 8500f }, { "Wraith", 19000f } };
                var gearWheels = Obj(Get(props, "tk_wheels")).Keys;
                AddBody(go, b, planeMass.TryGetValue(baseName, out var pm) ? pm : 5000f, Clearance(go, gearWheels, 0.25f));
                var av = go.AddComponent<AircraftVehicle>();
                av.displayName = dn;
                av.unitKey = name;
                av.localBounds = b;
                foreach (var kv in Obj(Get(props, "tk_controls")))
                {
                    var c = Obj(kv.Value);
                    av.surfaces.Add(new AircraftVehicle.Surface { bone = kv.Key, axis = S(Get(c, "axis")), max = F(Get(c, "max"), 20f) });
                }
                foreach (var kv in Obj(Get(props, "tk_gears")))
                {
                    var c = Obj(kv.Value);
                    av.gears.Add(new AircraftVehicle.GearLeg { bone = kv.Key, axis = S(Get(c, "axis"), "x"), angle = F(Get(c, "angle"), 90f) });
                }
                var wheels = Obj(Get(props, "tk_wheels"));
                av.wheelBones = wheels.Keys.ToArray();
                av.wheelRadii = wheels.Values.Select(v => F(v, 0.3f)).ToArray();
                var can = Obj(Get(props, "tk_canopy"));
                av.canopyMode = S(Get(can, "mode"));
                av.canopyTravel = F(Get(can, "travel"), 0.8f);
                av.hasProp = bones.Contains("prop");
                av.muzzleBones = Arr(Get(props, "tk_muzzles")).Select(o => S(o)).ToArray();
                av.afterburnerBones = Arr(Get(props, "tk_afterburners")).Select(o => S(o)).ToArray();
                var fp = new Dictionary<string, float[]>
                {   // top speed, lift-off speed, thrust/weight, pitch, roll, yaw (deg/s), fire interval
                    { "Kestrel", new[] { 55f, 24f, 0.32f, 60f, 120f, 30f, 0.08f } },
                    { "Falcon", new[] { 78f, 30f, 0.36f, 58f, 140f, 28f, 0.06f } },
                    { "Lancer", new[] { 230f, 60f, 0.45f, 45f, 150f, 20f, 0.05f } },
                    { "Saber", new[] { 265f, 63f, 0.55f, 50f, 180f, 20f, 0.05f } },
                    { "Wraith", new[] { 320f, 68f, 0.95f, 60f, 220f, 24f, 0.025f } },
                };
                if (fp.TryGetValue(baseName, out var p))
                {
                    av.maxSpeed = p[0]; av.takeoffSpeed = p[1]; av.thrustToWeight = p[2];
                    av.pitchRate = p[3]; av.rollRate = p[4]; av.yawRate = p[5]; av.fireInterval = p[6];
                }
            }
            else if (Obj(Get(props, "tk_steer")).Count > 0 || (kit == "Transports" && !props.ContainsKey("tk_track_pitch")))
            {
                AddBody(go, b, baseName == "Mule" ? 11000f : 14000f, Clearance(go, Obj(Get(props, "tk_wheels")).Keys, 0.15f));
                var wv = go.AddComponent<WheeledVehicle>();
                wv.displayName = dn;
                wv.unitKey = name;
                wv.localBounds = b;
                var wheels = Obj(Get(props, "tk_wheels"));
                wv.wheelBones = wheels.Keys.ToArray();
                wv.wheelRadii = wheels.Values.Select(v => F(v, 0.5f)).ToArray();
                var steer = Obj(Get(props, "tk_steer"));
                wv.steerBones = steer.Keys.ToArray();
                wv.maxSteer = baseName == "Mule" ? 19f : 22f;      // big trucks: wide turning circle
                if (props.ContainsKey("tk_turret_bone"))
                {
                    wv.turretBone = S(Get(props, "tk_turret_bone"));
                    wv.gunBone = S(Get(props, "tk_gun_bone"), "gun");
                    wv.gunMin = F(Get(props, "tk_gun_min"), -10f);
                    wv.gunMax = F(Get(props, "tk_gun_max"), 60f);
                }
                SetDoor(props, (bn, ax, ang) => { wv.doorBone = bn; wv.doorAxis = ax; wv.doorAngle = ang; });
                wv.maxSpeed = baseName == "Mule" ? 26f : 31f;
                wv.muzzleScale = 0.12f;
                wv.impactKind = ImpactKind.Bullet;
                wv.impactScale = 0.5f;
                wv.engineAccel = baseName == "Mule" ? 6.0f : 7.2f;
            }
            else
            {
                var tankMass = new Dictionary<string, float> { { "Scout", 18000f }, { "Medium", 45000f }, { "Heavy", 62000f }, { "Artillery", 40000f }, { "AntiAir", 38000f }, { "Carrier", 24000f } };
                AddBody(go, b, tankMass.TryGetValue(baseName, out var mass) ? mass : 30000f,
                    Clearance(go, Obj(Get(props, "tk_wheels")).Keys.Where(k => k.StartsWith("wheel")), 0.1f));
                var tv = go.AddComponent<TrackedVehicle>();
                tv.displayName = dn;
                tv.unitKey = name;
                tv.localBounds = b;
                tv.trackPitch = F(Get(props, "tk_track_pitch"), 0.17f);
                var wheels = Obj(Get(props, "tk_wheels"));
                tv.wheelBones = wheels.Keys.ToArray();
                tv.wheelRadii = wheels.Values.Select(v => F(v, 0.3f)).ToArray();
                foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                {
                    if (smr.name.EndsWith("_Track_L")) tv.trackLeft = smr;
                    if (smr.name.EndsWith("_Track_R")) tv.trackRight = smr;
                }
                tv.turretBone = S(Get(props, "tk_turret_bone"), "turret");
                tv.gunBone = S(Get(props, "tk_gun_bone"), "gun");
                tv.gunMin = F(Get(props, "tk_gun_min"), -8f);
                tv.gunMax = F(Get(props, "tk_gun_max"), 20f);
                var barrels = Arr(Get(props, "tk_barrels")).Select(Obj).ToList();
                tv.barrelBones = barrels.Select(o => S(Get(o, "bone"))).ToArray();
                tv.flashBones = barrels.Select(o => S(Get(o, "flash"))).ToArray();
                tv.muzzleBones = tv.barrelBones.Select(x => x.Replace("barrel", "muzzle")).ToArray();
                tv.recoils = barrels.Select(o => F(Get(o, "recoil"), 0.2f)).ToArray();
                tv.radarBone = S(Get(props, "tk_radar_bone"));
                var fire = new Dictionary<string, float> { { "Scout", 0.12f }, { "Medium", 4f }, { "Heavy", 6f }, { "Artillery", 8f }, { "AntiAir", 0.09f }, { "Carrier", 0.11f } };
                tv.fireInterval = fire.TryGetValue(baseName, out var fi) ? fi : 3f;
                tv.tracerWidth = tv.fireInterval < 0.5f ? 0.08f : 0.28f;
                // effect sizes per gun: muzzle blast, what lands, and how big
                var fx = new Dictionary<string, (float m, ImpactKind k, float s)>
                {
                    { "Scout", (0.3f, ImpactKind.Autocannon, 0.9f) }, { "Medium", (1.0f, ImpactKind.Shell, 1.0f) },
                    { "Heavy", (1.25f, ImpactKind.Shell, 1.25f) }, { "Artillery", (1.6f, ImpactKind.Shell, 1.8f) },
                    { "AntiAir", (0.3f, ImpactKind.Autocannon, 0.8f) }, { "Carrier", (0.18f, ImpactKind.Bullet, 0.6f) },
                };
                if (fx.TryGetValue(baseName, out var f)) { tv.muzzleScale = f.m; tv.impactKind = f.k; tv.impactScale = f.s; }
                var speeds = new Dictionary<string, float> { { "Scout", 25f }, { "Medium", 20f }, { "Heavy", 17f }, { "Artillery", 17f }, { "AntiAir", 20f }, { "Carrier", 22f } };
                tv.maxSpeed = speeds.TryGetValue(baseName, out var sp) ? sp : 18f;
                var accels = new Dictionary<string, float> { { "Scout", 7f }, { "Medium", 5.5f }, { "Heavy", 4.6f }, { "Artillery", 4.8f }, { "AntiAir", 5.5f }, { "Carrier", 6f } };
                tv.engineAccel = accels.TryGetValue(baseName, out var ac) ? ac : 5f;
                tv.maxReverse = tv.maxSpeed * 0.4f;
                // turret drives: the flak gun tracks aircraft, the SPG traverses slowly and lobs ballistic shells
                var traverse = new Dictionary<string, (float y, float p)> { { "AntiAir", (110f, 80f) }, { "Scout", (60f, 40f) }, { "Carrier", (70f, 50f) }, { "Artillery", (24f, 14f) } };
                if (traverse.TryGetValue(baseName, out var tr)) { tv.turretYawSpeed = tr.y; tv.turretPitchSpeed = tr.p; }
                tv.ballistic = baseName == "Artillery";
                tv.shellSpeed = 110f;
                SetDoor(props, (bn, ax, ang) => { tv.doorBone = bn; tv.doorAxis = ax; tv.doorAngle = ang; });
            }
            SavePrefab(go, name);
        }

        static void SetDoor(Dictionary<string, object> props, Action<string, string, float> set)
        {
            foreach (var kv in Obj(Get(props, "tk_doors")))
            {
                var c = Obj(kv.Value);
                set(kv.Key, S(Get(c, "axis"), "x"), F(Get(c, "angle"), 95f));
                return;
            }
        }

        static readonly string[] Dirs = { "F", "FR", "R", "BR", "B", "BL", "L", "FL" };

        static void BuildSoldierPrefab(string fbx, Dictionary<string, Material> mats)
        {
            string name = Path.GetFileNameWithoutExtension(fbx);
            var meta = Obj(Parse(File.ReadAllText(Path.ChangeExtension(fbx, ".json"))));
            var vel = Obj(Get(meta, "clip_velocity"));
            var model = ImportModel(fbx, mats, true, n => n != "Death");
            var clips = Clips(fbx);

            string ctrlPath = $"{Gen}/Animation/{name}.controller";
            AssetDatabase.DeleteAsset(ctrlPath);
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(ctrlPath);
            ctrl.AddParameter("VelX", AnimatorControllerParameterType.Float);
            ctrl.AddParameter("VelZ", AnimatorControllerParameterType.Float);
            ctrl.CreateBlendTreeInController("Locomotion", out BlendTree tree, 0);
            tree.blendType = BlendTreeType.FreeformDirectional2D;
            tree.blendParameter = "VelX";
            tree.blendParameterY = "VelZ";
            tree.AddChild(clips["Idle"], Vector2.zero);
            Vector2 V(string clip)
            {
                var a = Arr(Get(vel, clip));
                return a.Count == 2 ? new Vector2(F(a[0]), F(a[1])) : Vector2.zero;
            }
            foreach (var g in new[] { "Walk", "Run" })
                foreach (var dname in Dirs)
                    if (clips.TryGetValue($"{g}_{dname}", out var c)) tree.AddChild(c, V($"{g}_{dname}"));
            if (clips.TryGetValue("Death", out var deathClip))
            {
                // played once by SoldierController.Die (no transitions: the body stays down)
                var death = ctrl.layers[0].stateMachine.AddState("Death");
                death.motion = deathClip;
                // seated / crouched pose: airship deck gunners sit behind their guns
                if (clips.TryGetValue("Crouch", out var crouchClip))
                {
                    var crouch = ctrl.layers[0].stateMachine.AddState("Crouch");
                    crouch.motion = crouchClip;
                }
            }
            else Debug.LogWarning("[Dominion] no Death clip in " + fbx);

            // upper-body aim layer (spine and everything above it)
            var tmp = (GameObject)PrefabUtility.InstantiatePrefab(model);
            var mask = new AvatarMask();
            mask.AddTransformPath(tmp.transform, true);
            for (int i = 0; i < mask.transformCount; i++)
                mask.SetTransformActive(i, mask.GetTransformPath(i).Contains("/Spine"));
            Object.DestroyImmediate(tmp);
            string maskPath = $"{Gen}/Animation/{name}_UpperBody.mask";
            AssetDatabase.DeleteAsset(maskPath);
            AssetDatabase.CreateAsset(mask, maskPath);
            ctrl.AddLayer("UpperBody");
            var layers = ctrl.layers;
            layers[1].avatarMask = mask;
            layers[1].defaultWeight = 0f;
            layers[1].blendingMode = AnimatorLayerBlendingMode.Override;
            var aim = layers[1].stateMachine.AddState("Aim");
            aim.motion = clips["Rifle_Aim"];
            ctrl.layers = layers;
            EditorUtility.SetDirty(ctrl);

            var go = Instance(model, name);
            var anim = GetOrAdd<Animator>(go);
            anim.runtimeAnimatorController = ctrl;
            anim.applyRootMotion = false;
            anim.cullingMode = AnimatorCullingMode.CullUpdateTransforms;     // 50 soldiers in War: skip off-screen ones
            var cc = go.AddComponent<CharacterController>();
            cc.center = new Vector3(0f, 0.9f, 0f);
            cc.height = 1.8f;
            cc.radius = 0.32f;
            cc.stepOffset = 0.4f;
            cc.slopeLimit = 50f;
            cc.skinWidth = 0.03f;
            var sc = go.AddComponent<SoldierController>();
            sc.displayName = name.EndsWith("Female") ? "Soldier (Female)" : "Soldier (Male)";
            sc.walkVel = Dirs.Select(dn => V("Walk_" + dn)).ToArray();
            sc.runVel = Dirs.Select(dn => V("Run_" + dn)).ToArray();
            SavePrefab(go, name);
        }

        static void BuildMechPrefab(string mech)
        {
            string fbx = $"{Art}/Mechs/Mech_{mech}.fbx";
            var mats = new Dictionary<string, Material>();
            var body = Lit($"{Gen}/Materials/M_Mech_{mech}.mat");
            SetLitMaps(body, T($"T_{mech}_BaseColor"), T($"T_{mech}_Mask"), T($"T_{mech}_Normal"), Color.white, 1f, 1f);
            mats[$"MAT_Mech_{mech}"] = body;
            var glow = Lit($"{Gen}/Materials/M_MechGlow.mat");
            SetLitMaps(glow, null, null, null, new Color(0.25f, 0.85f, 1f), 0f, 0.8f);
            HDMaterial.SetEmissiveColor(glow, new Color(0.25f, 0.85f, 1f) * 4f);
            glow.SetFloat("_EmissiveExposureWeight", 0f);
            HDMaterial.ValidateMaterial(glow);
            mats["MAT_MechGlow"] = glow;
            foreach (var f in new[] { "SkyLegion", "IronRepublic", "StormCorsairs" })
            {
                var bm = Lit($"{Gen}/Materials/M_Banner_{mech}_{f}.mat");
                SetLitMaps(bm, T($"T_Banner_{mech}_{f}"), null, null, Color.white, 0f, 0.12f);
                HDMaterial.SetAlphaClipping(bm, true);
                HDMaterial.SetAlphaCutoff(bm, 0.5f);
                HDMaterial.ValidateMaterial(bm);
                mats[$"MAT_Banner_{mech}_{f}"] = bm;
            }
            mats["MAT_MuzzleFlash"] = AssetDatabase.LoadAssetAtPath<Material>($"{Gen}/Materials/M_MuzzleFlash.mat");
            mats["MAT_Afterburner"] = AssetDatabase.LoadAssetAtPath<Material>($"{Gen}/Materials/M_Afterburner.mat");
            var oneShot = new HashSet<string> { "Fire", "Stomp", "Slash", "ShieldBash", "Punch" };
            var model = ImportModel(fbx, mats, true, n => !oneShot.Contains(n));
            var clips = Clips(fbx);
            string strike = mech == "Halberd" ? "Slash" : mech == "Aegis" ? "ShieldBash" : "Punch";

            string ctrlPath = $"{Gen}/Animation/Mech_{mech}.controller";
            AssetDatabase.DeleteAsset(ctrlPath);
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(ctrlPath);
            var sm = ctrl.layers[0].stateMachine;
            var states = new Dictionary<string, AnimatorState>();
            foreach (var s in new[] { "Idle", "Walk", "Run", "Aim", "Fire", "Jets_On", "Fly", "Dash", "Stomp", strike })
                if (clips.TryGetValue(s, out var clip))
                {
                    var st = sm.AddState(s);
                    st.motion = clip;
                    states[s] = st;
                }
            sm.defaultState = states["Idle"];
            if (states.TryGetValue("Fire", out var fire) && states.TryGetValue("Aim", out var aimSt))
            {
                var tr = fire.AddTransition(aimSt);
                tr.hasExitTime = true;
                tr.exitTime = 1f;
                tr.duration = 0.15f;
            }
            if (clips.TryGetValue("Flag_Wave", out var wave))
            {
                ctrl.AddLayer("Banner");
                var layers = ctrl.layers;
                layers[1].defaultWeight = 0f;
                var st = layers[1].stateMachine.AddState("Flag_Wave");
                st.motion = wave;
                st.writeDefaultValues = false;
                ctrl.layers = layers;
            }
            // upper-body layer: melee strikes while the legs keep walking / running
            {
                var tmp = (GameObject)PrefabUtility.InstantiatePrefab(model);
                var mask = new AvatarMask();
                mask.AddTransformPath(tmp.transform, true);
                for (int i = 0; i < mask.transformCount; i++)
                {
                    string tp = mask.GetTransformPath(i);
                    mask.SetTransformActive(i, tp.Contains("/Spine") && !tp.Contains("/Flag_"));
                }
                Object.DestroyImmediate(tmp);
                string maskPath = $"{Gen}/Animation/Mech_{mech}_UpperBody.mask";
                AssetDatabase.DeleteAsset(maskPath);
                AssetDatabase.CreateAsset(mask, maskPath);
                ctrl.AddLayer("UpperBody");
                var layers = ctrl.layers;
                int li = layers.Length - 1;
                layers[li].avatarMask = mask;
                layers[li].defaultWeight = 0f;
                layers[li].blendingMode = AnimatorLayerBlendingMode.Override;
                var empty = layers[li].stateMachine.AddState("Empty");
                empty.writeDefaultValues = false;
                layers[li].stateMachine.defaultState = empty;
                if (clips.TryGetValue(strike, out var strikeClip))
                {
                    var st = layers[li].stateMachine.AddState(strike);
                    st.motion = strikeClip;
                    st.writeDefaultValues = false;
                }
                ctrl.layers = layers;
            }
            EditorUtility.SetDirty(ctrl);

            var go = Instance(model, $"Mech_{mech}");
            var anim = GetOrAdd<Animator>(go);
            anim.runtimeAnimatorController = ctrl;
            anim.applyRootMotion = false;
            anim.cullingMode = AnimatorCullingMode.CullUpdateTransforms;
            var mc = go.AddComponent<MechController>();
            mc.Faction = mech == "Aegis" ? MechFaction.SkyLegion : mech == "Halberd" ? MechFaction.IronRepublic : MechFaction.StormCorsairs;
            var rb = go.AddComponent<Rigidbody>();
            rb.mass = 40000f;
            rb.useGravity = true;
            rb.isKinematic = true;
            rb.freezeRotation = true;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            var col = go.AddComponent<CapsuleCollider>();
            col.center = new Vector3(0f, 4.7f, 0f);
            col.radius = 2.1f;
            col.height = 9.4f;
            col.sharedMaterial = noFriction;
            var mv = go.AddComponent<MechVehicle>();
            mv.displayName = DisplayNames[$"Mech_{mech}"];
            mv.unitKey = $"Mech_{mech}";
            mv.localBounds = new Bounds(new Vector3(0f, 4.7f, 0f), new Vector3(5f, 9.4f, 4f));
            mv.fireInterval = mech == "Aegis" ? 0.4f : mech == "Halberd" ? 1.4f : 0.07f;
            mv.tracerWidth = mech == "Halberd" ? 0.3f : mech == "Aegis" ? 0.2f : 0.1f;
            mv.hasJets = mech == "Halberd";
            mv.hasPods = mech == "Thunderhead";
            mv.shotImpulse = mech == "Halberd" ? 90000f : mech == "Aegis" ? 14000f : 1500f;
            mv.strikeClip = strike;
            mv.strikeLength = 1f;
            mv.strikeHitAt = mech == "Aegis" ? 0.38f : 0.42f;
            mv.strikeReach = mech == "Aegis" ? 5f : 6f;
            mv.strikeRadius = mech == "Halberd" ? 5f : mech == "Aegis" ? 4.5f : 3.5f;
            mv.strikeDv = mech == "Aegis" ? 5.5f : mech == "Halberd" ? 4f : 3.5f;
            mv.strikeLunge = mech == "Aegis";
            mv.muzzleScale = mech == "Halberd" ? 0.75f : mech == "Aegis" ? 0.55f : 0.15f;
            mv.impactKind = mech == "Halberd" ? ImpactKind.Rail : mech == "Aegis" ? ImpactKind.Shell : ImpactKind.Bullet;
            mv.impactScale = mech == "Halberd" ? 0.9f : mech == "Aegis" ? 0.45f : 0.6f;
            mv.stompLength = 32f / 24f;
            mv.stompHitAt = 32f / 24f * 0.55f;
            SavePrefab(go, $"Mech_{mech}");
        }
    }
}
