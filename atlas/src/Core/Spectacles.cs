// The shows: chariot race (track geometry round the spina, riders with surges and lane drift), arena games
// (gladiator pairs circling and lunging, beasts loping round with their hunters), theatre (chorus + actors).
// Same logic as blender/cinematic/events.py, so the Atlas and the film tell the same story.
using System;
using System.Collections.Generic;
using System.Linq;

namespace Atlas.Core
{
    public sealed class Track
    {
        public readonly Vec3 M0, M1, U, N;
        public readonly double D, Rc = 0.95, Z;
        public double Lap => 2 * D + 2 * Math.PI * Rc;

        public Track(Venue v)
        {
            M0 = Polyline.V(v.TurningPosts[0]); M1 = Polyline.V(v.TurningPosts[1]);
            Z = M0.Z;
            var d = M1 - M0;
            D = d.Length2D;
            U = new Vec3(d.X / D, d.Y / D, 0);
            N = new Vec3(-U.Y, U.X, 0);
        }

        /// <summary>Position at progress s (metres along the r=0.95 line; negative = before the first post) and radius r.</summary>
        public (Vec3 Pos, double Heading) Pos(double s, double r)
        {
            double turn = Math.PI * Rc;
            Vec3 p, dir;
            if (s < 0) { p = M0 + U * s - N * r; dir = U; }
            else
            {
                s %= Lap;
                if (s < D) { p = M0 + U * s - N * r; dir = U; }
                else if (s < D + turn) { double th = -Math.PI / 2 + (s - D) / Rc; p = M1 + (U * Math.Cos(th) + N * Math.Sin(th)) * r; dir = U * -Math.Sin(th) + N * Math.Cos(th); }
                else if (s < 2 * D + turn) { p = M1 - U * (s - D - turn) + N * r; dir = U * -1; }
                else { double th = Math.PI / 2 + (s - 2 * D - turn) / Rc; p = M0 + (U * Math.Cos(th) + N * Math.Sin(th)) * r; dir = U * -Math.Sin(th) + N * Math.Cos(th); }
            }
            return (new Vec3(p.X, p.Y, Z), Math.Atan2(dir.Y, dir.X));
        }

        public bool OnTurn(double s)
        {
            if (s < 0) return false;
            double lp = s % Lap;
            return (lp > D && lp < D + Math.PI * Rc) || lp > 2 * D + Math.PI * Rc;
        }
    }

    public sealed class Race
    {
        public sealed class Rider { public int Team; public double S, R, V, VMax, Phase, LaneTarget; public bool Done; public int Place; public Vec3 Pos; public double Heading; }
        public readonly Track Tr;
        public readonly List<Rider> Riders = new();
        public readonly int Laps;
        public double Time;
        public bool Finished => Riders.All(r => r.Done);
        public int Finishers => Riders.Count(r => r.Done);
        public const double StartDelay = 2.0;
        public static readonly string[] TeamNames = { "Red", "Blue", "Green", "White", "Gold", "Purple" };

        public Race(Venue v, int chariots, int laps, double speed, int seed = 3)
        {
            Tr = new Track(v);
            Laps = laps;
            var rng = new Random(seed);
            var gates = v.StartGates.Select(Polyline.V)
                         .Select(g => (g, side: (g.X - Tr.M0.X) * Tr.N.X + (g.Y - Tr.M0.Y) * Tr.N.Y))
                         .Where(x => x.side < 0).OrderByDescending(x => x.side).Take(chariots).ToList();
            for (int i = 0; i < gates.Count; i++)
            {
                var g = gates[i].g;
                double s0 = (g.X - Tr.M0.X) * Tr.U.X + (g.Y - Tr.M0.Y) * Tr.U.Y;
                Riders.Add(new Rider { Team = i, S = s0, R = -gates[i].side, VMax = speed * (0.95 + 0.1 * rng.NextDouble()),
                                       Phase = rng.NextDouble() * 6.28, LaneTarget = 0.45 + 0.2 * i });
            }
            foreach (var r in Riders) (r.Pos, r.Heading) = Tr.Pos(r.S, r.R);
        }

        public int LapOf(Rider r) => Math.Clamp((int)Math.Floor(Math.Max(0, r.S) / Tr.Lap) + 1, 1, Laps);
        public Rider Leader => Riders.Where(r => !r.Done).OrderByDescending(r => r.S).FirstOrDefault() ?? Riders.OrderBy(r => r.Place).First();

        public void Step(double dt)
        {
            Time += dt;
            double total = Laps * Tr.Lap;
            foreach (var r in Riders)
            {
                if (Time > StartDelay && !r.Done)
                {
                    double surge = 1.0 + 0.06 * Math.Sin(Time * 0.9 + r.Phase) + 0.03 * Math.Sin(Time * 2.3 + r.Phase * 2);
                    r.V = Math.Min(r.VMax * surge, r.V + 1.2 * dt);
                }
                else if (r.Done) r.V = Math.Max(0, r.V - 0.8 * dt);
                r.S += r.V * dt;
                if (!r.Done && r.S > total) { r.Done = true; r.Place = Finishers; }
                double target = r.LaneTarget * (Tr.OnTurn(r.S) ? 1.15 : 0.85);
                r.R += (Math.Clamp(target, 0.42, 1.5) - r.R) * Math.Min(1, 0.5 * dt * 24 * 0.04);
                (r.Pos, r.Heading) = Tr.Pos(r.S, r.R);
            }
        }
    }

    public sealed class Arena
    {
        public sealed class Fighter { public Vec3 Pos; public double Heading; public bool Visible = true; public int Team; public bool Beast, Hunter; }
        public readonly List<Fighter> F = new();
        readonly Vec3 _c, _ax, _ay; readonly double _a, _b, _z;
        readonly List<(Fighter A, Fighter B, Vec3 Home, double Ph, double W)> _pairs = new();
        readonly List<(Fighter Beast, Fighter Hunter, Vec3 Gate, double Ph, double Release)> _hunts = new();
        public double Time;

