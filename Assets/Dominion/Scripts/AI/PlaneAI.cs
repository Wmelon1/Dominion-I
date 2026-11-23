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
    /// </summary>
    public class PlaneAI : MonoBehaviour
    {
        enum Mode { Parked, Takeoff, Cruise, Dogfight, Attack, Extend, Evade }
        Mode mode = Mode.Cruise;
        AircraftVehicle a;
        Health self, target;
        float simAcc, simDt;
        float thinkT, modeT, waitT, runwayYaw, evadeSign = 1f, errT;
        float cruiseAlt, attackAlt, combatSpeed, cruiseSpeed, gunRange;
        bool gearCalled;
        Vector3 extendDir, aimErr;
        public string State => mode.ToString();
        public Health Target => target;

        public void Init(Health h, bool parked, float takeoffDelay)
        {
            a = GetComponent<AircraftVehicle>();
            self = h;
            mode = parked ? Mode.Parked : Mode.Cruise;
            waitT = takeoffDelay;
            runwayYaw = transform.eulerAngles.y;
            bool jet = a.Jet;
            cruiseAlt = jet ? Random.Range(380f, 520f) : Random.Range(220f, 320f);
            attackAlt = jet ? 520f : 300f;
            cruiseSpeed = jet ? Mathf.Min(a.maxSpeed * 0.75f, 210f) : a.maxSpeed * 0.92f;
            combatSpeed = jet ? Mathf.Min(a.maxSpeed * 0.62f, 175f) : a.maxSpeed * 0.95f;
            gunRange = jet ? 850f : 520f;
            thinkT = Random.Range(0f, 0.3f);
        }

        float Pref(Health h, float dist)
        {
            bool cannon = a.fireInterval < 0.04f;
            bool striker = cannon || a.unitKey == "Aircraft_Kestrel";
            if (h.IsDrone) return 0f;
            if (h.IsAirship) return cannon ? 0.5f : 0.15f;
            if (h.Airborne) return striker ? (dist < 600f ? 1.2f : 0.25f) : 1.6f;
            switch (h.cls)
            {
                case UnitClass.Soldier: return a.Jet ? 0.25f : 0.8f;
                case UnitClass.Mech: return cannon ? 0.8f : 0.2f;
                case UnitClass.Air: return 0.35f;                  // parked on the ground
                default:
                    if (cannon) return h.armor == ArmorClass.Armored ? 0.8f : 1f;
                    return h.armor == ArmorClass.Armored ? 0.05f : h.armor == ArmorClass.Light ? 0.35f : 0.7f;
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
            if (mode != Mode.Extend && mode != Mode.Evade)
            {
                target = AIUtil.PickTarget(self, pos, 2400f, Pref, target, transform, false, out _);
                if (target == null) { if (mode != Mode.Cruise) SetMode(Mode.Cruise); }
                else if (target.Airborne) { if (mode != Mode.Dogfight) SetMode(Mode.Dogfight); }
                else if (mode != Mode.Attack) SetMode(Mode.Attack);
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
                    // head for the enemy side at cruise altitude
                    Vector3 dest = war.EnemyBase(self.team) * 0.6f;
                    if (AIUtil.Flat(dest - pos).magnitude < 300f) dest = new Vector3(-pos.x, 0f, -pos.z * 0.5f);
                    dest.y = WorldGround.Top(dest.x, dest.z) + cruiseAlt;
                    want = (dest - pos).normalized;
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
                    if (modeT > Random.Range(2.2f, 3.5f)) SetMode(target && target.Alive && target.Airborne ? Mode.Dogfight : Mode.Cruise);
                    break;
                }
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
