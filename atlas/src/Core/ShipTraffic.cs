// Ships on the manifest's lanes: arrive -> dwell -> leave via `then`, fishing loops, plus scripted fleets.
using System;
using System.Collections.Generic;
using System.Linq;

namespace Atlas.Core
{
    public sealed class Lane
    {
        public readonly ShipLane Def;
        public readonly Polyline Path;
        public Lane(ShipLane d)
        {
            Def = d;
            Path = new Polyline(Polyline.Chaikin(Polyline.FromArray(d.Points), d.Loop, 2), d.Loop);
        }
        public (Vec3 Pos, double Heading) At(double s)
        {
            var (p, h) = Path.At(s);
            var (p2, _) = Path.At(Path.Closed ? s + 0.9 : Math.Min(Path.Length, s + 0.9));
            if ((p2 - p).Length2D > 1e-6) h = Math.Atan2(p2.Y - p.Y, p2.X - p.X);
            return (p, h);
        }
    }

    public sealed class Ship
    {
        public int Id;
        public string Kind;
        public Lane Lane;
        public double Born, Speed, Scale;
        public Vec3 Pos;
        public double Heading;
        public bool Visible, Done;
        public Func<double, (Vec3, double, bool, bool)> Script;   // custom motion (fleets): t -> pos, heading, visible, done
    }

    public sealed class ShipTraffic
    {
        public readonly Dictionary<string, Lane> Lanes;
        public readonly List<Ship> Ships = new();
        readonly Random _rng;
        readonly Dictionary<string, double> _nextSpawn = new();
        public double Time;
        public double Density = 1.0;
        int _ids;

        public ShipTraffic(CityManifest m, int seed = 7, bool prewarm = true)
        {
            _rng = new Random(seed);
            Lanes = m.ShipLanes.ToDictionary(l => l.Id, l => new Lane(l));
            var continued = m.ShipLanes.Where(l => l.Then != null).Select(l => l.Then).ToHashSet();
            foreach (var l in Lanes.Values)
            {
                if (l.Def.Loop)
                {
                    for (int k = 0; k < 2; k++)
                        Ships.Add(new Ship { Id = _ids++, Kind = l.Def.Kinds.FirstOrDefault() ?? "fisher", Lane = l, Born = -l.Path.Length * k / 2 / Math.Max(0.05, l.Def.Speed),
                                             Speed = l.Def.Speed, Scale = 1.2 });
                }
                else if (l.Def.EveryS > 0 && !continued.Contains(l.Def.Id))
                {
                    // prewarm: ships already under way when the city opens
                    double total = Total(l);
                    if (prewarm) for (double t0 = -total + _rng.NextDouble() * l.Def.EveryS; t0 < 0; t0 += l.Def.EveryS * (0.75 + 0.5 * _rng.NextDouble())) Spawn(l, t0);
                    _nextSpawn[l.Def.Id] = _rng.NextDouble() * l.Def.EveryS;
                }
            }
        }

        double Total(Lane l)
        {
            double t = l.Path.Length / l.Def.Speed + l.Def.DwellS;
            if (l.Def.Then != null && Lanes.TryGetValue(l.Def.Then, out var n)) t += n.Path.Length / l.Def.Speed;
            return t;
        }

        Ship Spawn(Lane l, double born)
        {
            var kinds = l.Def.Kinds is { Count: > 0 } ? l.Def.Kinds : new List<string> { "merchant" };
            var s = new Ship { Id = _ids++, Kind = kinds[_rng.Next(kinds.Count)], Lane = l, Born = born,
                               Speed = l.Def.Speed * (0.9 + 0.2 * _rng.NextDouble()), Scale = 1.35 * (0.85 + 0.15 * _rng.NextDouble()) };
            Ships.Add(s);
            return s;
        }

        public Ship AddScripted(string kind, double scale, Func<double, (Vec3, double, bool, bool)> script)
        {
            var s = new Ship { Id = _ids++, Kind = kind, Scale = scale, Born = Time, Script = script };
            Ships.Add(s);
            return s;
        }

        public void Step(double dt)
        {
            Time += dt;
            foreach (var (id, l) in Lanes)
            {
                if (!_nextSpawn.ContainsKey(id)) continue;
                if (Time >= _nextSpawn[id])
                {
                    Spawn(l, Time);
                    _nextSpawn[id] = Time + l.Def.EveryS / Math.Max(0.05, Density) * (0.75 + 0.5 * _rng.NextDouble());
                }
            }
            foreach (var s in Ships) Update(s);
            Ships.RemoveAll(s => s.Done);
        }

        void Update(Ship s)
        {
            double t = Time - s.Born;
            if (s.Script != null)
            {
                var (p, h, vis, done) = s.Script(t);
                s.Pos = p; s.Heading = h; s.Visible = vis; s.Done = done;
                return;
            }
            var l = s.Lane;
            double dist = t * s.Speed;
            if (l.Def.Loop) { (s.Pos, s.Heading) = l.At(dist); s.Visible = t >= 0; return; }
            if (dist < 0) { s.Visible = false; return; }
            s.Visible = true;
            if (dist <= l.Path.Length) { (s.Pos, s.Heading) = l.At(dist); return; }
            if (l.Def.Then == null || !Lanes.TryGetValue(l.Def.Then, out var next)) { s.Done = true; return; }
            double tArr = l.Path.Length / s.Speed;
            if (t < tArr + l.Def.DwellS) { (s.Pos, s.Heading) = l.At(l.Path.Length - 1e-3); return; }
            double d2 = (t - tArr - l.Def.DwellS) * s.Speed;
            if (d2 > next.Path.Length) { s.Done = true; return; }
            (s.Pos, s.Heading) = next.At(d2);
        }
    }
}
