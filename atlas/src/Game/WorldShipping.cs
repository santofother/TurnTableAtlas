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

        sealed record Vessel(Node3D Model, MeshInstance3D Wake, Polyline Path, double Speed, double Phase, bool FromOffMap);

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
                var to = map.Kw.Settlement(route.To);
                if (to == null || route.Points is not { Length: >= 2 } || !ValidOrigin(route))
                    throw new InvalidDataException($"Invalid shipping route {route.From} to {route.To}");

                var path = new Polyline(Polyline.Chaikin(Polyline.FromArray(route.Points), false));
                if (!IsRouteOnWater(path))
                {
                    GD.PushWarning($"[Atlas] shipping route crosses land: {route.From} to {to.Name}");
                    continue;
                }

                bool fromOffMap = route.From is "west_edge" or "east_edge";
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
                    _vessels.Add(new Vessel(model, wake, path, speed, phase, fromOffMap));
                }
                RouteCount++;
            }
            GD.Print($"[Atlas] shipping: {VesselCount} boats on {RouteCount} routes");
        }

        bool ValidOrigin(Route route) => route.From switch
        {
            "west_edge" => route.Points[0][0] == _map.Kw.BoundsXy[0],
            "east_edge" => route.Points[0][0] == _map.Kw.BoundsXy[2],
            "river_flame_delta" => true, // Sea berth off the River Flame mouth, north of inland Haven.
            _ => _map.Kw.Settlement(route.From) != null,
        };

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
                // Small map miniatures that stay readable on approach and stop growing at overview zoom.
                float scale = Math.Clamp(cameraDistance * 0.0044f, 0.055f, 0.92f);
                double lateral = Math.Min(0.20 * scale, clearOfBerth * 0.14);
                var offset = new Vec3(Math.Sin(heading) * lateral, -Math.Cos(heading) * lateral, 0);
                var position = p + offset;
                var axis = new Vec3(Math.Cos(heading), Math.Sin(heading), 0);
                if (boat.FromOffMap && distance < 1.1 * scale)
                {
                    boat.Model.Visible = false;
                    continue;
                }
                if (!IsWater(position)) position = p;
                while (scale > 0.002f && (!IsWater(position + axis * (1.1 * scale)) || !IsWater(position - axis * scale)))
                    scale *= 0.72f;

                boat.Model.Visible = true;
                boat.Model.Position = Geo.V(position) + Vector3.Up * 0.003f;
                boat.Model.Rotation = new Vector3(0, (float)heading, 0);
                boat.Model.Scale = Vector3.One * scale;
                boat.Wake.Visible = seconds < travel && clearOfBerth > 1.8 * scale && IsWater(position - axis * (1.85 * scale));
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
            var cedar = new Color(0.42f, 0.23f, 0.13f);
            var deck = new Color(0.76f, 0.52f, 0.27f);
            var red = new Color(0.61f, 0.18f, 0.12f);
            var bronze = new Color(0.90f, 0.65f, 0.34f);
            var sections = new[]   // sternpost, hull stations, and prow (bow points along +X)
            {
                new Vector3(-0.96f, 0.36f, 0f),
                new Vector3(-0.82f, 0.20f, 0.075f),
                new Vector3(-0.61f, 0.145f, 0.128f),
                new Vector3(0.39f, 0.145f, 0.14f),
                new Vector3(0.72f, 0.17f, 0.087f),
                new Vector3(0.90f, 0.23f, 0f),
            };
            for (int i = 1; i < sections.Length; i++)
            {
                var a = sections[i - 1];
                var b = sections[i];
                var aFar = new Vector3(a.X, a.Y, -a.Z);
                var bFar = new Vector3(b.X, b.Y, -b.Z);
                Quad(mesh, a, b, bFar, aFar, deck);
                foreach (float side in new[] { -1f, 1f })
                {
                    var topA = new Vector3(a.X, a.Y, a.Z * side);
                    var topB = new Vector3(b.X, b.Y, b.Z * side);
                    var trimA = topA - Vector3.Up * 0.041f;
                    var trimB = topB - Vector3.Up * 0.041f;
                    var hullA = new Vector3(a.X * 0.91f, -0.03f, a.Z * side * 0.53f);
                    var hullB = new Vector3(b.X * 0.91f, -0.03f, b.Z * side * 0.53f);
                    Quad(mesh, topA, topB, trimB, trimA, red);
                    Quad(mesh, trimA, trimB, hullB, hullA, cedar);
                }
            }
            var ram = new Vector3(1.1f, 0.023f, 0);
            var ramLeft = new Vector3(0.72f, 0.042f, -0.045f);
            var ramRight = new Vector3(0.72f, 0.042f, 0.045f);
            var prow = sections[^1];
            Triangle(mesh, ram, ramLeft, ramRight, bronze);
            Triangle(mesh, ram, ramLeft, prow, bronze);
            Triangle(mesh, ram, prow, ramRight, bronze);

            var tip = new Vector3(0.11f, 0.91f, 0);
            Beam(mesh, new Vector3(0.16f, 0.13f, 0), tip, 0.022f, cedar);
            Beam(mesh, tip + new Vector3(0, -0.09f, -0.30f), tip + new Vector3(0, -0.09f, 0.30f), 0.014f, cedar);
            Triangle(mesh, tip, tip - Vector3.Up * 0.093f, tip - new Vector3(0.23f, 0.05f, 0), red);

            // A transverse square sail with a curved belly and ochre outer panels.
            const int panels = 8;
            for (int i = 0; i < panels; i++)
            {
                float a = i / (float)panels * 2f - 1f;
                float b = (i + 1f) / panels * 2f - 1f;
                var cloth = i == 0 || i == panels - 1 ? bronze : new Color(1f, 0.93f, 0.74f);
                Quad(mesh, SailPoint(a, 0), SailPoint(b, 0), SailPoint(b, 1), SailPoint(a, 1), cloth);
            }

            foreach (float side in new[] { -1f, 1f })
            {
                // Three staggered banks share the hull silhouette while preserving the aft sweep of the blades.
                for (int bank = 0; bank < 3; bank++)
                {
                    for (int i = 0; i < 10; i++)
                    {
                        float x = -0.55f + i * 0.114f + bank * 0.022f;
                        var grip = new Vector3(x, 0.065f + bank * 0.039f, 0.123f * side);
                        var blade = new Vector3(x - 0.16f - bank * 0.019f, 0.012f, (0.29f + bank * 0.042f) * side);
                        var neck = grip.Lerp(blade, 0.78f);
                        Beam(mesh, grip, neck, 0.009f, deck);
                        var width = Vector3.Right * 0.015f;
                        Quad(mesh, neck - width * 0.45f, neck + width * 0.45f, blade + width, blade - width, deck);
                    }
                }
                Beam(mesh, new Vector3(-0.76f, 0.23f, 0.078f * side),
                    new Vector3(-0.92f, 0.012f, 0.19f * side), 0.022f, cedar);
            }
            return mesh.Commit();
        }

        static Vector3 SailPoint(float span, float foot)
        {
            float belly = 1f - span * span;
            return new Vector3(0.11f + foot * (0.06f + belly * 0.25f),
                0.82f - foot * (0.43f + 0.075f * belly), span * (0.285f + foot * 0.038f));
        }

        static void Beam(SurfaceTool mesh, Vector3 a, Vector3 b, float width, Color tint)
        {
            var dir = (b - a).Normalized();
            var side = (Math.Abs(dir.Y) > 0.9f ? Vector3.Right : Vector3.Up).Cross(dir).Normalized() * (width / 2f);
            var top = dir.Cross(side);
            Quad(mesh, a - side, a + side, b + side, b - side, tint);
            Quad(mesh, a - top, a + top, b + top, b - top, tint);
        }

        static ArrayMesh BuildWake()
        {
            var mesh = BeginMesh();
            var water = new Color(0.72f, 0.92f, 0.91f, 0.57f);
            foreach (float side in new[] { -1f, 1f })
                Triangle(mesh, new Vector3(-0.77f, 0, 0.07f * side),
                    new Vector3(-1.85f, 0, 0.35f * side), new Vector3(-1.53f, 0, 0.24f * side), water);
            return mesh.Commit();
        }

        static SurfaceTool BeginMesh()
        {
            var mesh = new SurfaceTool();
            mesh.Begin(Mesh.PrimitiveType.Triangles);
            return mesh;
        }

        static void Quad(SurfaceTool mesh, Vector3 a, Vector3 b, Vector3 c, Vector3 d, Color tint)
        {
            Triangle(mesh, a, b, c, tint);
            Triangle(mesh, a, c, d, tint);
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
