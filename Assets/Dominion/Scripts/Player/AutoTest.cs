using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Self-test, only active when the game is started with  -autotest  (optionally  -autotestdir "path").
    /// Walks the soldier in all 8 directions, then enters every vehicle, drives / flies / walks it, fires,
    /// takes screenshots and writes autotest.log, then quits. Normal play never runs this.
    /// </summary>
    public class AutoTest : MonoBehaviour
    {
        GameDirector dir;
        string outDir;
        bool vfxOnly;
        readonly StringBuilder log = new StringBuilder();
        readonly List<float> frameTimes = new List<float>();

        float warTime = 150f;
        int errors;
        string firstError;

        void Start()
        {
            var args = System.Environment.GetCommandLineArgs();
            bool on = false, war = false;
            bool cityShots = false;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "-autotest") on = true;
                if (args[i] == "-vfxonly") { on = true; vfxOnly = true; }
                if (args[i] == "-wartest") war = true;
                if (args[i] == "-citytest") { war = true; cityShots = true; }
                if (args[i] == "-wartime" && i + 1 < args.Length)
                    float.TryParse(args[i + 1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out warTime);
                if (args[i] == "-autotestdir" && i + 1 < args.Length) outDir = args[i + 1];
            }
            bool warScene = FindFirstObjectByType<WarManager>() != null;
            if (warScene) on = war;
            if (!on) { enabled = false; return; }
            if (string.IsNullOrEmpty(outDir)) outDir = Path.Combine(Application.dataPath, "..", "AutoTest");
            Directory.CreateDirectory(outDir);
            dir = FindFirstObjectByType<GameDirector>();
            dir.autopilot = true;
            Application.logMessageReceived += (msg, stack, type) =>
            {
                if (type == LogType.Exception || type == LogType.Error)
                {
                    errors++;
                    if (firstError == null) firstError = msg + "\n" + stack;
                }
            };
            StartCoroutine(warScene ? (cityShots ? CityShots() : WarRun()) : Run());
        }

        // ------------------------------------------------------------------ war test: a whole AI battle, watched and logged
        IEnumerator WarRun()
        {
            var war = WarManager.Instance;
            dir.Spectate();
            int crashes = 0, kills = 0;
            var deathsBy = new Dictionary<string, int>();
            Health.AnyDeath += (v, d) =>
            {
                if (d.attacker == null || d.attacker == v) crashes++; else kills++;
                string k = $"{v.team} {v.cls}";
                deathsBy[k] = deathsBy.TryGetValue(k, out int c) ? c + 1 : 1;
                if (v.cls == UnitClass.Air && blackBox.TryGetValue(v, out var q) && (d.attacker == null || d.attacker == v))
                    foreach (var line in q) Log("      fdr " + line);
                Vector3 p = v.transform.position;
                Log($"  DEATH {v.team} {v.unitName} at ({p.x:0},{p.y:0},{p.z:0})  by {(d.attacker ? d.attacker.team + " " + d.attacker.unitName : "-")}  {d.type} {d.amount:0}");
            };
            foreach (var u in war.Units) if (u.cls == UnitClass.Mech) Log($"mech: {u.team} {u.unitName}");
            var dealt = new Dictionary<Health, float>();
            Health.AnyDamage += (victim, d, dmg) => { if (d.attacker) dealt[d.attacker] = (dealt.TryGetValue(d.attacker, out float x) ? x : 0f) + dmg; };
            void Gunnery(string when)
            {
                foreach (var u in war.Units)
                {
                    var g = u ? u.GetComponent<GroundAI>() : null;
                    if (g == null) continue;
                    dealt.TryGetValue(u, out float dd);
                    var tg = g.Target;
                    Log($"  gun[{when}] {u.team,-4} {u.key,-16} alive {u.Alive,-5} {g.State,-12} shots {g.Shots,4} dealt {dd,6:0}  off {g.LastOff,5:0.0}  pos {u.transform.position}  fwd {u.transform.forward}  " +
                        $"tgt {(tg ? tg.unitName + " " + Vector3.Distance(tg.Center, u.Center).ToString("0") : "-")}");
                }
            }
            Log($"Dominion I WAR test  {Screen.width}x{Screen.height}  {SystemInfo.graphicsDeviceName}   units {war.Units.Count}   cover spots {war.Cover.Count}");
            var cityGen = CityGenerator.Instance;
            if (cityGen) Log($"map: {cityGen.MapName} (seed {cityGen.Seed}), generated in {cityGen.GenerateSeconds:0.00} s: {cityGen.Stats}");
            var b0 = war.Count(Team.Blue);
            var r0 = war.Count(Team.Red);
            Log($"spawned  BLUE inf {b0.soldiers} ground {b0.ground} air {b0.air} mech {b0.mech}   RED inf {r0.soldiers} ground {r0.ground} air {r0.air} mech {r0.mech}");
            var lead = war.Units.Find(h => h.team == Team.Blue && h.cls == UnitClass.Soldier);
            dir.Watch(lead);
            Look(0f, 8f);
            yield return new WaitForSeconds(2f);
            yield return Shot("war_00_countdown");
            SpawnCheck(war);
            while (!war.Fighting) yield return null;
            yield return new WaitForSeconds(1f);
            yield return Shot("war_01_fight");
            yield return PlayerControlTest(war);
            StartCoroutine(FlightRecorder(war));
            float t0 = Time.time, nextLog = 0f, nextCam = 6f;
            int shot = 2;
            UnitClass[] cycle = { UnitClass.Ground, UnitClass.Soldier, UnitClass.Air, UnitClass.Mech, UnitClass.Soldier, UnitClass.Ground };
            int ci = 0;
            frameTimes.Clear();
            while (Time.time - t0 < warTime && !war.Over)
            {
                float t = Time.time - t0;
                if (t >= nextLog)
                {
                    nextLog += 10f;
                    var b = war.Count(Team.Blue);
                    var r = war.Count(Team.Red);
                    foreach (var u in war.Units)
                    {
                        var pa = u && u.Alive ? u.GetComponent<PlaneAI>() : null;
                        if (pa && (pa.State == "Parked" || pa.State == "Takeoff"))
                        {
                            var av = (AircraftVehicle)u.Vehicle;
                            Log($"    {u.team} {u.unitName} {pa.State} speed {av.Airspeed:0} alt {av.Altitude:0.0} grounded {av.Grounded} throttle {av.Throttle:0.00} pos {u.transform.position} yaw {u.transform.eulerAngles.y:0}");
                        }
                    }
                    Log($"t={t,5:0}s  BLUE inf {b.soldiers,2} gnd {b.ground,2} air {b.air,2} mech {b.mech}   RED inf {r.soldiers,2} gnd {r.ground,2} air {r.air,2} mech {r.mech}" +
                        $"   kills {kills} crashes {crashes}   fps {Fps():0}   errors {errors}   paths {CityNav.TotalPaths} (failed {CityNav.FailedPaths}, grid {CityNav.GridSearches}, {CityNav.TotalMs:0} ms)" +
                        $"   front B {war.FrontLine(Team.Blue):0} R {war.FrontLine(Team.Red):0}   {AiSummary()}");
                    Log($"      timing: {Timings()}");
                    Log($"      intel: B {Intel.Known(Team.Blue)} contacts in {Intel.Hots(Team.Blue).Count} hotspots, R {Intel.Known(Team.Red)} in {Intel.Hots(Team.Red).Count}" +
                        $" (reports air {Intel.AirReports} drone {Intel.DroneReports} battle {Intel.BattleReports})" +
                        $" | transports: boarded {TransportBay.Boarded} dropped {TransportBay.Dropped} trips {TransportBay.Trips} bailed {TransportBay.BailedOut} ({TransportBay.BailDeaths} died)" +
                        $" | drones: launched {DroneUnit.Launched} up B {war.DroneCount(Team.Blue)} R {war.DroneCount(Team.Red)} down {DroneUnit.Downed} healed {Health.TotalHealed:0} hp" +
                        $" | mech dashes {MechVehicle.Dashes} | far vehicles on physics proxy {Perf.Proxied} | paratroopers jumped {Paratrooper.Jumped} landed {Paratrooper.Landed}");
                    Log($"      weapons: tank roof MG rounds {TrackedVehicle.MgRounds}, Wraith AAMs fired {AircraftVehicle.AamFired}, Sabers dropped tanks {AircraftVehicle.TanksDropped}" +
                        $" | projectile models drawn last frame {Projectiles.Drawn}, casings {Projectiles.CasingCount}" +
                        $" | airship gun hits {Tracers.FalloffHits}, mean damage {(Tracers.FalloffHits > 0 ? Tracers.FalloffSum / Tracers.FalloffHits * 100f : 0f):0}%," +
                        $" lowest {Tracers.FalloffLowest * 100f:0}% (longest flight {Tracers.FalloffFarthest:0} m)");
                    foreach (var a in Airship.All)
                        Log($"      ship {a.team} {a.displayName}: hp {(a.health ? a.health.Fraction * 100f : 0f):0}% {a.State} keel {a.AltitudeAboveGround:0} m over ground, " +
                            $"speed {a.Velocity.magnitude:0.0} m/s, goal {Vector3.Distance(AIUtil.Flat(a.transform.position), a.Goal):0} m away, shots {a.ShotsFired}, crew {a.CrewCount}");
                    frameTimes.Clear();
                }
                if (t >= 40f && t - Time.deltaTime < 40f) Gunnery("40s");
                if (!projShots && t >= 30f)
                {
                    projShots = true;
                    yield return ProjectileShots();
                }
                if (!paraShot && t >= 22f)
                {
                    paraShot = true;
                    yield return ParaShot();
                }
                if (!shipShots && t >= 14f)
                {
                    shipShots = true;
                    foreach (var a in Airship.All.ToArray())
                        if (a && a.team == Team.Blue)
                        {
                            yield return ShipShot(a, $"ship_{a.displayName.Replace(' ', '_')}", false);
                            yield return ShipShot(a, $"ship_{a.displayName.Replace(' ', '_')}_deck", true);
                            if (!a.flagship) yield return GunnerShot(a);
                        }
                }
                if (t >= nextCam && specialN++ % 2 == 1 && Special(out Health sub, out string stag, out Vector3 sLook))
                {
                    // drones at work (the camera rides the patient, looking at the drone) and transports loading / unloading
                    nextCam += 9f;
                    dir.Watch(sub);
                    Look(AIUtil.YawTo(sub.transform.position, sLook), 6f);
                    DroneUnit drone = null;
                    foreach (var h in Health.All)
                        if (h.Alive && h.IsDrone && h.Drone.Patient == sub && h.Drone.State == DroneUnit.Mode.Repair) { drone = h.Drone; break; }
                    if (drone && CameraRig.Main && Camera.main)
                    {
                        // close-up from the side: drone, beam and patient in one frame
                        var camT = Camera.main.transform;
                        CameraRig.Main.enabled = false;
                        for (float k = 0f; k < 1.5f && drone && sub; k += Time.deltaTime)
                        {
                            Vector3 dp = drone.transform.position, pc = sub.Center;
                            Vector3 along = AIUtil.Flat(pc - dp);
                            along = along.sqrMagnitude > 0.1f ? along.normalized : Vector3.forward;
                            Vector3 mid = Vector3.Lerp(dp, pc, 0.45f);
                            camT.position = mid + Vector3.Cross(Vector3.up, along) * (7f + sub.Radius * 2f) + Vector3.up * 1.5f - along * 2f;
                            camT.LookAt(mid);
                            yield return null;
                        }
                        if (sub) yield return Shot($"war_{shot++:00}_{stag}");
                        CameraRig.Main.enabled = true;
                    }
                    else
                    {
                        yield return new WaitForSeconds(2.5f);
                        if (sub) yield return Shot($"war_{shot++:00}_{stag}");
                    }
                }
                else if (t >= nextCam)
                {
                    nextCam += 9f;
                    var cls = cycle[ci++ % cycle.Length];
                    var pick = Pick(war, cls);
                    if (pick)
                    {
                        dir.Watch(pick);
                        Look(pick.transform.eulerAngles.y + 25f, cls == UnitClass.Soldier ? 8f : 14f);
                        yield return new WaitForSeconds(2.5f);
                        if (pick) yield return Shot($"war_{shot++:00}_{cls}_{pick.unitName.Replace(' ', '_')}");
                    }
                }
                yield return null;
            }
            Gunnery("end");
            var bf = war.Count(Team.Blue);
            var rf = war.Count(Team.Red);
            Log($"END t={Time.time - t0:0}s  over={war.Over} winner={war.Winner}   BLUE inf {bf.soldiers} gnd {bf.ground} air {bf.air} mech {bf.mech}   " +
                $"RED inf {rf.soldiers} gnd {rf.ground} air {rf.air} mech {rf.mech}");
            var sb = new StringBuilder("losses:");
            foreach (var kv in deathsBy) sb.Append($"  {kv.Key} {kv.Value}");
            Log(sb.ToString());
            Log($"kills {kills}, crashes / self-inflicted {crashes}, median fps {Fps():0}, errors {errors}" + (firstError != null ? "\nFIRST ERROR: " + firstError : ""));
            if (war.Over)
            {
                yield return new WaitForSeconds(1f);
                yield return Shot("war_99_victory");
            }
            Log("AUTOTEST DONE");
            yield return new WaitForSeconds(0.5f);
            Application.Quit();
        }

        /// <summary>-citytest: photograph the generated map (air, hills, downtown streets, suburbs, staging park, airfield), then quit.</summary>
        IEnumerator CityShots()
        {
            var city = CityGenerator.Instance;
            var war = WarManager.Instance;
            dir.Spectate();
            yield return null;
            Log($"Dominion I CITY test  {Screen.width}x{Screen.height}  {SystemInfo.graphicsDeviceName}");
            if (city == null) { Log("no city"); Application.Quit(); yield break; }
            Log($"map: {city.MapName} (seed {city.Seed}), generated in {city.GenerateSeconds:0.00} s: {city.Stats}");
            Log($"units {war.Units.Count}  cover spots {war.Cover.Count}  nav {(CityNav.Active ? "on" : "off")}");
            var cam = Camera.main;
            var rig = cam.GetComponent<CameraRig>();
            if (rig) rig.enabled = false;
            var plan = city.Plan;
            RoadNode NodeAt(float radial, int minDeg)
            {
                RoadNode best = null;
                float bd = float.MaxValue;
                foreach (var n in plan.Nodes)
                {
                    if (n.edges.Count < minDeg) continue;
                    float d = Mathf.Abs(plan.Radial(n.p) - radial) + Mathf.Abs(n.p.y) * 0.0002f;
                    if (d < bd) { bd = d; best = n; }
                }
                return best;
            }
            Vector3 StreetEye(RoadNode n, out Vector3 look)
            {
                var e = plan.Edges[n.edges[0]];
                Vector2 o = plan.Nodes[e.a] == n ? plan.Nodes[e.b].p : plan.Nodes[e.a].p;
                Vector2 d = (o - n.p).normalized;
                Vector2 side = new Vector2(-d.y, d.x) * (e.halfWidth * 0.5f);
                look = new Vector3(o.x, 6f, o.y);
                return new Vector3(n.p.x + side.x - d.x * 4f, 1.9f, n.p.y + side.y - d.y * 4f);
            }
            var shots = new List<(string name, Vector3 pos, Vector3 look)>
            {
                ("city_01_overview", new Vector3(0f, 1500f, -3300f), new Vector3(0f, 0f, -200f)),
                ("city_02_downtown_air", new Vector3(520f, 300f, -620f), new Vector3(0f, 60f, 0f)),
                ("city_03_hills", new Vector3(-2900f, 380f, -2300f), new Vector3(-600f, 0f, 0f)),
                ("city_04_topdown", new Vector3(0f, 2600f, -1f), Vector3.zero),
            };
            var dn = NodeAt(0.05f, 3);
            if (dn != null) { var e = StreetEye(dn, out var l); shots.Add(("city_05_downtown_street", e, l)); }
            var mn = NodeAt(0.32f, 3);
            if (mn != null) { var e = StreetEye(mn, out var l); shots.Add(("city_06_midtown_street", e, l)); }
            var rn = NodeAt(0.6f, 3);
            if (rn != null) { var e = StreetEye(rn, out var l); shots.Add(("city_07_residential_street", e, l)); }
            var sn = NodeAt(0.85f, 2);
            if (sn != null) { var e = StreetEye(sn, out var l); shots.Add(("city_08_suburb_street", e, l)); }
            if (dn != null) shots.Add(("city_09_downtown_block", new Vector3(dn.p.x + 90f, 70f, dn.p.y - 120f), new Vector3(dn.p.x, 10f, dn.p.y)));
            var st = plan.StagingS;
            shots.Add(("city_10_staging", new Vector3(st.center.x + 120f, 45f, st.yMin - 90f), new Vector3(st.center.x, 0f, st.center.y + 60f)));
            float ah = city.AirfieldHeight(false);
            shots.Add(("city_11_airfield", new Vector3(plan.AirS.x + 260f, ah + 90f, plan.AirS.y - 600f), new Vector3(plan.AirS.x, ah, plan.AirS.y)));
            if (plan.Highways.Count > 0)
            {
                var hw = plan.Highways[0];
                Vector2 a = hw[hw.Count / 2], b = hw[Mathf.Min(hw.Count - 1, hw.Count / 2 + 4)];
                float hy = WorldGround.Height(a.x, a.y);
                shots.Add(("city_12_highway", new Vector3(a.x, hy + 25f, a.y) - new Vector3(b.x - a.x, 0f, b.y - a.y).normalized * 60f,
                    new Vector3(b.x, WorldGround.Height(b.x, b.y), b.y)));
            }
            foreach (var (name, pos, look) in shots)
            {
                cam.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(look - pos));
                frameTimes.Clear();
                yield return new WaitForSeconds(2.5f);
                Log($"{name}: fps {Fps():0}  at {pos}");
                yield return Shot(name);
                yield return new WaitForSeconds(0.3f);
            }
            Log($"errors {errors}" + (firstError != null ? "\nFIRST ERROR: " + firstError : ""));
            Log("AUTOTEST DONE");
            yield return new WaitForSeconds(0.5f);
            Application.Quit();
        }

        /// <summary>The player's side of War mode: take command of a tank (its AI stands down), of a soldier, then die and respawn.</summary>
        IEnumerator PlayerControlTest(WarManager war)
        {
            var tankH = war.Units.Find(h => h.team == Team.Blue && h.Alive && h.key == "Tank_Medium");
            var soldiers = war.Units.FindAll(h => h.team == Team.Blue && h.Alive && h.cls == UnitClass.Soldier);
            if (tankH == null || soldiers.Count < 3) { Log("player test skipped"); yield break; }
            dir.spectate = false;
            dir.TakeCommand(tankH);
            yield return new WaitForSeconds(1f);
            var gai = tankH.GetComponent<GroundAI>();
            bool tankOk = dir.Current == tankH.Vehicle && tankH.Vehicle.PlayerDriven && tankH.Vehicle.Occupied;
            Log($"player test: T on {tankH.unitName}: controlling={tankOk} (AI stood down={tankH.Vehicle.PlayerDriven})");
            dir.TakeCommand(soldiers[1]);
            yield return new WaitForSeconds(0.5f);
            bool soldierOk = dir.Soldier == soldiers[1].Soldier && dir.Current == null && soldiers[1].Soldier.Controlled && !tankH.Vehicle.PlayerDriven;
            Log($"player test: T on a soldier: controlling={soldierOk}, tank back under AI={!tankH.Vehicle.PlayerDriven}");
            soldiers[1].Kill(new DamageInfo());
            yield return new WaitForSeconds(4.5f);
            var now = dir.Soldier;
            bool respawned = now != null && now != soldiers[1].Soldier && !now.Dead && now.Controlled;
            Log($"player test: killed -> respawned into another soldier={respawned} ({(now ? now.displayName : "none")})");
            // deploy onto an escort's open deck, ride it, then work one of its guns
            Airship deckShip = null;
            foreach (var a in Airship.All) if (a && a.team == Team.Blue && !a.flagship) { deckShip = a; break; }
            if (deckShip)
            {
                bool ok = dir.DeployShip(deckShip);
                Vector3 start = deckShip.transform.position;
                yield return new WaitForSeconds(6f);
                var me = dir.Soldier;
                bool aboard = me && Airship.Carry(me.transform.position, out _, out _);
                Log($"deploy test: {deckShip.displayName} deck spawn={ok}, still aboard after 6 s={aboard}, ship moved {Vector3.Distance(start, deckShip.transform.position):0.0} m, " +
                    $"gunner at {(me ? deckShip.transform.InverseTransformPoint(me.transform.position).ToString("F1") : "-")} (ship space)");
                int shots0 = deckShip.ShotsFired;
                deckShip.Man(0, true);
                for (float k = 0f; k < 2f; k += Time.deltaTime)
                {
                    deckShip.PlayerGun(0, deckShip.TurretPosition(0) + deckShip.transform.forward * 400f - Vector3.up * 60f, true);
                    yield return null;
                }
                deckShip.Man(0, false);
                Log($"deploy test: manned deck gun fired {deckShip.ShotsFired - shots0} rounds in 2 s");
                int seated = 0;
                foreach (var tu in deckShip.turrets) if (tu.deck && tu.seated) seated++;
                Log($"gunner test: {deckShip.displayName} deck guns with a seated gunner: {seated} of {deckShip.turrets.Count}");
                int crew0 = deckShip.CrewCount;
                int jumpers = deckShip.OrderDrop(4, deckShip.transform.position + deckShip.transform.forward * 60f);
                yield return new WaitForSeconds(3.5f);
                Log($"paradrop test: {deckShip.displayName} sent {jumpers} of its crew out (crew {crew0} -> {deckShip.CrewCount}, {deckShip.Jumpers} more could go)");
            }
            dir.Spectate();
        }

        readonly Dictionary<Health, Queue<string>> blackBox = new Dictionary<Health, Queue<string>>();

        IEnumerator FlightRecorder(WarManager war)
        {
            while (true)
            {
                foreach (var u in war.Units)
                {
                    if (!u || !u.Alive || u.cls != UnitClass.Air || u.IsDrone || u.IsAirship) continue;
                    var av = (AircraftVehicle)u.Vehicle;
                    var ai = u.GetComponent<PlaneAI>();
                    Transform t = u.transform;
                    float pitch = Mathf.Asin(Mathf.Clamp(t.forward.y, -1f, 1f)) * Mathf.Rad2Deg;
                    float bank = Mathf.Atan2(-t.right.y, t.up.y) * Mathf.Rad2Deg;
                    var tg = ai ? ai.Target : null;
                    string line = $"{Time.time:0.00} {ai?.State} alt {av.Altitude:0} spd {av.Airspeed:0} vy {av.Body.linearVelocity.y:0} pitch {pitch:0} bank {bank:0} " +
                                  $"aoa {av.AoA * Mathf.Rad2Deg:0.0} thr {av.Throttle:0.0} in({av.input.move.x:0.00},{av.input.move.y:0.00},{av.input.yaw:0.00}) " +
                                  $"pos ({t.position.x:0},{t.position.z:0}) tgt {(tg ? tg.unitName + " d" + Vector3.Distance(tg.Center, t.position).ToString("0") + " alt" + tg.Center.y.ToString("0") : "-")}";
                    if (!blackBox.TryGetValue(u, out var q)) blackBox[u] = q = new Queue<string>();
                    q.Enqueue(line);
                    while (q.Count > 24) q.Dequeue();
                }
                yield return new WaitForSeconds(0.25f);
            }
        }

        float Fps()
        {
            if (frameTimes.Count == 0) return 0f;
            var copy = new List<float>(frameTimes);
            copy.Sort();
            return 1f / Mathf.Max(copy[copy.Count / 2], 1e-4f);
        }

        int specialN;
        bool shipShots, paraShot, projShots;

        /// <summary>Soldiers and transports on the staging fields, tanks scattered through the city; doubled tank armour; Wraith missiles.</summary>
        void SpawnCheck(WarManager war)
        {
            var plan = CityGenerator.Instance ? CityGenerator.Instance.Plan : null;
            if (plan == null) return;
            int sIn = 0, sAll = 0, trIn = 0, trAll = 0, tkIn = 0, tkAll = 0;
            foreach (var u in war.Units)
            {
                if (!u) continue;
                bool inField = plan.InStaging(new Vector2(u.transform.position.x, u.transform.position.z), 30f);
                if (u.cls == UnitClass.Soldier) { sAll++; if (inField) sIn++; }
                else if (u.key != null && u.key.StartsWith("Tank_")) { tkAll++; if (inField) tkIn++; }
                else if (u.key == "Vehicle_Carrier" || u.key == "Vehicle_Bastion") { trAll++; if (inField) trIn++; }
            }
            var hp = new StringBuilder();
            foreach (var k in new[] { "Tank_Scout", "Tank_Medium", "Tank_Heavy", "Tank_Artillery", "Tank_AntiAir", "Vehicle_Carrier", "Mech_Aegis", "Mech_Halberd", "Mech_Thunderhead" })
            {
                var h = war.Units.Find(x => x && x.key == k);
                if (h) hp.Append($" {k} {h.maxHp:0}");
            }
            var w = war.Units.Find(x => x && x.key == "Aircraft_Wraith");
            Log($"spawn check: soldiers on the staging fields {sIn}/{sAll}, transports {trIn}/{trAll}, tanks {tkIn}/{tkAll} (the rest scattered) | hp{hp}" +
                $" | Wraith AAMs loaded {(w ? ((AircraftVehicle)w.Vehicle).MissilesLeft : -1)}");
        }

        /// <summary>
        /// Staged slow-motion close-ups beside the blue staging field: the big rounds just out of their muzzles, rifle and MG
        /// rounds with their brass, a burst's casings in the air, and the rockets / missiles on their motors.
        /// </summary>
        IEnumerator ProjectileShots()
        {
            var camT = Camera.main ? Camera.main.transform : null;
            var city = CityGenerator.Instance;
            if (camT == null || CameraRig.Main == null || city == null || city.Plan == null) yield break;
            CameraRig.Main.enabled = false;
            Vector2 c2 = city.Plan.StagingS.center;
            Vector3 g = new Vector3(c2.x, WorldGround.Height(c2.x, c2.y), c2.y);
            float oldScale = Time.timeScale;

            // 1) shells, slug and autocannon round (in-game tracer sizes), noses lined up just right of centre
            camT.SetPositionAndRotation(g + new Vector3(0.6f, 3.2f, -7.5f), Quaternion.LookRotation(new Vector3(-0.06f, -0.02f, 1f)));
            var big = new (ProjectileModel m, float v, float w, float len, float mz, float h)[]
            {
                (ProjectileModel.TankShell, 1100f, 0.25f, 15f, 1.1f, 1.0f), (ProjectileModel.Artillery, 600f, 0.25f, 4.5f, 1.3f, 2.1f),
                (ProjectileModel.ShipShell, 800f, 0.22f, 6f, 1.2f, 3.2f), (ProjectileModel.Rail, 1600f, 0.18f, 9f, 0.6f, 4.2f),
                (ProjectileModel.Autocannon, 900f, 0.09f, 5.4f, 0.4f, 5.1f),
            };
            const float tg = 0.0045f;
            Time.timeScale = 0.01f;
            foreach (var b in big)
            {
                Vector3 o = g + new Vector3(1.6f - Projectiles.LengthOf(b.m) - b.len - b.v * tg, b.h, 0f);
                var s = Dominion.Shot.Visual(b.v, b.w, b.len, 0f, ImpactKind.None, 0.5f);
                s.model = b.m;
                s.gravity = 0f;
                Tracers.Fire(o, Vector3.right, s);
                Vfx.Muzzle(o, Vector3.right, b.mz);
            }
            float until = Time.time + tg;
            while (Time.time < until) yield return null;
            Time.timeScale = 0f;
            yield return Shot("proj_01_shells");
            yield return ClearAir();

            // 2) a rifle and an MG round a metre out of the muzzle, brass leaving the breech
            camT.SetPositionAndRotation(g + new Vector3(-0.3f, 1.8f, -1.6f), Quaternion.LookRotation(new Vector3(-0.1f, -0.15f, 1f)));
            Time.timeScale = 0.01f;
            for (int i = 0; i < 2; i++)
            {
                bool mg = i == 1;
                Vector3 o = g + new Vector3((mg ? -1.0f : -0.8f) - 2.5f, mg ? 1.25f : 1.6f, 0.3f);
                var s = Dominion.Shot.Visual(mg ? 850f : 700f, mg ? 0.035f : 0.03f, 2.5f, 0f, ImpactKind.None, 0.35f);
                s.model = mg ? ProjectileModel.MG : ProjectileModel.Rifle;
                s.gravity = 0f;
                Tracers.Fire(o, Vector3.right, s);
                Vfx.Muzzle(o, Vector3.right, mg ? 0.07f : 0.06f);
            }
            until = Time.time + 0.0013f;
            while (Time.time < until) yield return null;
            Time.timeScale = 0f;
            yield return Shot("proj_02_small_arms");
            yield return ClearAir();

            // 3) an MG burst (time-compressed), its casings spinning out to the right and bouncing
            camT.SetPositionAndRotation(g + new Vector3(-1.2f, 1.6f, -2.4f), Quaternion.LookRotation(new Vector3(0.05f, -0.3f, 1f)));
            Time.timeScale = 0.08f;
            float burst0 = Time.time;
            for (int i = 0; i < 8; i++)
            {
                Vector3 o = g + new Vector3(-0.8f, 1.3f, 0.3f);
                var s = Dominion.Shot.Visual(850f, 0.035f, 2.5f, 0f, ImpactKind.None, 0.35f);
                s.model = ProjectileModel.MG;
                s.gravity = 0f;
                Tracers.Fire(o, Vector3.right, s);
                Vfx.Muzzle(o, Vector3.right, 0.07f);
                until = burst0 + 0.045f * (i + 1);
                while (Time.time < until) yield return null;
            }
            Time.timeScale = 0f;
            yield return Shot("proj_03_brass");
            yield return ClearAir();

            // 4) a rifle grenade, a rocket pod round and an air-to-air missile just off the rail, motors burning
            camT.SetPositionAndRotation(g + new Vector3(0.5f, 3.6f, -8.5f), Quaternion.LookRotation(new Vector3(-0.05f, -0.04f, 1f)));
            Time.timeScale = 0.02f;
            var noBlast = new WeaponStats(0f, DamageType.HE);
            Missile.Launch(g + new Vector3(-3.2f, 1.2f, 0f), new Vector3(1f, 0.05f, 0f), g + new Vector3(3000f, 300f, 0f), null, noBlast, null, null, 0.5f);
            Missile.Launch(g + new Vector3(-3.8f, 2.8f, 0f), new Vector3(1f, 0.05f, 0f), g + new Vector3(3000f, 300f, 0f), null, noBlast, null, null, 1f);
            Missile.Launch(g + new Vector3(-4.0f, 4.6f, 0f), new Vector3(1f, 0.05f, 0f), g + new Vector3(3000f, 600f, 0f), null,
                new WeaponStats(480f, DamageType.AP), null, null, 1f);
            until = Time.time + 0.07f;
            while (Time.time < until) yield return null;
            Time.timeScale = 0f;
            yield return Shot("proj_04_missiles");

            Time.timeScale = oldScale;
            CameraRig.Main.enabled = true;

            // full speed for a few seconds: the last shot's smoke clears and its rounds fly off before the next one
            IEnumerator ClearAir()
            {
                Time.timeScale = 1f;
                yield return new WaitForSeconds(3.5f);
            }
        }

        /// <summary>Close-up from beside a descending paratrooper (canopy, lines and jumper in frame).</summary>
        IEnumerator ParaShot()
        {
            Paratrooper pt = null;
            foreach (var p in FindObjectsByType<Paratrooper>(FindObjectsSortMode.None)) if (p.Descending) { pt = p; break; }
            var camT = Camera.main ? Camera.main.transform : null;
            if (pt == null || camT == null || CameraRig.Main == null) yield break;
            CameraRig.Main.enabled = false;
            for (float k = 0f; k < 0.6f && pt; k += Time.deltaTime)
            {
                Vector3 c = pt.transform.position + Vector3.up * 4f;
                camT.position = c + new Vector3(9f, -2f, -9f);
                camT.LookAt(c);
                yield return null;
            }
            if (pt) yield return Shot("para_descent");
            CameraRig.Main.enabled = true;
        }

        /// <summary>A Sentinel deck gun and its seated gunner, from just behind the mount.</summary>
        IEnumerator GunnerShot(Airship a)
        {
            var camT = Camera.main ? Camera.main.transform : null;
            if (a == null || camT == null || CameraRig.Main == null) yield break;
            Airship.Turret tu = null;
            foreach (var x in a.turrets) if (x.deck && x.seated) { tu = x; break; }
            if (tu == null) yield break;
            CameraRig.Main.enabled = false;
            for (float k = 0f; k < 0.6f && a; k += Time.deltaTime)
            {
                Vector3 g = tu.yawBone.position;
                Vector3 inboard = (a.transform.position - g);
                inboard.y = 0f;
                camT.position = g + inboard.normalized * 4.5f + a.transform.up * 2.2f + a.transform.forward * 2f;
                camT.LookAt(g + Vector3.down * 0.4f);
                yield return null;
            }
            yield return Shot($"ship_{a.displayName.Replace(' ', '_')}_gunner");
            CameraRig.Main.enabled = true;
        }

        /// <summary>An airship from off its beam, or from its own deck (crew in view).</summary>
        IEnumerator ShipShot(Airship a, string tag, bool deck)
        {
            var camT = Camera.main ? Camera.main.transform : null;
            if (a == null || camT == null || CameraRig.Main == null) yield break;
            CameraRig.Main.enabled = false;
            for (float k = 0f; k < 0.8f && a; k += Time.deltaTime)
            {
                Transform st = a.transform;
                if (deck)
                {
                    var db = a.deckBounds;
                    camT.position = st.TransformPoint(new Vector3(0f, a.flagship ? db.min.y + 1.7f : db.max.y - 2.6f, db.min.z + (a.flagship ? db.size.z * 0.3f : 4f)));
                    camT.rotation = Quaternion.LookRotation(st.forward - st.up * 0.08f, st.up);
                }
                else
                {
                    Vector3 c = st.TransformPoint(a.hullBounds.center);
                    camT.position = c + st.right * a.hullBounds.size.z * 0.9f + Vector3.up * 30f - st.forward * a.hullBounds.size.z * 0.35f;
                    camT.LookAt(c);
                }
                yield return null;
            }
            if (a) yield return Shot(tag);
            CameraRig.Main.enabled = true;
        }

        /// <summary>A repair drone at work (subject = its patient), else a transport loading or unloading troops.</summary>
        static bool Special(out Health subject, out string tag, out Vector3 lookAt)
        {
            subject = null;
            tag = null;
            lookAt = default;
            foreach (var h in Health.All)
            {
                if (!h.Alive || !h.IsDrone || h.Drone.State != DroneUnit.Mode.Repair || h.Drone.Patient == null) continue;
                var pt = h.Drone.Patient;
                if (pt.Vehicle == null && pt.Soldier == null) continue;
                subject = pt;
                lookAt = h.transform.position;
                tag = $"Repair_{h.unitName.Replace(' ', '_')}_on_{pt.unitName.Replace(' ', '_')}";
                return true;
            }
            foreach (var a in FindObjectsByType<GroundAI>(FindObjectsSortMode.None))
            {
                if (a.State != "loading" && a.State != "unloading") continue;
                var h = a.GetComponent<Health>();
                if (h == null || !h.Alive) continue;
                subject = h;
                lookAt = h.transform.position - h.transform.forward * 10f;
                tag = $"Transport_{a.State}_{h.unitName.Replace(' ', '_')}";
                return true;
            }
            return false;
        }

        static Health Pick(WarManager war, UnitClass cls)
        {
            Health best = null;
            float bestScore = float.MaxValue;
            foreach (var h in war.Units)
            {
                if (!h || !h.Alive || h.cls != cls || !h.gameObject.activeInHierarchy || h.IsDrone || h.IsAirship) continue;
                if (cls == UnitClass.Air && !h.Airborne) continue;
                // closest to the middle of the battlefield = most likely in a fight
                float score = Mathf.Abs(h.transform.position.z) + Random.value * 60f;
                if (score < bestScore) { bestScore = score; best = h; }
            }
            return best;
        }

        static string AiSummary()
        {
            var counts = new Dictionary<string, int>();
            void Add(string k) => counts[k] = counts.TryGetValue(k, out int c) ? c + 1 : 1;
            foreach (var a in FindObjectsByType<SoldierAI>(FindObjectsSortMode.None))
            {
                var sc = a.GetComponent<SoldierController>();
                if (a.isActiveAndEnabled && sc && !sc.Dead) Add("s:" + a.State);
            }
            foreach (var a in FindObjectsByType<PlaneAI>(FindObjectsSortMode.None))
            {
                var v = a.GetComponent<Vehicle>();
                if (v && !v.Destroyed) Add("p:" + a.State);
            }
            foreach (var a in FindObjectsByType<GroundAI>(FindObjectsSortMode.None))
            {
                var v = a.GetComponent<Vehicle>();
                if (v && !v.Destroyed) Add("g:" + a.State);
            }
            foreach (var d in FindObjectsByType<DroneUnit>(FindObjectsSortMode.None))
                if (d.State != DroneUnit.Mode.Down) Add("d:" + d.State);
            foreach (var a in FindObjectsByType<MechAI>(FindObjectsSortMode.None))
            {
                var v = a.GetComponent<Vehicle>();
                if (v && !v.Destroyed) Add("m:" + a.State);
            }
            int stucks = 0, nG = 0;
            float odo = 0f;
            foreach (var a in FindObjectsByType<GroundAI>(FindObjectsSortMode.None)) { stucks += a.Stucks; odo += a.Odo; nG++; }
            var sb = new StringBuilder($"vehicles: stuck {stucks} avg driven {(nG > 0 ? odo / nG : 0f):0} m, cars crushed {CarProp.CrushedCount} | " +
                                       $"LOD full {UnitLOD.FullCount} hidden {UnitLOD.HiddenCount} | ");
            foreach (var kv in counts) sb.Append(kv.Key).Append('=').Append(kv.Value).Append(' ');
            return sb.ToString();
        }

        static readonly string[] markers =
        {
            "FixedUpdate.PhysicsFixedUpdate", "FixedUpdate.ScriptRunBehaviourFixedUpdate", "Update.ScriptRunBehaviourUpdate",
            "PreLateUpdate.ScriptRunBehaviourLateUpdate", "PreLateUpdate.DirectorUpdateAnimationBegin", "PreLateUpdate.DirectorUpdateAnimationEnd",
            "PostLateUpdate.FinishFrameRendering", "PostLateUpdate.UpdateAllRenderers", "PostLateUpdate.PlayerUpdateCanvases",
            "PreUpdate.PhysicsUpdate", "Update.DirectorUpdate", "PostLateUpdate.UpdateAllSkinnedMeshes", "Gfx.WaitForPresentOnGfxThread",
            "PlayerLoop", "Gfx.WaitForRenderThread", "Gfx.PresentFrame", "WaitForTargetFPS", "GUI.Repaint", "Camera.Render", "CullScriptable", "Culling",
        };
        Unity.Profiling.ProfilerRecorder[] recs;
        double[] recSum;
        Unity.Profiling.ProfilerRecorder rBatches, rSetPass, rTris;
        double batches, setpass, tris;

        void StartRecorders()
        {
            recs = new Unity.Profiling.ProfilerRecorder[markers.Length];
            recSum = new double[markers.Length];
            for (int i = 0; i < markers.Length; i++) recs[i] = Unity.Profiling.ProfilerRecorder.StartNew(Unity.Profiling.ProfilerCategory.Internal, markers[i]);
            rBatches = Unity.Profiling.ProfilerRecorder.StartNew(Unity.Profiling.ProfilerCategory.Render, "Batches Count");
            rSetPass = Unity.Profiling.ProfilerRecorder.StartNew(Unity.Profiling.ProfilerCategory.Render, "SetPass Calls Count");
            rTris = Unity.Profiling.ProfilerRecorder.StartNew(Unity.Profiling.ProfilerCategory.Render, "Triangles Count");
        }

        readonly FrameTiming[] timing = new FrameTiming[1];
        double cpuMs, gpuMs, mainMs, rtMs, waitMs;
        int timingN, perfFrames;

        void Update()
        {
            frameTimes.Add(Time.unscaledDeltaTime);
            perfFrames++;
            if (recs == null) StartRecorders();
            for (int i = 0; i < recs.Length; i++) if (recs[i].Valid) recSum[i] += recs[i].LastValue;
            batches += rBatches.Valid ? rBatches.LastValue : 0;
            setpass += rSetPass.Valid ? rSetPass.LastValue : 0;
            tris += rTris.Valid ? rTris.LastValue : 0;
            FrameTimingManager.CaptureFrameTimings();
            if (FrameTimingManager.GetLatestTimings(1, timing) > 0)
            {
                cpuMs += timing[0].cpuFrameTime;
                mainMs += timing[0].cpuMainThreadFrameTime;
                rtMs += timing[0].cpuRenderThreadFrameTime;
                waitMs += timing[0].cpuMainThreadPresentWaitTime;
                gpuMs += timing[0].gpuFrameTime;
                timingN++;
            }
        }

        string Timings()
        {
            string s = timingN > 0 ? $"cpu {cpuMs / timingN:0.0} main {mainMs / timingN:0.0} render {rtMs / timingN:0.0} presentwait {waitMs / timingN:0.0} gpu {gpuMs / timingN:0.0} ms | " : "";
            s += Perf.Report(perfFrames);
            if (recs != null && perfFrames > 0)
            {
                s += "| engine:";
                for (int i = 0; i < recs.Length; i++)
                {
                    if (!recs[i].Valid) continue;
                    double ms = recSum[i] / perfFrames / 1e6;
                    if (ms >= 0.05) s += $" {markers[i]} {ms:0.0}";
                    recSum[i] = 0;
                }
                s += $" | batches {batches / perfFrames:0} setpass {setpass / perfFrames:0} tris {tris / perfFrames / 1e6:0.0}M";
                batches = setpass = tris = 0;
            }
            cpuMs = gpuMs = mainMs = rtMs = waitMs = 0;
            timingN = perfFrames = 0;
            return s;
        }

        void Log(string s)
        {
            log.AppendLine($"[{Time.time,7:0.00}] {s}");
            File.WriteAllText(Path.Combine(outDir, "autotest.log"), log.ToString());
        }

        IEnumerator Shot(string name)
        {
            yield return new WaitForEndOfFrame();
            ScreenCapture.CaptureScreenshot(Path.Combine(outDir, name + ".png"));
            yield return null;
        }

        void Look(float yaw, float pitch)
        {
            dir.cameraRig.yaw = yaw;
            dir.cameraRig.pitch = pitch;
            dir.simInput.lookYaw = yaw;
            dir.simInput.lookPitch = pitch;
        }

        IEnumerator MeleeTest(MechVehicle m, int n)
        {
            var targets = FindObjectsByType<WheeledVehicle>(FindObjectsSortMode.InstanceID);
            if (targets.Length == 0) yield break;
            var target = targets[0];
            Vector3 tHome = target.transform.position;
            Quaternion tRot = target.transform.rotation;
            string tag = $"veh_{n:00}_{m.displayName.Replace(' ', '_')}";
            var anim = m.GetComponent<Animator>();
            int upper = anim.GetLayerIndex("UpperBody");
            foreach (bool stomp in new[] { false, true })
            {
                Vector3 pad = new Vector3(-260f, 0.02f, -200f);
                dir.simInput = default;
                m.Teleport(pad, 0f);
                target.Body.isKinematic = true;
                Vector3 tp = pad + new Vector3(1f, target.RestHeight + 0.02f, stomp ? 9f : 11f);
                target.transform.SetPositionAndRotation(tp, Quaternion.Euler(0f, 90f, 0f));
                yield return new WaitForSeconds(0.8f);
                Look(10f, 14f);
                float t = 0f;
                bool onMove = false;
                while (t < (stomp ? 2.2f : 3.2f))
                {
                    dir.simInput = new ControlInput
                    {
                        move = new Vector2(0f, stomp ? 0f : 1f), lookYaw = dir.simInput.lookYaw, lookPitch = dir.simInput.lookPitch,
                        action1Down = !stomp && Mathf.Abs(t - 1.4f) < 0.01f, action2Down = stomp && Mathf.Abs(t - 0.3f) < 0.01f,
                    };
                    if (!stomp && t > 1.5f && t < 1.9f && upper >= 0 && anim.GetLayerWeight(upper) > 0.5f &&
                        anim.GetCurrentAnimatorStateInfo(0).IsName("Walk")) onMove = true;
                    if (!stomp && Mathf.Abs(t - 1.83f) < 0.01f) yield return Shot(tag + "_strike");
                    if (stomp && Mathf.Abs(t - 1.25f) < 0.01f) yield return Shot(tag + "_stomp");
                    t += Time.deltaTime;
                    yield return null;
                }
                dir.simInput = default;
                yield return new WaitForSeconds(0.6f);
                Log($"{m.displayName}: {(stomp ? "stomp" : m.strikeClip + (onMove ? " on the move (legs kept walking)" : " (standing)"))}: " +
                    $"bodies hit {m.LastStrikeHits}, truck shoved {Vector3.Distance(tp, target.transform.position):0.0} m");
            }
            target.Body.linearVelocity = Vector3.zero;
            target.Body.isKinematic = true;
            target.transform.SetPositionAndRotation(tHome, tRot);
        }

        IEnumerator CloseUps(SoldierController s)
        {
            // look down at the ground from closer to see shock rings and the cracked, scorched decals
            s.Place(new Vector3(60f, 0.05f, -318f), 0f);
            Look(0f, 22f);
            yield return new WaitForSeconds(0.5f);
            Vector3 c = new Vector3(60f, 0.05f, -300f);
            Vfx.Stomp(c, 16f);
            yield return new WaitForSeconds(0.18f);
            yield return Shot("vfx_11_close_stomp_ring");
            yield return new WaitForSeconds(3.5f);
            yield return Shot("vfx_12_close_stomp_cracks");
            Vfx.Explosion(c + new Vector3(-7f, 0.3f, 2f), 1.2f, true);
            yield return new WaitForSeconds(0.06f);
            yield return Shot("vfx_13_close_shell_burst");
            yield return new WaitForSeconds(7f);
            yield return Shot("vfx_14_close_shell_crater");
        }

        IEnumerator VfxShowcase(SoldierController s)
        {
            dir.simInput = default;
            s.Place(new Vector3(-150f, 0.05f, -320f), 0f);
            Look(0f, 6f);
            yield return new WaitForSeconds(0.6f);
            Vector3 c = new Vector3(-150f, 0.05f, -280f);
            Vfx.Explosion(c + Vector3.up * 0.3f, 1f, true);
            yield return new WaitForSeconds(0.1f);
            yield return Shot("vfx_01_shell_fireball");
            yield return new WaitForSeconds(1.2f);
            yield return Shot("vfx_02_shell_smoke");
            yield return new WaitForSeconds(4f);
            yield return Shot("vfx_03_shell_scorch_cracks");
            Vfx.Muzzle(c + new Vector3(-9f, 2.4f, -6f), new Vector3(0.4f, 0.08f, 1f), 1.6f);
            yield return new WaitForSeconds(0.12f);
            yield return Shot("vfx_04_artillery_muzzle");
            Vfx.Stomp(c + new Vector3(10f, 0f, 4f), 16f);
            yield return new WaitForSeconds(0.25f);
            yield return Shot("vfx_05_stomp_shockwave");
            yield return new WaitForSeconds(1.6f);
            yield return Shot("vfx_06_stomp_cracks");
            Vfx.Explosion(c + new Vector3(-6f, 0.3f, 14f), 1.8f, true);
            yield return new WaitForSeconds(0.15f);
            yield return Shot("vfx_07_artillery_impact");
            yield return new WaitForSeconds(2.5f);
            yield return Shot("vfx_08_artillery_smoke");
            Log("vfx showcase done");
        }

        IEnumerator Run()
        {
            Log($"Dominion I autotest  {Screen.width}x{Screen.height}  {SystemInfo.graphicsDeviceName}");
            yield return new WaitForSeconds(3f);
            var s = dir.Soldier;
            if (vfxOnly)
            {
                yield return VfxShowcase(s);
                yield return CloseUps(s);
                Log("AUTOTEST DONE");
                Application.Quit();
                yield break;
            }
            Look(s.transform.eulerAngles.y, 12f);
            yield return new WaitForSeconds(0.5f);
            yield return Shot("01_spawn");

            string[] names = { "F", "FR", "R", "BR", "B", "BL", "L", "FL" };
            for (int i = 0; i < 8; i++)
            {
                float a = i * 45f * Mathf.Deg2Rad;
                foreach (bool run in new[] { false, true })
                {
                    Vector3 p0 = s.transform.position;
                    dir.simInput = new ControlInput { move = new Vector2(Mathf.Sin(a), Mathf.Cos(a)), sprint = run, lookYaw = dir.cameraRig.yaw };
                    yield return new WaitForSeconds(1.2f);
                    Vector3 local = s.transform.InverseTransformDirection(s.transform.position - p0) / 1.2f;
                    var anim = s.GetComponentInChildren<Animator>();
                    Log($"soldier {(run ? "run " : "walk")} {names[i],-2}: local vel ({local.x:0.00}, {local.z:0.00}) m/s  " +
                        $"anim VelX {anim.GetFloat("VelX"):0.00} VelZ {anim.GetFloat("VelZ"):0.00}");
                    if (i == 2 && !run) yield return Shot("02_strafe_right");
                    if (i == 1 && run) yield return Shot("03_run_diagonal");
                }
            }
            dir.simInput = default;
            dir.simInput.lookYaw = dir.cameraRig.yaw;
            dir.simInput.aim = true;
            yield return new WaitForSeconds(0.8f);
            dir.simInput.fire = true;
            yield return new WaitForSeconds(0.4f);
            yield return Shot("04_soldier_aim_fire");
            dir.simInput = default;

            int n = 0;
            foreach (var v in FindObjectsByType<Vehicle>(FindObjectsSortMode.InstanceID))
            {
                n++;
                Vector3 home = v.transform.position;
                Quaternion homeRot = v.transform.rotation;
                s.Place(v.ExitPoint, v.transform.eulerAngles.y);
                dir.simInput = default;
                yield return new WaitForSeconds(0.3f);
                bool entered = dir.TryEnterNearest();
                if (!entered || dir.Current != v)
                {
                    Log($"{v.displayName}: could not enter (entered={entered}, current={(dir.Current ? dir.Current.displayName : "none")})");
                    if (dir.Current) dir.Exit();
                    continue;
                }
                Look(v.transform.eulerAngles.y + 25f, 12f);
                float yaw0 = v.transform.eulerAngles.y;
                Vector3 p0 = v.transform.position;
                var air = v as AircraftVehicle;
                if (air != null)
                {
                    dir.simInput = new ControlInput { sprint = true };
                    yield return new WaitForSeconds(16f);
                    Log($"{v.displayName}: takeoff roll {air.Status}");
                    dir.simInput = new ControlInput { sprint = true, move = new Vector2(0f, -0.6f) };
                    yield return new WaitForSeconds(5f);
                    dir.simInput = new ControlInput { sprint = true, action2Down = true };
                    yield return null;
                    dir.simInput = new ControlInput { sprint = true, move = new Vector2(0.6f, -0.4f), fire = true };
                    yield return new WaitForSeconds(2.5f);
                    yield return Shot($"veh_{n:00}_{v.displayName.Replace(' ', '_')}");
                    Log($"{v.displayName}: airborne={!air.Grounded} {air.Status}");
                }
                else
                {
                    // move to an open test pad so nothing parked is in the way
                    Vector3 pad = new Vector3(-260f, home.y + 0.05f, -200f);
                    v.Body.position = pad;
                    v.Body.rotation = Quaternion.identity;
                    v.transform.SetPositionAndRotation(pad, Quaternion.identity);
                    v.Body.linearVelocity = Vector3.zero;
                    yield return new WaitForSeconds(1.2f);
                    p0 = v.transform.position;
                    yaw0 = v.transform.eulerAngles.y;
                    if (!(v is MechVehicle)) Log($"{v.displayName}: resting pitch {Mathf.DeltaAngle(0f, v.transform.eulerAngles.x):0.00} deg (+ = nose down)");
                    // accelerate straight, corner hard, then brake hard: log the body pitch / roll the suspension produces
                    float t = 0f, accPitch = 0f, turnRoll = 0f, brakePitch = 0f, t40 = -1f, rSum = 0f;
                    int rN = 0;
                    bool mech = v is MechVehicle;
                    while (t < 6f)
                    {
                        Look(v.transform.eulerAngles.y + 25f, 12f);
                        float steer = t > 2.2f && t < 4.2f ? 1f : 0f;
                        bool braking = t >= 4.6f && !mech;
                        dir.simInput = new ControlInput
                        {
                            move = new Vector2(steer, braking ? 0f : 1f), sprint = true, jump = braking,
                            fire = mech ? t > 4.6f : t > 1.0f, aim = mech && t > 4.6f, special = mech && t > 4.8f,
                            action1Down = !mech && Mathf.Abs(t - 0.5f) < 0.01f,
                            lookYaw = dir.simInput.lookYaw,
                        };
                        float pitch = Mathf.DeltaAngle(0f, v.transform.eulerAngles.x);   // + = nose down
                        float roll = Mathf.DeltaAngle(0f, v.transform.eulerAngles.z);
                        if (t < 2f) accPitch = Mathf.Min(accPitch, pitch);
                        if (steer > 0f) turnRoll = Mathf.Abs(roll) > Mathf.Abs(turnRoll) ? roll : turnRoll;
                        if (braking) brakePitch = Mathf.Max(brakePitch, pitch);
                        if (t40 < 0f && v.ForwardSpeed > 40f / 3.6f) t40 = t;
                        if (t > 3.4f && t < 4.2f && Mathf.Abs(v.YawRate) > 1f)
                        {
                            rSum += Mathf.Abs(v.ForwardSpeed) / (Mathf.Abs(v.YawRate) * Mathf.Deg2Rad);
                            rN++;
                        }
                        if (Mathf.Abs(t - 3.6f) < 0.01f) yield return Shot($"veh_{n:00}_{v.displayName.Replace(' ', '_')}");
                        t += Time.deltaTime;
                        yield return null;
                    }
                    Log($"{v.displayName}: moved {Vector3.Distance(p0, v.transform.position):0.0} m, turned {Mathf.DeltaAngle(yaw0, v.transform.eulerAngles.y):0} deg, {v.Status}" +
                        (mech ? "" : $"   squat {-accPitch:0.0} deg, corner roll {turnRoll:0.0} deg, brake dive {brakePitch:0.0} deg" +
                                      $"   0-40 km/h {(t40 > 0f ? t40.ToString("0.0") + " s" : "not reached")}   turn radius {(rN > 0 ? rSum / rN : 0f):0.0} m"));
                    if (v is MechVehicle mm)
                        yield return MeleeTest(mm, n);
                    if (v is MechVehicle md && md.CanDash)
                    {
                        // hold Space: thruster dash toward the mouse, Shift boost after a moment
                        float dt0 = 0f, maxSpd = 0f, fuel0 = md.JetFuel, fuelMin = md.JetFuel, lean = 0f;
                        bool dashClip = false;
                        Vector3 d0 = v.transform.position;
                        float yawD = v.transform.eulerAngles.y;
                        var animD = v.GetComponent<Animator>();
                        while (dt0 < 4.5f)
                        {
                            Look(yawD + 25f * Mathf.Sin(dt0 * 0.9f), 10f);
                            dir.simInput = new ControlInput { jump = dt0 < 4f, sprint = dt0 > 1.5f, lookYaw = dir.simInput.lookYaw, lookPitch = dir.simInput.lookPitch };
                            maxSpd = Mathf.Max(maxSpd, AIUtil.Flat(v.Body.linearVelocity).magnitude);
                            lean = Mathf.Max(lean, md.Tilt);
                            fuelMin = Mathf.Min(fuelMin, md.JetFuel);
                            if (animD && animD.GetCurrentAnimatorStateInfo(0).IsName("Dash")) dashClip = true;
                            if (Mathf.Abs(dt0 - 2.6f) < 0.01f) yield return Shot($"veh_{n:00}_{v.displayName.Replace(' ', '_')}_dash");
                            dt0 += Time.deltaTime;
                            yield return null;
                        }
                        dir.simInput = default;
                        yield return new WaitForSeconds(2.5f);
                        Log($"{v.displayName}: dash {AIUtil.Flat(v.transform.position - d0).magnitude:0} m, top speed {maxSpd * 3.6f:0} km/h, lean {lean:0} deg, " +
                            $"charge used {fuel0 - fuelMin:0.0} of {md.jetFuelMax:0} s, Dash clip {(dashClip ? "playing" : "missing")}, after 2.5 s: {md.Status}");
                    }
                    if (v is MechVehicle mv && mv.hasJets)
                    {
                        // hold Space: climb toward the sky, then dive at the ground, firing
                        float ft = 0f, maxAlt = 0f, diveTilt = 0f, diveSpeed = 0f;
                        float yawF = v.transform.eulerAngles.y;
                        while (ft < 8f)
                        {
                            float pitchL = ft < 3.5f ? -28f : 38f;
                            Look(yawF + 15f * Mathf.Sin(ft), pitchL);
                            dir.simInput = new ControlInput { jump = ft < 7f, sprint = ft > 1f, fire = ft > 4.5f,
                                lookYaw = dir.simInput.lookYaw, lookPitch = dir.simInput.lookPitch };
                            maxAlt = Mathf.Max(maxAlt, v.transform.position.y);
                            if (ft > 4.5f && ft < 6f) { diveTilt = Mathf.Max(diveTilt, mv.Tilt); diveSpeed = Mathf.Max(diveSpeed, v.Body.linearVelocity.magnitude); }
                            if (Mathf.Abs(ft - 2.8f) < 0.01f) yield return Shot($"veh_{n:00}_{v.displayName.Replace(' ', '_')}_fly_climb");
                            if (Mathf.Abs(ft - 5.2f) < 0.01f) yield return Shot($"veh_{n:00}_{v.displayName.Replace(' ', '_')}_fly_dive");
                            ft += Time.deltaTime;
                            yield return null;
                        }
                        string anim = v.GetComponent<Animator>().GetCurrentAnimatorStateInfo(0).IsName("Fly") ? "Fly" : "other";
                        Log($"{v.displayName}: flight max alt {maxAlt:0} m, dive tilt {diveTilt:0} deg, dive speed {diveSpeed * 3.6f:0} km/h, state {anim}");
                        dir.simInput = default;
                        yield return new WaitForSeconds(4f);
                        Log($"{v.displayName}: after jets off y={v.transform.position.y:0.0} m tilt {mv.Tilt:0} deg");
                    }
                }
                dir.simInput = default;
                // park it back where it was and leave
                yield return new WaitForSeconds(0.2f);
                v.Body.linearVelocity = Vector3.zero;
                v.Body.position = home;
                v.Body.rotation = homeRot;
                v.transform.SetPositionAndRotation(home, homeRot);
                yield return new WaitForFixedUpdate();
                v.Body.linearVelocity = Vector3.zero;
                yield return new WaitForSeconds(0.3f);
                if (dir.Current == v && v.CanExit) dir.Exit();
                else
                {
                    Log($"{v.displayName}: CanExit=false after parking, forcing exit");
                    dir.Exit();
                }
            }
            yield return VfxShowcase(s);
            Look(0f, 25f);
            s.Place(new Vector3(0f, 0.05f, -30f), 0f);
            yield return new WaitForSeconds(1f);
            yield return Shot("99_overview");
            frameTimes.Sort();
            float med = frameTimes.Count > 0 ? frameTimes[frameTimes.Count / 2] : 0f;
            Log($"frames {frameTimes.Count}, median frame {med * 1000f:0.0} ms ({1f / Mathf.Max(med, 1e-4f):0} fps)");
            Log("AUTOTEST DONE");
            yield return new WaitForSeconds(0.5f);
            Application.Quit();
        }
    }
}
