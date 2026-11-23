using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Dominion
{
    /// <summary>
    /// Title screen: the camera drifts around two opposing battle lines while the menu offers
    /// SANDBOX (the free test range), WAR (two AI armies of 50 fight it out, the player is one of them) and QUIT.
    /// Command-line auto-tests skip straight to their scene.
    /// </summary>
    public class TitleScreen : MonoBehaviour
    {
        public Transform focus;
        public float orbitRadius = 54f, orbitHeight = 11f, orbitSpeed = 2.2f;
        public GameObject[] blueSide = new GameObject[0];
        public GameObject[] redSide = new GameObject[0];
        float angle = 200f, fade = 1f;
        bool settingsOpen;
        string loading;
        string seedText = "";
        int armyIdx = 2;

        void Start()
        {
            Time.timeScale = 1f;
            GraphicsMode.Apply();
            var args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "-autotest" || args[i] == "-vfxonly") { SceneManager.LoadScene("Baseplate"); return; }
                if (args[i] == "-wartest") { SceneManager.LoadScene("War"); return; }
                if (args[i] == "-titleshot" && i + 1 < args.Length) StartCoroutine(TitleShot(args[i + 1]));
            }
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            foreach (var go in blueSide) if (go) TeamPaint.Apply(go, Team.Blue, go.GetComponent<SoldierController>() != null);
            foreach (var go in redSide) if (go) TeamPaint.Apply(go, Team.Red, go.GetComponent<SoldierController>() != null);
            foreach (var go in blueSide) { var mc = go ? go.GetComponent<MechKit.MechController>() : null; if (mc) mc.Faction = MechKit.MechFaction.SkyLegion; }
            foreach (var go in redSide) { var mc = go ? go.GetComponent<MechKit.MechController>() : null; if (mc) mc.Faction = MechKit.MechFaction.StormCorsairs; }
            // the riflemen shoulder their weapons at each other
            foreach (var side in new[] { blueSide, redSide })
                foreach (var go in side)
                {
                    var sc = go ? go.GetComponent<SoldierController>() : null;
                    if (sc == null) continue;
                    sc.aiDriven = true;
                    sc.input = new ControlInput { aim = true, lookYaw = go.transform.eulerAngles.y };
                }
        }

        /// <summary>-titleshot path: capture the title screen after it fades in, then quit (auto-test).</summary>
        System.Collections.IEnumerator TitleShot(string path)
        {
            yield return new WaitForSeconds(4f);
            yield return new WaitForEndOfFrame();
            ScreenCapture.CaptureScreenshot(path);
            yield return new WaitForSeconds(1f);
            Application.Quit();
        }

        void LateUpdate()
        {
            fade = Mathf.MoveTowards(fade, 0f, Time.deltaTime * 0.8f);
            angle += orbitSpeed * Time.deltaTime;
            Vector3 c = focus ? focus.position : Vector3.zero;
            float a = angle * Mathf.Deg2Rad;
            Vector3 p = c + new Vector3(Mathf.Sin(a) * orbitRadius, orbitHeight + Mathf.Sin(Time.time * 0.15f) * 3f, Mathf.Cos(a) * orbitRadius);
            transform.position = p;
            transform.rotation = Quaternion.LookRotation(c + Vector3.up * 4f - p);
        }

        void Load(string scene, string label)
        {
            loading = label;
            SceneManager.LoadSceneAsync(scene);
        }

        void OnGUI()
        {
            Ui.Begin();
            float s = Ui.S, W = Screen.width, H = Screen.height;
            // darkening gradient behind the menu
            for (int i = 0; i < 12; i++) Ui.Rect(new Rect(0, H * (0.55f + i * 0.0375f), W, H * 0.0375f + 1), new Color(0f, 0f, 0f, 0.04f * i));
            Ui.ShadowLabel(new Rect(0, H * 0.13f, W, 150 * s), $"DOMINION <color=#{Ui.Hex(Ui.Gold)}>I</color>", Ui.Title);
            Ui.ShadowLabel(new Rect(0, H * 0.13f + 140 * s, W, 40 * s), "<color=#cfe0f2>COMBINED ARMS WARFARE</color>", Ui.Subtitle);
            if (settingsOpen)
            {
                if (SettingsPanel.Draw(s, W, H)) settingsOpen = false;
                return;
            }

            float bw = 380 * s, bh = 74 * s, x = (W - bw) * 0.5f, y = H * 0.44f;
            if (loading == null)
            {
                if (Ui.Btn(new Rect(x, y, bw, bh), "SANDBOX")) Load("Baseplate", "Loading the sandbox...");
                GUI.Label(new Rect(0, y + bh + 4 * s, W, 28 * s), "<color=#dbe6f2>Free test range: drive, fly and pilot everything</color>", Ui.Center);
                float wy = y + 130 * s;
                int army = MapInfo.ArmySizes[armyIdx];
                if (Ui.Btn(new Rect(x, wy, bw, bh), "WAR"))
                {
                    MapInfo.Seed = int.TryParse(seedText, out int sd) && sd != 0 ? sd : 0;
                    MapInfo.ArmySize = army;
                    Load("War", MapInfo.Seed != 0 ? $"Building {MapInfo.NameOf(MapInfo.Seed)} and deploying the armies..." : "Building a new city and deploying the armies...");
                }
                GUI.Label(new Rect(0, wy + bh + 4 * s, W, 28 * s),
                    $"<color=#dbe6f2>{army} vs {army} in a procedurally generated city: infantry, armour, aircraft and mechs</color>", Ui.Center);
                // map seed: empty = a new random city each time
                float ry = wy + bh + 40 * s, fw = 210 * s, lh = 40 * s;
                var field = new GUIStyle(GUI.skin.textField) { fontSize = Mathf.RoundToInt(20 * s), alignment = TextAnchor.MiddleCenter };
                GUI.Label(new Rect(x - 40 * s, ry, 130 * s, lh), "<color=#dbe6f2>Map seed</color>", Ui.Right);
                seedText = GUI.TextField(new Rect(x + 100 * s, ry, fw, lh), seedText ?? "", 7, field);
                seedText = new string((seedText ?? "").Where(char.IsDigit).ToArray());
                if (Ui.Btn(new Rect(x + 100 * s + fw + 10 * s, ry, 110 * s, lh), "NEW")) seedText = MapInfo.RandomSeed().ToString();
                string mapLine = int.TryParse(seedText, out int ps) && ps != 0
                    ? $"Map: <b><color=#{Ui.Hex(Ui.Gold)}>{MapInfo.NameOf(ps)}</color></b>" : "<color=#9fb4cc>Leave empty for a new random city every battle</color>";
                GUI.Label(new Rect(0, ry + lh + 4 * s, W, 28 * s), mapLine, Ui.Center);
                // army size per side
                float ay = ry + lh + 40 * s;
                GUI.Label(new Rect(x - 40 * s, ay, 130 * s, lh), "<color=#dbe6f2>Army size</color>", Ui.Right);
                for (int i = 0; i < MapInfo.ArmySizes.Length; i++)
                {
                    string label = i == armyIdx ? $"[{MapInfo.ArmySizes[i]}]" : MapInfo.ArmySizes[i].ToString();
                    if (Ui.Btn(new Rect(x + 100 * s + i * 108 * s, ay, 100 * s, lh), label)) armyIdx = i;
                }
                if (Ui.Btn(new Rect(x, ay + lh + 24 * s, bw * 0.48f, bh * 0.7f), "SETTINGS")) settingsOpen = true;
                if (Ui.Btn(new Rect(x + bw * 0.52f, ay + lh + 24 * s, bw * 0.48f, bh * 0.7f), "QUIT")) Application.Quit();
            }
            else GUI.Label(new Rect(0, y + 60 * s, W, 50 * s), loading, Ui.Center);
            GUI.Label(new Rect(16 * s, H - 34 * s, 600 * s, 30 * s), "<color=#8095aa>Dominion Studio</color>", Ui.Small);
            if (fade > 0f) Ui.Rect(new Rect(0, 0, W, H), new Color(0f, 0f, 0f, fade));
        }
    }
}
