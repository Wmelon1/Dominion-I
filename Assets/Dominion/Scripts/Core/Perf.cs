using System.Diagnostics;
using System.Text;

namespace Dominion
{
    /// <summary>Tiny CPU-time accumulators for the auto-test log (ms per frame by system).</summary>
    public static class Perf
    {
        public const int SoldierAI = 0, GroundAI = 1, PlaneAI = 2, MechAI = 3, Soldiers = 4, Vehicles = 5, Tracers = 6, Hud = 7,
                         VehicleRig = 8, Ships = 9, Drones = 10, Lod = 11;
        static readonly string[] Names = { "soldierAI", "groundAI", "planeAI", "mechAI", "soldiers", "vehicles", "tracers", "hud",
                                           "vehicleRig", "ships", "drones", "lod" };
        /// <summary>Ground vehicles currently on the far physics proxy (auto-test log).</summary>
        public static int Proxied;
        static readonly long[] ticks = new long[Names.Length];
        public static long Now => Stopwatch.GetTimestamp();
        public static void Add(int slot, long start) => ticks[slot] += Stopwatch.GetTimestamp() - start;

        public static string Report(int frames)
        {
            var sb = new StringBuilder();
            double f = 1000.0 / Stopwatch.Frequency / System.Math.Max(1, frames);
            for (int i = 0; i < Names.Length; i++)
            {
                sb.Append(Names[i]).Append(' ').Append((ticks[i] * f).ToString("0.00")).Append(' ');
                ticks[i] = 0;
            }
            return sb.ToString();
        }
    }
}
