using System;

namespace Atlas.Core
{
    /// <summary>Which map pins carry the big beacon (pole, glowing head, pulsing ring) at every zoom. A major site is a
    /// named settlement of the lore map (a capital, the temple-city); a minor one (an estate, a port with no settlement
    /// of its own, such as Flamemouth) only raises its beacon once the camera is in close enough to see about one realm.</summary>
    public static class PinTiers
    {
        /// <summary>Orbit distance (map units) below which a minor pin is at full size: about one kingdom fills the view
        /// (40° FOV, 16:9: ~1.3 × distance across, a realm is ~100 units wide).</summary>
        public const float MinorFullDist = 80f;
        /// <summary>Orbit distance above which a minor pin is gone.</summary>
        public const float MinorGoneDist = 110f;

        public static bool IsMajor(CityManifest m) =>
            m != null && !m.IsEstate && (m.IsMetropolis || !string.IsNullOrEmpty(m.WorldMap?.Settlement));

        /// <summary>How much of the pin shows at this orbit distance: 1 = full beacon, 0 = hidden (smooth in between).</summary>
        public static float Reveal(CityManifest m, float dist)
        {
            if (IsMajor(m)) return 1f;
            float t = Math.Clamp((MinorGoneDist - dist) / (MinorGoneDist - MinorFullDist), 0f, 1f);
            return t * t * (3f - 2f * t);
        }
    }
}
