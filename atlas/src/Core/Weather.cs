// Weather for the Atlas (city view and world map share one instance): a preset picks target parameters, the
// current parameters ease towards them, wind moves a drift offset that the cloud layer and its ground shadows
// sample, and "auto" walks a small seeded Markov chain of believable changes. Pure C#, unit-tested.
using System;
using System.Collections.Generic;

namespace Atlas.Core
{
    public enum WeatherKind { Clear, Fair, Cloudy, Overcast, Rain, Storm, Fog }

    /// <summary>Everything the renderers need, each 0..1 unless noted.</summary>
    public readonly record struct WeatherParams(
        double Coverage,     // fraction of the sky with cloud
        double Density,      // how thick / opaque the clouds are
        double Height,       // how tall the clouds tower (0 flat stratus .. 1 cumulonimbus)
        double Darkness,     // how much the cloud dims the sun and greys the sky
        double Rain,         // precipitation
        double Lightning,    // flash frequency
        double Fog,          // ground haze
        double Wind)         // wind strength (scales drift speed)
    {
        public static WeatherParams Lerp(WeatherParams a, WeatherParams b, double t) => new(
            a.Coverage + (b.Coverage - a.Coverage) * t, a.Density + (b.Density - a.Density) * t,
            a.Height + (b.Height - a.Height) * t, a.Darkness + (b.Darkness - a.Darkness) * t,
            a.Rain + (b.Rain - a.Rain) * t, a.Lightning + (b.Lightning - a.Lightning) * t,
            a.Fog + (b.Fog - a.Fog) * t, a.Wind + (b.Wind - a.Wind) * t);
    }

    public sealed class Weather
    {
        public static readonly WeatherKind[] All = (WeatherKind[])Enum.GetValues(typeof(WeatherKind));

        public static WeatherParams Preset(WeatherKind k) => k switch
        {
            WeatherKind.Clear => new(0.04, 0.55, 0.30, 0.00, 0, 0, 0.00, 0.25),
            WeatherKind.Fair => new(0.28, 0.75, 0.55, 0.05, 0, 0, 0.00, 0.45),
            WeatherKind.Cloudy => new(0.55, 0.90, 0.70, 0.25, 0, 0, 0.05, 0.60),
            WeatherKind.Overcast => new(0.90, 1.00, 0.45, 0.60, 0, 0, 0.15, 0.55),
            WeatherKind.Rain => new(0.85, 1.15, 0.65, 0.72, 0.65, 0, 0.30, 0.75),
            WeatherKind.Storm => new(0.82, 1.35, 1.00, 0.85, 1.00, 1.0, 0.35, 1.00),
            WeatherKind.Fog => new(0.20, 0.60, 0.25, 0.35, 0, 0, 1.00, 0.10),
            _ => throw new ArgumentOutOfRangeException(nameof(k)),
        };

        public static string Label(WeatherKind k) => k.ToString();

        // plausible next states for auto mode (weights)
        static readonly Dictionary<WeatherKind, (WeatherKind K, double W)[]> Next = new()
        {
            [WeatherKind.Clear] = new[] { (WeatherKind.Fair, 3.0), (WeatherKind.Fog, 0.6), (WeatherKind.Clear, 1.0) },
            [WeatherKind.Fair] = new[] { (WeatherKind.Clear, 1.5), (WeatherKind.Cloudy, 2.0), (WeatherKind.Fair, 1.0) },
            [WeatherKind.Cloudy] = new[] { (WeatherKind.Fair, 1.5), (WeatherKind.Overcast, 1.5), (WeatherKind.Rain, 0.8), (WeatherKind.Storm, 0.4) },
            [WeatherKind.Overcast] = new[] { (WeatherKind.Cloudy, 1.5), (WeatherKind.Rain, 1.5), (WeatherKind.Fog, 0.4) },
            [WeatherKind.Rain] = new[] { (WeatherKind.Overcast, 1.5), (WeatherKind.Cloudy, 1.0), (WeatherKind.Storm, 0.7) },
            [WeatherKind.Storm] = new[] { (WeatherKind.Rain, 2.0), (WeatherKind.Cloudy, 1.0) },
            [WeatherKind.Fog] = new[] { (WeatherKind.Clear, 1.5), (WeatherKind.Fair, 1.5), (WeatherKind.Overcast, 0.5) },
        };

