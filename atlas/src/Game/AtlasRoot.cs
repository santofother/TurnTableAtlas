// App shell: discovers city packages, shows the world map or a city, handles screenshots and test flags.
//   --city=<id>        open a city directly (otherwise the world map)   --view=CAM_03_North
//   --hour=19.5 --speed=0.1 --landmark=forum --event=chariot_race --arc
//   --quit-after=5     exit after N seconds (smoke tests)    --shots=3,6   save screenshots at those seconds
//   --cities=<dir>     where the packages live (default: <repo>/cities, or ./cities next to the executable)
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class AtlasRoot : Node
    {
        public List<CityManifest> Cities { get; private set; } = new();
        public string CitiesDir { get; private set; }
        CityView _city;
        public CityView City => _city;
        public WorldMap Map => _map;
        /// <summary>One weather for the whole Atlas: it carries over between the map and the cities.</summary>
        public Weather Weather { get; } = new(WeatherKind.Fair);
        AtlasUI _ui;
        WorldMap _map;
        double _t, _benchT; long _benchFrames;
        double _quitAfter = -1;
        readonly List<double> _shots = new();
        int _shotIdx;

        public override void _Ready()
        {
            CitiesDir = FindCitiesDir();
            Cities = CityManifest.Discover(CitiesDir);
            GD.Print($"[Atlas] {Cities.Count} cities in {CitiesDir}: {string.Join(", ", Cities.Select(c => c.Id))}");
            _quitAfter = Args.F("quit-after", -1);
            foreach (var s in (Args.Get("shots") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries))
                if (double.TryParse(s, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var d)) _shots.Add(d);
            var id = Args.Get("city");
            if (id != null && Cities.Any(c => c.Id == id)) OpenCity(id);
            else ShowMap();
        }

        static string FindCitiesDir()
        {
            var arg = Args.Get("cities");
            if (!string.IsNullOrEmpty(arg)) return Path.GetFullPath(arg);
            var res = ProjectSettings.GlobalizePath("res://");
            var cands = new[] { Path.Combine(res, "..", "cities"), Path.Combine(Path.GetDirectoryName(OS.GetExecutablePath()) ?? ".", "cities"), Path.Combine(res, "cities") };
            foreach (var c in cands)
                if (Directory.Exists(c)) return Path.GetFullPath(c);
            return Path.GetFullPath(cands[0]);
        }

        public void OpenCity(string id)
        {
            var m = Cities.First(c => c.Id == id);
            CloseAll();
            _city = CityView.Create(m);
            _city.SharedWeather = Weather;
            AddChild(_city);
            if (Args.Has("hour")) { _city.Tod.Hour = Args.F("hour", 17.5f); _city.Tod.Apply(); }
            if (Args.Has("speed")) _city.Tod.Speed = Args.F("speed", 0);
            if (Args.Has("arc")) _city.Gizmo.Visible = true;
            if (Args.Has("landmark")) { var lm = m.Landmarks.FirstOrDefault(l => l.Id == Args.Get("landmark")); if (lm != null) _city.Rig.Snap(Geo.V(lm.Camera.Target), (float)lm.Camera.Yaw, (float)lm.Camera.Pitch, (float)lm.Camera.Dist); }
            if (Args.Has("event")) _city.Events.Trigger(Args.Get("event"));
            _ui = new AtlasUI { Name = "UI" };
            AddChild(_ui);
            _ui.Build(_city);
            _ui.BackToMap += ShowMap;
            _ui.Screenshot += () => SaveShot("user");
            GD.Print($"[Atlas] city open: {m.Id} ({m.Name})");
        }

        public void ShowMap()
        {
            CloseAll();
            _map = new WorldMap { Name = "WorldMap" };
            AddChild(_map);
            _map.Build(this);
            GD.Print("[Atlas] world map");
        }

        void CloseAll()
        {
            foreach (var n in new Node[] { _city, _ui, _map })
                if (n != null && IsInstanceValid(n)) { RemoveChild(n); n.QueueFree(); }
            _city = null; _ui = null; _map = null;
        }

        public override void _Process(double delta)
        {
            _t += delta;
            if (_t > 2.5) { _benchT += delta; _benchFrames++; }
            if (Args.Has("debug-ui") && _t > 2 && _t - delta <= 2 && _ui != null)
                foreach (var c in _ui.GetChildren()) if (c is Control ctl) GD.Print($"[Atlas] ui {ctl.Name} {ctl.GetType().Name} rect {ctl.GetGlobalRect()} visible {ctl.IsVisibleInTree()} min {ctl.GetCombinedMinimumSize()}");
            if (_shotIdx < _shots.Count && _t >= _shots[_shotIdx]) { SaveShot("t" + _shots[_shotIdx].ToString(System.Globalization.CultureInfo.InvariantCulture)); _shotIdx++; }
            if (Args.Has("selftest")) SelfTest.Tick(this, _t);
            if (_quitAfter > 0 && _t >= _quitAfter)
            {
                GD.Print($"[Atlas] quit-after {_quitAfter:0.0}s, avg fps {(_benchT > 0 ? _benchFrames / _benchT : 0):0} (after 2.5 s), now {Engine.GetFramesPerSecond():0}");
                _quitAfter = -1;
                GetTree().Quit();
            }
        }

        void SaveShot(string tag)
        {
            if (DisplayServer.GetName() == "headless") return;
            var img = GetViewport().GetTexture().GetImage();
            var dir = ProjectSettings.GlobalizePath("res://perf_results");
            Directory.CreateDirectory(dir);
            var name = Path.Combine(dir, $"shot_{(_city?.M.Id ?? "map")}_{tag}.png");
            img.SavePng(name);
            GD.Print("[Atlas] screenshot " + name);
        }

        public override void _UnhandledInput(InputEvent e)
        {
            if (e is InputEventKey k && k.Pressed && !k.Echo)
            {
                if (k.Keycode == Key.F12) SaveShot(DateTime.Now.ToString("HHmmss"));
                if (k.Keycode == Key.Escape && _city != null) ShowMap();
            }
        }
    }
}
