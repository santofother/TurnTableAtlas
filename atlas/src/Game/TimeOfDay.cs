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

        public void Apply()
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
            _sun.LightEnergy = 2.2f * Smooth(-3.0, 9.0, el);
            _sun.LightColor = new Color(1.0f, 0.55f + 0.38f * warm, 0.30f + 0.55f * warm);
            _sun.Visible = el > -4;
            Orient(_moon, md);
            _moon.LightEnergy = 0.22f * (1f - Smooth(-8.0, 2.0, el)) * Smooth(-0.05, 0.25, md.Y);
            _moon.Visible = _moon.LightEnergy > 0.005f;
            _sky.SetShaderParameter("day", (float)Daylight);
            _sky.SetShaderParameter("dusk", (float)dusk);
            _sky.SetShaderParameter("night", (float)night);
            _sky.SetShaderParameter("sun_dir", d);
            _sky.SetShaderParameter("moon_dir", md);
            var env = _env.Environment;
            env.AmbientLightEnergy = (float)(0.45 + 0.35 * Daylight);
            var dayFog = new Color(0.80f, 0.70f, 0.72f);
            var duskFog = new Color(0.95f, 0.62f, 0.48f);
            var nightFog = new Color(0.05f, 0.06f, 0.11f);
            var fog = nightFog.Lerp(dayFog, (float)Daylight).Lerp(duskFog, (float)dusk * 0.7f);
            env.FogLightColor = fog;
            env.FogDensity = 0.0004f + 0.0006f * (float)Daylight;
            env.GlowIntensity = 0.35f + 0.5f * (float)LampLevel;
            env.TonemapExposure = 1.0f + 0.5f * (float)night;
            _mats?.SetNight((float)WindowLevel, (float)LampLevel);
            Changed?.Invoke();
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
