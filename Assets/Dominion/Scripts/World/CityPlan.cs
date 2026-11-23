using System;
using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    public enum Zone : byte { Rural, Downtown, Midtown, Residential, Suburb, Industrial, Park, Staging, Airfield }
    public enum RoadClass : byte { Local, Arterial, Highway }

    /// <summary>One Voronoi district: its own street-grid orientation and block size, and a land use.</summary>
    public class District
    {
        public int index;
        public Vector2 site;
        public Zone zone;
        public float angle;
        public Vector2 block, phase;
        public List<Vector2> poly = new List<Vector2>();
        public List<int> polyNeighbour = new List<int>();
    }

    public class RoadNode
    {
        public Vector2 p;
        public float y;
        public float trim;
        public readonly List<int> edges = new List<int>();
    }

    public class RoadEdge
    {
        public int a, b;
        public RoadClass cls;
        public Zone zone;
        public float halfWidth, sidewalk;
        public float Outer => halfWidth + sidewalk;
    }

    /// <summary>
    /// The city layout as data (no Unity objects): a huge irregular city of Voronoi districts, each filled with its own
    /// street grid (orientation and block size by land use), arterial avenues along the district borders, two staging
    /// parks for the armies (point-symmetric across the centre), highways winding out through the hills and roads to
    /// both airfields. Everything comes from the seed, so a seed always rebuilds the same map.
    /// </summary>
    public class CityPlan
    {
        public readonly int Seed;
        readonly System.Random rng;
        public float CityR;
        public float BaseAngle;
        readonly float[] bAmp = new float[4], bPh = new float[4];
        public readonly List<District> Districts = new List<District>();
        public readonly List<RoadNode> Nodes = new List<RoadNode>();
        public readonly List<RoadEdge> Edges = new List<RoadEdge>();
        public readonly List<List<Vector2>> Highways = new List<List<Vector2>>();
        /// <summary>Army staging parks (x, z rectangles): south = the Blue side by default.</summary>
        public Rect StagingS, StagingN;
        /// <summary>Airfield runway centres (runways run along z).</summary>
        public Vector2 AirS, AirN;
        public const float AirHalfLen = 700f, AirHalfWidth = 40f;

        float R(float a, float b) => a + (float)rng.NextDouble() * (b - a);
        bool Chance(float p) => rng.NextDouble() < p;

        struct Seg
        {
            public Vector2 a, b;
            public RoadClass cls;
        }

        readonly List<Seg> segs = new List<Seg>();

        public CityPlan(int seed, int battalions)
        {
            Seed = seed;
            rng = new System.Random(seed);
            CityR = R(1450f, 1700f);
            for (int k = 0; k < 4; k++) { bAmp[k] = R(0.02f, 0.075f); bPh[k] = R(0f, 6.283f); }
            BaseAngle = R(-0.35f, 0.35f);
            float halfW = battalions > 1 ? 440f : 250f, front = 560f, depth = battalions >= 4 ? 520f : 300f;
            StagingS = new Rect(-halfW, -(front + depth), halfW * 2f, depth);
            StagingN = new Rect(-halfW, front, halfW * 2f, depth);
            AirS = new Vector2(R(420f, 700f), -(CityR + 1250f));
            AirN = -AirS;
            MakeDistricts();
            MakeStreets();
            MakeHighways();
            Planarize();
            Cleanup();
            Classify();
            ComputeTrims();
        }

        // ------------------------------------------------------------------ boundary & lookups
        public float Boundary(float ang)
        {
            float r = 1f;
            for (int k = 0; k < 4; k++) r += bAmp[k] * Mathf.Sin((k + 2) * ang + bPh[k]);
            return CityR * r;
        }

        public float Boundary(Vector2 p) => Boundary(Mathf.Atan2(p.y, p.x));
        public bool InCity(Vector2 p, float margin = 0f) => p.magnitude < Boundary(p) + margin;

        public District Nearest(Vector2 p)
        {
            District best = null;
            float bd = float.MaxValue;
            foreach (var d in Districts)
            {
                float dd = (d.site - p).sqrMagnitude;
                if (dd < bd) { bd = dd; best = d; }
            }
            return best;
        }

        public bool InStaging(Vector2 p, float margin = 0f) => Grow(StagingS, margin).Contains(p) || Grow(StagingN, margin).Contains(p);

        public bool InAirfield(Vector2 p, float margin = 0f)
        {
            foreach (var a in new[] { AirS, AirN })
                if (Mathf.Abs(p.x - a.x) < AirHalfWidth + margin && Mathf.Abs(p.y - a.y) < AirHalfLen + margin) return true;
            return false;
        }

        public static Rect Grow(Rect r, float m) => new Rect(r.xMin - m, r.yMin - m, r.width + 2f * m, r.height + 2f * m);

        public Zone ZoneAt(Vector2 p)
        {
            if (InStaging(p)) return Zone.Staging;
            if (InAirfield(p)) return Zone.Airfield;
            if (!InCity(p)) return Zone.Rural;
            var d = Nearest(p);
            return d == null ? Zone.Rural : d.zone;
        }

        /// <summary>0 at the centre, 1 at the city edge.</summary>
        public float Radial(Vector2 p) => p.magnitude / Boundary(p);

        // ------------------------------------------------------------------ districts
        void MakeDistricts()
        {
            var sites = new List<Vector2>();
            for (int tries = 0; tries < 6000 && sites.Count < 140; tries++)
            {
                float ang = R(0f, Mathf.PI * 2f);
                float r = Mathf.Sqrt((float)rng.NextDouble()) * CityR * 1.22f;
                var p = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * r;
                float spacing = 210f + 190f * Mathf.Clamp01(r / CityR);
                bool ok = true;
                foreach (var s in sites) if ((s - p).sqrMagnitude < spacing * spacing) { ok = false; break; }
                if (ok) sites.Add(p);
            }
            float box = CityR * 1.7f;
            for (int i = 0; i < sites.Count; i++)
            {
                var d = new District { index = i, site = sites[i] };
                d.poly.AddRange(new[] { new Vector2(-box, -box), new Vector2(box, -box), new Vector2(box, box), new Vector2(-box, box) });
                d.polyNeighbour.AddRange(new[] { -1, -1, -1, -1 });
                for (int j = 0; j < sites.Count; j++)
                {
                    if (j == i) continue;
                    Vector2 n = sites[j] - sites[i];
                    Vector2 m = (sites[j] + sites[i]) * 0.5f;
                    ClipHalfPlane(d, m, n, j);
                    if (d.poly.Count < 3) break;
                }
                float rho = Radial(d.site);
                d.zone = rho > 1.03f ? Zone.Rural : rho < 0.19f ? Zone.Downtown : rho < 0.42f ? Zone.Midtown : rho < 0.72f ? Zone.Residential : Zone.Suburb;
                if ((d.zone == Zone.Residential || d.zone == Zone.Suburb) && rho > 0.5f && Chance(0.2f)) d.zone = Zone.Industrial;
                Districts.Add(d);
            }
            // one or two big parks in the inner rings
            int parks = 1 + (Chance(0.6f) ? 1 : 0);
            for (int k = 0, guard = 0; k < parks && guard < 200; guard++)
            {
                var d = Districts[rng.Next(Districts.Count)];
                if ((d.zone == Zone.Midtown || d.zone == Zone.Residential) && !InStaging(d.site, 260f) && Area(d.poly) < 260000f)
                {
                    d.zone = Zone.Park;
                    k++;
                }
            }
            foreach (var d in Districts)
            {
                float rho = Radial(d.site);
                switch (d.zone)
                {
                    case Zone.Downtown: d.angle = BaseAngle + R(-0.04f, 0.04f); d.block = new Vector2(R(86f, 100f), R(120f, 140f)); break;
                    case Zone.Midtown: d.angle = BaseAngle + R(-0.12f, 0.12f); d.block = new Vector2(R(95f, 115f), R(130f, 160f)); break;
                    case Zone.Residential:
                        d.angle = Chance(0.35f) ? Mathf.Atan2(d.site.y, d.site.x) : BaseAngle + R(-0.4f, 0.4f);
                        d.block = new Vector2(R(78f, 95f), R(150f, 185f)); break;
                    case Zone.Suburb: d.angle = R(0f, Mathf.PI); d.block = new Vector2(R(68f, 82f), R(160f, 210f)); break;
                    case Zone.Industrial: d.angle = BaseAngle + R(-0.2f, 0.2f); d.block = new Vector2(R(150f, 190f), R(200f, 260f)); break;
                    default: d.angle = BaseAngle; d.block = new Vector2(120f, 120f); break;
                }
                if (Chance(0.5f)) d.block = new Vector2(d.block.y, d.block.x);
                d.phase = new Vector2(R(0f, d.block.x), R(0f, d.block.y));
                _ = rho;
            }
        }

        static float Area(List<Vector2> poly)
        {
            float a = 0f;
            for (int i = 0; i < poly.Count; i++) { var p = poly[i]; var q = poly[(i + 1) % poly.Count]; a += p.x * q.y - q.x * p.y; }
            return Mathf.Abs(a) * 0.5f;
        }

        /// <summary>Keep the side of the bisector facing the site; the new edge is labelled with neighbour j.</summary>
        static void ClipHalfPlane(District d, Vector2 m, Vector2 n, int j)
        {
            var src = d.poly;
            var lab = d.polyNeighbour;
            var outP = new List<Vector2>();
            var outL = new List<int>();
            int c = src.Count;
            for (int i = 0; i < c; i++)
            {
                Vector2 p = src[i], q = src[(i + 1) % c];
                float dp = Vector2.Dot(p - m, n), dq = Vector2.Dot(q - m, n);
                bool pin = dp <= 0f, qin = dq <= 0f;
                if (pin)
                {
                    outP.Add(p);
                    if (qin) outL.Add(lab[i]);
                    else
                    {
                        Vector2 x = p + (q - p) * (dp / (dp - dq));
                        outL.Add(lab[i]);
                        outP.Add(x);
                        outL.Add(j);
                    }
                }
                else if (qin)
                {
                    Vector2 x = p + (q - p) * (dp / (dp - dq));
                    outP.Add(x);
                    outL.Add(lab[i]);
                }
            }
            d.poly = outP;
            d.polyNeighbour = outL;
        }

        // ------------------------------------------------------------------ streets
        void AddSeg(Vector2 a, Vector2 b, RoadClass cls)
        {
            if ((b - a).sqrMagnitude < 1f) return;
            // cut out the staging parks (their perimeter roads are added separately)
            var pieces = new List<(Vector2, Vector2)> { (a, b) };
            foreach (var r in new[] { Grow(StagingS, 30f), Grow(StagingN, 30f) })
            {
                var next = new List<(Vector2, Vector2)>();
                foreach (var (p, q) in pieces) SubtractRect(p, q, r, next);
                pieces = next;
            }
            foreach (var (p, q) in pieces)
                if ((q - p).sqrMagnitude > 64f) segs.Add(new Seg { a = p, b = q, cls = cls });
        }

        static void SubtractRect(Vector2 a, Vector2 b, Rect r, List<(Vector2, Vector2)> outList)
        {
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
            bool hit = Clip(-d.x, a.x - r.xMin) && Clip(d.x, r.xMax - a.x) && Clip(-d.y, a.y - r.yMin) && Clip(d.y, r.yMax - a.y);
            if (!hit || t1 <= t0) { outList.Add((a, b)); return; }
            if (t0 > 0.001f) outList.Add((a, a + d * t0));
            if (t1 < 0.999f) outList.Add((a + d * t1, b));
        }

        /// <summary>Clip a segment to the city boundary (plus margin); returns false when nothing is left.</summary>
        bool ClipToCity(ref Vector2 a, ref Vector2 b, float margin)
        {
            bool ain = InCity(a, margin), bin = InCity(b, margin);
            if (ain && bin) return true;
            if (!ain && !bin)
            {
                Vector2 mid = (a + b) * 0.5f;
                return false || (InCity(mid, margin) && Bisect(ref a, mid, margin) && Bisect(ref b, mid, margin));
            }
            if (!ain) return Bisect(ref a, b, margin);
            return Bisect(ref b, a, margin);
        }

        /// <summary>Move 'outside' toward 'inside' until it sits on the boundary.</summary>
        bool Bisect(ref Vector2 outside, Vector2 inside, float margin)
        {
            Vector2 lo = inside, hi = outside;
            for (int i = 0; i < 18; i++)
            {
                Vector2 m = (lo + hi) * 0.5f;
                if (InCity(m, margin)) lo = m; else hi = m;
            }
            outside = lo;
            return (outside - inside).sqrMagnitude > 25f;
        }

        void MakeStreets()
        {
            // arterials: district borders
            foreach (var d in Districts)
            {
                for (int k = 0; k < d.poly.Count; k++)
                {
                    int j = d.polyNeighbour[k];
                    if (j <= d.index) continue;
                    var o = Districts[j];
                    if (d.zone == Zone.Rural && o.zone == Zone.Rural) continue;
                    Vector2 a = d.poly[k], b = d.poly[(k + 1) % d.poly.Count];
                    if (!ClipToCity(ref a, ref b, 60f)) continue;
                    AddSeg(a, b, RoadClass.Arterial);
                }
            }
            // local street grids inside each district
            foreach (var d in Districts)
            {
                if (d.zone == Zone.Rural || d.zone == Zone.Park) continue;
                Vector2 u = new Vector2(Mathf.Cos(d.angle), Mathf.Sin(d.angle));
                Vector2 v = new Vector2(-u.y, u.x);
                for (int pass = 0; pass < 2; pass++)
                {
                    Vector2 dir = pass == 0 ? u : v, across = pass == 0 ? v : u;
                    float spacing = pass == 0 ? d.block.y : d.block.x;
                    float phase = pass == 0 ? d.phase.y : d.phase.x;
                    float smin = float.MaxValue, smax = float.MinValue;
                    foreach (var p in d.poly) { float s = Vector2.Dot(p - d.site, across); smin = Mathf.Min(smin, s); smax = Mathf.Max(smax, s); }
                    int k0 = Mathf.CeilToInt((smin - phase) / spacing), k1 = Mathf.FloorToInt((smax - phase) / spacing);
                    for (int k = k0; k <= k1; k++)
                    {
                        float s = phase + k * spacing;
                        Vector2 o = d.site + across * s;
                        if (!ClipLine(d.poly, o, dir, out float t0, out float t1)) continue;
                        Vector2 a = o + dir * t0, b = o + dir * t1;
                        if ((b - a).magnitude < 35f) continue;
                        if (NearParallelEdge(d.poly, a, b, spacing * 0.42f)) continue;
                        // suburbs: some streets stop short (cul-de-sacs and long blocks)
                        if (d.zone == Zone.Suburb && pass == 1 && Chance(0.25f)) continue;
                        if (!ClipToCity(ref a, ref b, 0f)) continue;
                        AddSeg(a, b, RoadClass.Local);
                    }
                }
            }
            // perimeter avenues around the staging parks
            foreach (var r in new[] { Grow(StagingS, 30f), Grow(StagingN, 30f) })
            {
                var c = new[] { new Vector2(r.xMin, r.yMin), new Vector2(r.xMax, r.yMin), new Vector2(r.xMax, r.yMax), new Vector2(r.xMin, r.yMax) };
                for (int i = 0; i < 4; i++) segs.Add(new Seg { a = c[i], b = c[(i + 1) % 4], cls = RoadClass.Arterial });
            }
        }

        /// <summary>Cyrus-Beck: clip the infinite line o + t*dir against a convex polygon.</summary>
        static bool ClipLine(List<Vector2> poly, Vector2 o, Vector2 dir, out float t0, out float t1)
        {
            t0 = -1e6f;
            t1 = 1e6f;
            int c = poly.Count;
            float sign = Area2(poly) > 0f ? 1f : -1f;
            for (int i = 0; i < c; i++)
            {
                Vector2 p = poly[i], q = poly[(i + 1) % c];
                Vector2 e = q - p;
                Vector2 n = new Vector2(e.y, -e.x) * sign;          // outward normal
                float den = Vector2.Dot(n, dir);
                float num = Vector2.Dot(n, p - o);
                if (Mathf.Abs(den) < 1e-6f) { if (num < 0f) return false; continue; }
                float t = num / den;
                if (den > 0f) t1 = Mathf.Min(t1, t); else t0 = Mathf.Max(t0, t);
                if (t0 > t1) return false;
            }
            return t1 - t0 > 1f;
        }

        static float Area2(List<Vector2> poly)
        {
            float a = 0f;
            for (int i = 0; i < poly.Count; i++) { var p = poly[i]; var q = poly[(i + 1) % poly.Count]; a += p.x * q.y - q.x * p.y; }
            return a;
        }

        static bool NearParallelEdge(List<Vector2> poly, Vector2 a, Vector2 b, float minDist)
        {
            Vector2 dir = (b - a).normalized;
            Vector2 mid = (a + b) * 0.5f;
            for (int i = 0; i < poly.Count; i++)
            {
                Vector2 p = poly[i], q = poly[(i + 1) % poly.Count];
                Vector2 e = q - p;
                if (e.sqrMagnitude < 1f) continue;
                if (Mathf.Abs(Vector2.Dot(dir, e.normalized)) < 0.93f) continue;
                if (DistToSeg(mid, p, q) < minDist) return true;
            }
            return false;
        }

        public static float DistToSeg(Vector2 p, Vector2 a, Vector2 b)
        {
            Vector2 ab = b - a;
            float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / Mathf.Max(ab.sqrMagnitude, 1e-6f));
            return (a + ab * t - p).magnitude;
        }

        // ------------------------------------------------------------------ highways
        void MakeHighways()
        {
            var dirs = new List<float>();
            int extra = 3 + rng.Next(0, 2);
            for (int i = 0, guard = 0; i < extra && guard < 100; guard++)
            {
                float a = R(0f, Mathf.PI * 2f);
                bool ok = Mathf.Abs(Mathf.DeltaAngle(a * Mathf.Rad2Deg, -90f)) > 30f && Mathf.Abs(Mathf.DeltaAngle(a * Mathf.Rad2Deg, 90f)) > 30f;
                foreach (var b in dirs) if (Mathf.Abs(Mathf.DeltaAngle(a * Mathf.Rad2Deg, b * Mathf.Rad2Deg)) < 50f) ok = false;
                if (!ok) continue;
                dirs.Add(a);
                i++;
            }
            foreach (float a in dirs)
            {
                var path = new List<Vector2>();
                float r0 = Boundary(a) - 220f;
                Vector2 p = new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r0;
                path.Add(p);
                float h = a;
                while (Mathf.Max(Mathf.Abs(p.x), Mathf.Abs(p.y)) < 4000f)
                {
                    h += R(-0.09f, 0.09f);
                    h = a + Mathf.Clamp(Mathf.DeltaAngle(a * Mathf.Rad2Deg, h * Mathf.Rad2Deg) * Mathf.Deg2Rad, -0.55f, 0.55f);
                    p += new Vector2(Mathf.Cos(h), Mathf.Sin(h)) * 70f;
                    if (InAirfield(p, 120f)) break;
                    path.Add(p);
                }
                Highways.Add(path);
            }
            // airfield roads: from the city edge straight-ish to the near end of each runway, then alongside it
            foreach (var air in new[] { AirS, AirN })
            {
                float s = Mathf.Sign(air.y);
                var path = new List<Vector2>();
                Vector2 start = new Vector2(air.x * 0.35f, s * (Boundary(s > 0 ? Mathf.PI / 2 : -Mathf.PI / 2) - 220f));
                Vector2 near = new Vector2(air.x - s * (AirHalfWidth + 55f), air.y - s * AirHalfLen);
                Vector2 far = new Vector2(near.x, air.y + s * AirHalfLen);
                int n = Mathf.Max(2, Mathf.CeilToInt((near - start).magnitude / 70f));
                float wob = R(-120f, 120f);
                for (int i = 0; i <= n; i++)
                {
                    float t = i / (float)n;
                    Vector2 q = Vector2.Lerp(start, near, t);
                    q.x += Mathf.Sin(t * Mathf.PI) * wob;
                    path.Add(q);
                }
                int m = Mathf.CeilToInt((far - near).magnitude / 70f);
                for (int i = 1; i <= m; i++) path.Add(Vector2.Lerp(near, far, i / (float)m));
                Highways.Add(path);
            }
            foreach (var path in Highways)
                for (int i = 0; i < path.Count - 1; i++)
                    segs.Add(new Seg { a = path[i], b = path[i + 1], cls = RoadClass.Highway });
        }

        // ------------------------------------------------------------------ graph
        readonly Dictionary<long, List<int>> nodeHash = new Dictionary<long, List<int>>();

        static long Key(int x, int y) => ((long)x << 32) ^ (uint)y;

        int NodeAt(Vector2 p, float snap)
        {
            int cx = Mathf.FloorToInt(p.x / 16f), cy = Mathf.FloorToInt(p.y / 16f);
            for (int dx = -1; dx <= 1; dx++)
                for (int dy = -1; dy <= 1; dy++)
                    if (nodeHash.TryGetValue(Key(cx + dx, cy + dy), out var list))
                        foreach (int i in list)
                            if ((Nodes[i].p - p).sqrMagnitude < snap * snap) return i;
            Nodes.Add(new RoadNode { p = p });
            int id = Nodes.Count - 1;
            if (!nodeHash.TryGetValue(Key(cx, cy), out var l)) nodeHash[Key(cx, cy)] = l = new List<int>();
            l.Add(id);
            return id;
        }

        static bool Intersect(Vector2 p, Vector2 p2, Vector2 q, Vector2 q2, out float t, out float u)
        {
            Vector2 r = p2 - p, s = q2 - q;
            float den = r.x * s.y - r.y * s.x;
            t = u = 0f;
            if (Mathf.Abs(den) < 1e-6f) return false;
            Vector2 qp = q - p;
            t = (qp.x * s.y - qp.y * s.x) / den;
            u = (qp.x * r.y - qp.y * r.x) / den;
            return t > -1e-4f && t < 1f + 1e-4f && u > -1e-4f && u < 1f + 1e-4f;
        }

        void Planarize()
        {
            int n = segs.Count;
            var splits = new List<float>[n];
            for (int i = 0; i < n; i++) splits[i] = new List<float> { 0f, 1f };
            var bmin = new Vector2[n];
            var bmax = new Vector2[n];
            for (int i = 0; i < n; i++) { bmin[i] = Vector2.Min(segs[i].a, segs[i].b) - Vector2.one * 3f; bmax[i] = Vector2.Max(segs[i].a, segs[i].b) + Vector2.one * 3f; }
            for (int i = 0; i < n; i++)
                for (int j = i + 1; j < n; j++)
                {
                    if (bmax[i].x < bmin[j].x || bmax[j].x < bmin[i].x || bmax[i].y < bmin[j].y || bmax[j].y < bmin[i].y) continue;
                    var A = segs[i];
                    var B = segs[j];
                    if (Intersect(A.a, A.b, B.a, B.b, out float t, out float u))
                    {
                        splits[i].Add(Mathf.Clamp01(t));
                        splits[j].Add(Mathf.Clamp01(u));
                    }
                    else
                    {
                        // T-junctions: an end of one lying (almost) on the other
                        TrySnap(A.a, B, splits[j]);
                        TrySnap(A.b, B, splits[j]);
                        TrySnap(B.a, A, splits[i]);
                        TrySnap(B.b, A, splits[i]);
                    }
                }
            for (int i = 0; i < n; i++)
            {
                var s = segs[i];
                var ts = splits[i];
                ts.Sort();
                int prev = NodeAt(s.a, 3f);
                for (int k = 1; k < ts.Count; k++)
                {
                    if (ts[k] - ts[k - 1] < 1e-4f && k < ts.Count - 1) continue;
                    int cur = NodeAt(Vector2.Lerp(s.a, s.b, ts[k]), 3f);
                    if (cur != prev) AddEdge(prev, cur, s.cls);
                    prev = cur;
                }
            }
        }

        static void TrySnap(Vector2 p, Seg s, List<float> into)
        {
            Vector2 ab = s.b - s.a;
            float L2 = ab.sqrMagnitude;
            if (L2 < 1e-4f) return;
            float t = Vector2.Dot(p - s.a, ab) / L2;
            if (t <= 0.001f || t >= 0.999f) return;
            if ((s.a + ab * t - p).sqrMagnitude < 2.5f * 2.5f) into.Add(t);
        }

        void AddEdge(int a, int b, RoadClass cls)
        {
            foreach (int e in Nodes[a].edges)
            {
                var E = Edges[e];
                if ((E.a == a && E.b == b) || (E.a == b && E.b == a))
                {
                    if (cls > E.cls) E.cls = cls;
                    return;
                }
            }
            Edges.Add(new RoadEdge { a = a, b = b, cls = cls });
            Nodes[a].edges.Add(Edges.Count - 1);
            Nodes[b].edges.Add(Edges.Count - 1);
        }

        void Cleanup()
        {
            // merge junctions closer than 12 m (union-find), rebuild the graph
            int n = Nodes.Count;
            var parent = new int[n];
            for (int i = 0; i < n; i++) parent[i] = i;
            int Find(int x) { while (parent[x] != x) x = parent[x] = parent[parent[x]]; return x; }
            var hash = new Dictionary<long, List<int>>();
            for (int i = 0; i < n; i++)
            {
                var p = Nodes[i].p;
                long k = Key(Mathf.FloorToInt(p.x / 12f), Mathf.FloorToInt(p.y / 12f));
                if (!hash.TryGetValue(k, out var l)) hash[k] = l = new List<int>();
                l.Add(i);
            }
            for (int i = 0; i < n; i++)
            {
                var p = Nodes[i].p;
                int cx = Mathf.FloorToInt(p.x / 12f), cy = Mathf.FloorToInt(p.y / 12f);
                for (int dx = -1; dx <= 1; dx++)
                    for (int dy = -1; dy <= 1; dy++)
                        if (hash.TryGetValue(Key(cx + dx, cy + dy), out var l))
                            foreach (int j in l)
                                if (j > i && (Nodes[j].p - p).sqrMagnitude < 12f * 12f) parent[Find(j)] = Find(i);
            }
            var sum = new Vector2[n];
            var cnt = new int[n];
            for (int i = 0; i < n; i++) { int r = Find(i); sum[r] += Nodes[i].p; cnt[r]++; }
            var oldEdges = new List<RoadEdge>(Edges);
            var remap = new int[n];
            var nodes = new List<RoadNode>();
            for (int i = 0; i < n; i++) remap[i] = -1;
            for (int i = 0; i < n; i++)
            {
                int r = Find(i);
                if (remap[r] < 0) { remap[r] = nodes.Count; nodes.Add(new RoadNode { p = sum[r] / cnt[r] }); }
                remap[i] = remap[r];
            }
            Nodes.Clear();
            Nodes.AddRange(nodes);
            Edges.Clear();
            foreach (var e in oldEdges)
            {
                int a = remap[e.a], b = remap[e.b];
                if (a != b) AddEdge(a, b, e.cls);
            }
            // prune short dead-end spurs, repeatedly
            var dead = new bool[Edges.Count];
            for (int iter = 0; iter < 6; iter++)
            {
                bool any = false;
                for (int e = 0; e < Edges.Count; e++)
                {
                    if (dead[e]) continue;
                    var E = Edges[e];
                    int da = Degree(E.a, dead), db = Degree(E.b, dead);
                    float len = (Nodes[E.a].p - Nodes[E.b].p).magnitude;
                    bool spur = (da == 1 || db == 1) && len < (E.cls == RoadClass.Highway ? 0f : 45f);
                    if (spur || len < 3f) { dead[e] = true; any = true; }
                }
                if (!any) break;
            }
            // drop tiny disconnected bits, then compact
            var comp = new int[Nodes.Count];
            for (int i = 0; i < comp.Length; i++) comp[i] = -1;
            var compSize = new List<int>();
            for (int i = 0; i < Nodes.Count; i++)
            {
                if (comp[i] >= 0) continue;
                int c = compSize.Count;
                compSize.Add(0);
                var stack = new Stack<int>();
                stack.Push(i);
                comp[i] = c;
                while (stack.Count > 0)
                {
                    int x = stack.Pop();
                    foreach (int e in Nodes[x].edges)
                    {
                        if (dead[e]) continue;
                        compSize[c]++;
                        int y = Edges[e].a == x ? Edges[e].b : Edges[e].a;
                        if (comp[y] < 0) { comp[y] = c; stack.Push(y); }
                    }
                }
            }
            int biggest = 0;
            for (int c = 1; c < compSize.Count; c++) if (compSize[c] > compSize[biggest]) biggest = c;
            var keepEdges = new List<RoadEdge>();
            for (int e = 0; e < Edges.Count; e++)
                if (!dead[e] && comp[Edges[e].a] == biggest) keepEdges.Add(Edges[e]);
            var newIndex = new int[Nodes.Count];
            var keepNodes = new List<RoadNode>();
            for (int i = 0; i < Nodes.Count; i++) newIndex[i] = -1;
            foreach (var e in keepEdges)
                foreach (int x in new[] { e.a, e.b })
                    if (newIndex[x] < 0) { newIndex[x] = keepNodes.Count; keepNodes.Add(new RoadNode { p = Nodes[x].p }); }
            Nodes.Clear();
            Nodes.AddRange(keepNodes);
            Edges.Clear();
            foreach (var e in keepEdges) AddEdge(newIndex[e.a], newIndex[e.b], e.cls);
        }

        int Degree(int node, bool[] dead)
        {
            int d = 0;
            foreach (int e in Nodes[node].edges) if (!dead[e]) d++;
            return d;
        }

        void Classify()
        {
            foreach (var e in Edges)
            {
                Vector2 mid = (Nodes[e.a].p + Nodes[e.b].p) * 0.5f;
                e.zone = ZoneAt(mid);
                if (e.zone == Zone.Staging) e.zone = Zone.Park;
                switch (e.cls)
                {
                    case RoadClass.Highway: e.halfWidth = 6f; e.sidewalk = 0f; break;
                    case RoadClass.Arterial:
                        e.halfWidth = 7f;
                        e.sidewalk = e.zone == Zone.Downtown || e.zone == Zone.Midtown ? 4.5f : e.zone == Zone.Rural ? 0f : 3f;
                        break;
                    default:
                        e.halfWidth = e.zone == Zone.Downtown ? 5f : 4f;
                        e.sidewalk = e.zone == Zone.Downtown ? 4f : e.zone == Zone.Midtown ? 3f : e.zone == Zone.Residential ? 2.5f :
                            e.zone == Zone.Industrial ? 1.5f : e.zone == Zone.Rural ? 0f : 2f;
                        break;
                }
            }
        }

        void ComputeTrims()
        {
            foreach (var node in Nodes)
            {
                node.trim = 0f;
                int deg = node.edges.Count;
                if (deg < 2) continue;
                var dirs = SortedDirs(node);
                float maxHalf = 0f;
                for (int i = 0; i < dirs.Count; i++)
                {
                    var (ang, e) = dirs[i];
                    var (ang2, e2) = dirs[(i + 1) % dirs.Count];
                    float th = ang2 - ang;
                    if (th <= 0f) th += Mathf.PI * 2f;
                    float w = Mathf.Max(Edges[e].Outer, Edges[e2].Outer);
                    if (th < Mathf.PI - 0.08f) node.trim = Mathf.Max(node.trim, w / Mathf.Tan(th * 0.5f));
                    maxHalf = Mathf.Max(maxHalf, Edges[e].halfWidth);
                }
                if (deg >= 3) node.trim = Mathf.Max(node.trim, maxHalf + 1f);
                float minLen = float.MaxValue;
                foreach (int e in node.edges) minLen = Mathf.Min(minLen, EdgeLength(e));
                node.trim = Mathf.Min(node.trim, minLen * 0.45f);
            }
        }

        public float EdgeLength(int e) => (Nodes[Edges[e].a].p - Nodes[Edges[e].b].p).magnitude;

        /// <summary>Incident edges of a node sorted counter-clockwise by direction angle.</summary>
        public List<(float ang, int e)> SortedDirs(RoadNode node)
        {
            var list = new List<(float, int)>();
            foreach (int e in node.edges)
            {
                var E = Edges[e];
                Vector2 other = Nodes[E.a] == node ? Nodes[E.b].p : Nodes[E.a].p;
                Vector2 d = other - node.p;
                list.Add((Mathf.Atan2(d.y, d.x), e));
            }
            list.Sort((x, y) => x.Item1.CompareTo(y.Item1));
            return list;
        }

        public float TotalRoadKm()
        {
            float s = 0f;
            for (int e = 0; e < Edges.Count; e++) s += EdgeLength(e);
            return s / 1000f;
        }
    }
}
