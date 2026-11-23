using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// The troop bay and drone rack of a transport (Carrier APC, Bastion MRAP, Mule truck). Soldiers booked for a ride
    /// walk to the rear door and climb in while the vehicle is stopped (they leave the battlefield until dismounted);
    /// the transport's AI (GroundAI) drives them to where its side knows the enemy is and unloads them one by one out of
    /// the back with an assault order. The rack holds a limited supply of repair drones, launched from the roof hatch
    /// toward damaged armour and mechs. If the vehicle is destroyed with troops aboard, they bail out of the burning
    /// hull and some of them don't make it.
    /// </summary>
    public class TransportBay : MonoBehaviour
    {
        public int capacity = 8;
        public readonly List<SoldierAI> aboard = new List<SoldierAI>();
        public readonly List<SoldierAI> booked = new List<SoldierAI>();
        public readonly List<string> drones = new List<string>();

        Vehicle v;
        Health h;
        bool unloading;
        float unloadT, launchCd, doorT;
        int unloadIndex;
        Vector3 assault;

        /// <summary>Battle totals (auto-test log).</summary>
        public static int Boarded, Dropped, BailedOut, BailDeaths, DronesLaunched, Trips;

        public static void ResetStats() => Boarded = Dropped = BailedOut = BailDeaths = DronesLaunched = Trips = 0;

        public Vehicle Vehicle => v;
        public Health Health => h;
        public bool Unloading => unloading;
        public int Free => capacity - aboard.Count - booked.Count;
        public bool Stopped => v != null && Mathf.Abs(v.ForwardSpeed) < 1.3f;
        public bool CanLaunch => drones.Count > 0 && launchCd <= 0f && v != null && !v.Destroyed;

        public void Init(Vehicle vehicle, Health health, int cap, IEnumerable<string> droneKeys)
        {
            v = vehicle;
            h = health;
            capacity = cap;
            drones.Clear();
            drones.AddRange(droneKeys);
            launchCd = Random.Range(4f, 9f);
            h.Died += OnDied;
        }

        /// <summary>Where riders climb in and out: on the ground just behind the rear door.</summary>
        public Vector3 BoardPoint
        {
            get
            {
                var b = v.localBounds;
                var p = transform.TransformPoint(new Vector3(b.center.x, 0f, b.min.z - 1.7f));
                p.y = WorldGround.Height(p.x, p.z);
                return p;
            }
        }

        public void Book(SoldierAI s)
        {
            if (s != null && !booked.Contains(s)) booked.Add(s);
        }

        public void Unbook(SoldierAI s) => booked.Remove(s);

        /// <summary>A rider at the door: in he goes (if there's a seat and the vehicle has stopped).</summary>
        public bool TryBoard(SoldierAI s)
        {
            if (v == null || v.Destroyed || unloading || aboard.Count >= capacity || !Stopped) return false;
            booked.Remove(s);
            aboard.Add(s);
            Boarded++;
            s.gameObject.SetActive(false);
            return true;
        }

        public void SetDoor(bool open)
        {
            if (v) v.SetDoor(open);
            if (open) doorT = 2.5f;
        }

        /// <summary>Everybody out, heading for 'target' (where the enemy is).</summary>
        public void Unload(Vector3 target)
        {
            if (aboard.Count == 0) return;
            unloading = true;
            assault = target;
            unloadT = 0.9f;
            unloadIndex = 0;
            Trips++;
            SetDoor(true);
        }

        void Update()
        {
            float dt = Time.deltaTime;
            launchCd -= dt;
            booked.RemoveAll(s => s == null);
            if (doorT > 0f)
            {
                doorT -= dt;
                if (doorT <= 0f && !unloading && booked.Count == 0 && v) v.SetDoor(false);
            }
            if (!unloading) return;
            unloadT -= dt;
            if (unloadT > 0f) return;
            aboard.RemoveAll(s => s == null);
            if (aboard.Count == 0)
            {
                unloading = false;
                doorT = 1.5f;
                return;
            }
            unloadT = 0.35f;
            var s0 = aboard[aboard.Count - 1];
            aboard.RemoveAt(aboard.Count - 1);
            Dismount(s0, assault, unloadIndex++);
            Dropped++;
        }

        void Dismount(SoldierAI s, Vector3 target, int i)
        {
            Vector3 p = BoardPoint + transform.right * ((i % 3) - 1) * 1.1f - transform.forward * (i / 3) * 0.9f;
            if (CityNav.Active && CityNav.Clearance(new Vector2(p.x, p.z)) < 0.5f)
            {
                var q = CityNav.NearestFree(new Vector2(p.x, p.z), 0.5f, false, 12f);
                p = new Vector3(q.x, p.y, q.y);
            }
            p.y = WorldGround.Height(p.x, p.z) + 0.05f;
            Vector3 face = AIUtil.Flat((target == Vector3.zero ? p - transform.position : target - p));
            s.transform.SetPositionAndRotation(p, face.sqrMagnitude > 0.01f ? Quaternion.LookRotation(face) : transform.rotation);
            s.gameObject.SetActive(true);
            s.Dismounted(target);
        }

        /// <summary>Roof hatch launch of one drone, sent to 'patient'. The Mender goes to the biggest jobs.</summary>
        public Health LaunchDrone(Health patient)
        {
            var war = WarManager.Instance;
            if (!CanLaunch || war == null || h == null) return null;
            string key = drones[0];
            bool bigJob = patient && (patient.cls == UnitClass.Mech || patient.maxHp - patient.hp > 1500f);
            if (bigJob && drones.Contains("Drone_Mender")) key = "Drone_Mender";
            else if (!bigJob)
                foreach (var k in drones) if (k != "Drone_Mender") { key = k; break; }
            var b = v.localBounds;
            Vector3 p = transform.TransformPoint(new Vector3(b.center.x, b.max.y + 0.6f, b.center.z - b.extents.z * 0.4f));
            var dh = war.SpawnDrone(key, p, transform.eulerAngles.y, h.team);
            if (dh == null || dh.Drone == null) return null;
            drones.Remove(key);
            dh.Drone.Launch(p, v.Velocity, patient);
            launchCd = 7f;
            DronesLaunched++;
            return dh;
        }

        void OnDied(DamageInfo d)
        {
            // riders bail out of the burning hull; the blast gets some of them
            int i = 0;
            foreach (var s in aboard)
            {
                if (s == null) continue;
                Dismount(s, Vector3.zero, i++);
                BailedOut++;
                var sh = s.GetComponent<Health>();
                if (sh == null) continue;
                if (Random.value < 0.4f)
                {
                    sh.Kill(new DamageInfo { attacker = d.attacker, point = transform.position, dir = s.transform.position - transform.position });
                    BailDeaths++;
                }
                else
                    sh.TakeDamage(new DamageInfo { amount = sh.maxHp * Random.Range(0.25f, 0.55f), type = DamageType.HE, team = Team.None,
                        point = transform.position, dir = s.transform.position - transform.position, attacker = d.attacker });
            }
            aboard.Clear();
            foreach (var s in booked.ToArray()) if (s) s.CancelRide();
            booked.Clear();
            drones.Clear();
            unloading = false;
        }
    }
}
