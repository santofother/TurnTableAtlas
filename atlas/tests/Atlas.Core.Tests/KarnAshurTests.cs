using System;
using System.Linq;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    /// <summary>Karn Ashur's hero patch (W5) on a stand-in relief: a cone under the settlement, like the baked map's.</summary>
    public class KarnAshurTests
    {
        static readonly double[] Bounds = { -185, -62, 500, 295 };
        const double Cx = 93.50045, Cy = 23.18162, UnitM = 16093.44, Exag = 15;
        static readonly Lazy<KarnAshurSite> Shared = new(Make);

        static KarnAshurSite Make()
        {
            int w = 1370, h = 714;
            var a = new float[w * h];
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                {
                    double x = Bounds[0] + (i + 0.5) / w * 685, y = Bounds[3] - (j + 0.5) / h * 357;
                    double d = Math.Sqrt((x - Cx + 0.8) * (x - Cx + 0.8) + (y - Cy - 1.2) * (y - Cy - 1.2));
                    a[j * w + i] = (float)(0.5 + 4.3 * Math.Max(0, 1 - d / 5.0));
                }
            return new KarnAshurSite(new ReliefSampler(a, w, h, Bounds, 1024, 534), Cx, Cy, UnitM, Exag);
        }

        [Fact]
        public void PatchMeetsTheReliefMeshAtItsEdge()
        {
            var s = Shared.Value;
            Assert.True(s.XMax - s.XMin > 2 * KarnAshurSite.PatchHalf && s.YMax - s.YMin > 2 * KarnAshurSite.PatchHalf);
            for (double f = 0; f <= 1.0; f += 0.01)
            {
                double x = s.XMin + f * (s.XMax - s.XMin), y = s.YMin + f * (s.YMax - s.YMin);
                foreach (var (px, py) in new[] { (x, s.YMin), (x, s.YMax), (s.XMin, y), (s.XMax, y) })
                    Assert.Equal(s.Relief.Coarse(px, py), s.MeshUnits(px, py), 9);
            }
            // no cliff-sized jumps where the basin hands over to the relief
            double prev = s.MeshUnits(s.XMin, s.Cy);
            for (double x = s.XMin + 0.005; x <= s.XMax; x += 0.005)
            {
                double hgt = s.MeshUnits(x, s.Cy);
                Assert.True(Math.Abs(hgt - prev) < 0.2, $"jump of {hgt - prev:0.000} units at x {x:0.000}");
                prev = hgt;
            }
        }

        [Fact]
        public void TheBasinIsShelteredButForTheSouthernPass()
        {
            var s = Shared.Value;
            Assert.InRange(s.GroundM(0.5, 0.02), KarnAshurSite.FloorM - 30, KarnAshurSite.FloorM + 30);
            Assert.True(s.GroundM(0.16, 0) < KarnAshurSite.WaterM, "the lake");
            Assert.True(s.GroundM(0, 0) > KarnAshurSite.WaterM, "the island");
            for (int deg = 0; deg < 360; deg += 10)
            {
                double th = deg * Math.PI / 180, top = 0;
                for (double r = 0.9; r < 2.4; r += 0.01) top = Math.Max(top, s.GroundM(r * Math.Cos(th), r * Math.Sin(th)));
                if (Math.Abs(deg - KarnAshurSite.PassDeg) < 10) continue;
                Assert.True(top > KarnAshurSite.FloorM + 150, $"rim at {deg}° only {top:0} m");
                if (deg is >= 60 and <= 120) Assert.True(top > 4000, $"northern wall at {deg}° only {top:0} m");
            }
        }

        [Fact]
        public void TheSouthernPassOpensTheValley()
        {
            var s = Shared.Value;
            double th = KarnAshurSite.PassDeg * Math.PI / 180, top = 0;
            for (double r = 0.9; r < 2.0; r += 0.01) top = Math.Max(top, s.GroundM(r * Math.Cos(th), r * Math.Sin(th)));
            Assert.True(top < KarnAshurSite.FloorM + 150, $"the pass is closed at {top:0} m");
        }

        [Fact]
        public void SwitchbackRoadClimbsToTheTemple()
        {
            var s = Shared.Value;
            Assert.Equal(KarnAshurSite.ShrineM, s.GroundM(s.ShrineX, s.ShrineY), 1);
            var road = s.Road;
            Assert.True(s.GroundM(road[0].X, road[0].Y) < KarnAshurSite.FloorM + 80, "starts on the valley floor");
            var end = road[^1];
            Assert.True(Math.Sqrt(Math.Pow(end.X - s.ShrineX, 2) + Math.Pow(end.Y - s.ShrineY, 2)) < KarnAshurSite.SummitR);
            int turns = 0;
            double lastSide = 0, prevH = s.GroundM(road[0].X, road[0].Y);
            double a0 = Math.Atan2(-s.ShrineY, -s.ShrineX);
            foreach (var p in road)
            {
                double h = s.GroundM(p.X, p.Y);
                Assert.True(h > prevH - 8, $"road drops from {prevH:0} to {h:0} m");
                prevH = Math.Max(prevH, h);
                double side = Math.Sign(KarnAshurSite.Wrap(Math.Atan2(p.Y - s.ShrineY, p.X - s.ShrineX) - a0));
                if (side != 0 && lastSide != 0 && side != lastSide) turns++;
                if (side != 0) lastSide = side;
            }
            Assert.True(turns >= 6, $"{turns} switchbacks");
        }

        [Fact]
        public void CityPartsStandWhereTheyShould()
        {
            var s = Shared.Value;
            Assert.True(s.Buildings.Count > 2500, $"{s.Buildings.Count} buildings");
            Assert.True(s.Trees.Count > 1500, $"{s.Trees.Count} trees");
            Assert.Equal(4, s.Gates.Count);
            Assert.True(s.WallTowers.Count >= 36);
            Assert.Equal(3, s.Ziggurats.Count);
            Assert.Equal(6, s.Falls.Count);
            foreach (var b in s.Buildings)
            {
                double r = Math.Sqrt(b.X * b.X + b.Y * b.Y), th = Math.Atan2(b.Y, b.X);
                Assert.True(r > s.Shore(th) + 0.01, "no building in the lake");
                Assert.InRange(b.Z, KarnAshurSite.FloorM - 30, KarnAshurSite.FloorM + 450);
                if (b.Kind is KarnAshurSite.Kind.House or KarnAshurSite.Kind.Tower)
                    Assert.False(s.Blocked(b.X, b.Y, 0), $"house in a street at ({b.X:0.000}, {b.Y:0.000})");
            }
            Assert.Equal(3, s.Aqueducts.Count);
            foreach (var a in s.Aqueducts)
            {
                double r0 = Math.Sqrt(a[0].X * a[0].X + a[0].Y * a[0].Y), r1 = Math.Sqrt(a[^1].X * a[^1].X + a[^1].Y * a[^1].Y);
                Assert.True(r0 > s.Outer(Math.Atan2(a[0].Y, a[0].X)) + 0.03, "aqueducts start in the fields");
                Assert.InRange(r1, KarnAshurSite.WallR, KarnAshurSite.WallR + 0.012);
            }
        }

        [Fact]
        public void LayoutTextureIsPaintedAndRepeatable()
        {
            var s = Shared.Value;
            const int res = 1024;
            var img = s.PaintLayout(res);
            byte At(double lx, double ly, int ch)
            {
                int x = (int)((lx + KarnAshurSite.FineHalf) / (2 * KarnAshurSite.FineHalf) * res);
                int y = (int)((KarnAshurSite.FineHalf - ly) / (2 * KarnAshurSite.FineHalf) * res);
                return img[(y * res + x) * 4 + ch];
            }
            Assert.Equal(255, At(0.0, 0.0, 2));                 // the island is paved
            Assert.Equal(255, At(0.16, 0.0, 0));                // the lake
            Assert.True(At(0.0, -0.52, 3) > 200, "the south avenue");
            Assert.Equal(255, At(0.43, 0.20, 2));               // the outer city
            int fields = 0;
            for (int i = 0; i < img.Length; i += 4) if (img[i + 1] is > 0 and <= 200) fields++;
            Assert.True(fields > res * res / 20, $"{fields} field pixels");
            Assert.Equal(img, Make().PaintLayout(res));
        }
    }
}
