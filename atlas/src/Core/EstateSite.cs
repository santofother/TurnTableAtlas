// A country estate on the Known World (Landric's villa, generator/villa.py): a small hero patch that replaces the
// coarse relief round the estate's pin, as KarnAshurSite does for Karn Ashur. Pure layout, no Godot:
//   - the estate's own plinth, drawn from the package's terrain grid (city.json `terrain_grid`) as a miniature,
//     `exaggeration` times its true size, so the house, its lake and its vineyards read on the map; the package's
//     city.glb stands on it at the same scale (both use S, blend units per model metre).
//   - rolling hills round the plinth that carry on the model's own hills, then hand over to the relief, meeting the
//     relief mesh exactly at the patch's edge.
// Lengths are blend units (1 = 10 miles), +x east, +y north. Heights are blend units too.
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace Atlas.Core
{
    public sealed class EstateSite
    {
        public readonly string Id;
        public readonly double Cx, Cy, UnitM, Exag;
        /// <summary>Blend units per model metre (model_scale x the miniature's exaggeration / metres per unit).</summary>
        public readonly double S;
        /// <summary>Half the plinth (blend units), and the model's own half extent (model metres).</summary>
        public readonly double Half, ModelHalf;
        /// <summary>Height (blend units) of the model's z = 0: the estate lake's surface.</summary>
        public readonly double Base;
        /// <summary>The hills reach this far from the centre; the ground is the relief's at PatchHalf - EdgeBlend.</summary>
        public readonly double HillsR, PatchHalf;
        public const double EdgeBlend = 0.32;
        public readonly ReliefSampler Relief;
        public readonly int I0, I1, J0, J1;
        public readonly double XMin, XMax, YMin, YMax;
        public readonly List<(double X, double Y, double R, double H)> Hills = new();
        readonly TerrainGrid _grid;
        readonly double _broad0;

        /// <summary>The relief smoothed over ~0.25 units: the land round the plinth follows its broad lie, not its texels.</summary>
        public double Broad(double x, double y)
        {
            double sum = Relief.Fine(x, y), n = 1;
            foreach (var rr in new[] { 0.12, 0.25 })
                for (int k = 0; k < 8; k++)
                {
                    double a = k * Math.PI / 4 + rr;
                    sum += Relief.Fine(x + rr * Math.Cos(a), y + rr * Math.Sin(a)); n++;
                }
            return sum / n;
        }

        public EstateSite(string id, ReliefSampler relief, double cx, double cy, double unitM, double exag,
                          double modelScale, double modelHalf, TerrainGrid grid, double miniature, double hillsR)
        {
            Id = id; Relief = relief; Cx = cx; Cy = cy; UnitM = unitM; Exag = exag; _grid = grid;
            S = modelScale * miniature / unitM;
            ModelHalf = modelHalf;
            Half = modelHalf * S;
            HillsR = Math.Max(hillsR, Half * 3.0);
            PatchHalf = HillsR + 0.6;
            I0 = (int)Math.Floor((cx - PatchHalf - relief.X0) / relief.Dx);
            I1 = (int)Math.Ceiling((cx + PatchHalf - relief.X0) / relief.Dx);
            J0 = (int)Math.Floor((relief.YTop - (cy + PatchHalf)) / relief.Dy);
            J1 = (int)Math.Ceiling((relief.YTop - (cy - PatchHalf)) / relief.Dy);
            XMin = relief.GridX(I0); XMax = relief.GridX(I1);
            YMax = relief.GridY(J0); YMin = relief.GridY(J1);
            // the plinth's rim sits on the relief: the lake level is the relief at the centre less the rim's mean height
            double rim = 0; int n = 0;
            for (int k = 0; k < grid.N; k++)
            {
                rim += grid.Z[k] + grid.Z[(grid.N - 1) * grid.N + k] + grid.Z[k * grid.N] + grid.Z[k * grid.N + grid.N - 1];
                n += 4;
            }
            _broad0 = Broad(cx, cy);
            Base = Math.Max(0.02, _broad0) - S * rim / n;
            // hills round the plinth, carrying on the model's: higher to the west and north, low to the south-east
            // (angle deg CCW from east, distance and radius in plinth halves, height in blend units)
            foreach (var (deg, d, r, h) in new[] { (180.0, 1.9, 0.9, 0.02), (135.0, 2.0, 1.0, 0.026), (95.0, 2.0, 0.9, 0.018),
                                                    (215.0, 1.9, 0.8, 0.014), (40.0, 2.0, 0.8, 0.014), (-25.0, 1.9, 0.7, 0.009) })
            {
                double a = deg * Math.PI / 180;
                Hills.Add((d * Half * Math.Cos(a), d * Half * Math.Sin(a), r * Half, h));
            }
        }

        public bool Contains(double x, double y) => x > XMin && x < XMax && y > YMin && y < YMax;
        public bool OnPlinth(double x, double y) => Math.Abs(x - Cx) <= Half && Math.Abs(y - Cy) <= Half;
        public (double U0, double V0, double U1, double V1) HoleUv =>
            ((I0 + 0.5) / Relief.Nx, (J0 + 0.5) / Relief.Ny, (I1 - 0.5) / Relief.Nx, (J1 - 0.5) / Relief.Ny);

        /// <summary>World point -> model metres (the package's frame).</summary>
        public (double X, double Y) ToModel(double x, double y) => ((x - Cx) / S, (y - Cy) / S);
        /// <summary>Model point (metres, z up) -> world xy and height (blend units).</summary>
        public (double X, double Y, double H) FromModel(double mx, double my, double mz) => (Cx + mx * S, Cy + my * S, Base + mz * S);

        static double SmoothStep(double e0, double e1, double x)
        {
            double t = Math.Clamp((x - e0) / (e1 - e0), 0, 1);
            return t * t * (3 - 2 * t);
        }

        /// <summary>The estate's own ground (blend units): the model's terrain on the plinth, carried outwards by its rim,
        /// with the hills rising beyond it.</summary>
        public double LocalUnits(double x, double y)
        {
            double lx = x - Cx, ly = y - Cy;
            double mx = Math.Clamp(lx / S, -ModelHalf, ModelHalf), my = Math.Clamp(ly / S, -ModelHalf, ModelHalf);
            double h = Base + S * _grid.At(mx, my, ModelHalf);
            double dx = Math.Max(Math.Abs(lx) - Half, 0), dy = Math.Max(Math.Abs(ly) - Half, 0);
            double dOut = Math.Sqrt(dx * dx + dy * dy);
            double out1 = SmoothStep(0, 0.35 * Half, dOut);
            if (out1 <= 0) return h;
            h += (Broad(x, y) - _broad0) * SmoothStep(0, 1.5 * Half, dOut);
            double hills = 0;
            foreach (var (hx, hy, hr, hh) in Hills)
            {
                double d = Math.Sqrt((lx - hx) * (lx - hx) + (ly - hy) * (ly - hy)) / hr;
                if (d < 1) hills += hh * Math.Pow(1 - d * d, 2);
            }
            return h + hills * out1;
        }

        /// <summary>Ground height (blend units): the estate's own inside HillsR, the relief's per-pixel height outside.</summary>
        public double GroundUnits(double x, double y)
        {
            double r = Math.Sqrt((x - Cx) * (x - Cx) + (y - Cy) * (y - Cy));
            double w = SmoothStep(HillsR * 0.75, PatchHalf - EdgeBlend, r);
            double fine = Math.Max(0.0, Relief.Fine(x, y));
            if (w >= 1) return fine;
            double local = LocalUnits(x, y);
            return local + (fine - local) * w;
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
    }
}
