// Weather on screen, for the city view and both world maps: the volumetric cloud layer (clouds.gdshader), cloud
// shadows and wet ground on the materials underneath (cloud_shadow.gdshaderinc), rain streaks (city only),
// lightning, and the sky / sun / haze changes (via TimeOfDay). The state itself is Atlas.Core.Weather, shared by
// every view so the weather carries over from map to city.
using System;
using System.Collections.Generic;
using Atlas.Core;
using Godot;

namespace Atlas
{
    /// <summary>How big the weather is in one view (world units).</summary>
    public sealed class CloudScale
    {
        public float Base = 30, Top = 56;               // fair-weather layer
        public float DeckBase = -1, DeckTop = -1;       // > 0: overcast / rain / storm rise to a deck here (city view)
        public float Ground;
        public Vector2 Center, Half = new(200, 200);
        public float Cell = 140, Shape = 24, Detail = 7;
        public float NearFade = 3, Edge = 30, FlashR = 40, SigmaK = 7f, ShadowK = 0.42f;
        public int Steps = 56;
    }

    public partial class CloudLayer : Node3D
    {
        static NoiseTexture2D _weatherTex;
        static NoiseTexture3D _shapeTex, _detailTex;
        MeshInstance3D _box;
        ShaderMaterial _mat;
        CloudScale _s;
        readonly List<ShaderMaterial> _ground = new();
        public float Base { get; private set; }
        public float Top { get; private set; }

        public static Texture2D WeatherTexture => _weatherTex ??= new NoiseTexture2D
        {
            Width = 512, Height = 512, Seamless = true, SeamlessBlendSkirt = 0.2f, GenerateMipmaps = true, Normalize = true,
            Noise = new FastNoiseLite { NoiseType = FastNoiseLite.NoiseTypeEnum.SimplexSmooth, Seed = 11, Frequency = 0.0085f,
                                        FractalType = FastNoiseLite.FractalTypeEnum.Fbm, FractalOctaves = 5, FractalGain = 0.5f, FractalLacunarity = 2.1f },
        };

        static NoiseTexture3D Billows(int size, float freq, int seed, int octaves) => new()
        {
            Width = size, Height = size, Depth = size, Seamless = true, Normalize = true, Invert = true,
            Noise = new FastNoiseLite { NoiseType = FastNoiseLite.NoiseTypeEnum.Cellular, Seed = seed, Frequency = freq,
                                        CellularDistanceFunction = FastNoiseLite.CellularDistanceFunctionEnum.Euclidean,
                                        CellularReturnType = FastNoiseLite.CellularReturnTypeEnum.Distance,
                                        FractalType = FastNoiseLite.FractalTypeEnum.Fbm, FractalOctaves = octaves, FractalGain = 0.45f },
        };

        public void Setup(CloudScale s, IEnumerable<ShaderMaterial> ground)
        {
            _s = s;
            _shapeTex ??= Billows(64, 0.065f, 5, 3);
            _detailTex ??= Billows(32, 0.13f, 9, 2);
            _mat = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/clouds.gdshader"), RenderPriority = 10 };
            _mat.SetShaderParameter("weather_tex", WeatherTexture);
            _mat.SetShaderParameter("shape_tex", _shapeTex);
            _mat.SetShaderParameter("detail_tex", _detailTex);
            float top = Math.Max(s.Top, s.DeckTop) * 1.05f;
            var size = new Vector3(s.Half.X * 2, top - s.Ground, s.Half.Y * 2);
            _box = new MeshInstance3D { Name = "CloudBox", Mesh = new BoxMesh { Size = size }, MaterialOverride = _mat,
                                        CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
                                        Position = new Vector3(s.Center.X, s.Ground + size.Y / 2, s.Center.Y),
                                        ExtraCullMargin = 50f };
            AddChild(_box);
            _ground.Clear();
            foreach (var m in ground)
            {
                if (m == null) continue;
                m.SetShaderParameter("cloud_weather", WeatherTexture);
                m.SetShaderParameter("cloud_cell", s.Cell);
                _ground.Add(m);
            }
            Base = s.Base; Top = s.Top;
        }

