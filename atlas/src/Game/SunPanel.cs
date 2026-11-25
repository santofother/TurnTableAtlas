// Sun-arc controls (latitude, season, north offset, the sun path, reset), shared by the city side panel (AtlasUI) and
// the Known World's sun drop-down (WorldMap).
using System;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class SunPanel : VBoxContainer
    {
        TimeOfDay _tod;
        SunArcGizmo _gizmo;
        HSlider _lat, _doy, _north;
        Label _sunL, _latL, _doyL, _northL;
        CheckBox _show;

        /// <summary>The latitude, season and north sliders (the self-test drags them like a user would).</summary>
        public HSlider Latitude => _lat;
        public CheckBox ShowPath => _show;

        public void Build(TimeOfDay tod, SunDefaults defaults, SunArcGizmo gizmo)
        {
            _tod = tod; _gizmo = gizmo;
            AddThemeConstantOverride("separation", 6);
            _sunL = new Label { AutowrapMode = TextServer.AutowrapMode.WordSmart };
            AddChild(_sunL);
            _latL = new Label(); AddChild(_latL);
            _lat = Slider(-66, 66, 0.5, x => _tod.Latitude = x);
            _doyL = new Label(); AddChild(_doyL);
            _doy = Slider(1, 365, 1, x => _tod.DayOfYear = x);
            _northL = new Label(); AddChild(_northL);
            _north = Slider(-180, 180, 1, x => _tod.NorthOffset = x);
            var row = new HBoxContainer();
            AddChild(row);
            _show = new CheckBox { Text = "Show sun path", ButtonPressed = gizmo.Visible, FocusMode = FocusModeEnum.None };
            _show.Toggled += on => _gizmo.Visible = on;
            row.AddChild(_show);
            var reset = new Button { Text = "Reset", FocusMode = FocusModeEnum.None };
            reset.Pressed += () => { _tod.ResetSun(defaults); _gizmo.Rebuild(_tod); };
            row.AddChild(reset);
            tod.Changed += Sync;
            gizmo.Rebuild(tod);
            Sync();
        }

        HSlider Slider(double min, double max, double step, Action<double> set)
        {
            var s = new HSlider { MinValue = min, MaxValue = max, Step = step, SizeFlagsHorizontal = SizeFlags.ExpandFill, FocusMode = FocusModeEnum.None };
            s.ValueChanged += x => { set(x); _tod.Apply(); _gizmo.Rebuild(_tod); };
            AddChild(s);
            return s;
        }

        void Sync()
        {
            var t = _tod;
            _lat.SetValueNoSignal(t.Latitude);
            _doy.SetValueNoSignal(t.DayOfYear);
            _north.SetValueNoSignal(t.NorthOffset);
            _latL.Text = $"Latitude {Math.Abs(t.Latitude):0.#}° {(t.Latitude >= 0 ? "N" : "S")}";
            _doyL.Text = "Day " + DateLabel(t.DayOfYear);
            _northL.Text = $"North offset {t.NorthOffset:0}°";
            var (rise, set) = SunArc.SunriseSunset(t.Latitude, t.DayOfYear);
            var noon = SunArc.Position(t.Latitude, t.DayOfYear, 12).Elevation;
            _sunL.Text = rise.HasValue
                ? $"Sun {t.Elevation:0}° up · rises {TimeOfDay.Clock(rise.Value)} · noon {noon:0}° · sets {TimeOfDay.Clock(set.Value)}"
                : "Polar night: the sun does not rise";
        }

        static string DateLabel(double doy)
        {
            var d = new DateTime(2025, 1, 1).AddDays(Math.Clamp((int)doy, 1, 365) - 1);
            return d.ToString("d MMM", System.Globalization.CultureInfo.InvariantCulture) + $" ({(int)doy})";
        }
    }
}
