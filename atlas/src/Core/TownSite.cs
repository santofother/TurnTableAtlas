// A town package standing on the Known World as a miniature (Corivessa Port, Corivessa): the package's own model,
// `exaggeration` times its true size, laid onto the relief round its pin. Pure layout, no Godot.
// No patch is cut into the relief. Every vertex keeps its height above the model's own ground (above sea level where
// the model is under water) and stands that far above the relief (above sea level over the map's water). The model's
// own hills rise over the relief in the middle and flatten towards the square's edge, so the ground meets the map
// there. Houses, walls and quays follow the map's slopes and coast.
// Lengths are blend units (1 = 10 miles), +x east, +y north. Heights are blend units too.
using System;
using System.Collections.Generic;

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
        /// <summary>The ground stands this far above the relief, clear of its triangles.</summary>
        public const double Lift = 0.0015;
        /// <summary>The model's own hills keep their full height inside this share of the half extent and are flat at
        /// <see cref="FlatAt"/>.</summary>
        public const double HillsFrom = 0.55, FlatAt = 0.95;
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
        }

        public bool Contains(double x, double y) => Math.Abs(x - Cx) <= Half && Math.Abs(y - Cy) <= Half;

        /// <summary>The model's own ground (model metres, z up) at a model point.</summary>
        public double ModelGround(double mx, double my) => _grid.At(mx, my, ModelHalf);

        /// <summary>The map under a world point: the relief's land, or sea level.</summary>
        public double Base(double x, double y) => Math.Max(0.0, _relief(x, y));

        /// <summary>How much of the model's own hills stand above the relief here: 1 in the middle, 0 at the edge.</summary>
        public double HillWeight(double mx, double my)
        {
            double r = Math.Max(Math.Abs(mx), Math.Abs(my)) / ModelHalf;
            double t = Math.Clamp((r - HillsFrom) / (FlatAt - HillsFrom), 0, 1);
            return 1 - t * t * (3 - 2 * t);
        }

        /// <summary>A model point (metres, z up) on the map: world xy and height (blend units).</summary>
        public (double X, double Y, double H) Place(double mx, double my, double mz)
        {
            double x = Cx + mx * S, y = Cy + my * S;
            double g = Math.Max(ModelGround(mx, my), 0.0);
            return (x, y, Base(x, y) + Lift + (mz - g + HillWeight(mx, my) * g) * S);
        }

        /// <summary>Trees, fields and farms thin out from this share of the half extent to the edge, a cell (model
        /// metres) at a time, so the model's countryside ends in scattered groves rather than a straight line.</summary>
        public const double ThinFrom = 0.68, ThinTo = 0.97, ThinCell = 1.5;

        /// <summary>Whether a piece of countryside at this model point is drawn (always inside ThinFrom, never past ThinTo).</summary>
        public bool KeepAtEdge(double mx, double my)
        {
            double r = Math.Max(Math.Abs(mx), Math.Abs(my)) / ModelHalf;
            if (r <= ThinFrom) return true;
            double t = Math.Clamp((r - ThinFrom) / (ThinTo - ThinFrom), 0, 1);
            long cx = (long)Math.Floor(mx / ThinCell), cy = (long)Math.Floor(my / ThinCell);
            ulong h = unchecked((ulong)(cx * 73856093L) ^ (ulong)(cy * 19349663L));
            h ^= h >> 13; h = unchecked(h * 0x5bd1e995UL); h ^= h >> 15;
            return (h % 10007) / 10007.0 >= t * t * (3 - 2 * t);
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
