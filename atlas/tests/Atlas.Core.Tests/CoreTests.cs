using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    public static class Repo
    {
        public static string Root
        {
            get
            {
                var d = new DirectoryInfo(AppContext.BaseDirectory);
                while (d != null && !File.Exists(Path.Combine(d.FullName, "AGENTS.md"))) d = d.Parent;
                return d?.FullName ?? throw new DirectoryNotFoundException("repo root (AGENTS.md) not found");
            }
        }
        public static string Cities => Path.Combine(Root, "cities");
    }

    public class SunArcTests
    {
        static void Near(double expected, double actual, double tol = 2e-5, string what = "")
            => Assert.True(Math.Abs(expected - actual) <= tol, $"{what}: expected {expected}, got {actual}");

        [Fact]
        public void MatchesPythonCaseTable()
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(Repo.Root, "tests", "sunarc_cases.json")));
            int n = 0;
            foreach (var c in doc.RootElement.EnumerateArray())
            {
                double lat = c.GetProperty("lat").GetDouble(), doy = c.GetProperty("doy").GetDouble();
                double hour = c.GetProperty("hour").GetDouble(), off = c.GetProperty("north_offset").GetDouble();
                var (el, az) = SunArc.Position(lat, doy, hour, off);
                Near(c.GetProperty("elevation").GetDouble(), el, 2e-5, "elevation");
                double dAz = Math.Abs(((c.GetProperty("azimuth").GetDouble() - az) % 360 + 540) % 360 - 180);
                Assert.True(dAz < 1e-4, $"azimuth {az} vs {c.GetProperty("azimuth")}");
                var d = SunArc.Direction(lat, doy, hour, off);
                var dir = c.GetProperty("dir").EnumerateArray().Select(x => x.GetDouble()).ToArray();
                Near(dir[0], d.X); Near(dir[1], d.Y); Near(dir[2], d.Z);
                Near(c.GetProperty("daylight").GetDouble(), SunArc.Daylight(el));
                Near(c.GetProperty("dusk").GetDouble(), SunArc.Dusk(el));
                Near(c.GetProperty("window_level").GetDouble(), SunArc.WindowLevel(el, hour));
                var (rise, set) = SunArc.SunriseSunset(lat, doy);
                var pr = c.GetProperty("sunrise");
                if (pr.ValueKind == JsonValueKind.Null) Assert.Null(rise); else Near(pr.GetDouble(), rise.Value);
                var ps = c.GetProperty("sunset");
                if (ps.ValueKind == JsonValueKind.Null) Assert.Null(set); else Near(ps.GetDouble(), set.Value);
                n++;
            }
            Assert.True(n >= 300, $"only {n} cases");
        }

        [Fact]
        public void ArcRisesInTheEastAtMidLatitudeSummer()
        {
            var arc = SunArc.Arc(38, 172, 0);
            Assert.True(arc.Count > 40);
            Assert.True(arc[0].Dir.X > 0.3);                       // first point above the horizon is east-ish
            Assert.True(arc.Max(a => a.Dir.Z) > 0.95);             // high noon sun
        }

        [Fact]
        public void LatitudeChangesNoonHeight()
        {
            Assert.True(SunArc.Position(10, 355, 12).Elevation > SunArc.Position(60, 355, 12).Elevation + 40);
        }
    }

    public class ManifestTests
    {
        [Fact]
        public void EveryPackageParsesAndIsUsable()
        {
            var cities = CityManifest.Discover(Repo.Cities);
            Assert.NotEmpty(cities);
            foreach (var m in cities)
            {
                Assert.Equal(1, m.Version);
                Assert.True(m.StreetGraph.Nodes.Length > 200);
                Assert.NotEmpty(m.Landmarks);
                Assert.Contains(m.Landmarks, l => l.Id == "overview");
                Assert.True(File.Exists(m.FilePath("model")), "model missing for " + m.Id);
                if (m.IsEstate)   // FIX(villa): a country estate has no venues, but a ground grid for the Known World
                    Assert.True(m.Venues.Count == 0 && m.Terrain.Z.Length == m.Terrain.N * m.Terrain.N && m.Anchors.Count >= 10);
                else if (m.IsMetropolis)   // FIX(karn_ashur): no venues; instances, its true ground and the basin's layout
                    Assert.True(m.Venues.Count == 0 && m.Instances.Count > 50000 && m.TerrainHeight != null && m.Site.Districts.Count == 4);
                else
                    Assert.True(m.Venues.Sum(v => v.Capacity) > 500);
                if (m.WorldMap.PinUv != null) Assert.InRange(m.WorldMap.PinUv[0], 0, 1);
                else Assert.StartsWith("settlement:", m.WorldMap.Settlement);   // a city off the painted Caelora map
            }
        }

        [Fact]
        public void PolylineAtWalksTheArc()
        {
            var pl = new Polyline(new[] { new Vec3(0, 0, 0), new Vec3(10, 0, 0), new Vec3(10, 10, 0) });
            Assert.Equal(20, pl.Length, 6);
            var (p, h) = pl.At(15);
            Assert.Equal(10, p.X, 6); Assert.Equal(5, p.Y, 6);
            Assert.Equal(Math.PI / 2, h, 6);
            var loop = new Polyline(new[] { new Vec3(0, 0, 0), new Vec3(1, 0, 0), new Vec3(1, 1, 0), new Vec3(0, 1, 0) }, closed: true);
            Assert.Equal(4, loop.Length, 6);
            Assert.Equal(loop.At(0.5).Pos.X, loop.At(4.5).Pos.X, 6);
        }
    }
}
