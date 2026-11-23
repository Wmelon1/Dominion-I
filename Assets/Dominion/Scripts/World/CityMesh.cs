using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Dominion
{
    /// <summary>Accumulates flat-shaded geometry with one submesh per material.</summary>
    public class MeshAcc
    {
        public readonly List<Vector3> v = new List<Vector3>();
        public readonly List<Vector3> n = new List<Vector3>();
        public readonly List<Vector2> uv = new List<Vector2>();
        public readonly List<Material> mats = new List<Material>();
        public readonly List<List<int>> tris = new List<List<int>>();
        public Bounds bounds;
        bool any;

        List<int> T(Material m)
        {
            int i = mats.IndexOf(m);
            if (i < 0) { mats.Add(m); tris.Add(new List<int>()); i = mats.Count - 1; }
            return tris[i];
        }

        void Grow(Vector3 p)
        {
            if (!any) { bounds = new Bounds(p, Vector3.zero); any = true; }
            else bounds.Encapsulate(p);
        }

        /// <summary>Triangle fan / quad: points in order; the face is flipped if needed so its normal agrees with 'facing'.</summary>
        public void Poly(Material m, IList<Vector3> p, IList<Vector2> t, Vector3 facing)
        {
            int c = p.Count;
            if (c < 3 || m == null) return;
            Vector3 nrm = Vector3.zero;
            for (int i = 0; i < c; i++) nrm += Vector3.Cross(p[i], p[(i + 1) % c]);
            if (nrm.sqrMagnitude < 1e-10f) return;
            // Unity draws triangle (a, b, c) facing Cross(b - a, c - a), which is the direction of this loop sum for
            // the points in order: keep the order when it already faces 'facing', otherwise emit reversed.
            bool rev = Vector3.Dot(nrm, facing) < 0f;
            Vector3 fn = (rev ? -nrm : nrm).normalized;
            var list = T(m);
            int b = v.Count;
            for (int i = 0; i < c; i++)
            {
                int k = rev ? c - 1 - i : i;
                v.Add(p[k]);
                n.Add(fn);
                uv.Add(t[k]);
                Grow(p[k]);
            }
            for (int i = 1; i < c - 1; i++) { list.Add(b); list.Add(b + i); list.Add(b + i + 1); }
        }

        public void Quad(Material m, Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector2 ta, Vector2 tb, Vector2 tc, Vector2 td, Vector3 facing)
        {
            qp[0] = a; qp[1] = b; qp[2] = c; qp[3] = d;
            qt[0] = ta; qt[1] = tb; qt[2] = tc; qt[3] = td;
            Poly(m, qp, qt, facing);
        }

        readonly Vector3[] qp = new Vector3[4];
        readonly Vector2[] qt = new Vector2[4];

        /// <summary>Quad with world-planar UVs (xz for flat faces, along/up for walls) at 'tile' metres per repeat.</summary>
        public void QuadP(Material m, Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 facing, float tile)
        {
            Quad(m, a, b, c, d, PUV(a, facing, tile), PUV(b, facing, tile), PUV(c, facing, tile), PUV(d, facing, tile), facing);
        }

        public static Vector2 PUV(Vector3 p, Vector3 n, float tile)
        {
            if (Mathf.Abs(n.y) > 0.7f) return new Vector2(p.x / tile, p.z / tile);
            Vector3 along = Vector3.Cross(Vector3.up, n).normalized;
            return new Vector2(Vector3.Dot(p, along) / tile, p.y / tile);
        }

        /// <summary>Append another mesh (all submeshes) transformed by M, with its materials.</summary>
        public void Append(Mesh mesh, Material[] materials, Matrix4x4 M)
        {
            var vs = mesh.vertices;
            var ns = mesh.normals;
            var us = mesh.uv;
            int b = v.Count;
            var nm = M.inverse.transpose;
            for (int i = 0; i < vs.Length; i++)
            {
                Vector3 p = M.MultiplyPoint3x4(vs[i]);
                v.Add(p);
                n.Add(ns.Length > i ? nm.MultiplyVector(ns[i]).normalized : Vector3.up);
                uv.Add(us.Length > i ? us[i] : Vector2.zero);
                Grow(p);
            }
            for (int s = 0; s < mesh.subMeshCount && s < materials.Length; s++)
            {
                var list = T(materials[s]);
                foreach (int i in mesh.GetTriangles(s)) list.Add(b + i);
            }
        }

        public bool Empty => v.Count == 0;

        public Mesh Build(string name)
        {
            var mesh = new Mesh { name = name, indexFormat = IndexFormat.UInt32 };
            mesh.SetVertices(v);
            mesh.SetNormals(n);
            mesh.SetUVs(0, uv);
            mesh.subMeshCount = tris.Count;
            for (int i = 0; i < tris.Count; i++) mesh.SetTriangles(tris[i], i, false);
            mesh.RecalculateBounds();
            mesh.RecalculateTangents();
            return mesh;
        }
    }

    /// <summary>Spatial chunks of MeshAcc, emitted as one renderer per chunk (few draw calls for a huge city).</summary>
    public class ChunkSet
    {
        readonly float size;
        readonly Dictionary<long, MeshAcc> chunks = new Dictionary<long, MeshAcc>();
        readonly List<long> order = new List<long>();

        public ChunkSet(float size) { this.size = size; }

        public MeshAcc At(Vector3 p)
        {
            long k = ((long)Mathf.FloorToInt(p.x / size) << 32) ^ (uint)Mathf.FloorToInt(p.z / size);
            if (!chunks.TryGetValue(k, out var acc))
            {
                acc = new MeshAcc();
                chunks[k] = acc;
                order.Add(k);
            }
            return acc;
        }

        public int Triangles
        {
            get
            {
                int t = 0;
                foreach (var c in chunks.Values) foreach (var l in c.tris) t += l.Count / 3;
                return t;
            }
        }

        /// <summary>One GameObject per chunk. cull > 0 adds a LODGroup that hides the chunk below that screen height.</summary>
        public List<GameObject> Emit(Transform parent, string name, bool shadows, float cull, bool collider, int layer = 0)
        {
            var list = new List<GameObject>();
            int i = 0;
            foreach (var k in order)
            {
                var acc = chunks[k];
                if (acc.Empty) continue;
                var go = new GameObject($"{name} {i++}");
                go.layer = layer;
                go.transform.SetParent(parent, false);
                var mesh = acc.Build(go.name);
                go.AddComponent<MeshFilter>().sharedMesh = mesh;
                var mr = go.AddComponent<MeshRenderer>();
                mr.sharedMaterials = acc.mats.ToArray();
                mr.shadowCastingMode = shadows ? ShadowCastingMode.On : ShadowCastingMode.Off;
                if (collider) go.AddComponent<MeshCollider>().sharedMesh = mesh;
                if (cull > 0f)
                {
                    var lg = go.AddComponent<LODGroup>();
                    lg.SetLODs(new[] { new LOD(cull, new Renderer[] { mr }) });
                    lg.RecalculateBounds();
                }
                go.isStatic = true;
                list.Add(go);
            }
            return list;
        }
    }
}
