using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.SceneManagement;

namespace Dominion
{
    public enum GfxMode { Low, Medium, High, Max }

    /// <summary>
    /// Graphics modes (Settings menu, saved between sessions). MAX is exactly the game as authored: the High Fidelity HDRP
    /// asset, the scene's shadow distance, every screen-space effect, full level of detail and the full tree distance.
    /// The lower modes step down to the Balanced / Performant HDRP assets (shadow atlas, quality tiers), shorten the
    /// shadow and tree distances, drop camera effects (contact shadows, motion blur, ambient occlusion, volumetric fog)
    /// and use cheaper anti-aliasing and nearer level-of-detail switching. Airships are always drawn in full.
    /// </summary>
    public static class GraphicsMode
    {
        const string PrefKey = "dominion_gfx";
        public static readonly string[] Names = { "LOW", "MEDIUM", "HIGH", "MAX" };
        public static readonly string[] Info =
        {
            "Performant pipeline. Shadows to 300 m, no volumetric fog, ambient occlusion or contact shadows, FXAA, nearer level of detail, trees to 450 m, coarser distant terrain.",
            "Balanced pipeline. Shadows to 500 m, volumetric fog and ambient occlusion on, no contact shadows or motion blur, SMAA, trees to 700 m.",
            "Full pipeline. Shadows to 700 m, everything on except motion blur, slightly nearer level of detail, trees to 1 km.",
            "Everything at full quality: the full shadow distance, volumetric fog, ambient occlusion, contact shadows, motion blur, full level of detail, trees to 1.2 km.",
        };

        public static GfxMode Current { get; private set; } = (GfxMode)Mathf.Clamp(PlayerPrefs.GetInt(PrefKey, (int)GfxMode.Max), 0, 3);

        public static void Set(GfxMode m)
        {
            Current = m;
            PlayerPrefs.SetInt(PrefKey, (int)m);
            PlayerPrefs.Save();
            Apply();
        }

        // the scene's own values, captured once per scene: MAX restores exactly these
        static Scene captured;
        static bool hasCapture;
        static float lodBiasMax = -1f;
        static readonly Dictionary<Terrain, (float trees, float error)> terrainMax = new Dictionary<Terrain, (float, float)>();
        static readonly Dictionary<HDShadowSettings, float> shadowMax = new Dictionary<HDShadowSettings, float>();
        static HDAdditionalCameraData.AntialiasingMode aaMax;
        static HDAdditionalCameraData aaCam;

        static void Capture()
        {
            var scene = SceneManager.GetActiveScene();
            if (hasCapture && scene == captured) return;
            captured = scene;
            hasCapture = true;
            if (lodBiasMax < 0f) lodBiasMax = QualitySettings.lodBias;
            terrainMax.Clear();
            shadowMax.Clear();
            aaCam = null;
            foreach (var t in Terrain.activeTerrains) if (t) terrainMax[t] = (t.treeDistance, t.heightmapPixelError);
            foreach (var v in Object.FindObjectsByType<Volume>(FindObjectsSortMode.None))
            {
                var p = v.HasInstantiatedProfile() ? v.profile : v.sharedProfile;
                if (p != null && p.TryGet(out HDShadowSettings sh) && !shadowMax.ContainsKey(sh)) shadowMax[sh] = sh.maxShadowDistance.value;
            }
        }