        public WeatherKind Kind { get; private set; }
        public WeatherParams Current { get; private set; }
        public WeatherParams Target { get; private set; }
        /// <summary>Coverage set by hand (slider); null = the preset's.</summary>
        public double? CoverageOverride;
        /// <summary>Degrees counter-clockwise from +X (east), the direction the wind blows towards.</summary>
        public double WindDirDeg = 20;
        /// <summary>Multiplies the preset's wind (slider).</summary>
        public double WindScale = 1.0;
        /// <summary>Drift in "cloud cells" (renderers multiply by their cell size): (east, north).</summary>
        public double OffsetX { get; private set; }
        public double OffsetY { get; private set; }
        public bool Auto;
        /// <summary>Seconds of real time a state holds in auto mode before it may change.</summary>
        public double AutoHold = 40;
        public event Action<WeatherKind> KindChanged;

        WeatherParams _from;
        double _blend = 1, _blendDur = 1, _held;
        readonly Random _rng;

        public Weather(WeatherKind start = WeatherKind.Fair, int seed = 7)
        {
            _rng = new Random(seed);
            Kind = start;
            Current = Target = _from = Preset(start);
        }

        /// <summary>Change weather; the parameters ease over <paramref name="seconds"/> (0 = at once).</summary>
        public void Set(WeatherKind k, double seconds = 6)
        {
            _from = Current;
            Target = Preset(k);
            _blendDur = Math.Max(1e-6, seconds);
            _blend = seconds <= 0 ? 1 : 0;
            if (seconds <= 0) Current = Effective(Target);
            _held = 0;
            if (k != Kind) { Kind = k; KindChanged?.Invoke(k); }
        }

        WeatherParams Effective(WeatherParams p) =>
            CoverageOverride.HasValue ? p with { Coverage = Math.Clamp(CoverageOverride.Value, 0, 1) } : p;

        /// <summary>Smootherstep progress of the current transition (1 = settled).</summary>
        public double Progress => _blend;

        /// <summary>Drift speed in cells per second for the current wind.</summary>
        public double DriftSpeed => 0.004 + 0.028 * Current.Wind * WindScale;

        public void Step(double dt)
        {
            if (dt <= 0) return;
            if (_blend < 1) _blend = Math.Min(1, _blend + dt / _blendDur);
            double s = _blend * _blend * _blend * (_blend * (_blend * 6 - 15) + 10);
            Current = WeatherParams.Lerp(Effective(_from), Effective(Target), s);
            double a = WindDirDeg * Math.PI / 180, v = DriftSpeed * dt;
            OffsetX += Math.Cos(a) * v;
            OffsetY += Math.Sin(a) * v;
            // keep the offset bounded without a visible jump: the cloud textures tile every 1 cell
            if (Math.Abs(OffsetX) > 4096) OffsetX -= Math.Truncate(OffsetX);
            if (Math.Abs(OffsetY) > 4096) OffsetY -= Math.Truncate(OffsetY);
            if (Auto && _blend >= 1)
            {
                _held += dt;
                if (_held >= AutoHold) Set(PickNext(), 12);
            }
        }

        WeatherKind PickNext()
        {
            var opts = Next[Kind];
            double tot = 0;
            foreach (var o in opts) tot += o.W;
            double r = _rng.NextDouble() * tot;
            foreach (var o in opts) { r -= o.W; if (r <= 0) return o.K; }
            return opts[^1].K;
        }
    }
}
