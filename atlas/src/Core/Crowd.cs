// People on the street graph: wandering walkers (density by hour) and streams heading to venue entrances
// (or leaving them). Pure simulation; the Godot side only draws Positions/Headings.
using System;
using System.Collections.Generic;
using System.Linq;

namespace Atlas.Core
{
    public sealed class StreetGraph
    {
        public readonly Vec3[] Nodes;
        public readonly List<(int To, double Len)>[] Adj;

        public StreetGraph(StreetGraphData g)
        {
            Nodes = g.Nodes.Select(Polyline.V).ToArray();
            Adj = new List<(int, double)>[Nodes.Length];
            for (int i = 0; i < Nodes.Length; i++) Adj[i] = new List<(int, double)>();
            foreach (var e in g.Edges)
            {
                int a = (int)e[0], b = (int)e[1];
                double len = Math.Max(1e-4, (Nodes[a] - Nodes[b]).Length2D);
                Adj[a].Add((b, len));
                Adj[b].Add((a, len));
            }
        }

        public int Nearest(double x, double y)
        {
            int best = 0; double bd = double.MaxValue;
            for (int i = 0; i < Nodes.Length; i++)
            {
                double dx = Nodes[i].X - x, dy = Nodes[i].Y - y, d = dx * dx + dy * dy;
                if (d < bd) { bd = d; best = i; }
            }
            return best;
        }

        /// <summary>Multi-source Dijkstra: for every node, the next hop toward the nearest target and the distance.</summary>
        public (int[] Next, double[] Dist) RouteTo(IEnumerable<int> targets)
        {
            var dist = Enumerable.Repeat(double.MaxValue, Nodes.Length).ToArray();
            var next = Enumerable.Repeat(-1, Nodes.Length).ToArray();
            var pq = new PriorityQueue<int, double>();
            foreach (var t in targets) { dist[t] = 0; next[t] = t; pq.Enqueue(t, 0); }
            while (pq.TryDequeue(out var u, out var d))
            {
                if (d > dist[u]) continue;
                foreach (var (v, w) in Adj[u])
                {
                    double nd = d + w;
                    if (nd < dist[v]) { dist[v] = nd; next[v] = u; pq.Enqueue(v, nd); }
                }
            }
            return (next, dist);
        }
    }

    public sealed class Walker
    {
        public int From, To;
        public double T, Speed, Side;
        public int Prev = -1;
        public bool Active = true;
        public int Kind;            // which figure mesh
        public int Stream = -1;     // -1 wandering, else index of the stream it belongs to
        public double StartAt;      // streams: when this person sets off
    }

    public sealed class Crowd
    {
        public readonly StreetGraph G;
        public readonly List<Walker> W = new();
        readonly Random _rng;
        readonly List<(int[] Next, double[] Dist, bool Leaving, HashSet<int> Targets)> _streams = new();
        public double Time;
        public int Wanderers;

        public Crowd(StreetGraph g, int wanderers, int seed = 1)
        {
            G = g; _rng = new Random(seed);
            Wanderers = wanderers;
            for (int i = 0; i < wanderers; i++) W.Add(NewWanderer());
        }

        Walker NewWanderer()
        {
            int a = _rng.Next(G.Nodes.Length);
            while (G.Adj[a].Count == 0) a = _rng.Next(G.Nodes.Length);
            var (b, _) = G.Adj[a][_rng.Next(G.Adj[a].Count)];
            return new Walker { From = a, To = b, T = _rng.NextDouble(), Speed = 0.09 + 0.06 * _rng.NextDouble(),
                                Side = (_rng.NextDouble() * 2 - 1) * 0.09, Kind = _rng.Next(2) };
        }

        /// <summary>How busy the streets are by hour (same curve as blender/cinematic/crowds.py).</summary>
        public static double DensityAt(double hour)
        {
            double h = ((hour % 24) + 24) % 24;
            double S(double e0, double e1, double x) { var t = Math.Clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); }
            double day = S(5.0, 8.5, h) * (1.0 - S(21.0, 23.5, h));
            double siesta = 1.0 - 0.25 * Math.Exp(-Math.Pow((h - 14.5) / 1.6, 2));
            return 0.06 + 0.94 * day * siesta;
        }

