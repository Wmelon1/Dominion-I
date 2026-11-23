using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using Debug = UnityEngine.Debug;

namespace Dominion
{
    /// <summary>
    /// War-mode map generator. From one seed it builds an 8 x 8 km world: a huge city (about 3 km across) of districts
    /// with their own street grids, avenues, downtown towers, midtown blocks, rowhouse neighbourhoods, suburbs, industrial
    /// estates and parks, sitting flat in a basin ringed by soft forested hills that highways wind through, with an
    /// airfield in a valley on each side. Buildings come from the BuildingKit prefabs (enterable) plus procedural sealed
    /// blocks; roads get sidewalks, curbs, crosswalks, lamps and traffic lights; parked cars and burnt wrecks line the
    /// streets and barricades stand in the battle zone. It also builds the AI navigation data, cover boxes and minimap.
    /// Runs before WarManager.
    /// </summary>
    [DefaultExecutionOrder(-200)]
    public partial class CityGenerator : MonoBehaviour
    {
        public static CityGenerator Instance { get; private set; }
        public CityKit kit;

        public CityPlan Plan { get; private set; }
        public int Seed { get; private set; }
        public string MapName { get; private set; }
        public int Battalions { get; private set; }
        public Texture2D Minimap { get; private set; }
        public const float MapRange = 2600f;
        public string Stats { get; private set; } = "";
        public float GenerateSeconds { get; private set; }

        /// <summary>Boxes soldiers can hide behind (centre at mid-height, full size, yaw in degrees).</summary>
        public readonly List<(Vector3 center, Vector3 size, float yaw)> CoverBoxes = new List<(Vector3, Vector3, float)>();

        System.Random rng;
        Transform root;

        // ---- heightfield: 8192 m, 4 m cells, 4 x 4 terrain tiles of 2048 m
        const int Tiles = 4;
        const float TileSize = 2048f;
        const int TileRes = 513;
        public const float Half = Tiles * TileSize * 0.5f;
        const int N = Tiles * (TileRes - 1) + 1;
        const float Cell = TileSize / (TileRes - 1);
        const float BaseY = -60f, HeightRange = 720f;
        float[,] H;
        float airHeightS, airHeightN;
        float ox1, oz1, ox2, oz2, ox3, oz3;

        float R(float a, float b) => a + (float)rng.NextDouble() * (b - a);
        bool Chance(float p) => rng.NextDouble() < p;

        static float Smooth(float e0, float e1, float x)
        {
            float t = Mathf.Clamp01((x - e0) / (e1 - e0));
            return t * t * (3f - 2f * t);
        }

        void Awake()
        {
            Instance = this;
            MapInfo.FromCommandLine();
            Seed = MapInfo.Seed != 0 ? MapInfo.Seed : MapInfo.RandomSeed();
            MapInfo.LastSeed = Seed;
            MapName = MapInfo.NameOf(Seed);
            Battalions = Mathf.Clamp(MapInfo.ArmySize / 50, 1, 4);
            if (Battalions == 3) Battalions = 4;
            var sw = Stopwatch.StartNew();
            Generate();
            GenerateSeconds = (float)sw.Elapsed.TotalSeconds;
            Debug.Log($"[City] {MapName} (seed {Seed}) generated in {GenerateSeconds:0.00} s: {Stats}");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            WorldGround.Reset();
            CityNav.Clear();
        }

        readonly List<string> timings = new List<string>();
        Stopwatch stage;

        void Mark(string what)
        {
            timings.Add($"{what} {stage.Elapsed.TotalMilliseconds:0}ms");
            stage.Restart();
        }