        public Arena(Venue v, int pairs, int beasts, double beastAt, int seed = 5)
        {
            var P = v.FloorPoly.Select(Polyline.V).ToList();
            _c = new Vec3(P.Average(p => p.X), P.Average(p => p.Y), v.FloorZ);
            double ang = v.HeadingDeg * Math.PI / 180;
            _ax = new Vec3(Math.Cos(ang), Math.Sin(ang), 0); _ay = new Vec3(-Math.Sin(ang), Math.Cos(ang), 0);
            _a = P.Max(p => Math.Abs((p.X - _c.X) * _ax.X + (p.Y - _c.Y) * _ax.Y)) * 0.78;
            _b = P.Max(p => Math.Abs((p.X - _c.X) * _ay.X + (p.Y - _c.Y) * _ay.Y)) * 0.78;
            _z = v.FloorZ;
            var rng = new Random(seed);
            for (int k = 0; k < pairs; k++)
            {
                double t = 2 * Math.PI * k / pairs + rng.NextDouble() * 0.4 - 0.2;
                var home = _c + _ax * (_a * 0.55 * Math.Cos(t)) + _ay * (_b * 0.55 * Math.Sin(t));
                var a = new Fighter { Team = 0 }; var b = new Fighter { Team = 1 };
                F.Add(a); F.Add(b);
                _pairs.Add((a, b, home, rng.NextDouble() * 6.28, 0.7 + 0.6 * rng.NextDouble()));
            }
            var gates = (v.BeastGates ?? Array.Empty<double[]>()).Select(Polyline.V).ToList();
            if (gates.Count == 0) gates.Add(_c);
            for (int k = 0; k < beasts; k++)
            {
                var beast = new Fighter { Beast = true, Visible = false };
                var hunter = new Fighter { Hunter = true, Team = 2, Visible = false };
                F.Add(beast); F.Add(hunter);
                _hunts.Add((beast, hunter, gates[k % gates.Count], rng.NextDouble() * 6.28, beastAt + k * 0.4));
            }
        }

        Vec3 Ring(double th, double k) => _c + _ax * (_a * k * Math.Cos(th)) + _ay * (_b * k * Math.Sin(th));

        public void Step(double dt)
        {
            Time += dt;
            double t = Time;
            foreach (var (a, b, home, ph, w) in _pairs)
            {
                var mid = home + new Vec3(Math.Sin(t * 0.21 * w + ph) * 0.35, Math.Cos(t * 0.17 * w + ph * 2) * 0.35, 0);
                double th = t * 0.9 * w + ph, gap = 0.075 + 0.04 * Math.Max(0, Math.Sin(t * 3.1 * w + ph));
                var off = new Vec3(Math.Cos(th) * gap, Math.Sin(th) * gap, 0);
                a.Pos = new Vec3(mid.X + off.X, mid.Y + off.Y, _z); b.Pos = new Vec3(mid.X - off.X, mid.Y - off.Y, _z);
                a.Heading = Math.Atan2(-off.Y, -off.X); b.Heading = Math.Atan2(off.Y, off.X);
            }
            foreach (var (beast, hunter, gate, ph, rel) in _hunts)
            {
                double tt = t - rel;
                beast.Visible = tt >= 0; hunter.Visible = tt >= 1.5;
                if (tt < 0) continue;
                double run = Math.Min(1, tt / 1.5), th = ph + tt * 0.55;
                var ring = Ring(th, 0.85);
                var p = gate * (1 - run) + ring * run;
                var p2 = Ring(th + 0.05, 0.85);
                beast.Pos = new Vec3(p.X, p.Y, _z);
                beast.Heading = run >= 1 ? Math.Atan2(p2.Y - p.Y, p2.X - p.X) : Math.Atan2(ring.Y - gate.Y, ring.X - gate.X);
                var hp = Ring(th - 0.35, 0.8);
                hunter.Pos = new Vec3(hp.X, hp.Y, _z); hunter.Heading = beast.Heading;
            }
        }
    }

    public sealed class Play
    {
        public readonly List<(Vec3 Pos, double Heading, int Role)> Cast = new();
        readonly Vec3 _c, _focus; readonly double _r, _z;
        public double Time;
        public Play(Venue v)
        {
            var st = v.Stage.Select(Polyline.V).ToList();
            _c = new Vec3(st.Average(p => p.X), st.Average(p => p.Y), v.StageZ);
            _r = st.Max(p => (p - _c).Length2D) * 0.75;
            _z = v.StageZ;
            _focus = Polyline.V(v.Center);
            for (int i = 0; i < 11; i++) Cast.Add((_c, 0, i < 8 ? 0 : i - 7));
        }
        public void Step(double dt)
        {
            Time += dt;
            double t = Time;
            for (int k = 0; k < 8; k++)
            {
                double th = t * 0.35 + 2 * Math.PI * k / 8;
                Cast[k] = (new Vec3(_c.X + Math.Cos(th) * _r * 0.8, _c.Y + Math.Sin(th) * _r * 0.8, _z), th + Math.PI / 2, 0);
            }
            for (int k = 0; k < 3; k++)
            {
                int beat = (int)(t / 3.0 + k) % 3;
                var m = new Vec3(_c.X + Math.Cos(beat * 2.1 + k) * _r * 0.35, _c.Y + Math.Sin(beat * 2.1 + k) * _r * 0.35, _z);
                Cast[8 + k] = (m, Math.Atan2(_focus.Y - m.Y, _focus.X - m.X) + Math.PI, k + 1);
            }
        }
    }
}
