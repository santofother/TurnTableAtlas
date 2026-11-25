// The River Flame on the Known World, at the relief's own (true) scale (atlas/assets/map/known_world/flame_valley.json):
// the trunk from the Varduun Highlands to the delta and the delta's arms, from KnownWorld.blend's own river mesh.
// Pure C#, no Godot:
//   - links the trunk to Haven's hero patch: the part under the patch is dropped, the patch's own river (BasinSite's
//     inlet and outlet paths) joins the ends where the trunk crosses the patch's edge;
//   - paints the river silt-red into the map's albedo, with irrigated fields on both banks (a belt widening downstream
//     to the whole delta) and a sharp edge to the desert;
//   - places farming villages along both banks and across the delta, and the market towns, and adds up their people;
//   - gives the field overlay its weights (how much of a point is farmland) and the river's direction there.
// Lengths are blend units (1 = 10 miles), +x east, +y north.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Atlas.Core
{
    public class FlameValleyData
    {
        [JsonPropertyName("water_colour")] public double[] WaterColour { get; set; } = { 0.66, 0.29, 0.17 };
        [JsonPropertyName("trunk")] public double[][] Trunk { get; set; }
        [JsonPropertyName("arms")] public List<FvArm> Arms { get; set; } = new();
        [JsonPropertyName("belt")] public FvBelt Belt { get; set; } = new();
        [JsonPropertyName("delta")] public double[][] Delta { get; set; }
        [JsonPropertyName("towns")] public List<HdTown> Towns { get; set; } = new();
        [JsonPropertyName("population")] public Dictionary<string, double> Population { get; set; } = new();

        public static FlameValleyData Load(string path) => JsonSerializer.Deserialize<FlameValleyData>(File.ReadAllText(path));
    }

    public class FvArm
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("pts")] public double[][] Pts { get; set; }
    }

    public class FvBelt
    {
        [JsonPropertyName("start_y")] public double StartY { get; set; } = 29.5;
        [JsonPropertyName("full_y")] public double FullY { get; set; } = 33.5;
        /// <summary>[y, half width (units)] pairs: the irrigated belt each side of the trunk, by latitude.</summary>
        [JsonPropertyName("half_width")] public double[][] HalfWidth { get; set; }
    }

    public sealed class FlameValleyRegion
    {
        public readonly record struct Village(double X, double Y, int Houses, double Angle);
        public readonly record struct Town(string Id, string Label, double X, double Y, double Size);

        public readonly FlameValleyData D;
        public readonly double UnitM, Exag;
        /// <summary>Every stretch of the river drawn on the relief: the trunk (split round a hero patch), the delta's
        /// arms, and the patch's own joins across its ring.</summary>
        public readonly List<(string Id, (double X, double Y)[] Pts, double Width)> Reaches = new();
        public readonly List<Village> Villages = new();
        public readonly List<Town> Towns = new();
        public (double R, double G, double B) Water => (D.WaterColour[0], D.WaterColour[1], D.WaterColour[2]);
        public (double X, double Y)[] Trunk { get; }
        readonly (double X, double Y)[] _delta;
        readonly List<Func<double, double, bool>> _patches = new();
        public const double TrunkWidth = 0.09, ArmWidth = 0.06;

        public FlameValleyRegion(FlameValleyData d, double unitM, double exag)
        {
            D = d; UnitM = unitM; Exag = exag;
            Trunk = d.Trunk.Select(p => (p[0], p[1])).ToArray();
            _delta = d.Delta.Select(p => (p[0], p[1])).ToArray();
            Reaches.Add(("trunk", Trunk, TrunkWidth));
            foreach (var a in d.Arms) Reaches.Add((a.Id, a.Pts.Select(p => (p[0], p[1])).ToArray(), ArmWidth));
            foreach (var t in d.Towns) Towns.Add(new Town(t.Id, t.Label, t.At[0], t.At[1], t.Size));
        }

        public int Population => (int)(Villages.Count * D.Population.GetValueOrDefault("per_village", 900)
                                       + Towns.Sum(t => t.Size) * D.Population.GetValueOrDefault("per_town", 12000));

        // ---------------------------------------------------------------- Haven's patch

        /// <summary>Cut the trunk where a hero patch covers it. Returns where the trunk enters the patch (upstream) and
        /// leaves it (downstream), the last points outside, or null if the trunk misses it.</summary>
        public ((double X, double Y) Up, (double X, double Y) Down)? LinkPatch(Func<double, double, bool> inPatch)
        {
            _patches.Add(inPatch);
            var t = Reaches.First(r => r.Id == "trunk");
            int k1 = Array.FindIndex(t.Pts, p => inPatch(p.X, p.Y));
            if (k1 <= 0) return null;
            int k2 = Array.FindLastIndex(t.Pts, p => inPatch(p.X, p.Y));
            if (k2 >= t.Pts.Length - 1) return null;
            Reaches.RemoveAll(r => r.Id == "trunk");
            Reaches.Insert(0, ("trunk_upper", t.Pts.Take(k1).ToArray(), TrunkWidth));
            Reaches.Insert(1, ("trunk_lower", t.Pts.Skip(k2 + 1).ToArray(), TrunkWidth));
            return (t.Pts[k1 - 1], t.Pts[k2 + 1]);
        }

        /// <summary>The patch's own river across its ring (painted red under the patch's water).</summary>
        public void AddJoin(string id, (double X, double Y)[] pts)
        {
            if (pts is { Length: > 1 }) Reaches.Add((id, pts, TrunkWidth));
        }

        bool InPatch(double x, double y) => _patches.Any(p => p(x, y));

        // ---------------------------------------------------------------- where the farmland is

        public bool InDelta(double x, double y) => HighDunesRegion.InPoly(x, y, _delta);

        /// <summary>The belt's half width (units) each side of the trunk at latitude y (0 above the foothills).</summary>
        public double HalfWidth(double y)
        {
            var hw = D.Belt.HalfWidth;
            if (y < D.Belt.StartY) return 0;
            if (y <= hw[0][0]) return hw[0][1];
            for (int i = 0; i + 1 < hw.Length; i++)
                if (y <= hw[i + 1][0]) return hw[i][1] + (hw[i + 1][1] - hw[i][1]) * (y - hw[i][0]) / (hw[i + 1][0] - hw[i][0]);
            return hw[^1][1];
        }

        /// <summary>Distance to the nearest stretch of the river and the river's direction there (unit vector).</summary>
        public (double D, double Dx, double Dy, bool Trunk) Nearest(double x, double y)
        {
            double best = double.MaxValue, bx = 0, by = 1;
            bool trunk = false;
            foreach (var (id, pts, _) in Reaches)
                for (int k = 0; k + 1 < pts.Length; k++)
                {
                    var a = pts[k]; var b = pts[k + 1];
                    double ux = b.X - a.X, uy = b.Y - a.Y, l2 = ux * ux + uy * uy;
                    if (Math.Abs(x - a.X) > 1.6 + Math.Abs(ux) || Math.Abs(y - a.Y) > 1.6 + Math.Abs(uy)) continue;
                    double t = Math.Clamp(((x - a.X) * ux + (y - a.Y) * uy) / Math.Max(1e-12, l2), 0, 1);
                    double d = Hyp(x - a.X - ux * t, y - a.Y - uy * t);
                    if (d < best) { best = d; double l = Math.Sqrt(l2); bx = ux / l; by = uy / l; trunk = id.StartsWith("trunk"); }
                }
            return (best, bx, by, trunk);
        }

        /// <summary>How much of a point is irrigated farmland (0..1): the belt along the trunk with a wandering edge, the
        /// whole delta; never the river itself, the sea or the highlands.</summary>
        public double FieldWeight(double x, double y, double heightM)
        {
            var (d, _, _, trunk) = Nearest(x, y);
            return FieldWeightFast(x, y, heightM, d, (trunk ? TrunkWidth : ArmWidth) * 0.5);
        }

        // ---------------------------------------------------------------- villages and towns

        /// <summary>Villages on both banks every ~0.25 units, deeper into the fields downstream, and across the delta on
        /// a jittered grid; dry ground and the sea stay empty, and so do the hero patches.</summary>
        public void PlaceSettlements(Func<double, double, double> heightM, Func<double, double, bool> skip, int seed = 2611)
        {
            var rng = new Random(seed);
            Villages.Clear();
            bool Clear(double x, double y, double min) => Villages.All(v => Hyp(v.X - x, v.Y - y) > min)
                                                         && Towns.All(t => Hyp(t.X - x, t.Y - y) > 0.3 * t.Size + 0.15);
            foreach (var (id, pts, width) in Reaches.ToList())
            {
                if (id.StartsWith("join")) continue;
                var p = HighDunesRegion.Resample(pts, 0.05);
                double s = 0;
                for (int k = 1; k < p.Length; k++)
                {
                    s += Hyp(p[k].X - p[k - 1].X, p[k].Y - p[k - 1].Y);
                    if (s < 0.24 * (0.7 + 0.6 * rng.NextDouble())) continue;
                    s = 0;
                    double ux = p[k].X - p[k - 1].X, uy = p[k].Y - p[k - 1].Y, l = Math.Max(1e-9, Hyp(ux, uy));
                    double nx = -uy / l, ny = ux / l;
                    foreach (int side in new[] { -1, 1 })
                    {
                        double hw = InDelta(p[k].X, p[k].Y) ? 0.7 : HalfWidth(p[k].Y);
                        if (hw <= 0) continue;
                        double off = width * 0.5 + 0.07 + rng.NextDouble() * hw * 0.8;
                        double vx = p[k].X + nx * side * off, vy = p[k].Y + ny * side * off;
                        if (skip(vx, vy) || InPatch(vx, vy)) continue;
                        double hm = heightM(vx, vy);
                        if (FieldWeight(vx, vy, hm) < 0.5 || !Clear(vx, vy, 0.16)) continue;
                        Villages.Add(new Village(vx, vy, 6 + rng.Next(8), rng.NextDouble() * Math.PI));
                    }
                }
            }
            // the delta's interior, between the arms
            var (x0, y0, x1, y1) = (_delta.Min(q => q.X), _delta.Min(q => q.Y), _delta.Max(q => q.X), _delta.Max(q => q.Y));
            for (double y = y0; y < y1; y += 0.45)
                for (double x = x0; x < x1; x += 0.45)
                {
                    double vx = x + 0.3 * (rng.NextDouble() - 0.5), vy = y + 0.3 * (rng.NextDouble() - 0.5);
                    if (!InDelta(vx, vy) || skip(vx, vy) || InPatch(vx, vy)) continue;
                    if (FieldWeight(vx, vy, heightM(vx, vy)) < 0.6 || !Clear(vx, vy, 0.3)) continue;
                    Villages.Add(new Village(vx, vy, 6 + rng.Next(8), rng.NextDouble() * Math.PI));
                }
        }

        // ---------------------------------------------------------------- the albedo

        /// <summary>Paint the valley into the map's albedo (RGBA8, w x hh, row 0 to the north): fields, the red river,
        /// villages and towns as dots. `heightM` is the relief in metres; `skip` the hero patches' plinths.</summary>
        public void PaintAlbedo(byte[] rgba, int w, int hh, double[] bounds, Func<double, double, double> heightM, Func<double, double, bool> skip)
        {
            double x0 = bounds[0], y1 = bounds[3];
            double px = (bounds[2] - x0) / w, py = (y1 - bounds[1]) / hh;
            double rx0 = double.MaxValue, ry0 = double.MaxValue, rx1 = double.MinValue, ry1 = double.MinValue;
            foreach (var (_, pts, _) in Reaches)
                foreach (var q in pts) { rx0 = Math.Min(rx0, q.X); ry0 = Math.Min(ry0, q.Y); rx1 = Math.Max(rx1, q.X); ry1 = Math.Max(ry1, q.Y); }
            rx0 -= 2.2; ry0 -= 1; rx1 += 2.2; ry1 += 1;
            int i0 = Math.Max(0, (int)((rx0 - x0) / px)), i1 = Math.Min(w - 1, (int)((rx1 - x0) / px));
            int j0 = Math.Max(0, (int)((y1 - ry1) / py)), j1 = Math.Min(hh - 1, (int)((y1 - ry0) / py));
            int bw = i1 - i0 + 1, bh = j1 - j0 + 1;
            // distance to the river (windowed per segment) and its half width there
            var dRiv = new float[bw * bh];
            var half = new float[bw * bh];
            Array.Fill(dRiv, 99f);
            foreach (var (_, pts, width) in Reaches)
                for (int k = 0; k + 1 < pts.Length; k++)
                {
                    var a = pts[k]; var b = pts[k + 1];
                    const double margin = 1.8;
                    int ia = Math.Max(i0, (int)((Math.Min(a.X, b.X) - margin - x0) / px)), ib = Math.Min(i1, (int)((Math.Max(a.X, b.X) + margin - x0) / px));
                    int ja = Math.Max(j0, (int)((y1 - Math.Max(a.Y, b.Y) - margin) / py)), jb = Math.Min(j1, (int)((y1 - Math.Min(a.Y, b.Y) + margin) / py));
                    double ux = b.X - a.X, uy = b.Y - a.Y, l2 = Math.Max(1e-12, ux * ux + uy * uy);
                    for (int j = ja; j <= jb; j++)
                        for (int i = ia; i <= ib; i++)
                        {
                            double x = x0 + (i + 0.5) * px, y = y1 - (j + 0.5) * py;
                            double t = Math.Clamp(((x - a.X) * ux + (y - a.Y) * uy) / l2, 0, 1);
                            float d = (float)Hyp(x - a.X - ux * t, y - a.Y - uy * t);
                            int o = (j - j0) * bw + (i - i0);
                            if (d < dRiv[o]) { dRiv[o] = d; half[o] = (float)(width * 0.5); }
                        }
                }
            var (wr, wg, wb) = Water;
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                {
                    double x = x0 + (i + 0.5) * px, y = y1 - (j + 0.5) * py;
                    if (skip(x, y)) continue;
                    double hm = heightM(x, y);
                    if (hm <= 0) continue;                                             // the sea keeps its colours
                    int o = (j - j0) * bw + (i - i0), p = (j * w + i) * 4;
                    double cr = rgba[p] / 255.0, cg = rgba[p + 1] / 255.0, cb = rgba[p + 2] / 255.0;
                    void Mix(double r, double g, double b, double a)
                    {
                        a = Math.Clamp(a, 0, 1);
                        cr += (r - cr) * a; cg += (g - cg) * a; cb += (b - cb) * a;
                    }
                    double d = dRiv[o];
                    if (d < 2.2)
                    {
                        double fw = d < 1.9 ? FieldWeightFast(x, y, hm, d, half[o]) : 0;
                        if (fw > 0)
                        {
                            // a patchwork of plots (green wheat and clover, ripening gold, flax), darker palm groves by the water
                            double cell = Fbm(Math.Floor(x * 9 + y * 2.5), Math.Floor(y * 7 - x * 2), 2, 31);
                            double fr, fg, fb;
                            if (cell > 0.62) { fr = 0.78; fg = 0.68; fb = 0.30; }
                            else if (cell > 0.5) { fr = 0.58; fg = 0.62; fb = 0.24; }
                            else if (cell > 0.4) { fr = 0.42; fg = 0.58; fb = 0.20; }
                            else { fr = 0.33; fg = 0.50; fb = 0.17; }
                            double n = 0.92 + 0.14 * Fbm(x * 14, y * 14, 2, 33);
                            Mix(fr * n, fg * n, fb * n, fw * 0.88);
                            double grove = 1 - SmoothStep(half[o] + 0.03, half[o] + 0.12, d);
                            Mix(0.22, 0.36, 0.13, grove * 0.7 * fw);
                        }
                        // the river: silt red, a darker wet edge
                        double hr = half[o] * (0.9 + 0.2 * Fbm(x * 6, y * 6, 2, 35));
                        Mix(wr * 0.78, wg * 0.74, wb * 0.72, 1 - SmoothStep(hr, hr + px * 0.9, d));
                        Mix(wr, wg, wb, 1 - SmoothStep(hr * 0.55, hr * 0.85, d));
                    }
                    rgba[p] = (byte)Math.Clamp(cr * 255 + 0.5, 0, 255);
                    rgba[p + 1] = (byte)Math.Clamp(cg * 255 + 0.5, 0, 255);
                    rgba[p + 2] = (byte)Math.Clamp(cb * 255 + 0.5, 0, 255);
                }
            foreach (var v in Villages) Dot(rgba, w, hh, x0, y1, px, py, v.X, v.Y, 0.045, 0.80, 0.70, 0.52, 0.8, skip);
            foreach (var t in Towns) Dot(rgba, w, hh, x0, y1, px, py, t.X, t.Y, 0.12 * t.Size, 0.82, 0.66, 0.50, 0.95, skip);
        }

        double FieldWeightFast(double x, double y, double hm, double d, double half)
        {
            if (hm <= 0.5 || hm > 420 || d < half + 0.02) return 0;
            double edge = 0.12 * (Fbm(x * 0.9, y * 0.9, 3, 21) - 0.5) + 0.1 * Math.Sin(y * 1.3 + x * 0.4);
            double hw = HalfWidth(y);
            double belt = hw > 0 ? 1 - SmoothStep(hw * 0.86, hw, d + edge * hw) : 0;
            belt *= y >= D.Belt.FullY ? 1 : SmoothStep(D.Belt.StartY, D.Belt.FullY, y);
            if (InDelta(x, y)) belt = Math.Max(belt, SmoothStep(0, 0.35, DistToEdge(x, y, _delta)));
            belt *= 1 - SmoothStep(120, 420, hm);
            return Math.Clamp(belt, 0, 1) * SmoothStep(half + 0.02, half + 0.05, d);
        }

        static void Dot(byte[] rgba, int w, int hh, double x0, double y1, double px, double py, double cx, double cy, double rad,
                        double r, double g, double b, double a, Func<double, double, bool> skip)
        {
            int i0 = (int)((cx - rad - x0) / px), i1 = (int)((cx + rad - x0) / px) + 1;
            int j0 = (int)((y1 - cy - rad) / py), j1 = (int)((y1 - cy + rad) / py) + 1;
            for (int j = Math.Max(0, j0); j <= Math.Min(hh - 1, j1); j++)
                for (int i = Math.Max(0, i0); i <= Math.Min(w - 1, i1); i++)
                {
                    double x = x0 + (i + 0.5) * px, y = y1 - (j + 0.5) * py;
                    if (skip(x, y)) continue;
                    double c = Math.Clamp(0.5 + (rad - Hyp(x - cx, y - cy)) / px, 0, 1) * a;
                    int p = (j * w + i) * 4;
                    rgba[p] = (byte)(rgba[p] + (r * 255 - rgba[p]) * c);
                    rgba[p + 1] = (byte)(rgba[p + 1] + (g * 255 - rgba[p + 1]) * c);
                    rgba[p + 2] = (byte)(rgba[p + 2] + (b * 255 - rgba[p + 2]) * c);
                }
        }

        // ---------------------------------------------------------------- the miniature (instance records)

        /// <summary>Instance records (x, y, z = ground, w, d, h, rot, r, g, b, kind) for the villages, the market towns and
        /// the palm groves lining both banks; `s` blend units per real metre of a building (the miniature's scale).</summary>
        public float[] Records(Func<double, double, double> groundUnits, Dictionary<string, int> kinds, double s, int seed = 91)
        {
            var rng = new Random(seed);
            var a = new List<float>();
            void Add(string kind, double x, double y, double w, double d, double h, double rot, (double R, double G, double B) c)
            {
                if (!kinds.TryGetValue(kind, out int k)) return;
                a.AddRange(new[] { (float)x, (float)y, (float)(groundUnits(x, y) - 0.15 * h), (float)w, (float)d, (float)(h * 1.15), (float)rot,
                                   (float)c.R, (float)c.G, (float)c.B, k });
            }
            string roofed = kinds.ContainsKey("roofhouse") ? "roofhouse" : "house";
            (double, double, double) Wall() { double v = rng.NextDouble(); return (0.84 + 0.08 * v, 0.72 + 0.08 * v, 0.54 + 0.06 * v); }
            (double, double, double) Palm() => (0.28 + 0.06 * rng.NextDouble(), 0.42 + 0.06 * rng.NextDouble(), 0.17);
            foreach (var v in Villages)
            {
                for (int k = 0; k < v.Houses; k++)
                {
                    double r = 0.0045 * Math.Sqrt(k + 1), th = k * 2.4 + v.Angle;
                    double x = v.X + r * Math.Cos(th), y = v.Y + r * Math.Sin(th);
                    Add(k == 0 ? "tower" : (rng.NextDouble() < 0.4 ? roofed : "house"), x, y, (k == 0 ? 7 : 12 + 6 * rng.NextDouble()) * s,
                        (k == 0 ? 7 : 10 + 5 * rng.NextDouble()) * s, (k == 0 ? 13 : 5 + 3 * rng.NextDouble()) * s, v.Angle, Wall());
                }
                for (int k = 0; k < 8; k++)
                {
                    double r = 0.01 + 0.012 * rng.NextDouble(), th = rng.NextDouble() * 6.28;
                    Add("palm", v.X + r * Math.Cos(th), v.Y + r * Math.Sin(th), 9 * s, 9 * s, 15 * s, th, Palm());
                }
            }
            foreach (var t in Towns)
            {
                int n = (int)(90 * t.Size);
                for (int k = 0; k < n; k++)
                {
                    double r = 0.0055 * Math.Sqrt(k + 1), th = k * 2.399;
                    Add(k % 19 == 0 ? "tower" : (k % 3 == 0 ? roofed : "house"), t.X + r * Math.Cos(th), t.Y + r * Math.Sin(th),
                        16 * s, 14 * s, (6 + 5 * rng.NextDouble()) * s, 0.2, Wall());
                }
                for (int k = 0; k < 6; k++)                                         // the town's round granaries
                    Add(kinds.ContainsKey("silo") ? "silo" : "warehouse", t.X + 0.06 * t.Size + (k % 2) * 30 * s, t.Y - 0.02 + (k / 2) * 30 * s,
                        26 * s, 26 * s, 28 * s, 0, (0.88, 0.78, 0.60));
            }
            // palm groves lining the banks
            foreach (var (id, pts, width) in Reaches)
            {
                var p = HighDunesRegion.Resample(pts, 0.012);
                for (int k = 1; k < p.Length; k++)
                {
                    double ux = p[k].X - p[k - 1].X, uy = p[k].Y - p[k - 1].Y, l = Math.Max(1e-9, Hyp(ux, uy));
                    double nx = -uy / l, ny = ux / l;
                    foreach (int side in new[] { -1, 1 })
                    {
                        if (rng.NextDouble() < 0.35) continue;
                        double off = width * 0.5 + 0.008 + 0.03 * rng.NextDouble();
                        double x = p[k].X + nx * side * off, y = p[k].Y + ny * side * off;
                        if (InPatch(x, y) || groundUnits(x, y) <= 0) continue;
                        Add("palm", x, y, 9 * s, 9 * s, 15 * s * (0.85 + 0.3 * rng.NextDouble()), rng.NextDouble() * 6.28, Palm());
                    }
                }
            }
            return a.ToArray();
        }

        // ---------------------------------------------------------------- helpers

        static double DistToEdge(double x, double y, (double X, double Y)[] poly)
        {
            double d = double.MaxValue;
            for (int i = 0; i < poly.Length; i++)
            {
                var a = poly[i]; var b = poly[(i + 1) % poly.Length];
                double bx = b.X - a.X, by = b.Y - a.Y;
                double t = Math.Clamp(((x - a.X) * bx + (y - a.Y) * by) / (bx * bx + by * by), 0, 1);
                d = Math.Min(d, Hyp(x - a.X - bx * t, y - a.Y - by * t));
            }
            return d;
        }

        static double Hyp(double x, double y) => Math.Sqrt(x * x + y * y);

        static double SmoothStep(double e0, double e1, double x)
        {
            double t = Math.Clamp((x - e0) / (e1 - e0), 0, 1);
            return t * t * (3 - 2 * t);
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

        static double Fbm(double x, double y, int oct, int seed)
        {
            double s = 0, a = 0.5, n = 0;
            for (int o = 0; o < oct; o++) { s += Value(x, y, seed + o) * a; n += a; a *= 0.5; x *= 2.03; y *= 2.03; }
            return s / n;
        }
    }
}