        void Generate()
        {
            stage = Stopwatch.StartNew();
            rng = new System.Random(Seed * 7919 + 17);
            root = new GameObject($"City of {MapName}").transform;
            Plan = new CityPlan(Seed, Battalions);
            Mark("plan");
            ox1 = R(0f, 900f); oz1 = R(0f, 900f); ox2 = R(0f, 900f); oz2 = R(0f, 900f); ox3 = R(0f, 900f); oz3 = R(0f, 900f);
            BuildHeights();
            WorldGround.HeightFn = HeightAt;
            foreach (var n in Plan.Nodes) n.y = HeightAt(n.p.x, n.p.y);
            Mark("heights");
            BuildRoads();
            Mark("roads");
            PlaceBuildings();
            BuildBuildings();
            Mark("buildings");
            PlaceProps();
            Mark("props");
            BuildZoneGrid();
            PlaceTrees();
            BuildTerrain();
            Mark("terrain");
            BuildRunways();
            BuildNav();
            Mark("nav");
            BuildMinimap();
            WorldGround.TopFn = TopAt;
            TuneAtmosphere();
            Mark("minimap");
            Stats = $"{Plan.Districts.Count} districts, {Plan.Nodes.Count} junctions, {Plan.TotalRoadKm():0} km of road, " +
                    $"{prefabCount} enterable + {shellCount} merged + {procCount} procedural buildings, {carCount} cars/wrecks, {treeCount} trees, " +
                    $"{CoverBoxes.Count} cover boxes | " + string.Join(", ", timings);
        }

        // ------------------------------------------------------------------ heights
        float Fbm(float x, float z, int oct)
        {
            float s = 0f, a = 1f, f = 1f, norm = 0f;
            for (int i = 0; i < oct; i++)
            {
                s += a * Mathf.PerlinNoise(x * f, z * f);
                norm += a;
                a *= 0.5f;
                f *= 2.03f;
            }
            return s / norm;
        }

        float Hills(float x, float z)
        {
            float n1 = Fbm(x / 2300f + ox1, z / 2300f + oz1, 4);
            float n2 = Fbm(x / 650f + ox2, z / 650f + oz2, 3);
            float big = Mathf.Pow(Mathf.Clamp01(n1 * 1.45f - 0.28f), 1.35f);
            float rim = Smooth(2900f, 4050f, Mathf.Max(Mathf.Abs(x), Mathf.Abs(z))) * 170f;
            return Mathf.Max(3f, 26f + 250f * big + 46f * (n2 - 0.5f) + rim);
        }

        void BuildHeights()
        {
            H = new float[N, N];
            for (int iz = 0; iz < N; iz++)
            {
                float z = -Half + iz * Cell;
                for (int ix = 0; ix < N; ix++)
                {
                    float x = -Half + ix * Cell;
                    float r = Mathf.Sqrt(x * x + z * z);
                    float rb = Plan.Boundary(Mathf.Atan2(z, x));
                    float flat = 1f - Smooth(rb + 140f, rb + 1000f, r);
                    H[iz, ix] = flat >= 1f ? 0f : (1f - flat) * Hills(x, z);
                }
            }
            // airfields: a level runway at the valley's mean height
            airHeightS = FlattenAirfield(Plan.AirS);
            airHeightN = FlattenAirfield(Plan.AirN);
            // highways: graded road profiles carved into the hills
            foreach (var path in Plan.Highways) CarveHighway(path);
        }

        float FlattenAirfield(Vector2 c)
        {
            float sum = 0f;
            int n = 0;
            for (float z = -CityPlan.AirHalfLen; z <= CityPlan.AirHalfLen; z += 50f) { sum += HeightAt(c.x, c.y + z); n++; }
            float h = Mathf.Max(0f, sum / n * 0.7f);
            float blend = 260f;
            ForCells(c.x - CityPlan.AirHalfWidth - 80f - blend, c.y - CityPlan.AirHalfLen - 80f - blend,
                c.x + CityPlan.AirHalfWidth + 80f + blend, c.y + CityPlan.AirHalfLen + 80f + blend, (ix, iz, x, z) =>
                {
                    float dx = Mathf.Max(0f, Mathf.Abs(x - c.x) - CityPlan.AirHalfWidth - 80f);
                    float dz = Mathf.Max(0f, Mathf.Abs(z - c.y) - CityPlan.AirHalfLen - 80f);
                    float w = 1f - Smooth(0f, blend, Mathf.Sqrt(dx * dx + dz * dz));
                    H[iz, ix] = Mathf.Lerp(H[iz, ix], h, w);
                });
            return h;
        }

