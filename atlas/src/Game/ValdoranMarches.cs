// The pack road runs across the Calderran frontier to the north shore of Corivessa Bay.
// XY is the north-up Known World frame. The eastern branch follows the capital into Ventara.
using System;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class ValdoranMarches : Node3D
    {
        KnownWorldMap _map;
        Texture2D _albedo;
        /// <summary>Farmland plots drawn (FIX(S31): shaded from the map's own colour by marches_fields.gdshader).</summary>
        public int FieldPlots { get; private set; }
        public const string ViewId = "CAM_ValdoranMarches";
        public static KnownWorldMap.View View() => new()
        {
            Id = ViewId, Name = "Valdora · western marches", Target = new[] { 135.0, 166.0, .25 },
            Dist = 34, Yaw = -98, Pitch = 48
        };

        /// <param name="covered">FIX(S31): true where a town miniature stands; the roads and farms stop at its edge.</param>
        /// <param name="mapAlbedo">FIX(S31): the map's colour, which the farmland takes its tones from.</param>
        public void Build(KnownWorldMap map, ReliefSampler ground, Func<double, double, bool> covered = null, Texture2D mapAlbedo = null)
        {
            _map = map; _albedo = mapAlbedo;
            covered ??= (_, _) => false;
            Name = "ValdoranMarches";
            Vector2 Place(string id)
            {
                var uv = map.Settlement(id).Uv;
                var (x, y) = map.UvToXy(uv[0], uv[1]);
                return new Vector2((float)x, (float)y);
            }
            var port = Place("corivessa_port");
            var gate = Place("corivessa_great_gate");
            var junction = new Vector2(132.7f, 162.1f);
            var roads = new Vector2[][]
            {
                new Vector2[] { new(121.3f,163.6f), new(122.1f,163.3f), new(123.5f,163.6f), new(125.4f,163.2f),
                    new(126.1f,163.35f), new(127.2f,163.1f), new(128.5f,162.7f), new(129.2f,162.9f),
                    new(130.1f,162.45f), new(131.2f,162.6f), junction, new(133.3f,161.5f), port },
                new Vector2[] { junction, new(134.7f,163.7f), new(135.2f,165.8f), new(137.3f,167.5f),
                    new(139.4f,168.9f), gate, new(141.9f,172.23f), new(143.8f,172.3f), new(146.4f,172.0f) }
            };
            BuildRoadsideSites(roads[0], roads[1], ground, covered);
            var surface = new SurfaceTool();
            surface.Begin(Mesh.PrimitiveType.Triangles);
            Vector3 OnGround(Vector2 p) => new(p.X, (float)ground.Coarse(p.X, p.Y) + .004f, -p.Y);
            foreach (var path in roads)
            {
                for (int i = 1; i < path.Length; i++)
                {
                    var a = path[i - 1];
                    var b = path[i];
                    var verge = (b - a).Normalized().Orthogonal() * .009f;   // FIX(S31): ~300 m, beside the towns' own streets
                    int steps = Mathf.CeilToInt(a.DistanceTo(b) / .08f);
                    for (int k = 0; k < steps; k++)
                    {
                        var p = a.Lerp(b, (float)k / steps);
                        var q = a.Lerp(b, (float)(k + 1) / steps);
                        if (covered(p.X, p.Y) || covered(q.X, q.Y)) continue;
                        var left = OnGround(p + verge);
                        var right = OnGround(p - verge);
                        var nextLeft = OnGround(q + verge);
                        var nextRight = OnGround(q - verge);
                        surface.AddVertex(left); surface.AddVertex(right); surface.AddVertex(nextLeft);
                        surface.AddVertex(nextLeft); surface.AddVertex(right); surface.AddVertex(nextRight);
                    }
                }
            }
            surface.GenerateNormals();
            AddChild(new MeshInstance3D
            {
                Name = "MarshAndCanyonRoads", Mesh = surface.Commit(),
                MaterialOverride = new StandardMaterial3D { AlbedoColor = new Color(.55f,.47f,.33f), CullMode = BaseMaterial3D.CullModeEnum.Disabled },
                CastShadow = GeometryInstance3D.ShadowCastingSetting.Off, VisibilityRangeEnd = 85
            });
        }

        // Tents on the dry knolls west of the port give way to tiled farmsteads and fields inland.
        // Batch all the roofs, canvas and fields into one mesh at map-table scale.
        void BuildRoadsideSites(Vector2[] marshRoad, Vector2[] canyonRoad, ReliefSampler ground, Func<double, double, bool> covered)
        {
            var rng = new Random(301);
            var mesh = new SurfaceTool();
            mesh.Begin(Mesh.PrimitiveType.Triangles);
            var fields = new SurfaceTool();
            fields.Begin(Mesh.PrimitiveType.Triangles);
            Vector3 Ground(Vector2 p, float lift) => new(p.X, (float)ground.Coarse(p.X, p.Y) + lift, -p.Y);

            void Triangle(Vector3 a, Vector3 b, Vector3 c, Color colour)
            {
                mesh.SetColor(colour);
                mesh.AddVertex(a); mesh.AddVertex(b); mesh.AddVertex(c);
            }
            void Hut(Vector2 p, Vector2 along, float size, bool tent)
            {
                var end = along * size;
                var side = along.Orthogonal() * size * .63f;
                float wall = tent ? .003f : size * .65f;
                var a = Ground(p-end-side, wall);
                var b = Ground(p+end-side, wall);
                var c = Ground(p+end+side, wall);
                var d = Ground(p-end+side, wall);
                var west = Ground(p-end, wall + size * .8f);
                var east = Ground(p+end, wall + size * .8f);
                var roof = tent ? new Color(.69f,.60f,.42f) : new Color(.57f,.34f,.21f);
                Triangle(a, b, east, roof); Triangle(a, east, west, roof);
                Triangle(c, d, west, roof); Triangle(c, west, east, roof);
                var stone = new Color(.75f,.68f,.53f);
                if (tent) return;
                Triangle(a, west, d, stone); Triangle(b, c, east, stone);
                var corners = new[] { a,b,c,d };
                for (int k = 0; k < 4; k++)
                {
                    var v = corners[k]; var w = corners[(k+1)%4];
                    var drop = Vector3.Up * (wall+.012f);
                    Triangle(v, w, v-drop, stone); Triangle(v-drop, w, w-drop, stone);
                }
            }

            for (int i = 1; i < marshRoad.Length - 3; i += 3)
            {
                var axis = (marshRoad[i+1] - marshRoad[i]).Normalized();
                var at = marshRoad[i] + axis.Orthogonal() * .23f;
                for (int k = 0; k < 4; k++)
                    if (!covered(at.X, at.Y)) Hut(at + axis * (.03f * k) + axis.Orthogonal() * (.035f * (k%2)), axis, .01f, true);   // FIX(S31): at the towns' scale
            }
            for (int i = 1; i < canyonRoad.Length; i++)
            {
                var a = canyonRoad[i-1];
                var b = canyonRoad[i];
                var axis = (b-a).Normalized();
                var side = axis.Orthogonal();
                for (int k = 0; k < 22; k++)
                {
                    var p = a.Lerp(b, rng.NextSingle()) + side * ((rng.NextSingle()-.5f)*2.3f);
                    if (ground.Fine(p.X,p.Y) < .035 || ground.Fine(p.X,p.Y) > .65) continue;
                    if (Math.Abs(ground.Coarse(p.X+.12,p.Y) - ground.Coarse(p.X-.12,p.Y)) > .065) continue;
                    if (Geometry2D.GetClosestPointToSegment(p,a,b).DistanceTo(p) < .15f) continue;
                    if (covered(p.X, p.Y)) continue;
                    var end = axis * (.07f + rng.NextSingle()*.10f);
                    var edge = side * (.05f + rng.NextSingle()*.06f);
                    // FIX(S31): the plot follows the relief on a small grid; its seeds pick the crops and the strips
                    var seed = new Color(rng.NextSingle(), rng.NextSingle(), rng.NextSingle(), 1f);
                    const int GU = 8, GV = 6;
                    for (int gu = 0; gu < GU; gu++)
                        for (int gv = 0; gv < GV; gv++)
                        {
                            Vector3 At(int iu, int iv, out Vector2 uv)
                            {
                                uv = new Vector2((float)iu / GU, (float)iv / GV);
                                return Ground(p + end * (2 * uv.X - 1) + edge * (2 * uv.Y - 1), .004f);
                            }
                            var v0 = At(gu, gv, out var t0); var v1 = At(gu + 1, gv, out var t1);
                            var v2 = At(gu + 1, gv + 1, out var t2); var v3 = At(gu, gv + 1, out var t3);
                            foreach (var (pt, uv) in new[] { (v0, t0), (v1, t1), (v2, t2), (v0, t0), (v2, t2), (v3, t3) })
                            {
                                fields.SetColor(seed); fields.SetUV(uv); fields.AddVertex(pt);
                            }
                        }
                    FieldPlots++;
                    if (k%4 == 0)   // FIX(S31): a farmstead of a few houses at the town miniatures' scale
                        for (int f = 0; f < 3; f++)
                            Hut(p + end + edge + axis * (.028f * f) + side * (.02f * (f % 2)), axis, .011f, false);
                }
            }
            if (FieldPlots > 0)
            {
                fields.GenerateNormals();
                var mat = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/marches_fields.gdshader") };
                mat.SetShaderParameter("albedo_tex", _albedo);
                mat.SetShaderParameter("world_min", new Vector2((float)_map.BoundsXy[0], -(float)_map.BoundsXy[3]));
                mat.SetShaderParameter("world_size", new Vector2((float)_map.Width, (float)_map.Depth));
                AddChild(new MeshInstance3D
                {
                    Name = "Farmland", Mesh = fields.Commit(), MaterialOverride = mat, VisibilityRangeEnd = 55,
                    CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
                });
            }
            mesh.GenerateNormals();
            AddChild(new MeshInstance3D
            {
                Name = "CampsAndFields", Mesh = mesh.Commit(), VisibilityRangeEnd = 55,
                MaterialOverride = new StandardMaterial3D { VertexColorUseAsAlbedo = true, CullMode = BaseMaterial3D.CullModeEnum.Disabled },
                CastShadow = GeometryInstance3D.ShadowCastingSetting.Off
            });
        }
    }
}
