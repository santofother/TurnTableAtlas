// River barge traffic on Haven's River Flame (the city view and the Known World): grain barges laden with heaped wheat
// running downstream to the sea, empty barges sailing back up. Each direction keeps its own lane, one either side of the
// channel's middle, and every barge in a lane moves at the lane's speed, so the gaps dealt out at the start (never less
// than the lane's MinGap) hold for ever: no barge can run into the one ahead, and the two streams pass clear of each other.
using System;
using System.Collections.Generic;
using System.Linq;

namespace Atlas.Core
{
    /// <summary>One barge at a moment: position in the lane's frame, heading (radians CCW from +X), length (frame units).</summary>
    public readonly record struct Barge(double X, double Y, double Heading, double Length, bool Laden, bool Visible);

    public sealed class BargeLane
    {
        public readonly string Id;
        public readonly Polyline Path;
        public readonly bool Laden;
        public readonly double Speed, MinGap, Jitter;
        /// <summary>Arc length of one round: the path, then a hidden stretch past its end before the barge comes round again.</summary>
        public readonly double Loop;
        readonly double[] _start, _len, _side;

        public int Count => _start.Length;

        /// <param name="pts">the lane in the order of travel</param>
        /// <param name="jitter">each barge's own fixed offset to the side of the lane, at most this</param>
        public BargeLane(string id, IReadOnlyList<(double X, double Y)> pts, bool laden, double speed, int count, double minGap,
                         double lenMin, double lenMax, double jitter = 0, int seed = 1)
        {
            if (pts.Count < 2) throw new ArgumentException("a lane needs two points");
            if (minGap < lenMax) throw new ArgumentException("barges would overlap: min gap below the longest barge");
            Id = id; Laden = laden; Speed = speed; MinGap = minGap; Jitter = jitter;
            Path = new Polyline(pts.Select(p => new Vec3(p.X, p.Y, 0)).ToList());
            Loop = Path.Length + 2 * lenMax;
            count = Math.Clamp(count, 0, (int)Math.Floor(Loop / minGap));
            var rng = new Random(seed);
            var w = Enumerable.Range(0, count).Select(_ => 0.35 + rng.NextDouble()).ToArray();
            double spare = Loop - count * minGap, sum = w.Sum();
            _start = new double[count]; _len = new double[count]; _side = new double[count];
            double s = rng.NextDouble() * minGap;
            for (int k = 0; k < count; k++)
            {
                _start[k] = s;
                s += minGap + spare * w[k] / sum;   // every gap at least minGap; together they fill the loop exactly
                _len[k] = lenMin + rng.NextDouble() * (lenMax - lenMin);
                _side[k] = (rng.NextDouble() * 2 - 1) * jitter;
            }
        }

        /// <summary>Where barge k is along the lane at time t (arc length, in [0, Loop)).</summary>
        public double ArcAt(int k, double t)
        {
            double s = (_start[k] + Speed * t) % Loop;
            return s < 0 ? s + Loop : s;
        }

        public Barge At(int k, double t)
        {
            double s = ArcAt(k, t);
            bool visible = s <= Path.Length;
            double sc = Math.Min(s, Path.Length);
            var (p, h) = Path.At(sc);
            double look = Math.Max(_len[k] * 0.6, 1e-6);   // heading from the chord across the barge's length: no snapping at vertices
            var tan = Path.At(sc + look).Pos - Path.At(sc - look).Pos;
            if (tan.Length2D > 1e-9) h = Math.Atan2(tan.Y, tan.X);
            double nx = -Math.Sin(h), ny = Math.Cos(h);
            return new Barge(p.X + nx * _side[k], p.Y + ny * _side[k], h, _len[k], Laden, visible);
        }

        public IEnumerable<Barge> All(double t)
        {
            for (int k = 0; k < Count; k++) yield return At(k, t);
        }
    }

    public static class RiverBarges
    {
        /// <summary>Offset a polyline sideways by d(i) (+ to the left of the direction of the points).</summary>
        public static (double X, double Y)[] Offset(IReadOnlyList<(double X, double Y)> pts, Func<int, double> d)
        {
            var o = new (double X, double Y)[pts.Count];
            for (int i = 0; i < pts.Count; i++)
            {
                var a = pts[Math.Max(i - 1, 0)]; var b = pts[Math.Min(i + 1, pts.Count - 1)];
                double dx = b.X - a.X, dy = b.Y - a.Y, l = Math.Max(1e-12, Math.Sqrt(dx * dx + dy * dy));
                o[i] = (pts[i].X - dy / l * d(i), pts[i].Y + dx / l * d(i));
            }
            return o;
        }