        void ForCells(float x0, float z0, float x1, float z1, System.Action<int, int, float, float> f)
        {
            int ix0 = Mathf.Clamp(Mathf.FloorToInt((x0 + Half) / Cell), 0, N - 1), ix1 = Mathf.Clamp(Mathf.CeilToInt((x1 + Half) / Cell), 0, N - 1);
            int iz0 = Mathf.Clamp(Mathf.FloorToInt((z0 + Half) / Cell), 0, N - 1), iz1 = Mathf.Clamp(Mathf.CeilToInt((z1 + Half) / Cell), 0, N - 1);
            for (int iz = iz0; iz <= iz1; iz++)
                for (int ix = ix0; ix <= ix1; ix++)
                    f(ix, iz, -Half + ix * Cell, -Half + iz * Cell);
        }

        void CarveHighway(List<Vector2> path)
        {
            int n = path.Count;
            var h = new float[n];
            for (int i = 0; i < n; i++)
            {
                h[i] = HeightAt(path[i].x, path[i].y);
                if (Plan.InAirfield(path[i], 200f)) h[i] = path[i].y < 0f ? airHeightS : airHeightN;
            }
            for (int pass = 0; pass < 3; pass++)
            {
                var s = new float[n];
                for (int i = 0; i < n; i++)
                {
                    float acc = 0f;
                    int c = 0;
                    for (int k = -3; k <= 3; k++) { int j = Mathf.Clamp(i + k, 0, n - 1); acc += h[j]; c++; }
                    s[i] = Plan.InCity(path[i], 100f) ? 0f : acc / c;
                }
                h = s;
            }
            for (int i = 1; i < n; i++)
            {
                float d = (path[i] - path[i - 1]).magnitude * 0.07f;
                h[i] = Mathf.Clamp(h[i], h[i - 1] - d, h[i - 1] + d);
            }
            for (int i = n - 2; i >= 0; i--)
            {
                float d = (path[i] - path[i + 1]).magnitude * 0.07f;
                h[i] = Mathf.Clamp(h[i], h[i + 1] - d, h[i + 1] + d);
            }
            for (int i = 0; i < n - 1; i++)
            {
                Vector2 a = path[i], b = path[i + 1];
                float ha = h[i], hb = h[i + 1];
                ForCells(Mathf.Min(a.x, b.x) - 48f, Mathf.Min(a.y, b.y) - 48f, Mathf.Max(a.x, b.x) + 48f, Mathf.Max(a.y, b.y) + 48f,
                    (ix, iz, x, z) =>
                    {
                        Vector2 p = new Vector2(x, z), ab = b - a;
                        float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / Mathf.Max(ab.sqrMagnitude, 1e-4f));
                        float d = (a + ab * t - p).magnitude;
                        float w = 1f - Smooth(10f, 46f, d);
                        if (w > 0f) H[iz, ix] = Mathf.Lerp(H[iz, ix], Mathf.Lerp(ha, hb, t), w);
                    });
            }
        }

        public float HeightAt(float x, float z)
        {
            if (H == null) return 0f;
            float fx = Mathf.Clamp((x + Half) / Cell, 0f, N - 1.001f), fz = Mathf.Clamp((z + Half) / Cell, 0f, N - 1.001f);
            int ix = (int)fx, iz = (int)fz;
            float tx = fx - ix, tz = fz - iz;
            float a = Mathf.Lerp(H[iz, ix], H[iz, ix + 1], tx);
            float b = Mathf.Lerp(H[iz + 1, ix], H[iz + 1, ix + 1], tx);
            return Mathf.Lerp(a, b, tz);
        }

        float Slope(float x, float z)
        {
            float dx = HeightAt(x + 4f, z) - HeightAt(x - 4f, z);
            float dz = HeightAt(x, z + 4f) - HeightAt(x, z - 4f);
            return Mathf.Sqrt(dx * dx + dz * dz) / 8f;
        }