        /// <summary>Send `count` people to the nearest of `targets` (or, leaving, from targets out into the streets).
        /// They set off spread over `window` seconds from now, at random graph nodes within `radius` metres.</summary>
        public int AddStream(IEnumerable<int> targets, int count, double window, bool leaving = false, double radius = 40)
        {
            var tset = targets.ToHashSet();
            var (next, dist) = G.RouteTo(tset);
            int sid = _streams.Count;
            _streams.Add((next, dist, leaving, tset));
            var starts = Enumerable.Range(0, G.Nodes.Length).Where(i => dist[i] > 3 && dist[i] < radius).ToList();
            if (starts.Count == 0) return sid;
            for (int i = 0; i < count; i++)
            {
                int a;
                if (!leaving) a = starts[_rng.Next(starts.Count)];
                else a = tset.ElementAt(_rng.Next(tset.Count));
                var w = new Walker { From = a, To = a, T = 1, Speed = 0.12 + 0.06 * _rng.NextDouble(), Side = (_rng.NextDouble() * 2 - 1) * 0.1,
                                     Kind = _rng.Next(2), Stream = sid, StartAt = Time + _rng.NextDouble() * window, Active = false };
                if (leaving) w.Prev = -2;     // marker: walk away from the venue until far enough
                W.Add(w);
            }
            return sid;
        }

        public int StreamRemaining(int sid) => W.Count(w => w.Stream == sid);

        public void Step(double dt, double density)
        {
            Time += dt;
            int active = (int)Math.Round(Wanderers * Math.Clamp(density, 0, 1));
            for (int i = W.Count - 1; i >= 0; i--)
            {
                var w = W[i];
                if (w.Stream < 0) w.Active = i < active;
                else if (!w.Active) { if (Time >= w.StartAt) w.Active = true; else continue; }
                if (!w.Active) continue;
                double len = Math.Max(1e-4, (G.Nodes[w.To] - G.Nodes[w.From]).Length2D);
                w.T += w.Speed * dt / len;
                while (w.T >= 1.0)
                {
                    w.T -= 1.0;
                    if (!Arrive(w)) { W.RemoveAt(i); break; }
                    len = Math.Max(1e-4, (G.Nodes[w.To] - G.Nodes[w.From]).Length2D);
                }
            }
        }

        bool Arrive(Walker w)
        {
            int at = w.To;
            if (w.Stream >= 0)
            {
                var s = _streams[w.Stream];
                if (!s.Leaving)
                {
                    if (s.Targets.Contains(at)) return false;                 // entered the venue
                    int nx = s.Next[at];
                    if (nx < 0 || nx == at) return false;
                    w.From = at; w.To = nx; return true;
                }
                // leaving: walk uphill in distance, then melt into the crowd
                if (s.Dist[at] > 25) return false;
                var opts = G.Adj[at].Where(e => s.Dist[e.To] > s.Dist[at]).ToList();
                if (opts.Count == 0) return false;
                w.From = at; w.To = opts[_rng.Next(opts.Count)].To; return true;
            }
            var adj = G.Adj[at];
            if (adj.Count == 0) return true;
            int pick = adj[_rng.Next(adj.Count)].To;
            if (pick == w.From && adj.Count > 1) pick = adj[_rng.Next(adj.Count)].To;
            w.Prev = w.From; w.From = at; w.To = pick;
            return true;
        }

        public (Vec3 Pos, double Heading) Pose(Walker w)
        {
            var a = G.Nodes[w.From]; var b = G.Nodes[w.To];
            var d = b - a;
            double h = Math.Atan2(d.Y, d.X);
            var p = a + d * w.T;
            p = new Vec3(p.X - Math.Sin(h) * w.Side, p.Y + Math.Cos(h) * w.Side, p.Z);
            return (p, h);
        }
    }
}
