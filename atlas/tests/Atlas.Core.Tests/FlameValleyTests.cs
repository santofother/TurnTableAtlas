using System;
using System.IO;
using System.Linq;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    /// <summary>Haven (a floodplain "metropolis" from generator/rivercity.py) on the Known World, the red River Flame and its
    /// farmland (FlameValleyRegion over known_world/flame_valley.json), and the port at the river's mouth (a kw_xy pin).
    /// The relief is a stand-in: a 10 m floodplain rising to 300 m desert away from the river, the sea north of y 86.</summary>
    public class FlameValleyTests
    {
        static readonly double[] Bounds = { -185, -62, 500, 295 };
        const double UnitM = 16093.44, Exag = 15, Cx = 177.0, Cy = 63.2;
        static readonly Lazy<CityManifest> Haven = new(() => CityManifest.Load(Path.Combine(Repo.Cities, "haven", "city.json")));
        static readonly Lazy<FlameValleyData> Data = new(() => FlameValleyData.Load(Path.Combine(Repo.Root, "atlas", "assets", "map", "known_world", "flame_valley.json")));

        static double U(double m) => m / UnitM * Exag;
        static double M(double u) => u * UnitM / Exag;

        static double Metres(double x, double y) => y > 86.0 + 0.4 * Math.Sin(x) ? -30 : 10 + 290 * Math.Clamp((Math.Abs(x - 178 - 0.12 * (60 - y)) - 4) / 6, 0, 1);

        static ReliefSampler Relief()
        {
            int w = 1370, h = 714;
            var a = new float[w * h];
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                    a[j * w + i] = (float)U(Metres(Bounds[0] + i / (double)(w - 1) * 685, Bounds[3] - j / (double)(h - 1) * 357));
            return new ReliefSampler(a, w, h, Bounds, 1024, 534);
        }

        static BasinSite Site(ReliefSampler rs)
        {
            var m = Haven.Value;
            var th = m.TerrainHeight;
            var hm = BasinSite.FromGrid(m.Terrain, m.ModelScale, th.ModelVex, th.ModelDatumM);
            var mini = m.WorldMap.Miniature;
            return new BasinSite(m.Id, m.Site, hm, m.Terrain.N, rs, Cx, Cy, UnitM, Exag, mini.Exaggeration, mini.PatchHalf, m.ModelScale, th.ModelVex, th.ModelDatumM);
        }

        [Fact]
        public void HavenIsAFloodplainCapitalWithThreePyramids()
        {
            var m = Haven.Value;
            Assert.True(m.IsMetropolis && m.Site.IsFloodplain);
            Assert.Empty(m.Site.Peaks);
            Assert.Equal(3, m.Anchors.Keys.Count(k => k.EndsWith("_pyramid")));
            var t = InstanceTable.Load(m.Directory, m.Instances);
            Assert.True(t.CountOf("house") + t.CountOf("roofhouse") > 40000);
            Assert.True(t.CountOf("marble") >= 18 && t.CountOf("boat") > 100 && t.CountOf("silo") > 20);
            // the pyramids are white marble and the tallest things in the city
            double top = m.Anchors["great_pyramid"][2] * m.ModelScale;
            Assert.True(top > 150, $"the Great Pyramid's summit {top:0} m");
            foreach (int i in t.OfKind("marble")) { var c = t.Srgb(i); Assert.True(c.R > 0.85 && c.G > 0.85 && c.B > 0.8); }
            Assert.True(m.Site.WaterColour[0] > 2 * m.Site.WaterColour[2], "the River Flame runs red");
        }

        [Fact]
        public void HavensPatchCarriesTheRiverAcrossItsRing()
        {
            var rs = Relief();
            var s = Site(rs);
            Assert.True(s.Floodplain);
            Assert.True(s.InletPath.Length > 2 && s.OutletPath.Length > 2);
            // the river comes in at the patch's south edge and reaches the plinth's south edge at the package's inlet
            Assert.True(s.InletPath[0].Y < s.Cy - s.Half && s.InletPath[^1].Y <= s.Cy - s.Half + 1e-6);
            Assert.True(s.OutletPath[0].Y >= s.Cy + s.Half - 1e-6 && s.OutletPath[^1].Y > s.Cy + s.Half);
            // no mountain spurs: the ring stays close to the plain
            double hiRing = 0;
            for (int k = 0; k < 200; k++)
            {
                double a = k * Math.PI / 100, r = s.Half + 0.5 * (s.PatchHalf - s.Half);
                hiRing = Math.Max(hiRing, M(s.GroundUnits(s.Cx + r * Math.Cos(a), s.Cy + r * Math.Sin(a))));
            }
            Assert.True(hiRing < 120, $"the ring rises to {hiRing:0} m");
            // the patch meets the relief mesh at its edge
            for (int k = 0; k <= 20; k++)
            {
                double x = s.XMin + (s.XMax - s.XMin) * k / 20.0;
                Assert.True(Math.Abs(s.MeshUnits(x, s.YMax) - rs.Coarse(x, s.YMax)) < 1e-6);
            }
            // joined to the relief's own river where it crosses the edge
            s.SetRiverEnds((s.Cx + 0.3, s.YMin - 0.2), (s.Cx - 0.2, s.YMax + 0.2));
            Assert.Equal(s.Cx + 0.3, s.InletPath[0].X, 6);
            Assert.Equal(s.Cx - 0.2, s.OutletPath[^1].X, 6);
        }

        [Fact]
        public void TheFlameIsRedAndFarmedOnBothBanks()
        {
            var rs = Relief();
            var s = Site(rs);
            var r = new FlameValleyRegion(Data.Value, UnitM, Exag);
            var ends = r.LinkPatch(s.Contains);
            Assert.NotNull(ends);
            Assert.False(s.Contains(ends.Value.Up.X, ends.Value.Up.Y));
            Assert.False(s.Contains(ends.Value.Down.X, ends.Value.Down.Y));
            Assert.True(ends.Value.Up.Y < s.YMin + 0.3 && ends.Value.Down.Y > s.YMax - 0.3);
            s.SetRiverEnds(ends.Value.Up, ends.Value.Down);
            r.AddJoin("join_in", s.InletPath);
            r.AddJoin("join_out", s.OutletPath);
            Assert.DoesNotContain(r.Reaches, q => q.Id == "trunk");
            Assert.True(r.Reaches.Count(q => q.Id.EndsWith("_arm")) == 4);
            Assert.All(r.Reaches.Where(q => q.Id.StartsWith("trunk")).SelectMany(q => q.Pts), p => Assert.False(s.Contains(p.X, p.Y)));
            // farmland: none on the river, a belt along it, desert beyond, the delta all farmed
            var (x45, y45) = r.Trunk.OrderBy(p => Math.Abs(p.Y - 45)).First();
            Assert.Equal(0, r.FieldWeight(x45, y45, 10));
            Assert.True(r.FieldWeight(x45 + 0.45, y45, 10) > 0.8 && r.FieldWeight(x45 - 0.45, y45, 10) > 0.8);
            Assert.Equal(0, r.FieldWeight(x45 + 3.0, y45, 10));
            Assert.True(r.InDelta(176.5, 78) && r.FieldWeight(178.0, 79.0, 5) > 0.8);
            Assert.Equal(0, r.FieldWeight(178.0, 79.0, -5));                                  // not the sea
            // villages on both banks, none in the patch, the river or the sea
            r.PlaceSettlements(Metres, (_, _) => false);
            Assert.True(r.Villages.Count > 400, $"{r.Villages.Count} villages");
            int east = 0, west = 0;
            foreach (var v in r.Villages)
            {
                Assert.False(s.Contains(v.X, v.Y));
                Assert.True(Metres(v.X, v.Y) > 0);
                var (d, dx, dy, _) = r.Nearest(v.X, v.Y);
                Assert.True(d > FlameValleyRegion.ArmWidth / 2, $"village in the river at ({v.X:0.00}, {v.Y:0.00})");
                var (tx, ty) = r.Trunk.OrderBy(p => Math.Abs(p.Y - v.Y)).First();
                if (v.Y < 60) { if (v.X > tx) east++; else west++; }
            }
            Assert.True(east > 60 && west > 60, $"villages east {east}, west {west} of the upper river");
            Assert.True(r.Population > 400000, $"{r.Population} people in the valley");
            // the albedo: red on the river, green beside it
            int w = 6144, hh = 3202;
            var rgba = new byte[w * hh * 4];
            for (int i = 0; i < rgba.Length; i += 4) { rgba[i] = 215; rgba[i + 1] = 170; rgba[i + 2] = 120; rgba[i + 3] = 255; }
            r.PaintAlbedo(rgba, w, hh, Bounds, Metres, s.OnPlinth);
            (byte R, byte G, byte B) Px(double x, double y)
            {
                int i = (int)((x - Bounds[0]) / 685 * w), j = (int)((Bounds[3] - y) / 357 * hh);
                int o = (j * w + i) * 4;
                return (rgba[o], rgba[o + 1], rgba[o + 2]);
            }
            var river = Px(x45, y45);
            Assert.True(river.R > 1.6 * river.G && river.R > 2 * river.B, $"river pixel {river}");
            var field = Px(x45 + 0.5, y45);
            Assert.True(field.G > field.B + 30, $"field pixel {field}");
            var desert = Px(x45 + 4, y45);
            Assert.Equal((215, 170, 120), (desert.R, desert.G, desert.B));
        }

        [Fact]
        public void BargesRunTheWholeFlameThroughHaven()
        {
            var rs = Relief();
            var s = Site(rs);
            var r = new FlameValleyRegion(Data.Value, UnitM, Exag);
            var ends = r.LinkPatch(s.Contains).Value;
            s.SetRiverEnds(ends.Up, ends.Down);
            var river = r.BargeRiver(s);
            Assert.Equal(r.Trunk[0], river[0].P);
            Assert.Equal(Data.Value.Trunk[^1][1], river[^1].P.Y, 6);
            Assert.Contains(river, q => s.OnPlinth(q.P.X, q.P.Y) && q.W > 0.15);      // across the plinth on Haven's own river
            double k = s.SModel / Haven.Value.ModelScale;                                       // metres -> units at the miniature's scale
            var lanes = r.Barges(s, k);
            var down = lanes.Single(l => l.Laden);
            Assert.True(down.Path.P[^1].Y > 86 && lanes.Single(l => !l.Laden).Path.P[^1].Y < 20, "grain down to the sea, empties back up");
            Assert.True(down.Count > 100);
            var fine = RiverBarges.Resample(river, 0.004);
            for (double t = 0; t < 20000; t += 1111)
            {
                Assert.True(RiverBarges.MinSpacing(lanes, t) > 80 * k, $"barges {RiverBarges.MinSpacing(lanes, t) / k:0} m apart");
                foreach (var b in lanes.SelectMany(l => l.All(t)).Where(b => b.Visible).Take(400))
                {
                    var near = fine.OrderBy(q => Math.Abs(q.P.X - b.X) + Math.Abs(q.P.Y - b.Y)).First();
                    double d = Math.Sqrt(Math.Pow(near.P.X - b.X, 2) + Math.Pow(near.P.Y - b.Y, 2));
                    Assert.True(d < near.W / 2, $"barge off the water at ({b.X:0.00}, {b.Y:0.00}): {d:0.000} from the middle, half-width {near.W / 2:0.000}");
                }
            }
        }

        [Fact]
        public void ThePortStandsAtTheMouth()
        {
            var m = CityManifest.Load(Path.Combine(Repo.Cities, "flamemouth", "city.json"));
            Assert.False(m.IsMetropolis);
            Assert.Null(m.WorldMap.Settlement);
            var kw = KnownWorldMap.Load(Path.Combine(Repo.Root, "atlas", "assets", "map", "known_world", "known_world.json"));
            var uv = kw.PinFor(m.WorldMap);
            Assert.NotNull(uv);
            var (x, y) = kw.UvToXy(uv.Value.U, uv.Value.V);
            var mouth = Data.Value.Trunk[^1];
            Assert.True(Math.Abs(x - mouth[0]) < 0.6 && Math.Abs(y - mouth[1]) < 0.6, $"pin at ({x:0.00}, {y:0.00}), mouth ({mouth[0]}, {mouth[1]})");
        }
    }
}
