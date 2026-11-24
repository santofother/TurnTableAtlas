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
        // scripted scenes (the villa's chapter events): actors on a stage, a camera that can follow one, the cutaway
        public Stage Stage { get; private set; }
        readonly Dictionary<string, Swarm> _actorSwarms = new();
        string _follow;
        Dictionary<string, bool> _cutawaySaved;
        Swarm _flare;
        OmniLight3D _flareLight;
        double _flareLeft;
        Vector3 _flareAt;

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
            Stage = new Stage(v.Life.Crowd.G, _m.ModelScale > 0 ? _m.ModelScale : 15);
            foreach (var k in new[] { "citizen", "robed", "seated", "horse", "rider" })
                if (Props.Get(k) is { } mesh) _actorSwarms[k] = Make("Actors_" + k, mesh, fig, 24, true);
            _flare = Make("Flare", new QuadMesh { Size = Vector2.One }, glow, 4, false);
            _flareLight = new OmniLight3D { LightColor = new Color(1f, 0.55f, 0.2f), OmniRange = 4f, LightEnergy = 0, Visible = false };
            AddChild(_flareLight);
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
            Stage?.Clear();
            foreach (var sw in _actorSwarms.Values) { sw.Begin(); sw.End(); }
            _follow = null;
            _flareLeft = 0; _flare?.Begin(); _flare?.End();
            if (_flareLight != null) _flareLight.Visible = false;
            if (_cutawaySaved != null)
            {
                var layers = _v.Life.Layers().ToDictionary(l => l.Item1);
                foreach (var (k, on) in _cutawaySaved) if (layers.TryGetValue(k, out var l)) l.Item3(on);
                _cutawaySaved = null;
            }
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
            if (Stage != null && Stage.Actors.Count > 0) StepStage(dt);
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
                case "clock":
                    _v.Tod.Hour = s.Num("hour", _v.Tod.Hour);
                    if (s.Args.ContainsKey("speed")) _v.Tod.Speed = s.Num("speed", 0);
                    _v.Tod.Apply();
                    break;
                case "cutaway":
                {
                    var layers = _v.Life.Layers().ToDictionary(l => l.Item1);
                    foreach (var (key, name) in new[] { ("roofs", "Roofs"), ("upper", "Upper floor") })
                        if (s.Args.TryGetValue(key, out var onv) && layers.TryGetValue(name, out var l))
                        {
                            _cutawaySaved ??= new();
                            if (!_cutawaySaved.ContainsKey(name)) _cutawaySaved[name] = l.Item2();
                            l.Item3(onv.GetBoolean());
                        }
                    break;
                }
                case "camera":
                    _follow = null;
                    if (Place(s, "target") is { } ct)
                        _v.Rig.FlyTo(new CameraPreset { Target = new[] { ct.X, ct.Y, ct.Z }, Dist = s.Num("dist_m", 30) * Stage.Scale, Yaw = s.Num("yaw", -90), Pitch = s.Num("pitch", 30) }, s.Num("over", 2));
                    break;
                case "follow":
                    _follow = s.Str("actor");
                    if (_follow != null && Stage[_follow] is { } fa)
                        _v.Rig.FlyTo(new CameraPreset { Target = new[] { fa.Pos.X, fa.Pos.Y, fa.Pos.Z }, Dist = s.Num("dist_m", 30) * Stage.Scale, Yaw = s.Num("yaw", -90), Pitch = s.Num("pitch", 30) }, s.Num("over", 2));
                    break;
                case "cast":
                    if (s.Args.TryGetValue("actors", out var arr))
                        foreach (var e in arr.EnumerateArray()) CastOne(e);
                    break;
                case "walk":
                    foreach (var id in Ids(s))
                    {
                        double sp = s.Num("speed", 1.3);
                        if (s.Str("route") is { } rid && _m.Routes.TryGetValue(rid, out var rp))
                        {
                            var pl = new Polyline(Polyline.FromArray(rp));
                            double from = Math.Max(0, pl.Length - s.Num("from_end_m", 1e9) * Stage.Scale), to = pl.Length - s.Num("to_end_m", 0) * Stage.Scale;
                            var pts = new List<Vec3>();
                            for (double a = from; a < to; a += 0.25) pts.Add(pl.At(a).Pos);
                            pts.Add(pl.At(to).Pos);
                            if (Place(s, "then") is { } th) pts.Add(th);
                            Stage.WalkPath(id, pts, sp);
                        }
                        else if (s.Args.TryGetValue("via", out var via))
                            Stage.WalkPath(id, via.EnumerateArray().Select(PlaceOf).Where(p => p.HasValue).Select(p => p.Value), sp);
                        else if (Place(s, "to") is { } tp)
                            Stage.WalkTo(id, tp, sp);
                    }
                    break;
                case "approach":
                    foreach (var id in Ids(s))
                        if (Place(s, "to") is { } ap) Stage.Approach(id, ap, s.Num("gap", 0.6), s.Num("speed", 1.2));
                    break;
                case "lead":
                    foreach (var id in Ids(s)) Stage.Lead(id, s.Str("leader"), s.Num("gap", 2.6));
                    break;
                case "release": foreach (var id in Ids(s)) Stage.Release(id); break;
                case "mount": foreach (var id in Ids(s)) Stage.Mount(id, s.Str("horse")); break;
                case "dismount": foreach (var id in Ids(s)) Stage.Dismount(id, (int)s.Num("side", 1)); break;
                case "face":
                    foreach (var id in Ids(s)) if (Place(s, "to") is { } fp) Stage.Face(id, fp);
                    break;
                case "tilt": foreach (var id in Ids(s)) Stage.Tilt(id, s.Num("deg", 15), s.Num("over", 1)); break;
                case "sink": foreach (var id in Ids(s)) Stage.Sink(id, s.Num("depth", 1), s.Num("over", 1.5)); break;
                case "kind":
                    foreach (var id in Ids(s))
                        if (Stage[id] is { } ka)
                        {
                            if (s.Str("kind") is { } kk) { ka.Kind = kk; ka.FootKind = kk; }
                            if (s.Args.TryGetValue("color", out var kc)) { var c = kc.EnumerateArray().Select(x => x.GetDouble()).ToArray(); (ka.R, ka.G, ka.B) = (c[0], c[1], c[2]); }
                        }
                    break;
                case "exit": foreach (var id in Ids(s)) Stage.Actors.Remove(id); break;
                case "flare":
                    if (Place(s, "target") is { } fl) { _flareAt = Geo.V(fl) + Vector3.Up * 0.12f; _flareLeft = s.Num("for", 4); }
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
            "all_idle" => Stage.AllIdle,
            _ when c.StartsWith("idle:") => c[5..].Split(',').All(id => Stage.Idle(id.Trim())),
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

        // ------------------------------------------------------------------ scripted scenes (Stage)
        static IEnumerable<string> Ids(EventStep s)
        {
            if (s.Str("actor") is { } one) return new[] { one };
            return s.List("actors");
        }

        Vec3? Place(EventStep s, string key) => s.Args.TryGetValue(key, out var e) ? PlaceOf(e) : null;

        /// <summary>A place in a step: {"anchor"|"actor"|"landmark": id, "off": [x, y] real metres} or {"route": id, "from_end_m": m}.</summary>
        Vec3? PlaceOf(System.Text.Json.JsonElement e)
        {
            if (e.ValueKind != System.Text.Json.JsonValueKind.Object) return null;
            Vec3? p = null;
            if (e.TryGetProperty("anchor", out var an) && _m.Anchors.TryGetValue(an.GetString(), out var ap)) p = Polyline.V(ap);
            else if (e.TryGetProperty("actor", out var ac) && Stage[ac.GetString()] is { } act) p = act.Pos;
            else if (e.TryGetProperty("landmark", out var lm) && _m.Landmarks.FirstOrDefault(l => l.Id == lm.GetString()) is { } l) p = Polyline.V(l.Camera.Target);
            else if (e.TryGetProperty("route", out var ro) && _m.Routes.TryGetValue(ro.GetString(), out var rp))
            {
                var pl = new Polyline(Polyline.FromArray(rp));
                double fe = e.TryGetProperty("from_end_m", out var f) ? f.GetDouble() * Stage.Scale : 0;
                p = pl.At(pl.Length - fe).Pos;
            }
            if (p is { } q && e.TryGetProperty("off", out var off))
            {
                var o = off.EnumerateArray().Select(x => x.GetDouble()).ToArray();
                p = new Vec3(q.X + o[0] * Stage.Scale, q.Y + o[1] * Stage.Scale, q.Z + (o.Length > 2 ? o[2] * Stage.Scale : 0));
            }
            return p;
        }

        void CastOne(System.Text.Json.JsonElement e)
        {
            string id = e.GetProperty("id").GetString();
            string kind = e.TryGetProperty("kind", out var k) ? k.GetString() : "citizen";
            var col = e.TryGetProperty("color", out var c) ? c.EnumerateArray().Select(x => x.GetDouble()).ToArray() : new[] { 0.8, 0.75, 0.65 };
            var pos = e.TryGetProperty("at", out var at) ? PlaceOf(at) ?? new Vec3(0, 0, 0) : new Vec3(0, 0, 0);
            double hd = e.TryGetProperty("heading_deg", out var h) ? h.GetDouble() * Math.PI / 180 : 0;
            var a = Stage.Cast(id, kind, (col[0], col[1], col[2]), pos, hd);
            if (e.TryGetProperty("face", out var f) && PlaceOf(f) is { } fp) Stage.Face(id, fp);
            if (e.TryGetProperty("mount", out var m)) Stage.Mount(id, m.GetString());
        }

        void StepStage(double dt)
        {
            Stage.Step(dt);
            foreach (var sw in _actorSwarms.Values) sw.Begin();
            foreach (var a in Stage.Actors.Values)
            {
                if (!a.Visible || !_actorSwarms.TryGetValue(a.Kind, out var sw)) continue;
                var col = new Color((float)a.R, (float)a.G, (float)a.B).SrgbToLinear();
                var p = Geo.V(a.Pos) + Vector3.Down * (float)a.Sink;
                sw.AddTilted(p, (float)a.Heading, (float)a.Tilt, 1f, new Color(col.R, col.G, col.B, a.Walking && a.Kind != "horse" ? 1 : 0));
            }
            foreach (var sw in _actorSwarms.Values) sw.End();
            if (_follow != null && Stage[_follow] is { } fa) _v.Rig.Track(Geo.V(fa.Pos) + Vector3.Up * 0.3f);
            _flare.Begin();
            if (_flareLeft > 0)
            {
                _flareLeft -= dt;
                float k = (float)Math.Clamp(_flareLeft, 0, 1) * (0.8f + 0.2f * Mathf.Sin((float)Stage.Time * 9f));
                _flare.Add(_flareAt, 0, 0.5f * k, new Color(2, 0, 1, 0));
                _flareLight.Position = _flareAt + Vector3.Up * 0.2f;
                _flareLight.LightEnergy = 3f * k;
                _flareLight.Visible = true;
            }
            else _flareLight.Visible = false;
            _flare.End();
        }
    }
}
