using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    /// <summary>Small sites keep their beacon off the map until about one realm fills the view.</summary>
    public class PinTierTests
    {
        static CityManifest City(string kind, string settlement) =>
            new() { Kind = kind, WorldMap = new WorldMapPin { Settlement = settlement } };

        [Fact]
        public void CapitalsAndMetropolesAreMajorEstatesAndUnlistedPortsAreNot()
        {
            Assert.True(PinTiers.IsMajor(City("city", "settlement:calderra")));
            Assert.True(PinTiers.IsMajor(City("metropolis", "settlement:haven")));
            Assert.False(PinTiers.IsMajor(City("estate", null)));
            Assert.False(PinTiers.IsMajor(City("city", null)));            // Flamemouth: no lore-map settlement of its own
        }

        [Fact]
        public void MinorPinsAppearOnlyWhenZoomedInToARealm()
        {
            var port = City("city", null);
            Assert.Equal(0f, PinTiers.Reveal(port, 374f));                 // the Known World overview
            Assert.Equal(0f, PinTiers.Reveal(port, PinTiers.MinorGoneDist));
            Assert.InRange(PinTiers.Reveal(port, (PinTiers.MinorFullDist + PinTiers.MinorGoneDist) / 2), 0.4f, 0.6f);
            Assert.Equal(1f, PinTiers.Reveal(port, 52f));                  // the River Flame view
            Assert.Equal(1f, PinTiers.Reveal(City("city", "settlement:calderra"), 900f));
        }
    }
}
