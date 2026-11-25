using System;
using System.IO;
using System.Linq;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    /// <summary>Karn Ashur (kind "metropolis"): its instance table, its basin on the Known World (on a stand-in relief: the
    /// old cone on a 575 m plain, as the baked map has it) and the High Dunes' rivers graded downhill.</summary>
    public class BasinTests
    {
        static readonly double[] Bounds = { -185, -62, 500, 295 };
        const double UnitM = 16093.44, Exag = 15, Cx = 93.50045, Cy = 23.20162;
        static readonly Lazy<CityManifest> Ka = new(() => CityManifest.Load(Path.Combine(Repo.Cities, "karn_ashur", "city.json")));

        static double U(double m) => m / UnitM * Exag;

        /// <summary>A desert plain at 575 m rising to the east, the old 3,600 m cone at the settlement, and a bump of 40 m
        /// that the rivers must cut through.</summary>
        static (float[] H, int W, int Hh) Relief()
        {
            int w = 1370, h = 714;
            var a = new float[w * h];
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                {
                    double x = Bounds[0] + i / (double)(w - 1) * 685, y = Bounds[3] - j / (double)(h - 1) * 357;
                    double r = Math.Sqrt((x - Cx) * (x - Cx) + (y - Cy) * (y - Cy));
                    double e = (x - 104) * (x - 104) + (y - 26) * (y - 26);                       // the eastern massif
                    double m = 575 + 1500 * Math.Exp(-e / 10.0) + 3000 * Math.Exp(-r * r / 2.0) + 40 * Math.Exp(-Math.Pow((y - 40) / 0.6, 2));
                    if (y > 58) m = -40;                                                     // the Gulf of Qamar
                    a[j * w + i] = (float)U(m);
                }
            return (a, w, h);
        }

        static BasinSite Site(ReliefSampler rs)
        {
            var m = Ka.Value;
            var th = m.TerrainHeight;
            var hm = BasinSite.FromGrid(m.Terrain, m.ModelScale, th.ModelVex, th.ModelDatumM);
            var mini = m.WorldMap.Miniature;
            return new BasinSite(m.Id, m.Site, hm, m.Terrain.N, rs, Cx, Cy, UnitM, Exag, mini.Exaggeration, mini.PatchHalf, m.ModelScale, th.ModelVex, th.ModelDatumM);
        }

        [Fact]
        public void InstanceTableMatchesItsManifest()
        {
            var m = Ka.Value;
            Assert.True(m.IsMetropolis);
            var t = InstanceTable.Load(m.Directory, m.Instances);
            Assert.Equal(m.Instances.Count, t.Count);
            Assert.True(t.CountOf("house") > 40000, $"{t.CountOf("house")} houses");
            foreach (var (kind, id) in m.Instances.Kinds)
                foreach (int i in t.OfKind(kind))
                {
                    Assert.Equal(id, t.Kind(i));
                    Assert.True(t.W(i) > 0 && t.D(i) > 0 && t.H(i) > 0, $"{kind} {i}: {t.W(i)} x {t.D(i)} x {t.H(i)}");
                    Assert.True(Math.Abs(t.X(i)) <= 50.5 && Math.Abs(t.Y(i)) <= 50.5, $"{kind} {i} off the plinth at ({t.X(i)}, {t.Y(i)})");
                }
            var order = t.WindowOrder(t.OfKind("house").First(), 0, 0);
            Assert.InRange(order, 0.01f, 0.98f);
        }

        [Fact]
        public void PrototypesTriangulateWithWindowsAndCourts()
        {
            var m = Ka.Value;
            var house = new ProtoMesh(m.Instances.Protos["house"]);
            Assert.True(house.Triangles >= 26, $"{house.Triangles} triangles");
            int windows = 0, courts = 0;
            for (int v = 0; v < house.Col.Count / 4; v++)
            {
                if (house.Col[4 * v + 3] == 0.5f) windows++;
                if (house.Col[4 * v + 3] == 0f) courts++;
                float nx = house.Nrm[3 * v], ny = house.Nrm[3 * v + 1], nz = house.Nrm[3 * v + 2];
                Assert.InRange(nx * nx + ny * ny + nz * nz, 0.99f, 1.01f);
            }
            Assert.Equal(2 * 2 * 3, windows);                                                // two front windows, two triangles each
            Assert.True(courts >= 6, "the sunken court's floor");
            // every face of the box points outwards (Godot frame: y up), so the roof ring faces up
            var roofUp = Enumerable.Range(0, house.Pos.Count / 3).Any(v => house.Pos[3 * v + 1] > 0.999f && house.Nrm[3 * v + 1] > 0.99f);
            Assert.True(roofUp);
        }

        [Fact]
        public void BasinKeepsThePackagesGroundAndMeetsTheRelief()
        {
            var (a, w, h) = Relief();
            var rs = new ReliefSampler(a, w, h, Bounds, 1024, 534);
            var s = Site(rs);
            Assert.True(s.F >= 4 && s.Half > 2 && s.PatchHalf > s.Half + 0.8);
            // the plinth is the package's own ground: the summit of the First Flame and the city's benches
            var (fx, fy, fh) = s.Place("first_flame");
            Assert.InRange(s.Metres(fh), 3450, 3760);
            Assert.InRange(s.Metres(s.GroundUnits(s.Cx, s.Cy)), 1100, 1500);
            var west = s.Site.Peaks[0];
            var (ex, ey) = s.KmToWorld(s.Site.Peaks[1].At[0], s.Site.Peaks[1].At[1]);
            Assert.True(s.GroundUnits(fx, fy) > s.GroundUnits(ex, ey), "the western peak is the higher");
            Assert.Equal("first_flame", west.Id);
            // the patch meets the relief mesh at its edge, and nothing jumps between
            for (double f = 0; f <= 1.0; f += 0.02)
            {
                double x = s.XMin + f * (s.XMax - s.XMin), y = s.YMin + f * (s.YMax - s.YMin);
                foreach (var (px, py) in new[] { (x, s.YMin), (x, s.YMax), (s.XMin, y), (s.XMax, y) })
                    Assert.Equal(s.Relief.Coarse(px, py), s.MeshUnits(px, py), 9);
            }
            foreach (double yy in new[] { s.Cy - 2.0, s.Cy, s.Cy + 1.5 })
            {
                double prev = s.MeshUnits(s.XMin, yy);
                for (double x = s.XMin + 0.004; x <= s.XMax; x += 0.004)
                {
                    double hgt = s.MeshUnits(x, yy);
                    Assert.True(Math.Abs(hgt - prev) < 0.12, $"step of {hgt - prev:0.000} units at ({x:0.00}, {yy:0.00})");
                    prev = hgt;
                }
            }
            // the outlet's valley runs downhill to the patch's edge
            var outlet = s.OutletPath.Select(p => s.MeshUnits(p.X, p.Y)).ToArray();
            Assert.True(outlet[^1] < outlet[0], "the outlet leaves the plinth downhill");
        }

        [Fact]
        public void HighDunesRiversAreGradedDownhillAndPeopled()
        {
            var (a, w, h) = Relief();
            var pre = new ReliefSampler(a, w, h, Bounds, 1024, 534);
            var s = Site(pre);
            var d = HighDunesData.Load(Path.Combine(Repo.Root, "atlas", "assets", "map", "known_world", "high_dunes.json"));
            var r = new HighDunesRegion(d, UnitM, Exag);
            r.LinkOutlet(s.OutletEnd);
            r.LinkRoad(s.RoadEnd, s.OnPlinth);
            var before = (float[])a.Clone();
            r.EditHeights(a, w, h, Bounds, s.OnPlinth);
            Assert.Equal(5, r.Rivers.Count);                                                  // the outlet's link and four traces
            foreach (var run in r.Rivers)
            {
                for (int k = 1; k < run.BedM.Length; k++)
                    Assert.True(run.BedM[k] <= run.BedM[k - 1] + 1e-9, $"{run.Id} climbs at {k}");
                Assert.True(run.MaxUphillM < 200, $"{run.Id} had to cut {run.MaxUphillM:0} m");
                if (run.ToSea) Assert.True(run.BedM[^1] <= 0, $"{run.Id} reaches the sea");
            }
            Assert.Contains(r.Rivers, run => run.Id == "north_river" && run.MaxUphillM > 30);   // cut through the stand-in bump
            // the summits elsewhere stay below the great peak, and nothing changed under the basin
            double maxElsewhere = 0;
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                {
                    double x = Bounds[0] + i / (double)(w - 1) * 685, y = Bounds[3] - j / (double)(h - 1) * 357;
                    if (s.OnPlinth(x, y)) { Assert.Equal(before[j * w + i], a[j * w + i]); continue; }
                    if (r.RegionWeight(x, y) >= 1) maxElsewhere = Math.Max(maxElsewhere, r.M(a[j * w + i]));
                }
            Assert.True(maxElsewhere <= d.SummitCapM + 1, $"{maxElsewhere:0} m");
            // villages along the valleys with dry ground between them, and the region's people
            var rs = new ReliefSampler(a, w, h, Bounds, 1024, 534);
            r.PlaceSettlements((x, y) => r.M(rs.Fine(x, y)), s.OnPlinth);
            Assert.True(r.Villages.Count > 150, $"{r.Villages.Count} villages");
            foreach (var v in r.Villages)
                Assert.True(r.Villages.Count(o => Math.Abs(o.X - v.X) + Math.Abs(o.Y - v.Y) < 0.15) == 1, "villages crowd each other");
            Assert.InRange(r.Population, 200000, 420000);
            Assert.True(r.Corridor[^1] == s.RoadEnd && r.Corridor.Length > 5, "the caravan corridor reaches the basin's road");
            Assert.Equal(6, r.Towns.Count);
        }
    }
}