        /// <summary>Apply the current mode to the active scene (call after the scene / city is set up).</summary>
        public static void Apply()
        {
            Capture();
            var m = Current;
            int level = m == GfxMode.Low ? 2 : m == GfxMode.Medium ? 1 : 0;
            if (level < QualitySettings.count && QualitySettings.GetQualityLevel() != level) QualitySettings.SetQualityLevel(level, true);
            QualitySettings.lodBias = lodBiasMax * (m == GfxMode.Low ? 0.55f : m == GfxMode.Medium ? 0.72f : m == GfxMode.High ? 0.88f : 1f);

            foreach (var kv in terrainMax)
            {
                if (kv.Key == null) continue;
                kv.Key.treeDistance = m == GfxMode.Max ? kv.Value.trees : Mathf.Min(kv.Value.trees, m == GfxMode.High ? 1000f : m == GfxMode.Medium ? 700f : 450f);
                kv.Key.heightmapPixelError = m == GfxMode.Max ? kv.Value.error : Mathf.Max(kv.Value.error, m == GfxMode.High ? 5f : m == GfxMode.Medium ? 7f : 10f);
            }
            foreach (var kv in shadowMax)
            {
                if (kv.Key == null) continue;
                kv.Key.maxShadowDistance.overrideState = true;
                kv.Key.maxShadowDistance.value = m == GfxMode.Max ? kv.Value : Mathf.Min(kv.Value, m == GfxMode.High ? 700f : m == GfxMode.Medium ? 500f : 300f);
            }

            var cam = Camera.main;
            var hd = cam ? cam.GetComponent<HDAdditionalCameraData>() : null;
            if (hd == null) return;
            if (aaCam != hd) { aaCam = hd; aaMax = hd.antialiasing; }
            hd.antialiasing = m == GfxMode.Low ? HDAdditionalCameraData.AntialiasingMode.FastApproximateAntialiasing
                            : m == GfxMode.Medium ? HDAdditionalCameraData.AntialiasingMode.SubpixelMorphologicalAntiAliasing : aaMax;
            hd.customRenderingSettings = m != GfxMode.Max;
            if (m == GfxMode.Max) return;
            var mask = hd.renderingPathCustomFrameSettingsOverrideMask;
            var fs = hd.renderingPathCustomFrameSettings;
            void F(FrameSettingsField f, bool on)
            {
                mask.mask[(uint)f] = true;
                fs.SetEnabled(f, on);
            }
            F(FrameSettingsField.SSAO, m >= GfxMode.Medium);
            F(FrameSettingsField.Volumetrics, m >= GfxMode.Medium);
            F(FrameSettingsField.ContactShadows, m >= GfxMode.High);
            F(FrameSettingsField.MotionBlur, false);
            hd.renderingPathCustomFrameSettingsOverrideMask = mask;
            hd.renderingPathCustomFrameSettings = fs;
        }
    }

    /// <summary>The settings overlay (title screen and pause menu): graphics mode buttons with what each one changes.</summary>
    public static class SettingsPanel
    {
        /// <summary>Draws the panel; true when BACK was pressed.</summary>
        public static bool Draw(float s, float W, float H)
        {
            Ui.Rect(new Rect(0, 0, W, H), new Color(0f, 0f, 0f, 0.5f));
            float w = 700 * s, h = 440 * s, x = (W - w) * 0.5f, y = (H - h) * 0.5f;
            Ui.Panel(new Rect(x, y, w, h));
            GUI.Label(new Rect(x, y + 16 * s, w, 64 * s), "SETTINGS", new GUIStyle(Ui.Big) { fontSize = Mathf.RoundToInt(50 * s) });
            GUI.Label(new Rect(x, y + 84 * s, w, 30 * s), "<color=#dbe6f2>Graphics mode</color>", Ui.Center);
            float gap = 12 * s, bw = (w - 80 * s - gap * 3f) / 4f;
            for (int i = 0; i < 4; i++)
            {
                string label = (int)GraphicsMode.Current == i ? $"[{GraphicsMode.Names[i]}]" : GraphicsMode.Names[i];
                if (Ui.Btn(new Rect(x + 40 * s + i * (bw + gap), y + 122 * s, bw, 60 * s), label)) GraphicsMode.Set((GfxMode)i);
            }
            var wrap = new GUIStyle(Ui.Small) { wordWrap = true, alignment = TextAnchor.UpperCenter, fontSize = Mathf.RoundToInt(18 * s) };
            GUI.Label(new Rect(x + 40 * s, y + 200 * s, w - 80 * s, 110 * s), $"<color=#cfe0f2>{GraphicsMode.Info[(int)GraphicsMode.Current]}</color>", wrap);
            GUI.Label(new Rect(x + 40 * s, y + 300 * s, w - 80 * s, 40 * s), "<color=#8fa6bd>Airships are always drawn and simulated in full, in every mode.</color>", wrap);
            return Ui.Btn(new Rect(x + w * 0.3f, y + h - 86 * s, w * 0.4f, 60 * s), "BACK");
        }
    }
}
