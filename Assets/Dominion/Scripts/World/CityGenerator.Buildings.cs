using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    public partial class CityGenerator
    {
        enum Proc : byte { None, Tower, Office, MidRise, Row, Shed, Reserved }

        class Lot
        {
            public Vector2 c, half;
            public float yaw;               // degrees: local +z (the front) faces the street
            public int def = -1;            // kit building index, -1 = procedural
            public Proc proc;
            public int floors, palette;
            public float floorH, groundH, height;
            public bool shop;
            public Zone zone;
            public Vector2 Ax => new Vector2(Mathf.Cos(yaw * Mathf.Deg2Rad), -Mathf.Sin(yaw * Mathf.Deg2Rad));
            public Vector2 Az => new Vector2(Mathf.Sin(yaw * Mathf.Deg2Rad), Mathf.Cos(yaw * Mathf.Deg2Rad));
        }

        readonly List<Lot> lots = new List<Lot>();
        readonly Dictionary<long, List<int>> lotHash = new Dictionary<long, List<int>>();
        readonly Dictionary<long, List<int>> edgeHash = new Dictionary<long, List<int>>();
        readonly Dictionary<string, List<int>> defsByType = new Dictionary<string, List<int>>();
        int prefabCount, procCount;
        const float LotCell = 48f, EdgeCell = 64f;
        static long HKey(int x, int y) => ((long)x << 32) ^ (uint)y;

        // ------------------------------------------------------------------ spatial queries
        void IndexEdges()
        {
            for (int i = 0; i < Plan.Edges.Count; i++)
            {
                var e = Plan.Edges[i];
                Vector2 a = Plan.Nodes[e.a].p, b = Plan.Nodes[e.b].p;
                float m = e.Outer + 2f;
                int x0 = Mathf.FloorToInt((Mathf.Min(a.x, b.x) - m) / EdgeCell), x1 = Mathf.FloorToInt((Mathf.Max(a.x, b.x) + m) / EdgeCell);
                int y0 = Mathf.FloorToInt((Mathf.Min(a.y, b.y) - m) / EdgeCell), y1 = Mathf.FloorToInt((Mathf.Max(a.y, b.y) + m) / EdgeCell);
                for (int y = y0; y <= y1; y++)
                    for (int x = x0; x <= x1; x++)
                    {
                        if (!edgeHash.TryGetValue(HKey(x, y), out var l)) edgeHash[HKey(x, y)] = l = new List<int>();
                        l.Add(i);
                    }
            }
        }

        readonly HashSet<int> seen = new HashSet<int>();

        /// <summary>Is an oriented box within (road outer half-width + margin) of any road?</summary>
        bool NearRoadBox(Vector2 c, Vector2 ax, Vector2 az, Vector2 half, float margin)
        {
            float ext = half.magnitude + 20f;
            int x0 = Mathf.FloorToInt((c.x - ext) / EdgeCell), x1 = Mathf.FloorToInt((c.x + ext) / EdgeCell);
            int y0 = Mathf.FloorToInt((c.y - ext) / EdgeCell), y1 = Mathf.FloorToInt((c.y + ext) / EdgeCell);
            seen.Clear();
            for (int y = y0; y <= y1; y++)
                for (int x = x0; x <= x1; x++)
                {
                    if (!edgeHash.TryGetValue(HKey(x, y), out var l)) continue;
                    foreach (int i in l)
                    {
                        if (!seen.Add(i)) continue;
                        var e = Plan.Edges[i];
                        Vector2 a = Plan.Nodes[e.a].p - c, b = Plan.Nodes[e.b].p - c;
                        Vector2 la = new Vector2(Vector2.Dot(a, ax), Vector2.Dot(a, az)), lb = new Vector2(Vector2.Dot(b, ax), Vector2.Dot(b, az));
                        if (SegBoxDist(la, lb, half) < e.Outer + margin) return true;
                    }
                }
            return false;
        }

        bool NearRoad(Vector2 p, float margin, int ignore) => NearRoadBox(p, Vector2.right, Vector2.up, Vector2.zero, margin);

        static float SegBoxDist(Vector2 a, Vector2 b, Vector2 h)
        {
            // Liang-Barsky: does the segment cross the box?
            Vector2 d = b - a;
            float t0 = 0f, t1 = 1f;
            bool Clip(float p, float q)
            {
                if (Mathf.Abs(p) < 1e-7f) return q >= 0f;
                float t = q / p;
                if (p < 0f) { if (t > t1) return false; if (t > t0) t0 = t; }
                else { if (t < t0) return false; if (t < t1) t1 = t; }
                return true;
            }
            if (Clip(-d.x, a.x + h.x) && Clip(d.x, h.x - a.x) && Clip(-d.y, a.y + h.y) && Clip(d.y, h.y - a.y) && t0 <= t1) return 0f;
            float best = Mathf.Min(PointBox(a, h), PointBox(b, h));
            best = Mathf.Min(best, CityPlan.DistToSeg(new Vector2(h.x, h.y), a, b));
            best = Mathf.Min(best, CityPlan.DistToSeg(new Vector2(-h.x, h.y), a, b));
            best = Mathf.Min(best, CityPlan.DistToSeg(new Vector2(h.x, -h.y), a, b));
            best = Mathf.Min(best, CityPlan.DistToSeg(new Vector2(-h.x, -h.y), a, b));
            return best;
        }

        static float PointBox(Vector2 p, Vector2 h) => new Vector2(Mathf.Max(Mathf.Abs(p.x) - h.x, 0f), Mathf.Max(Mathf.Abs(p.y) - h.y, 0f)).magnitude;

        bool OverlapsLot(Vector2 c, Vector2 ax, Vector2 az, Vector2 half)
        {
            float ext = half.magnitude;
            int x0 = Mathf.FloorToInt((c.x - ext - 60f) / LotCell), x1 = Mathf.FloorToInt((c.x + ext + 60f) / LotCell);
            int y0 = Mathf.FloorToInt((c.y - ext - 60f) / LotCell), y1 = Mathf.FloorToInt((c.y + ext + 60f) / LotCell);
            seen.Clear();
            for (int y = y0; y <= y1; y++)
                for (int x = x0; x <= x1; x++)
                {
                    if (!lotHash.TryGetValue(HKey(x, y), out var l)) continue;
                    foreach (int i in l)
                    {
                        if (!seen.Add(i)) continue;
                        var o = lots[i];
                        if (ObbOverlap(c, ax, az, half, o.c, o.Ax, o.Az, o.half)) return true;
                    }
                }
            return false;
        }

        static bool ObbOverlap(Vector2 c1, Vector2 x1, Vector2 z1, Vector2 h1, Vector2 c2, Vector2 x2, Vector2 z2, Vector2 h2)
        {
            Vector2 d = c2 - c1;
            foreach (var axis in new[] { x1, z1, x2, z2 })
            {
                float r1 = h1.x * Mathf.Abs(Vector2.Dot(x1, axis)) + h1.y * Mathf.Abs(Vector2.Dot(z1, axis));
                float r2 = h2.x * Mathf.Abs(Vector2.Dot(x2, axis)) + h2.y * Mathf.Abs(Vector2.Dot(z2, axis));
                if (Mathf.Abs(Vector2.Dot(d, axis)) > r1 + r2) return false;
            }
            return true;
        }

        bool BlockedByBuilding(Vector2 p, float r) => OverlapsLot(p, Vector2.right, Vector2.up, new Vector2(r, r));

        void AddLot(Lot l)
        {
            lots.Add(l);
            int id = lots.Count - 1;
            float ext = l.half.magnitude;
            int x0 = Mathf.FloorToInt((l.c.x - ext) / LotCell), x1 = Mathf.FloorToInt((l.c.x + ext) / LotCell);
            int y0 = Mathf.FloorToInt((l.c.y - ext) / LotCell), y1 = Mathf.FloorToInt((l.c.y + ext) / LotCell);
            for (int y = y0; y <= y1; y++)
                for (int x = x0; x <= x1; x++)
                {
                    if (!lotHash.TryGetValue(HKey(x, y), out var list)) lotHash[HKey(x, y)] = list = new List<int>();
                    list.Add(id);
                }
        }

        // ------------------------------------------------------------------ choosing buildings
        int Def(string type)
        {
            if (!defsByType.TryGetValue(type, out var l) || l.Count == 0) return -1;
            return l[rng.Next(l.Count)];
        }

        int RInt(int a, int b) => rng.Next(a, b + 1);

        Lot Pick(Zone zone, float rho)
        {
            var l = new Lot { zone = zone };
            float u = (float)rng.NextDouble();
            switch (zone)
            {
                case Zone.Downtown:
                    if (u < 0.025f) l.def = Def("Building_Skyscraper");
                    else if (u < 0.13f) l.def = Def("Building_Office");
                    else if (u < 0.3f) l.proc = Proc.Tower;
                    else if (u < 0.66f) l.proc = Proc.Office;
                    else if (u < 0.9f) l.proc = Proc.MidRise;
                    else l.def = Def("Building_Apartment");
                    break;
                case Zone.Midtown:
                    if (u < 0.07f) l.def = Def("Building_Office");
                    else if (u < 0.18f) l.def = Def("Building_Apartment");
                    else if (u < 0.24f) l.def = Def("Building_Shop");
                    else if (u < 0.44f) l.proc = Proc.Office;
                    else if (u < 0.85f) l.proc = Proc.MidRise;
                    else if (u < 0.875f) l.proc = Proc.Tower;
                    else l.proc = Proc.Row;
                    break;
                case Zone.Residential:
                    if (u < 0.09f) l.def = Def("Building_Apartment");
                    else if (u < 0.18f) l.def = Def("Building_Shop");
                    else if (u < 0.31f) l.def = Def("Building_House");
                    else if (u < 0.37f) l.def = Def("Building_Cottage");
                    else if (u < 0.55f) l.proc = Proc.MidRise;
                    else l.proc = Proc.Row;
                    break;
                case Zone.Suburb:
                    if (u < 0.45f) l.def = Def("Building_House");
                    else if (u < 0.84f) l.def = Def("Building_Cottage");
                    else if (u < 0.89f) l.def = Def("Building_Shop");
                    else l.proc = Proc.Row;
                    break;
                case Zone.Industrial:
                    if (u < 0.33f) l.def = Def("Building_Warehouse");
                    else if (u < 0.9f) l.proc = Proc.Shed;
                    else l.proc = Proc.Office;
                    break;
                default:
                    return null;
            }
            if (l.def >= 0)
            {
                var d = kit.buildings[l.def];
                l.half = (d.max - d.min) * 0.5f;
                l.height = d.height;
                return l;
            }
            if (l.proc == Proc.None) { l.proc = Proc.Row; }
            switch (l.proc)
            {
                case Proc.Tower:
                {
                    l.half = new Vector2(0.75f * RInt(15, 27), 0.75f * RInt(14, 25));
                    float top = Mathf.Lerp(28f, 14f, Mathf.Clamp01(rho / 0.3f));
                    l.floors = Mathf.Clamp(Mathf.RoundToInt(top * R(0.7f, 1.15f)), 10, 32);
                    l.floorH = 3.6f;
                    l.groundH = 0f;
                    l.height = l.floors * 3.6f;
                    break;
                }
                case Proc.Office:
                    l.half = new Vector2(1.8f * RInt(6, 11), 1.8f * RInt(5, 8));
                    l.floors = zone == Zone.Downtown ? RInt(5, 13) : zone == Zone.Industrial ? RInt(2, 4) : RInt(3, 8);
                    l.floorH = 3.6f;
                    l.groundH = 4.5f;
                    l.shop = true;
                    l.height = l.groundH + l.floors * 3.6f;
                    break;
                case Proc.MidRise:
                    l.half = new Vector2(3.2f * RInt(2, 5), 1.6f * RInt(8, 14));
                    l.floors = zone == Zone.Residential ? RInt(3, 6) : RInt(4, 8);
                    l.floorH = 3.2f;
                    l.shop = zone != Zone.Residential || Chance(0.4f);
                    l.groundH = l.shop ? 4f : 3.2f;
                    l.height = l.groundH + l.floors * 3.2f;
                    break;
                case Proc.Row:
                    l.half = new Vector2(3.2f * RInt(1, 3), 1.6f * RInt(6, 10));
                    l.floors = RInt(1, 3);
                    l.floorH = 3.2f;
                    l.shop = zone == Zone.Midtown && Chance(0.5f);
                    l.groundH = l.shop ? 4f : 3.2f;
                    l.height = l.groundH + l.floors * 3.2f;
                    break;
                case Proc.Shed:
                    l.half = new Vector2(2f * RInt(6, 12), 2f * RInt(5, 9));
                    l.height = R(7f, 11f);
                    break;
            }
            l.palette = rng.Next(16);
            return l;
        }

        // ------------------------------------------------------------------ placement along every street
        void PlaceBuildings()
        {
            for (int i = 0; i < kit.buildings.Count; i++)
            {
                var b = kit.buildings[i];
                if (b.prefab == null) continue;
                if (!defsByType.TryGetValue(b.type, out var l)) defsByType[b.type] = l = new List<int>();
                l.Add(i);
            }
            IndexEdges();
            // reserve the staging parks so nothing is built in them
            foreach (var r in new[] { Plan.StagingS, Plan.StagingN })
                AddLot(new Lot { c = r.center, half = r.size * 0.5f + Vector2.one * 8f, proc = Proc.Reserved });
            var order = new List<int>();
            for (int i = 0; i < Plan.Edges.Count; i++) order.Add(i);
            // arterials first (their frontage is the prime real estate), then the rest
            order.Sort((a, b) => Plan.Edges[b].cls.CompareTo(Plan.Edges[a].cls));
            foreach (int ei in order)
            {
                var e = Plan.Edges[ei];
                if (e.cls == RoadClass.Highway) continue;
                var A = Plan.Nodes[e.a];
                var B = Plan.Nodes[e.b];
                Vector2 d = B.p - A.p;
                float L = d.magnitude;
                if (L < 20f) continue;
                d /= L;
                Vector2 left = Left(d);
                for (int side = -1; side <= 1; side += 2)
                {
                    Vector2 nrm = left * side;
                    Vector2 probe = (A.p + B.p) * 0.5f + nrm * (e.Outer + 14f);
                    Zone zone = Plan.ZoneAt(probe);
                    if (zone == Zone.Rural || zone == Zone.Park || zone == Zone.Staging || zone == Zone.Airfield) continue;
                    float t = A.trim + 2f, end = L - B.trim - 2f;
                    int fails = 0;
                    while (t < end - 5f && fails < 40)
                    {
                        // pocket parks, plazas and parking lots break up the frontage
                        float roll = (float)rng.NextDouble();
                        if ((zone == Zone.Midtown || zone == Zone.Residential || zone == Zone.Downtown || zone == Zone.Industrial) && roll < 0.045f)
                        {
                            float w = R(28f, 52f), dd = R(26f, 40f);
                            if (t + w > end) { t += 6f; fails++; continue; }
                            Vector2 c = A.p + d * (t + w * 0.5f) + nrm * (e.Outer + dd * 0.5f + 1f);
                            float yaw = Mathf.Atan2(-nrm.x, -nrm.y) * Mathf.Rad2Deg;
                            var res = new Lot { c = c, half = new Vector2(w * 0.5f, dd * 0.5f), yaw = yaw, proc = Proc.Reserved, zone = zone };
                            if (!OverlapsLot(c, res.Ax, res.Az, res.half) && !NearRoadBox(c, res.Ax, res.Az, res.half, 0.2f))
                            {
                                AddLot(res);
                                byte kind = zone == Zone.Industrial ? (byte)2 : zone == Zone.Downtown ? (byte)1 : roll < 0.02f ? (byte)2 : (byte)3;
                                PaintOver(c, res.half, yaw, kind);
                                reservedPatches.Add((c, res.half, yaw, kind));
                                t += w + 2f;
                                continue;
                            }
                        }
                        var lot = Pick(zone, Plan.Radial(A.p));
                        if (lot == null) break;
                        float wAlong = lot.half.x * 2f, depth = lot.half.y * 2f;
                        if (t + wAlong > end) { t += 4f; fails++; continue; }
                        float setback, gap, vacant;
                        switch (zone)
                        {
                            case Zone.Downtown: setback = R(1f, 3f); gap = R(3f, 8f); vacant = 0.1f; break;
                            case Zone.Midtown: setback = R(1f, 4f); gap = R(3f, 8f); vacant = 0.18f; break;
                            case Zone.Residential: setback = lot.proc == Proc.Row ? R(1f, 2.5f) : R(2f, 5f); gap = lot.proc == Proc.Row ? 0.25f : R(4f, 8f); vacant = 0.22f; break;
                            case Zone.Suburb: setback = R(6f, 10f); gap = R(6f, 14f); vacant = 0.3f; break;
                            default: setback = R(6f, 14f); gap = R(8f, 18f); vacant = 0.25f; break;
                        }
                        if (Chance(vacant)) { t += wAlong + gap; continue; }
                        // the lot centre: prefab footprints are off-centre (porches, garages)
                        Vector2 centerAlong = A.p + d * (t + wAlong * 0.5f) + nrm * (e.Outer + setback + depth * 0.5f);
                        lot.yaw = Mathf.Atan2(-nrm.x, -nrm.y) * Mathf.Rad2Deg;
                        lot.c = centerAlong;
                        if (ValidLot(lot, gap))
                        {
                            AddLot(lot);
                            t += wAlong + gap;
                            fails = 0;
                        }
                        else { t += 4f; fails++; }
                    }
                }
            }
        }

        readonly List<(Vector2 c, Vector2 half, float yaw, byte kind)> reservedPatches = new List<(Vector2, Vector2, float, byte)>();

        bool ValidLot(Lot l, float gap)
        {
            if (!Plan.InCity(l.c, -4f)) return false;
            var z = Plan.ZoneAt(l.c);
            if (z == Zone.Rural || z == Zone.Park || z == Zone.Staging || z == Zone.Airfield) return false;
            if (Plan.InStaging(l.c, l.half.magnitude + 6f)) return false;
            if (NearRoadBox(l.c, l.Ax, l.Az, l.half, 0.5f)) return false;
            if (OverlapsLot(l.c, l.Ax, l.Az, l.half + Vector2.one * (gap * 0.5f))) return false;
            return true;
        }

        // ------------------------------------------------------------------ building the buildings
        ChunkSet buildChunks;
        Transform colRoot;

        void BuildBuildings()
        {
            buildChunks = new ChunkSet(256f);
            var parent = new GameObject("Buildings").transform;
            parent.SetParent(root, false);
            colRoot = new GameObject("Building Colliders").transform;
            colRoot.SetParent(parent, false);
            var prefRoot = new GameObject("Enterable").transform;
            prefRoot.SetParent(parent, false);
            topGrid = new float[TopW * TopW];
            foreach (var l in lots)
            {
                if (l.proc == Proc.Reserved) continue;
                if (l.def >= 0 && DetailZone(l.c))
                {
                    var d = kit.buildings[l.def];
                    Vector2 lc = (d.min + d.max) * 0.5f;
                    Vector2 off = l.Ax * lc.x + l.Az * lc.y;
                    Vector2 pos = l.c - off;
                    var go = Instantiate(d.prefab, new Vector3(pos.x, 0f, pos.y), Quaternion.Euler(0f, l.yaw, 0f), prefRoot);
                    go.name = d.name;
                    prefabCount++;
                }
                else if (l.def >= 0)
                {
                    // away from the fighting: the building's exterior shell merged into the chunk mesh, a plain box collider
                    var d = kit.buildings[l.def];
                    Vector2 lc = (d.min + d.max) * 0.5f;
                    Vector2 pos = l.c - (l.Ax * lc.x + l.Az * lc.y);
                    var shell = Shell(d);
                    if (shell.mesh != null)
                        buildChunks.At(new Vector3(l.c.x, 0f, l.c.y)).Append(shell.mesh, shell.mats,
                            Matrix4x4.TRS(new Vector3(pos.x, 0f, pos.y), Quaternion.Euler(0f, l.yaw, 0f), Vector3.one));
                    var cgo = new GameObject("S");
                    cgo.transform.SetParent(colRoot, false);
                    cgo.transform.SetPositionAndRotation(new Vector3(l.c.x, l.height * 0.5f, l.c.y), Quaternion.Euler(0f, l.yaw, 0f));
                    cgo.AddComponent<BoxCollider>().size = new Vector3(l.half.x * 2f, l.height, l.half.y * 2f);
                    cgo.isStatic = true;
                    shellCount++;
                }
                else
                {
                    ProcBuilding(l);
                    var cgo = new GameObject("B");
                    cgo.transform.SetParent(colRoot, false);
                    cgo.transform.SetPositionAndRotation(new Vector3(l.c.x, l.height * 0.5f, l.c.y), Quaternion.Euler(0f, l.yaw, 0f));
                    var bc = cgo.AddComponent<BoxCollider>();
                    bc.size = new Vector3(l.half.x * 2f, l.height, l.half.y * 2f);
                    cgo.isStatic = true;
                    procCount++;
                }
                if (InBattleZone(l.c) || DetailZone(l.c))
                    CoverBoxes.Add((new Vector3(l.c.x, l.height * 0.5f, l.c.y), new Vector3(l.half.x * 2f, l.height, l.half.y * 2f), l.yaw));
                StampTop(l);
            }
            buildChunks.Emit(parent, "Blocks", true, 0f, false);
        }

        int shellCount;
        readonly Dictionary<GameObject, (Mesh mesh, Material[] mats)> shells = new Dictionary<GameObject, (Mesh, Material[])>();

        /// <summary>Where the armies fight: enterable buildings (with interiors) and full car prefabs only here.</summary>
        bool DetailZone(Vector2 p) => Mathf.Abs(p.x) < 800f && Mathf.Abs(p.y) < Plan.StagingN.yMin + 120f;

        (Mesh mesh, Material[] mats) Shell(CityKit.BuildingDef d)
        {
            var key = d.prefab;
            if (shells.TryGetValue(key, out var s)) return s;
            s = (null, null);
            foreach (var mf in d.prefab.GetComponentsInChildren<MeshFilter>(true))
                if (mf.name.EndsWith("_LOD1")) { s = (mf.sharedMesh, mf.GetComponent<MeshRenderer>().sharedMaterials); break; }
            shells[key] = s;
            return s;
        }

        // roof heights for the pilots' terrain/obstacle clearance (16 m cells)
        const float TopCell = 16f;
        const int TopW = (int)(ZHalf * 2f / TopCell);
        float[] topGrid;

        void StampTop(Lot l)
        {
            float ext = l.half.magnitude;
            int i0 = Mathf.Max(0, (int)((l.c.x - ext + ZHalf) / TopCell)), i1 = Mathf.Min(TopW - 1, (int)((l.c.x + ext + ZHalf) / TopCell));
            int j0 = Mathf.Max(0, (int)((l.c.y - ext + ZHalf) / TopCell)), j1 = Mathf.Min(TopW - 1, (int)((l.c.y + ext + ZHalf) / TopCell));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    topGrid[j * TopW + i] = Mathf.Max(topGrid[j * TopW + i], l.height + 4f);
        }

        public float TopAt(float x, float z)
        {
            float h = HeightAt(x, z);
            if (topGrid == null) return h;
            int i = (int)((x + ZHalf) / TopCell), j = (int)((z + ZHalf) / TopCell);
            if (i < 0 || j < 0 || i >= TopW || j >= TopW) return h;
            return Mathf.Max(h, topGrid[j * TopW + i]);
        }

        // ------------------------------------------------------------------ procedural sealed buildings
        Material Pal(Material[] set, int k) => set != null && set.Length > 0 ? set[k % set.Length] : kit.concrete;

        void ProcBuilding(Lot l)
        {
            var acc = buildChunks.At(new Vector3(l.c.x, 0f, l.c.y));
            switch (l.proc)
            {
                case Proc.Tower when l.palette % 4 == 3:
                {
                    // concrete office tower: banded precast facade, glass lobby, rooftop plant
                    var facade = Pal(kit.facadeConcrete, l.palette / 4);
                    var store = Pal(kit.storefront, l.palette);
                    Tier(acc, l, l.half, 0f, l.height, f => Facade(f, facade, store, 7.2f, 7.2f, 4.5f, 6.4f), 1.1f, kit.concrete, 0f);
                    RoofBox(acc, l, new Vector2(l.half.x * 0.4f, l.half.y * 0.35f), l.height, l.height + 4f, kit.concrete);
                    Rooftop(acc, l);
                    break;
                }
                case Proc.Tower:
                {
                    float uo = (l.palette % 8) / 8f;
                    curtainMat = Pal(kit.curtain, l.palette / 2);
                    bool setback = l.floors > 24 && l.half.x > 13f && l.half.y > 13f;
                    float h1 = setback ? Mathf.Round(l.floors * R(0.5f, 0.7f)) * 3.6f : l.height;
                    Tier(acc, l, l.half, 0f, h1, f => Curtain(f), 1.2f, kit.metalDark, uo);
                    if (setback)
                    {
                        Vector2 h2 = l.half - Vector2.one * 3f;
                        Tier(acc, l, h2, h1, l.height, f => Curtain(f), 1.2f, kit.metalDark, uo + 0.37f);
                    }
                    Vector2 top = setback ? l.half - Vector2.one * 3f : l.half;
                    RoofBox(acc, l, new Vector2(top.x * 0.45f, top.y * 0.4f), l.height, l.height + R(3f, 6f), kit.metalDark);
                    if (Chance(0.6f)) Mast(acc, l, l.height + 4f, R(8f, 22f));
                    break;
                }
                case Proc.Office:
                {
                    var facade = Pal(kit.facadeConcrete, l.palette);
                    var store = Pal(kit.storefront, l.palette);
                    Tier(acc, l, l.half, 0f, l.height, f => Facade(f, facade, store, 7.2f, 7.2f, l.groundH, 6.4f), 1.1f, kit.concrete, 0f);
                    Rooftop(acc, l);
                    break;
                }
                case Proc.MidRise:
                case Proc.Row:
                {
                    bool brick = l.palette % 3 != 0;
                    var facade = brick ? Pal(kit.brick, l.palette) : Pal(kit.plaster, l.palette);
                    var store = Pal(kit.storefront, l.palette);
                    if (!l.shop) store = facade;
                    Tier(acc, l, l.half, 0f, l.height, f => Facade(f, facade, store, 6.4f, 6.4f, l.groundH, 6.4f), 0.9f, kit.stone, 0f);
                    Cornice(acc, l, l.height - 0.25f, l.height + 0.25f, kit.stone);
                    if (l.shop) Cornice(acc, l, l.groundH - 0.1f, l.groundH + 0.15f, kit.stone, 0.06f);
                    Rooftop(acc, l);
                    break;
                }
                case Proc.Shed:
                    Shed(acc, l);
                    break;
            }
        }

        struct Face
        {
            public Vector3 a, b;        // bottom corners (left to right seen from outside)
            public float z0, z1, s0;    // heights, distance along the wall loop at 'a'
            public Vector3 n;
        }

        Material curtainMat;

        System.Action<MeshAcc, Face> Curtain(Face f) => (acc, F) =>
        {
            // UV-locked glass curtain wall (12 m x 4 floors per tile)
            float L = (F.b - F.a).magnitude;
            var a0 = F.a + Vector3.up * F.z0;
            var b0 = F.b + Vector3.up * F.z0;
            acc.Quad(curtainMat ? curtainMat : kit.curtainWall, a0, b0, F.b + Vector3.up * F.z1, F.a + Vector3.up * F.z1,
                new Vector2(F.s0 / 12f, F.z0 / 14.4f), new Vector2((F.s0 + L) / 12f, F.z0 / 14.4f),
                new Vector2((F.s0 + L) / 12f, F.z1 / 14.4f), new Vector2(F.s0 / 12f, F.z1 / 14.4f), F.n);
        };

        System.Action<MeshAcc, Face> Facade(Face f, Material wall, Material ground, float tileW, float tileH, float groundH, float storeW) => (acc, F) =>
        {
            float L = (F.b - F.a).magnitude;
            float s0 = F.s0, s1 = F.s0 + L;
            if (groundH > 0.01f && ground != wall)
            {
                acc.Quad(ground, F.a, F.b, F.b + Vector3.up * groundH, F.a + Vector3.up * groundH,
                    new Vector2(s0 / storeW, 0f), new Vector2(s1 / storeW, 0f), new Vector2(s1 / storeW, 1f), new Vector2(s0 / storeW, 1f), F.n);
                acc.Quad(wall, F.a + Vector3.up * groundH, F.b + Vector3.up * groundH, F.b + Vector3.up * F.z1, F.a + Vector3.up * F.z1,
                    new Vector2(s0 / tileW, 0f), new Vector2(s1 / tileW, 0f), new Vector2(s1 / tileW, (F.z1 - groundH) / tileH),
                    new Vector2(s0 / tileW, (F.z1 - groundH) / tileH), F.n);
            }
            else
            {
                float v0 = (groundH > 0.01f ? -groundH : 0f) / tileH;
                acc.Quad(wall, F.a, F.b, F.b + Vector3.up * F.z1, F.a + Vector3.up * F.z1,
                    new Vector2(s0 / tileW, 0f), new Vector2(s1 / tileW, 0f), new Vector2(s1 / tileW, F.z1 / tileH), new Vector2(s0 / tileW, F.z1 / tileH), F.n);
                _ = v0;
            }
        };

        /// <summary>A box tier: four walls drawn by 'wall', a parapet, coping and a gravel roof.</summary>
        void Tier(MeshAcc acc, Lot l, Vector2 half, float z0, float z1, System.Func<Face, System.Action<MeshAcc, Face>> wall, float parapet, Material parapetMat, float uo)
        {
            Vector2 ax = l.Ax, az = l.Az;
            // corners counter-clockwise seen from above, each side's outward normal to the right of a->b
            Vector2[] c =
            {
                l.c - ax * half.x - az * half.y, l.c + ax * half.x - az * half.y, l.c + ax * half.x + az * half.y, l.c - ax * half.x + az * half.y,
            };
            Vector2[] nrm = { -az, ax, az, -ax };
            float s = uo * 12f;
            for (int i = 0; i < 4; i++)
            {
                // seen from outside, left -> right runs from corner i+1 to corner i for this winding
                Vector2 pa = c[(i + 1) % 4], pb = c[i];
                Vector2 n2 = nrm[i];
                Vector2 right = new Vector2(n2.y, -n2.x) * -1f;     // Cross(up, -n) in xz
                if (Vector2.Dot(pb - pa, right) < 0f) { var tmp = pa; pa = pb; pb = tmp; }
                var f = new Face { a = V3(pa, 0f), b = V3(pb, 0f), z0 = z0, z1 = z1, s0 = s, n = V3(n2, 0f) };
                wall(f)(acc, f);
                s += (pb - pa).magnitude;
                // parapet: outside band, inside face, coping
                Vector3 A0 = V3(pa, z1), B0 = V3(pb, z1);
                Vector3 up = Vector3.up * parapet;
                acc.QuadP(parapetMat, A0, B0, B0 + up, A0 + up, f.n, 2f);
                Vector3 inA = V3(pa - n2 * 0.3f + (pb - pa).normalized * 0.3f, z1), inB = V3(pb - n2 * 0.3f - (pb - pa).normalized * 0.3f, z1);
                acc.QuadP(parapetMat, inB, inA, inA + up, inB + up, -f.n, 2f);
                acc.QuadP(kit.stone, A0 + up, B0 + up, inB + up, inA + up, Vector3.up, 2f);
            }
            // roof
            Vector2 hi = half - Vector2.one * 0.3f;
            Vector3 r0 = V3(l.c - ax * hi.x - az * hi.y, z1 + 0.02f), r1 = V3(l.c + ax * hi.x - az * hi.y, z1 + 0.02f);
            Vector3 r2 = V3(l.c + ax * hi.x + az * hi.y, z1 + 0.02f), r3 = V3(l.c - ax * hi.x + az * hi.y, z1 + 0.02f);
            acc.QuadP(kit.gravel, r0, r1, r2, r3, Vector3.up, 4f);
        }

        void Cornice(MeshAcc acc, Lot l, float z0, float z1, Material m, float out_ = 0.25f)
        {
            Vector2 h = l.half + Vector2.one * out_;
            Vector2 ax = l.Ax, az = l.Az;
            Vector2[] c = { l.c - ax * h.x - az * h.y, l.c + ax * h.x - az * h.y, l.c + ax * h.x + az * h.y, l.c - ax * h.x + az * h.y };
            Vector2[] nrm = { -az, ax, az, -ax };
            for (int i = 0; i < 4; i++)
            {
                Vector2 pa = c[i], pb = c[(i + 1) % 4];
                acc.QuadP(m, V3(pa, z0), V3(pb, z0), V3(pb, z1), V3(pa, z1), V3(nrm[i], 0f), 2f);
                acc.QuadP(m, V3(pa, z0), V3(pb, z0), V3(pb - nrm[i] * out_, z0), V3(pa - nrm[i] * out_, z0), Vector3.down, 2f);
                acc.QuadP(m, V3(pa, z1), V3(pb, z1), V3(pb - nrm[i] * out_, z1), V3(pa - nrm[i] * out_, z1), Vector3.up, 2f);
            }
        }

        void RoofBox(MeshAcc acc, Lot l, Vector2 half, float z0, float z1, Material m)
        {
            Vector2 off = l.Ax * R(-1f, 1f) * (l.half.x - half.x) * 0.5f + l.Az * R(-1f, 1f) * (l.half.y - half.y) * 0.5f;
            Box(acc, l.c + off, l.Ax, l.Az, half, z0, z1, m, kit.galvanized);
        }

        void Box(MeshAcc acc, Vector2 c, Vector2 ax, Vector2 az, Vector2 half, float z0, float z1, Material side, Material top)
        {
            Vector2[] p = { c - ax * half.x - az * half.y, c + ax * half.x - az * half.y, c + ax * half.x + az * half.y, c - ax * half.x + az * half.y };
            Vector2[] nrm = { -az, ax, az, -ax };
            for (int i = 0; i < 4; i++)
                acc.QuadP(side, V3(p[i], z0), V3(p[(i + 1) % 4], z0), V3(p[(i + 1) % 4], z1), V3(p[i], z1), V3(nrm[i], 0f), 2f);
            acc.QuadP(top, V3(p[0], z1), V3(p[1], z1), V3(p[2], z1), V3(p[3], z1), Vector3.up, 2f);
        }

        void Rooftop(MeshAcc acc, Lot l)
        {
            int n = RInt(1, 3);
            for (int i = 0; i < n; i++)
            {
                Vector2 h = new Vector2(R(0.8f, 1.6f), R(0.6f, 1.1f));
                if (h.x > l.half.x - 1.5f || h.y > l.half.y - 1.5f) continue;
                Vector2 off = l.Ax * R(-1f, 1f) * (l.half.x - h.x - 1f) + l.Az * R(-1f, 1f) * (l.half.y - h.y - 1f);
                Box(acc, l.c + off, l.Ax, l.Az, h, l.height, l.height + R(1f, 1.8f), kit.galvanized, kit.metalDark);
            }
            if ((l.proc == Proc.MidRise || l.proc == Proc.Row) && Chance(0.25f) && l.half.x > 4f && l.half.y > 4f)
            {
                // water tower
                Vector2 c = l.c + l.Ax * R(-1f, 1f) * (l.half.x - 3f) + l.Az * R(-1f, 1f) * (l.half.y - 3f);
                Cyl(acc, c, l.height + 1.8f, l.height + 4.2f, 1.3f, kit.metalDark);
                Box(acc, c, l.Ax, l.Az, new Vector2(1.2f, 1.2f), l.height, l.height + 1.8f, kit.metalDark, kit.metalDark);
            }
        }

        void Mast(MeshAcc acc, Lot l, float z0, float h)
        {
            Cyl(acc, l.c, z0, z0 + h, 0.25f, kit.galvanized, 6);
            Cyl(acc, l.c, z0 + h * 0.6f, z0 + h * 0.6f + 0.8f, 0.7f, kit.galvanized, 6);
        }

        void Cyl(MeshAcc acc, Vector2 c, float z0, float z1, float r, Material m, int segs = 10)
        {
            for (int i = 0; i < segs; i++)
            {
                float a0 = i * Mathf.PI * 2f / segs, a1 = (i + 1) * Mathf.PI * 2f / segs;
                Vector2 u0 = new Vector2(Mathf.Cos(a0), Mathf.Sin(a0)), u1 = new Vector2(Mathf.Cos(a1), Mathf.Sin(a1));
                acc.Quad(m, V3(c + u0 * r, z0), V3(c + u1 * r, z0), V3(c + u1 * r, z1), V3(c + u0 * r, z1),
                    new Vector2(a0, z0), new Vector2(a1, z0), new Vector2(a1, z1), new Vector2(a0, z1), V3(u0 + u1, 0f));
                acc.Quad(m, V3(c, z1), V3(c + u0 * r, z1), V3(c + u1 * r, z1), V3(c, z1), Vector2.zero, Vector2.zero, Vector2.zero, Vector2.zero, Vector3.up);
            }
        }

        void Shed(MeshAcc acc, Lot l)
        {
            Vector2 ax = l.Ax, az = l.Az, h = l.half;
            bool alongX = h.x >= h.y;
            float eave = l.height, pitch = 0.18f;
            float span = alongX ? h.y : h.x;
            float ridge = eave + span * pitch;
            var wall = l.palette % 2 == 0 ? kit.corrugated : kit.corrugatedRed;
            var roof = l.palette % 2 == 0 ? kit.corrugatedRed : kit.galvanized;
            Vector2[] c = { l.c - ax * h.x - az * h.y, l.c + ax * h.x - az * h.y, l.c + ax * h.x + az * h.y, l.c - ax * h.x + az * h.y };
            Vector2[] nrm = { -az, ax, az, -ax };
            for (int i = 0; i < 4; i++)
            {
                Vector2 pa = c[i], pb = c[(i + 1) % 4];
                acc.QuadP(wall, V3(pa, 0f), V3(pb, 0f), V3(pb, eave), V3(pa, eave), V3(nrm[i], 0f), 2f);
                bool gable = alongX ? (i == 1 || i == 3) : (i == 0 || i == 2);
                if (gable)
                {
                    Vector2 mid = (pa + pb) * 0.5f;
                    var tri = new List<Vector3> { V3(pa, eave), V3(pb, eave), V3(mid, ridge) };
                    var uv = new List<Vector2> { MeshAcc.PUV(tri[0], V3(nrm[i], 0f), 2f), MeshAcc.PUV(tri[1], V3(nrm[i], 0f), 2f), MeshAcc.PUV(tri[2], V3(nrm[i], 0f), 2f) };
                    acc.Poly(wall, tri, uv, V3(nrm[i], 0f));
                }
            }
            // roller doors on the front
            int doors = Mathf.Max(1, Mathf.RoundToInt(h.x / 9f));
            for (int k = 0; k < doors; k++)
            {
                float u = -h.x + (k + 0.5f) * (2f * h.x / doors);
                Vector2 p0 = l.c + ax * (u - 2.5f) + az * (h.y + 0.03f), p1 = l.c + ax * (u + 2.5f) + az * (h.y + 0.03f);
                acc.QuadP(kit.metalDark, V3(p0, 0f), V3(p1, 0f), V3(p1, 4.8f), V3(p0, 4.8f), V3(az, 0f), 1f);
            }
            // roof planes
            Vector2 ra, rb;
            if (alongX) { ra = l.c - ax * h.x; rb = l.c + ax * h.x; }
            else { ra = l.c - az * h.y; rb = l.c + az * h.y; }
            Vector2 across = alongX ? az : ax;
            float o = 0.4f;
            foreach (float sgn in new[] { -1f, 1f })
            {
                Vector2 e0 = ra + across * sgn * (span + o), e1 = rb + across * sgn * (span + o);
                float ye = eave - o * pitch;
                Vector3 up = (V3(across * sgn, 0f) * -pitch + Vector3.up).normalized;
                acc.QuadP(roof, V3(e0, ye), V3(e1, ye), V3(rb, ridge), V3(ra, ridge), up + V3(across * sgn, 0f) * 0.2f, 2f);
            }
        }
    }
}
