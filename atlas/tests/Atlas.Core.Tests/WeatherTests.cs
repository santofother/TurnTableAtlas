using System;
using System.IO;
using System.Linq;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    public class WeatherTests
    {
        [Fact]
        public void PresetsAreOrderedSensibly()
        {
            foreach (var k in Weather.All)
            {
                var p = Weather.Preset(k);
                foreach (var x in new[] { p.Coverage, p.Height, p.Darkness, p.Rain, p.Lightning, p.Fog, p.Wind })
                    Assert.InRange(x, 0.0, 1.0);
            }
            var clear = Weather.Preset(WeatherKind.Clear); var storm = Weather.Preset(WeatherKind.Storm);
            Assert.True(storm.Coverage > clear.Coverage + 0.5 && storm.Darkness > 0.7 && storm.Lightning > 0.5);
            Assert.True(Weather.Preset(WeatherKind.Overcast).Coverage > Weather.Preset(WeatherKind.Cloudy).Coverage);
            Assert.True(Weather.Preset(WeatherKind.Fog).Fog > 0.9 && clear.Rain == 0);
        }

        [Fact]
        public void TransitionsEaseAndSettle()
        {
            var w = new Weather(WeatherKind.Clear);
            w.Set(WeatherKind.Storm, 6);
            w.Step(1.0);
            var early = w.Current.Coverage;
            Assert.InRange(early, Weather.Preset(WeatherKind.Clear).Coverage, 0.3);   // still mostly clear after 1 s
            for (int i = 0; i < 60; i++) w.Step(0.1);
            Assert.Equal(1.0, w.Progress);
            Assert.Equal(Weather.Preset(WeatherKind.Storm).Coverage, w.Current.Coverage, 6);
            Assert.Equal(WeatherKind.Storm, w.Kind);
        }

        [Fact]
        public void CoverageOverrideWins()
        {
            var w = new Weather(WeatherKind.Fair) { CoverageOverride = 0.9 };
            w.Step(0.1);
            Assert.Equal(0.9, w.Current.Coverage, 6);
            w.CoverageOverride = null;
            w.Step(0.1);
            Assert.Equal(Weather.Preset(WeatherKind.Fair).Coverage, w.Current.Coverage, 6);
        }

        [Fact]
        public void WindDriftsDownwindAtTheRightSpeed()
        {
            var w = new Weather(WeatherKind.Rain) { WindDirDeg = 90 };   // towards north
            for (int i = 0; i < 100; i++) w.Step(0.1);
            Assert.True(Math.Abs(w.OffsetX) < 1e-9);
            Assert.Equal(w.DriftSpeed * 10, w.OffsetY, 6);
            var calm = new Weather(WeatherKind.Fog);
            Assert.True(calm.DriftSpeed < w.DriftSpeed);
        }

        [Fact]
        public void AutoModeIsDeterministicAndOnlyTakesPlausibleSteps()
        {
            string Run(int seed)
            {
                var w = new Weather(WeatherKind.Fair, seed) { Auto = true, AutoHold = 5 };
                var seen = new System.Collections.Generic.List<WeatherKind> { w.Kind };
                w.KindChanged += k => seen.Add(k);
                for (int i = 0; i < 20 * 600; i++) w.Step(0.05);
                Assert.True(seen.Count > 5, $"only {seen.Count} states in 10 minutes");
                for (int i = 1; i < seen.Count; i++)   // never jumps straight from clear skies to a storm
                    Assert.False(seen[i - 1] == WeatherKind.Clear && seen[i] == WeatherKind.Storm);
                return string.Join(",", seen);
            }
            Assert.Equal(Run(3), Run(3));
            Assert.NotEqual(Run(3), Run(4));
        }
    }

    public class KnownWorldMapTests
    {
        static KnownWorldMap Kw => KnownWorldMap.Load(Path.Combine(Repo.Root, "atlas", "assets", "map", "known_world", "known_world.json"));

        [Fact]
        public void BakedMapHasTheCapitals()
        {
            var kw = Kw;
            Assert.True(kw.Width > 600 && kw.Depth > 300);
            Assert.True(kw.ElevMin < 0 && kw.ElevMax > 3000);
            foreach (var id in new[] { "calderra", "astera", "dovehall", "kervara" })
                Assert.NotNull(kw.Settlement(id));
            Assert.All(kw.Settlements, s => { Assert.InRange(s.Uv[0], 0, 1); Assert.InRange(s.Uv[1], 0, 1); });
            Assert.True(File.Exists(Path.Combine(kw.Directory, kw.Albedo)) && File.Exists(Path.Combine(kw.Directory, kw.Height)));
        }

        [Fact]
        public void PaintedMapPinsCarryOverToTheRelief()
        {
            var kw = Kw;
            var cal = kw.Settlement("settlement:calderra");
            var (u, v) = kw.FromGeo(1301 / 3278.0, 1495 / 1920.0);     // the Calderra star on the painted map
            Assert.True(Math.Abs(u - cal.Uv[0]) < 0.02 && Math.Abs(v - cal.Uv[1]) < 0.02, $"({u:0.000},{v:0.000}) vs {cal.Uv[0]},{cal.Uv[1]}");
            var linked = kw.PinFor(new WorldMapPin { PinUv = new[] { 0.1, 0.1 }, Settlement = "settlement:calderra" });
            Assert.Equal(cal.Uv[0], linked.Value.U, 6);
            Assert.Equal(32767 / 65535.0 * (kw.ElevMax - kw.ElevMin) + kw.ElevMin, kw.Metres(127, 255), 3);
        }

        [Fact]
        public void ReliefKeepsTheBlendsProportionsAndCameras()
        {
            var kw = Kw;
            Assert.Equal(16093.44, kw.UnitM, 1);
            Assert.Equal(15, kw.Exaggeration, 3);
            Assert.InRange(kw.Units(kw.ElevMax), 6, 9);                  // ~7.3 units: highest peak at 15x
            Assert.Contains(kw.Cameras, c => c.Id == "CAM_01_Overview_KnownWorld");
            Assert.All(kw.Cameras, c => { Assert.InRange(c.Pitch, 1, 90); Assert.True(c.Dist > 0); });
            var (x, y) = kw.UvToXy(0.25, 0.75);
            var (u, v) = kw.XyToUv(x, y);
            Assert.Equal(0.25, u, 9); Assert.Equal(0.75, v, 9);
            var g = kw.ToGeo(kw.FromGeo(0.4, 0.7).U, kw.FromGeo(0.4, 0.7).V);
            Assert.Equal(0.4, g.U, 9); Assert.Equal(0.7, g.V, 9);
        }

        [Fact]
        public void HomeViewIsNorthUpOverTheMiddleOfTheMap()
        {
            var kw = Kw;
            var home = kw.HomeView();
            var (u, v) = kw.XyToUv(home.Target[0], home.Target[1]);
            Assert.Equal(0.5, u, 9); Assert.Equal(0.5, v, 9);
            Assert.Equal(-90, home.Yaw);
            Assert.Equal(kw.Cameras[0].Pitch, home.Pitch);
            Assert.Equal(kw.Cameras[0].Dist, home.Dist);
        }

        [Fact]
        public void EveryCityPackageLandsOnBothMaps()
        {
            var kw = Kw;
            foreach (var m in CityManifest.Discover(Repo.Cities))
            {
                Assert.NotNull(m.WorldMap);
                if (m.WorldMap.PinUv != null)            // on the painted Caelora map
                {
                    Assert.InRange(m.WorldMap.PinUv[0], 0, 1);
                    Assert.InRange(m.WorldMap.PinUv[1], 0, 1);
                }
                else if (m.WorldMap.KwXy == null) Assert.NotNull(kw.Settlement(m.WorldMap.Settlement));   // off Caelora: Known World only
                // FIX(haven): or placed straight on the Known World (kw_xy), as the port at the River Flame's mouth
                var p = kw.PinFor(m.WorldMap);
                Assert.True(p.HasValue && p.Value.U is > 0 and < 1 && p.Value.V is > 0 and < 1, m.Id);
            }
        }
    }
}
