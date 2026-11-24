// Runs data-driven events (atlas/events/*.json) on the city: streams of people, venue fill/cheers, the race,
// the games, the play, an arriving fleet, the festival procession and lanterns. Triggered from the UI, by
// --event=<id>, or by the clock (schedule_hour) while time is playing.
using System;
using System.Collections.Generic;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class EventRunner : Node3D, IEventHandler
    {
        public record EventInfo(string Id, string Label);
        public List<EventInfo> Available { get; } = new();
        public event Action<string> StatusChanged;
        public double TimeScale = 1.0;
        public EventTimeline Running { get; private set; }
        public string Status { get; private set; } = "";

        CityView _v;
        CityManifest _m;
        List<EventDef> _defs = new();
        Venue _venue;
        readonly Dictionary<string, (double From, double To, double Dur, double T, bool Seat)> _fills = new();
        readonly Dictionary<string, (double Amount, double Left, bool Seat)> _cheers = new();
        public Race Race { get; private set; }
        public Arena Arena { get; private set; }
        public Play Play { get; private set; }
        double _gamesDur, _playDur;
        Swarm _chariots, _fighters, _beasts, _cast, _torches, _flames, _lanterns;
        readonly List<OmniLight3D> _procLights = new();
        List<Ship> _fleet = new();
        Polyline _route;
        double _procHead, _procSpeed, _procRows;
        bool _procOn;
        double _lastHour = -1;
        Node3D _staticChariots;

        public void Setup(CityView v)
        {
            _v = v; _m = v.M;
            _defs = EventDef.LoadDir(ProjectSettings.GlobalizePath("res://events")).Where(d => d.AvailableIn(_m)).ToList();
            foreach (var d in _defs) Available.Add(new EventInfo(d.Id, d.Label));
            TimeScale = Args.F("event-speed", 1f);
            _staticChariots = v.City.ByName.TryGetValue("CAP_LM_Hippodrome_Chariots", out var sc) ? sc : null;
            var fig = v.City.Mats.Figure;
            _chariots = Make("Chariots", Props.Get("chariot"), fig, 8, true);
            _fighters = Make("Fighters", Props.Get("gladiator"), fig, 24, true);
            _beasts = Make("Beasts", Props.Get("beast"), fig, 8, true);
            _cast = Make("Cast", Props.Get("robed"), fig, 16, true);
            _torches = Make("Procession", Props.Get("torch_bearer"), fig, 120, true);
            var glow = (ShaderMaterial)v.City.Mats.Glow.Duplicate();
            glow.SetShaderParameter("lamp_level", 1.0f);
            glow.SetShaderParameter("window_level", 0.0f);
            _flames = Make("Flames", new QuadMesh { Size = Vector2.One }, glow, 120, false);
            _lanterns = Make("Lanterns", new QuadMesh { Size = Vector2.One }, glow, 200, false);
            for (int i = 0; i < 3; i++)
            {
                var l = new OmniLight3D { LightColor = new Color(1f, 0.6f, 0.25f), OmniRange = 3.5f, LightEnergy = 0, Visible = false };
                AddChild(l);
                _procLights.Add(l);
            }
            if (_m.Routes.TryGetValue("procession", out var r) && r.Length > 1) _route = new Polyline(Polyline.FromArray(r));
        }

        Swarm Make(string name, Mesh mesh, Material mat, int cap, bool shadows)
        {
            var s = new Swarm(name, mesh, mat, cap, shadows);
            AddChild(s.Node);
            return s;
        }

        public void Trigger(string id)
        {
            var d = _defs.FirstOrDefault(x => x.Id == id);
            if (d == null) { SetStatus($"'{id}' is not available in {_m.Name}"); return; }
            Stop();
            _venue = d.VenueType != null ? _m.VenueOfType(d.VenueType) : null;
            Running = new EventTimeline(d);
            GD.Print($"[Atlas] event start {id}");
            SetStatus(d.Label + "…");
        }

        public void Stop()
        {
            if (Running == null) return;
            Race = null; Arena = null; Play = null; _procOn = false;
            foreach (var s in new[] { _chariots, _fighters, _beasts, _cast, _torches, _flames, _lanterns }) { s.Begin(); s.End(); }
            foreach (var l in _procLights) l.Visible = false;
            if (_staticChariots != null) _staticChariots.Visible = true;
            foreach (var z in _v.Life.ZoneOverride.Keys.ToList()) _v.Life.ZoneOverride.Remove(z);
            Running = null;
        }

        void SetStatus(string s) { Status = s; StatusChanged?.Invoke(s); }

        public override void _Process(double delta)
        {
            double dt = delta * TimeScale;
            AutoSchedule();
            if (Running != null)
            {
                Running.Step(dt, this);
                if (Running.Done) { GD.Print($"[Atlas] event done {Running.Def.Id} after {Running.Elapsed:0}s"); SetStatus(""); Stop(); }
            }
            StepFills(dt);
            if (Race != null) StepRace(dt);
            if (Arena != null) StepArena(dt);
            if (Play != null) StepPlay(dt);
            if (_procOn) StepProcession(dt);
        }

        void AutoSchedule()
        {
            double h = _v.Tod.Hour;
            if (_lastHour >= 0 && _v.Tod.Speed > 0 && Running == null)
                foreach (var d in _defs.Where(d => d.ScheduleHour.HasValue))
                {
                    double s = d.ScheduleHour.Value;
                    bool crossed = _lastHour <= h ? (_lastHour < s && s <= h) : (_lastHour < s || s <= h);
                    if (crossed) { Trigger(d.Id); break; }
                }
            _lastHour = h;
        }

        // ------------------------------------------------------------------ IEventHandler
        public void Run(EventStep s)
        {
            var life = _v.Life;
            switch (s.Do)
            {
                case "status": SetStatus(s.Str("text", "")); break;
                case "focus": _v.Jump(s.Str("landmark", "overview")); break;
                case "stream_in":
                case "stream_out":
                    if (_venue != null)
                    {
                        var targets = _venue.Entrances.Select(e => life.Crowd.G.Nearest(e[0], e[1])).Distinct();
                        life.Crowd.AddStream(targets, (int)s.Num("count", 300), s.Num("window", 20), s.Do == "stream_out");
                    }
                    break;
                case "stream_to_quay":
                    var quay = _m.SpawnZones.FirstOrDefault(z => z.Id == "harbour_quay");
                    if (quay != null)
                        life.Crowd.AddStream(quay.Points.Where((_, i) => i % 12 == 0).Select(p => life.Crowd.G.Nearest(p[0], p[1])).Distinct(),
                                             (int)s.Num("count", 300), s.Num("window", 30));
                    break;
                case "fill":
                    if (_venue != null && life.Seats.TryGetValue(_venue.Id, out var pc))
                        _fills[_venue.Id] = (pc.Fill, s.Num("to", 1), Math.Max(0.1, s.Num("over", 10)), 0, true);
                    break;
                case "gather":
                    foreach (var z in s.List("zones"))
                        if (life.Zones.TryGetValue(z, out var zc))
                        {
                            double to = s.Num("to", 1);
                            _fills[z] = (zc.Fill, to < 0 ? Crowd.DensityAt(_v.Tod.Hour) * (_m.SpawnZones.First(x => x.Id == z).Density) : to,
                                         Math.Max(0.1, s.Num("over", 10)), 0, false);
                            if (to < 0) _fills[z] = _fills[z] with { To = -_fills[z].To - 1 };      // negative = release afterwards
                        }
                    break;
                case "cheer":
                    if (_venue != null) _cheers[_venue.Id] = (s.Num("amount", 1), s.Num("over", 6), true);
                    break;
                case "cheer_zones":
                    foreach (var z in s.List("zones")) _cheers[z] = (s.Num("amount", 1), s.Num("over", 6), false);
                    break;
                case "race":
                    if (_venue != null && _venue.TurningPosts != null)
                    {
                        Race = new Race(_venue, (int)s.Num("chariots", 6), (int)s.Num("laps", 5), s.Num("speed", 1.9));
                        if (_staticChariots != null) _staticChariots.Visible = false;
                        if (life.Seats.TryGetValue(_venue.Id, out var rs)) rs.SetExcitement(0.35);
                    }
                    break;
                case "games":
                    if (_venue != null) { Arena = new Arena(_venue, (int)s.Num("pairs", 5), (int)s.Num("beasts", 3), s.Num("beast_at", 30)); _gamesDur = s.Num("duration", 60); }
                    break;
                case "play":
                    if (_venue != null && _venue.Stage != null) { Play = new Play(_venue); _playDur = s.Num("duration", 60); }
                    break;
                case "fleet": StartFleet((int)s.Num("ships", 5), s.Str("lane", "harbour_in"), s.Num("speed", 1.3)); break;
                case "night":
                    if (_v.Tod.Elevation > -6) { _v.Tod.Hour = s.Num("hour", 21); _v.Tod.Apply(); }
                    break;
                case "lanterns": SetLanterns(s.Args.TryGetValue("on", out var on) && on.GetBoolean()); break;
                case "procession":
                    if (_route != null) { _procOn = true; _procRows = s.Num("rows", 24); _procSpeed = s.Num("speed", 0.35); _procHead = 0; }
                    break;
                case "end": break;
                default: GD.PushWarning($"[Atlas] unknown event step '{s.Do}'"); break;
            }
        }

        public bool Check(string c) => c switch
        {
            "race_finished" => Race == null || Race.Finished,
            "games_over" => Arena == null || Arena.Time >= _gamesDur,
            "play_over" => Play == null || Play.Time >= _playDur,
            "fleet_moored" => _fleet.Count == 0 || _fleet.All(f => f.Done || f.Script == null || (Time() - f.Born) > _fleetDone),
            "procession_done" => !_procOn || _route == null || _procHead - _procRows * 0.17 >= _route.Length,
            _ => true,
        };

        double Time() => _v.Life.Traffic.Time;
        double _fleetDone;

        // ------------------------------------------------------------------ fills and cheers
        void StepFills(double dt)
        {
            var life = _v.Life;
            foreach (var k in _fills.Keys.ToList())
            {
                var f = _fills[k];
                f.T += dt;
                bool release = f.To < 0 && !f.Seat;
                double to = release ? -f.To - 1 : f.To;
                double u = Math.Clamp(f.T / f.Dur, 0, 1);
                double val = f.From + (to - f.From) * (u * u * (3 - 2 * u));
                if (f.Seat && life.Seats.TryGetValue(k, out var pc)) pc.SetFill(val);
                else if (!f.Seat) life.ZoneOverride[k] = val;
                if (u >= 1) { _fills.Remove(k); if (release) life.ZoneOverride.Remove(k); }
                else _fills[k] = f;
            }
            foreach (var k in _cheers.Keys.ToList())
            {
                var c = _cheers[k];
                c.Left -= dt;
                var pc = c.Seat ? life.Seats.GetValueOrDefault(k) : life.Zones.GetValueOrDefault(k);
                pc?.SetExcitement(c.Left > 0 ? c.Amount : (c.Seat ? 0.1 : 0.0));
                if (c.Left <= 0) _cheers.Remove(k); else _cheers[k] = c;
            }
        }

        // ------------------------------------------------------------------ the shows
        void StepRace(double dt)
        {
            Race.Step(dt);
            _chariots.Begin();
            foreach (var r in Race.Riders)
                _chariots.Add(Geo.V(r.Pos), (float)r.Heading, 1f, new Color(Props.Teams[r.Team % 6].R, Props.Teams[r.Team % 6].G, Props.Teams[r.Team % 6].B, 0));
            _chariots.End();
            var lead = Race.Leader;
            if (Race.Time < Race.StartDelay) SetStatus("They're under starter's orders…");
            else if (!Race.Finished && Race.Finishers == 0) SetStatus($"Lap {Race.LapOf(lead)}/{Race.Laps} · {Race.TeamNames[lead.Team]} leads");
            else
            {
                var win = Race.Riders.OrderBy(r => r.Place).First(r => r.Done);
                SetStatus($"{Race.TeamNames[win.Team]} wins!");
            }
            if (Race.Finished && Race.Riders.All(r => r.V < 0.05)) { Race = null; _chariots.Begin(); _chariots.End(); if (_staticChariots != null) _staticChariots.Visible = true; }
        }

        void StepArena(double dt)
        {
            Arena.Step(dt);
            _fighters.Begin(); _beasts.Begin();
            foreach (var f in Arena.F.Where(f => f.Visible))
            {
                var col = f.Beast ? new Color(0.7f, 0.52f, 0.28f, 0) : f.Hunter ? new Color(0.85f, 0.66f, 0.28f, 0) : Props.Teams[f.Team];
                (f.Beast ? _beasts : _fighters).Add(Geo.V(f.Pos), (float)f.Heading, 1f, new Color(col.R, col.G, col.B, f.Beast ? 0 : 1));
            }
            _fighters.End(); _beasts.End();
            if (Arena.Time >= _gamesDur + 4) { Arena = null; _fighters.Begin(); _fighters.End(); _beasts.Begin(); _beasts.End(); }
        }

        void StepPlay(double dt)
        {
            Play.Step(dt);
            _cast.Begin();
            foreach (var (p, h, role) in Play.Cast)
            {
                var c = role == 0 ? new Color(0.9f, 0.88f, 0.84f) : Props.Teams[(role - 1) % 6];
                _cast.Add(Geo.V(p), (float)h, 1f, new Color(c.R, c.G, c.B, role == 0 ? 1 : 0));
            }
            _cast.End();
            if (Play.Time >= _playDur + 2) { Play = null; _cast.Begin(); _cast.End(); }
        }

        void StartFleet(int n, string laneId, double speed)
        {
            var traffic = _v.Life.Traffic;
            if (!traffic.Lanes.TryGetValue(laneId, out var lane)) return;
            var berths = _m.Berths.Select(Polyline.V).ToList();
            if (berths.Count == 0) berths.Add(lane.At(lane.Path.Length).Pos);
            string[] kinds = { "galley", "galley", "merchant2", "merchant", "merchant2", "galley" };
            double spacing = 3.4, offAt = lane.Path.Length * 0.72;
            foreach (var old in _fleet) old.Done = true;          // the previous fleet sails off-stage
            _fleet.Clear();
            _fleetDone = 0;
            for (int k = 0; k < n; k++)
            {
                var tgt = berths[k % berths.Count];
                double lag = spacing * k / speed;
                var (pOff, hOff) = lane.At(offAt);
                double glide = (tgt - pOff).Length2D * 1.6 / speed;
                _fleetDone = Math.Max(_fleetDone, lag + offAt / speed + glide + 1);
                var ship = traffic.AddScripted(kinds[k % kinds.Length], 1.3, t =>
                {
                    double s = (t - lag) * speed;
                    if (s < 0) return (lane.At(0).Pos, lane.At(0).Heading, false, false);
                    if (s < offAt) { var (p, h) = lane.At(s); return (p, h, true, false); }
                    double u = Math.Min(1, (s - offAt) / Math.Max(1e-6, (tgt - pOff).Length2D * 1.6));
                    double e = 1 - (1 - u) * (1 - u);
                    var q = pOff * (1 - e) + tgt * e;
                    double hh = u < 0.97 ? Math.Atan2(tgt.Y - pOff.Y, tgt.X - pOff.X) : Math.Atan2(tgt.Y - pOff.Y, tgt.X - pOff.X);
                    return (new Vec3(q.X, q.Y, 0), hh, true, false);
                });
                _fleet.Add(ship);
            }
        }

        void SetLanterns(bool on)
        {
            _lanterns.Begin();
            var forum = _m.SpawnZones.FirstOrDefault(z => z.Id == "forum");
            if (on && forum != null)
            {
                double x0 = forum.Poly.Min(p => p[0]) + 0.4, x1 = forum.Poly.Max(p => p[0]) - 0.4;
                double y0 = forum.Poly.Min(p => p[1]) + 0.5, y1 = forum.Poly.Max(p => p[1]) - 0.5;
                double zb = forum.Points.Average(p => p[2]) + 0.75;
                for (int r = 0; r < 7; r++)
                    for (int k = 0; k < 14; k++)
                    {
                        double u = k / 13.0, y = y0 + (y1 - y0) * r / 6.0;
                        var p = Geo.V(new[] { x0 + (x1 - x0) * u, y, zb - 0.25 * Math.Sin(Math.PI * u) });
                        _lanterns.Add(p, 0, 0.28f, new Color(1, 0, 1, 0));      // kind 1 = lamp, strength 1
                    }
            }
            _lanterns.End();
        }

        void StepProcession(double dt)
        {
            _procHead += _procSpeed * dt;
            _torches.Begin(); _flames.Begin();
            int rows = (int)_procRows;
            for (int r = 0; r < rows; r++)
                for (int lane = -1; lane <= 1; lane++)
                {
                    double s = Math.Clamp(_procHead - r * 0.17, 0, _route.Length - 0.01);
                    if (_procHead - r * 0.17 < 0) continue;
                    var (p, h) = _route.At(s);
                    var q = new Vec3(p.X - Math.Sin(h) * lane * 0.075, p.Y + Math.Cos(h) * lane * 0.075, p.Z);
                    var pal = Props.Palette[(r * 3 + lane + 1) % Props.Palette.Length];
                    var gp = Geo.V(q);
                    _torches.Add(gp, (float)h, 1f, new Color(pal.R, pal.G, pal.B, 1));
                    var flame = gp + new Basis(Vector3.Up, (float)h) * new Vector3(0.012f, 0.135f, -0.018f);
                    _flames.Add(flame, 0, 0.12f, new Color(2, 0, 1, 0));
                }
            _torches.End(); _flames.End();
            for (int i = 0; i < _procLights.Count; i++)
            {
                double s = Math.Clamp(_procHead - i * rows * 0.17 / _procLights.Count, 0, _route.Length);
                var (p, _) = _route.At(s);
                _procLights[i].Position = Geo.V(p) + Vector3.Up * 0.4f;
                _procLights[i].LightEnergy = 1.2f;
                _procLights[i].Visible = _procHead - i * rows * 0.17 / _procLights.Count > 0;
            }
            if (_procHead - rows * 0.17 >= _route.Length + 25) { _procOn = false; _torches.Begin(); _torches.End(); _flames.Begin(); _flames.End(); foreach (var l in _procLights) l.Visible = false; }
        }
    }
}