        // ------------------------------------------------------------------ zones, ground patches, terrain
        const float ZCell = 8f, ZHalf = 2600f;
        int zw;
        byte[] zoneGrid;
        // ground overrides at 4 m: 1 paving, 2 lot gravel, 3 park grass, 4 dirt, 5 no-trees (road corridor)
        const float OCell = 4f;
        int ow;
        byte[] over;

        void EnsureOver()
        {
            if (over != null) return;
            ow = Mathf.CeilToInt(ZHalf * 2f / OCell);
            over = new byte[ow * ow];
        }

        /// <summary>Paint a ground override into an oriented rectangle (centre, half extents, yaw deg).</summary>
        void PaintOver(Vector2 c, Vector2 half, float yawDeg, byte value, float pad = 0f)
        {
            EnsureOver();
            float rad = yawDeg * Mathf.Deg2Rad;
            Vector2 ax = new Vector2(Mathf.Cos(rad), -Mathf.Sin(rad)), az = new Vector2(Mathf.Sin(rad), Mathf.Cos(rad));
            float ext = half.magnitude + pad;
            int i0 = Mathf.Max(0, (int)((c.x - ext + ZHalf) / OCell)), i1 = Mathf.Min(ow - 1, (int)((c.x + ext + ZHalf) / OCell));
            int j0 = Mathf.Max(0, (int)((c.y - ext + ZHalf) / OCell)), j1 = Mathf.Min(ow - 1, (int)((c.y + ext + ZHalf) / OCell));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                {
                    Vector2 p = new Vector2(-ZHalf + (i + 0.5f) * OCell, -ZHalf + (j + 0.5f) * OCell) - c;
                    if (Mathf.Abs(Vector2.Dot(p, ax)) <= half.x + pad && Mathf.Abs(Vector2.Dot(p, az)) <= half.y + pad)
                        if (value == 5 || over[j * ow + i] != 5) over[j * ow + i] = value;
                }
        }

        byte OverAt(float x, float z)
        {
            if (over == null) return 0;
            int i = (int)((x + ZHalf) / OCell), j = (int)((z + ZHalf) / OCell);
            if (i < 0 || j < 0 || i >= ow || j >= ow) return 0;
            return over[j * ow + i];
        }

        void BuildZoneGrid()
        {
            zw = Mathf.CeilToInt(ZHalf * 2f / ZCell);
            zoneGrid = new byte[zw * zw];
            for (int j = 0; j < zw; j++)
                for (int i = 0; i < zw; i++)
                    zoneGrid[j * zw + i] = (byte)Plan.ZoneAt(new Vector2(-ZHalf + (i + 0.5f) * ZCell, -ZHalf + (j + 0.5f) * ZCell));
            EnsureOver();
            // highway shoulders: dirt and no trees
            foreach (var path in Plan.Highways)
                for (int k = 0; k < path.Count - 1; k++)
                {
                    Vector2 a = path[k], b = path[k + 1];
                    Vector2 c = (a + b) * 0.5f, d = b - a;
                    float yaw = Mathf.Atan2(d.x, d.y) * Mathf.Rad2Deg;
                    PaintOver(c, new Vector2(16f, d.magnitude * 0.5f + 4f), yaw, 4);
                }
        }

        Zone ZoneAt(float x, float z)
        {
            if (zoneGrid == null) return Plan.ZoneAt(new Vector2(x, z));
            int i = (int)((x + ZHalf) / ZCell), j = (int)((z + ZHalf) / ZCell);
            if (i < 0 || j < 0 || i >= zw || j >= zw) return Zone.Rural;
            return (Zone)zoneGrid[j * zw + i];
        }

        float Forest(float x, float z)
        {
            float n = Fbm(x / 800f + ox3, z / 800f + oz3, 3);
            return Smooth(0.47f, 0.62f, n) * 0.58f + 0.02f;
        }

