using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Pilot AI for the force-based flight model (it only moves the stick, rudder and throttle).
    /// Roll-and-pull steering: roll until the target sits above the canopy, then pull; near the nose it levels the wings
    /// and fine-aims with pitch and rudder. Dogfights with lead pursuit, makes diving gun runs on ground targets and
    /// extends away to set up the next pass, breaks hard when an enemy sits on its tail, manages speed with the
    /// throttle, never pulls into a stall and always recovers from a dive with height to spare. Parked aircraft taxi
    /// down the runway and take off on their own.
    /// Roles:
    ///  - Biplanes are the scouts: slow, so they stay out of trouble. They fly high over the parts of the map their side
    ///    has looked at least recently (Intel recon cells), steer around enemy flak (anti-air tanks, airship guns, places
    ///    they were shot at), and when a jet comes for them they run for the cover of a friendly airship or jet, break
    ///    hard when it closes in, and call for help. They only shoot back in self-defence.
    ///  - Jets answer a scout's call for help first, then hunt: enemy aircraft (enemy scouts and anything chasing ours
    ///    first), ground units and airships. Wraiths fly escort on a scout. Idle jets strike the best known enemy
    ///    position or sweep the stalest part of the map for intel.
    /// </summary>
    public class PlaneAI : MonoBehaviour
    {
        enum Mode { Parked, Takeoff, Cruise, Dogfight, Attack, Extend, Evade, Recon, Flee, Escort }
        Mode mode = Mode.Cruise;
        AircraftVehicle a;
        Health self, target;
        float simAcc, simDt;
        float thinkT, modeT, waitT, runwayYaw, evadeSign = 1f, errT;
        float cruiseAlt, attackAlt, combatSpeed, cruiseSpeed, gunRange;
        bool gearCalled, scout, counted, hasDest;
        Vector3 extendDir, aimErr, dest, haven;
        public string State => mode.ToString();
        public Health Target => target;

        // ------------------------------------------------------------------ roles
        static readonly List<PlaneAI> planes = new List<PlaneAI>();
        /// <summary>Enemy aircraft chasing one of a side's scouts, and when that was last seen (jets go for them first).</summary>
        static readonly Dictionary<Health, float>[] wanted = { null, new Dictionary<Health, float>(), new Dictionary<Health, float>() };
        /// <summary>Places a side's scouts were shot at from the ground, avoided for a while.</summary>
        static readonly List<(Team team, Vector3 p, float until)> hazards = new List<(Team, Vector3, float)>();
        struct Zone { public Vector3 c; public float r; }
        readonly List<Zone> zones = new List<Zone>();
        PlaneAI helping, escortOf;
        float threatT = -99f, safeT;
        System.Func<Vector3, bool> blockedFn;
        /// <summary>Scout: who is after it right now.</summary>
        public Health Threat { get; private set; }
        public bool Scout => scout;
        public bool InDanger => Threat && Threat.Alive && Time.time - threatT < 4f;
        public static int HelpCalls, Responses, ScoutLosses, JetLosses;

        void OnDestroy() => planes.Remove(this);

        public void Init(Health h, bool parked, float takeoffDelay)
        {
            a = GetComponent<AircraftVehicle>();
            self = h;
            mode = parked ? Mode.Parked : Mode.Cruise;
            waitT = takeoffDelay;
            runwayYaw = transform.eulerAngles.y;
            bool jet = a.Jet;
            scout = !jet;
            // scouts fly high: out of small-arms reach, and the flak has less of a slant range on them
            cruiseAlt = jet ? Random.Range(380f, 520f) : Random.Range(600f, 720f);
            attackAlt = jet ? 520f : 300f;
            blockedFn = Blocked;
            if (!planes.Contains(this)) planes.Add(this);
            cruiseSpeed = jet ? Mathf.Min(a.maxSpeed * 0.75f, 210f) : a.maxSpeed * 0.92f;
            combatSpeed = jet ? Mathf.Min(a.maxSpeed * 0.62f, 175f) : a.maxSpeed * 0.95f;
            gunRange = jet ? 850f : 520f;
            thinkT = Random.Range(0f, 0.3f);
        }

        /// <summary>Enemy airships' gun umbrellas (centre, radius^2), refreshed before each target pick.</summary>
        readonly List<(Vector3 c, float r2)> umbrella = new List<(Vector3, float)>();

        /// <summary>Jet target preference (scouts don't hunt). Anything under an enemy airship's guns is worth less.</summary>
        float Pref(Health h, float dist)
        {
            float p = BasePref(h, dist);
            if (p > 0f && !h.IsAirship)
                for (int i = 0; i < umbrella.Count; i++)
                    if ((h.Center - umbrella[i].c).sqrMagnitude < umbrella[i].r2) { p *= 0.35f; break; }
            return p;
        }

        float BasePref(Health h, float dist)
        {
            if (h.IsDrone) return 0f;
            bool cannon = a.fireInterval < 0.04f;
            bool fighter = a.unitKey == "Aircraft_Wraith" || a.unitKey == "Aircraft_Saber";
            bool flying = h.cls == UnitClass.Air && h.Airborne && !h.IsAirship;
            if (escortOf != null)
            {
                // flying escort: only aircraft near our scout, or whoever is shooting at us
                if (!flying) return 0f;
                if ((h.Center - escortOf.transform.position).sqrMagnitude > 1800f * 1800f && h != self.LastAttacker) return 0f;
                return 2f;
            }
            if (flying)
            {
                if (wanted[(int)self.team].TryGetValue(h, out float wt) && Time.time - wt < 5f) return 3f;   // after one of our scouts
                if (h.Vehicle is AircraftVehicle ev && !ev.Jet) return 1.6f;                                   // their eyes in the sky
                return fighter ? (dist < 900f ? 1.4f : 0.6f) : (dist < 600f ? 1.1f : 0.3f);
            }
            if (h.IsAirship) return cannon ? 0.7f : 0.1f;              // only cannon fire hurts a hull that size
            switch (h.cls)
            {
                case UnitClass.Soldier: return 0.4f;
                case UnitClass.Mech: return cannon ? 0.9f : 0.2f;
                case UnitClass.Air: return 0.35f;                  // parked on the ground
                default:
                    if (cannon) return h.armor == ArmorClass.Armored ? 0.9f : 1f;
                    return h.armor == ArmorClass.Armored ? 0.05f : h.armor == ArmorClass.Light ? 0.4f : 0.8f;
            }
        }

        void SetMode(Mode m)
        {
            mode = m;
            modeT = 0f;
        }

        void Update()
        {
            long perfT0 = Perf.Now;
            float sdt = Time.deltaTime;
            if (self == null || a == null || a.PlayerDriven || self.SimTick(ref simAcc, out sdt))
            {
                simDt = sdt;
                UpdateTimed();
            }
            Perf.Add(Perf.PlaneAI, perfT0);
        }

        void UpdateTimed()
        {
            if (!counted && a != null && self != null && (a.Destroyed || !self.Alive))
            {
                counted = true;
                if (scout) ScoutLosses++; else JetLosses++;
            }
            if (a == null || self == null || a.Destroyed || !self.Alive) return;
            if (a.PlayerDriven) { if (mode == Mode.Parked || mode == Mode.Takeoff) SetMode(Mode.Cruise); gearCalled = true; return; }
            var war = WarManager.Instance;
            if (war == null || !war.Fighting) return;
            if (!a.Occupied) a.OnEnter();
            float dt = simDt;
            modeT += dt;
            thinkT -= dt;
            if (thinkT <= 0f)
            {
                thinkT = 0.3f;
                Think(war);
            }
            Steer(war, dt);
        }

        // ------------------------------------------------------------------ decisions
        void Think(WarManager war)
        {
            if (mode == Mode.Parked || mode == Mode.Takeoff) return;
            Vector3 pos = transform.position;
            if (scout)
            {
                ThinkScout(war, pos);
                return;
            }
            if (escortOf != null && (!escortOf || !escortOf.self || !escortOf.self.Alive)) escortOf = null;
            if (escortOf == null && a.unitKey == "Aircraft_Wraith") escortOf = ScoutToEscort(pos);
            if (mode != Mode.Extend && mode != Mode.Evade)
            {
                Health call = AnswerHelp(pos);
                if (call) { target = call; if (mode != Mode.Dogfight) SetMode(Mode.Dogfight); }
                else
                {
                    umbrella.Clear();
                    foreach (var sh in Airship.All)
                        if (sh && Health.Enemies(sh.team, self.team) && sh.health && sh.health.Alive)
                            umbrella.Add((sh.transform.position, sh.gunRange * sh.gunRange * 0.56f));
                    target = AIUtil.PickTarget(self, pos, 2400f, Pref, target, transform, false, out _);
                    if (target == null)
                    {
                        if (escortOf != null) { if (mode != Mode.Escort) SetMode(Mode.Escort); }
                        else if ((mode != Mode.Cruise && mode != Mode.Recon) || !hasDest || AIUtil.Flat(dest - pos).magnitude < 400f) Idle(war, pos);
                    }
                    else if (target.Airborne) { if (mode != Mode.Dogfight) SetMode(Mode.Dogfight); }
                    else if (mode != Mode.Attack) SetMode(Mode.Attack);
                }
            }
            // stores: the Saber drops its tanks going into a fight; the Wraith fires missiles at aircraft ahead of the nose
            if (target && (mode == Mode.Dogfight || mode == Mode.Attack)) a.JettisonTanks();
            if (target && target.Airborne && !target.IsAirship && a.HasMissiles)
            {
                Vector3 to = target.Center - pos;
                float d = to.magnitude;
                if (d > 250f && d < 2200f && Vector3.Angle(transform.forward, to) < 22f) a.FireMissile(target);
            }
            // someone on my six? break
            if (mode != Mode.Evade)
            {
                var all = Health.All;
                for (int i = 0; i < all.Count; i++)
                {
                    var h = all[i];
                    if (h.cls != UnitClass.Air || !h.Alive || !Health.Enemies(h.team, self.team) || !h.Airborne) continue;
                    Vector3 d = pos - h.Center;
                    float dist = d.magnitude;
                    if (dist > 650f || dist < 1f) continue;
                    bool behind = Vector3.Dot(transform.forward, -d / dist) < -0.4f;
                    bool pointing = Vector3.Dot(h.transform.forward, d / dist) > 0.96f;
                    if (behind && pointing && Random.value < 0.55f)
                    {
                        evadeSign = Random.value < 0.5f ? -1f : 1f;
                        target = h;
                        SetMode(Mode.Evade);
                        break;
                    }
                }
            }
        }

        /// <summary>Jet with nothing in reach: strike the best known enemy position, else sweep the stalest part of the map.</summary>
        void Idle(WarManager war, Vector3 pos)
        {
            if (Intel.Best(self.team, pos, out var hot, 2.5f) && AIUtil.Flat(hot.pos - pos).magnitude > 500f)
            {
                dest = hot.pos;
                hasDest = true;
                SetMode(Mode.Cruise);
            }
            else if (Intel.ReconTarget(self.team, pos, war.EnemyBase(self.team), 1f, null, out dest))
            {
                hasDest = true;
                SetMode(Mode.Recon);
            }
            else
            {
                hasDest = false;
                SetMode(Mode.Cruise);
            }
        }

        /// <summary>A friendly scout under attack by an aircraft, within 4 km, with fewer than two jets already coming.</summary>
        Health AnswerHelp(Vector3 pos)
        {
            if (helping != null && helping && helping.InDanger && helping.Threat.Airborne) return helping.Threat;
            helping = null;
            PlaneAI best = null;
            float bd = 4000f;
            foreach (var s in planes)
            {
                if (!s || !s.scout || s.self == null || s.self.team != self.team || !s.self.Alive || !s.InDanger) continue;
                if (s.Threat.cls != UnitClass.Air || !s.Threat.Airborne) continue;      // a jet can't help against flak
                float d = Vector3.Distance(pos, s.transform.position);
                if (d >= bd) continue;
                int n = 0;
                foreach (var p in planes) if (p && p != this && p.helping == s) n++;
                if (n >= 2) continue;
                bd = d;
                best = s;
            }
            if (best == null) return null;
            helping = best;
            Responses++;
            return best.Threat;
        }

        /// <summary>Wraiths: the nearest friendly scout in the air that has no escort yet.</summary>
        PlaneAI ScoutToEscort(Vector3 pos)
        {
            PlaneAI best = null;
            float bd = 6000f;
            foreach (var s in planes)
            {
                if (!s || !s.scout || s.self == null || s.self.team != self.team || !s.self.Alive || s.a.Grounded) continue;
                bool taken = false;
                foreach (var p in planes) if (p && p != this && p.escortOf == s) { taken = true; break; }
                if (taken) continue;
                float d = Vector3.Distance(pos, s.transform.position);
                if (d < bd) { bd = d; best = s; }
            }
            return best;
        }

        // ------------------------------------------------------------------ scouts
        void ThinkScout(WarManager war, Vector3 pos)
        {
            BuildZones(pos);
            Health air = AirThreat(pos);
            var la = self.LastAttacker;
            bool hit = Time.time - self.LastHitTime < 2.5f && la && la.Alive;
            bool hitFromAir = hit && la.cls == UnitClass.Air && la.Airborne && !la.IsAirship;
            if (hit && !hitFromAir && (hazards.Count == 0 || hazards[hazards.Count - 1].until < Time.time + 74f))
                hazards.Add((self.team, la.transform.position, Time.time + 75f));       // flak / ground fire: remember where
            Health threat = air ? air : hitFromAir ? la : hit ? la : null;
            if (threat)
            {
                bool airThreat = threat.cls == UnitClass.Air && threat.Airborne;
                if (airThreat && (Threat != threat || Time.time - threatT > 4f)) HelpCalls++;
                Threat = threat;
                threatT = Time.time;
                if (airThreat) wanted[(int)self.team][threat] = Time.time;
                safeT = 0f;
                haven = Haven(pos);
                if (mode != Mode.Flee && mode != Mode.Evade) SetMode(Mode.Flee);
            }
            else if (mode == Mode.Flee)
            {
                haven = Haven(pos);
                if ((safeT += 0.3f) > 5f) { hasDest = false; SetMode(Mode.Recon); }
            }
            if (mode == Mode.Cruise) SetMode(Mode.Recon);
            if (mode == Mode.Recon && (!hasDest || AIUtil.Flat(dest - pos).magnitude < 300f || Blocked(dest)))
            {
                // hurt: keep to our own half
                float bias = self.Fraction < 0.45f ? -0.8f : 0.8f;
                hasDest = Intel.ReconTarget(self.team, pos, war.EnemyBase(self.team), bias, blockedFn, out dest);
            }
            // a jet on my tail: break hard (scouts nearly always see it coming)
            if (mode != Mode.Evade && air)
            {
                Vector3 d = pos - air.Center;
                float dist = d.magnitude;
                if (dist < 700f && Vector3.Dot(transform.forward, -d / dist) < -0.3f && Random.value < 0.9f)
                {
                    evadeSign = Random.value < 0.5f ? -1f : 1f;
                    SetMode(Mode.Evade);
                }
            }
        }

        /// <summary>The nearest enemy jet coming at us (pointing our way within 1.3 km, or anywhere within 600 m).</summary>
        Health AirThreat(Vector3 pos)
        {
            Health best = null;
            float bd = 1300f;
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (h.cls != UnitClass.Air || !h.Alive || !h.Airborne || h.IsAirship || h.IsDrone || !Health.Enemies(h.team, self.team)) continue;
                if (!(h.Vehicle is AircraftVehicle ev) || !ev.Jet) continue;
                Vector3 rel = pos - h.Center;
                float dist = rel.magnitude;
                if (dist >= bd || dist < 1f) continue;
                bool pointing = Vector3.Dot(h.transform.forward, rel / dist) > 0.85f;
                if (!pointing && dist > 600f) continue;
                bd = dist;
                best = h;
            }
            return best;
        }

        /// <summary>Where to run: under a friendly airship's guns, else to the nearest friendly jet, else home.</summary>
        Vector3 Haven(Vector3 pos)
        {
            float bd = 5000f;
            Vector3 best = Vector3.zero;
            bool found = false;
            foreach (var s in Airship.All)
            {
                if (!s || s.team != self.team || !s.health || !s.health.Alive) continue;
                float d = AIUtil.Flat(s.transform.position - pos).magnitude;
                if (d < bd) { bd = d; best = s.transform.position; found = true; }
            }
            if (found) return best;
            bd = 3000f;
            foreach (var p in planes)
            {
                if (!p || p.scout || p.self == null || p.self.team != self.team || !p.self.Alive || p.a.Grounded) continue;
                float d = Vector3.Distance(p.transform.position, pos);
                if (d < bd) { bd = d; best = p.transform.position; found = true; }
            }
            if (found) return best;
            return WarManager.Instance ? WarManager.Instance.OwnBase(self.team) * 0.5f : Vector3.zero;
        }

        /// <summary>Flak the scout keeps clear of: enemy anti-air tanks, enemy airship guns, and places it was shot at.</summary>
        void BuildZones(Vector3 pos)
        {
            zones.Clear();
            float alt = cruiseAlt;
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (!h.Alive || h.key != "Tank_AntiAir" || !Health.Enemies(h.team, self.team)) continue;
                Vector3 c = h.transform.position;
                if (AIUtil.Flat(c - pos).sqrMagnitude > 4000f * 4000f) continue;
                zones.Add(new Zone { c = c, r = Mathf.Sqrt(Mathf.Max(0f, 1150f * 1150f - alt * alt)) + 200f });
            }
            foreach (var s in Airship.All)
            {
                if (!s || !Health.Enemies(s.team, self.team) || !s.health || !s.health.Alive) continue;
                float dh = Mathf.Max(0f, alt - s.AltitudeAboveGround);
                float R = s.gunRange * 0.85f;
                zones.Add(new Zone { c = s.transform.position, r = Mathf.Sqrt(Mathf.Max(0f, R * R - dh * dh)) + 150f });
            }
            for (int i = hazards.Count - 1; i >= 0; i--)
            {
                if (hazards[i].until < Time.time) { hazards.RemoveAt(i); continue; }
                if (hazards[i].team == self.team) zones.Add(new Zone { c = hazards[i].p, r = 700f });
            }
        }

        bool Blocked(Vector3 p)
        {
            for (int i = 0; i < zones.Count; i++)
                if (AIUtil.Flat(p - zones[i].c).sqrMagnitude < zones[i].r * zones[i].r) return true;
            return false;
        }

        /// <summary>Bend the wanted heading away from flak zones (hard when already inside one, at full power).</summary>
        Vector3 Avoid(Vector3 want, Vector3 pos, ref float speed)
        {
            Vector3 push = Vector3.zero;
            for (int i = 0; i < zones.Count; i++)
            {
                var z = zones[i];
                Vector3 off = AIUtil.Flat(pos - z.c);
                float d = off.magnitude, m = z.r + 350f;
                if (d >= m) continue;
                float k = Mathf.Clamp01((m - d) / 350f) * (d < z.r ? 2.5f : 1.2f);
                push += (d > 1f ? off / d : transform.right) * k;
                if (d < z.r) speed = a.maxSpeed;
            }
            return push == Vector3.zero ? want : (want + push).normalized;
        }

        // ------------------------------------------------------------------ flying
        void Steer(WarManager war, float dt)
        {
            var ci = new ControlInput();
            Vector3 pos = transform.position;
            Vector3 vel = a.Body.linearVelocity;
            Vector3 flatFwd = AIUtil.Flat(transform.forward).normalized;
            if (flatFwd.sqrMagnitude < 0.01f) flatFwd = AIUtil.Flat(vel).normalized;
            Vector3 want = flatFwd;
            float wantSpeed = cruiseSpeed;
            bool fireOk = false;

            if (mode == Mode.Parked)
            {
                ci.jump = true;
                waitT -= dt;
                if (waitT <= 0f) SetMode(Mode.Takeoff);
                a.input = ci;
                return;
            }
            if (mode == Mode.Takeoff)
            {
                // full power down the runway, keep the centreline, rotate at lift-off speed, gear up once climbing
                ci.sprint = true;
                float hdg = Mathf.DeltaAngle(transform.eulerAngles.y, runwayYaw);
                float steer = Mathf.Clamp(hdg / 6f, -1f, 1f);
                ci.move = new Vector2(a.Grounded ? steer : 0f, 0f);
                ci.yaw = a.Grounded ? steer * 0.5f : 0f;
                if (a.Grounded && a.Airspeed > a.takeoffSpeed)
                {
                    ci.move = new Vector2(steer * 0.5f, -0.6f);
                }
                else if (!a.Grounded)
                {
                    Vector3 climb = flatFwd + Vector3.up * (a.Jet ? 0.2f : 0.12f);
                    Fly(ref ci, climb, a.maxSpeed, dt);
                    ci.sprint = true;
                    ci.crouch = false;
                }
                if (!a.Grounded && a.Altitude > 18f && !gearCalled) { ci.action2Down = true; gearCalled = true; }
                if (a.Altitude > 40f || (!a.Grounded && modeT > 60f)) SetMode(Mode.Cruise);
                a.input = ci;
                return;
            }

            switch (mode)
            {
                case Mode.Cruise:
                {
                    // head for a known enemy position (or the enemy side) at cruise altitude
                    Vector3 dst = hasDest ? dest : war.EnemyBase(self.team) * 0.6f;
                    if (!hasDest && AIUtil.Flat(dst - pos).magnitude < 300f) dst = new Vector3(-pos.x, 0f, -pos.z * 0.5f);
                    dst.y = WorldGround.Top(dst.x, dst.z) + cruiseAlt;
                    want = (dst - pos).normalized;
                    break;
                }
                case Mode.Recon:
                {
                    // fly over the stalest part of the map; a scout with nowhere safe to go loiters over our own side
                    Vector3 dst = hasDest ? dest : war.OwnBase(self.team) * 0.35f;
                    dst.y = WorldGround.Top(dst.x, dst.z) + cruiseAlt;
                    want = (dst - pos).normalized;
                    if (scout) want = Avoid(want, pos, ref wantSpeed);
                    break;
                }
                case Mode.Flee:
                {
                    // run for cover at full power, diving a little for speed when a jet is after us; away from flak
                    bool airThreat = Threat && Threat.cls == UnitClass.Air && Threat.Airborne;
                    Vector3 h = haven;
                    h.y = WorldGround.Top(h.x, h.z) + (airThreat ? 250f : cruiseAlt);
                    want = (h - pos).normalized;
                    if (Threat && !airThreat) want = (want + AIUtil.Flat(pos - Threat.transform.position).normalized * 1.2f).normalized;
                    wantSpeed = a.maxSpeed;
                    want = Avoid(want, pos, ref wantSpeed);
                    break;
                }
                case Mode.Escort:
                {
                    // circle our scout a little above it, ready to pounce on anything that comes for it
                    if (escortOf == null || !escortOf) { SetMode(Mode.Cruise); break; }
                    Vector3 c = escortOf.transform.position + Vector3.up * 120f;
                    Vector3 rel = AIUtil.Flat(pos - c);
                    if (rel.magnitude > 1400f) { want = (c - pos).normalized; wantSpeed = cruiseSpeed; break; }
                    float ang = Mathf.Atan2(rel.x, rel.z) + 35f * Mathf.Deg2Rad;
                    Vector3 p = c + new Vector3(Mathf.Sin(ang), 0f, Mathf.Cos(ang)) * 650f;
                    want = (p - pos).normalized;
                    wantSpeed = combatSpeed;
                    break;
                }
                case Mode.Dogfight:
                {
                    if (!target || !target.Alive || !target.Airborne) { SetMode(Mode.Cruise); break; }
                    Vector3 gun = pos + transform.forward * 3f;
                    if ((errT -= dt) <= 0f) { errT = 0.4f; aimErr = AIUtil.AimError(Vector3.Distance(pos, target.Center), 0.35f); }
                    Vector3 lead = AIUtil.Lead(gun, target, a.ProjectileSpeed, 0.15f) + aimErr;
                    Vector3 to = lead - pos;
                    float dist = to.magnitude;
                    want = to / Mathf.Max(dist, 1f);
                    wantSpeed = dist > 900f ? cruiseSpeed : combatSpeed;
                    // don't ram it: overshoot avoidance
                    if (dist < 70f && Vector3.Dot(vel - target.Velocity, to) > 0f) want = Quaternion.AngleAxis(50f * evadeSign, Vector3.up) * want + Vector3.up * 0.4f;
                    float cone = 3.5f + Mathf.Atan2(target.Radius * 2f, Mathf.Max(dist, 1f)) * Mathf.Rad2Deg;
                    fireOk = dist < gunRange && Vector3.Angle(transform.forward, to) < cone;
                    break;
                }
                case Mode.Attack:
                {
                    if (!target || !target.Alive) { SetMode(Mode.Cruise); break; }
                    Vector3 to = target.Center - pos;
                    float flat = AIUtil.Flat(to).magnitude;
                    float diveStart = a.Jet ? 1500f : 750f;
                    if (flat > diveStart)
                    {
                        // run in at attack altitude
                        Vector3 dest = target.Center;
                        dest.y = WorldGround.Height(dest.x, dest.z) + attackAlt;
                        want = (dest - pos).normalized;
                        wantSpeed = cruiseSpeed;
                    }
                    else
                    {
                        if ((errT -= dt) <= 0f) { errT = 0.4f; aimErr = AIUtil.AimError(to.magnitude, 0.3f); }
                        Vector3 lead = AIUtil.Lead(pos, target, a.ProjectileSpeed, 0.15f) + aimErr;
                        Vector3 tl = lead - pos;
                        want = tl.normalized;
                        wantSpeed = combatSpeed;
                        fireOk = tl.magnitude < gunRange * 1.15f && Vector3.Angle(transform.forward, tl) < 2.5f;
                        // pass over: pull off and extend
                        if (flat < (a.Jet ? 260f : 140f) || a.Altitude < PullOut() + 25f)
                        {
                            extendDir = flatFwd;
                            SetMode(Mode.Extend);
                        }
                    }
                    break;
                }
                case Mode.Extend:
                {
                    want = (extendDir + Vector3.up * 0.35f).normalized;
                    wantSpeed = cruiseSpeed;
                    bool farEnough = !target || AIUtil.Flat(target.Center - pos).magnitude > (a.Jet ? 1500f : 800f);
                    if (modeT > 14f || (modeT > 5f && a.Altitude > attackAlt * 0.7f && farEnough)) SetMode(Mode.Cruise);
                    break;
                }
                case Mode.Evade:
                {
                    // hard break turn, diving a little to keep the speed up
                    want = (transform.right * evadeSign * 1.3f + flatFwd * 0.3f + Vector3.down * 0.15f).normalized;
                    wantSpeed = a.maxSpeed;
                    if (modeT > Random.Range(2.2f, 3.5f))
                    {
                        if (scout) SetMode(InDanger ? Mode.Flee : Mode.Recon);
                        else SetMode(target && target.Alive && target.Airborne ? Mode.Dogfight : Mode.Cruise);
                    }
                    break;
                }
            }
            // scouts only shoot in self-defence: a snap shot at the jet chasing them when it crosses the nose
            if (scout && Threat && Threat.Alive && Threat.Airborne && (mode == Mode.Flee || mode == Mode.Evade))
            {
                Vector3 to = Threat.Center - pos;
                fireOk = to.magnitude < gunRange && Vector3.Angle(transform.forward, to) < 5f;
            }

            // ---------------- safety overrides: battlefield edge, ceiling, dive limit, then ground recovery (always wins)
            // height above whatever is below us and along our flight path (hills, towers)
            float alt = Mathf.Min(a.Altitude, ClearanceAhead(pos, vel));
            if (Mathf.Abs(pos.x) > war.airBound || Mathf.Abs(pos.z) > war.airBound)
            {
                Vector3 home = (-AIUtil.Flat(pos)).normalized;
                want = (home + Vector3.up * Mathf.Clamp((cruiseAlt - alt) / 300f, -0.2f, 0.4f)).normalized;
            }
            if (alt > 1100f) want = new Vector3(want.x, Mathf.Min(want.y, -0.15f), want.z);
            // never dive steeper than the height allows (no split-S at low level): a shallower attack angle instead
            want.Normalize();
            float maxDive = a.Jet ? Mathf.Clamp((alt - 120f) / 12f, 3f, 35f) : Mathf.Clamp((alt - 60f) / 6f, 3f, 40f);
            if (want.y < -Mathf.Sin(maxDive * Mathf.Deg2Rad))
            {
                Vector3 f = AIUtil.Flat(want);
                f = f.sqrMagnitude > 1e-4f ? f.normalized : flatFwd;
                want = f * Mathf.Cos(maxDive * Mathf.Deg2Rad) - Vector3.up * Mathf.Sin(maxDive * Mathf.Deg2Rad);
            }
            // don't collide with anyone (head-on passes, merges)
            want = Deconflict(want, pos, vel, alt);
            if (alt < PullOut())
            {
                want = (flatFwd * 0.8f + Vector3.up * 0.6f).normalized;
                wantSpeed = a.maxSpeed;
                fireOk = fireOk && alt > 25f;
            }

            Fly(ref ci, want, wantSpeed, dt);
            ci.fire = fireOk;
            a.input = ci;
        }

        static float ClearanceAhead(Vector3 pos, Vector3 vel)
        {
            float best = float.MaxValue;
            for (int i = 0; i < 5; i++)
            {
                Vector3 p = pos + vel * (i * 1.2f);
                best = Mathf.Min(best, p.y - WorldGround.Top(p.x, p.z));
            }
            return best;
        }

        /// <summary>
        /// Height below which we must start pulling out: the height lost rolling upright, plus the arc of a pull-up at a
        /// sustainable load factor from the current dive angle, plus a floor.
        /// </summary>
        float PullOut()
        {
            Vector3 v = a.Body.linearVelocity;
            float speed = Mathf.Max(v.magnitude, 1f);
            float sink = Mathf.Max(0f, -v.y);
            float gamma = Mathf.Asin(Mathf.Clamp01(sink / speed));
            float n = a.Jet ? 5.5f : 3.5f;
            float r = speed * speed / (9.81f * n);
            float bank = Mathf.Abs(Mathf.Atan2(-transform.right.y, transform.up.y) * Mathf.Rad2Deg);
            float rollT = bank > 60f ? bank / Mathf.Max(a.rollRate * 0.6f, 30f) : 0f;
            return (a.Jet ? 70f : 40f) + r * (1f - Mathf.Cos(gamma)) + sink * (rollT + 0.5f);
        }

        /// <summary>Steer around any aircraft we are about to pass too close to (time to closest approach under 3 s).</summary>
        Vector3 Deconflict(Vector3 want, Vector3 pos, Vector3 vel, float alt)
        {
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (h == self || h.cls != UnitClass.Air || !h.Alive || !h.Airborne) continue;
                Vector3 rel = h.Center - pos;
                if (rel.sqrMagnitude > 900f * 900f) continue;
                Vector3 rv = h.Velocity - vel;
                float tca = -Vector3.Dot(rel, rv) / Mathf.Max(rv.sqrMagnitude, 1f);
                if (tca <= 0f || tca > 3f) continue;
                Vector3 miss = rel + rv * tca;
                float m = miss.magnitude;
                if (m > 35f) continue;
                // break away from the closest-approach point; prefer climbing when low
                Vector3 away = m > 1f ? -miss / m : transform.up;
                if (alt < 250f && away.y < 0f) away.y = -away.y;
                return (want + away * 1.2f).normalized;
            }
            return want;
        }

        /// <summary>Roll-and-pull steering toward a world direction, plus throttle for the wanted airspeed.</summary>
        void Fly(ref ControlInput ci, Vector3 want, float speed, float dt)
        {
            Transform T = transform;
            Vector3 dl = T.InverseTransformDirection(want.normalized);
            float off = Vector3.Angle(Vector3.forward, dl);
            float theta = Mathf.Atan2(dl.x, dl.y) * Mathf.Rad2Deg;          // where the target sits around the nose: 0 = above the canopy
            bool push = dl.y < 0f && off < 20f;
            float rollErr = push ? Mathf.DeltaAngle(180f, theta) : theta;
            float bank = Mathf.Atan2(-T.right.y, T.up.y) * Mathf.Rad2Deg;   // + = right wing down
            float k = Mathf.Clamp01((off - 3f) / 15f);
            rollErr = Mathf.Lerp(-bank * 0.6f, rollErr, k);                 // close to the nose: wings level, fine aim with pitch / rudder
            Vector3 w = T.InverseTransformDirection(a.Body.angularVelocity) * Mathf.Rad2Deg;
            float roll = Mathf.Clamp(rollErr / 40f + w.z * 0.005f, -1f, 1f);
            float pitchErr = Mathf.Atan2(dl.y, dl.z) * Mathf.Rad2Deg;
            float pull = Mathf.Clamp(pitchErr / 9f + w.x * 0.01f, -0.6f, 1f);
            // energy: don't pull into a stall
            if (a.AoA > 0.2f) pull = Mathf.Min(pull, 0.12f);
            if (a.Airspeed < a.takeoffSpeed * 1.15f) pull = Mathf.Min(pull, 0.3f);
            float yawErr = Mathf.Atan2(dl.x, dl.z) * Mathf.Rad2Deg;
            ci.move = new Vector2(roll, -pull);
            ci.yaw = Mathf.Clamp(yawErr / 5f, -1f, 1f) * (1f - k);
            float sp = a.Airspeed;
            ci.sprint = sp < speed - 4f || a.Throttle < 0.25f;
            ci.crouch = !ci.sprint && sp > speed + 10f && a.Throttle > 0.3f;
        }
    }
}
