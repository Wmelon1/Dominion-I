using System;

namespace Dominion
{
    /// <summary>
    /// Ground queries for code that must work on any map: terrain height (0 on the flat baseplate scenes) and the top of
    /// whatever stands there (terrain or building roofs), which pilots use to keep clear of hills and towers.
    /// The city generator installs the functions; they are cleared when it is destroyed.
    /// </summary>
    public static class WorldGround
    {
        public static Func<float, float, float> HeightFn;
        public static Func<float, float, float> TopFn;

        public static float Height(float x, float z) => HeightFn != null ? HeightFn(x, z) : 0f;
        public static float Top(float x, float z) => TopFn != null ? TopFn(x, z) : Height(x, z);

        public static void Reset()
        {
            HeightFn = null;
            TopFn = null;
        }
    }
}
