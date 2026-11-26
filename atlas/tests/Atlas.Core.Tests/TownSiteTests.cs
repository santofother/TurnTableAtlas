using System;
using System.Collections.Generic;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    /// <summary>A town miniature laid onto the Known World relief (Corivessa Port, Corivessa).</summary>
    public class TownSiteTests
    {
        const double UnitM = 16093.44, Half = 50;

        /// <summary>A model ground: a hill in the middle (4 m high), sea below y = -30.</summary>
        static double ModelZ(double x, double y) => y < -30 ? -1 : 4 * Math.Exp(-(x * x + y * y) / 200);

        static TerrainGrid Grid()
        {
            var pts = new List<(double, double, double)>();
            for (double x = -Half; x <= Half; x += 0.5)
                for (double y = -Half; y <= Half; y += 0.5) pts.Add((x, y, ModelZ(x, y)));
            return TownSite.GridFromPoints(pts, Half, 101);
        }

        /// <summary>Relief: land rising east at 0.05 units per unit north of y = 99.9, sea south of it.</summary>
        static double Relief(double x, double y) => y < 99.9 ? -0.2 : 0.1 + 0.05 * (x - 100);

        static TownSite Site() => new("t", Relief, 100, 100, UnitM, 15, Half, Grid(), 5);

        [Fact]
        public void ScaleAndSquareFollowTheModelAndTheExaggeration()
        {
            var s = Site();
            Assert.Equal(15 * 5 / UnitM, s.S, 12);
            Assert.Equal(Half * s.S, s.Half, 12);
            Assert.True(s.Contains(100 + s.Half * 0.99, 100));
            Assert.False(s.Contains(100 + s.Half * 1.01, 100));
        }

        [Fact]
        public void GridFromPointsKeepsTheModelGround()
        {
            var g = Grid();
            Assert.Equal(4, g.At(0, 0, Half), 1);   // the nearest vertices averaged
            Assert.Equal(-1, g.At(10, -40, Half), 6);
            // a grid with gaps is filled from its neighbours
            var sparse = TownSite.GridFromPoints(new[] { (-50.0, -50.0, 2.0), (50.0, 50.0, 2.0) }, Half, 9);
            Assert.All(sparse.Z, z => Assert.Equal(2, z, 9));
        }

        [Fact]
        public void BuildingsKeepTheirHeightAboveTheGroundOnTheRelief()
        {
            var s = Site();
            // a 2 m wall at the edge of the square (no model hill there): it stands 2 m (scaled) above the relief
            var foot = s.Place(45, 20, ModelZ(45, 20));
            var top = s.Place(45, 20, ModelZ(45, 20) + 2);
            Assert.Equal(Relief(foot.X, foot.Y) + TownSite.Lift, foot.H, 4);
            Assert.Equal(2 * s.S, top.H - foot.H, 9);
            // on the hilltop the model's own hill stands above the relief
            var hill = s.Place(0, 0, ModelZ(0, 0));
            Assert.Equal(Relief(hill.X, hill.Y) + TownSite.Lift + 4 * s.S, hill.H, 4);
            Assert.Equal(hill.H, s.GroundAt(100, 100).Value, 4);
        }

        [Fact]
        public void ShipsFloatAtSeaLevelOverTheMapsWater()
        {
            var s = Site();
            // the model's sea (ground -1 m) over the map's sea: a hull's waterline is at the map's sea level
            var w = s.Place(0, -40, 0);
            Assert.True(w.Y < 99.9);
            Assert.Equal(TownSite.Lift, w.H, 9);
            Assert.True(s.Place(0, -40, -1).H < w.H);   // the model's seabed lies under the water
            Assert.Null(s.GroundAt(100, 100 + s.Half * 1.5));
        }

        [Fact]
        public void CountrysideThinsOutTowardsTheEdge()
        {
            var s = Site();
            int Kept(double r0, double r1)
            {
                int n = 0;
                for (double x = -Half; x < Half; x += 0.37)
                    for (double y = -Half; y < Half; y += 0.37)
                    {
                        double r = s.Rim(x, y);
                        if (r >= r0 && r < r1 && s.KeepAtEdge(x, y)) n++;
                    }
                return n;
            }
            int Total(double r0, double r1) { int n = 0; for (double x = -Half; x < Half; x += 0.37) for (double y = -Half; y < Half; y += 0.37) { double r = s.Rim(x, y); if (r >= r0 && r < r1) n++; } return n; }
            Assert.Equal(Total(0, TownSite.ThinFrom), Kept(0, TownSite.ThinFrom));     // the town itself is whole
            double mid = (TownSite.ThinFrom + TownSite.ThinTo) / 2;
            double share = Kept(mid - 0.02, mid + 0.02) / (double)Total(mid - 0.02, mid + 0.02);
            Assert.InRange(share, 0.3, 0.7);
            Assert.Equal(0, Kept(TownSite.ThinTo, 2));
        }
    }
}
