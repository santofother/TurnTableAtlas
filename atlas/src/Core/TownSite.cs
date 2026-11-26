// A town package standing on the Known World as a miniature (Corivessa Port, Corivessa): the package's own model,
// `exaggeration` times its true size, laid onto the relief round its pin. Pure layout, no Godot.
// No patch is cut into the relief. Every vertex keeps its height above the model's own ground (above sea level where
// the model is under water) and stands that far above the relief (above sea level over the map's water). Where the
// model's ground rises above its own plain (a palace hill), that rise stands over the relief in the middle and dies
// out along a rounded, ragged rim, the same rim along which the town's ground hands over to the map's colour
// (town_ground.gdshader) and its countryside thins out, as Karn Ashur's basin does. Houses, walls and quays follow
// the map's slopes and coast.
// Lengths are blend units (1 = 10 miles), +x east, +y north. Heights are blend units too.
using System;
using System.Collections.Generic;
using System.Linq;

namespace Atlas.Core
{
    public sealed class TownSite
    {
        public readonly string Id;
        public readonly double Cx, Cy;
        /// <summary>Blend units per model metre (model_scale x the miniature's exaggeration / metres per unit).</summary>
        public readonly double S;
        /// <summary>The model's half extent (model metres) and the square it covers on the map (blend units).</summary>
        public readonly double ModelHalf, Half;
        /// <summary>The model's plain (model metres): its ground rises above this only on its hills.</summary>
        public readonly double Plain;
        /// <summary>The ground stands this far above the relief, clear of its triangles.</summary>
        public const double Lift = 0.0015;
        /// <summary>The model's own hills keep their full height inside this rim and are flat from <see cref="FlatAt"/>.</summary>
        public const double HillsFrom = 0.42, FlatAt = 0.78;
        /// <summary>Trees, fields and farms thin out between these rims, a cell (model metres) at a time, so the model's
        /// countryside ends in scattered groves rather than a line.</summary>
        public const double ThinFrom = 0.5, ThinTo = 0.86, ThinCell = 1.5;
        /// <summary>How far the rim wanders in and out (a share of the half extent).</summary>
        public const double RimNoise = 0.1;
        readonly Func<double, double, double> _relief;
        readonly TerrainGrid _grid;

        /// <param name="relief">The relief mesh's surface at a world point (blend units, sea &lt; 0 or 0).</param>
        public TownSite(string id, Func<double, double, double> relief, double cx, double cy, double unitM,
                        double modelScale, double modelHalf, TerrainGrid grid, double miniature)
        {
            Id = id; _relief = relief; Cx = cx; Cy = cy; _grid = grid;
            S = modelScale * miniature / unitM;
            ModelHalf = modelHalf;
            Half = modelHalf * S;
            var land = grid.Z.Where(z => z > 0).OrderBy(z => z).ToArray();
            Plain = land.Length > 0 ? land[land.Length / 4] : 0;
        }

        public bool Contains(double x, double y) => Math.Abs(x - Cx) <= Half && Math.Abs(y - Cy) <= Half;

        /// <summary>The model's own ground (model metres, z up) at a model point.</summary>
        public double ModelGround(double mx, double my) => _grid.At(mx, my, ModelHalf);

        /// <summary>The map under a world point: the relief's land, or sea level.</summary>
        public double Base(double x, double y) => Math.Max(0.0, _relief(x, y));

        static double Hash(double x, double y)
        {
            double h = Math.Sin(x * 127.1 + y * 311.7) * 43758.5453;
            return h - Math.Floor(h);
        }

        static double ValueNoise(double x, double y)
        {
            double ix = Math.Floor(x), iy = Math.Floor(y), fx = x - ix, fy = y - iy;
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
            double a = Hash(ix, iy) + (Hash(ix + 1, iy) - Hash(ix, iy)) * fx;
            double b = Hash(ix, iy + 1) + (Hash(ix + 1, iy + 1) - Hash(ix, iy + 1)) * fx;
            return a + (b - a) * fy;
        }

        /// <summary>The rounded, ragged rim's measure at a model point: about 0 at the centre, 1 at the middle of the
        /// square's sides, more in its corners.</summary>
        public double Rim(double mx, double my)
        {
            double qx = mx / ModelHalf, qy = my / ModelHalf;
            double r = Math.Pow(Math.Pow(Math.Abs(qx), 4) + Math.Pow(Math.Abs(qy), 4), 0.25);
            double n = ValueNoise(qx * 3.1 + 7.3, qy * 3.1 + 1.9) * 0.65 + ValueNoise(qx * 7.7 + 2.2, qy * 7.7 + 5.4) * 0.35;
            return r + RimNoise * (n - 0.5) * Math.Min(1, r * 2);
        }

