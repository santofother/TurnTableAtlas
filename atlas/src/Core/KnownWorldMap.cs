// The Known World relief map's metadata (atlas/assets/map/known_world/known_world.json, written by
// tools/bake_known_world.py from KnownWorld.blend): bounds in blend units (1 unit = UnitM metres, +X east, +Y north),
// elevation range and the blend's vertical exaggeration, settlements and realm seats, the blend's CAM_* cameras as
// orbit presets, and the affine that carries a uv on the painted Caelora Geography map onto this map.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Atlas.Core
{
    public sealed class KnownWorldMap
    {
        [JsonPropertyName("bounds_xy")] public double[] BoundsXy { get; set; }
        [JsonPropertyName("elev_min_m")] public double ElevMin { get; set; }
        [JsonPropertyName("elev_max_m")] public double ElevMax { get; set; }
        /// <summary>Metres per blend unit (the blend's unit scale: 10 miles).</summary>
        [JsonPropertyName("unit_m")] public double UnitM { get; set; } = 16093.44;
        /// <summary>Vertical exaggeration of the blend's terrain (its Z scale).</summary>
        [JsonPropertyName("exaggeration")] public double Exaggeration { get; set; } = 15;
        [JsonPropertyName("cameras")] public List<View> Cameras { get; set; } = new();
        [JsonPropertyName("albedo")] public string Albedo { get; set; }
        [JsonPropertyName("height")] public string Height { get; set; }
        [JsonPropertyName("height_size")] public int[] HeightSize { get; set; }
        [JsonPropertyName("geo_to_kw")] public double[][] GeoToKw { get; set; }
        [JsonPropertyName("settlements")] public List<Place> Settlements { get; set; } = new();
        [JsonPropertyName("realms")] public List<Place> Realms { get; set; } = new();
        [JsonIgnore] public string Directory { get; private set; }

        public sealed class View
        {
            [JsonPropertyName("id")] public string Id { get; set; }
            [JsonPropertyName("name")] public string Name { get; set; }
            [JsonPropertyName("target")] public double[] Target { get; set; }
            [JsonPropertyName("yaw")] public double Yaw { get; set; }
            [JsonPropertyName("pitch")] public double Pitch { get; set; }
            [JsonPropertyName("dist")] public double Dist { get; set; }
            public CameraPreset Preset => new() { Target = Target, Yaw = Yaw, Pitch = Pitch, Dist = Dist };
        }

        public sealed class Place
        {
            [JsonPropertyName("id")] public string Id { get; set; }
            [JsonPropertyName("name")] public string Name { get; set; }
            [JsonPropertyName("type")] public string Type { get; set; }
            [JsonPropertyName("realm")] public string Realm { get; set; }
            [JsonPropertyName("uv")] public double[] Uv { get; set; }
        }

        public static KnownWorldMap Load(string jsonPath)
        {
            var m = JsonSerializer.Deserialize<KnownWorldMap>(File.ReadAllText(jsonPath));
            m.Directory = Path.GetDirectoryName(Path.GetFullPath(jsonPath));
            return m;
        }

        public double Width => BoundsXy[2] - BoundsXy[0];
        public double Depth => BoundsXy[3] - BoundsXy[1];

        /// <summary>uv on the painted Geography map -> uv on this map (both from the top-left).</summary>
        public (double U, double V) FromGeo(double u, double v)
        {
            var a = GeoToKw;
            return (a[0][0] * u + a[0][1] * v + a[0][2], a[1][0] * u + a[1][1] * v + a[1][2]);
        }

        /// <summary>uv on this map -> uv on the painted Geography map (the inverse of <see cref="FromGeo"/>).</summary>
        public (double U, double V) ToGeo(double u, double v)
        {
            var a = GeoToKw;
            double det = a[0][0] * a[1][1] - a[0][1] * a[1][0];
            double x = u - a[0][2], y = v - a[1][2];
            return ((a[1][1] * x - a[0][1] * y) / det, (-a[1][0] * x + a[0][0] * y) / det);
        }

        /// <summary>uv (from the top-left) -> blend-world (x east, y north).</summary>
        public (double X, double Y) UvToXy(double u, double v) => (BoundsXy[0] + u * Width, BoundsXy[3] - v * Depth);

        /// <summary>Blend-world (x east, y north) -> uv from the top-left.</summary>
        public (double U, double V) XyToUv(double x, double y) => ((x - BoundsXy[0]) / Width, (BoundsXy[3] - y) / Depth);

        /// <summary>Height in blend units, exaggerated as in the blend (sea level 0).</summary>
        public double Units(double metres) => metres / UnitM * Exaggeration;

        /// <summary>The opening view: square to the table (north up), aimed at the middle of the map,
        /// at the pitch and distance of the blend's overview camera.</summary>
        public CameraPreset HomeView()
        {
            var overview = Cameras.FirstOrDefault();
            return new CameraPreset
            {
                Target = new[] { BoundsXy[0] + Width / 2, BoundsXy[1] + Depth / 2, 0.0 },
                Yaw = -90,
                Pitch = overview?.Pitch ?? 58,
                Dist = overview?.Dist ?? Width,
            };
        }

        public Place Settlement(string id) =>
            id == null ? null : Settlements.FirstOrDefault(s => s.Id == id || s.Id == "settlement:" + id);

        /// <summary>Where a city package sits on this map: its linked settlement, else its painted-map pin carried over.</summary>
        public (double U, double V)? PinFor(WorldMapPin pin)
        {
            if (pin == null) return null;
            var s = Settlement(pin.Settlement);
            if (s != null) return (s.Uv[0], s.Uv[1]);
            if (pin.KwXy is { Length: 2 }) return XyToUv(pin.KwXy[0], pin.KwXy[1]);   // FIX(haven)
            if (pin.PinUv is { Length: 2 }) return FromGeo(pin.PinUv[0], pin.PinUv[1]);
            return null;
        }

        /// <summary>Decode height.png's packed 16-bit value (R high byte, G low byte) to metres.</summary>
        public double Metres(byte r, byte g) => ElevMin + (r * 256 + g) / 65535.0 * (ElevMax - ElevMin);
    }
}
