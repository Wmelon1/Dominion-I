using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Mech pilot AI. Walks the line toward the enemy, then alternates braced firing (turning the hull so the torso can
    /// track, leading the target) with repositioning walks. Thunderhead salvoes homing missiles at armour; anything that
    /// gets close is met with the melee strike (on the move) and a crowd around the feet gets stomped. Halberd jet-leaps
    /// toward distant targets, strafing them in the dive, and jets out of trouble when badly damaged. Aegis and
    /// Thunderhead thruster-dash down long straight stretches of road (and away when badly hurt). With nothing in sight
    /// every mech pushes on toward its side's objective (Intel hotspots, enemy staging area, nearest enemy).
    /// </summary>
    public class MechAI : MonoBehaviour
    {
        MechVehicle m;
        Health self, target;
        bool visible, firePhase, flyingAI, friendBlock;
        float tDist = 999f, thinkT, phaseT, settleT, flyT, flyCd = 12f, meleeCd, stuckT, errT, avoid, dashCd = 4f, evadeT;
        bool dashing;
        Vector3 evadeGoal;
        int closeCount;
        Health closest;
        Vector3 flyGoal, aimErr, lastPos, walkGoal;
        readonly NavPath nav = new NavPath(2.6f, 25f, 6f, true);
        public string State { get; private set; } = "";
        public Health Target => target;

        public void Init(Health h)
        {
            m = GetComponent<MechVehicle>();
            self = h;
            thinkT = Random.Range(0f, 0.3f);
            lastPos = transform.position;
        }

        float Pref(Health h, float dist)
        {
            bool gatling = m.fireInterval < 0.2f;
            if (h.IsDrone) return gatling && dist < 250f ? 0.25f : 0f;
            if (h.IsAirship) return dist < 700f ? 0.5f : 0f;
            if (h.Airborne) return gatling ? 0.6f : dist < 400f ? 0.25f : 0f;
            switch (h.cls)
            {
                case UnitClass.Soldier: return gatling ? 1f : 0.45f;
                case UnitClass.Mech: return 1.3f;
                case UnitClass.Air: return 0.2f;
                default: return h.armor == ArmorClass.Armored ? 1f : 0.85f;
            }
        }

        void Update()
        {
            long perfT0 = Perf.Now;
            UpdateTimed();
            Perf.Add(Perf.MechAI, perfT0);
        }

        void UpdateTimed()
        {
            if (m == null || self == null || m.Destroyed || !self.Alive) return;
            if (m.PlayerDriven) { flyingAI = false; return; }
            var war = WarManager.Instance;
            if (war == null || !war.Fighting) return;
            if (!m.Occupied) m.OnEnter();
            float dt = Time.deltaTime;
            meleeCd -= dt;
            flyCd -= dt;
            dashCd -= dt;
            evadeT -= dt;
            thinkT -= dt;
            if (thinkT <= 0f)
            {
                thinkT = 0.3f;
                Think(war, 0.3f);
            }
            Act(war, dt);
        }

        void Think(WarManager war, float iv)
        {
            Vector3 pos = transform.position;
            Vector3 eye = transform.TransformPoint(0f, 7.5f, 0f);
            target = AIUtil.PickTarget(self, eye, 520f, Pref, target, transform, true, out visible);
            tDist = target ? Vector3.Distance(pos, target.Center) : 999f;
            if (target && visible) Intel.Report(self.team, target, true);
            // badly hurt and under fire: dash out of it (mechs without jets)
            if (m.CanDash && evadeT <= 0f && self.Fraction < 0.3f && Time.time - self.LastHitTime < 3f && m.JetFuel > m.jetFuelMax * 0.5f)
            {
                Vector3 away = AIUtil.Flat(pos - self.LastHitFrom);
                away = away.sqrMagnitude > 1f ? away.normalized : -war.Forward(self.team);
                evadeGoal = pos + away * 170f;
                evadeT = 6f;
                State = "dash out";
            }
            friendBlock = false;
            if (target && visible && m.GetAim(out Vector3 o, out _))
            {
                Vector3 d = target.Center - o;
                friendBlock = AIUtil.FriendlyInLine(o, d.normalized, d.magnitude - target.Radius - 2f, self.team, transform);
            }
            // who is close enough for melee?
            closeCount = 0;
            closest = null;
            float best = 999f;
            var all = Health.All;
            for (int i = 0; i < all.Count; i++)
            {
                var h = all[i];
                if (!h.Alive || !Health.Enemies(h.team, self.team) || h.Airborne) continue;
                float d = AIUtil.Flat(h.Center - pos).magnitude - h.Radius;
                if (d < 13f) closeCount += h.cls == UnitClass.Soldier ? 1 : 3;
                if (d < best) { best = d; closest = h; }
            }
            if (closest && best > 12f) closest = null;

            // stuck against a wall or wreck while walking
            float moved = Vector3.Distance(pos, lastPos);
            lastPos = pos;
            stuckT = !firePhase && !flyingAI && moved < 0.3f ? stuckT + iv : 0f;
            if (stuckT > 2f) { stuckT = 0f; avoid = Random.value < 0.5f ? -1f : 1f; }
            else if (avoid != 0f && moved > 1f) avoid *= 0.5f;
            if (Mathf.Abs(avoid) < 0.1f) avoid = 0f;

            // Halberd: jet leap toward a distant target, or out of trouble
            if (m.hasJets && !flyingAI && flyCd <= 0f && m.Grounded && m.JetFuel > m.jetFuelMax * 0.75f)
            {
                Vector3 fwd = war.Forward(self.team);
                if (self.Fraction < 0.3f && Time.time - self.LastHitTime < 3f)
                {
                    flyGoal = pos - fwd * 160f + Vector3.right * Random.Range(-60f, 60f);
                    StartFlight("evade");
                }
                else if (target && tDist > 230f && tDist < 520f)
                {
                    Vector3 dir = AIUtil.Flat(target.Center - pos).normalized;
                    Vector3 lz = target.Center - dir * 45f + Vector3.Cross(Vector3.up, dir) * Random.Range(-25f, 25f);
                    if (ArmorNear(lz, 220f) <= 2)
                    {
                        flyGoal = lz;
                        StartFlight("jet assault");
                    }
                    else flyCd = 6f;
                }
            }
        }

        int ArmorNear(Vector3 p, float r)
        {
            int n = 0;
            foreach (var h in Health.All)
                if (h.Alive && Health.Enemies(h.team, self.team) && (h.cls == UnitClass.Mech || h.armor == ArmorClass.Armored || h.armor == ArmorClass.Light) &&
                    AIUtil.Flat(h.Center - p).sqrMagnitude < r * r) n++;
            return n;
        }

        void StartFlight(string why)
        {
            flyingAI = true;
            flyT = 0f;
            firePhase = false;
            State = why;
        }

        void Act(WarManager war, float dt)
        {
            Vector3 pos = transform.position;
            Vector3 fwd = war.Forward(self.team);
            var ci = new ControlInput();
            ci.aimPoint = transform.TransformPoint(0f, 5f, 80f);

            if (flyingAI)
            {
                flyT += dt;
                Vector3 to = flyGoal - pos;
                float flat = AIUtil.Flat(to).magnitude;
                Vector3 dest = flyGoal + Vector3.up * (flat > 140f ? 55f : -10f);
                Vector3 d = dest - pos;
                ci.jump = true;
                ci.sprint = flat > 100f;
                ci.lookYaw = Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
                ci.lookPitch = Mathf.Clamp(-Mathf.Atan2(d.y, Mathf.Max(AIUtil.Flat(d).magnitude, 1f)) * Mathf.Rad2Deg, -40f, 60f);
                if (target && visible)
                {
                    ci.aimPoint = AIUtil.Lead(pos, target, m.ProjectileSpeed, 0.15f);
                    ci.fire = Vector3.Angle(transform.up, ci.aimPoint - pos) < 50f;
                }
                if (flyT > 8f || flat < 22f || m.JetFuel < 1f || (flyT > 1.2f && m.Grounded))
                {
                    flyingAI = false;
                    flyCd = Random.Range(18f, 30f);
                    ci.jump = false;
                }
                m.input = ci;
                return;
            }

            if (evadeT > 0f)
            {
                Walk(ref ci, evadeGoal, true);
                m.input = ci;
                return;
            }

            // melee first: anything at arm's length gets hit, a crowd gets stomped
            if (!m.Attacking && meleeCd <= 0f && closest)
            {
                float ang = AIUtil.AngleTo(transform, closest.Center);
                float d = AIUtil.Flat(closest.Center - pos).magnitude - closest.Radius;
                if (closeCount >= 3 && d < 10f) { ci.action2Down = true; meleeCd = 2.4f; State = "stomp"; }
                else if (d < m.strikeReach + 2f && Mathf.Abs(ang) < 40f) { ci.action1Down = true; meleeCd = 1.5f; State = "strike"; }
            }
            if (m.Attacking)
            {
                // keep walking through a strike; turn toward whoever is closest
                if (closest) ci.move.x = Mathf.Clamp(AIUtil.AngleTo(transform, closest.Center) / 25f, -1f, 1f);
                ci.move.y = closest && AIUtil.Flat(closest.Center - pos).magnitude > 5f ? 0.7f : 0f;
                m.input = ci;
                return;
            }
            if (closest)
            {
                // close quarters: walk at them, turning, ready to strike
                float ang = AIUtil.AngleTo(transform, closest.Center);
                ci.move = new Vector2(Mathf.Clamp(ang / 20f, -1f, 1f), Mathf.Abs(ang) < 50f ? 0.8f : 0.2f);
                State = "melee range";
                m.input = ci;
                return;
            }

            if (target)
            {
                if (firePhase)
                {
                    float ang = AIUtil.AngleTo(transform, target.Center);
                    ci.aim = true;
                    ci.move.x = Mathf.Abs(ang) > 12f ? Mathf.Clamp(ang / 25f, -1f, 1f) : 0f;
                    if ((errT -= dt) <= 0f) { errT = 0.5f; aimErr = AIUtil.AimError(tDist, 0.35f); }
                    if (m.GetAim(out Vector3 o, out _)) ci.aimPoint = AIUtil.Lead(o, target, m.ProjectileSpeed, 0.15f) + aimErr;
                    settleT += dt;
                    ci.fire = settleT > 0.8f && Mathf.Abs(ang) < 38f && visible && !friendBlock && tDist < 520f;
                    if (m.hasPods && AIUtil.IsVehicle(target) && tDist < 330f && settleT > 1f && visible)
                    {
                        m.lockTarget = target;
                        ci.special = true;
                    }
                    phaseT -= dt;
                    if (phaseT <= 0f || (!visible && settleT > 2f))
                    {
                        firePhase = false;
                        phaseT = Random.Range(2.5f, 4.5f);
                        settleT = 0f;
                        Vector3 dir = AIUtil.Flat(target.Center - pos).normalized;
                        float want = Mathf.Clamp(tDist, 140f, 260f);
                        walkGoal = target.Center - dir * want + Vector3.Cross(Vector3.up, dir) * Random.Range(-30f, 30f);
                    }
                    State = "firing";
                }
                else
                {
                    Walk(ref ci, HoldLine(war, walkGoal == Vector3.zero ? target.Center : walkGoal), true);
                    phaseT -= dt;
                    if (phaseT <= 0f && visible && tDist < 480f)
                    {
                        firePhase = true;
                        phaseT = Random.Range(3.5f, 6f);
                        settleT = 0f;
                    }
                    State = "advancing";
                }
            }
            else
            {
                var prey = war.Endgame(self.team) ? war.NearestEnemy(self.team, pos) : null;
                if (prey) Walk(ref ci, prey.transform.position, true);
                else Walk(ref ci, HoldLine(war, war.Objective(self.team, pos)), true);
                State = dashing ? "dash" : "advance";
            }
            m.input = ci;
        }

        /// <summary>Mechs lead the push but don't run off alone: a goal far ahead of the friendly infantry front is pulled back.</summary>
        Vector3 HoldLine(WarManager war, Vector3 goal)
        {
            Vector3 fwd = war.Forward(self.team);
            float limit = war.FrontLine(self.team) + 160f;
            float prog = Vector3.Dot(goal, fwd);
            if (prog > limit) goal -= fwd * (prog - limit);
            return goal;
        }

        void Walk(ref ControlInput ci, Vector3 goal, bool sprint)
        {
            Vector3 pos = transform.position;
            float dist = AIUtil.Flat(goal - pos).magnitude;
            Vector3 steer = dist > 14f ? nav.Steer(pos, goal, dashing ? 20f : 6f) : goal;
            float ang = AIUtil.AngleTo(transform, steer) + avoid * 70f;
            // wall or wreck straight ahead: turn away from it
            Vector3 knee = pos + Vector3.up * 1.5f;
            if (AIUtil.Cast(knee, transform.forward, 9f, transform, out RaycastHit h) && h.normal.y < 0.7f && Health.Of(h.collider) == null &&
                h.collider.GetComponentInParent<CarProp>() == null)
                ang += Vector3.Dot(h.normal, transform.right) >= 0f ? 60f : -60f;
            ci.move = new Vector2(Mathf.Clamp(ang / 25f, -1f, 1f), dist > 12f ? (Mathf.Abs(ang) < 45f ? 1f : 0.35f) : 0f);
            ci.sprint = sprint && dist > 60f && Mathf.Abs(ang) < 30f;
            if (!m.CanDash) return;
            // thruster dash down long, straight stretches; drop out of it before corners, walls and the destination
            float straight = Mathf.Abs(ang);
            float turnAhead = nav.TurnAhead(pos, 45f);
            if (dashing)
            {
                if (dist < 70f || straight > 40f || turnAhead > 40f || m.JetFuel < 0.5f) { dashing = false; dashCd = 2.5f; }
            }
            else if (dashCd <= 0f && dist > 130f && straight < 15f && turnAhead < 25f && m.JetFuel > m.jetFuelMax * 0.45f && m.Grounded)
                dashing = true;
            if (dashing)
            {
                ci.jump = true;
                ci.sprint = dist > 260f;
                ci.lookYaw = AIUtil.YawTo(pos, steer);
                ci.move = new Vector2(0f, 1f);
            }
        }
    }
}