        void BuildTerrain()
        {
            var protos = new TreePrototype[kit.trees.Length];
            for (int i = 0; i < protos.Length; i++) protos[i] = new TreePrototype { prefab = kit.trees[i] };
            var terrains = new Terrain[Tiles, Tiles];
            for (int tz = 0; tz < Tiles; tz++)
                for (int tx = 0; tx < Tiles; tx++)
                {
                    var td = new TerrainData { heightmapResolution = TileRes };
                    td.size = new Vector3(TileSize, HeightRange, TileSize);
                    var hs = new float[TileRes, TileRes];
                    for (int j = 0; j < TileRes; j++)
                        for (int i = 0; i < TileRes; i++)
                            hs[j, i] = Mathf.Clamp01((H[tz * (TileRes - 1) + j, tx * (TileRes - 1) + i] - BaseY) / HeightRange);
                    td.SetHeights(0, 0, hs);
                    bool central = (tx == 1 || tx == 2) && (tz == 1 || tz == 2);
                    int ares = central ? 1024 : 256;
                    td.alphamapResolution = ares;
                    td.baseMapResolution = 512;
                    td.terrainLayers = kit.layers;
                    float x0 = -Half + tx * TileSize, z0 = -Half + tz * TileSize;
                    td.SetAlphamaps(0, 0, Splat(x0, z0, ares));
                    td.treePrototypes = protos;
                    td.RefreshPrototypes();
                    var list = trees[tz * Tiles + tx];
                    td.SetTreeInstances(list.ToArray(), true);
                    var go = Terrain.CreateTerrainGameObject(td);
                    go.name = $"Terrain {tx},{tz}";
                    go.transform.SetParent(root, false);
                    go.transform.position = new Vector3(x0, BaseY, z0);
                    var t = go.GetComponent<Terrain>();
                    t.materialTemplate = kit.terrainMaterial;
                    t.drawInstanced = false;
                    t.heightmapPixelError = 4f;
                    t.basemapDistance = 20000f;
                    t.treeDistance = 1200f;      // beyond this a tree is a few pixels in the haze: not drawn
                    t.treeBillboardDistance = 4000f;
                    t.treeMaximumFullLODCount = 100000;
                    t.groupingID = 7;
                    t.allowAutoConnect = true;
                    t.shadowCastingMode = ShadowCastingMode.On;
                    go.isStatic = true;
                    terrains[tx, tz] = t;
                }
            for (int tz = 0; tz < Tiles; tz++)
                for (int tx = 0; tx < Tiles; tx++)
                    terrains[tx, tz].SetNeighbors(tx > 0 ? terrains[tx - 1, tz] : null, tz < Tiles - 1 ? terrains[tx, tz + 1] : null,
                        tx < Tiles - 1 ? terrains[tx + 1, tz] : null, tz > 0 ? terrains[tx, tz - 1] : null);
        }

