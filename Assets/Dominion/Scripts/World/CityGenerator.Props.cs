using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    public partial class CityGenerator
    {
        ChunkSet propChunks;
        Transform carRoot, coverRoot;
        int carCount;
        /// <summary>Small static obstacles for the navigation grid: centre, half size, yaw.</summary>
        readonly List<(Vector2 c, Vector2 half, float yaw, bool crushable)> obstacles = new List<(Vector2, Vector2, float, bool)>();

        /// <summary>The battle zone between the two staging parks, where the streets look fought over.</summary>
        bool InBattleZone(Vector2 p) => Mathf.Abs(p.y) < Plan.StagingN.yMin - 20f && Mathf.Abs(p.x) < 950f;

        static (Mesh mesh, Material[] mats) Lod0(GameObject prefab)
        {
            if (prefab == null) return (null, null);
            foreach (var mf in prefab.GetComponentsInChildren<MeshFilter>(true))
                if (mf.name.EndsWith("_LOD0"))
                    return (mf.sharedMesh, mf.GetComponent<MeshRenderer>().sharedMaterials);
            var any = prefab.GetComponentInChildren<MeshFilter>(true);
            return any ? (any.sharedMesh, any.GetComponent<MeshRenderer>().sharedMaterials) : (null, null);
        }

        /// <summary>Cars parked along the curbs and abandoned in the lanes (off: clear streets; car parks keep theirs).</summary>
        static readonly bool RoadCars = false;

        void PlaceProps()
        {
            propChunks = new ChunkSet(160f);
            var parent = new GameObject("Street").transform;
            parent.SetParent(root, false);
            carRoot = new GameObject("Cars").transform;
            carRoot.SetParent(parent, false);
            coverRoot = new GameObject("Barricades").transform;
            coverRoot.SetParent(parent, false);
            var lamp = Lod0(kit.streetLamp);
            var signal = Lod0(kit.trafficLight);
            var bench = Lod0(kit.bench);
            float sideY = RoadLift + CurbH;

            foreach (var e in Plan.Edges)
            {
                if (e.cls == RoadClass.Highway || e.sidewalk <= 0f) continue;
                var A = Plan.Nodes[e.a];
                var B = Plan.Nodes[e.b];
                Vector2 d = B.p - A.p;
                float L = d.magnitude;
                d /= L;
                Vector2 left = Left(d);
                float t0 = A.trim + 7f, t1 = L - B.trim - 7f;
                // ---- street lamps
                if (lamp.mesh != null)
                {
                    bool both = e.cls == RoadClass.Arterial;
                    float spacing = e.cls == RoadClass.Arterial ? 38f : e.zone == Zone.Downtown || e.zone == Zone.Midtown ? 42f : 55f;
                    int sideSel = rng.Next(2) * 2 - 1;
                    for (int side = -1; side <= 1; side += 2)
                    {
                        if (!both && side != sideSel) continue;
                        for (float t = t0 + (side > 0 ? spacing * 0.5f : 0f); t < t1; t += spacing)
                        {
                            Vector2 n = left * side;
                            Vector2 p = A.p + d * t + n * (e.halfWidth + 0.6f);
                            if (BlockedByBuilding(p, 0.6f)) continue;
                            Vector2 dir = -n;
                            var M = Matrix4x4.TRS(V3(p, sideY), Quaternion.Euler(0f, Mathf.Atan2(dir.x, dir.y) * Mathf.Rad2Deg, 0f), Vector3.one);
                            propChunks.At(V3(p, 0f)).Append(lamp.mesh, lamp.mats, M);
                        }
                    }
                }
                // ---- parked cars along the curbs
                if (e.zone == Zone.Staging || e.zone == Zone.Rural) continue;
                float density = e.zone switch
                {
                    Zone.Downtown => 0.38f, Zone.Midtown => 0.36f, Zone.Residential => 0.3f, Zone.Suburb => 0.15f, Zone.Industrial => 0.2f, _ => 0.08f,
                };
                for (int side = -1; side <= 1; side += 2)
                {
                    Vector2 n = left * side;
                    for (float t = t0 + R(0f, 6f); t < t1 - 3f;)
                    {
                        bool bus = e.cls == RoadClass.Arterial && Chance(0.04f) && kit.bus != null;
                        float len = bus ? 13f : R(6.2f, 8.5f);
                        if (t + len > t1) break;
                        if (RoadCars && Chance(density))
                        {
                            Vector2 p = A.p + d * (t + len * 0.5f) + n * (e.halfWidth - (bus ? 1.6f : 1.15f));
                            bool war = InBattleZone(p);
                            float yaw = Mathf.Atan2(d.x, d.y) * Mathf.Rad2Deg + (side > 0 ? 180f : 0f) + R(-3f, 3f);
                            if (war && Chance(0.3f)) yaw += R(-35f, 35f);
                            SpawnCar(p, yaw, bus, war && Chance(0.55f));
                        }
                        t += len;
                    }
                }
                // ---- abandoned / burnt cars in the traffic lanes of the battle zone
                Vector2 mid = (A.p + B.p) * 0.5f;
                if (RoadCars && InBattleZone(mid) && L > 40f && Chance(0.35f))
                {
                    int count = rng.Next(1, 3);
                    for (int k = 0; k < count; k++)
                    {
                        float t = R(t0 + 4f, Mathf.Max(t0 + 5f, t1 - 4f));
                        Vector2 p = A.p + d * t + left * R(-e.halfWidth * 0.5f, e.halfWidth * 0.5f);
                        SpawnCar(p, Mathf.Atan2(d.x, d.y) * Mathf.Rad2Deg + R(-60f, 60f), false, Chance(0.7f));
                    }
                }
            }

            // ---- traffic lights at avenue junctions, barricades at junctions in the battle zone
            foreach (var node in Plan.Nodes)
            {
                if (node.edges.Count < 3) continue;
                var dirs = Plan.SortedDirs(node);
                bool avenue = false, highway = false;
                foreach (var (_, ei) in dirs)
                {
                    if (Plan.Edges[ei].cls == RoadClass.Arterial) avenue = true;
                    if (Plan.Edges[ei].cls == RoadClass.Highway) highway = true;
                }
                if (avenue && !highway && signal.mesh != null)
                {
                    for (int k = 0; k < dirs.Count; k += 2)
                    {
                        var e = Plan.Edges[dirs[k].e];
                        if (e.sidewalk <= 0f) continue;
                        Vector2 d = new Vector2(Mathf.Cos(dirs[k].ang), Mathf.Sin(dirs[k].ang));
                        Vector2 corner = node.p + d * (node.trim + 1.2f) - Left(d) * (e.halfWidth + 0.7f);
                        Vector2 arm = Left(d);
                        var M = Matrix4x4.TRS(V3(corner, sideY), Quaternion.Euler(0f, Mathf.Atan2(arm.x, arm.y) * Mathf.Rad2Deg, 0f), Vector3.one);
                        propChunks.At(V3(corner, 0f)).Append(signal.mesh, signal.mats, M);
                    }
                }
                if (!highway && InBattleZone(node.p) && Chance(0.2f)) Barricade(node, dirs);
            }

            // ---- benches and parked cars in the open lots
            foreach (var (c, half, yaw, kind) in reservedPatches)
            {
                Vector2 ax = new Vector2(Mathf.Cos(yaw * Mathf.Deg2Rad), -Mathf.Sin(yaw * Mathf.Deg2Rad));
                Vector2 az = new Vector2(Mathf.Sin(yaw * Mathf.Deg2Rad), Mathf.Cos(yaw * Mathf.Deg2Rad));
                if (kind == 2)
                {
                    for (float x = -half.x + 2f; x < half.x - 2f; x += 3f)
                        foreach (float row in new[] { -half.y * 0.45f, half.y * 0.35f })
                            if (Chance(0.45f))
                                SpawnCar(c + ax * x + az * row, yaw + 90f + (Chance(0.5f) ? 180f : 0f) + R(-4f, 4f), false, InBattleZone(c) && Chance(0.4f));
                }
                else if (bench.mesh != null)
                {
                    for (int k = 0; k < 3; k++)
                    {
                        Vector2 p = c + ax * R(-half.x + 2f, half.x - 2f) + az * R(-half.y + 2f, half.y - 2f);
                        var M = Matrix4x4.TRS(V3(p, 0.02f), Quaternion.Euler(0f, yaw + rng.Next(4) * 90f, 0f), Vector3.one);
                        propChunks.At(V3(p, 0f)).Append(bench.mesh, bench.mats, M);
                    }
                }
            }
            // benches around the staging parks and big parks
            if (bench.mesh != null)
                foreach (var d in Plan.Districts)
                {
                    if (d.zone != Zone.Park) continue;
                    for (int k = 0; k < 24; k++)
                    {
                        Vector2 p = d.site + new Vector2(R(-120f, 120f), R(-120f, 120f));
                        if (Plan.ZoneAt(p) != Zone.Park || NearRoad(p, 3f, -1)) continue;
                        var M = Matrix4x4.TRS(V3(p, 0.02f), Quaternion.Euler(0f, R(0f, 360f), 0f), Vector3.one);
                        propChunks.At(V3(p, 0f)).Append(bench.mesh, bench.mats, M);
                    }
                }
            propChunks.Emit(parent, "Props", true, 0.08f, false);
        }

        void SpawnCar(Vector2 p, float yaw, bool bus, bool wreck)
        {
            GameObject prefab;
            if (bus) prefab = wreck ? kit.busWreck : kit.bus;
            else if (wreck && kit.wrecks.Length > 0) prefab = kit.wrecks[rng.Next(kit.wrecks.Length)];
            else if (kit.cars.Length > 0) prefab = kit.cars[rng.Next(kit.cars.Length)];
            else return;
            if (prefab == null) return;
            Vector2 half = bus ? new Vector2(1.3f, 6f) : new Vector2(1.0f, 2.5f);
            float r = yaw * Mathf.Deg2Rad;
            Vector2 ax = new Vector2(Mathf.Cos(r), -Mathf.Sin(r)), az = new Vector2(Mathf.Sin(r), Mathf.Cos(r));
            if (OverlapsLot(p, ax, az, half)) return;
            if (DetailZone(p))
            {
                var go = Instantiate(prefab, new Vector3(p.x, RoadLift + 0.01f, p.y), Quaternion.Euler(0f, yaw, 0f), carRoot);
                go.isStatic = true;
            }
            else
            {
                // far from the fighting: merged into the street chunk mesh, with a plain box collider
                var (mesh, mats) = CarShell(prefab);
                if (mesh != null)
                    propChunks.At(new Vector3(p.x, 0f, p.y)).Append(mesh, mats,
                        Matrix4x4.TRS(new Vector3(p.x, RoadLift + 0.01f, p.y), Quaternion.Euler(0f, yaw, 0f), Vector3.one));
                var cgo = new GameObject("Car");
                cgo.transform.SetParent(carRoot, false);
                cgo.transform.SetPositionAndRotation(new Vector3(p.x, 0.8f, p.y), Quaternion.Euler(0f, yaw, 0f));
                cgo.AddComponent<BoxCollider>().size = new Vector3(half.x * 2f, 1.5f, half.y * 2f);
                cgo.AddComponent<CarProp>();
                cgo.isStatic = true;
            }
            obstacles.Add((p, half, yaw, true));
            if (bus || prefab.name.Contains("Van")) CoverBoxes.Add((new Vector3(p.x, 1.2f, p.y), new Vector3(half.x * 2f, 2.4f, half.y * 2f), yaw));
            carCount++;
        }

        readonly Dictionary<GameObject, (Mesh, Material[])> carShells = new Dictionary<GameObject, (Mesh, Material[])>();

        (Mesh mesh, Material[] mats) CarShell(GameObject prefab)
        {
            var key = prefab;
            if (carShells.TryGetValue(key, out var s)) return s;
            s = (null, null);
            foreach (var mf in prefab.GetComponentsInChildren<MeshFilter>(true))
                if (mf.name.EndsWith("_LOD1")) { s = (mf.sharedMesh, mf.GetComponent<MeshRenderer>().sharedMaterials); break; }
            carShells[key] = s;
            return s;
        }

        /// <summary>A hasty roadblock: a T-wall line or a row of jersey barriers across part of one approach.</summary>
        void Barricade(RoadNode node, List<(float ang, int e)> dirs)
        {
            var (ang, ei) = dirs[rng.Next(dirs.Count)];
            var e = Plan.Edges[ei];
            Vector2 d = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
            Vector2 l = Left(d);
            float dist = node.trim + R(8f, 20f);
            if (dist > Plan.EdgeLength(ei) - 10f) return;
            bool twall = Chance(0.55f) && kit.twall != null;
            var prefab = twall ? kit.twall : kit.jersey;
            if (prefab == null) return;
            float pieceW = twall ? 1.5f : 3.7f;
            // block one side of the road (and sometimes a staggered piece on the other) so vehicles can still weave through
            float side = Chance(0.5f) ? 1f : -1f;
            float from = side > 0 ? 0.4f : -e.halfWidth + 0.4f, to = side > 0 ? e.halfWidth - 0.3f : -0.4f;
            float yaw = Mathf.Atan2(l.x, l.y) * Mathf.Rad2Deg;
            for (float s = from + pieceW * 0.5f; s <= to - pieceW * 0.5f + 0.01f; s += pieceW + 0.05f)
            {
                Vector2 p = node.p + d * dist + l * s;
                var go = Instantiate(prefab, new Vector3(p.x, RoadLift, p.y), Quaternion.Euler(0f, yaw + 90f, 0f), coverRoot);
                go.isStatic = true;
                obstacles.Add((p, twall ? new Vector2(0.75f, 0.6f) : new Vector2(1.85f, 0.35f), yaw + 90f, false));
            }
            if (Chance(0.5f))
            {
                // a second, staggered piece further out on the other side
                float s2 = -side * e.halfWidth * 0.5f;
                Vector2 p = node.p + d * (dist + R(6f, 10f)) + l * s2;
                var go = Instantiate(prefab, new Vector3(p.x, RoadLift, p.y), Quaternion.Euler(0f, yaw + 90f, 0f), coverRoot);
                go.isStatic = true;
                obstacles.Add((p, twall ? new Vector2(0.75f, 0.6f) : new Vector2(1.85f, 0.35f), yaw + 90f, false));
            }
        }

        // ------------------------------------------------------------------ navigation + minimap
        void BuildNav()
        {
            var boxes = new List<(Vector2 c, Vector2 half, float yaw, bool crushable)>();
            foreach (var l in lots)
            {
                if (l.proc == Proc.Reserved) continue;
                boxes.Add((l.c, l.half + Vector2.one * 0.3f, l.yaw, false));
            }
            boxes.AddRange(obstacles);
            foreach (var t in cityTrees) boxes.Add((new Vector2(t.x, t.z), new Vector2(0.5f, 0.5f), 0f, false));
            CityNav.Build(Plan, boxes, ZHalf);
        }

        void BuildMinimap()
        {
            const int S = 1024;
            var px = new Color32[S * S];
            float mpp = MapRange * 2f / S;
            for (int j = 0; j < S; j++)
            {
                float z = -MapRange + (j + 0.5f) * mpp;
                for (int i = 0; i < S; i++)
                {
                    float x = -MapRange + (i + 0.5f) * mpp;
                    float h = HeightAt(x, z);
                    float shade = Mathf.Clamp((HeightAt(x - mpp, z + mpp) - h) * 0.04f, -0.15f, 0.15f);
                    var zone = ZoneAt(x, z);
                    Color c = zone switch
                    {
                        Zone.Rural => Color.Lerp(new Color(0.24f, 0.32f, 0.2f), new Color(0.42f, 0.44f, 0.34f), h / 260f),
                        Zone.Park => new Color(0.25f, 0.4f, 0.22f),
                        Zone.Staging => new Color(0.3f, 0.38f, 0.25f),
                        Zone.Downtown => new Color(0.36f, 0.36f, 0.37f),
                        Zone.Midtown => new Color(0.33f, 0.34f, 0.33f),
                        Zone.Industrial => new Color(0.36f, 0.34f, 0.3f),
                        Zone.Airfield => new Color(0.4f, 0.4f, 0.38f),
                        _ => new Color(0.3f, 0.35f, 0.28f),
                    };
                    byte o = OverAt(x, z);
                    if (o == 3) c = new Color(0.25f, 0.4f, 0.22f);
                    if (zone == Zone.Rural && Forest(x, z) > 0.3f) c *= 0.82f;
                    c += new Color(shade, shade, shade);
                    c.a = 0.92f;
                    px[j * S + i] = c;
                }
            }
            // roads
            foreach (var e in Plan.Edges)
            {
                Vector2 a = Plan.Nodes[e.a].p, b = Plan.Nodes[e.b].p;
                Color32 rc = e.cls == RoadClass.Highway ? new Color32(214, 196, 140, 240) : e.cls == RoadClass.Arterial ? new Color32(200, 200, 196, 240) : new Color32(150, 150, 148, 240);
                float w = (e.Outer) / mpp;
                int steps = Mathf.CeilToInt((b - a).magnitude / (mpp * 0.5f));
                for (int k = 0; k <= steps; k++)
                {
                    Vector2 p = Vector2.Lerp(a, b, k / (float)steps);
                    int ci = (int)((p.x + MapRange) / mpp), cj = (int)((p.y + MapRange) / mpp);
                    int r = Mathf.Max(0, Mathf.RoundToInt(w * 0.6f));
                    for (int dj = -r; dj <= r; dj++)
                        for (int di = -r; di <= r; di++)
                        {
                            int ii = ci + di, jj = cj + dj;
                            if (ii >= 0 && jj >= 0 && ii < S && jj < S) px[jj * S + ii] = rc;
                        }
                }
            }
            // buildings
            foreach (var l in lots)
            {
                if (l.proc == Proc.Reserved) continue;
                byte g = (byte)Mathf.Clamp(70 - l.height * 0.35f, 30, 70);
                var bc = new Color32(g, g, (byte)(g + 4), 255);
                Vector2 ax = l.Ax, az = l.Az;
                float ext = l.half.magnitude;
                int i0 = Mathf.Max(0, (int)((l.c.x - ext + MapRange) / mpp)), i1 = Mathf.Min(S - 1, (int)((l.c.x + ext + MapRange) / mpp));
                int j0 = Mathf.Max(0, (int)((l.c.y - ext + MapRange) / mpp)), j1 = Mathf.Min(S - 1, (int)((l.c.y + ext + MapRange) / mpp));
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                    {
                        Vector2 p = new Vector2(-MapRange + (i + 0.5f) * mpp, -MapRange + (j + 0.5f) * mpp) - l.c;
                        if (Mathf.Abs(Vector2.Dot(p, ax)) <= l.half.x && Mathf.Abs(Vector2.Dot(p, az)) <= l.half.y) px[j * S + i] = bc;
                    }
            }
            // runways
            foreach (var a in new[] { Plan.AirS, Plan.AirN })
                for (float z = -CityPlan.AirHalfLen; z <= CityPlan.AirHalfLen; z += mpp * 0.5f)
                    for (float x = -20f; x <= 20f; x += mpp * 0.5f)
                    {
                        int i = (int)((a.x + x + MapRange) / mpp), j = (int)((a.y + z + MapRange) / mpp);
                        if (i >= 0 && j >= 0 && i < S && j < S) px[j * S + i] = new Color32(90, 90, 92, 255);
                    }
            Minimap = new Texture2D(S, S, TextureFormat.RGBA32, true) { name = "Minimap", wrapMode = TextureWrapMode.Clamp, anisoLevel = 2 };
            Minimap.SetPixels32(px);
            Minimap.Apply(true, true);
        }
    }
}
