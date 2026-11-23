using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    public partial class CityGenerator
    {
        const float RoadLift = 0.05f, CurbH = 0.15f;
        ChunkSet roadChunks, roadCols;

        static Vector3 V3(Vector2 p, float y) => new Vector3(p.x, y, p.y);
        static Vector2 Left(Vector2 d) => new Vector2(-d.y, d.x);

        Material RoadMat(RoadEdge e, out float pattern)
        {
            switch (e.cls)
            {
                case RoadClass.Highway: pattern = 12f; return kit.roadHighway;
                case RoadClass.Arterial: pattern = 14f; return kit.roadArterial;
                default: pattern = 8f; return kit.roadLocal;
            }
        }

        void BuildRoads()
        {
            roadChunks = new ChunkSet(384f);
            roadCols = new ChunkSet(384f);
            for (int i = 0; i < Plan.Edges.Count; i++) RoadEdgeMesh(i);
            foreach (var node in Plan.Nodes) JunctionMesh(node);
            var parent = new GameObject("Roads").transform;
            parent.SetParent(root, false);
            roadChunks.Emit(parent, "Road", false, 0f, false);
            foreach (var go in roadCols.Emit(parent, "RoadCollider", false, 0f, true))
                go.GetComponent<MeshRenderer>().enabled = false;
        }

        void RoadEdgeMesh(int ei)
        {
            var e = Plan.Edges[ei];
            var A = Plan.Nodes[e.a];
            var B = Plan.Nodes[e.b];
            Vector2 d = B.p - A.p;
            float L = d.magnitude;
            if (L < 0.5f) return;
            d /= L;
            Vector2 left = Left(d);
            float tA = A.edges.Count >= 2 ? A.trim : 0f, tB = B.edges.Count >= 2 ? B.trim : 0f;
            if (tA + tB > L - 0.5f) { float k = (L - 0.5f) / Mathf.Max(tA + tB, 0.01f); tA *= k; tB *= k; }
            var mat = RoadMat(e, out float pattern);
            float len = L - tA - tB;
            int pieces = e.cls == RoadClass.Highway || A.y != 0f || B.y != 0f ? Mathf.Max(1, Mathf.CeilToInt(len / 10f)) : 1;
            float hw = e.halfWidth, sw = e.sidewalk;
            for (int k = 0; k < pieces; k++)
            {
                float s0 = tA + len * k / pieces, s1 = tA + len * (k + 1) / pieces;
                Vector2 p0 = A.p + d * s0, p1 = A.p + d * s1;
                float y0 = GroundY(p0, e), y1 = GroundY(p1, e);
                var acc = roadChunks.At(V3((p0 + p1) * 0.5f, 0f));
                var col = roadCols.At(V3((p0 + p1) * 0.5f, 0f));
                Vector3 r0 = V3(p0 - left * hw, y0 + RoadLift), l0 = V3(p0 + left * hw, y0 + RoadLift);
                Vector3 r1 = V3(p1 - left * hw, y1 + RoadLift), l1 = V3(p1 + left * hw, y1 + RoadLift);
                float v0 = s0 / pattern, v1 = s1 / pattern;
                acc.Quad(mat, r0, l0, l1, r1, new Vector2(0f, v0), new Vector2(1f, v0), new Vector2(1f, v1), new Vector2(0f, v1), Vector3.up);
                col.Quad(mat, r0, l0, l1, r1, Vector2.zero, Vector2.zero, Vector2.zero, Vector2.zero, Vector3.up);
                if (sw > 0f)
                {
                    foreach (int side in new[] { -1, 1 })
                    {
                        Vector2 n = left * side;
                        Vector3 c0 = V3(p0 + n * hw, y0 + RoadLift), c1 = V3(p1 + n * hw, y1 + RoadLift);
                        Vector3 t0 = c0 + Vector3.up * CurbH, t1 = c1 + Vector3.up * CurbH;
                        Vector3 o0 = V3(p0 + n * (hw + sw), y0 + RoadLift + CurbH), o1 = V3(p1 + n * (hw + sw), y1 + RoadLift + CurbH);
                        Vector3 nf = V3(-n, 0f);
                        acc.QuadP(kit.curb, c0, c1, t1, t0, nf, 1f);
                        acc.QuadP(kit.sidewalk, t0, t1, o1, o0, Vector3.up, 3f);
                        acc.QuadP(kit.curb, o0, o1, o1 + Vector3.down * 0.45f, o0 + Vector3.down * 0.45f, V3(n, 0f), 1f);
                        col.QuadP(kit.curb, c0, c1, t1, t0, nf, 1f);
                        col.QuadP(kit.sidewalk, t0, t1, o1, o0, Vector3.up, 3f);
                    }
                }
                else
                {
                    // rural road / highway: edges skirt down into the verge
                    acc.QuadP(kit.asphalt, r0, r1, r1 + Vector3.down * 0.8f, r0 + Vector3.down * 0.8f, V3(-left, 0f), 4f);
                    acc.QuadP(kit.asphalt, l0, l1, l1 + Vector3.down * 0.8f, l0 + Vector3.down * 0.8f, V3(left, 0f), 4f);
                }
            }
            // keep the road corridor free of trees
            PaintOver((A.p + B.p) * 0.5f, new Vector2(e.Outer + 1.5f, L * 0.5f), Mathf.Atan2(d.x, d.y) * Mathf.Rad2Deg, 5);
        }

        float GroundY(Vector2 p, RoadEdge e) => e.cls == RoadClass.Highway || !Plan.InCity(p, 200f) ? HeightAt(p.x, p.y) : 0f;

        void JunctionMesh(RoadNode node)
        {
            int deg = node.edges.Count;
            float y = node.y + RoadLift;
            var acc = roadChunks.At(V3(node.p, 0f));
            var col = roadCols.At(V3(node.p, 0f));
            if (deg == 1)
            {
                var e = Plan.Edges[node.edges[0]];
                if (e.cls == RoadClass.Highway || e.sidewalk <= 0f) return;
                // cul-de-sac turnaround
                const int segs = 14;
                float r = e.halfWidth + 2f, ro = r + e.sidewalk;
                for (int i = 0; i < segs; i++)
                {
                    float a0 = i / (float)segs * Mathf.PI * 2f, a1 = (i + 1) / (float)segs * Mathf.PI * 2f;
                    Vector2 u0 = new Vector2(Mathf.Cos(a0), Mathf.Sin(a0)), u1 = new Vector2(Mathf.Cos(a1), Mathf.Sin(a1));
                    Vector3 c = V3(node.p, y);
                    Vector3 e0 = V3(node.p + u0 * r, y), e1 = V3(node.p + u1 * r, y);
                    acc.Quad(kit.asphalt, c, e0, e1, c, UVp(c, 8f), UVp(e0, 8f), UVp(e1, 8f), UVp(c, 8f), Vector3.up);
                    col.Quad(kit.asphalt, c, e0, e1, c, Vector2.zero, Vector2.zero, Vector2.zero, Vector2.zero, Vector3.up);
                    Vector3 t0 = e0 + Vector3.up * CurbH, t1 = e1 + Vector3.up * CurbH;
                    Vector3 o0 = V3(node.p + u0 * ro, y + CurbH), o1 = V3(node.p + u1 * ro, y + CurbH);
                    acc.QuadP(kit.curb, e0, e1, t1, t0, V3(-(u0 + u1), 0f), 1f);
                    acc.QuadP(kit.sidewalk, t0, t1, o1, o0, Vector3.up, 3f);
                    acc.QuadP(kit.curb, o0, o1, o1 + Vector3.down * 0.45f, o0 + Vector3.down * 0.45f, V3(u0 + u1, 0f), 1f);
                    col.QuadP(kit.sidewalk, t0, t1, o1, o0, Vector3.up, 3f);
                }
                return;
            }
            if (node.trim < 0.05f) return;
            var dirs = Plan.SortedDirs(node);
            int n = dirs.Count;
            var R = new Vector2[n];
            var Lc = new Vector2[n];
            var D = new Vector2[n];
            var E = new RoadEdge[n];
            for (int i = 0; i < n; i++)
            {
                var e = Plan.Edges[dirs[i].e];
                Vector2 d = new Vector2(Mathf.Cos(dirs[i].ang), Mathf.Sin(dirs[i].ang));
                Vector2 c = node.p + d * node.trim;
                D[i] = d;
                E[i] = e;
                R[i] = c - Left(d) * e.halfWidth;
                Lc[i] = c + Left(d) * e.halfWidth;
            }
            // asphalt polygon around the junction, fanned from the centre
            var poly = new List<Vector3>();
            for (int i = 0; i < n; i++) { poly.Add(V3(R[i], y)); poly.Add(V3(Lc[i], y)); }
            Vector3 ctr = V3(node.p, y);
            for (int i = 0; i < poly.Count; i++)
            {
                Vector3 a = poly[i], b = poly[(i + 1) % poly.Count];
                acc.Quad(kit.asphalt, ctr, a, b, ctr, UVp(ctr, 8f), UVp(a, 8f), UVp(b, 8f), UVp(ctr, 8f), Vector3.up);
                col.Quad(kit.asphalt, ctr, a, b, ctr, Vector2.zero, Vector2.zero, Vector2.zero, Vector2.zero, Vector3.up);
            }
            // sidewalk corners between neighbouring roads
            for (int i = 0; i < n; i++)
            {
                int j = (i + 1) % n;
                float swi = E[i].sidewalk, swj = E[j].sidewalk;
                if (swi <= 0f && swj <= 0f) continue;
                float sw = Mathf.Max(swi, swj);
                Vector2 li = Lc[i], rj = R[j];
                Vector2 lo = li + Left(D[i]) * (swi > 0f ? swi : sw), roo = rj - Left(D[j]) * (swj > 0f ? swj : sw);
                var pts = new List<Vector3> { V3(li, y + CurbH), V3(lo, y + CurbH) };
                // the corner where the two outer sidewalk edges meet, when it lies beyond the trimmed ends
                if (LineX(lo, D[i], roo, D[j], out Vector2 x, out float ti, out float tj) && ti > 0.2f && tj > 0.2f && ti < 40f && tj < 40f)
                    pts.Add(V3(x, y + CurbH));
                pts.Add(V3(roo, y + CurbH));
                pts.Add(V3(rj, y + CurbH));
                var uvs = new List<Vector2>();
                foreach (var p in pts) uvs.Add(UVp(p, 3f));
                acc.Poly(kit.sidewalk, pts, uvs, Vector3.up);
                col.Poly(kit.sidewalk, pts, uvs, Vector3.up);
                Vector3 a0 = V3(li, y), b0 = V3(rj, y);
                Vector3 inward = V3(node.p - (li + rj) * 0.5f, 0f);
                acc.QuadP(kit.curb, a0, b0, b0 + Vector3.up * CurbH, a0 + Vector3.up * CurbH, inward, 1f);
                col.QuadP(kit.curb, a0, b0, b0 + Vector3.up * CurbH, a0 + Vector3.up * CurbH, inward, 1f);
            }
            // zebra crossings on city streets at real junctions
            if (n >= 3)
                for (int i = 0; i < n; i++)
                {
                    if (E[i].cls == RoadClass.Highway || E[i].sidewalk <= 0f) continue;
                    Vector2 c0 = node.p + D[i] * (node.trim + 0.6f), c1 = node.p + D[i] * (node.trim + 4.2f);
                    float hw = E[i].halfWidth - 0.4f;
                    Vector2 l = Left(D[i]);
                    float yy = y + 0.012f;
                    float uw = E[i].halfWidth * 2f / 3.2f;
                    acc.Quad(kit.crosswalk, V3(c0 - l * hw, yy), V3(c0 + l * hw, yy), V3(c1 + l * hw, yy), V3(c1 - l * hw, yy),
                        new Vector2(0f, 0f), new Vector2(uw, 0f), new Vector2(uw, 1f), new Vector2(0f, 1f), Vector3.up);
                }
        }

        static Vector2 UVp(Vector3 p, float tile) => new Vector2(p.x / tile, p.z / tile);

        /// <summary>Intersection of the lines p + s*dp and q + t*dq.</summary>
        static bool LineX(Vector2 p, Vector2 dp, Vector2 q, Vector2 dq, out Vector2 x, out float s, out float t)
        {
            float den = dp.x * dq.y - dp.y * dq.x;
            x = Vector2.zero;
            s = t = 0f;
            if (Mathf.Abs(den) < 1e-4f) return false;
            Vector2 qp = q - p;
            s = (qp.x * dq.y - qp.y * dq.x) / den;
            t = (qp.x * dp.y - qp.y * dp.x) / den;
            x = p + dp * s;
            return true;
        }

        // ------------------------------------------------------------------ runways
        void BuildRunways()
        {
            var acc = new MeshAcc();
            foreach (var (c, h) in new[] { (Plan.AirS, airHeightS), (Plan.AirN, airHeightN) })
            {
                float y = h + 0.06f;
                float hw = CityPlan.AirHalfWidth - 10f, hl = CityPlan.AirHalfLen;
                Vector3 a = new Vector3(c.x - hw, y, c.y - hl), b = new Vector3(c.x + hw, y, c.y - hl);
                Vector3 d = new Vector3(c.x + hw, y, c.y + hl), e = new Vector3(c.x - hw, y, c.y + hl);
                acc.Quad(kit.runway, a, b, d, e, new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(1f, 1f), new Vector2(0f, 1f), Vector3.up);
                PaintOver(c, new Vector2(CityPlan.AirHalfWidth + 20f, CityPlan.AirHalfLen + 30f), 0f, 5);
            }
            var go = new GameObject("Airfields");
            go.transform.SetParent(root, false);
            go.AddComponent<MeshFilter>().sharedMesh = acc.Build("Runways");
            go.AddComponent<MeshRenderer>().sharedMaterials = acc.mats.ToArray();
            go.isStatic = true;
        }

        public float AirfieldHeight(bool north) => north ? airHeightN : airHeightS;
    }
}
