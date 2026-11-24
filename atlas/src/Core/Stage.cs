// A small stage for scripted scenes (the villa's chapter events): named actors (people and horses) who walk the
// street graph or a given path, lead one another (a groom and the horses behind him), mount and dismount, turn,
// bow (tilt) and go under water (sink). Pure logic in the manifest frame (model metres); speeds are given in real
// metres per second and scaled by the package's model_scale. EventRunner draws it and drives it from event steps.
using System;
using System.Collections.Generic;
using System.Linq;

namespace Atlas.Core
{
    public sealed class Actor
    {
        public string Id, Kind, FootKind;
        public double R, G, B;
        public Vec3 Pos;
        public double Heading, Tilt, Sink;
        public bool Visible = true;
        public string Mount;                 // a horse this actor rides
        internal Polyline Path;
        internal double S, Speed;
        internal string Leader;
        internal double Gap, TrailS, TrailSpeed;
        internal List<Vec3> Trail;           // the leader's footsteps (followers only)
        internal List<double> TrailLen;
        internal (double From, double To, double T, double Dur) TiltTw, SinkTw;
        public bool Walking => Path != null;
        public bool Busy => Path != null || TiltTw.T < TiltTw.Dur || SinkTw.T < SinkTw.Dur;
    }

    public sealed class Stage
    {
        public readonly StreetGraph G;
        /// <summary>Model metres per real metre (1 / model_scale).</summary>
        public readonly double Scale;
        public readonly Dictionary<string, Actor> Actors = new();
        public double Time { get; private set; }

        public Stage(StreetGraph g, double modelScale) { G = g; Scale = 1.0 / Math.Max(0.1, modelScale); }

        public Actor this[string id] => Actors.TryGetValue(id, out var a) ? a : null;

        public Actor Cast(string id, string kind, (double R, double G, double B) col, Vec3 pos, double heading)
        {
            var a = new Actor { Id = id, Kind = kind, FootKind = kind, R = col.R, G = col.G, B = col.B, Pos = pos, Heading = heading };
            Actors[id] = a;
            return a;
        }

        public void Clear() => Actors.Clear();

        // ---------------------------------------------------------------- movement

        /// <summary>Walk to a point along the street graph (the nearest nodes at both ends), then straight to it.</summary>
        public void WalkTo(string id, Vec3 target, double speedMps)
        {
            var a = this[id];
            if (a == null) return;
            var pts = new List<Vec3> { a.Pos };
            int s = G.Nearest(a.Pos.X, a.Pos.Y), t = G.Nearest(target.X, target.Y);
            double direct = (target - a.Pos).Length2D;
            if (s != t && direct > 2.5 * Math.Max((G.Nodes[s] - a.Pos).Length2D, (G.Nodes[t] - target).Length2D))
            {
                var nodes = ShortestPath(s, t);
                // don't walk back to a node that lies behind us, nor past the target to the last one
                if (nodes.Count > 1 && (G.Nodes[nodes[1]] - a.Pos).Length2D < (G.Nodes[nodes[1]] - G.Nodes[nodes[0]]).Length2D) nodes.RemoveAt(0);
                if (nodes.Count > 1 && (G.Nodes[nodes[^2]] - target).Length2D < (G.Nodes[nodes[^2]] - G.Nodes[nodes[^1]]).Length2D) nodes.RemoveAt(nodes.Count - 1);
                pts.AddRange(nodes.Select(n => G.Nodes[n]));
            }
            pts.Add(target);
            Go(a, pts, speedMps);
        }

        /// <summary>Walk a given path (straight segments), starting from where the actor stands.</summary>
        public void WalkPath(string id, IEnumerable<Vec3> path, double speedMps, bool fromHere = true)
        {
            var a = this[id];
            if (a == null) return;
            var pts = new List<Vec3>();
            if (fromHere) pts.Add(a.Pos);
            pts.AddRange(path);
            Go(a, pts, speedMps);
        }