        float[,,] Splat(float x0, float z0, int res)
        {
            int L = Mathf.Max(1, kit.layers.Length);
            var am = new float[res, res, L];
            float step = TileSize / res;
            var w = new float[6];
            for (int j = 0; j < res; j++)
            {
                float z = z0 + (j + 0.5f) * step;
                for (int i = 0; i < res; i++)
                {
                    float x = x0 + (i + 0.5f) * step;
                    for (int k = 0; k < 6; k++) w[k] = 0f;
                    float n = Mathf.PerlinNoise(x * 0.021f + ox1, z * 0.021f + oz1);
                    float n2 = Mathf.PerlinNoise(x * 0.11f + ox2, z * 0.11f + oz2);
                    var zone = ZoneAt(x, z);
                    switch (zone)
                    {
                        case Zone.Rural:
                        {
                            float g = 0.5f + 0.5f * n;
                            w[0] = g; w[1] = 1f - g + 0.15f;
                            w[2] = Smooth(0.68f, 0.84f, n2) * 0.5f;
                            float f = Forest(x, z);
                            w[2] += f * 0.5f;
                            w[1] += f * 0.4f;
                            float s = Slope(x, z);
                            w[3] = Smooth(0.38f, 0.75f, s) * 4f;
                            break;
                        }
                        case Zone.Downtown: w[4] = 1f; w[2] = 0.04f; break;
                        case Zone.Midtown: w[4] = 0.55f + 0.4f * n; w[0] = 0.45f - 0.4f * n; break;
                        case Zone.Residential: w[0] = 0.8f; w[2] = 0.1f + 0.25f * Smooth(0.65f, 0.9f, n2); w[1] = 0.1f; break;
                        case Zone.Suburb: w[0] = 0.75f; w[1] = 0.25f * n; w[2] = 0.08f; break;
                        case Zone.Industrial: w[5] = 0.6f; w[2] = 0.3f + 0.2f * n; w[0] = 0.1f; break;
                        case Zone.Park: w[0] = 0.85f; w[1] = 0.15f + 0.2f * n; break;
                        case Zone.Staging: w[0] = 0.45f; w[2] = 0.25f + 0.3f * n2; w[1] = 0.2f; break;
                        case Zone.Airfield: w[5] = 0.5f; w[0] = 0.5f; break;
                    }
                    switch (OverAt(x, z))
                    {
                        case 1: for (int k = 0; k < 6; k++) w[k] *= 0.05f; w[4] = 1f; break;
                        case 2: for (int k = 0; k < 6; k++) w[k] *= 0.1f; w[5] = 1f; w[2] += 0.2f * n2; break;
                        case 3: for (int k = 0; k < 6; k++) w[k] *= 0.1f; w[0] = 0.9f; w[1] = 0.2f * n; break;
                        case 4: w[2] += 0.9f; break;
                    }
                    float sum = 0f;
                    for (int k = 0; k < 6; k++) sum += w[k];
                    if (sum < 1e-4f) { w[0] = 1f; sum = 1f; }
                    for (int k = 0; k < L && k < 6; k++) am[j, i, k] = w[k] / sum;
                }
            }
            return am;
        }

        // ------------------------------------------------------------------ trees (terrain tree instances, per tile)
        readonly List<TreeInstance>[] trees = new List<TreeInstance>[Tiles * Tiles];
        int treeCount;
        readonly List<Vector3> cityTrees = new List<Vector3>();

        void AddTree(float x, float z, int proto, float scale)
        {
            int tx = Mathf.Clamp(Mathf.FloorToInt((x + Half) / TileSize), 0, Tiles - 1);
            int tz = Mathf.Clamp(Mathf.FloorToInt((z + Half) / TileSize), 0, Tiles - 1);
            float x0 = -Half + tx * TileSize, z0 = -Half + tz * TileSize;
            var list = trees[tz * Tiles + tx] ??= new List<TreeInstance>();
            list.Add(new TreeInstance
            {
                position = new Vector3((x - x0) / TileSize, 0f, (z - z0) / TileSize),
                prototypeIndex = proto,
                widthScale = scale * R(0.9f, 1.1f),
                heightScale = scale,
                rotation = R(0f, Mathf.PI * 2f),
                color = Color.Lerp(Color.white, new Color(0.85f, 0.9f, 0.8f), R(0f, 1f)),
                lightmapColor = Color.white,
            });
            treeCount++;
        }

