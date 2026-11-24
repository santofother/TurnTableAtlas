// The Known World relief as the Atlas draws it (WorldMap.cs + relief.gdshader): the baked heights (blend units, sea < 0)
// sampled the way the GPU does (bilinear between texel centres, clamped at the edges), and the relief mesh's own
// surface: its grid vertices joined by flat triangles. A hero patch that replaces part of the relief has to meet that
// mesh surface exactly along its edge, and should match the per-pixel heights inside, where the relief takes its normals.
using System;

namespace Atlas.Core
{
    public sealed class ReliefSampler
    {
        readonly float[] _h;
        readonly int _w, _hh;
        /// <summary>West edge (x) and north edge (y) of the map, and its size, in blend units.</summary>
        public readonly double X0, YTop, Width, Depth;
        /// <summary>Quads of the relief mesh across (x) and down (y): its PlaneMesh subdivisions + 1.</summary>
        public readonly int Nx, Ny;

        public ReliefSampler(float[] heights, int w, int h, double[] boundsXy, int nx, int ny)
        {
            _h = heights; _w = w; _hh = h;
            X0 = boundsXy[0]; YTop = boundsXy[3];
            Width = boundsXy[2] - boundsXy[0]; Depth = boundsXy[3] - boundsXy[1];
            Nx = nx; Ny = ny;
        }

        public double Dx => Width / Nx;
        public double Dy => Depth / Ny;
        public double GridX(int i) => X0 + i * Dx;
        public double GridY(int j) => YTop - j * Dy;

        /// <summary>Height texture at a uv from the top-left, as a linear-filtered GPU fetch reads it.</summary>
        public double Texel(double u, double v)
        {
            double tx = Math.Clamp(u * _w - 0.5, 0, _w - 1), ty = Math.Clamp(v * _hh - 0.5, 0, _hh - 1);
            int x0 = (int)tx, y0 = (int)ty, x1 = Math.Min(x0 + 1, _w - 1), y1 = Math.Min(y0 + 1, _hh - 1);
            double fx = tx - x0, fy = ty - y0;
            double a = _h[y0 * _w + x0] + (_h[y0 * _w + x1] - _h[y0 * _w + x0]) * fx;
            double b = _h[y1 * _w + x0] + (_h[y1 * _w + x1] - _h[y1 * _w + x0]) * fx;
            return a + (b - a) * fy;
        }

        /// <summary>Per-pixel relief height (blend units, sea &lt; 0) at a world point.</summary>
        public double Fine(double x, double y) => Texel((x - X0) / Width, (YTop - y) / Depth);

        /// <summary>Height of relief mesh vertex (i across from the west, j down from the north): land only, the sea is flat at 0.</summary>
        public double Vertex(int i, int j) => Math.Max(0.0, Texel(i / (double)Nx, j / (double)Ny));

        /// <summary>The relief mesh's surface at a world point. Godot's PlaneMesh splits each quad along the diagonal from
        /// its (low u, high v) corner to its (high u, low v) corner.</summary>
        public double Coarse(double x, double y)
        {
            double gu = (x - X0) / Width * Nx, gv = (YTop - y) / Depth * Ny;
            int a = Math.Clamp((int)Math.Floor(gu), 0, Nx - 1), b = Math.Clamp((int)Math.Floor(gv), 0, Ny - 1);
            double fx = Math.Clamp(gu - a, 0, 1), fy = Math.Clamp(gv - b, 0, 1);
            double h00 = Vertex(a, b), h10 = Vertex(a + 1, b), h01 = Vertex(a, b + 1), h11 = Vertex(a + 1, b + 1);
            return fx + fy <= 1
                ? h00 + fx * (h10 - h00) + fy * (h01 - h00)
                : h11 + (1 - fx) * (h01 - h11) + (1 - fy) * (h10 - h11);
        }
    }
}