        /// <summary>Walk straight towards another actor (or point), stopping `gapM` real metres short.</summary>
        public void Approach(string id, Vec3 target, double gapM, double speedMps)
        {
            var a = this[id];
            if (a == null) return;
            var d = target - a.Pos;
            double L = d.Length2D, stop = Math.Max(0, L - gapM * Scale);
            if (L < 1e-6) return;
            var end = a.Pos + new Vec3(d.X / L * stop, d.Y / L * stop, (target.Z - a.Pos.Z) * (stop / L));
            Go(a, new List<Vec3> { a.Pos, end }, speedMps);
        }

        void Go(Actor a, List<Vec3> pts, double speedMps)
        {
            var clean = new List<Vec3> { pts[0] };
            foreach (var p in pts.Skip(1)) if ((p - clean[^1]).Length2D > 1e-4) clean.Add(p);
            if (clean.Count < 2) { a.Path = null; return; }
            a.Path = new Polyline(clean);
            a.S = 0;
            a.Speed = speedMps * Scale;
            a.Leader = null;
        }

        /// <summary>`id` follows `leaderId`'s footsteps, `gapM` real metres behind (a led horse, a companion).</summary>
        public void Lead(string id, string leaderId, double gapM)
        {
            var a = this[id]; var l = this[leaderId];
            if (a == null || l == null || a == l) return;
            a.Path = null;
            a.Leader = leaderId;
            a.Gap = gapM * Scale;
            a.Trail = new List<Vec3> { a.Pos, l.Pos };
            a.TrailLen = new List<double> { 0, (l.Pos - a.Pos).Length2D };
            a.TrailS = 0;
        }

        public void Release(string id) { var a = this[id]; if (a != null) { a.Leader = null; a.Trail = null; } }

        public void Mount(string riderId, string horseId)
        {
            var r = this[riderId]; var h = this[horseId];
            if (r == null || h == null) return;
            r.Mount = horseId; r.Kind = "rider"; r.Path = null; r.Leader = null;
            r.Pos = h.Pos; r.Heading = h.Heading;
        }

        /// <summary>Step down on the horse's left (side 1) or right (-1).</summary>
        public void Dismount(string riderId, int side = 1)
        {
            var r = this[riderId];
            if (r?.Mount == null) return;
            var h = this[r.Mount];
            r.Mount = null; r.Kind = r.FootKind == "rider" ? "citizen" : r.FootKind;
            double c = Math.Cos(h.Heading), s = Math.Sin(h.Heading), off = 0.95 * Scale * side;
            r.Pos = h.Pos + new Vec3(-s * off, c * off, 0);
            r.Heading = h.Heading;
        }

        public void Face(string id, Vec3 p)
        {
            var a = this[id];
            if (a == null) return;
            var d = p - a.Pos;
            if (d.Length2D > 1e-6) a.Heading = Math.Atan2(d.Y, d.X);
        }

        /// <summary>Lean forward by `deg` (a bow, an embrace) over `over` seconds; 0 stands up again.</summary>
        public void Tilt(string id, double deg, double over)
        {
            var a = this[id];
            if (a != null) a.TiltTw = (a.Tilt, deg * Math.PI / 180, 0, Math.Max(1e-3, over));
        }

        /// <summary>Go `depthM` real metres down (into a pool) over `over` seconds; 0 comes back up.</summary>
        public void Sink(string id, double depthM, double over)
        {
            var a = this[id];
            if (a != null) a.SinkTw = (a.Sink, depthM * Scale, 0, Math.Max(1e-3, over));
        }

        public bool Idle(string id) => this[id] is not { } a || (!a.Busy && (a.Leader == null || !FollowerMoving(a)));
        public bool AllIdle => Actors.Keys.All(Idle);

        bool FollowerMoving(Actor a) => a.Trail != null && a.TrailS + 1e-4 < a.TrailLen[^1] - a.Gap;

        // ---------------------------------------------------------------- simulation

