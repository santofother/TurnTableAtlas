// Weather controls, shared by the city side panel (AtlasUI) and the world map's weather drop-down (WorldMap):
// the seven presets, auto (a believable walk from one to the next), cloud cover (overrides the preset's), wind
// strength and wind direction. They drive the one Atlas.Core.Weather that AtlasRoot shares between every view, so
// what you set on the map is what you find in the city. The panel polls the model, so auto changes show up too.
using System;
using System.Collections.Generic;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class WeatherPanel : VBoxContainer
    {
        public Weather W { get; private set; }
        readonly Dictionary<WeatherKind, Button> _kinds = new();
        CheckBox _auto;
        HSlider _cover, _wind, _dir;
        Label _state, _coverL, _windL, _dirL;
        Button _coverReset;
        static readonly Color Accent = new(0.95f, 0.72f, 0.38f);

        public void Build(Weather w, int columns = 4)
        {
            W = w;
            AddThemeConstantOverride("separation", 4);
            _state = new Label { AutowrapMode = TextServer.AutowrapMode.WordSmart };
            AddChild(_state);
            var grid = new GridContainer { Columns = columns };
            grid.AddThemeConstantOverride("h_separation", 4);
            AddChild(grid);
            foreach (var k in Weather.All)
            {
                var kind = k;
                var b = new Button { Text = Weather.Label(k), ToggleMode = true, FocusMode = FocusModeEnum.None, SizeFlagsHorizontal = SizeFlags.ExpandFill,
                                     TooltipText = $"{Weather.Label(k)}: eases in over a few seconds" };
                b.Pressed += () => { W.CoverageOverride = null; W.Set(kind); Sync(); };
                grid.AddChild(b);
                _kinds[k] = b;
            }
            _auto = new CheckBox { Text = "Auto: let the weather change by itself", FocusMode = FocusModeEnum.None };
            _auto.Toggled += on => W.Auto = on;
            AddChild(_auto);

            var coverRow = new HBoxContainer();
            _coverL = new Label { SizeFlagsHorizontal = SizeFlags.ExpandFill };
            coverRow.AddChild(_coverL);
            _coverReset = new Button { Text = "Preset", Flat = true, FocusMode = FocusModeEnum.None, TooltipText = "Back to the preset's cloud cover" };
            _coverReset.Pressed += () => { W.CoverageOverride = null; Sync(); };
            coverRow.AddChild(_coverReset);
            AddChild(coverRow);
            _cover = Slider(0, 100, 1, v => W.CoverageOverride = v / 100.0);
            _windL = new Label();
            AddChild(_windL);
            _wind = Slider(0, 3, 0.05, v => W.WindScale = v);
            _dirL = new Label();
            AddChild(_dirL);
            _dir = Slider(0, 359, 1, v => W.WindDirDeg = v);
            Sync();
        }

        HSlider Slider(double min, double max, double step, Action<double> changed)
        {
            var s = new HSlider { MinValue = min, MaxValue = max, Step = step, SizeFlagsHorizontal = SizeFlags.ExpandFill, FocusMode = FocusModeEnum.None };
            s.ValueChanged += x => { changed(x); Sync(); };
            AddChild(s);
            return s;
        }

        public override void _Process(double delta) => Sync();

        /// <summary>A preset's button (the self-test presses them like a user would).</summary>
        public Button KindButton(WeatherKind k) => _kinds[k];

        void Sync()
        {
            if (W == null) return;
            foreach (var (k, b) in _kinds) b.SetPressedNoSignal(k == W.Kind);
            _auto.SetPressedNoSignal(W.Auto);
            var p = W.Current;
            string changing = W.Progress < 0.999 ? $" (changing, {W.Progress * 100:0}%)" : "";
            _state.Text = $"{Weather.Label(W.Kind)}{changing} · cloud {p.Coverage * 100:0}%" +
                          (p.Rain > 0.05 ? $" · rain {p.Rain * 100:0}%" : "") + (p.Fog > 0.3 ? " · fog" : "") + (p.Lightning > 0.05 ? " · lightning" : "");
            _cover.SetValueNoSignal((W.CoverageOverride ?? Weather.Preset(W.Kind).Coverage) * 100);
            _coverL.Text = $"Cloud cover {_cover.Value:0}%" + (W.CoverageOverride.HasValue ? "" : " (preset)");
            _coverReset.Visible = W.CoverageOverride.HasValue;
            _wind.SetValueNoSignal(W.WindScale);
            _windL.Text = $"Wind strength ×{W.WindScale:0.00}";
            _dir.SetValueNoSignal(W.WindDirDeg);
            _dirL.Text = $"Wind from the {Compass(W.WindDirDeg + 180)}, blowing {Compass(W.WindDirDeg)}";
        }

        /// <summary>Compass point for a direction in degrees counter-clockwise from east (the manifest convention).</summary>
        public static string Compass(double ccwFromEast)
        {
            double bearing = ((90 - ccwFromEast) % 360 + 360) % 360;
            string[] n = { "north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west" };
            return n[(int)Math.Round(bearing / 45) % 8];
        }
    }
}
