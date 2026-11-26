// The side panel: time and playback speed, weather (WeatherPanel), sun-arc controls (SunPanel), places, events,
// layers, screenshot and back-to-map. Built in code (no editor scenes to maintain).
using System;
using System.Collections.Generic;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class AtlasUI : CanvasLayer
    {
        public event Action BackToMap;
        public event Action Screenshot;
        CityView _v;
        HSlider _time;
        Label _clock, _eventL;
        readonly List<Button> _speedButtons = new();
        static readonly Color Accent = new(0.95f, 0.72f, 0.38f);

        public void Build(CityView v)
        {
            _v = v;
            Layer = 10;
            var panel = new PanelContainer { Name = "Panel" };
            panel.AddThemeStyleboxOverride("panel", Box(new Color(0.08f, 0.07f, 0.06f, 0.82f), 10));
            panel.SetAnchorsPreset(Control.LayoutPreset.RightWide);
            panel.OffsetLeft = -340; panel.OffsetRight = -12; panel.OffsetTop = 12; panel.OffsetBottom = -12;
            AddChild(panel);
            var scroll = new ScrollContainer { HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled };
            panel.AddChild(scroll);
            var col = new VBoxContainer { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            col.AddThemeConstantOverride("separation", 6);
            scroll.AddChild(col);

            var title = new Label { Text = v.M.Name };
            title.AddThemeFontSizeOverride("font_size", 22);
            title.AddThemeColorOverride("font_color", Accent);
            col.AddChild(title);
            var top = new HBoxContainer();
            col.AddChild(top);
            top.AddChild(Btn("◂ World map", () => BackToMap?.Invoke()));
            top.AddChild(Btn("Screenshot", () => Screenshot?.Invoke()));
            var centre = Btn("Centre view (C)", () => v.Rig.Recentre());
            centre.FocusMode = Control.FocusModeEnum.None;
            col.AddChild(centre);

            Section(col, "Time of day");
            _clock = new Label();
            _clock.AddThemeFontSizeOverride("font_size", 26);
            col.AddChild(_clock);
            _time = Slider(col, 0, 24, 0.01, v.Tod.Hour, h => { v.Tod.Hour = h; v.Tod.Apply(); });
            var speeds = new HBoxContainer();
            col.AddChild(speeds);
            foreach (var (label, hps) in new[] { ("Pause", 0.0), ("1 min/s", 1 / 60.0), ("10 min/s", 1 / 6.0), ("1 h/s", 1.0) })
            {
                var b = Btn(label, () => { v.Tod.Speed = hps; RefreshSpeed(); });
                b.ToggleMode = true;
                b.SetMeta("hps", hps);
                speeds.AddChild(b);
                _speedButtons.Add(b);
            }

            Section(col, "Weather");
            var weather = new WeatherPanel { Name = "Weather" };
            col.AddChild(weather);
            weather.Build(v.Weather.W);

            Section(col, "Sun arc");
            var sun = new SunPanel { Name = "Sun" };
            col.AddChild(sun);
            sun.Build(v.Tod, v.M.Sun, v.Gizmo);

            Section(col, "Places");
            var grid = new GridContainer { Columns = 2 };
            col.AddChild(grid);
            foreach (var lm in v.M.Landmarks)
            {
                var id = lm.Id;
                var b = Btn(lm.Label, () => v.Jump(id));
                b.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
                grid.AddChild(b);
            }
            var camRow = new HBoxContainer();
            col.AddChild(camRow);
            var auto = new CheckBox { Text = "Auto-rotate (R)" };
            auto.Toggled += on => v.Rig.AutoRotate = on;
            camRow.AddChild(auto);
            var fly = new CheckBox { Text = "Free fly (F)" };
            fly.Toggled += on => { if (on != v.Rig.FreeFly) v.Rig.ToggleFreeFly(); };
            camRow.AddChild(fly);

            Section(col, "Events");
            _eventL = new Label { Text = "", AutowrapMode = TextServer.AutowrapMode.WordSmart };
            var evGrid = new GridContainer { Columns = 2 };
            col.AddChild(evGrid);
            foreach (var ev in v.Events.Available)
            {
                var id = ev.Id;
                var b = Btn(ev.Label, () => v.Events.Trigger(id));
                b.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
                evGrid.AddChild(b);
            }
            col.AddChild(_eventL);

            Section(col, "Layers");
            foreach (var (name, get, set) in v.Life.Layers())
            {
                var cb = new CheckBox { Text = name, ButtonPressed = get() };
                cb.Toggled += on => set(on);
                col.AddChild(cb);
            }

            var hint = new Label { Text = "Drag: orbit · Right-drag / arrows: pan · Scroll / Q E: zoom · W S: up/down · A D: orbit · Double-click: focus · C: centre view · R: auto-rotate · F: free-fly" };
            hint.AddThemeFontSizeOverride("font_size", 13);
            hint.AddThemeColorOverride("font_color", new Color(1, 1, 1, 0.75f));
            hint.SetAnchorsPreset(Control.LayoutPreset.BottomLeft);
            hint.OffsetLeft = 14; hint.OffsetTop = -30;
            AddChild(hint);

            v.Tod.Changed += SyncFromModel;
            v.Events.StatusChanged += s => _eventL.Text = s;
            SyncFromModel();
            RefreshSpeed();
        }

        void SyncFromModel()
        {
            var t = _v.Tod;
            _time.SetValueNoSignal(t.Hour);
            _clock.Text = TimeOfDay.Clock(t.Hour) + (t.Speed > 0 ? "  ▶" : "");
        }

        void RefreshSpeed()
        {
            foreach (var b in _speedButtons) b.SetPressedNoSignal(Math.Abs((double)b.GetMeta("hps") - _v.Tod.Speed) < 1e-9);
        }

        static StyleBoxFlat Box(Color c, int r) => new() { BgColor = c, CornerRadiusTopLeft = r, CornerRadiusTopRight = r,
            CornerRadiusBottomLeft = r, CornerRadiusBottomRight = r, ContentMarginLeft = 12, ContentMarginRight = 12, ContentMarginTop = 10, ContentMarginBottom = 10 };

        static void Section(VBoxContainer col, string text)
        {
            col.AddChild(new HSeparator());
            var l = new Label { Text = text.ToUpperInvariant() };
            l.AddThemeFontSizeOverride("font_size", 13);
            l.AddThemeColorOverride("font_color", Accent);
            col.AddChild(l);
        }

        static Button Btn(string text, Action a)
        {
            var b = new Button { Text = text };
            b.Pressed += () => a();
            return b;
        }

        static HSlider Slider(VBoxContainer col, double min, double max, double step, double value, Action<double> changed)
        {
            var s = new HSlider { MinValue = min, MaxValue = max, Step = step, Value = value, SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            s.ValueChanged += x => changed(x);
            col.AddChild(s);
            return s;
        }
    }
}
