// city.json v1 (docs/city_schema.md) as plain C# classes. Points stay double[] in the manifest frame.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Atlas.Core
{
    public class CityManifest
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("name")] public string Name { get; set; }
        [JsonPropertyName("version")] public int Version { get; set; }
        [JsonPropertyName("model_scale")] public double ModelScale { get; set; }
        [JsonPropertyName("extent")] public double[] Extent { get; set; }
        [JsonPropertyName("world_map")] public WorldMapPin WorldMap { get; set; }
        [JsonPropertyName("sun")] public SunDefaults Sun { get; set; }
        [JsonPropertyName("files")] public Dictionary<string, string> Files { get; set; }
        [JsonPropertyName("street_graph")] public StreetGraphData StreetGraph { get; set; }
        [JsonPropertyName("spawn_zones")] public List<SpawnZone> SpawnZones { get; set; } = new();
        [JsonPropertyName("ship_lanes")] public List<ShipLane> ShipLanes { get; set; } = new();
        [JsonPropertyName("moorings")] public List<ShipPlacement> Moorings { get; set; } = new();
        [JsonPropertyName("anchored_ships")] public List<ShipPlacement> AnchoredShips { get; set; } = new();
        [JsonPropertyName("boats")] public List<ShipPlacement> Boats { get; set; } = new();
        [JsonPropertyName("berths")] public List<double[]> Berths { get; set; } = new();
        [JsonPropertyName("venues")] public List<Venue> Venues { get; set; } = new();
        [JsonPropertyName("routes")] public Dictionary<string, double[][]> Routes { get; set; } = new();
        [JsonPropertyName("night_lights")] public List<NightLight> NightLights { get; set; } = new();
        [JsonPropertyName("landmarks")] public List<Landmark> Landmarks { get; set; } = new();
        [JsonPropertyName("steam_vents")] public List<double[]> SteamVents { get; set; } = new();
        [JsonPropertyName("events")] public List<string> Events { get; set; } = new();
        /// <summary>"city" (default) or "estate": a country house with its grounds (fewer people, no ships or venues).</summary>
        [JsonPropertyName("kind")] public string Kind { get; set; } = "city";
        /// <summary>Estates: named staging points (gate_stop, aegis_painting, cold_pool...), model metres.</summary>
        [JsonPropertyName("anchors")] public Dictionary<string, double[]> Anchors { get; set; } = new();
        /// <summary>Estates: object name prefixes the Atlas can hide to look inside (roofs, upper storey).</summary>
        [JsonPropertyName("cutaway")] public Dictionary<string, List<string>> Cutaway { get; set; } = new();
        /// <summary>Estates: the ground as an n x n height grid over the extent (model metres, row 0 = south).</summary>
        [JsonPropertyName("terrain_grid")] public TerrainGrid Terrain { get; set; }
        [JsonIgnore] public bool IsEstate => Kind == "estate";

        [JsonIgnore] public string Directory { get; set; }

        public Venue Venue(string id) => Venues.FirstOrDefault(v => v.Id == id);
        public Venue VenueOfType(string type) => Venues.FirstOrDefault(v => v.Type == type);
        public ShipLane Lane(string id) => ShipLanes.FirstOrDefault(l => l.Id == id);

        public static CityManifest Load(string path)
        {
            var m = JsonSerializer.Deserialize<CityManifest>(File.ReadAllText(path));
            if (m == null) throw new InvalidDataException("empty manifest " + path);
            if (m.Version != 1) throw new InvalidDataException($"unsupported city.json version {m.Version}");
            m.Directory = Path.GetDirectoryName(Path.GetFullPath(path));
            return m;
        }

        /// <summary>All packages under a cities/ folder (each sub-folder with a city.json), sorted by name.</summary>
        public static List<CityManifest> Discover(string citiesDir)
        {
            var list = new List<CityManifest>();
            if (!System.IO.Directory.Exists(citiesDir)) return list;
            foreach (var d in System.IO.Directory.GetDirectories(citiesDir).OrderBy(x => x))
            {
                var p = Path.Combine(d, "city.json");
                if (File.Exists(p)) list.Add(Load(p));
            }
            return list;
        }

        public string FilePath(string key) => Path.Combine(Directory, Files[key]);
    }

    public class TerrainGrid
    {
        [JsonPropertyName("n")] public int N { get; set; }
        [JsonPropertyName("z")] public double[] Z { get; set; }

        /// <summary>Bilinear height at a model point (extent [-half, half] on both axes).</summary>
        public double At(double x, double y, double half)
        {
            double fx = Math.Clamp((x + half) / (2 * half) * (N - 1), 0, N - 1.000001), fy = Math.Clamp((y + half) / (2 * half) * (N - 1), 0, N - 1.000001);
            int i = (int)fx, j = (int)fy;
            double tx = fx - i, ty = fy - j;
            double a = Z[j * N + i] + (Z[j * N + i + 1] - Z[j * N + i]) * tx;
            double b = Z[(j + 1) * N + i] + (Z[(j + 1) * N + i + 1] - Z[(j + 1) * N + i]) * tx;
            return a + (b - a) * ty;
        }
    }

    /// <summary>How an estate stands on the Known World: its miniature's size (x its true size) and its hills.</summary>
    public class MapMiniature
    {
        [JsonPropertyName("exaggeration")] public double Exaggeration { get; set; } = 12;
        [JsonPropertyName("hills_radius_units")] public double HillsRadius { get; set; } = 0.55;
    }

    public class WorldMapPin
    {
        [JsonPropertyName("miniature")] public MapMiniature Miniature { get; set; }
        [JsonPropertyName("map")] public string Map { get; set; }
        [JsonPropertyName("pin_uv")] public double[] PinUv { get; set; }
        /// <summary>Optional settlement id on the Known World relief map (e.g. "settlement:calderra").</summary>
        [JsonPropertyName("settlement")] public string Settlement { get; set; }
        [JsonPropertyName("lore")] public string Lore { get; set; }
    }

    public class SunDefaults
    {
        [JsonPropertyName("latitude_deg")] public double LatitudeDeg { get; set; }
        [JsonPropertyName("default_day_of_year")] public double DefaultDayOfYear { get; set; }
        [JsonPropertyName("north_offset_deg")] public double NorthOffsetDeg { get; set; }
        [JsonPropertyName("sunrise_h")] public double SunriseH { get; set; }
        [JsonPropertyName("sunset_h")] public double SunsetH { get; set; }
    }

    public class StreetGraphData
    {
        [JsonPropertyName("nodes")] public double[][] Nodes { get; set; }
        [JsonPropertyName("edges")] public double[][] Edges { get; set; }
    }

    public class SpawnZone
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("poly")] public double[][] Poly { get; set; }
        [JsonPropertyName("density")] public double Density { get; set; }
        [JsonPropertyName("points")] public double[][] Points { get; set; }
    }

    public class ShipLane
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("points")] public double[][] Points { get; set; }
        [JsonPropertyName("loop")] public bool Loop { get; set; }
        [JsonPropertyName("kinds")] public List<string> Kinds { get; set; }
        [JsonPropertyName("speed")] public double Speed { get; set; }
        [JsonPropertyName("every_s")] public double EveryS { get; set; }
        [JsonPropertyName("dwell_s")] public double DwellS { get; set; }
        [JsonPropertyName("then")] public string Then { get; set; }
    }

    public class ShipPlacement
    {
        [JsonPropertyName("object")] public string Object { get; set; }
        [JsonPropertyName("kind")] public string Kind { get; set; }
        [JsonPropertyName("pos")] public double[] Pos { get; set; }
        [JsonPropertyName("heading_deg")] public double HeadingDeg { get; set; }
        [JsonPropertyName("scale")] public double Scale { get; set; }
        [JsonPropertyName("voyage")] public BoatVoyageData Voyage { get; set; }
    }

    public class BoatVoyageData
    {
        [JsonPropertyName("points")] public double[][] Points { get; set; }
        [JsonPropertyName("speed")] public double Speed { get; set; }
        [JsonPropertyName("dwell_s")] public double DwellS { get; set; }
        [JsonPropertyName("phase_s")] public double PhaseS { get; set; }
    }

    public class SeatTier
    {
        [JsonPropertyName("ring")] public double[][] Ring { get; set; }
        [JsonPropertyName("capacity")] public int Capacity { get; set; }
    }

    public class Venue
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("type")] public string Type { get; set; }
        [JsonPropertyName("label")] public string Label { get; set; }
        [JsonPropertyName("center")] public double[] Center { get; set; }
        [JsonPropertyName("heading_deg")] public double HeadingDeg { get; set; }
        [JsonPropertyName("seat_tiers")] public List<SeatTier> SeatTiers { get; set; } = new();
        [JsonPropertyName("entrances")] public double[][] Entrances { get; set; }
        [JsonPropertyName("floor_poly")] public double[][] FloorPoly { get; set; }
        [JsonPropertyName("floor_z")] public double FloorZ { get; set; }
        [JsonPropertyName("beast_gates")] public double[][] BeastGates { get; set; }
        [JsonPropertyName("track_centerline")] public double[][] TrackCenterline { get; set; }
        [JsonPropertyName("lanes")] public int Lanes { get; set; }
        [JsonPropertyName("lane_width")] public double LaneWidth { get; set; }
        [JsonPropertyName("lane_radii")] public double[] LaneRadii { get; set; }
        [JsonPropertyName("start_gates")] public double[][] StartGates { get; set; }
        [JsonPropertyName("turning_posts")] public double[][] TurningPosts { get; set; }
        [JsonPropertyName("laps")] public int Laps { get; set; }
        [JsonPropertyName("royal_box")] public double[] RoyalBox { get; set; }
        [JsonPropertyName("stage")] public double[][] Stage { get; set; }
        [JsonPropertyName("stage_z")] public double StageZ { get; set; }

        public int Capacity => SeatTiers.Sum(t => t.Capacity);
        public IEnumerable<double[]> Seats => SeatTiers.SelectMany(t => t.Ring);
    }

    public class NightLight
    {
        [JsonPropertyName("pos")] public double[] Pos { get; set; }
        [JsonPropertyName("kind")] public string Kind { get; set; }
        [JsonPropertyName("strength")] public double Strength { get; set; }
        [JsonPropertyName("order")] public double Order { get; set; }
    }

    public class Landmark
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("label")] public string Label { get; set; }
        [JsonPropertyName("camera")] public CameraPreset Camera { get; set; }
    }

    public class CameraPreset
    {
        [JsonPropertyName("target")] public double[] Target { get; set; }
        [JsonPropertyName("dist")] public double Dist { get; set; }
        [JsonPropertyName("yaw")] public double Yaw { get; set; }
        [JsonPropertyName("pitch")] public double Pitch { get; set; }
    }
}
