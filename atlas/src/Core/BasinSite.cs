// A metropolis's basin on the Known World (Karn Ashur, generator/metropolis.py): a hero patch that replaces the coarse
// relief round the settlement with the package's own ground, so the map and the city view show one layout.
// Pure layout, no Godot:
//   - the plinth: the package's true heights (terrain_height.png, metres) drawn as a miniature `F` times its true size
//     horizontally and at the relief's own 15x vertically, the package's painted ground on it, its instance table
//     (houses, terraces, trees) re-seated on it.
//   - the ring round the plinth: the plinth's edge carried outwards and eased onto the relief, with the massif's spurs
//     running out, the outlet's valley carrying the rivers on towards the farm belt and the caravan road's grade.
//   - it meets the relief mesh exactly at the patch's edge.
// Lengths are blend units (1 = 10 miles) unless named km; +x east, +y north; heights are blend units.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Atlas.Core
{
    public sealed class BasinSite
    {
        public readonly string Id;
        public readonly double Cx, Cy, UnitM, Exag, F;
        /// <summary>Blend units per kilometre of the package (the miniature's scale), and per model metre.</summary>
        public readonly double S, SModel;
        /// <summary>Half the plinth (blend units) and the patch's half size.</summary>
        public readonly double Half, PatchHalf, HalfKm;
        public const double EdgeBlend = 0.95;
        public readonly ReliefSampler Relief;
        public readonly int I0, I1, J0, J1;
        public readonly double XMin, XMax, YMin, YMax;
        public readonly SiteData Site;
        readonly float[] _m;          // true metres, n x n over the plinth, row 0 to the north
        readonly int _n;
        readonly double _modelScale, _vex, _datum;

        public BasinSite(string id, SiteData site, float[] heightsM, int n, ReliefSampler relief, double cx, double cy,
                         double unitM, double exag, double miniature, double patchHalf, double modelScale, double vex, double datum)
        {
            Id = id; Site = site; _m = heightsM; _n = n; Relief = relief; Cx = cx; Cy = cy; UnitM = unitM; Exag = exag; F = miniature;
            _modelScale = modelScale; _vex = vex; _datum = datum;
            HalfKm = site.PlinthHalfKm;
            S = 1000.0 * F / unitM;
            SModel = modelScale * F / unitM;
            Half = HalfKm * S;
            PatchHalf = Math.Max(patchHalf, Half + 0.9);
            I0 = (int)Math.Floor((cx - PatchHalf - relief.X0) / relief.Dx);
            I1 = (int)Math.Ceiling((cx + PatchHalf - relief.X0) / relief.Dx);
            J0 = (int)Math.Floor((relief.YTop - (cy + PatchHalf)) / relief.Dy);
            J1 = (int)Math.Ceiling((relief.YTop - (cy - PatchHalf)) / relief.Dy);
            XMin = relief.GridX(I0); XMax = relief.GridX(I1);
            YMax = relief.GridY(J0); YMin = relief.GridY(J1);
            BuildRingPaths();
        }

        /// <summary>The package's coarse terrain_grid (model metres, exaggerated) turned back into true metres, row 0 to the
        /// north (for tests and for packages without terrain_height.png).</summary>
        public static float[] FromGrid(TerrainGrid g, double modelScale, double vex, double datum)
        {
            var a = new float[g.N * g.N];
            for (int j = 0; j < g.N; j++)
                for (int i = 0; i < g.N; i++)
                    a[j * g.N + i] = (float)(datum + (g.Z[(g.N - 1 - j) * g.N + i] * modelScale - datum) / vex);
            return a;
        }

        /// <summary>The package's own ground is kept unchanged within this rounded radius (blend units).</summary>
        public double InnerR => 0.9 * Half;
        public bool Contains(double x, double y) => x > XMin && x < XMax && y > YMin && y < YMax;
        public bool OnPlinth(double x, double y) => Math.Abs(x - Cx) <= Half && Math.Abs(y - Cy) <= Half;
        public (double U0, double V0, double U1, double V1) HoleUv =>
            ((I0 + 0.5) / Relief.Nx, (J0 + 0.5) / Relief.Ny, (I1 - 0.5) / Relief.Nx, (J1 - 0.5) / Relief.Ny);

        public double Units(double metres) => metres / UnitM * Exag;
        public double Metres(double units) => units * UnitM / Exag;
        public (double X, double Y) KmToWorld(double lxKm, double lyKm) => (Cx + lxKm * S, Cy + lyKm * S);
        public (double X, double Y) WorldToKm(double x, double y) => ((x - Cx) / S, (y - Cy) / S);
        /// <summary>A model point (metres of the package) on the map.</summary>
        public (double X, double Y) ModelToWorld(double mx, double my) => (Cx + mx * SModel, Cy + my * SModel);

        // ---------------------------------------------------------------- the plinth's own ground

        /// <summary>True elevation (metres) at a point of the plinth (km), clamped to the plinth.</summary>
        public double PlinthMetres(double lxKm, double lyKm)
        {
            double fx = Math.Clamp((lxKm + HalfKm) / (2 * HalfKm) * (_n - 1), 0, _n - 1.000001);
            double fy = Math.Clamp((HalfKm - lyKm) / (2 * HalfKm) * (_n - 1), 0, _n - 1.000001);
            int i = (int)fx, j = (int)fy;
            double tx = fx - i, ty = fy - j;
            double a = _m[j * _n + i] + (_m[j * _n + i + 1] - _m[j * _n + i]) * tx;
            double b = _m[(j + 1) * _n + i] + (_m[(j + 1) * _n + i + 1] - _m[(j + 1) * _n + i]) * tx;
            return a + (b - a) * ty;
        }

        /// <summary>The model's exaggerated z (model metres) for a true elevation (metres): the package's own frame.</summary>
        public double ModelZ(double metres) => (_datum + (metres - _datum) * _vex) / _modelScale;
        /// <summary>The model's z back to true metres.</summary>
        public double TrueMetres(double modelZ) => _datum + (modelZ * _modelScale - _datum) / _vex;

        // ---------------------------------------------------------------- the ring

        /// <summary>Valleys and roads carried across the ring: the outlet's river to the farm belt, the freight road out
        /// to the caravan corridor (world xy, set from the site).</summary>
        public (double X, double Y)[] OutletPath { get; private set; }
        public (double X, double Y)[] RoadPath { get; private set; }
        /// <summary>Where the outlet's valley meets the relief, and where the road does (world xy).</summary>
        /// <summary>A tributary entering the ring from the relief (the eastern one), carried round the plinth to the outlet.</summary>
        public (double X, double Y)[] TributaryPath { get; private set; } = Array.Empty<(double X, double Y)>();
        public (double X, double Y) OutletEnd => OutletPath[^1];
        /// <summary>FIX(haven): a floodplain capital's river coming in across the ring (from the patch's edge to the
        /// plinth); its OutletPath carries the river on from the plinth to the patch's edge.</summary>
        public (double X, double Y)[] InletPath { get; private set; } = Array.Empty<(double X, double Y)>();
        public bool Floodplain => Site.IsFloodplain;

        /// <summary>Join a floodplain river to the relief's own river where it crosses the patch's edge (`upstream`
        /// where it comes in, `downstream` where it leaves).</summary>
        public void SetRiverEnds((double X, double Y) upstream, (double X, double Y) downstream)
        {
            if (!Floodplain) return;
            var (ix, iy) = KmToWorld(Site.InletKm[0], Site.InletKm[1]);
            var (ox, oy) = KmToWorld(Site.OutletKm[0], Site.OutletKm[1]);
            InletPath = Line(upstream, (ix, iy), 16, 0.04, 5);
            OutletPath = Line((ox, oy), downstream, 16, 0.04, 9);
        }

        /// <summary>Carry a river that reaches the patch at `entry` round the plinth (outside its rounded footprint) to the
        /// outlet's valley.</summary>
        public void SetTributary((double X, double Y) entry)
        {
            var join = OutletPath.OrderBy(p => Math.Abs(p.X - (Cx + 0.4 * Half)) + Math.Abs(p.Y - (Cy - Half - 0.6))).First();
            var e = (Math.Min(entry.X, XMax - 0.02), Math.Clamp(entry.Y, YMin + 0.02, YMax - 0.02));
            var p1 = (Cx + Half + 0.55, e.Item2 - 0.6);
            var p2 = (Cx + Half + 0.2, Cy - Half - 0.45);
            var pts = new List<(double X, double Y)>();
            foreach (var (a, b) in new[] { (e, p1), (p1, p2), (p2, join) })
                foreach (var q in Line(a, b, 10, 0.03, 13)) if (pts.Count == 0 || pts[^1] != q) pts.Add(q);
            TributaryPath = pts.ToArray();
        }
        public (double X, double Y) RoadEnd => RoadPath[^1];

        void BuildRingPaths()
        {
            if (Floodplain && Site.InletKm != null && Site.OutletKm != null)   // FIX(haven): straight on to the patch's edge
            {
                var (ix, iy) = KmToWorld(Site.InletKm[0], Site.InletKm[1]);
                var (qx, qy) = KmToWorld(Site.OutletKm[0], Site.OutletKm[1]);
                InletPath = Line((ix, Cy - PatchHalf + 0.02), (ix, iy), 16, 0.04, 5);
                OutletPath = Line((qx, qy), (qx, Cy + PatchHalf - 0.02), 16, 0.04, 9);
                var w = Site.FreightEntryKm ?? new[] { -HalfKm, 0.0 };
                var (wx, wy) = KmToWorld(Math.Clamp(w[0], -HalfKm, HalfKm), Math.Clamp(w[1], -HalfKm, HalfKm));
                RoadPath = Line((wx, wy), (Cx - PatchHalf + 0.05, wy), 16, 0.03, 11);
                return;
            }
            var o = Site.OutletKm ?? new[] { 3.75, -10.4 };
            var (ox, oy) = KmToWorld(Math.Clamp(o[0], -HalfKm, HalfKm), Math.Clamp(o[1], -HalfKm, HalfKm));
            // south-east down to the patch's edge: the farm belt's river picks it up there
            OutletPath = Line((ox, oy), (ox + 0.35 * (PatchHalf - Half), Cy - Half - 1.42), 24, 0.06, 7);
            if (Site.Roads.TryGetValue("north_pass", out var pass))
            {
                var mouth = KmToWorld(pass[0][0], pass[0][1]);
                RoadPath = Line(mouth, (Cx + 1.8, Cy + 5.15), 32, 0.10, 11);
                return;
            }
            var r = Site.FreightEntryKm ?? new[] { -HalfKm, 0.9 };
            var (rx, ry) = KmToWorld(Math.Clamp(r[0], -HalfKm, HalfKm), Math.Clamp(r[1], -HalfKm, HalfKm));
            RoadPath = Line((rx, ry), (Cx - PatchHalf + 0.05, ry - 0.25 * (PatchHalf - Half)), 24, 0.05, 11);
        }

        static (double X, double Y)[] Line((double X, double Y) a, (double X, double Y) b, int n, double wiggle, int seed)
        {
            var p = new (double X, double Y)[n + 1];
            double dx = b.X - a.X, dy = b.Y - a.Y, len = Math.Sqrt(dx * dx + dy * dy), nx = -dy / len, ny = dx / len;
            for (int i = 0; i <= n; i++)
            {
                double t = i / (double)n, off = wiggle * Math.Sin(Math.PI * t) * Math.Sin(t * 7.0 + seed);
                p[i] = (a.X + dx * t + nx * off, a.Y + dy * t + ny * off);
            }
            return p;
        }

        /// <summary>The relief smoothed over ~0.3 units (the ring follows its broad lie).</summary>
        public double Broad(double x, double y)
        {
            double sum = Relief.Fine(x, y), n = 1;
            foreach (var rr in new[] { 0.15, 0.32 })
                for (int k = 0; k < 8; k++)
                {
                    double a = k * Math.PI / 4 + rr;
                    sum += Relief.Fine(x + rr * Math.Cos(a), y + rr * Math.Sin(a)); n++;
                }
            return Math.Max(0, sum / n);
        }

        /// <summary>Ground (blend units): the package's ground on the plinth, then the ring, then the relief.</summary>
        public double GroundUnits(double x, double y)
        {
            double lx = x - Cx, ly = y - Cy;
            double cx = Math.Clamp(lx, -Half, Half), cy = Math.Clamp(ly, -Half, Half);
            double edge = Units(PlinthMetres(cx / S, cy / S));
            // a rounded footprint (a superellipse): the plinth's corners and outer tenth already ease towards the land
            double r4 = Math.Pow(Math.Pow(Math.Abs(lx), 4) + Math.Pow(Math.Abs(ly), 4), 0.25);
            double dOut = r4 - InnerR;
            if (dOut <= 0) return edge;
            double span = PatchHalf - EdgeBlend - InnerR;
            double w = SmoothStep(0, span, dOut);
            double fine = Math.Max(0.0, Relief.Fine(x, y));
            double broad = Broad(x, y);
            double target = fine + (broad - fine) * (1 - w) * 0.6;
            // the massif's spurs run out into the ring where the plinth's edge stands above the land beyond
            // Two outward spurs continue the high northern skyline across the apron.
            double wing = Math.Max(0, Math.Abs(lx) - Half * 0.65);
            double crestY = Half * 0.68 + 0.18 * wing + 0.28 * Math.Sin(wing * 1.5);
            double spur = Floodplain ? 0 : Math.Exp(-Math.Pow((ly - crestY) / 0.85, 2))
                          * (0.65 + 0.35 * Math.Cos(wing * 4.8));
            double h = edge + (target - edge) * Math.Pow(w, 0.8) + 0.48 * spur * w * (1 - w) * 4 * (1 - 0.5 * w);
            // the outlet's valley and the road's bench
            double dv = DistToLine(x, y, OutletPath), dr = DistToLine(x, y, RoadPath);
            if (TributaryPath.Length > 1) dv = Math.Min(dv, DistToLine(x, y, TributaryPath));
            if (InletPath.Length > 1) dv = Math.Min(dv, DistToLine(x, y, InletPath));
            double floorV = Lerp(edge, target, w) - (Floodplain ? 0.004 : 0.05);
            double vw = Floodplain ? 0.14 : 0.35;                    // FIX(haven): a river's bed, not a mountain valley
            if (dv < vw) h = Lerp(Math.Min(h, floorV), h, SmoothStep(vw * 0.17, vw, dv));
            if (dr < 0.75)
            {
                var start = RoadPath[0];
                var end = RoadEnd;
                double dx = end.X - start.X, dy = end.Y - start.Y;
                double t = Math.Clamp(((x - start.X) * dx + (y - start.Y) * dy) / (dx * dx + dy * dy), 0, 1);
                var mouth = WorldToKm(start.X, start.Y);
                double bench = Lerp(Units(PlinthMetres(mouth.X, mouth.Y)), Broad(end.X, end.Y), t);
                h = Lerp(h, bench, (1 - SmoothStep(0.1, 0.75, dr)) * SmoothStep(0, 0.25, dOut));
            }
            return Math.Max(h, 0.0);
        }

        /// <summary>The patch mesh's surface: the ground, turning into the relief mesh's own triangles at the patch's edge.</summary>
        public double MeshUnits(double x, double y)
        {
            double g = GroundUnits(x, y);
            double e = Math.Min(Math.Min(x - XMin, XMax - x), Math.Min(y - YMin, YMax - y));
            double b = 1 - SmoothStep(0, EdgeBlend, e);
            return b > 0 ? g + (Relief.Coarse(x, y) - g) * b : g;
        }

        /// <summary>Heights on a grid over the patch (row 0 to the north), on the grid lines, seam-matched.</summary>
        public float[] SampleMesh(int nx, int ny)
        {
            var a = new float[nx * ny];
            double sx = (XMax - XMin) / (nx - 1), sy = (YMax - YMin) / (ny - 1);
            Parallel.For(0, ny, j =>
            {
                double y = YMax - j * sy;
                for (int i = 0; i < nx; i++) a[j * nx + i] = (float)MeshUnits(XMin + i * sx, y);
            });
            return a;
        }

        // ---------------------------------------------------------------- places

        public (double X, double Y, double H) Place(string id)
        {
            if (!Site.Places.TryGetValue(id, out var p)) return (Cx, Cy, GroundUnits(Cx, Cy));
            var (x, y) = KmToWorld(p.At[0], p.At[1]);
            return (x, y, GroundUnits(x, y));
        }

        /// <summary>A km polyline of the site as world xy (rivers' third value, the bed in metres, is dropped).</summary>
        public (double X, double Y)[] Path(double[][] km) => km.Select(p => KmToWorld(p[0], p[1])).ToArray();

        // ---------------------------------------------------------------- maths

        public static double SmoothStep(double e0, double e1, double x)
        {
            double t = Math.Clamp((x - e0) / (e1 - e0), 0, 1);
            return t * t * (3 - 2 * t);
        }

        static double Lerp(double a, double b, double t) => a + (b - a) * t;

        public static double DistToLine(double x, double y, (double X, double Y)[] line)
        {
            double best = double.MaxValue;
            for (int i = 0; i + 1 < line.Length; i++)
            {
                double ax = line[i].X, ay = line[i].Y, bx = line[i + 1].X - ax, by = line[i + 1].Y - ay;
                double t = Math.Clamp(((x - ax) * bx + (y - ay) * by) / Math.Max(1e-12, bx * bx + by * by), 0, 1);
                double ex = x - ax - bx * t, ey = y - ay - by * t;
                best = Math.Min(best, Math.Sqrt(ex * ex + ey * ey));
            }
            return best;
        }

        static uint Hash(int x, int y, int seed)
        {
            unchecked
            {
                uint h = (uint)x * 374761393u + (uint)y * 668265263u + (uint)seed * 2246822519u;
                h = (h ^ (h >> 13)) * 1274126177u;
                return h ^ (h >> 16);
            }
        }

        static double Value(double x, double y, int seed)
        {
            int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y);
            double fx = x - xi, fy = y - yi;
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
            double a = Hash(xi, yi, seed) / 4294967296.0, b = Hash(xi + 1, yi, seed) / 4294967296.0;
            double c = Hash(xi, yi + 1, seed) / 4294967296.0, d = Hash(xi + 1, yi + 1, seed) / 4294967296.0;
            return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
        }

        public static double Ridged(double x, double y, int oct, int seed)
        {
            double s = 0, a = 0.5, wgt = 1, n = 0;
            for (int o = 0; o < oct; o++)
            {
                double v = 1 - Math.Abs(2 * Value(x, y, seed + o) - 1);
                v *= v * wgt;
                wgt = Math.Clamp(v * 2, 0, 1);
                s += v * a; n += a; a *= 0.5; x *= 2.03; y *= 2.03;
            }
            return s / n;
        }
    }
}