        public void Step(double dt)
        {
            Time += dt;
            foreach (var a in Actors.Values.Where(a => a.Leader == null && a.Mount == null)) Move(a, dt);
            // followers in chain order (a horse may follow a horse that follows a groom)
            var done = new HashSet<string>(Actors.Values.Where(a => a.Leader == null).Select(a => a.Id));
            for (int pass = 0; pass < 8; pass++)
                foreach (var a in Actors.Values.Where(a => a.Leader != null && !done.Contains(a.Id) && done.Contains(a.Leader)).ToList())
                {
                    Follow(a, this[a.Leader], dt);
                    done.Add(a.Id);
                }
            foreach (var a in Actors.Values.Where(a => a.Mount != null))
                if (this[a.Mount] is { } h) { a.Pos = h.Pos; a.Heading = h.Heading; a.Sink = h.Sink; }
            foreach (var a in Actors.Values)
            {
                Tween(ref a.TiltTw, ref a.Tilt, dt);
                Tween(ref a.SinkTw, ref a.Sink, dt);
            }
        }

        static void Tween(ref (double From, double To, double T, double Dur) tw, ref double v, double dt)
        {
            if (tw.Dur <= 0 || tw.T >= tw.Dur) return;
            tw.T = Math.Min(tw.Dur, tw.T + dt);
            double u = tw.T / tw.Dur;
            v = tw.From + (tw.To - tw.From) * (u * u * (3 - 2 * u));
        }

        static void Move(Actor a, double dt)
        {
            if (a.Path == null) return;
            a.S += a.Speed * dt;
            var (p, h) = a.Path.At(a.S);
            a.Pos = p;
            a.Heading = h;
            if (a.S >= a.Path.Length) a.Path = null;
        }

        static void Follow(Actor a, Actor l, double dt)
        {
            if (l == null || a.Trail == null) return;
            if ((l.Pos - a.Trail[^1]).Length2D > 0.005)
            {
                a.TrailLen.Add(a.TrailLen[^1] + (l.Pos - a.Trail[^1]).Length2D);
                a.Trail.Add(l.Pos);
            }
            double want = a.TrailLen[^1] - a.Gap;
            if (want <= a.TrailS) return;
            double v = Math.Max(l.Speed, a.TrailSpeed) * 1.6 + 1e-3;
            if (l.Speed > 0) a.TrailSpeed = l.Speed;
            a.TrailS = Math.Min(want, a.TrailS + v * dt);
            int i = a.TrailLen.BinarySearch(a.TrailS);
            if (i < 0) i = Math.Max(1, ~i);
            i = Math.Clamp(i, 1, a.Trail.Count - 1);
            double seg = Math.Max(1e-9, a.TrailLen[i] - a.TrailLen[i - 1]), t = Math.Clamp((a.TrailS - a.TrailLen[i - 1]) / seg, 0, 1);
            var p0 = a.Trail[i - 1]; var p1 = a.Trail[i];
            a.Pos = p0 + (p1 - p0) * t;
            a.Heading = Math.Atan2(p1.Y - p0.Y, p1.X - p0.X);
        }

        /// <summary>Straight-line distance between two points (model metres, in plan).</summary>
        public double Path(Vec3 a, Vec3 b) => (b - a).Length2D;

        /// <summary>Dijkstra over the street graph (node ids, from s to t inclusive).</summary>
        public List<int> ShortestPath(int s, int t)
        {
            int n = G.Nodes.Length;
            var dist = new double[n];
            var prev = new int[n];
            Array.Fill(dist, double.MaxValue);
            Array.Fill(prev, -1);
            dist[s] = 0;
            var pq = new PriorityQueue<int, double>();
            pq.Enqueue(s, 0);
            while (pq.TryDequeue(out int u, out double d))
            {
                if (u == t) break;
                if (d > dist[u]) continue;
                foreach (var (v, len) in G.Adj[u])
                    if (d + len < dist[v]) { dist[v] = d + len; prev[v] = u; pq.Enqueue(v, dist[v]); }
            }
            var path = new List<int>();
            if (prev[t] < 0 && s != t) return new List<int> { s, t };
            for (int u = t; u >= 0; u = u == s ? -1 : prev[u]) path.Add(u);
            path.Reverse();
            return path;
        }
    }
}
