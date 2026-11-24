// Polylines in the manifest frame (2D + z): resampling, Chaikin smoothing, arc-length lookup with heading.
using System;
using System.Collections.Generic;

namespace Atlas.Core
{
    public sealed class Polyline
    {
        public readonly Vec3[] P;
        public readonly double[] S;
        public readonly bool Closed;
        public double Length => S[^1];

        public Polyline(IReadOnlyList<Vec3> pts, bool closed = false)
        {
            var list = new List<Vec3>(pts);
            if (closed && list.Count > 1) list.Add(list[0]);
            P = list.ToArray();
            S = new double[P.Length];
            for (int i = 1; i < P.Length; i++) S[i] = S[i - 1] + (P[i] - P[i - 1]).Length2D;
            Closed = closed;
        }

        public static Vec3 V(double[] p) => new(p[0], p[1], p.Length > 2 ? p[2] : 0.0);

        public static List<Vec3> FromArray(double[][] pts)
        {
            var l = new List<Vec3>(pts.Length);
            foreach (var p in pts) l.Add(V(p));
            return l;
        }

        /// <summary>Chaikin corner cutting, `iterations` times (keeps the end points of open lines).</summary>
        public static List<Vec3> Chaikin(List<Vec3> pts, bool closed, int iterations = 2)
        {
            var cur = new List<Vec3>(pts);
            for (int it = 0; it < iterations; it++)
            {
                var q = new List<Vec3>();
                int n = cur.Count;
                if (!closed) q.Add(cur[0]);
                int segs = closed ? n : n - 1;
                for (int i = 0; i < segs; i++)
                {
                    var a = cur[i]; var b = cur[(i + 1) % n];
                    q.Add(a * 0.75 + b * 0.25);
                    q.Add(a * 0.25 + b * 0.75);
                }
                if (!closed) q.Add(cur[n - 1]);
                cur = q;
            }
            return cur;
        }

        /// <summary>Position and heading (radians CCW from +X) at arc length s (wrapped if closed, clamped if open).</summary>
        public (Vec3 Pos, double Heading) At(double s)
        {
            if (Closed) { s %= Length; if (s < 0) s += Length; }
            else s = Math.Clamp(s, 0.0, Length);
            int lo = 0, hi = S.Length - 1;
            while (hi - lo > 1) { int mid = (lo + hi) / 2; if (S[mid] <= s) lo = mid; else hi = mid; }
            double seg = Math.Max(1e-9, S[hi] - S[lo]);
            double t = (s - S[lo]) / seg;
            var a = P[lo]; var b = P[hi];
            var pos = a + (b - a) * t;
            return (pos, Math.Atan2(b.Y - a.Y, b.X - a.X));
        }
    }
}