        static double Smooth(double e0, double e1, double x)
        {
            double t = Math.Clamp((x - e0) / (e1 - e0), 0, 1);
            return t * t * (3 - 2 * t);
        }

        /// <summary>How much of the model's own hills stand above the relief here: 1 in the middle, 0 past the rim.</summary>
        public double HillWeight(double mx, double my) => 1 - Smooth(HillsFrom, FlatAt, Rim(mx, my));

        /// <summary>A model point (metres, z up) on the map: world xy and height (blend units).</summary>
        public (double X, double Y, double H) Place(double mx, double my, double mz)
        {
            double x = Cx + mx * S, y = Cy + my * S;
            double g = Math.Max(ModelGround(mx, my), 0.0);
            double rise = HillWeight(mx, my) * Math.Max(g - Plain, 0.0);
            // the model's seabed sinks under the map's water rather than lifting with the land
            return (x, y, Base(x, y) + (mz < 0 ? -2 * Lift : Lift) + (mz - g + rise) * S);
        }

        /// <summary>Inside the rim, where the town stands (its regional roads and farms keep out).</summary>
        public bool Inside(double x, double y) => Contains(x, y) && Rim((x - Cx) / S, (y - Cy) / S) < ThinFrom + 0.1;

        /// <summary>Whether a piece of countryside at this model point is drawn (always inside ThinFrom, never past ThinTo).</summary>
        public bool KeepAtEdge(double mx, double my)
        {
            double t = Smooth(ThinFrom, ThinTo, Rim(mx, my));
            if (t <= 0) return true;
            if (t >= 1) return false;
            long cx = (long)Math.Floor(mx / ThinCell), cy = (long)Math.Floor(my / ThinCell);
            ulong h = unchecked((ulong)(cx * 73856093L) ^ (ulong)(cy * 19349663L));
            h ^= h >> 13; h = unchecked(h * 0x5bd1e995UL); h ^= h >> 15;
            return (h % 10007) / 10007.0 >= t;
        }

        /// <summary>The miniature's ground (blend units) under a world point, or null off its square.</summary>
        public double? GroundAt(double x, double y)
        {
            if (!Contains(x, y)) return null;
            var (mx, my) = ((x - Cx) / S, (y - Cy) / S);
            return Place(mx, my, Math.Max(ModelGround(mx, my), 0.0)).H;
        }

        /// <summary>A height grid (model metres, row 0 to the south) from a terrain mesh's vertices: each grid node takes
        /// the mean of the vertices nearest to it; nodes with none take their neighbours'.</summary>
        public static TerrainGrid GridFromPoints(IEnumerable<(double X, double Y, double Z)> points, double half, int n)
        {
            var sum = new double[n * n];
            var count = new int[n * n];
            foreach (var (x, y, z) in points)
            {
                int i = (int)Math.Round((x + half) / (2 * half) * (n - 1)), j = (int)Math.Round((y + half) / (2 * half) * (n - 1));
                if (i < 0 || j < 0 || i >= n || j >= n) continue;
                sum[j * n + i] += z;
                count[j * n + i]++;
            }
            var z0 = new double[n * n];
            var known = new bool[n * n];
            for (int k = 0; k < z0.Length; k++)
                if (count[k] > 0) { z0[k] = sum[k] / count[k]; known[k] = true; }
            for (int pass = 0; pass < n; pass++)
            {
                bool missing = false;
                var next = (bool[])known.Clone();
                for (int j = 0; j < n; j++)
                    for (int i = 0; i < n; i++)
                    {
                        int k = j * n + i;
                        if (known[k]) continue;
                        double s = 0; int c = 0;
                        if (i > 0 && known[k - 1]) { s += z0[k - 1]; c++; }
                        if (i < n - 1 && known[k + 1]) { s += z0[k + 1]; c++; }
                        if (j > 0 && known[k - n]) { s += z0[k - n]; c++; }
                        if (j < n - 1 && known[k + n]) { s += z0[k + n]; c++; }
                        if (c > 0) { z0[k] = s / c; next[k] = true; } else missing = true;
                    }
                known = next;
                if (!missing) break;
            }
            return new TerrainGrid { N = n, Z = z0 };
        }
    }
}
