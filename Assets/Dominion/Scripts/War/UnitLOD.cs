using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Unit level-of-detail for big battles. A unit is drawn in full only when the player can actually see it: on screen,
    /// within range for its type, and with a clear line of sight from the camera (or simply very close, or the player's own
    /// unit). Everything else stops rendering, which also stops its skeletal animation and skinning, and vehicles skip
    /// their cosmetic rig work (track blend shapes, wheel spin, dust). Gameplay (AI, physics, weapons, damage) is untouched.
    /// Units are re-checked round-robin (the whole army several times a second) and stay full for a moment after leaving
    /// view, so nothing pops while the camera sweeps.
    /// </summary>
    [DefaultExecutionOrder(500)]
    public class UnitLOD : MonoBehaviour
    {
        class Entry
        {
            public Health h;
            public Renderer[] renderers;
            public Vehicle vehicle;
            public DroneUnit drone;
            public float maxDist, lastSeen = -99f;
            public bool full = true;
        }

        public static UnitLOD Instance { get; private set; }
        public static int FullCount, HiddenCount;
        const float Near = 45f, Linger = 1.2f;

        readonly List<Entry> entries = new List<Entry>();
        readonly HashSet<Health> known = new HashSet<Health>();
        readonly Plane[] planes = new Plane[6];
        readonly RaycastHit[] hits = new RaycastHit[8];
        int cursor;
        GameDirector director;

        void Awake()
        {
            Instance = this;
            director = FindFirstObjectByType<GameDirector>();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        void Register(Health h)
        {
            if (!known.Add(h)) return;
            if (h.IsAirship) return;
            var list = new List<Renderer>();
            foreach (var r in h.GetComponentsInChildren<Renderer>(true))
                if (r is MeshRenderer || r is SkinnedMeshRenderer) list.Add(r);
            entries.Add(new Entry
            {
                h = h, renderers = list.ToArray(), vehicle = h.GetComponent<Vehicle>(), drone = h.Drone,
                maxDist = h.cls == UnitClass.Soldier ? 420f : h.IsDrone ? 800f : h.cls == UnitClass.Air ? 3500f : h.cls == UnitClass.Mech ? 2500f : 1500f,
            });
        }

        void LateUpdate()
        {
            long perfT0 = Perf.Now;
            LateUpdateTimed();
            Perf.Add(Perf.Lod, perfT0);
        }

        void LateUpdateTimed()
        {
            var cam = Camera.main;
            if (cam == null) return;
            var all = Health.All;
            if (known.Count < all.Count) foreach (var h in all) if (h) Register(h);
            if (entries.Count == 0) return;
            GeometryUtility.CalculateFrustumPlanes(cam, planes);
            Vector3 eye = cam.transform.position;
            Health mine = director ? director.PlayerUnit : null;
            int budget = Mathf.Min(entries.Count, Mathf.Max(32, entries.Count / 6));
            for (int k = 0; k < budget; k++)
            {
                cursor = (cursor + 1) % entries.Count;
                var e = entries[cursor];
                if (e.h == null) continue;
                bool vis = Visible(e, eye, mine);
                if (vis) e.lastSeen = Time.time;
                bool full = vis || Time.time - e.lastSeen < Linger;
                if (full != e.full) Apply(e, full);
                // simulation LOD for soldiers, ground vehicles and drones that nobody can see
                bool lodable = e.h.cls == UnitClass.Soldier || e.h.cls == UnitClass.Ground || e.h.IsDrone;
                float d = Vector3.Distance(eye, e.h.Center);
                if (e.h.cls == UnitClass.Air && !e.h.IsDrone && !e.h.IsAirship)
                {
                    e.h.SimStride = full || d < 600f ? 1 : 2;
                    continue;
                }
                // seen units run every frame up close; far beyond 220 m a soldier is ~15 px tall and steps at half rate
                e.h.SimStride = !lodable || d < 200f ? 1 : full ? (d < 220f || e.h.cls != UnitClass.Soldier ? 1 : 2) : d < 600f ? 2 : 4;
            }
            int f = 0;
            foreach (var e in entries) if (e.full) f++;
            FullCount = f;
            HiddenCount = entries.Count - f;
        }

        bool Visible(Entry e, Vector3 eye, Health mine)
        {
            if (e.h == mine) return true;
            if (e.vehicle && (e.vehicle.Occupied && e.vehicle.PlayerDriven)) return true;
            Vector3 c = e.h.Center;
            float d = Vector3.Distance(eye, c);
            if (d < Near) return true;
            if (d > e.maxDist) return false;
            float r = Mathf.Max(e.h.Radius, 0.6f);
            if (!GeometryUtility.TestPlanesAABB(planes, new Bounds(c, Vector3.one * (r * 2.4f)))) return false;
            // line of sight from the camera to the unit's middle or top: buildings, terrain and walls block it, units don't
            return Clear(eye, c, d, r) || Clear(eye, c + Vector3.up * r * 0.85f, d, r);
        }

        bool Clear(Vector3 eye, Vector3 p, float d, float r)
        {
            Vector3 dir = p - eye;
            float len = dir.magnitude;
            if (len < 0.01f) return true;
            int n = Physics.RaycastNonAlloc(eye, dir / len, hits, len - r * 0.5f, ~0, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var col = hits[i].collider;
                if (col == null || Health.Of(col) != null) continue;
                return false;
            }
            return true;
        }

        static void Apply(Entry e, bool full)
        {
            e.full = full;
            foreach (var r in e.renderers) if (r) r.forceRenderingOff = !full;
            if (e.vehicle) e.vehicle.LodHidden = !full;
            if (e.drone) e.drone.LodHidden = !full;
        }
    }
}
