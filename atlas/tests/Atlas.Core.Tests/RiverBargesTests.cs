using System;
using System.IO;
using System.Linq;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    /// <summary>River barges (RiverBarges): laden downstream, empty upstream, one lane each side of the middle, never
    /// closer than a lane's minimum gap, and always on the water.</summary>
    public class RiverBargesTests
    {
        /// <summary>A winding river, source at y -40 to the sea at y 40, 2.8 units wide.</summary>
        static ((double X, double Y) P, double W)[] Winding() =>
            Enumerable.Range(0, 161).Select(k => { double y = -40 + k * 0.5; return ((6 * Math.Sin(y / 9.0), y), 2.8); }).ToArray();

        static double DistTo((double X, double Y)[] line, double x, double y)
        {
            double best = double.MaxValue;
            for (int i = 0; i + 1 < line.Length; i++)
            {
                var (a, b) = (line[i], line[i + 1]);
                double dx = b.X - a.X, dy = b.Y - a.Y, t = Math.Clamp(((x - a.X) * dx + (y - a.Y) * dy) / Math.Max(1e-12, dx * dx + dy * dy), 0, 1);
                best = Math.Min(best, Math.Sqrt(Math.Pow(x - a.X - t * dx, 2) + Math.Pow(y - a.Y - t * dy, 2)));
            }
            return best;
        }

        [Fact]
        public void LanesKeepTheirGapsAndTheirSides()
        {
            var river = Winding();
            var lanes = RiverBarges.Lanes(river, 0.5, new BargeSpec(0.06, 30, 1.6, 0.17, 0.24, 0.03, 3), new BargeSpec(0.04, 24, 1.6, 0.15, 0.22, 0.03, 5));
            var down = lanes.Single(l => l.Laden);
            var up = lanes.Single(l => !l.Laden);
            Assert.Equal(30, down.Count);
            Assert.True(down.Path.P[0].Y < down.Path.P[^1].Y, "laden barges head for the sea");
            Assert.True(up.Path.P[0].Y > up.Path.P[^1].Y, "empty barges head upstream");
            var centre = river.Select(r => r.P).ToArray();
            for (double t = 0; t < 3000; t += 7.3)
            {
                Assert.True(RiverBarges.MinSpacing(lanes, t) > 0.6, $"two barges {RiverBarges.MinSpacing(lanes, t):0.00} apart at t {t}");
                foreach (var l in lanes)
                {
                    // within a lane the gap along the river never drops below the minimum: the barges never close up
                    var s = Enumerable.Range(0, l.Count).Select(k => l.ArcAt(k, t)).OrderBy(v => v).ToArray();
                    for (int k = 0; k < s.Length; k++)
                    {
                        double gap = (k + 1 < s.Length ? s[k + 1] : s[0] + l.Loop) - s[k];
                        Assert.True(gap >= l.MinGap - 1e-9, $"{l.Id}: gap {gap:0.000} at t {t}");
                    }
                    foreach (var b in l.All(t).Where(b => b.Visible))
                    {
                        double d = DistTo(centre, b.X, b.Y);
                        Assert.True(d > 0.35 && d < 1.4 - b.Length * 0.15, $"{l.Id} barge {d:0.00} off the middle");
                        // heading along the lane's direction of travel
                        double dir = l.Laden ? 1 : -1;
                        Assert.True(Math.Sin(b.Heading) * dir > 0.3, $"{l.Id} heading {b.Heading:0.00}");
                    }
                }
            }
            // laden on the right of the middle looking downstream (east of a river flowing north), empty on the left
            var bd = down.At(0, 0); var bu = up.At(0, 0);
            Assert.True(bd.X > 6 * Math.Sin(bd.Y / 9.0) && bu.X < 6 * Math.Sin(bu.Y / 9.0));
            // they move: a barge a minute later is further on
            var b0 = down.At(1, 100); var b1 = down.At(1, 160);
            if (b0.Visible && b1.Visible) Assert.True(b1.Y > b0.Y);
        }

        [Fact]
        public void ALaneRefusesBargesThatWouldOverlap()
        {
            Assert.Throws<ArgumentException>(() => new BargeLane("x", new[] { (0.0, 0.0), (0.0, 10.0) }, true, 1, 5, 0.2, 0.2, 0.3));
            var crowded = new BargeLane("x", new[] { (0.0, 0.0), (0.0, 10.0) }, true, 1, 500, 1.0, 0.2, 0.3);
            Assert.True(crowded.Count <= 11, "no more barges than the lane holds at the minimum gap");
        }

        [Fact]
        public void HavensLanesComeFromTheGenerator()
        {
            var m = CityManifest.Load(Path.Combine(Repo.Cities, "haven", "city.json"));
            var rt = m.RiverTraffic;
            Assert.NotNull(rt);
            var lanes = rt.Build();
            Assert.Equal(2, lanes.Length);
            Assert.Contains(lanes, l => l.Laden && l.Path.P[0].Y < l.Path.P[^1].Y);    // the Flame flows north
            Assert.Contains(lanes, l => !l.Laden && l.Path.P[0].Y > l.Path.P[^1].Y);
            Assert.True(lanes.Sum(l => l.Count) >= 24, $"{lanes.Sum(l => l.Count)} barges");
            var protos = m.Instances.Protos;
            Assert.True(protos.ContainsKey("barge_grain") && protos.ContainsKey("barge_empty"));
            double longest = lanes.Max(l => rt.Lanes.First(d => d.Id == l.Id).Length[1]);
            for (double t = 0; t < 4000; t += 13.7)
                Assert.True(RiverBarges.MinSpacing(lanes, t) > 1.5 * longest, $"barges {RiverBarges.MinSpacing(lanes, t):0.00} apart at t {t}");
        }
    }
}
