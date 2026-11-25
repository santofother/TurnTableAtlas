// The High Dunes round Karn Ashur on the Known World, at the relief's own (true) scale: the brief's proposed rivers,
// wadi, caravan corridor and farm belts (atlas/assets/map/known_world/high_dunes.json). Pure C#, no Godot:
//   - grades each river downhill along its trace (a running minimum of the relief from source to mouth), reports the
//     bumps it had to cut through, and carves the channel into the relief's heights;
//   - caps the massif's other summits below Karn Ashur's great peak (the lore's "largest of the snow-crowned peaks");
//   - paints the region into the map's albedo: red rock on the massif, sand at its feet, snow on the summits, green
//     farm belts along the rivers, the rivers, the dry wadi, villages and market towns as dots;
//   - places the villages and market towns (for the instanced miniature) and adds up their people.
// Lengths are blend units (1 = 10 miles), +x east, +y north; relief heights are blend units (metres x exag / unitM).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Atlas.Core
{
    public class HighDunesData
    {
        [JsonPropertyName("region")] public double[][] Region { get; set; }
        [JsonPropertyName("rivers")] public List<HdRiver> Rivers { get; set; } = new();
        [JsonPropertyName("south_river_tie_in")] public double[][] TieIn { get; set; }
        [JsonPropertyName("caravan_corridor")] public double[][] Corridor { get; set; }
        [JsonPropertyName("farm_belts")] public Dictionary<string, double[][]> FarmBelts { get; set; } = new();
        [JsonPropertyName("towns")] public List<HdTown> Towns { get; set; } = new();
        [JsonPropertyName("population")] public Dictionary<string, double> Population { get; set; } = new();
        [JsonPropertyName("snow_line_m")] public double SnowLineM { get; set; } = 3050;
        [JsonPropertyName("summit_cap_m")] public double SummitCapM { get; set; } = 3350;

        public static HighDunesData Load(string path) => JsonSerializer.Deserialize<HighDunesData>(File.ReadAllText(path));
    }

    public class HdRiver
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("label")] public string Label { get; set; }
        [JsonPropertyName("pts")] public double[][] Pts { get; set; }
        [JsonPropertyName("seasonal")] public bool Seasonal { get; set; }
        [JsonPropertyName("to_sea")] public bool ToSea { get; set; }
        [JsonPropertyName("depth_m")] public double DepthM { get; set; } = 25;
    }

    public class HdTown
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("label")] public string Label { get; set; }
        [JsonPropertyName("at")] public double[] At { get; set; }
        [JsonPropertyName("kind")] public string Kind { get; set; }
        [JsonPropertyName("size")] public double Size { get; set; } = 1;
    }

    public sealed class HighDunesRegion
    {
        public sealed class RiverRun
        {
            public string Id, Label;
            public bool Seasonal, ToSea;
            public double DepthM;
            public (double X, double Y)[] Pts;
            public double[] S;                    // arclength (units)
            public double[] BedM;                 // graded bed (metres), non-increasing from source to mouth
            public double MaxUphillM, MaxCarveM, DropM;
            /// <summary>Where the trace climbed most above the bed graded so far (the bump the channel cuts through).</summary>
            public (double X, double Y) UphillAt;
            public double Length => S[^1];
            public double BedAt(double s)
            {
                int i = Array.BinarySearch(S, s);
                if (i >= 0) return BedM[i];
                i = ~i;
                if (i <= 0) return BedM[0];
                if (i >= S.Length) return BedM[^1];
                double t = (s - S[i - 1]) / (S[i] - S[i - 1]);
                return BedM[i - 1] + (BedM[i] - BedM[i - 1]) * t;
            }
        }

        public readonly record struct Town(string Id, string Label, string Kind, double X, double Y, double Size);
        public readonly record struct Village(double X, double Y, int Houses, double Angle);

        public readonly HighDunesData D;
        public readonly double UnitM, Exag;
        public readonly List<RiverRun> Rivers = new();
        public (double X, double Y)[] Corridor { get; private set; }
        /// <summary>Where the eastern tributary reaches the basin's patch (its last point).</summary>
        public (double X, double Y)? TributaryEntry => D.Rivers.FirstOrDefault(r => r.Id == "east_tributary")?.Pts is { Length: > 0 } t ? (t[^1][0], t[^1][1]) : null;
        public readonly List<Town> Towns = new();
        public readonly List<Village> Villages = new();
        readonly (double X, double Y)[] _region;
        readonly List<(double X, double Y)[]> _belts;
        (double X, double Y)[] _outlet;

        public HighDunesRegion(HighDunesData d, double unitM, double exag)
        {
            D = d; UnitM = unitM; Exag = exag;
            _region = d.Region.Select(p => (p[0], p[1])).ToArray();
            _belts = d.FarmBelts.Values.Select(b => b.Select(p => (p[0], p[1])).ToArray()).ToList();
            Corridor = d.Corridor.Select(p => (p[0], p[1])).ToArray();
            foreach (var t in d.Towns) Towns.Add(new Town(t.Id.Split(' ')[0], t.Label, t.Kind, t.At[0], t.At[1], t.Size));
        }

        public double M(double units) => units * UnitM / Exag;
        public double U(double metres) => metres / UnitM * Exag;
        public int Population => (int)(Villages.Count * D.Population.GetValueOrDefault("per_village", 650)
                                       + Towns.Sum(t => t.Size) * D.Population.GetValueOrDefault("per_town", 9000));

        // ---------------------------------------------------------------- links to the basin

        /// <summary>The basin's outlet (where its valley meets the relief) joins the southern river: a short river of its own.</summary>
        public void LinkOutlet((double X, double Y) from)
        {
            var south = D.Rivers.First(r => r.Id == "south_river").Pts.Select(p => (p[0], p[1])).ToArray();
            var tie = D.TieIn?.LastOrDefault();
            (double X, double Y) to = tie != null ? (tie[0], tie[1]) : south[0];
            // the nearest point of the southern river to the brief's tie-in end
            double best = double.MaxValue;
            foreach (var p in south)
            {
                double dd = Hyp(p.Item1 - to.X, p.Item2 - to.Y);
                if (dd < best) { best = dd; to = p; }
            }
            var pts = new List<(double X, double Y)>();
            for (int i = 0; i <= 12; i++)
            {
                double t = i / 12.0, off = 0.12 * Math.Sin(Math.PI * t) * Math.Sin(t * 5.3);
                double dx = to.X - from.X, dy = to.Y - from.Y, len = Hyp(dx, dy);
                pts.Add((from.X + dx * t - dy / len * off, from.Y + dy * t + dx / len * off));
            }
            _outlet = pts.ToArray();
        }

        /// <summary>The caravan corridor ends at the basin's road (the patch carries it on to the freight gate).</summary>
        public void LinkRoad((double X, double Y) roadEnd, Func<double, double, bool> inPatch)
        {
            var keep = Corridor.Where(p => !inPatch(p.X, p.Y)).ToList();
            keep.Add(roadEnd);
            Corridor = keep.ToArray();
        }

        // ---------------------------------------------------------------- heights

        /// <summary>Grade, carve and cap the relief (blend units, w x h, row 0 to the north) in place. `skip` marks the
        /// hero patches (their own ground replaces the relief there).</summary>
        public void EditHeights(float[] h, int w, int hh, double[] bounds, Func<double, double, bool> skip,
                                Func<double, double, double?> basinMetres = null)
        {
            double x0 = bounds[0], y0 = bounds[1], x1 = bounds[2], y1 = bounds[3];
            double px = (x1 - x0) / (w - 1), py = (y1 - y0) / (hh - 1);
            double Hm(double x, double y) => M(Bilinear(h, w, hh, (x - x0) / px, (y1 - y) / py));
            double Surface(double x, double y) => basinMetres?.Invoke(x, y) ?? Hm(x, y);
            // 1. the other summits of the massif stay below the great peak
            var (rx0, ry0, rx1, ry1) = Bounds(_region, 2);
            double cap = D.SummitCapM, knee = cap - 380;
            for (int j = (int)Math.Max(0, (y1 - ry1) / py); j <= Math.Min(hh - 1, (y1 - ry0) / py); j++)
                for (int i = (int)Math.Max(0, (rx0 - x0) / px); i <= Math.Min(w - 1, (rx1 - x0) / px); i++)
                {
                    double x = x0 + i * px, y = y1 - j * py;
                    double mw = RegionWeight(x, y);
                    if (mw <= 0 || skip(x, y)) continue;
                    double m = M(h[j * w + i]);
                    if (m <= knee) continue;
                    double c = knee + (cap - knee) * Math.Tanh((m - knee) / (cap - knee));
                    h[j * w + i] = (float)U(m + (c - m) * mw);
                }
            // 2. grade and carve each river, the basin's outlet first (it feeds the southern river)
            var runs = new List<(string Id, string Label, bool Seasonal, bool ToSea, double Depth, (double X, double Y)[] Pts)>();
            if (_outlet != null) runs.Add(("basin_outlet", "The outlet of the Karn Ashur basin", false, false, 22, _outlet));
            foreach (var r in D.Rivers) runs.Add((r.Id, r.Label, r.Seasonal, r.ToSea, r.DepthM, r.Pts.Select(p => (p[0], p[1])).ToArray()));
            foreach (var (id, label, seasonal, toSea, depth, raw) in runs)
            {
                var pts = Resample(raw, 0.08);
                var s = new double[pts.Length];
                for (int k = 1; k < pts.Length; k++) s[k] = s[k - 1] + Hyp(pts[k].X - pts[k - 1].X, pts[k].Y - pts[k - 1].Y);
                var bed = new double[pts.Length];
                double first = double.NaN;
                for (int k = 0; k < pts.Length && double.IsNaN(first); k++)
                    if (!skip(pts[k].X, pts[k].Y)) first = Math.Max(Surface(pts[k].X, pts[k].Y), 0);
                if (double.IsNaN(first)) continue;
                double run = first, uphill = 0, carve = 0;
                (double X, double Y) upAt = pts[0];
                for (int k = 0; k < pts.Length; k++)
                {
                    double m = skip(pts[k].X, pts[k].Y) ? run : Math.Max(Surface(pts[k].X, pts[k].Y), 0);
                    if (m - run > uphill) { uphill = m - run; upAt = pts[k]; }
                    run = Math.Min(run, m);
                    bed[k] = run - depth * (k == 0 ? 0 : 1);
                    if (toSea && k == pts.Length - 1) bed[k] = Math.Min(bed[k], -5);
                    carve = Math.Max(carve, m - bed[k]);
                }
                for (int k = 1; k < bed.Length; k++) bed[k] = Math.Min(bed[k], bed[k - 1]);
                var rr = new RiverRun { Id = id, Label = label, Seasonal = seasonal, ToSea = toSea, DepthM = depth, Pts = pts, S = s, BedM = bed,
                                        MaxUphillM = uphill, MaxCarveM = carve, DropM = bed[0] - bed[^1], UphillAt = upAt };
                Rivers.Add(rr);
                Carve(h, w, hh, x0, y1, px, py, rr, skip);
            }
        }

        void Carve(float[] h, int w, int hh, double x0, double y1, double px, double py, RiverRun r, Func<double, double, bool> skip)
        {
            double rad = 1.6 * px;
            for (int k = 0; k + 1 < r.Pts.Length; k++)
            {
                var a = r.Pts[k]; var b = r.Pts[k + 1];
                int i0 = (int)Math.Floor((Math.Min(a.X, b.X) - rad - x0) / px), i1 = (int)Math.Ceiling((Math.Max(a.X, b.X) + rad - x0) / px);
                int j0 = (int)Math.Floor((y1 - Math.Max(a.Y, b.Y) - rad) / py), j1 = (int)Math.Ceiling((y1 - Math.Min(a.Y, b.Y) + rad) / py);
                for (int j = Math.Max(0, j0); j <= Math.Min(hh - 1, j1); j++)
                    for (int i = Math.Max(0, i0); i <= Math.Min(w - 1, i1); i++)
                    {
                        double x = x0 + i * px, y = y1 - j * py;
                        if (skip(x, y)) continue;
                        double bx = b.X - a.X, by = b.Y - a.Y;
                        double t = Math.Clamp(((x - a.X) * bx + (y - a.Y) * by) / Math.Max(1e-12, bx * bx + by * by), 0, 1);
                        double d = Hyp(x - a.X - bx * t, y - a.Y - by * t);
                        if (d > rad) continue;
                        double bed = r.BedM[k] + (r.BedM[k + 1] - r.BedM[k]) * t;
                        double want = bed + (M(h[j * w + i]) - bed) * SmoothStep(0.45 * px, rad, d);
                        h[j * w + i] = (float)Math.Min(h[j * w + i], U(want));
                    }
            }
        }

        // ---------------------------------------------------------------- villages and towns

        /// <summary>Villages along the rivers in the farm belts and up the mountain valleys, hamlets at the wadi's wells,
        /// with dry ground between them. `heightM` is the (edited) relief in metres.</summary>
        public void PlaceSettlements(Func<double, double, double> heightM, Func<double, double, bool> skip, int seed = 1124)
        {
            var rng = new Random(seed);
            Villages.Clear();
            bool Clear(double x, double y, double min) => Villages.All(v => Hyp(v.X - x, v.Y - y) > min)
                                                         && Towns.All(t => Hyp(t.X - x, t.Y - y) > 0.55 * t.Size + 0.2);
            foreach (var r in Rivers)
            {
                double step = r.Seasonal ? 1.6 : 0.2;
                for (double s = 0.2; s < r.Length; s += step * (0.7 + 0.6 * rng.NextDouble()))
                {
                    var (x, y, nx, ny) = Along(r, s);
                    if (r.BedAt(s) <= 2) continue;                                  // the estuary
                    for (int tries = 0; tries < 3; tries++)
                    {
                        double side = rng.NextDouble() < 0.5 ? -1 : 1, off = r.Seasonal ? 0.05 + 0.1 * rng.NextDouble() : 0.1 + 0.32 * rng.NextDouble();
                        double vx = x + nx * side * off, vy = y + ny * side * off;
                        if (skip(vx, vy) || RegionWeight(vx, vy) < 0.5) continue;
                        double hm = heightM(vx, vy);
                        bool belt = InBelt(vx, vy);
                        bool valley = hm > 600 && hm < 2300;                          // the narrow green valleys up the massif
                        if (hm <= 2 || (!belt && !valley && !r.Seasonal)) continue;
                        if (!belt && rng.NextDouble() < 0.45) continue;               // fewer outside the belts
                        if (!Clear(vx, vy, r.Seasonal ? 0.8 : 0.2)) continue;
                        int houses = r.Seasonal ? 3 + rng.Next(3) : 5 + rng.Next(6);
                        Villages.Add(new Village(vx, vy, houses, rng.NextDouble() * Math.PI));
                        break;
                    }
                }
            }
        }

        (double X, double Y, double Nx, double Ny) Along(RiverRun r, double s)
        {
            int k = Math.Clamp(Array.BinarySearch(r.S, s) is var i && i < 0 ? ~i - 1 : i, 0, r.Pts.Length - 2);
            var a = r.Pts[k]; var b = r.Pts[k + 1];
            double t = Math.Clamp((s - r.S[k]) / Math.Max(1e-9, r.S[k + 1] - r.S[k]), 0, 1);
            double dx = b.X - a.X, dy = b.Y - a.Y, len = Math.Max(1e-9, Hyp(dx, dy));
            return (a.X + dx * t, a.Y + dy * t, -dy / len, dx / len);
        }

        // ---------------------------------------------------------------- the albedo

        /// <summary>Paint the region into the map's albedo (RGBA8, w x hh, row 0 to the north). `heightM` gives the edited
        /// relief in metres; `skip` the hero patches.</summary>
        public void PaintAlbedo(byte[] rgba, int w, int hh, double[] bounds, Func<double, double, double> heightM, Func<double, double, bool> skip)
        {
            double x0 = bounds[0], y0 = bounds[1], x1 = bounds[2], y1 = bounds[3];
            double px = (x1 - x0) / w, py = (y1 - y0) / hh;
            var (rx0, ry0, rx1, ry1) = Bounds(_region, 2.5);
            foreach (var r in Rivers) { var (a, b, c, d) = Bounds(r.Pts, 1.0); rx0 = Math.Min(rx0, a); ry0 = Math.Min(ry0, b); rx1 = Math.Max(rx1, c); ry1 = Math.Max(ry1, d); }
            int i0 = Math.Max(0, (int)((rx0 - x0) / px)), i1 = Math.Min(w - 1, (int)((rx1 - x0) / px));
            int j0 = Math.Max(0, (int)((y1 - ry1) / py)), j1 = Math.Min(hh - 1, (int)((y1 - ry0) / py));
            int bw = i1 - i0 + 1, bh = j1 - j0 + 1;
            // distance to the rivers (and to the perennial ones alone), per pixel of the window
            var dRiv = new float[bw * bh]; var dPer = new float[bw * bh]; var dWadi = new float[bw * bh];
            Array.Fill(dRiv, 99f); Array.Fill(dPer, 99f); Array.Fill(dWadi, 99f);
            foreach (var r in Rivers)
                for (int k = 0; k + 1 < r.Pts.Length; k++)
                {
                    var a = r.Pts[k]; var b = r.Pts[k + 1];
                    double margin = r.Seasonal ? 0.7 : 1.5;
                    int ia = Math.Max(i0, (int)((Math.Min(a.X, b.X) - margin - x0) / px)), ib = Math.Min(i1, (int)((Math.Max(a.X, b.X) + margin - x0) / px));
                    int ja = Math.Max(j0, (int)((y1 - Math.Max(a.Y, b.Y) - margin) / py)), jb = Math.Min(j1, (int)((y1 - Math.Min(a.Y, b.Y) + margin) / py));
                    for (int j = ja; j <= jb; j++)
                        for (int i = ia; i <= ib; i++)
                        {
                            double x = x0 + (i + 0.5) * px, y = y1 - (j + 0.5) * py;
                            double bx = b.X - a.X, by = b.Y - a.Y;
                            double t = Math.Clamp(((x - a.X) * bx + (y - a.Y) * by) / Math.Max(1e-12, bx * bx + by * by), 0, 1);
                            float d = (float)Hyp(x - a.X - bx * t, y - a.Y - by * t);
                            int o = (j - j0) * bw + (i - i0);
                            if (r.Seasonal) dWadi[o] = Math.Min(dWadi[o], d);
                            else { dPer[o] = Math.Min(dPer[o], d); dRiv[o] = Math.Min(dRiv[o], d); }
                        }
                }
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                {
                    double x = x0 + (i + 0.5) * px, y = y1 - (j + 0.5) * py;
                    if (skip(x, y)) continue;
                    int o = (j - j0) * bw + (i - i0), p = (j * w + i) * 4;
                    double cr = rgba[p] / 255.0, cg = rgba[p + 1] / 255.0, cb = rgba[p + 2] / 255.0;
                    double hm = heightM(x, y);
                    if (hm <= 0) continue;                                             // the sea keeps its colours
                    double rw = RegionWeight(x, y);
                    double n1 = Fbm(x * 1.7, y * 1.7, 3, 5), n2 = Fbm(x * 9, y * 9, 2, 6);
                    void Mix(double r, double g, double b, double a)
                    {
                        a = Math.Clamp(a, 0, 1);
                        cr += (r - cr) * a; cg += (g - cg) * a; cb += (b - cb) * a;
                    }
                    if (rw > 0)
                    {
                        // sand at the mountains' feet, red rock above, darker high rock, snow on the summits
                        double feet = SmoothStep(560, 760, hm) * (1 - SmoothStep(950, 1350, hm));
                        Mix(0.86 + 0.04 * n2, 0.63 + 0.04 * n2, 0.38, feet * 0.72 * rw);
                        double rock = SmoothStep(1050, 1600, hm);
                        double band = 0.5 + 0.5 * Math.Sin(hm / 140.0 + 4 * n1);
                        Mix(0.60 + 0.12 * band, 0.31 + 0.08 * band, 0.21 + 0.05 * band, rock * 0.78 * rw);
                        Mix(0.48, 0.38, 0.34, SmoothStep(2300, 2900, hm) * 0.6 * rw);
                        double snow = SmoothStep(D.SnowLineM - 180 + 160 * (n1 - 0.5), D.SnowLineM + 60, hm);
                        Mix(0.95, 0.96, 0.98, snow * 0.95 * rw);
                    }
                    // green farm belts along the perennial rivers (and the narrow valleys up the massif)
                    double dp = dPer[o];
                    if (dp < 1.5 || dWadi[o] < 0.7)
                    {
                        bool belt = InBelt(x, y);
                        double reach = belt ? 1.45 : 0.88;
                        double grade = Hyp(heightM(x + px, y) - hm, heightM(x, y + py) - hm) / (px * UnitM);
                        double tillable = (1 - SmoothStep(0.06, 0.20, grade)) * (1 - SmoothStep(1950, 2400, hm));
                        double g = (1 - SmoothStep(reach * 0.45, reach, dp + 0.08 * (n1 - 0.5))) * (hm < 2300 ? 1 : 0);
                        double well = (1 - SmoothStep(0.15, 0.65, dWadi[o])) * SmoothStep(0.38, 0.66, n1);
                        g = Math.Max(g, well) * tillable;
                        double patch = Fbm(Math.Floor(x * 7 + y * 2), Math.Floor(y * 10 - x * 3), 2, 9);
                        double fr = patch > 0.62 ? 0.72 : patch > 0.45 ? 0.45 : 0.30, fg = patch > 0.62 ? 0.70 : patch > 0.45 ? 0.62 : 0.52, fb = patch > 0.62 ? 0.34 : 0.24;
                        Mix(fr, fg, fb, g * 0.94);
                    }
                    // the rivers themselves, the dry wadi's bed
                    if (dRiv[o] < 0.2) Mix(0.20, 0.44, 0.54, 1 - SmoothStep(0.05, 0.13, dRiv[o]));
                    if (dWadi[o] < 0.15)
                    {
                        Mix(0.90, 0.80, 0.62, (1 - SmoothStep(0.03, 0.1, dWadi[o])) * 0.9);
                        Mix(0.55, 0.43, 0.30, (SmoothStep(0.05, 0.08, dWadi[o]) - SmoothStep(0.08, 0.13, dWadi[o])) * 0.5);
                    }
                    rgba[p] = (byte)Math.Clamp(cr * 255 + 0.5, 0, 255);
                    rgba[p + 1] = (byte)Math.Clamp(cg * 255 + 0.5, 0, 255);
                    rgba[p + 2] = (byte)Math.Clamp(cb * 255 + 0.5, 0, 255);
                }
            // villages and towns as dots
            foreach (var v in Villages) Dot(rgba, w, hh, x0, y1, px, py, v.X, v.Y, 0.05, 0.56, 0.40, 0.28, 0.85, skip);
            foreach (var t in Towns) Dot(rgba, w, hh, x0, y1, px, py, t.X, t.Y, 0.14 * t.Size, 0.50, 0.34, 0.24, 0.95, skip);
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

        /// <summary>Instance records in world units (x, y, z = ground, w, d, h, rot, r, g, b, kind) for the villages and
        /// towns, `s` blend units per real metre of a building (the basin miniature's scale).</summary>
        public float[] Records(Func<double, double, double> groundUnits, Dictionary<string, int> kinds, double s, int seed = 77)
        {
            var rng = new Random(seed);
            var a = new List<float>();
            void Add(string kind, double x, double y, double w, double d, double h, double rot, (double R, double G, double B) c)
            {
                if (!kinds.TryGetValue(kind, out int k)) return;
                a.AddRange(new[] { (float)x, (float)y, (float)(groundUnits(x, y) - 0.4 * h), (float)w, (float)d, (float)(h * 1.4), (float)rot,
                                   (float)c.R, (float)c.G, (float)c.B, k });
            }
            (double, double, double) Wall() { double v = rng.NextDouble(); return (0.78 + 0.08 * v, 0.60 + 0.08 * v, 0.40 + 0.06 * v); }
            foreach (var v in Villages)
            {
                for (int k = 0; k < v.Houses; k++)
                {
                    double r = 0.006 * Math.Sqrt(k + 1), th = k * 2.4 + v.Angle;
                    double x = v.X + r * Math.Cos(th), y = v.Y + r * Math.Sin(th);
                    Add(k == 0 ? "tower" : "house", x, y, (k == 0 ? 8 : 12 + 6 * rng.NextDouble()) * s, (k == 0 ? 8 : 11 + 5 * rng.NextDouble()) * s,
                        (k == 0 ? 13 : 5 + 4 * rng.NextDouble()) * s, v.Angle, Wall());
                }
                for (int k = 0; k < 6; k++)
                {
                    double r = 0.012 + 0.012 * rng.NextDouble(), th = rng.NextDouble() * 6.28;
                    Add("palm", v.X + r * Math.Cos(th), v.Y + r * Math.Sin(th), 9 * s, 9 * s, 15 * s, th, (0.30, 0.44, 0.18));
                }
            }
            foreach (var t in Towns)
            {
                int n = (int)(70 * t.Size);
                for (int k = 0; k < n; k++)
                {
                    double r = 0.007 * Math.Sqrt(k + 1), th = k * 2.399;
                    double x = t.X + r * Math.Cos(th), y = t.Y + r * Math.Sin(th);
                    Add(k % 17 == 0 ? "tower" : "house", x, y, 16 * s, 15 * s, (6 + 6 * rng.NextDouble()) * s, 0.3, Wall());
                }
                // a caravanserai and granaries on the town's edge
                double cx = t.X + 0.09 * t.Size, cy = t.Y - 0.04;
                foreach (var (u, vv, w, d) in new[] { (0.0, -1.0, 2.0, 0.3), (0.0, 1.0, 2.0, 0.3), (-1.0, 0.0, 0.3, 2.0), (1.0, 0.0, 0.3, 2.0) })
                    Add("wall", cx + u * 45 * s, cy + vv * 45 * s, w * 45 * s, d * 45 * s, 8 * s, 0, (0.74, 0.48, 0.32));
                for (int k = 0; k < 4; k++)
                    Add("warehouse", cx - 0.04 * t.Size, cy - 0.05 + k * 22 * s, 60 * s, 14 * s, 10 * s, 0, (0.82, 0.66, 0.46));
            }
            return a.ToArray();
        }

        // ---------------------------------------------------------------- helpers

        public bool InBelt(double x, double y) => _belts.Any(b => InPoly(x, y, b));

        /// <summary>1 well inside the region's outline, fading to 0 over 1.5 units outside it.</summary>
        public double RegionWeight(double x, double y)
        {
            if (InPoly(x, y, _region)) return 1;
            double d = double.MaxValue;
            for (int i = 0; i < _region.Length; i++)
            {
                var a = _region[i]; var b = _region[(i + 1) % _region.Length];
                double bx = b.X - a.X, by = b.Y - a.Y;
                double t = Math.Clamp(((x - a.X) * bx + (y - a.Y) * by) / (bx * bx + by * by), 0, 1);
                d = Math.Min(d, Hyp(x - a.X - bx * t, y - a.Y - by * t));
            }
            return 1 - SmoothStep(0, 1.5, d);
        }

        public static bool InPoly(double x, double y, (double X, double Y)[] p)
        {
            bool c = false;
            for (int i = 0, j = p.Length - 1; i < p.Length; j = i++)
                if ((p[i].Y > y) != (p[j].Y > y) && x < (p[j].X - p[i].X) * (y - p[i].Y) / (p[j].Y - p[i].Y) + p[i].X) c = !c;
            return c;
        }

        static (double, double, double, double) Bounds((double X, double Y)[] p, double pad) =>
            (p.Min(q => q.X) - pad, p.Min(q => q.Y) - pad, p.Max(q => q.X) + pad, p.Max(q => q.Y) + pad);

        public static (double X, double Y)[] Resample((double X, double Y)[] p, double step)
        {
            var o = new List<(double X, double Y)> { p[0] };
            for (int i = 0; i + 1 < p.Length; i++)
            {
                double dx = p[i + 1].X - p[i].X, dy = p[i + 1].Y - p[i].Y;
                int n = Math.Max(1, (int)Math.Ceiling(Hyp(dx, dy) / step));
                for (int k = 1; k <= n; k++) o.Add((p[i].X + dx * k / n, p[i].Y + dy * k / n));
            }
            return o.ToArray();
        }

        public static double Bilinear(float[] a, int w, int hh, double fx, double fy)
        {
            fx = Math.Clamp(fx, 0, w - 1.000001); fy = Math.Clamp(fy, 0, hh - 1.000001);
            int i = (int)fx, j = (int)fy;
            double tx = fx - i, ty = fy - j;
            double p = a[j * w + i] + (a[j * w + i + 1] - a[j * w + i]) * tx;
            double q = a[(j + 1) * w + i] + (a[(j + 1) * w + i + 1] - a[(j + 1) * w + i]) * tx;
            return p + (q - p) * ty;
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
