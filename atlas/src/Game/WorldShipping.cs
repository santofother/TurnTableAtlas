using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class WorldShipping : Node3D
    {
        public sealed class Route
        {
            [JsonPropertyName("from")] public string From { get; set; }
            [JsonPropertyName("to")] public string To { get; set; }
            [JsonPropertyName("points")] public double[][] Points { get; set; }
        }

        sealed record Vessel(Node3D Model, MeshInstance3D Wake, Polyline Path, double Speed, double Phase);

        const double PortStay = 5.0;
        readonly List<Vessel> _vessels = new();
        readonly StandardMaterial3D _paint = Paint();
        WorldMap _map;
        double _time;

        public int RouteCount { get; private set; }
        public int VesselCount => _vessels.Count;

        public void Build(WorldMap map)
        {
            Name = "Shipping";
            _map = map;
            var file = Path.Combine(map.Kw.Directory, "shipping_routes.json");
            var routes = JsonSerializer.Deserialize<Route[]>(File.ReadAllText(file));
            var vesselMesh = BuildVessel();
            var wakeMesh = BuildWake();
            var wakePaint = Paint(transparent: true);
            foreach (var route in routes)
            {
                var from = map.Kw.Settlement(route.From);
                var to = map.Kw.Settlement(route.To);
                if (from == null || to == null || route.Points is not { Length: >= 2 })
                    throw new InvalidDataException($"Invalid shipping route {route.From} to {route.To}");

                var path = new Polyline(Polyline.Chaikin(Polyline.FromArray(route.Points), false));
                if (!IsRouteOnWater(path))
                {
                    GD.PushWarning($"[Atlas] shipping route crosses land: {from.Name} to {to.Name}");
                    continue;
                }

                double speed = 1.45 + RouteCount % 3 * 0.18;
                double leg = path.Length / speed;
                int count = leg > 36 ? 3 : 2;
                for (int i = 0; i < count; i++)
                {
                    var model = new Node3D { Name = $"{route.From}_{route.To}_{i + 1}" };
                    AddChild(model);
                    model.AddChild(Instance(vesselMesh, _paint));
                    var wake = Instance(wakeMesh, wakePaint);
                    model.AddChild(wake);
                    double phase = (i + 0.25 + RouteCount * 0.11) * 2 * (leg + PortStay) / count;
                    _vessels.Add(new Vessel(model, wake, path, speed, phase));
                }
                RouteCount++;
            }
            GD.Print($"[Atlas] shipping: {VesselCount} boats on {RouteCount} routes");
        }

        public void Tick(double delta, float cameraDistance, float night)
        {
            _time += delta;
            _paint.AlbedoColor = Colors.White.Lerp(new Color(0.63f, 0.67f, 0.75f), night);
            foreach (var boat in _vessels)
            {
                var path = boat.Path;
                double travel = path.Length / boat.Speed;
                double leg = travel + PortStay;
                double elapsed = (_time + boat.Phase) % (2 * leg);
                bool returning = elapsed >= leg;
                double seconds = returning ? elapsed - leg : elapsed;
                double progress = Math.Min(seconds * boat.Speed, path.Length);
                double distance = returning ? path.Length - progress : progress;
                var (p, heading) = path.At(distance);
                var forward = path.At(distance + 0.35).Pos - path.At(distance - 0.35).Pos;
                if (forward.Length2D > 1e-6) heading = Math.Atan2(forward.Y, forward.X);
                if (returning) heading += Math.PI;
                float turn = (float)Math.Clamp((seconds - travel) / PortStay, 0, 1);
                heading += Math.PI * Mathf.SmoothStep(0, 1, turn);

                double clearOfBerth = Math.Min(distance, path.Length - distance);
                double lateral = Math.Min(0.24, clearOfBerth * 0.14);
                var offset = new Vec3(Math.Sin(heading) * lateral, -Math.Cos(heading) * lateral, 0);
                var position = p + offset;
                float scale = Math.Clamp(cameraDistance * 0.013f, 0.38f, 4.2f);
                var axis = new Vec3(Math.Cos(heading), Math.Sin(heading), 0);
                while (scale > 0.55f && (!IsWater(position + axis * (0.8 * scale)) || !IsWater(position - axis * (0.8 * scale))))
                    scale *= 0.72f;

                boat.Model.Position = Geo.V(position) + Vector3.Up * 0.07f;
                boat.Model.Rotation = new Vector3(0, (float)heading, 0);
                boat.Model.Scale = Vector3.One * scale;
                boat.Wake.Visible = seconds < travel && clearOfBerth > 1.0 && IsWater(position - axis * (1.65 * scale));
            }
        }

        bool IsRouteOnWater(Polyline path)
        {
            for (double distance = 0; distance < path.Length; distance += 0.15)
                if (!IsWater(path.At(distance).Pos)) return false;
            return IsWater(path.P[^1]);
        }

        bool IsWater(Vec3 p)
        {
            var (u, v) = _map.Kw.XyToUv(p.X, p.Y);
            return u >= 0 && u <= 1 && v >= 0 && v <= 1 && _map.HeightUv(u, v) < 0;
        }

        static StandardMaterial3D Paint(bool transparent = false) => new()
        {
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled,
            VertexColorUseAsAlbedo = true,
            VertexColorIsSrgb = true,
            Transparency = transparent ? BaseMaterial3D.TransparencyEnum.Alpha : BaseMaterial3D.TransparencyEnum.Disabled,
        };

        static MeshInstance3D Instance(Mesh mesh, Material paint) => new()
        {
            Mesh = mesh, MaterialOverride = paint, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };

        static ArrayMesh BuildVessel()
        {
            var mesh = BeginMesh();
            var bow = new Vector3(0.78f, 0.12f, 0);
            var port = new Vector3(0.02f, 0.14f, -0.22f);
            var starboard = new Vector3(0.02f, 0.14f, 0.22f);
            var stern = new Vector3(-0.65f, 0.14f, 0);
            var keel = new Vector3(0, -0.08f, 0);
            var deck = new Color(0.65f, 0.39f, 0.20f);
            var hull = new Color(0.31f, 0.17f, 0.11f);
            Triangle(mesh, bow, port, starboard, deck);
            Triangle(mesh, stern, starboard, port, deck);
            Triangle(mesh, bow, keel, starboard, hull);
            Triangle(mesh, bow, port, keel, hull);
            Triangle(mesh, stern, keel, port, hull);
            Triangle(mesh, stern, starboard, keel, hull);

            var cloth = new Color(1.0f, 0.92f, 0.67f);
            var belly = new Vector3(0.22f, 0.54f, 0);
            var peak = new Vector3(-0.14f, 1.12f, 0);
            Triangle(mesh, peak, belly, new Vector3(-0.10f, 0.25f, -0.30f), cloth);
            Triangle(mesh, belly, peak, new Vector3(-0.10f, 0.25f, 0.30f), new Color(0.91f, 0.74f, 0.46f));
            Triangle(mesh, peak, peak + new Vector3(0, 0.16f, 0), peak + new Vector3(-0.32f, 0.10f, 0), new Color(0.84f, 0.30f, 0.19f));
            return mesh.Commit();
        }

        static ArrayMesh BuildWake()
        {
            var mesh = BeginMesh();
            var water = new Color(0.72f, 0.92f, 0.91f, 0.57f);
            foreach (float side in new[] { -1f, 1f })
                Triangle(mesh, new Vector3(-0.55f, 0, 0.09f * side),
                    new Vector3(-1.65f, 0, 0.49f * side), new Vector3(-1.45f, 0, 0.30f * side), water);
            return mesh.Commit();
        }

        static SurfaceTool BeginMesh()
        {
            var mesh = new SurfaceTool();
            mesh.Begin(Mesh.PrimitiveType.Triangles);
            return mesh;
        }

        static void Triangle(SurfaceTool mesh, Vector3 a, Vector3 b, Vector3 c, Color tint)
        {
            mesh.SetColor(tint);
            mesh.AddVertex(a);
            mesh.AddVertex(b);
            mesh.AddVertex(c);
        }
    }
}
