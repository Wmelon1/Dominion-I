using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Crew AI for tanks and transports (drives through the same ControlInput as the player).
    /// Tank: pushes toward its side's objective (Intel hotspots, else the enemy staging area, else the nearest enemy),
    /// closes to its gun's sweet spot and holds there hull-on to the enemy, shooting and scooting sideways every few
    /// shots, backing off when rushed. Scout: fast flanker. Artillery: follows the army forward and drops ballistic
    /// shells on anything its side can see, out to ~1.1 km. Anti-air: shadows the armour and hunts aircraft with
    /// proximity-fuzed flak. Transports (APC, MRAP, truck, with a TransportBay): gather idle infantry, drive them to
    /// where the enemy is known to be and unload them 150 m short with an assault order, then go back for more; on
    /// the way they launch repair drones at damaged armour and mechs. The armed ones shoot while they drive.
    /// All of them lead their shots, wait for the gun to be on target, hold fire across friendlies, steer around
    /// obstacles, back out when stuck and right themselves after a rollover.
    /// </summary>
    public class GroundAI : MonoBehaviour
    {
        public enum Role { Tank, Scout, Artillery, AntiAir, Transport, APC }
        public Role role;
        public float laneX;

        Vehicle v;
        TrackedVehicle tracked;
        Health self, target;
        bool visible, armed, friendBlock;
        float tDist = 999f;
        Vector3 goal, aimErr, home, scoot;
        float thinkT, scootT, stuckT, reverseT, reverseSteer, flipT, errT, avoidT, avoidSteer, avoidThrottle = 1f;
        float range, holdMin, holdMax, tolDeg, errDeg;
        NavPath nav;
        float simAcc, simDt;
        // transports
        enum Ferry { Gather, Load, Drive, Unload }
        TransportBay bay;
        Ferry ferry;
        float ferryT, gatherCd, dropT, relocateT;
        Vector3 drop, dropTarget;

        public string State { get; private set; } = "";
        /// <summary>Rounds fired and the last aiming error (deg), for the auto-test log.</summary>
        public int Shots;
        /// <summary>Times the driver had to back out of a jam, and metres driven (auto-test stats).</summary>
        public int Stucks;
        public float Odo;
        Vector3 odoLast;
        public float LastOff;
        public Health Target => target;

        public void Init(Health h, Role r, float lane)
        {
            v = GetComponent<Vehicle>();
            tracked = v as TrackedVehicle;
            self = h;
            role = r;
            laneX = lane;
            home = transform.position;
            armed = v.GetAim(out _, out _);
            bay = GetComponent<TransportBay>();
            float radius = Mathf.Clamp(v.localBounds.extents.x + 0.25f, 1.4f, 2.4f);
            nav = new NavPath(radius, 20f, 6f, true);
            thinkT = Random.Range(0f, 0.5f);
            switch (r)
            {
                case Role.Tank: range = 700f; holdMin = 110f; holdMax = 420f; tolDeg = 0.8f; errDeg = 0.3f; break;
                case Role.Scout: range = 480f; holdMin = 70f; holdMax = 260f; tolDeg = 2.5f; errDeg = 0.55f; break;
                case Role.Artillery: range = 1150f; holdMin = 140f; holdMax = 1150f; tolDeg = 1.2f; errDeg = 0f; break;
                case Role.AntiAir: range = 1150f; holdMin = 60f; holdMax = 500f; tolDeg = 3.5f; errDeg = 0.45f; break;
                case Role.APC: range = 430f; holdMin = 50f; holdMax = 300f; tolDeg = 3.5f; errDeg = 0.6f; break;
                default: range = 0f; holdMin = 0f; holdMax = 0f; tolDeg = 5f; errDeg = 1f; break;
            }
        }

        float Pref(Health h, float dist)
        {
            bool air = h.Airborne;
            switch (role)
            {
                case Role.AntiAir:
                    if (h.IsDrone) return dist < 400f ? 0.3f : 0f;
                    if (h.IsAirship) return dist < 1100f ? 0.5f : 0f;
                    if (air) return 1.4f;
                    return dist < 500f ? (h.cls == UnitClass.Soldier ? 0.35f : 0.3f) : 0f;
                case Role.Artillery:
                    if (air) return 0f;
                    return dist < holdMin ? 0f : h.cls == UnitClass.Soldier ? 0.7f : 1f;
                case Role.Tank:
                    if (air) return 0f;
                    return h.cls == UnitClass.Mech ? 0.8f : h.cls == UnitClass.Ground ? (h.armor == ArmorClass.Armored ? 1f : 0.85f) : 0.3f;
                case Role.Scout:
                    if (air) return dist < 350f ? 0.25f : 0f;
                    return h.cls == UnitClass.Soldier ? 0.9f : h.armor == ArmorClass.Armored ? 0.35f : 1f;
                case Role.APC:
                    if (air) return dist < 300f ? 0.2f : 0f;
                    return h.cls == UnitClass.Soldier ? 1f : h.armor == ArmorClass.Soft ? 0.7f : 0.15f;
            }
            return 0f;
        }

        void Update()
        {
            long perfT0 = Perf.Now;
            float sdt = Time.deltaTime;
            if (self == null || v == null || v.PlayerDriven || self.SimTick(ref simAcc, out sdt))
            {
                simDt = sdt;
                UpdateTimed();
            }
            Perf.Add(Perf.GroundAI, perfT0);
        }

        void UpdateTimed()
        {
            if (v == null || self == null || v.Destroyed || !self.Alive) return;
            if (v.PlayerDriven)
            {
                // the player took the wheel: riders hop out at the first stop and carry on by themselves
                if (bay != null && bay.aboard.Count > 0 && !bay.Unloading && bay.Stopped) bay.Unload(Vector3.zero);
                ferry = Ferry.Gather;
                return;
            }
            var war = WarManager.Instance;
            if (war == null || !war.Fighting) return;
            if (!v.Occupied) v.OnEnter();
            float dt = simDt;
            Vector3 op = transform.position;
            if (odoLast != Vector3.zero) Odo += AIUtil.Flat(op - odoLast).magnitude;
            odoLast = op;
            thinkT -= dt;
            if (thinkT <= 0f)
            {
                float iv = Random.Range(0.3f, 0.45f);
                thinkT = iv;
                Think(war, iv);
            }
            avoidT -= dt;
            if (avoidT <= 0f)
            {
                avoidT = 0.12f;
                Avoidance();
            }
            Drive(dt);
            Gun(dt);
        }

        // ------------------------------------------------------------------ decisions
        void Think(WarManager war, float iv)
        {
            Vector3 pos = transform.position;
            Vector3 fwd = war.Forward(self.team);
            Vector3 eye = transform.TransformPoint(v.localBounds.center + Vector3.up * v.localBounds.extents.y);
            if (armed)
            {
                bool needSight = role != Role.Artillery;
                target = AIUtil.PickTarget(self, eye, range, Pref, target, transform, needSight, out visible);
                // artillery fires on anything its side can see
                if (role == Role.Artillery && target && !war.Spotted(target, self.team)) target = null;
                if (target && visible && role != Role.Artillery) Intel.Report(self.team, target, true);
            }
            tDist = target ? Vector3.Distance(pos, target.Center) : 999f;
            friendBlock = false;
            if (target && visible && armed && role != Role.Artillery && v.GetAim(out Vector3 o, out _))
            {
                Vector3 d = target.Center - o;
                friendBlock = AIUtil.FriendlyInLine(o, d.normalized, d.magnitude - target.Radius - 2f, self.team, transform);
            }

            // flipped over: the crew rights it after a few seconds
            flipT = transform.up.y < 0.45f ? flipT + iv : 0f;
            if (flipT > 3f) { flipT = 0f; v.ResetUpright(); }

            float speed = Mathf.Abs(v.ForwardSpeed);
            scootT -= iv;
            if (bay != null && (role == Role.APC || role == Role.Transport))
            {
                TransportThink(war, pos, iv);
                goal.y = 0f;
                StuckCheck(pos, speed, iv);
                return;
            }
            switch (role)
            {
                case Role.Tank:
                case Role.Scout:
                case Role.APC:
                {
                    if (role == Role.APC && (!target || !visible))
                    {
                        // keep with the infantry line, a little behind it
                        Vector3 sc = war.SoldierCentroid(self.team, laneX);
                        goal = sc - fwd * 22f;
                        State = "support";
                        break;
                    }
                    if (target && visible)
                    {
                        Vector3 to = AIUtil.Flat(target.Center - pos);
                        Vector3 dir = to.normalized;
                        if (tDist > holdMax) { goal = pos + dir * (tDist - holdMax * 0.85f); State = "close in"; }
                        else if (tDist < holdMin) { goal = pos - dir * 35f; State = "back off"; }
                        else
                        {
                            // shoot and scoot: hop sideways now and then so return fire misses
                            if (scootT <= 0f)
                            {
                                scootT = Random.Range(9f, 16f);
                                scoot = pos + Vector3.Cross(Vector3.up, dir) * (Random.value < 0.5f ? -1f : 1f) * Random.Range(15f, 28f);
                            }
                            goal = scoot;
                            State = "engage";
                        }
                    }
                    else if (target) { goal = Vector3.MoveTowards(pos, target.Center, 60f); State = "hunt"; }
                    else if (war.Endgame(self.team) && war.NearestEnemy(self.team, pos) is Health prey)
                    {
                        goal = Vector3.MoveTowards(pos, prey.transform.position, 60f);
                        State = "mop up";
                    }
                    else
                    {
                        // nothing in sight: push on toward the objective (scouts swing out to a flank on the way)
                        Vector3 obj = war.Objective(self.team, pos);
                        Vector3 dir = AIUtil.Flat(obj - pos);
                        float L = dir.magnitude;
                        if (role == Role.Scout && L > 250f) obj += Vector3.Cross(Vector3.up, dir / L) * Mathf.Sign(laneX == 0f ? 1f : laneX) * 120f;
                        goal = Vector3.MoveTowards(pos, obj, 160f);
                        State = "advance";
                    }
                    break;
                }
                case Role.Artillery:
                    // keep the guns within reach of the fight: move the firing area up behind the army
                    relocateT -= iv;
                    if (relocateT <= 0f)
                    {
                        relocateT = 25f;
                        Vector3 obj = war.Objective(self.team, pos);
                        float d = AIUtil.Flat(obj - home).magnitude;
                        if (d > 850f)
                        {
                            home = Vector3.MoveTowards(home, obj, d - 700f);
                            home.y = 0f;
                            scootT = 0f;
                        }
                    }
                    if (scootT <= 0f)
                    {
                        scootT = Random.Range(45f, 70f);
                        scoot = home + Vector3.right * Random.Range(-35f, 35f) + fwd * Random.Range(-10f, 25f);
                    }
                    goal = scoot;
                    State = target ? "fire mission" : "standby";
                    break;
                case Role.AntiAir:
                {
                    Vector3 armor = war.ArmorCentroid(self.team);
                    goal = armor - fwd * 70f + Vector3.right * (laneX * 0.3f);
                    if (target && visible && !target.Airborne && tDist < 200f) goal = pos - AIUtil.Flat(target.Center - pos).normalized * 30f;
                    State = target && target.Airborne ? "tracking air" : "escort";
                    break;
                }
                case Role.Transport:
                {
                    Vector3 sc = war.SoldierCentroid(self.team, laneX);
                    goal = sc - fwd * 60f;
                    if (self.Fraction < 0.5f) goal = home;
                    State = "resupply";
                    break;
                }
            }
            goal.y = 0f;
            StuckCheck(pos, speed, iv);
        }

        void StuckCheck(Vector3 pos, float speed, float iv)
        {
            // stuck: pushing but not moving -> reverse out with the wheel turned
            bool pushing = Mathf.Abs(v.input.move.y) > 0.3f;
            stuckT = pushing && speed < 0.5f && reverseT <= 0f ? stuckT + iv : 0f;
            if (stuckT > 2.2f)
            {
                stuckT = 0f;
                reverseT = Random.Range(1.6f, 2.4f);
                Stucks++;
                // back out swinging the nose toward the open side (the feelers know where the room is)
                reverseSteer = Mathf.Abs(avoidSteer) > 0.05f ? -Mathf.Sign(avoidSteer) : (Random.value < 0.5f ? -1f : 1f);
                nav.Invalidate();
            }
        }

        // ------------------------------------------------------------------ transports
        /// <summary>Gather riders -> load -> drive to the drop point -> unload -> again; drones out to damaged armour.</summary>
        void TransportThink(WarManager war, Vector3 pos, float iv)
        {
            ferryT += iv;
            // repair drones: one at a time to the most valuable damaged strong unit within reach
            if (bay.CanLaunch)
            {
                var patient = DroneUnit.PickPatient(self.team, pos, 700f, null, 0.8f);
                if (patient) bay.LaunchDrone(patient);
            }
            switch (ferry)
            {
                case Ferry.Gather:
                {
                    if (bay.aboard.Count >= bay.capacity) { StartDrive(war, pos); break; }
                    gatherCd -= iv;
                    if (bay.booked.Count == 0 && gatherCd <= 0f)
                    {
                        gatherCd = 4f;
                        war.FindRiders(self.team, pos, bay, out _);
                    }
                    if (bay.booked.Count == 0)
                    {
                        if (bay.aboard.Count > 0 && ferryT > 10f) { StartDrive(war, pos); break; }
                        // nobody to fetch: trail the army (armed ones fight from there), drones ready
                        Vector3 obj = war.Objective(self.team, pos);
                        Vector3 sc = war.SoldierCentroid(self.team, laneX);
                        Vector3 back = AIUtil.Flat(obj - sc);
                        goal = sc - (back.sqrMagnitude > 1f ? back.normalized : war.Forward(self.team)) * 70f;
                        State = "standby";
                        break;
                    }
                    Vector3 rc = Vector3.zero;
                    int n = 0;
                    foreach (var s0 in bay.booked) if (s0) { rc += s0.transform.position; n++; }
                    rc = n > 0 ? rc / n : pos;
                    goal = rc;
                    State = "pickup";
                    if (AIUtil.Flat(rc - pos).magnitude < 30f || ferryT > 30f) { ferry = Ferry.Load; ferryT = 0f; bay.SetDoor(true); }
                    break;
                }
                case Ferry.Load:
                    goal = pos;
                    State = "loading";
                    bay.SetDoor(true);
                    if (bay.booked.Count == 0 || ferryT > 22f || bay.aboard.Count >= bay.capacity)
                    {
                        foreach (var s0 in bay.booked.ToArray()) if (s0) s0.CancelRide();
                        if (bay.aboard.Count > 0) StartDrive(war, pos);
                        else { ferry = Ferry.Gather; ferryT = 0f; gatherCd = 3f; }
                    }
                    break;
                case Ferry.Drive:
                {
                    dropT -= iv;
                    if (dropT <= 0f) PlanDrop(war, pos);
                    goal = drop;
                    State = "ferry";
                    float dd = AIUtil.Flat(drop - pos).magnitude;
                    bool underFire = Time.time - self.LastHitTime < 2f && AIUtil.Flat(dropTarget - pos).magnitude < 420f;
                    // any known enemy close by (not just the one we were heading for): everybody out here
                    bool contact = Intel.Nearest(self.team, pos, out var near) && AIUtil.Flat(near.pos - pos).magnitude < 230f;
                    if (dd < 24f || self.Fraction < 0.4f || underFire || contact || ferryT > 60f)
                    {
                        ferry = Ferry.Unload;
                        ferryT = 0f;
                        bay.Unload(dropTarget);
                    }
                    break;
                }
                case Ferry.Unload:
                    goal = pos;
                    State = "unloading";
                    if (!bay.Unloading && bay.aboard.Count == 0) { ferry = Ferry.Gather; ferryT = 0f; gatherCd = 1f; }
                    break;
            }
        }

        void StartDrive(WarManager war, Vector3 pos)
        {
            bay.SetDoor(false);
            ferry = Ferry.Drive;
            ferryT = 0f;
            PlanDrop(war, pos);
        }

        /// <summary>Drop riders ~150 m short of the best place our side knows the enemy to be (re-planned as it changes).</summary>
        void PlanDrop(WarManager war, Vector3 pos)
        {
            dropT = 2.5f;
            // the nearest real fight (a few units at least), not the biggest one across the city
            dropTarget = Intel.Best(self.team, pos, out var hot, 3f, 350f) ? hot.pos : war.Objective(self.team, pos);
            dropTarget.y = 0f;
            Vector3 d = AIUtil.Flat(dropTarget - pos);
            float L = d.magnitude;
            drop = L > 170f ? dropTarget - d / L * 150f : pos;
            if (CityNav.Active && L > 170f)
            {
                var q = CityNav.NearestFree(new Vector2(drop.x, drop.z), 3f, true, 40f);
                drop = new Vector3(q.x, 0f, q.y);
            }
            drop.y = 0f;
        }

        /// <summary>Three feelers ahead of the hull; steer toward the clearer side and slow down for obstacles.</summary>
        void Avoidance()
        {
            avoidSteer = 0f;
            avoidThrottle = 1f;
            float speed = Mathf.Abs(v.ForwardSpeed);
            if (speed < 0.5f && Mathf.Abs(v.input.move.y) < 0.1f) return;
            float sign = v.ForwardSpeed < -0.5f ? -1f : 1f;
            var b = v.localBounds;
            Vector3 front = transform.TransformPoint(new Vector3(b.center.x, 1.1f, sign > 0f ? b.max.z + 0.3f : b.min.z - 0.3f));
            Vector3 f = transform.forward * sign;
            float L = 7f + speed * 1.6f;
            float c = Feeler(front, f, L);
            float l = Feeler(front - transform.right * b.extents.x * 0.8f, Quaternion.AngleAxis(-25f, Vector3.up) * f, L * 0.75f);
            float r = Feeler(front + transform.right * b.extents.x * 0.8f, Quaternion.AngleAxis(25f, Vector3.up) * f, L * 0.75f);
            if (c < L || l < L * 0.75f || r < L * 0.75f)
            {
                float urgency = 1f - Mathf.Min(c / L, Mathf.Min(l, r) / (L * 0.75f));
                avoidSteer = (l < r ? 1f : -1f) * Mathf.Clamp01(urgency * 1.8f) * sign;
                avoidThrottle = Mathf.Clamp(c / L, 0.35f, 1f);
            }
        }

        float Feeler(Vector3 from, Vector3 dir, float len)
        {
            if (!AIUtil.Cast(from, dir, len, transform, out RaycastHit h)) return len;
            if (h.normal.y > 0.75f) return len;                              // ground / ramps
            if (h.collider.GetComponentInParent<CarProp>() != null) return len;  // parked cars: drive over them
            var hh = Health.Of(h.collider);
            if (hh && hh.cls == UnitClass.Soldier && hh.team != self.team) return len;   // enemy infantry: run them down
            return h.distance;
        }

        // ------------------------------------------------------------------ driving
        void Drive(float dt)
        {
            Vector3 pos = transform.position;
            float dist = AIUtil.Flat(goal - pos).magnitude;
            // follow a route along the streets (aiming a little way along it); straight at the goal once it's close
            float spd = Mathf.Abs(v.ForwardSpeed);
            Vector3 steerPt = dist > 12f ? nav.Steer(pos, goal, 5f + spd * 0.6f) : goal;
            float turnAhead = dist > 12f ? nav.TurnAhead(pos, 10f + spd * 1.6f) : 0f;
            Vector3 to = AIUtil.Flat(steerPt - pos);
            Vector3 local = transform.InverseTransformDirection(to);
            float ang = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
            float throttle, steer;
            bool brake = false;
            float speed = v.ForwardSpeed;
            float arrive = role == Role.Artillery ? 10f : 7f;
            if (reverseT > 0f)
            {
                reverseT -= dt;
                throttle = -0.8f;
                steer = reverseSteer;
            }
            else if (dist < arrive)
            {
                throttle = 0f;
                steer = 0f;
                brake = Mathf.Abs(speed) > 0.5f;
                // parked tanks swing the hull to face the threat (front armour)
                if (tracked && target && visible && role != Role.AntiAir)
                {
                    float ta = AIUtil.AngleTo(transform, target.Center);
                    if (Mathf.Abs(ta) > 30f) steer = Mathf.Sign(ta) * 0.7f;
                }
            }
            else if (Mathf.Abs(ang) > 125f && dist < 45f)
            {
                // goal close behind us: reverse onto it (keeps the front toward the enemy when backing off)
                throttle = -0.75f;
                steer = Mathf.Sign(ang) * Mathf.Clamp01((180f - Mathf.Abs(ang)) / 30f);
            }
            else if (tracked)
            {
                if (Mathf.Abs(ang) > 55f) { throttle = 0.15f; steer = Mathf.Sign(ang); }      // pivot
                else { throttle = Mathf.Clamp01(dist / 25f + 0.35f); steer = Mathf.Clamp(ang / 30f, -1f, 1f); }
            }
            else
            {
                steer = Mathf.Clamp(ang / 20f, -1f, 1f);
                throttle = (Mathf.Abs(ang) > 70f ? 0.45f : 1f) * Mathf.Clamp01(dist / 30f + 0.35f);
            }
            if (reverseT <= 0f)
            {
                steer = Mathf.Clamp(steer + avoidSteer, -1f, 1f);
                if (throttle > 0f) throttle *= avoidThrottle;
                // brake for sharp corners on the route ahead
                if (throttle > 0f && turnAhead > 35f) throttle *= Mathf.Lerp(1f, 0.4f, Mathf.Clamp01((turnAhead - 35f) / 70f));
            }
            v.input.move = new Vector2(steer, throttle);
            v.input.jump = brake;
            v.input.sprint = false;
        }

        // ------------------------------------------------------------------ gunnery
        void Gun(float dt)
        {
            if (!armed)
            {
                v.input.fire = false;
                return;
            }
            bool hasAim = v.GetAim(out Vector3 o, out Vector3 barrel);
            if (!target || !target.Alive || !hasAim)
            {
                v.input.fire = false;
                v.input.aimPoint = transform.position + transform.forward * 120f + Vector3.up * 2.5f;
                return;
            }
            errT -= dt;
            Vector3 aim;
            if (role == Role.Artillery)
            {
                // ballistic: lead by the shell's flight time; spread grows with range
                float speedS = v.ProjectileSpeed;
                float e = Vehicle.BallisticElevation(o, target.Center, speedS) * Mathf.Deg2Rad;
                float t = AIUtil.Flat(target.Center - o).magnitude / Mathf.Max(1f, speedS * Mathf.Cos(e));
                if (errT <= 0f) { errT = 1.5f; aimErr = AIUtil.Flat(Random.insideUnitSphere) * (5f + tDist * 0.012f); }
                aim = target.Center + AIUtil.Flat(target.Velocity) * t + aimErr;
                aim.y = target.transform.position.y;
                v.input.aimPoint = aim;
                // aligned when the barrel points the right way in azimuth and its elevation matches the solution
                float az = Vector3.Angle(AIUtil.Flat(barrel), AIUtil.Flat(aim - o));
                float want = Vehicle.BallisticElevation(o, aim, speedS);
                float have = Mathf.Asin(Mathf.Clamp(barrel.y, -1f, 1f)) * Mathf.Rad2Deg;
                v.input.fire = az < tolDeg && Mathf.Abs(want - have) < 1.2f && tDist > holdMin;
                return;
            }
            if (errT <= 0f)
            {
                errT = 0.45f;
                float deg = errDeg + (Mathf.Abs(v.ForwardSpeed) > 2f ? errDeg * 0.8f : 0f);
                aimErr = AIUtil.AimError(tDist, deg);
            }
            aim = AIUtil.Lead(o, target, v.ProjectileSpeed, v.ProjectileGravity) + aimErr;
            v.input.aimPoint = aim;
            float off = Vector3.Angle(barrel, aim - o);
            LastOff = off;
            float tol = tolDeg + Mathf.Atan2(target.Radius, Mathf.Max(tDist, 1f)) * Mathf.Rad2Deg;
            v.input.fire = visible && tDist < range && off < tol && !friendBlock;
            if (v.input.fire && v.Reloaded) Shots++;
        }
    }
}