        /// <summary>Points every `step` along a polyline, carrying a per-point value (the river's width) by interpolation.</summary>
        public static ((double X, double Y) P, double W)[] Resample(IReadOnlyList<((double X, double Y) P, double W)> pts, double step)
        {
            var outp = new List<((double X, double Y), double)> { pts[0] };
            double carry = 0;
            for (int i = 0; i + 1 < pts.Count; i++)
            {
                var (a, wa) = pts[i]; var (b, wb) = pts[i + 1];
                double L = Math.Sqrt((b.X - a.X) * (b.X - a.X) + (b.Y - a.Y) * (b.Y - a.Y));
                double s = step - carry;
                while (s <= L)
                {
                    double t = s / Math.Max(L, 1e-12);
                    outp.Add(((a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t), wa + (wb - wa) * t));
                    s += step;
                }
                carry = L - (s - step);
            }
            if (carry > step * 0.3) outp.Add(pts[^1]);
            return outp.ToArray();
        }

        /// <summary>Smooth a path's corners (Chaikin, end points kept), so barges turn gently.</summary>
        public static ((double X, double Y) P, double W)[] Smooth(IReadOnlyList<((double X, double Y) P, double W)> pts, int iterations = 2)
        {
            var cur = pts.ToList();
            for (int it = 0; it < iterations; it++)
            {
                var q = new List<((double X, double Y), double)> { cur[0] };
                for (int i = 0; i + 1 < cur.Count; i++)
                {
                    var (a, wa) = cur[i]; var (b, wb) = cur[i + 1];
                    q.Add(((a.X * 0.75 + b.X * 0.25, a.Y * 0.75 + b.Y * 0.25), wa * 0.75 + wb * 0.25));
                    q.Add(((a.X * 0.25 + b.X * 0.75, a.Y * 0.25 + b.Y * 0.75), wa * 0.25 + wb * 0.75));
                }
                q.Add(cur[^1]);
                cur = q;
            }
            return cur.ToArray();
        }

        /// <summary>The two lanes of a river given as its centreline from source to sea with the width at each point:
        /// laden barges downstream to the right of the middle (looking downstream), empty ones upstream on the other side,
        /// each lane `share` of the half-width out from the middle.</summary>
        public static BargeLane[] Lanes(IReadOnlyList<((double X, double Y) P, double W)> centre, double share, BargeSpec down, BargeSpec up)
        {
            var pts = centre.Select(c => c.P).ToArray();
            var dn = Offset(pts, i => -share * centre[i].W / 2);
            var upl = Offset(pts, i => share * centre[i].W / 2).Reverse().ToArray();
            return new[]
            {
                new BargeLane("downstream", dn, true, down.Speed, down.Count, down.MinGap, down.LenMin, down.LenMax, down.Jitter, down.Seed),
                new BargeLane("upstream", upl, false, up.Speed, up.Count, up.MinGap, up.LenMin, up.LenMax, up.Jitter, up.Seed),
            };
        }

        /// <summary>The closest any two visible barges come at time t (centre to centre), and the pair's lanes.</summary>
        public static double MinSpacing(IEnumerable<BargeLane> lanes, double t)
        {
            var all = lanes.SelectMany(l => l.All(t)).Where(b => b.Visible).ToArray();
            double best = double.MaxValue;
            for (int i = 0; i < all.Length; i++)
                for (int j = i + 1; j < all.Length; j++)
                    best = Math.Min(best, Math.Sqrt((all[i].X - all[j].X) * (all[i].X - all[j].X) + (all[i].Y - all[j].Y) * (all[i].Y - all[j].Y)));
            return best;
        }
    }

    public readonly record struct BargeSpec(double Speed, int Count, double MinGap, double LenMin, double LenMax, double Jitter, int Seed);

    /// <summary>city.json `river_traffic` (Haven): the lanes the generator laid and checked (model metres, order of travel).</summary>
    public class RiverTrafficData
    {
        [System.Text.Json.Serialization.JsonPropertyName("z")] public double Z { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("beam")] public double Beam { get; set; } = 0.3;
        [System.Text.Json.Serialization.JsonPropertyName("height")] public double Height { get; set; } = 0.5;
        [System.Text.Json.Serialization.JsonPropertyName("lanes")] public List<RiverLaneData> Lanes { get; set; } = new();

        public BargeLane[] Build() => Lanes.Select(l => new BargeLane(l.Id, l.Points.Select(p => (p[0], p[1])).ToArray(), l.Laden, l.Speed, l.Count,
                                                                      l.MinGap, l.Length[0], l.Length[1], l.Jitter, l.Seed)).ToArray();
    }

    public class RiverLaneData
    {
        [System.Text.Json.Serialization.JsonPropertyName("id")] public string Id { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("laden")] public bool Laden { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("points")] public double[][] Points { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("speed")] public double Speed { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("count")] public int Count { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("min_gap")] public double MinGap { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("length")] public double[] Length { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("jitter")] public double Jitter { get; set; }
        [System.Text.Json.Serialization.JsonPropertyName("seed")] public int Seed { get; set; } = 1;
    }
}
