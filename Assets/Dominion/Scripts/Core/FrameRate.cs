using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// No vsync, frame rate capped at the display's refresh rate. With vsync on a 120 Hz panel, any frame slower than
    /// 8.3 ms waits for the next refresh, so an 18 ms frame would show at 25 ms (40 fps); uncapped it shows at ~55 fps
    /// (and adaptive-sync displays stay tear-free). -vsync on the command line restores vsync.
    /// </summary>
    public static class FrameRate
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Init()
        {
            if (System.Array.IndexOf(System.Environment.GetCommandLineArgs(), "-vsync") >= 0) return;
            QualitySettings.vSyncCount = 0;
            double hz = Screen.currentResolution.refreshRateRatio.value;
            Application.targetFrameRate = hz > 30 ? Mathf.RoundToInt((float)hz) : 144;
        }
    }
}