        public void Apply(Weather w, TimeOfDay tod, float flash, Vector2 flashXz, float wet)
        {
            var p = w.Current;
            float deck = _s.DeckBase > 0 ? Mathf.SmoothStep(0.6f, 0.85f, (float)p.Coverage) : 0f;
            Base = Mathf.Lerp(_s.Base, _s.DeckBase, deck);
            Top = Mathf.Lerp(_s.Top, _s.DeckTop, deck);
            float thick = Top - Base;
            var wind = new Vector2((float)w.OffsetX, -(float)w.OffsetY) * _s.Cell;      // Godot z = -north
            float a = Mathf.DegToRad((float)w.WindDirDeg);
            var (dir, col, top, bot) = tod.CloudLight();
            var m = _mat;
            m.SetShaderParameter("box_center", _s.Center);
            m.SetShaderParameter("box_half", _s.Half);
            m.SetShaderParameter("ground_y", _s.Ground);
            m.SetShaderParameter("base_y", Base);
            m.SetShaderParameter("top_y", Top);
            m.SetShaderParameter("cell", _s.Cell);
            m.SetShaderParameter("shape_size", _s.Shape);
            m.SetShaderParameter("detail_size", _s.Detail);
            m.SetShaderParameter("wind", wind);
            m.SetShaderParameter("wind_dir", new Vector2(Mathf.Cos(a), -Mathf.Sin(a)));
            m.SetShaderParameter("coverage", (float)p.Coverage);
            m.SetShaderParameter("tower", (float)p.Height);
            m.SetShaderParameter("sigma", _s.SigmaK / Math.Max(1f, thick) * (float)p.Density);
            m.SetShaderParameter("darkness", (float)p.Darkness);
            m.SetShaderParameter("rain", (float)p.Rain);
            m.SetShaderParameter("flash", flash);
            m.SetShaderParameter("flash_xz", flashXz);
            m.SetShaderParameter("flash_r", _s.FlashR);
            m.SetShaderParameter("sun_dir", dir);
            m.SetShaderParameter("sun_col", Lin(col));
            m.SetShaderParameter("amb_top", Lin(top));
            m.SetShaderParameter("amb_bot", Lin(bot));
            m.SetShaderParameter("near_fade", _s.NearFade);
            m.SetShaderParameter("edge", _s.Edge);
            m.SetShaderParameter("steps", _s.Steps);
            // a full deck shades evenly (the dimmer sun already does it): patchy shadows only under broken cloud
            float shadowK = _s.ShadowK * (1f - Mathf.SmoothStep(0.7f, 1.0f, (float)p.Coverage)) * (Visible ? 1f : 0f) * (dir.Y > 0.03f ? 1f : 0f);
            foreach (var g in _ground)
            {
                g.SetShaderParameter("cloud_cover", (float)p.Coverage);
                g.SetShaderParameter("cloud_wind", wind);
                g.SetShaderParameter("cloud_sun", dir);
                g.SetShaderParameter("cloud_mid", Base + thick * 0.3f);
                g.SetShaderParameter("cloud_shadow_k", shadowK);
                g.SetShaderParameter("cloud_wet", wet);
            }
        }

        static Vector3 Lin(Color c)
        {
            var l = new Color(Math.Min(c.R, 1f), Math.Min(c.G, 1f), Math.Min(c.B, 1f)).SrgbToLinear();
            float k = Math.Max(1f, Math.Max(c.R, Math.Max(c.G, c.B)));      // keep intensities above 1
            return new Vector3(l.R, l.G, l.B) * k;
        }
    }

    /// <summary>Rain streaks around the camera's focus (city scale).</summary>
    public partial class RainFx : GpuParticles3D
    {
        public void Setup(float height, float radius)
        {
            Amount = 9000;
            Lifetime = 1.6f;
            Preprocess = 1.6f;
            FixedFps = 60;
            VisibilityAabb = new Aabb(new Vector3(-radius, -height - 5, -radius), new Vector3(radius * 2, height + 10, radius * 2));
            ProcessMaterial = new ParticleProcessMaterial
            {
                EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box, EmissionBoxExtents = new Vector3(radius, 1, radius),
                Direction = Vector3.Down, Spread = 2f, InitialVelocityMin = 26f, InitialVelocityMax = 32f, Gravity = new Vector3(0, -6f, 0),
                ScaleMin = 0.8f, ScaleMax = 1.2f,
            };
            var mat = new StandardMaterial3D
            {
                ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                AlbedoColor = new Color(0.78f, 0.82f, 0.9f, 0.28f), BillboardMode = BaseMaterial3D.BillboardModeEnum.FixedY,
                BillboardKeepScale = true, CullMode = BaseMaterial3D.CullModeEnum.Disabled,
            };
            DrawPass1 = new QuadMesh { Size = new Vector2(0.025f, 1.1f), Material = mat };
            Position = new Vector3(0, height, 0);
            AmountRatio = 0;
            Emitting = false;
        }

