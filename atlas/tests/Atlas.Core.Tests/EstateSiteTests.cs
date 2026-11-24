using System;
using System.Linq;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    /// <summary>An estate's hero patch (Landric's villa) on a stand-in relief: a gentle slope, as on the upland north of
    /// Calderra, and a small model terrain grid with a lake below 0 in one corner.</summary>
    public class EstateSiteTests
    {
        static readonly double[] Bounds = { -185, -62, 500, 295 };
        const double Cx = 107.65, Cy = 147.95, UnitM = 16093.44, Exag = 15, ModelScale = 3, ModelHalf = 50, Mini = 12;
        static readonly Lazy<EstateSite> Shared = new(Make);

        static TerrainGrid Grid()
        {
            int n = 17;
            var z = new double[n * n];
            for (int j = 0; j < n; j++)
                for (int i = 0; i < n; i++)
                {
                    double x = -50 + 100.0 * i / (n - 1), y = -50 + 100.0 * j / (n - 1);
                    double lake = Math.Sqrt((x - 24) * (x - 24) + (y - 21) * (y - 21));
                    z[j * n + i] = lake < 16 ? -1.0 : 2.0 + 0.04 * Math.Max(0, -x);
                }
            return new TerrainGrid { N = n, Z = z };
        }

        static EstateSite Make()
        {
            int w = 1370, h = 714;
            var a = new float[w * h];
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                {
                    double x = Bounds[0] + (i + 0.5) / w * 685, y = Bounds[3] - (j + 0.5) / h * 357;
                    a[j * w + i] = (float)(0.25 + 0.02 * (y - Cy) - 0.01 * (x - Cx) + 0.01 * Math.Sin(x * 3.1));
                }
            return new EstateSite("landric_villa", new ReliefSampler(a, w, h, Bounds, 1024, 534), Cx, Cy, UnitM, Exag, ModelScale, ModelHalf, Grid(), Mini, 0.36);
        }

        [Fact]
        public void PatchMeetsTheReliefMeshAtItsEdge()
        {
            var s = Shared.Value;
            Assert.True(s.XMax - s.XMin >= 2 * s.PatchHalf && s.YMax - s.YMin >= 2 * s.PatchHalf);
            for (double f = 0; f <= 1.0; f += 0.01)
            {
                double x = s.XMin + f * (s.XMax - s.XMin), y = s.YMin + f * (s.YMax - s.YMin);
                foreach (var (px, py) in new[] { (x, s.YMin), (x, s.YMax), (s.XMin, y), (s.XMax, y) })
                    Assert.Equal(s.Relief.Coarse(px, py), s.MeshUnits(px, py), 9);
            }
            double prev = s.MeshUnits(s.XMin, s.Cy);
            for (double x = s.XMin + 0.002; x <= s.XMax; x += 0.002)
            {
                double hgt = s.MeshUnits(x, s.Cy);
                Assert.True(Math.Abs(hgt - prev) < 0.01, $"step of {hgt - prev:0.0000} units at x {x:0.000}");
                prev = hgt;
            }
        }

        [Fact]
        public void PlinthIsTheModelsOwnGroundAtTheMiniaturesScale()
        {
            var s = Shared.Value;
            Assert.Equal(ModelScale * Mini / UnitM, s.S, 12);
            Assert.Equal(ModelHalf * s.S, s.Half, 12);
            var g = Grid();
            foreach (var (mx, my) in new[] { (0.0, 0.0), (-40.0, 30.0), (24.0, 21.0), (45.0, -45.0) })
            {
                var (x, y, hb) = s.FromModel(mx, my, g.At(mx, my, ModelHalf));
                Assert.True(s.OnPlinth(x, y));
                Assert.Equal(hb, s.GroundUnits(x, y), 9);
                Assert.Equal(hb, s.MeshUnits(x, y), 9);
                var (bx, by) = s.ToModel(x, y);
                Assert.Equal(mx, bx, 9);
                Assert.Equal(my, by, 9);
            }
            // the lake lies below the model's zero, which is the patch's Base; the land stands above it
            Assert.True(s.GroundUnits(s.FromModel(24, 21, 0).X, s.FromModel(24, 21, 0).Y) < s.Base);
            Assert.True(s.GroundUnits(s.Cx, s.Cy) > s.Base);
        }

        [Fact]
        public void EstateIsSmallAndItsRimSitsOnTheRelief()
        {
            var s = Shared.Value;
            Assert.InRange(s.Half * 2, 0.15, 0.35);            // a villa: a few km of miniature, not a city
            Assert.InRange(s.PatchHalf, 0.6, 1.2);
            double rim = Enumerable.Range(0, 40).Select(k => { double a = k * Math.PI / 20; return s.GroundUnits(s.Cx + s.Half * Math.Cos(a), s.Cy + s.Half * Math.Sin(a)); }).Average();
            Assert.True(Math.Abs(rim - s.Broad(s.Cx, s.Cy)) < 0.03, $"rim {rim:0.000} vs relief {s.Broad(s.Cx, s.Cy):0.000}");
            Assert.True(s.Contains(s.Cx, s.Cy) && !s.Contains(s.Cx + 2 * s.PatchHalf, s.Cy));
        }
    }
}