        void PlaceTrees()
        {
            for (int i = 0; i < trees.Length; i++) trees[i] ??= new List<TreeInstance>();
            if (System.Array.IndexOf(System.Environment.GetCommandLineArgs(), "-notrees") >= 0) return;   // perf A/B test
            // hills and fields: forests where the forest noise is high, a scattering elsewhere
            const float step = 12f;
            for (float z = -Half + 30f; z < Half - 30f; z += step)
                for (float x = -Half + 30f; x < Half - 30f; x += step)
                {
                    float px = x + R(-4.5f, 4.5f), pz = z + R(-4.5f, 4.5f);
                    if (ZoneAt(px, pz) != Zone.Rural) continue;
                    if (OverAt(px, pz) == 4 || Plan.InAirfield(new Vector2(px, pz), 140f)) continue;
                    if (Plan.InCity(new Vector2(px, pz), 60f)) continue;
                    if (!Chance(Forest(px, pz))) continue;
                    float h = HeightAt(px, pz);
                    int proto = Chance(Mathf.Clamp01(0.3f + h / 260f)) ? (Chance(0.4f) ? 4 : 3) : (Chance(0.7f) ? 0 : 1);
                    AddTree(px, pz, proto, R(0.8f, 1.3f));
                }
            // city: parks, staging-park borders, pocket parks
            for (float z = -ZHalf; z < ZHalf; z += 13f)
                for (float x = -ZHalf; x < ZHalf; x += 13f)
                {
                    float px = x + R(-5f, 5f), pz = z + R(-5f, 5f);
                    var zone = ZoneAt(px, pz);
                    byte o = OverAt(px, pz);
                    bool park = zone == Zone.Park || o == 3;
                    bool stagingEdge = zone == Zone.Staging && !CityPlan.Grow(Plan.StagingS, -30f).Contains(new Vector2(px, pz)) &&
                                       !CityPlan.Grow(Plan.StagingN, -30f).Contains(new Vector2(px, pz));
                    if (!park && !stagingEdge) continue;
                    if (o == 5 || BlockedByBuilding(new Vector2(px, pz), 3f)) continue;
                    float n = Mathf.PerlinNoise(px * 0.012f + ox3, pz * 0.012f + oz3);
                    if (!Chance(park ? 0.12f + 0.45f * n : 0.35f)) continue;
                    int proto = Chance(0.5f) ? 0 : Chance(0.5f) ? 1 : 2;
                    AddCityTree(px, pz, proto, R(0.85f, 1.2f));
                }
            // street trees along residential, suburban and midtown streets
            foreach (var e in Plan.Edges)
            {
                if (e.cls == RoadClass.Highway || e.sidewalk <= 0f) continue;
                if (e.zone != Zone.Residential && e.zone != Zone.Suburb && e.zone != Zone.Midtown && e.zone != Zone.Park) continue;
                Vector2 a = Plan.Nodes[e.a].p, b = Plan.Nodes[e.b].p;
                Vector2 d = (b - a).normalized, left = new Vector2(-d.y, d.x);
                float L = (b - a).magnitude;
                float spacing = e.zone == Zone.Midtown ? 18f : 14f;
                for (int side = -1; side <= 1; side += 2)
                    for (float t = Plan.Nodes[e.a].trim + 8f; t < L - Plan.Nodes[e.b].trim - 8f; t += spacing * R(0.85f, 1.2f))
                    {
                        Vector2 p = a + d * t + left * side * (e.Outer - 0.9f);
                        if (BlockedByBuilding(p, 2.5f) || NearRoad(p, 2.5f, -1)) continue;
                        AddCityTree(p.x, p.y, e.zone == Zone.Midtown ? 2 : (Chance(0.6f) ? 2 : 1), R(0.85f, 1.1f));
                    }
            }
        }

        void AddCityTree(float x, float z, int proto, float scale)
        {
            AddTree(x, z, proto, scale);
            cityTrees.Add(new Vector3(x, 0f, z));
        }

        // ------------------------------------------------------------------ atmosphere
        void TuneAtmosphere()
        {
            foreach (var vol in FindObjectsByType<Volume>(FindObjectsSortMode.None))
            {
                var p = vol.profile;
                if (p == null) continue;
                if (p.TryGet(out Fog fog))
                {
                    fog.meanFreePath.overrideState = true;
                    fog.meanFreePath.value = 3800f;
                    fog.baseHeight.overrideState = true;
                    fog.baseHeight.value = 0f;
                    fog.maximumHeight.overrideState = true;
                    fog.maximumHeight.value = 900f;
                    fog.maxFogDistance.overrideState = true;
                    fog.maxFogDistance.value = 9000f;
                }
                if (p.TryGet(out HDShadowSettings sh))
                {
                    sh.maxShadowDistance.overrideState = true;
                    sh.maxShadowDistance.value = Mathf.Max(sh.maxShadowDistance.value, 900f);
                }
            }
            var cam = Camera.main;
            if (cam) cam.farClipPlane = 12000f;
        }
    }
}
