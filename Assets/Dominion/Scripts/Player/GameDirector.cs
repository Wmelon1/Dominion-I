using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;

namespace Dominion
{
    /// <summary>
    /// Owns the player: which soldier or vehicle is controlled, boarding / leaving vehicles with E, the camera, the
    /// HUD and the pause menu (Esc). Sandbox: Tab swaps between the two soldiers.
    /// War: the player is one unit of the Blue army; everything else is AI. T takes command of the friendly unit under
    /// the crosshair (soldier, vehicle, aircraft or mech), Tab jumps to the nearest friendly soldier, and after dying the
    /// player takes over another friendly soldier. A soldier left aboard a vehicle stays on as its crew.
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public class GameDirector : MonoBehaviour
    {
        public SoldierController[] soldiers = new SoldierController[0];
        public CameraRig cameraRig;
        public float enterRange = 3.5f;

        [System.NonSerialized] public bool autopilot;
        [System.NonSerialized] public ControlInput simInput;
        [System.NonSerialized] public bool warMode;
        [System.NonSerialized] public Team playerTeam = Team.None;
        /// <summary>No player unit at all (war auto-test): every unit fights on its own.</summary>
        [System.NonSerialized] public bool spectate;

        public static GameDirector Instance { get; private set; }
        public Vehicle Current { get; private set; }
        public SoldierController Soldier { get; private set; }
        public bool Paused { get; private set; }
        public Health PlayerUnit => Current ? Current.health : Soldier && !Soldier.Dead ? Soldier.health : null;
        public float RespawnIn => respawnT;

        Vehicle[] vehicles;
        Vehicle nearest;
        Health commandTarget;
        bool bodyInside, showHelp = true;
        float fps = 60f, respawnT = -1f, hitT;
        readonly Dictionary<Vehicle, List<SoldierController>> crew = new Dictionary<Vehicle, List<SoldierController>>();
        readonly List<Vehicle> crewGone = new List<Vehicle>();

        /// <summary>
        /// Physics rate. 66.7 Hz: the suspension, track, tyre and aero results match 100 Hz to within 0.1 (measured with the
        /// Sandbox self-test) at two thirds of the physics cost. -physhz overrides it for testing.
        /// </summary>
        public static float PhysicsHz
        {
            get
            {
                var args = System.Environment.GetCommandLineArgs();
                for (int i = 0; i < args.Length - 1; i++)
                    if (args[i] == "-physhz" && float.TryParse(args[i + 1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float hz))
                        return Mathf.Clamp(hz, 30f, 200f);
                return 66.7f;
            }
        }

        void Awake()
        {
            Instance = this;
            Time.fixedDeltaTime = 1f / PhysicsHz;
            Time.timeScale = 1f;
        }

        void Start()
        {
            vehicles = FindObjectsByType<Vehicle>(FindObjectsSortMode.None);
            if (cameraRig == null) cameraRig = FindFirstObjectByType<CameraRig>();
            foreach (var s in soldiers) if (s) s.Controlled = false;
            if (soldiers.Length > 0 && !spectate) TakeSoldier(soldiers[0]);
            LockCursor(true);
            Health.AnyDamage += OnAnyDamage;
            GraphicsMode.Apply();
        }

        // ------------------------------------------------------------------ deploy screen (War): ground or an airship deck
        bool deployOpen, deployShown, settingsOpen;
        public bool DeployOpen => deployOpen;
        Airship mannedShip, gunShip;
        int mannedGun = -1, gunIndex = -1;

        void OpenDeploy()
        {
            if (autopilot || !warMode) return;
            deployOpen = true;
            LockCursor(false);
        }

        void CloseDeploy()
        {
            deployOpen = false;
            LockCursor(!Paused && !Over);
        }

        static bool Aboard(Vector3 p) => Airship.All.Count > 0 && Airship.Carry(p, out _, out _);

        /// <summary>Fight on the ground: keep the soldier you have there, else take over the nearest one.</summary>
        public void DeployGround()
        {
            CloseDeploy();
            LeaveGun();
            if (Current != null || (Soldier && !Soldier.Dead && !Aboard(Soldier.transform.position))) return;
            respawnT = -1f;
            Respawn();
        }

        /// <summary>Join one of our airships: a new deck gunner on its deck (the old body stays where it was).</summary>
        public bool DeployShip(Airship ship)
        {
            CloseDeploy();
            var war = WarManager.Instance;
            if (war == null || ship == null || ship.Destroyed) return false;
            var sc = war.SpawnPlayerOnShip(ship);
            if (sc == null) return false;
            LeaveGun();
            respawnT = -1f;
            var list = new System.Collections.Generic.List<SoldierController>(soldiers) { sc };
            soldiers = list.ToArray();
            spectate = false;
            TakeSoldier(sc);
            return true;
        }

        /// <summary>A soldier who joined the battle later (a paratrooper): add him to the roster Tab / respawn pick from.</summary>
        public void AddSoldier(SoldierController sc)
        {
            if (sc == null) return;
            var list = new System.Collections.Generic.List<SoldierController>(soldiers) { sc };
            soldiers = list.ToArray();
        }

        void LeaveGun()
        {
            if (mannedShip != null) mannedShip.Man(mannedGun, false);
            mannedShip = null;
            mannedGun = -1;
        }

        void DrawDeploy(float s, float W, float H)
        {
            var war = WarManager.Instance;
            if (war == null) return;
            var ships = new System.Collections.Generic.List<Airship>(war.Ships(playerTeam));
            Ui.Rect(new Rect(0, 0, W, H), new Color(0f, 0f, 0f, 0.35f));
            float w = 640 * s, h = (196 + 80 * (ships.Count + 1)) * s, x = (W - w) * 0.5f, y = (H - h) * 0.5f;
            Ui.Panel(new Rect(x, y, w, h));
            GUI.Label(new Rect(x, y + 14 * s, w, 64 * s), "DEPLOY", new GUIStyle(Ui.Big) { fontSize = Mathf.RoundToInt(50 * s) });
            bool dead = PlayerUnit == null;
            GUI.Label(new Rect(x, y + 78 * s, w, 30 * s), dead ? "<color=#dbe6f2>You were killed. Choose where to rejoin the fight.</color>"
                                                                : "<color=#dbe6f2>Choose where to fight. J opens this again at any time.</color>", Ui.Center);
            float bx = x + 36 * s, bw = w - 72 * s, by = y + 120 * s, bh = 62 * s;
            if (Ui.Btn(new Rect(bx, by, bw, bh), "GROUND  ·  a soldier in the city")) DeployGround();
            foreach (var a in ships)
            {
                by += 80 * s;
                float hp = a.health ? a.health.Fraction * 100f : 0f;
                if (Ui.Btn(new Rect(bx, by, bw, bh), $"{a.displayName.ToUpper()}  ·  {(a.flagship ? "flagship" : "escort")}  ·  hull {hp:0}%  ·  crew {a.CrewCount}"))
                    DeployShip(a);
            }
            if (!dead) GUI.Label(new Rect(x, y + h - 38 * s, w, 28 * s), "<color=#8fa6bd>Esc or J to close</color>", Ui.Center);
        }

        void OnDestroy()
        {
            Health.AnyDamage -= OnAnyDamage;
            if (Instance == this) Instance = null;
            Time.timeScale = 1f;
        }

        void OnAnyDamage(Health victim, DamageInfo d, float dmg)
        {
            var me = PlayerUnit;
            if (me != null && d.attacker == me && victim != me && Health.Enemies(victim.team, me.team)) hitT = victim.Alive ? 0.18f : 0.45f;
        }

        static void LockCursor(bool on)
        {
            Cursor.lockState = on ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !on;
        }

        bool Over => warMode && WarManager.Instance && WarManager.Instance.Over;

        public void SetPaused(bool p)
        {
            Paused = p;
            Time.timeScale = p ? 0f : 1f;
            LockCursor(!p && !Over);
        }

        void Update()
        {
            float udt = Time.unscaledDeltaTime;
            fps = Mathf.Lerp(fps, 1f / Mathf.Max(udt, 1e-4f), 0.05f);
            if (!autopilot)
            {
                if (GameInput.Down(Key.Escape))
                {
                    if (settingsOpen) settingsOpen = false;
                    else if (deployOpen && PlayerUnit != null) CloseDeploy();
                    else SetPaused(!Paused);
                }
                if (Paused) return;
                if (warMode && !deployShown && Time.timeSinceLevelLoad > 0.25f) { deployShown = true; OpenDeploy(); }
                if (warMode && GameInput.Down(Key.J)) { if (deployOpen) { if (PlayerUnit != null) CloseDeploy(); } else OpenDeploy(); }
                if (!GameInput.CursorLocked && GameInput.LeftClickDown && !Over && !deployOpen) LockCursor(true);
                if (GameInput.Down(Key.F1)) showHelp = !showHelp;
            }
            if (Paused) return;
            cameraRig.inputEnabled = !autopilot;
            hitT -= Time.deltaTime;
            if (warMode) WarUpkeep(Time.deltaTime);

            ControlInput ci = autopilot ? simInput : GameInput.Read();
            if (!autopilot)
            {
                ci.lookYaw = cameraRig.yaw;
                ci.lookPitch = cameraRig.pitch;
            }
            ci.aimPoint = cameraRig.AimPoint();
            if ((warMode && WarManager.Instance && !WarManager.Instance.Fighting) || (deployOpen && !autopilot))
                ci = new ControlInput { lookYaw = ci.lookYaw, lookPitch = ci.lookPitch, aimPoint = ci.aimPoint };   // countdown / deploy menu: hold

            // vehicle within reach on foot
            nearest = null;
            if (Current == null && Soldier && !Soldier.Dead)
            {
                float best = enterRange;
                foreach (var v in vehicles)
                {
                    if (v == null || v.Destroyed || (warMode && v.team != playerTeam)) continue;
                    float d = v.DistanceTo(Soldier.transform.position + Vector3.up);
                    if (d < best)
                    {
                        best = d;
                        nearest = v;
                    }
                }
            }
            // deck guns on our airships: E mans the one within reach, E again leaves it
            gunShip = null;
            gunIndex = -1;
            if (warMode && Current == null && Soldier && !Soldier.Dead && mannedShip == null && Airship.All.Count > 0)
                foreach (var a in Airship.All)
                {
                    if (a == null || a.team != playerTeam || a.Destroyed) continue;
                    int gi = a.TurretNear(Soldier.transform.position + Vector3.up, 3.6f);
                    if (gi >= 0) { gunShip = a; gunIndex = gi; break; }
                }
            if (mannedShip != null && (mannedShip.Destroyed || Soldier == null || Soldier.Dead || Current != null)) LeaveGun();
            if (!autopilot && GameInput.Down(Key.E))
            {
                if (mannedShip != null) LeaveGun();
                else if (Current == null && nearest) Enter(nearest);
                else if (Current == null && gunShip != null) { mannedShip = gunShip; mannedGun = gunIndex; mannedShip.Man(mannedGun, true); }
                else if (Current != null && bodyInside && Current.CanExit) Exit();
            }
            if (mannedShip != null)
            {
                // the gun follows the crosshair (never our own hull); the gunner stays at his post
                Vector3 aim = ci.aimPoint;
                if (Vector3.Distance(aim, mannedShip.transform.position) < mannedShip.hullBounds.extents.z * 1.2f)
                    aim = cameraRig.transform.position + cameraRig.transform.forward * 1200f;
                mannedShip.PlayerGun(mannedGun, aim, ci.fire);
                ci.move = Vector2.zero;
                ci.fire = ci.aim = ci.sprint = ci.action2Down = false;
            }
            if (!autopilot && GameInput.Down(Key.Tab)) SwitchSoldier();
            if (warMode && !autopilot && GameInput.Down(Key.T) && commandTarget) TakeCommand(commandTarget);

            if (Current != null) Current.input = ci;
            else if (Soldier && !Soldier.Dead) Soldier.input = ci;
        }

        // ------------------------------------------------------------------ War: deaths, crew, command target
        void WarUpkeep(float dt)
        {
            // soldiers left aboard as crew die with their vehicle
            crewGone.Clear();
            foreach (var kv in crew)
                if (kv.Key == null || kv.Key.Destroyed)
                {
                    foreach (var s in kv.Value)
                        if (s && s.health && s.health.Alive) s.health.Kill(new DamageInfo { attacker = kv.Key && kv.Key.health ? kv.Key.health.LastAttacker : null });
                    crewGone.Add(kv.Key);
                }
            foreach (var v in crewGone) crew.Remove(v);

            if (Current != null && Current.Destroyed)
            {
                var v = Current;
                Current = null;
                v.PlayerDriven = false;
                if (bodyInside && Soldier && Soldier.health && Soldier.health.Alive)
                    Soldier.health.Kill(new DamageInfo { attacker = v.health ? v.health.LastAttacker : null });
                bodyInside = false;
                if (respawnT < 0f) respawnT = 3.5f;
            }
            else if (Current == null && Soldier != null && Soldier.Dead && respawnT < 0f) respawnT = 3.5f;
            else if (Current == null && Soldier == null && !spectate && respawnT < 0f) respawnT = 0.5f;
            if (respawnT >= 0f)
            {
                respawnT -= dt;
                if (respawnT < 0f)
                {
                    if (autopilot || spectate) Respawn();
                    else { respawnT = -1f; LeaveGun(); OpenDeploy(); }
                }
            }
            commandTarget = spectate ? null : FindCommandTarget();
        }

        void Respawn()
        {
            respawnT = -1f;
            Vector3 from = cameraRig.transform.position;
            SoldierController best = null;
            float bd = float.MaxValue;
            foreach (var s in soldiers)
            {
                if (s == null || s.Dead || !s.gameObject.activeInHierarchy || (s.health && !s.health.Alive) || Aboard(s.transform.position)) continue;
                float d = (s.transform.position - from).sqrMagnitude;
                if (d < bd) { bd = d; best = s; }
            }
            if (best) { TakeSoldier(best); return; }
            Vehicle bv = null;
            foreach (var v in vehicles)
            {
                if (v == null || v.Destroyed || v.team != playerTeam) continue;
                float d = (v.transform.position - from).sqrMagnitude;
                if (d < bd) { bd = d; bv = v; }
            }
            if (bv) TakeCommand(bv.health);
            else spectate = true;                           // nothing left to command
        }

        /// <summary>Friendly unit closest to the crosshair (for T).</summary>
        Health FindCommandTarget()
        {
            Transform cam = cameraRig.transform;
            Health me = PlayerUnit, best = null;
            float bestA = float.MaxValue;
            foreach (var h in Health.All)
            {
                if (!h.Alive || h == me || h.team != playerTeam || !h.gameObject.activeInHierarchy || h.IsDrone || h.IsAirship) continue;
                Vector3 d = h.Center - cam.position;
                float dist = d.magnitude;
                float lim = h.cls == UnitClass.Air ? 2500f : h.cls == UnitClass.Soldier ? 400f : 1500f;
                if (dist > lim || dist < 2f) continue;
                float ang = Vector3.Angle(cam.forward, d);
                float tol = 2.5f + Mathf.Atan2(h.Radius * 1.5f, dist) * Mathf.Rad2Deg;
                if (ang < tol && ang < bestA) { bestA = ang; best = h; }
            }
            return best;
        }

        // ------------------------------------------------------------------ control transfer
        void SetCurrent(Vehicle v)
        {
            Current = v;
            v.PlayerDriven = true;
            v.OnEnter();
            cameraRig.FollowVehicle(v, v is AircraftVehicle);
        }

        void ReleaseCurrent()
        {
            if (Current == null) return;
            var v = Current;
            Current = null;
            v.PlayerDriven = false;
            v.OnExit();
        }

        /// <summary>Leave the current vehicle to its AI; our soldier climbs out if it can, otherwise stays aboard as crew.</summary>
        void AbandonCurrent()
        {
            if (Current == null) return;
            var v = Current;
            if (bodyInside && Soldier && !Soldier.Dead)
            {
                if (v.CanExit)
                {
                    ReleaseCurrent();
                    Soldier.gameObject.SetActive(true);
                    Soldier.Place(v.ExitPoint, v.transform.eulerAngles.y);
                    Soldier.Controlled = false;
                }
                else
                {
                    if (!crew.TryGetValue(v, out var list)) crew[v] = list = new List<SoldierController>();
                    list.Add(Soldier);
                    ReleaseCurrent();
                }
                Soldier = null;
            }
            else ReleaseCurrent();
            bodyInside = false;
        }

        void TakeSoldier(SoldierController s)
        {
            if (s == null) return;
            if (Current != null) AbandonCurrent();
            if (Soldier && Soldier != s) Soldier.Controlled = false;
            Soldier = s;
            s.aiDriven = false;
            s.Controlled = true;
            cameraRig.yaw = s.transform.eulerAngles.y;
            cameraRig.pitch = 12f;
            cameraRig.FollowSoldier(s);
        }

        /// <summary>T: take over a friendly unit remotely (our previous soldier carries on under AI control).</summary>
        public void TakeCommand(Health h)
        {
            if (h == null || !h.Alive) return;
            if (h.Soldier) { TakeSoldier(h.Soldier); return; }
            if (h.Vehicle == null || h.Vehicle.Destroyed) return;
            if (Current != null) AbandonCurrent();
            else if (Soldier) Soldier.Controlled = false;
            Soldier = null;
            bodyInside = false;
            SetCurrent(h.Vehicle);
        }

        public bool TryEnterNearest()
        {
            if (Current == null && nearest)
            {
                Enter(nearest);
                return true;
            }
            return false;
        }

        /// <summary>E: our soldier boards the vehicle.</summary>
        public void Enter(Vehicle v)
        {
            if (Current != null || v == null || v.Destroyed || Soldier == null) return;
            Soldier.Controlled = false;
            Soldier.gameObject.SetActive(false);
            bodyInside = true;
            SetCurrent(v);
        }

        /// <summary>E: our soldier climbs out.</summary>
        public void Exit()
        {
            if (Current == null) return;
            var v = Current;
            ReleaseCurrent();
            if (bodyInside && Soldier)
            {
                Soldier.gameObject.SetActive(true);
                Soldier.Place(v.ExitPoint, v.transform.eulerAngles.y);
                Soldier.Controlled = true;
                cameraRig.yaw = v.transform.eulerAngles.y;
                cameraRig.FollowSoldier(Soldier);
            }
            bodyInside = false;
        }

        public void SwitchSoldier()
        {
            if (warMode)
            {
                // nearest other friendly soldier
                Vector3 from = cameraRig.transform.position;
                SoldierController best = null;
                float bd = float.MaxValue;
                foreach (var s in soldiers)
                {
                    if (s == null || s == Soldier || s.Dead || !s.gameObject.activeInHierarchy) continue;
                    float d = (s.transform.position - from).sqrMagnitude;
                    if (d < bd) { bd = d; best = s; }
                }
                if (best) TakeSoldier(best);
                return;
            }
            if (soldiers.Length < 2 || Current != null) return;
            int i = System.Array.IndexOf(soldiers, Soldier);
            TakeSoldier(soldiers[(i + 1) % soldiers.Length]);
        }

        /// <summary>Hand every unit to the AI and let the camera roam (war auto-test).</summary>
        public void Spectate()
        {
            if (Current != null) AbandonCurrent();
            if (Soldier) Soldier.Controlled = false;
            Soldier = null;
            spectate = true;
        }

        /// <summary>Point the camera at a unit without taking control of it (spectator).</summary>
        public void Watch(Health h)
        {
            if (h == null) return;
            if (h.Soldier) cameraRig.FollowSoldier(h.Soldier);
            else if (h.Vehicle) cameraRig.FollowVehicle(h.Vehicle, h.Vehicle is AircraftVehicle);
        }

        // ------------------------------------------------------------------ HUD
        void OnGUI()
        {
            Ui.Begin();
            float s = Ui.S;
            float W = Screen.width, H = Screen.height;
            float cx = W * 0.5f, cy = H * 0.5f;

            if (!spectate)
            {
                // crosshair, and a hit marker when our rounds connect
                float c = 9f * s;
                Ui.Rect(new Rect(cx - c, cy - 1, c * 2, 2), new Color(1f, 1f, 1f, 0.85f));
                Ui.Rect(new Rect(cx - 1, cy - c, 2, c * 2), new Color(1f, 1f, 1f, 0.85f));
                if (hitT > 0f)
                {
                    var m = GUI.matrix;
                    Color hc = hitT > 0.2f ? new Color(1f, 0.3f, 0.25f) : Color.white;
                    for (int k = 0; k < 4; k++)
                    {
                        GUIUtility.RotateAroundPivot(45f + 90f * k, new Vector2(cx, cy));
                        Ui.Rect(new Rect(cx + 7 * s, cy - 1, 8 * s, 2), hc);
                        GUI.matrix = m;
                    }
                }
            }

            string who = Current != null ? Current.displayName : Soldier ? Soldier.displayName : spectate ? "Spectating" : "";
            string status = Current != null ? Current.Status : Soldier ? $"{Soldier.Speed:0.0} m/s" : "";
            if (Soldier && !Current && warMode && Soldier.GrenadeCooldown > 0f) status += $"   grenade {Soldier.GrenadeCooldown:0}s";
            GUI.Label(new Rect(20 * s, H - 70 * s, 900 * s, 60 * s), $"<b>{who}</b>   {status}", Ui.Label);
            var me = PlayerUnit;
            if (warMode && me)
            {
                float bw = 260 * s;
                Ui.Rect(new Rect(20 * s, H - 84 * s, bw, 8 * s), new Color(0f, 0f, 0f, 0.55f));
                Ui.Rect(new Rect(20 * s, H - 84 * s, bw * me.Fraction, 8 * s), Color.Lerp(new Color(1f, 0.25f, 0.2f), new Color(0.4f, 1f, 0.45f), me.Fraction));
                GUI.Label(new Rect(24 * s + bw, H - 94 * s, 200 * s, 28 * s), $"{me.hp:0} / {me.maxHp:0}", Ui.Small);
            }
            GUI.Label(new Rect(W - 230 * s, 12 * s, 220 * s, 30 * s), $"<b>DOMINION I</b>   {fps:0} fps", Ui.Label);

            if (nearest && Current == null)
                GUI.Label(new Rect(0, cy + 60 * s, W, 40 * s), $"Press <b>E</b> to enter <b>{nearest.displayName}</b>", Ui.Center);
            if (Current != null && GameInput.Held(Key.E))
            {
                if (!bodyInside) GUI.Label(new Rect(0, cy + 60 * s, W, 40 * s), "Commanding remotely: T or Tab to switch units", Ui.Center);
                else if (!Current.CanExit) GUI.Label(new Rect(0, cy + 60 * s, W, 40 * s), "Stop (and land) before exiting", Ui.Center);
            }
            if (warMode && commandTarget && !nearest)
                GUI.Label(new Rect(0, cy + 92 * s, W, 40 * s),
                    $"Press <b>T</b> to take command of <color=#{Ui.Hex(TeamPaint.Of(commandTarget.team))}><b>{commandTarget.unitName}</b></color>", Ui.Center);
            if (respawnT >= 0f)
                GUI.Label(new Rect(0, cy - 140 * s, W, 40 * s), $"<b>You were killed.</b>  Redeploy in {Mathf.Max(0f, respawnT):0.0} s", Ui.Center);
            if (gunShip != null && mannedShip == null && !nearest)
                GUI.Label(new Rect(0, cy + 60 * s, W, 40 * s), $"Press <b>E</b> to man the <b>{gunShip.displayName}</b> deck gun", Ui.Center);
            if (mannedShip != null)
                GUI.Label(new Rect(0, cy + 60 * s, W, 40 * s), $"On the <b>{mannedShip.displayName}</b> gun:  <b>LMB</b> fire   <b>E</b> leave", Ui.Center);
            if (!GameInput.CursorLocked && !autopilot && !Paused && !Over)
                GUI.Label(new Rect(0, cy - 100 * s, W, 40 * s), "Click to capture the mouse", Ui.Center);

            if (showHelp && !Paused && !spectate)
            {
                string help = Current != null ? Current.ControlsHelp :
                    "WASD  move (8-direction strafe)     Shift  run\nMouse  look     RMB  aim     LMB  fire (while aiming)" +
                    (warMode ? "     G  rifle grenade" : "") + "\nE  enter nearby vehicle     Tab  switch soldier";
                if (warMode) help += "\nT  take command of the friendly unit under the crosshair";
                help += "\nF1  hide help     Esc  pause menu";
                Ui.Panel(new Rect(16 * s, 16 * s, 600 * s, (warMode ? 176 : 150) * s));
                GUI.Label(new Rect(28 * s, 26 * s, 580 * s, 160 * s), help, Ui.Small);
            }
            if (deployOpen && !autopilot && !Paused) DrawDeploy(s, W, H);
            if (Paused)
            {
                if (settingsOpen) { if (SettingsPanel.Draw(s, W, H)) settingsOpen = false; }
                else DrawPause(s, W, H);
            }
        }

        void DrawPause(float s, float W, float H)
        {
            Ui.Rect(new Rect(0, 0, W, H), new Color(0f, 0f, 0f, 0.45f));
            float w = 420 * s, h = 506 * s, x = (W - w) * 0.5f, y = (H - h) * 0.5f;
            Ui.Panel(new Rect(x, y, w, h));
            GUI.Label(new Rect(x, y + 18 * s, w, 70 * s), "PAUSED", new GUIStyle(Ui.Big) { fontSize = Mathf.RoundToInt(56 * s) });
            float bw = w - 80 * s, bh = 62 * s, bx = x + 40 * s, by = y + 110 * s, gap = 76 * s;
            if (Ui.Btn(new Rect(bx, by, bw, bh), "RESUME")) SetPaused(false);
            if (Ui.Btn(new Rect(bx, by + gap, bw, bh), "SETTINGS")) settingsOpen = true;
            if (Ui.Btn(new Rect(bx, by + gap * 2, bw, bh), "RESTART")) { SetPaused(false); SceneManager.LoadScene(SceneManager.GetActiveScene().name); }
            if (Ui.Btn(new Rect(bx, by + gap * 3, bw, bh), "MAIN MENU")) { SetPaused(false); SceneManager.LoadScene("Title"); }
            if (Ui.Btn(new Rect(bx, by + gap * 4, bw, bh), "QUIT")) Application.Quit();
        }
    }
}
