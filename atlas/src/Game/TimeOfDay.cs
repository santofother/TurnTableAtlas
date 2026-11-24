// Time of day for the Atlas: the shared sun-arc maths drives the sun/moon lights, the sky shader, fog/haze,
// ambient, window and lamp levels. Same curves as blender/cinematic/sky.py (via SunArc).
using System;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class TimeOfDay : Node3D
    {
        public double Hour = 17.5;
        public double Speed;                 // hours per real second (0 = paused)
        public double Latitude = 38, DayOfYear = 172, NorthOffset;
        public double Elevation { get; private set; }
        public double WindowLevel { get; private set; }
        public double LampLevel { get; private set; }
        public double Daylight { get; private set; }
        public event Action Changed;
        /// <summary>Weather (WeatherView sets it every frame): dims the sun, greys the sky, thickens the haze.</summary>
        public WeatherParams Wx = Weather.Preset(WeatherKind.Clear);
        public float Flash;            // lightning, 0..1
        public float FogScale = 1f;    // the world maps are far bigger than a city: thinner haze per unit
        public DirectionalLight3D SunLight => _sun;
        Vector3 _sunDir = Vector3.Up, _moonDir = Vector3.Down;
        float _sunBase, _moonBase;
        double _dusk, _night;

        DirectionalLight3D _sun, _moon;
        WorldEnvironment _env;
        ShaderMaterial _sky;
        Materials _mats;

        public void Setup(Materials mats, SunDefaults s)
        {
            _mats = mats;
            Latitude = s.LatitudeDeg; DayOfYear = s.DefaultDayOfYear; NorthOffset = s.NorthOffsetDeg;
            _sun = new DirectionalLight3D { Name = "Sun", ShadowEnabled = true, DirectionalShadowMaxDistance = 220f,
                                            DirectionalShadowMode = DirectionalLight3D.ShadowMode.Parallel4Splits,
                                            ShadowBlur = 1.2f, LightAngularDistance = 1.2f };
            _moon = new DirectionalLight3D { Name = "Moon", ShadowEnabled = true, DirectionalShadowMaxDistance = 160f,
                                             LightColor = new Color(0.62f, 0.72f, 1.0f) };
            AddChild(_sun);
            AddChild(_moon);
            _sky = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/sky.gdshader") };
            var env = new Godot.Environment
            {
                BackgroundMode = Godot.Environment.BGMode.Sky,
                Sky = new Sky { SkyMaterial = _sky, RadianceSize = Sky.RadianceSizeEnum.Size128, ProcessMode = Sky.ProcessModeEnum.Realtime },
                AmbientLightSource = Godot.Environment.AmbientSource.Sky,
                ReflectedLightSource = Godot.Environment.ReflectionSource.Sky,
                TonemapMode = Godot.Environment.ToneMapper.Agx,
                TonemapExposure = 1.0f,
                GlowEnabled = true, GlowIntensity = 0.55f, GlowBloom = 0.04f, GlowHdrThreshold = 1.1f,
                FogEnabled = true, FogMode = Godot.Environment.FogModeEnum.Exponential, FogDensity = 0.0008f,
                FogSkyAffect = 0.0f, FogAerialPerspective = 0.1f,
                SsaoEnabled = true, SsaoRadius = 0.6f, SsaoIntensity = 1.2f,
            };
            _env = new WorldEnvironment { Name = "Env", Environment = env };
            AddChild(_env);
            Apply();
        }

        public void ResetSun(SunDefaults s) { Latitude = s.LatitudeDeg; DayOfYear = s.DefaultDayOfYear; NorthOffset = s.NorthOffsetDeg; Apply(); }

        public override void _Process(double delta)
        {
            if (Speed != 0)
            {
                Hour = ((Hour + Speed * delta) % 24.0 + 24.0) % 24.0;
                Apply();
            }
        }

        static float Smooth(double e0, double e1, double x) { var t = Math.Clamp((x - e0) / (e1 - e0), 0, 1); return (float)(t * t * (3 - 2 * t)); }

        public void Apply(bool notify = true)
        {
            var (el, _) = SunArc.Position(Latitude, DayOfYear, Hour, NorthOffset);
            Elevation = el;
            var d = Geo.V(SunArc.Direction(Latitude, DayOfYear, Hour, NorthOffset)).Normalized();
            var md = Geo.V(SunArc.Direction(Latitude, (DayOfYear + 182) % 365 + 1, (Hour + 12.4) % 24, NorthOffset)).Normalized();
            Daylight = SunArc.Daylight(el);
            double dusk = SunArc.Dusk(el), night = 1.0 - Smooth(-10.0, 1.0, el);
            WindowLevel = SunArc.WindowLevel(el, Hour);
            LampLevel = SunArc.NightLevel(el);
            float warm = Smooth(2.0, 35.0, el);
            Orient(_sun, d);
            _sunBase = 2.2f * Smooth(-3.0, 9.0, el);
            _sun.LightEnergy = _sunBase * (float)(1.0 - 0.8 * Wx.Darkness);
            _sun.LightColor = new Color(1.0f, 0.55f + 0.38f * warm, 0.30f + 0.55f * warm);
            _sun.Visible = el > -4;
            Orient(_moon, md);
            _moonBase = 0.22f * (1f - Smooth(-8.0, 2.0, el)) * Smooth(-0.05, 0.25, md.Y);
            _moon.LightEnergy = _moonBase * (float)(1.0 - 0.7 * Wx.Darkness);
            _moon.Visible = _moon.LightEnergy > 0.005f;
            _sky.SetShaderParameter("day", (float)Daylight);
            _sky.SetShaderParameter("dusk", (float)dusk);
            _sky.SetShaderParameter("night", (float)night);
            _sky.SetShaderParameter("sun_dir", d);
            _sky.SetShaderParameter("moon_dir", md);
            _sky.SetShaderParameter("overcast", (float)Math.Clamp(Wx.Darkness * 1.25, 0, 1));
            _sky.SetShaderParameter("flash", Flash);
            _sunDir = d; _moonDir = md; _dusk = dusk; _night = night;
            var env = _env.Environment;
            env.AmbientLightEnergy = (float)((0.45 + 0.35 * Daylight) * (1.0 - 0.25 * Wx.Darkness)) + 1.6f * Flash;
            var dayFog = new Color(0.80f, 0.70f, 0.72f);
            var duskFog = new Color(0.95f, 0.62f, 0.48f);
            var nightFog = new Color(0.05f, 0.06f, 0.11f);
            var fog = nightFog.Lerp(dayFog, (float)Daylight).Lerp(duskFog, (float)dusk * 0.7f);
            fog = fog.Lerp(new Color(0.55f, 0.57f, 0.60f) * (0.12f + 0.88f * (float)Daylight), (float)Math.Clamp(Wx.Darkness + Wx.Fog * 0.6, 0, 0.85));
            env.FogLightColor = fog;
            env.FogDensity = (0.0004f + 0.0006f * (float)Daylight + (float)(Wx.Fog * 0.011 + Wx.Rain * 0.003)) * FogScale;
            env.GlowIntensity = 0.35f + 0.5f * (float)LampLevel;
            env.TonemapExposure = 1.0f + 0.5f * (float)night;
            _mats?.SetNight((float)WindowLevel, (float)LampLevel);
            if (notify) Changed?.Invoke();
        }

        /// <summary>What lights the clouds: the sun by day, the moon by night, and the sky's ambient above and below.</summary>
        public (Vector3 Dir, Color Col, Color AmbTop, Color AmbBot) CloudLight()
        {
            bool sunUp = Elevation > -4;
            var dir = sunUp ? _sunDir : _moonDir;
            var src = sunUp ? _sun : _moon;
            float e = sunUp ? _sunBase * 1.15f : _moonBase * 1.6f;
            var col = src.LightColor * e;
            float day = (float)Daylight, dusk = (float)_dusk, night = (float)_night;
            var top = new Color(0.035f, 0.05f, 0.10f).Lerp(new Color(0.50f, 0.62f, 0.86f), day).Lerp(new Color(0.85f, 0.55f, 0.50f), dusk * 0.7f);
            var bot = new Color(0.02f, 0.025f, 0.05f).Lerp(new Color(0.42f, 0.43f, 0.47f), day).Lerp(new Color(0.48f, 0.32f, 0.30f), dusk * 0.7f);
            float k = 1f - 0.4f * night;
            return (dir.Normalized(), col, top * k, bot * k);
        }

        static void Orient(DirectionalLight3D l, Vector3 towardSun)
        {
            var dir = -towardSun;                                   // light travels from the sun
            var up = Mathf.Abs(dir.Y) > 0.99f ? Vector3.Forward : Vector3.Up;
            l.Basis = Basis.LookingAt(dir, up);
        }

        public static string Clock(double h)
        {
            int hh = (int)Math.Floor(h) % 24, mm = (int)Math.Floor((h - Math.Floor(h)) * 60);
            return $"{hh:00}:{mm:00}";
        }
    }
}