        public void SetRain(float rain, Vector3 focus, Vector2 windDir, float height)
        {
            AmountRatio = Math.Clamp(rain, 0, 1);
            Emitting = rain > 0.02f;
            Visible = Emitting;
            GlobalPosition = new Vector3(focus.X, height, focus.Z);
            if (ProcessMaterial is ParticleProcessMaterial pm) pm.Gravity = new Vector3(windDir.X * 9f * rain, -6f, windDir.Y * 9f * rain);
        }
    }

    /// <summary>Drives one view's weather from the shared Weather: clouds, rain, lightning, sky and light.</summary>
    public partial class WeatherView : Node3D
    {
        public Weather W { get; private set; }
        public CloudLayer Clouds { get; private set; }
        public RainFx Rain { get; private set; }
        TimeOfDay _tod;
        Func<Vector3> _focus;
        Func<double> _boost;
        CloudScale _s;
        float _flash, _flashT = -1, _nextFlash = 2, _wet;
        Vector2 _flashXz;
        readonly RandomNumberGenerator _rng = new();
        public bool RainVisible = true;

        public void Setup(Weather w, TimeOfDay tod, CloudScale s, IEnumerable<ShaderMaterial> ground, bool rainFx, Func<Vector3> focus, Func<double> timeBoost = null)
        {
            W = w; _tod = tod; _s = s; _focus = focus; _boost = timeBoost;
            Clouds = new CloudLayer { Name = "Clouds" };
            AddChild(Clouds);
            Clouds.Setup(s, ground);
            if (rainFx)
            {
                Rain = new RainFx { Name = "Rain" };
                AddChild(Rain);
                Rain.Setup(Math.Min(s.Base, 45f), 55f);
            }
            _rng.Seed = 1234;
            _wet = (float)w.Current.Rain;
            Update(0);
        }

        public override void _Process(double delta) => Update(delta);

        void Update(double delta)
        {
            double boost = _boost?.Invoke() ?? 1.0;
            W.Step(delta * boost);
            var p = W.Current;
            float dt = (float)delta;
            // lightning: bursts of 2-3 flickers, a few seconds apart in a storm
            if (p.Lightning > 0.05)
            {
                _nextFlash -= dt;
                if (_nextFlash <= 0)
                {
                    _flashT = 0;
                    var f = _focus?.Invoke() ?? Vector3.Zero;
                    _flashXz = new Vector2(f.X, f.Z) + new Vector2(_rng.RandfRange(-1, 1), _rng.RandfRange(-1, 1)) * _s.Half * 0.5f;
                    _nextFlash = _rng.RandfRange(2.5f, 9f) / (float)p.Lightning;
                }
            }
            if (_flashT >= 0)
            {
                _flashT += dt;
                float t = _flashT;
                _flash = t < 0.08f ? 1f : t < 0.16f ? 0.15f : t < 0.24f ? 0.8f : t < 0.6f ? 0.8f * (1f - (t - 0.24f) / 0.36f) : 0f;
                _flash *= (float)p.Lightning;
                if (t > 0.6f) { _flashT = -1; _flash = 0; }
            }
            // ground gets wet in rain and dries slowly after
            _wet = Mathf.MoveToward(_wet, (float)p.Rain, dt * (p.Rain > _wet ? 0.12f : 0.03f) * (float)Math.Max(1, boost));
            _tod.Wx = p;
            _tod.Flash = Clouds.Visible ? _flash * 0.5f : 0f;
            _tod.Apply(false);
            Clouds.Apply(W, _tod, _flash, _flashXz, _wet);
            if (Rain != null)
            {
                float a = Mathf.DegToRad((float)W.WindDirDeg);
                Rain.SetRain(RainVisible ? (float)p.Rain : 0f, _focus?.Invoke() ?? Vector3.Zero, new Vector2(Mathf.Cos(a), -Mathf.Sin(a)), Math.Min(Clouds.Base, 45f));
            }
        }
    }
}
