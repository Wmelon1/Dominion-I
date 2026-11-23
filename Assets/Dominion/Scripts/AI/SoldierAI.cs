using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Infantry combat AI (writes the same ControlInput a player would). Pushes toward its side's objective (where Intel
    /// places the enemy, else the enemy staging area, else the nearest enemy) bound by bound between cover, rides the
    /// transports when they come to pick it up (and assaults where it is dropped), hides behind walls and leans out at
    /// the wall's end to fire
    /// aimed bursts (leading moving targets, tightening its aim the longer it tracks), ducks back when hit,
    /// fights from the open with evasive strafing when there is no cover, falls back when badly wounded, sidesteps
    /// vehicles, holds fire when a friendly is in the line, and (anti-tank riflemen) launches rifle grenades at armour.
    /// </summary>
    [RequireComponent(typeof(SoldierController))]
    public class SoldierAI : MonoBehaviour
    {
        public bool antiTank;
        public float laneX;
        public float skill = 1f;

        enum Mode { Advance, ToCover, Hide, Peek, Engage, Retreat, Board }
        Mode mode = Mode.Advance;
        SoldierController sc;
        Health self, target;
        bool visible, retreating, friendBlock;
        float targetDist = 999f;
        CoverSpot cover;
        Vector3 goal, aimErr, sidestep, separation, lastPos;
        bool hasGoal;
        float thinkT, modeT, burstT, pauseT, strafeT, strafeSign = 1f, noEnemyT, sideT, stuckT, onTargetT, errT, holdFor, peekFor, grenadeWant;
        // transport rides and assault orders
        float simAcc, simDt;
        TransportBay ride;
        float rideT, assaultT;
        Vector3 assault;
        readonly NavPath nav = new NavPath(0.45f, 10f, 5f);
        readonly System.Collections.Generic.List<CoverSpot> near = new System.Collections.Generic.List<CoverSpot>();

        /// <summary>Where to steer for a destination: straight there when close, else the next waypoint of a route around the buildings.</summary>
        Vector3 Nav(Vector3 dest)
        {
            Vector3 d = dest - transform.position;
            d.y = 0f;
            return d.sqrMagnitude > 25f ? nav.Steer(transform.position, dest, 2f) : dest;
        }

        public string State => mode.ToString();
        public Team Team => self ? self.team : Team.None;

        /// <summary>Free to be picked up by a transport: AI-driven, not fighting, not hurt, not already riding.</summary>
        public bool Available => self && self.Alive && sc && !sc.Dead && !sc.Controlled && ride == null && !retreating &&
                                 mode != Mode.Retreat && mode != Mode.Board && noEnemyT > 3f && self.Fraction > 0.4f &&
                                 assaultT <= 0f && isActiveAndEnabled;   // just dropped off: fight first (no taxi loops)

        /// <summary>A transport has a seat for us: run to its rear door.</summary>
        public void BoardTransport(TransportBay bay)
        {
            ReleaseCover();
            ride = bay;
            rideT = 0f;
            bay.Book(this);
            SetMode(Mode.Board);
            hasGoal = false;
            nav.Invalidate();
        }

        /// <summary>Ride called off (timed out, transport gone, or we had to fight).</summary>
        public void CancelRide()
        {
            if (ride) ride.Unbook(this);
            ride = null;
            if (mode == Mode.Board) { SetMode(Mode.Advance); hasGoal = false; }
        }

        /// <summary>Out of the back of a transport: assault 'target' (zero = just carry on).</summary>
        public void Dismounted(Vector3 target)
        {
            ride = null;
            ReleaseCover();
            SetMode(Mode.Advance);
            hasGoal = false;
            noEnemyT = 0f;
            stuckT = 0f;
            lastPos = transform.position;
            nav.Invalidate();
            if (target != Vector3.zero) { assault = target; assaultT = 75f; }
            thinkT = Random.Range(0f, 0.3f);
        }

        /// <summary>Where we are pushing: an assault order from a transport drop, else the side's objective.</summary>
        Vector3 Objective(WarManager war)
        {
            Vector3 pos = transform.position;
            if (assaultT > 0f && AIUtil.Flat(assault - pos).magnitude > 35f) return assault;
            return war.Objective(self.team, pos);
        }

        static Vector3 DirOr(Vector3 d, Vector3 fallback)
        {
            d.y = 0f;
            return d.sqrMagnitude > 1f ? d.normalized : fallback;
        }

        void Awake() => sc = GetComponent<SoldierController>();

        public void Init(Health h, float lane, bool at)
        {
            self = h;
            laneX = lane;
            antiTank = at;
            skill = Random.Range(0.85f, 1.25f);
            thinkT = Random.Range(0f, 0.4f);
            lastPos = transform.position;
        }

        void OnDisable() => ReleaseCover();

        void ReleaseCover()
        {
            if (cover != null && cover.occupant == this) cover.occupant = null;
            cover = null;
        }

        void SetMode(Mode m)
        {
            mode = m;
            modeT = 0f;
        }

        float Pref(Health h, float dist)
        {
            switch (h.cls)
            {
                case UnitClass.Soldier: return 1f;
                case UnitClass.Air: return h.Airborne ? (dist < 160f ? 0.08f : 0f) : 0.3f;
                case UnitClass.Mech: return antiTank ? 0.9f : 0.12f;
                default:
                    if (antiTank) return 1.1f;
                    return h.armor == ArmorClass.Armored ? 0.06f : h.armor == ArmorClass.Light ? 0.25f : 0.5f;
            }
        }

        void Update()
        {
            long perfT0 = Perf.Now;
            float sdt = Time.deltaTime;
            if (self == null || sc == null || sc.Controlled || self.SimTick(ref simAcc, out sdt))
            {
                simDt = sdt;
                UpdateTimed();
            }
            Perf.Add(Perf.SoldierAI, perfT0);
        }

        void UpdateTimed()
        {
            if (self == null || sc.Dead || !self.Alive) { ReleaseCover(); return; }
            if (sc.Controlled)
            {
                sc.aiDriven = false;
                ReleaseCover();
                mode = Mode.Advance;
                hasGoal = false;
                return;
            }
            sc.aiDriven = true;
            var war = WarManager.Instance;
            if (war == null || !war.Fighting)
            {
                sc.input = new ControlInput { lookYaw = transform.eulerAngles.y, aimPoint = transform.position + transform.forward * 50f };
                return;
            }
            float dt = simDt;
            modeT += dt;
            thinkT -= dt;
            if (thinkT <= 0f)
            {
                float iv = Random.Range(0.25f, 0.4f);
                thinkT = iv;
                Think(war, iv);
            }
            Act(war, dt);
        }

        // ------------------------------------------------------------------ decisions
        void Think(WarManager war, float iv)
        {
            Vector3 pos = transform.position;
            Vector3 eye = pos + Vector3.up * 1.6f;
            target = AIUtil.PickTarget(self, eye, 280f, Pref, target, transform, true, out visible);
            targetDist = target ? Vector3.Distance(pos, target.Center) : 999f;
            noEnemyT = target && visible ? 0f : noEnemyT + iv;
            if (target && visible) Intel.Report(self.team, target, true);
            if (assaultT > 0f) assaultT -= iv;
            bool hurtRecently = Time.time - self.LastHitTime < 1.2f;
            Vector3 fwd = war.Forward(self.team);

            friendBlock = false;
            if (target && visible && sc.Muzzle)
            {
                Vector3 d = target.Center - sc.Muzzle.position;
                friendBlock = AIUtil.FriendlyInLine(sc.Muzzle.position, d.normalized, d.magnitude - target.Radius - 1f, self.team, transform);
            }

            // separation from nearby friendlies, and get out of the way of vehicles
            separation = Vector3.zero;
            sideT -= iv;
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (h == self || !h.Alive) continue;
                Vector3 off = AIUtil.Flat(pos - h.Center);
                float d2 = off.sqrMagnitude;
                if (h.cls == UnitClass.Soldier)
                {
                    if (h.team == self.team && d2 < 4f && d2 > 1e-4f) separation += off / d2;
                }
                else if (h.cls != UnitClass.Air && d2 < 20f * 20f)
                {
                    Vector3 v = AIUtil.Flat(h.Velocity);
                    if (v.sqrMagnitude > 4f && Vector3.Dot(v, off) > 0f)
                    {
                        // is the vehicle's path going through us?
                        Vector3 vn = v.normalized;
                        float lateral = Vector3.Cross(vn, off).y;
                        if (Mathf.Abs(lateral) < h.Radius + 3f)
                        {
                            sidestep = Vector3.Cross(Vector3.up, vn) * (lateral >= 0f ? 1f : -1f);   // step off the side we are on
                            sideT = 1.3f;
                        }
                    }
                }
            }

            // stuck against something while trying to move
            if (Vector3.Distance(pos, lastPos) < 0.25f && (mode == Mode.Advance || mode == Mode.ToCover || mode == Mode.Retreat || mode == Mode.Board)) stuckT += iv;
            else stuckT = 0f;
            lastPos = pos;
            if (stuckT > 1.4f)
            {
                stuckT = 0f;
                sidestep = Quaternion.Euler(0f, Random.value < 0.5f ? 90f : -90f, 0f) * (goal - pos).normalized;
                sideT = 1.1f;
                nav.Invalidate();
            }

            if (mode == Mode.Board)
            {
                rideT += iv;
                if (ride == null || ride.Vehicle == null || ride.Vehicle.Destroyed || ride.Unloading || rideT > 32f ||
                    (target && visible && targetDist < 70f))
                    CancelRide();
                else if (AIUtil.Flat(ride.BoardPoint - pos).magnitude < 3.4f && ride.TryBoard(this))
                    return;
                else
                    return;
            }
            if (!retreating && self.Fraction < 0.35f)
            {
                if (ride) CancelRide();
                retreating = true;
                var c = FindCover(war, target ? target.Center : pos + fwd * 100f, 45f, -999f, 3f);
                if (c != null) GoCover(c);
                else { goal = pos - fwd * 35f; hasGoal = true; SetMode(Mode.Retreat); }
                return;
            }

            switch (mode)
            {
                case Mode.Advance:
                    if (target && visible && targetDist < 170f)
                    {
                        var c = FindCover(war, target.Center, 24f, -6f, 14f);
                        if (c != null) GoCover(c);
                        else SetMode(Mode.Engage);
                    }
                    else if (!hasGoal || AIUtil.Flat(goal - pos).magnitude < 2f) PickAdvance(war);
                    break;
                case Mode.ToCover:
                    if (cover == null) { SetMode(Mode.Advance); break; }
                    if (target && visible && !cover.Protects(target.Center) && targetDist < 120f)
                    {
                        var c = FindCover(war, target.Center, 22f, -10f, 10f);
                        if (c != null) GoCover(c); else { ReleaseCover(); SetMode(Mode.Engage); }
                    }
                    else if (AIUtil.Flat(cover.hide - pos).magnitude < 0.9f)
                    {
                        SetMode(Mode.Hide);
                        holdFor = retreating ? Random.Range(3f, 6f) : Random.Range(0.8f, 2.2f) / skill;
                    }
                    break;
                case Mode.Hide:
                    if (cover == null) { SetMode(Mode.Advance); break; }
                    if (target && !cover.Protects(target.Center) && targetDist < 150f)
                    {
                        var c = FindCover(war, target.Center, 22f, -10f, 10f);
                        if (c != null) GoCover(c); else { ReleaseCover(); SetMode(Mode.Engage); }
                    }
                    else if (modeT > holdFor)
                    {
                        if (target && targetDist < 260f && noEnemyT < 8f)
                        {
                            SetMode(Mode.Peek);
                            peekFor = Random.Range(1.6f, 3.2f) * (retreating ? 0.6f : 1f);
                        }
                        else if (!retreating && noEnemyT > 2.5f && (CanAdvance(war) || war.Endgame(self.team))) { ReleaseCover(); PickAdvance(war); }
                    }
                    break;
                case Mode.Peek:
                    if (cover == null) { SetMode(Mode.Advance); break; }
                    if ((hurtRecently && modeT > 0.5f) || modeT > peekFor || (noEnemyT > 2.5f && modeT > 1.5f))
                    {
                        SetMode(Mode.Hide);
                        holdFor = (hurtRecently ? Random.Range(2f, 3.5f) : Random.Range(0.9f, 2f)) / skill;
                    }
                    break;
                case Mode.Engage:
                    if (!target || noEnemyT > 3f) { SetMode(Mode.Advance); hasGoal = false; break; }
                    if (modeT > 1.5f && targetDist < 200f)
                    {
                        var c = FindCover(war, target.Center, hurtRecently ? 26f : 18f, -12f, 8f);
                        if (c != null) GoCover(c);
                    }
                    break;
                case Mode.Retreat:
                    if (AIUtil.Flat(goal - pos).magnitude < 2f)
                    {
                        var c = FindCover(war, target ? target.Center : pos + fwd * 100f, 40f, -999f, 5f);
                        if (c != null) GoCover(c); else SetMode(Mode.Engage);
                    }
                    break;
            }

            // anti-tank grenade on armour in range
            grenadeWant = 0f;
            if (antiTank && target && visible && AIUtil.IsVehicle(target) && targetDist < 170f && sc.GrenadeCooldown <= 0f) grenadeWant = 1f;
        }

        bool CanAdvance(WarManager war)
        {
            if (assaultT > 0f || noEnemyT > 8f) return true;
            float prog = Vector3.Dot(transform.position, war.Forward(self.team));
            return prog < war.FrontLine(self.team) + 70f;
        }

        void PickAdvance(WarManager war)
        {
            Vector3 pos = transform.position;
            Vector3 obj = Objective(war);
            float objDist = AIUtil.Flat(obj - pos).magnitude;
            Vector3 fwd = DirOr(obj - pos, war.Forward(self.team));
            if (war.Endgame(self.team) && !(target && visible))
            {
                // the last enemies are holding out somewhere: go and find them
                var prey = war.NearestEnemy(self.team, pos);
                if (prey)
                {
                    goal = Vector3.MoveTowards(pos, prey.transform.position, 40f);
                    goal.y = 0f;
                    hasGoal = true;
                    SetMode(Mode.Advance);
                    return;
                }
            }
            if (!CanAdvance(war))
            {
                // too far ahead of the line: hold in the nearest cover facing the enemy
                var hold = FindCover(war, pos + fwd * 150f, 25f, -15f, 4f);
                if (hold != null) { GoCover(hold); return; }
                goal = pos;
                hasGoal = true;
                SetMode(Mode.Advance);
                return;
            }
            if (target == null && noEnemyT > 4f)
            {
                // nobody within range: cover the ground quickly in long legs toward the objective
                goal = pos + fwd * Mathf.Min(110f, Mathf.Max(objDist, 20f)) + Vector3.Cross(Vector3.up, fwd) * Random.Range(-12f, 12f);
                goal.y = pos.y;
                hasGoal = true;
                SetMode(Mode.Advance);
                return;
            }
            Vector3 threat = pos + fwd * 160f;
            CoverSpot best = null;
            float bestScore = float.MaxValue;
            war.CoverNear(pos + fwd * 35f, 60f, near);
            foreach (var c in near)
            {
                if (c.occupant != null) continue;
                Vector3 d = c.hide - pos;
                float adv = Vector3.Dot(d, fwd);
                if (adv < 10f || adv > 60f) continue;
                float lane = Mathf.Abs(Vector3.Cross(fwd, AIUtil.Flat(d)).y);     // off the line of advance
                if (lane > 40f) continue;
                if (!c.Protects(threat)) continue;
                float score = Mathf.Abs(adv - 30f) + lane * 0.45f + Random.value * 8f;
                if (score < bestScore) { bestScore = score; best = c; }
            }
            if (best != null) { GoCover(best); return; }
            // no cover ahead: push on toward the enemy (or the objective)
            goal = pos + fwd * 35f;
            if (target) goal = Vector3.MoveTowards(pos, target.Center, 35f);
            goal.y = 0f;
            hasGoal = true;
            SetMode(Mode.Advance);
        }

        CoverSpot FindCover(WarManager war, Vector3 threat, float radius, float minAdv, float maxAdv)
        {
            Vector3 pos = transform.position;
            Vector3 fwd = DirOr(threat - pos, war.Forward(self.team));
            CoverSpot best = null;
            float bestScore = float.MaxValue;
            war.CoverNear(pos, radius, near);
            foreach (var c in near)
            {
                if (c.occupant != null && c.occupant != this) continue;
                Vector3 d = c.hide - pos;
                d.y = 0f;
                float dist = d.magnitude;
                if (dist > radius) continue;
                float adv = Vector3.Dot(d, fwd);
                if (adv < minAdv || adv > maxAdv) continue;
                if (!c.Protects(threat)) continue;
                float score = dist - adv * 0.25f + Random.value * 3f;
                if (score < bestScore) { bestScore = score; best = c; }
            }
            return best;
        }

        void GoCover(CoverSpot c)
        {
            if (cover != c) ReleaseCover();
            cover = c;
            c.occupant = this;
            hasGoal = false;
            SetMode(Mode.ToCover);
        }

        // ------------------------------------------------------------------ per-frame control
        void Act(WarManager war, float dt)
        {
            Vector3 pos = transform.position;
            Vector3 move = Vector3.zero;
            bool sprint = false, aim = false;
            bool tooClose = target && visible && targetDist < 45f;
            switch (mode)
            {
                case Mode.Advance:
                    if (hasGoal) move = AIUtil.Flat(Nav(goal) - pos);
                    if (move.magnitude < 0.6f) move = Vector3.zero;
                    sprint = !(target && visible && targetDist < 200f);
                    aim = !sprint && target && visible;
                    break;
                case Mode.ToCover:
                case Mode.Retreat:
                    move = AIUtil.Flat(Nav(mode == Mode.ToCover && cover != null ? cover.hide : goal) - pos);
                    sprint = !tooClose;
                    aim = tooClose;
                    break;
                case Mode.Board:
                    if (ride != null)
                    {
                        Vector3 bp = ride.BoardPoint;
                        move = AIUtil.Flat(Nav(bp) - pos);
                        if (AIUtil.Flat(bp - pos).magnitude < 1.2f) move = Vector3.zero;
                    }
                    sprint = true;
                    break;
                case Mode.Hide:
                    if (cover != null) { move = AIUtil.Flat(cover.hide - pos); if (move.magnitude < 0.35f) move = Vector3.zero; }
                    break;
                case Mode.Peek:
                    if (cover != null) { move = AIUtil.Flat(cover.peek - pos); if (move.magnitude < 0.3f) move = Vector3.zero; }
                    aim = true;
                    break;
                case Mode.Engage:
                    aim = true;
                    strafeT -= dt;
                    if (strafeT <= 0f) { strafeT = Random.Range(0.9f, 2.2f); strafeSign = Random.value < 0.5f ? -1f : 1f; if (Random.value < 0.25f) strafeSign = 0f; }
                    if (target)
                    {
                        Vector3 to = AIUtil.Flat(target.Center - pos).normalized;
                        move = Vector3.Cross(Vector3.up, to) * strafeSign;
                        if (targetDist > 150f) move += to * 0.7f;          // close to effective range
                    }
                    break;
            }
            if (sideT > 0f)
            {
                move = sidestep;
                sprint = true;
                aim = false;
            }
            if (move.sqrMagnitude > 1e-4f) move = move.normalized;
            if (separation.sqrMagnitude > 1e-4f) move = (move + Vector3.ClampMagnitude(separation, 1f) * 0.6f);
            if (move.sqrMagnitude > 1f) move.Normalize();

            var ci = new ControlInput();
            float yaw = transform.eulerAngles.y;
            if (target && (aim || (visible && targetDist < 220f && !sprint))) yaw = AIUtil.YawTo(pos, target.Center);
            else if (move.sqrMagnitude > 0.01f) yaw = Mathf.Atan2(move.x, move.z) * Mathf.Rad2Deg;
            ci.lookYaw = yaw;
            Vector3 local = Quaternion.Euler(0f, -transform.eulerAngles.y, 0f) * move;
            ci.move = new Vector2(local.x, local.z);
            ci.sprint = sprint && !aim;
            ci.aim = aim && target != null;

            // aiming and burst fire
            if (target && sc.Muzzle)
            {
                errT -= dt;
                bool moving = move.sqrMagnitude > 0.1f;
                if (errT <= 0f)
                {
                    errT = 0.3f;
                    float deg = 1.05f / skill + (moving ? 0.55f : 0f) + (target.Velocity.sqrMagnitude > 9f ? 0.35f : 0f);
                    deg *= Mathf.Lerp(1f, 0.45f, Mathf.Clamp01(onTargetT / 3f));
                    aimErr = AIUtil.AimError(targetDist, deg);
                }
                ci.aimPoint = AIUtil.Lead(sc.Muzzle.position, target, 700f, 0.15f) + aimErr;
                bool canShoot = ci.aim && visible && sc.AimReady && targetDist < 260f && !friendBlock;
                onTargetT = canShoot ? onTargetT + dt : Mathf.Max(0f, onTargetT - dt * 2f);
                if (canShoot)
                {
                    if (burstT > 0f)
                    {
                        ci.fire = true;
                        burstT -= dt;
                        if (burstT <= 0f) pauseT = Random.Range(0.2f, 0.65f);
                    }
                    else
                    {
                        pauseT -= dt;
                        if (pauseT <= 0f) burstT = targetDist < 60f ? Random.Range(0.5f, 1.2f) : Random.Range(0.25f, 0.7f);
                    }
                    if (grenadeWant > 0f && AIUtil.IsVehicle(target))
                    {
                        ci.aimPoint = target.Center;
                        ci.action2Down = true;
                        ci.fire = false;
                        grenadeWant = 0f;
                    }
                }
            }
            else ci.aimPoint = pos + Vector3.up * 1.4f + transform.forward * 50f;
            sc.input = ci;
        }
    }
}
