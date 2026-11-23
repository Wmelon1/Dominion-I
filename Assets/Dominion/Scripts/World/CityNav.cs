using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// City navigation for the AI. Two 2 m clearance grids (distance to the nearest obstacle): one for infantry, where
    /// everything blocks, and one for heavy units (tanks, armour, mechs), which crush parked cars and so only steer around
    /// buildings, barricades and trees. They answer "can a unit of radius r go straight from A to B"; long trips run A*
    /// over the road network (each edge knows the widest unit it can pass on each layer), short detours run a windowed
    /// grid A*. Paths are string-pulled. A per-frame budget keeps hundreds of AI units cheap. Inactive (straight lines)
    /// on maps without a city.
    /// </summary>
    public static class CityNav
    {
        public static bool Active { get; private set; }
        const float Cell = 2f;
        static float half;
        static int W;
        static byte[] clrAll, clrHeavy;     // clearance in 0.25 m units (0 = blocked)
        static Vector2[] nodes;
        static List<(int to, float cost, float clearAll, float clearHeavy)>[] adj;
        static readonly Dictionary<long, List<int>> nodeHash = new Dictionary<long, List<int>>();
        const float NodeCell = 80f;
        static int frame, used;
        public const int Budget = 6;
        /// <summary>Planning time allowed per frame (ms); requests over budget wait for the next frame.</summary>
        public const double FrameMs = 2.0;
        public static int TotalPaths, FailedPaths, GridSearches;
        public static double TotalMs;
        static double frameMs;
        static readonly System.Diagnostics.Stopwatch clock = new System.Diagnostics.Stopwatch();

        public static void Clear()
        {
            Active = false;
            clrAll = clrHeavy = null;
            nodes = null;
            adj = null;
            nodeHash.Clear();
            TotalPaths = FailedPaths = GridSearches = 0;
            TotalMs = 0;
        }

        static long Key(int x, int y) => ((long)x << 32) ^ (uint)y;

        /// <summary>boxes: centre, half size, yaw (deg), and whether heavy units ignore it (parked cars).</summary>
        public static void Build(CityPlan plan, List<(Vector2 c, Vector2 half, float yaw, bool crushable)> boxes, float halfExtent)
        {
            half = halfExtent;
            W = Mathf.CeilToInt(half * 2f / Cell);
            var all = new int[W * W];
            var heavy = new int[W * W];
            const int Big = 1 << 20;
            for (int i = 0; i < all.Length; i++) all[i] = heavy[i] = Big;
            foreach (var (c, h, yaw, crushable) in boxes)
            {
                float r = yaw * Mathf.Deg2Rad;
                Vector2 ax = new Vector2(Mathf.Cos(r), -Mathf.Sin(r)), az = new Vector2(Mathf.Sin(r), Mathf.Cos(r));
                float ext = h.magnitude + Cell;
                int i0 = Mathf.Max(0, (int)((c.x - ext + half) / Cell)), i1 = Mathf.Min(W - 1, (int)((c.x + ext + half) / Cell));
                int j0 = Mathf.Max(0, (int)((c.y - ext + half) / Cell)), j1 = Mathf.Min(W - 1, (int)((c.y + ext + half) / Cell));
                bool any = false;
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                    {
                        Vector2 p = new Vector2(-half + (i + 0.5f) * Cell, -half + (j + 0.5f) * Cell) - c;
                        if (Mathf.Abs(Vector2.Dot(p, ax)) <= h.x && Mathf.Abs(Vector2.Dot(p, az)) <= h.y)
                        {
                            all[j * W + i] = 0;
                            if (!crushable) heavy[j * W + i] = 0;
                            any = true;
                        }
                    }
                if (!any)
                {
                    // small obstacle between cell centres: block the cell it sits in
                    int ci = (int)((c.x + half) / Cell), cj = (int)((c.y + half) / Cell);
                    if (ci >= 0 && cj >= 0 && ci < W && cj < W)
                    {
                        all[cj * W + ci] = 0;
                        if (!crushable) heavy[cj * W + ci] = 0;
                    }
                }
            }
            clrAll = Transform(all);
            clrHeavy = Transform(heavy);
            // road graph: each edge knows the narrowest clearance along it on both layers
            nodes = new Vector2[plan.Nodes.Count];
            adj = new List<(int, float, float, float)>[nodes.Length];
            nodeHash.Clear();
            for (int i = 0; i < nodes.Length; i++)
            {
                nodes[i] = plan.Nodes[i].p;
                adj[i] = new List<(int, float, float, float)>();
                long k = Key(Mathf.FloorToInt(nodes[i].x / NodeCell), Mathf.FloorToInt(nodes[i].y / NodeCell));
                if (!nodeHash.TryGetValue(k, out var l)) nodeHash[k] = l = new List<int>();
                l.Add(i);
            }
            foreach (var e in plan.Edges)
            {
                Vector2 a = nodes[e.a], b = nodes[e.b];
                float len = (b - a).magnitude, ma = 99f, mh = 99f;
                int n = Mathf.Max(1, Mathf.CeilToInt(len / Cell));
                for (int s = 0; s <= n; s++)
                {
                    Vector2 p = Vector2.Lerp(a, b, s / (float)n);
                    ma = Mathf.Min(ma, Clearance(p, false));
                    mh = Mathf.Min(mh, Clearance(p, true));
                }
                adj[e.a].Add((e.b, len, ma, mh));
                adj[e.b].Add((e.a, len, ma, mh));
            }
            Active = true;
        }

        /// <summary>Chamfer distance transform (3 per straight step, 4 per diagonal) to clearance in quarter metres.</summary>
        static byte[] Transform(int[] dist)
        {
            for (int j = 0; j < W; j++)
                for (int i = 0; i < W; i++)
                {
                    int k = j * W + i;
                    int v = dist[k];
                    if (v == 0) continue;
                    if (i > 0) v = Mathf.Min(v, dist[k - 1] + 3);
                    if (j > 0)
                    {
                        v = Mathf.Min(v, dist[k - W] + 3);
                        if (i > 0) v = Mathf.Min(v, dist[k - W - 1] + 4);
                        if (i < W - 1) v = Mathf.Min(v, dist[k - W + 1] + 4);
                    }
                    dist[k] = v;
                }
            for (int j = W - 1; j >= 0; j--)
                for (int i = W - 1; i >= 0; i--)
                {
                    int k = j * W + i;
                    int v = dist[k];
                    if (v == 0) continue;
                    if (i < W - 1) v = Mathf.Min(v, dist[k + 1] + 3);
                    if (j < W - 1)
                    {
                        v = Mathf.Min(v, dist[k + W] + 3);
                        if (i < W - 1) v = Mathf.Min(v, dist[k + W + 1] + 4);
                        if (i > 0) v = Mathf.Min(v, dist[k + W - 1] + 4);
                    }
                    dist[k] = v;
                }
            var clr = new byte[W * W];
            // distance between cell centres, minus half a cell: the free distance from this cell's centre to the obstacle's edge
            for (int k = 0; k < clr.Length; k++)
                clr[k] = dist[k] == 0 ? (byte)0 : (byte)Mathf.Clamp(Mathf.RoundToInt((dist[k] / 3f * Cell - Cell * 0.5f) * 4f), 1, 255);
            return clr;
        }

        public static float Clearance(Vector2 p, bool heavy = false)
        {
            var clr = heavy ? clrHeavy : clrAll;
            if (clr == null) return 99f;
            int i = (int)((p.x + half) / Cell), j = (int)((p.y + half) / Cell);
            if (i < 0 || j < 0 || i >= W || j >= W) return 64f;
            return clr[j * W + i] * 0.25f;
        }

        public static bool LineClear(Vector2 a, Vector2 b, float r, bool heavy = false)
        {
            if (!Active) return true;
            float L = (b - a).magnitude;
            int n = Mathf.Max(1, Mathf.CeilToInt(L / (Cell * 0.7f)));
            for (int k = 0; k <= n; k++)
                if (Clearance(Vector2.Lerp(a, b, k / (float)n), heavy) < r) return false;
            return true;
        }

        public static bool LineClear(Vector3 a, Vector3 b, float r, bool heavy = false) =>
            LineClear(new Vector2(a.x, a.z), new Vector2(b.x, b.z), r, heavy);

        /// <summary>The nearest point with at least r clearance (searching outward up to 'search' metres).</summary>
        public static Vector2 NearestFree(Vector2 p, float r, bool heavy = false, float search = 40f)
        {
            if (Clearance(p, heavy) >= r) return p;
            for (float rad = Cell; rad <= search; rad += Cell)
            {
                int steps = Mathf.Max(8, Mathf.CeilToInt(rad * 2f * Mathf.PI / Cell));
                Vector2 best = p;
                float bc = -1f;
                for (int s = 0; s < steps; s++)
                {
                    float a = s * Mathf.PI * 2f / steps;
                    Vector2 q = p + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * rad;
                    float c = Clearance(q, heavy);
                    if (c >= r && c > bc) { bc = c; best = q; }
                }
                if (bc >= r) return best;
            }
            return p;
        }

        /// <summary>Plan a path; false when out of this frame's budget (try again next frame).</summary>
        public static bool FindPath(Vector3 from, Vector3 to, float r, List<Vector3> path, bool heavy = false)
        {
            if (Time.frameCount != frame) { frame = Time.frameCount; used = 0; frameMs = 0; }
            if (used >= Budget || frameMs > FrameMs) return false;
            used++;
            TotalPaths++;
            clock.Restart();
            try { return Plan(from, to, r, path, heavy); }
            finally
            {
                double ms = clock.Elapsed.TotalMilliseconds;
                frameMs += ms;
                TotalMs += ms;
            }
        }

        static readonly List<Vector2> pts = new List<Vector2>();

        static bool Plan(Vector3 from, Vector3 to, float r, List<Vector3> path, bool heavy)
        {
            path.Clear();
            Vector2 a = new Vector2(from.x, from.z);
            Vector2 b = NearestFree(new Vector2(to.x, to.z), r, heavy);
            float y = to.y;
            if (LineClear(a, b, r, heavy)) { path.Add(new Vector3(b.x, y, b.y)); return true; }
            pts.Clear();
            Vector2 a0 = NearestFree(a, r, heavy, 10f);
            // short hops: a local grid search; longer trips: along the streets
            bool ok = (b - a).sqrMagnitude < 140f * 140f && GridAStar(a0, b, r, heavy, 3500, pts);
            if (!ok)
            {
                pts.Clear();
                var sa = VisibleNodes(a0, r, heavy);
                var sb = VisibleNodes(b, r, heavy);
                ok = sa.Count > 0 && sb.Count > 0 && GraphAStar(a0, b, sa, sb, r, heavy, pts);
                if (!ok && sa.Count > 0)
                {
                    // the goal can't see a street (a courtyard, a narrow gap): drive to the street nearest the goal
                    var near = VisibleNodes(b, 0.3f, heavy);
                    pts.Clear();
                    ok = near.Count > 0 && GraphAStar(a0, nodes[near[0]], sa, new List<int> { near[0] }, r, heavy, pts);
                }
                if (!ok && (b - a).sqrMagnitude < 380f * 380f)
                {
                    pts.Clear();
                    ok = GridAStar(a0, b, r, heavy, 9000, pts);
                }
                if (!ok)
                {
                    FailedPaths++;
                    path.Add(new Vector3(b.x, y, b.y));
                    return true;
                }
            }
            // string-pull (keeps r clearance along every straight leg)
            Vector2 cur = a0;
            if ((a0 - a).sqrMagnitude > 1f) path.Add(new Vector3(a0.x, y, a0.y));
            int i = 0;
            while (i < pts.Count)
            {
                int far = i;
                for (int j = Mathf.Min(pts.Count - 1, i + 12); j > i; j--)
                    if (LineClear(cur, pts[j], r, heavy)) { far = j; break; }
                cur = pts[far];
                path.Add(new Vector3(cur.x, y, cur.y));
                i = far + 1;
            }
            return true;
        }

        static readonly List<(float d, int i)> cand = new List<(float, int)>();

        static List<int> VisibleNodes(Vector2 p, float r, bool heavy)
        {
            cand.Clear();
            int cx = Mathf.FloorToInt(p.x / NodeCell), cy = Mathf.FloorToInt(p.y / NodeCell);
            for (int dx = -3; dx <= 3; dx++)
                for (int dy = -3; dy <= 3; dy++)
                    if (nodeHash.TryGetValue(Key(cx + dx, cy + dy), out var l))
                        foreach (int i in l)
                        {
                            float d = (nodes[i] - p).sqrMagnitude;
                            if (d < 240f * 240f) cand.Add((d, i));
                        }
            cand.Sort((x, y) => x.d.CompareTo(y.d));
            var res = new List<int>();
            int tests = 0;
            foreach (var (_, i) in cand)
            {
                if (tests++ > 12 || res.Count >= 5) break;
                if (LineClear(p, nodes[i], r, heavy)) res.Add(i);
            }
            return res;
        }

        // ------------------------------------------------------------------ A* on the road graph
        static float[] g;
        static int[] from, stamp;
        static int stampId;

        static bool GraphAStar(Vector2 a, Vector2 b, List<int> starts, List<int> goals, float r, bool heavy, List<Vector2> outPts)
        {
            int n = nodes.Length;
            if (g == null || g.Length != n) { g = new float[n]; from = new int[n]; stamp = new int[n]; }
            stampId++;
            var goalSet = new HashSet<int>(goals);
            var open = new Heap();
            foreach (int s in starts)
            {
                stamp[s] = stampId;
                g[s] = (nodes[s] - a).magnitude;
                from[s] = -1;
                open.Push(s, g[s] + (nodes[s] - b).magnitude);
            }
            int found = -1, expanded = 0;
            while (open.Count > 0 && expanded < 6000)
            {
                int u = open.Pop(out float f);
                if (f > g[u] + (nodes[u] - b).magnitude + 0.01f) continue;
                expanded++;
                if (goalSet.Contains(u)) { found = u; break; }
                foreach (var (v, cost, ca, ch) in adj[u])
                {
                    if ((heavy ? ch : ca) < r) continue;
                    float ng = g[u] + cost;
                    if (stamp[v] == stampId && ng >= g[v]) continue;
                    stamp[v] = stampId;
                    g[v] = ng;
                    from[v] = u;
                    open.Push(v, ng + (nodes[v] - b).magnitude);
                }
            }
            if (found < 0) return false;
            var rev = new List<Vector2>();
            for (int k = found; k >= 0; k = from[k]) rev.Add(nodes[k]);
            rev.Reverse();
            outPts.AddRange(rev);
            outPts.Add(b);
            return true;
        }

        // ------------------------------------------------------------------ bounded A* on the clearance grid (local window)
        const int Win = 200;                              // 400 m window around the start and goal
        static readonly float[] wg = new float[Win * Win];
        static readonly int[] wpar = new int[Win * Win];
        static readonly int[] wstamp = new int[Win * Win];
        static int wstampId;

        static bool GridAStar(Vector2 a, Vector2 b, float r, bool heavy, int maxExpand, List<Vector2> outPts)
        {
            GridSearches++;
            var clr = heavy ? clrHeavy : clrAll;
            int ai = (int)((a.x + half) / Cell), aj = (int)((a.y + half) / Cell);
            int bi = (int)((b.x + half) / Cell), bj = (int)((b.y + half) / Cell);
            if (Mathf.Abs(ai - bi) > Win - 8 || Mathf.Abs(aj - bj) > Win - 8) return false;
            if (ai < 0 || aj < 0 || ai >= W || aj >= W || bi < 0 || bj < 0 || bi >= W || bj >= W) return false;
            int oi = (ai + bi) / 2 - Win / 2, oj = (aj + bj) / 2 - Win / 2;
            wstampId++;
            int start = (aj - oj) * Win + (ai - oi), goal = (bj - oj) * Win + (bi - oi);
            byte need = (byte)Mathf.Clamp(Mathf.CeilToInt(r * 4f), 1, 255);
            var open = new Heap();
            wstamp[start] = wstampId;
            wg[start] = 0f;
            wpar[start] = -1;
            open.Push(start, H2(start, bi - oi, bj - oj));
            int expanded = 0;
            bool found = false;
            while (open.Count > 0 && expanded < maxExpand)
            {
                int u = open.Pop(out float f);
                float gu = wg[u];
                int ui = u % Win, uj = u / Win;
                if (f > gu + H2(u, bi - oi, bj - oj) + 0.01f) continue;
                if (u == goal) { found = true; break; }
                expanded++;
                for (int dj = -1; dj <= 1; dj++)
                    for (int di = -1; di <= 1; di++)
                    {
                        if (di == 0 && dj == 0) continue;
                        int vi = ui + di, vj = uj + dj;
                        if (vi < 0 || vj < 0 || vi >= Win || vj >= Win) continue;
                        int gi = vi + oi, gj = vj + oj;
                        if (gi < 0 || gj < 0 || gi >= W || gj >= W) continue;
                        int v = vj * Win + vi;
                        byte c = clr[gj * W + gi];
                        if (c < need && v != goal) continue;
                        // prefer the middle of open space: cells close to obstacles cost a little more
                        float step = di != 0 && dj != 0 ? 1.4142f : 1f;
                        float ng = gu + step * (c < need + 8 ? 1.35f : 1f);
                        if (wstamp[v] == wstampId && ng >= wg[v]) continue;
                        wstamp[v] = wstampId;
                        wg[v] = ng;
                        wpar[v] = u;
                        open.Push(v, ng + H2(v, bi - oi, bj - oj));
                    }
            }
            if (!found) return false;
            var rev = new List<Vector2>();
            for (int k = goal; k >= 0; k = wpar[k])
                rev.Add(new Vector2(-half + (k % Win + oi + 0.5f) * Cell, -half + (k / Win + oj + 0.5f) * Cell));
            rev.Reverse();
            rev[rev.Count - 1] = b;
            outPts.AddRange(rev);
            return true;
        }

        static float H2(int k, int bi, int bj)
        {
            int dx = Mathf.Abs(k % Win - bi), dy = Mathf.Abs(k / Win - bj);
            return Mathf.Max(dx, dy) + 0.4142f * Mathf.Min(dx, dy);
        }

        /// <summary>Minimal binary heap of (item, priority).</summary>
        class Heap
        {
            readonly List<(int item, float pri)> a = new List<(int, float)>();
            public int Count => a.Count;

            public void Push(int item, float pri)
            {
                a.Add((item, pri));
                int i = a.Count - 1;
                while (i > 0)
                {
                    int p = (i - 1) / 2;
                    if (a[p].pri <= a[i].pri) break;
                    (a[p], a[i]) = (a[i], a[p]);
                    i = p;
                }
            }

            public int Pop(out float pri)
            {
                var top = a[0];
                int last = a.Count - 1;
                a[0] = a[last];
                a.RemoveAt(last);
                int i = 0;
                while (true)
                {
                    int l = i * 2 + 1, r = l + 1, m = i;
                    if (l < a.Count && a[l].pri < a[m].pri) m = l;
                    if (r < a.Count && a[r].pri < a[m].pri) m = r;
                    if (m == i) break;
                    (a[m], a[i]) = (a[i], a[m]);
                    i = m;
                }
                pri = top.pri;
                return top.item;
            }
        }
    }

    /// <summary>
    /// One unit's current route. Replans when the destination moves, the route gets old or the unit has drifted off it;
    /// steers at a point 'lookahead' metres further along the route (pure pursuit), so vehicles follow the street around
    /// corners instead of cutting them, and reports the sharpest turn coming up so drivers can slow for it.
    /// </summary>
    public class NavPath
    {
        readonly List<Vector3> pts = new List<Vector3>();       // pts[0] = where we started
        readonly List<Vector3> tmp = new List<Vector3>();
        readonly float radius, replanDist, replanEvery;
        readonly bool heavy;
        int seg;
        Vector3 goal;
        float planT = -99f;
        public float Deviation { get; private set; }

        public NavPath(float radius, float replanDist, float replanEvery, bool heavy = false)
        {
            this.radius = radius;
            this.replanDist = replanDist;
            this.replanEvery = replanEvery;
            this.heavy = heavy;
        }

        public int Count => pts.Count;
        public void Invalidate() => pts.Clear();

        static float Flat(Vector3 a, Vector3 b) { a.y = b.y = 0f; return Vector3.Distance(a, b); }

        static float ProjT(Vector3 p, Vector3 a, Vector3 b)
        {
            Vector3 ab = b - a;
            ab.y = 0f;
            Vector3 ap = p - a;
            ap.y = 0f;
            return Vector3.Dot(ap, ab) / Mathf.Max(ab.sqrMagnitude, 1e-4f);
        }

        void Plan(Vector3 pos, Vector3 dest)
        {
            if (CityNav.LineClear(pos, dest, radius, heavy))
            {
                pts.Clear();
                pts.Add(pos);
                pts.Add(dest);
            }
            else if (CityNav.FindPath(pos, dest, radius, tmp, heavy))
            {
                pts.Clear();
                pts.Add(pos);
                pts.AddRange(tmp);
            }
            else return;                                         // over this frame's budget: keep the old route
            seg = 0;
            goal = dest;
            planT = Time.time;
            Deviation = 0f;
        }

        public Vector3 Steer(Vector3 pos, Vector3 dest, float lookahead = 0f)
        {
            if (!CityNav.Active) return dest;
            Vector3 dg = dest - goal;
            dg.y = 0f;
            if (pts.Count < 2 || dg.sqrMagnitude > replanDist * replanDist || Time.time - planT > replanEvery || Deviation > radius * 2f + 4f)
                Plan(pos, dest);
            if (pts.Count < 2) return dest;
            while (seg < pts.Count - 2 && (ProjT(pos, pts[seg], pts[seg + 1]) >= 1f || Flat(pos, pts[seg + 1]) < 2.5f)) seg++;
            float t = Mathf.Clamp01(ProjT(pos, pts[seg], pts[seg + 1]));
            Vector3 p = Vector3.Lerp(pts[seg], pts[seg + 1], t);
            Deviation = Flat(pos, p);
            if (lookahead <= 0f) return pts[seg + 1];
            float remain = lookahead;
            int k = seg;
            while (remain > 0f && k < pts.Count - 1)
            {
                float d = Flat(p, pts[k + 1]);
                if (d >= remain)
                {
                    Vector3 dir = pts[k + 1] - p;
                    dir.y = 0f;
                    p += dir.normalized * remain;
                    break;
                }
                remain -= d;
                p = pts[k + 1];
                k++;
            }
            return p;
        }

        /// <summary>The sharpest turn (deg) at route corners within 'within' metres ahead.</summary>
        public float TurnAhead(Vector3 pos, float within)
        {
            if (!CityNav.Active || pts.Count < 3) return 0f;
            float acc = Flat(pos, pts[Mathf.Min(seg + 1, pts.Count - 1)]);
            float worst = 0f;
            for (int k = seg + 1; k < pts.Count - 1 && acc <= within; k++)
            {
                Vector3 a = pts[k] - pts[k - 1], b = pts[k + 1] - pts[k];
                a.y = b.y = 0f;
                if (a.sqrMagnitude > 0.01f && b.sqrMagnitude > 0.01f) worst = Mathf.Max(worst, Vector3.Angle(a, b));
                acc += b.magnitude;
            }
            return worst;
        }
    }
}
