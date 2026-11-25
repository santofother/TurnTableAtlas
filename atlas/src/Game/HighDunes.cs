// Regional rivers, settlements and camel trains along the Qasr Samir–Karn Ashur caravan corridor.
using System;
using System.Collections.Generic;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class HighDunes : Node3D
    {
        const float VillageRange = 26f, CaravanRange = 9f;
        public HighDunesRegion R { get; private set; }
        public int VillageCount => R.Villages.Count;
        public int TownCount => R.Towns.Count;
        public readonly List<ShaderMaterial> WeatherMaterials = new();
        public readonly List<Label3D> Labels = new();
        Materials _mats;
        MultiMeshInstance3D _camels;
        (double X, double Y)[] _land;
        double[] _landS;
        Func<double, double, float> _ground;

        public void Build(HighDunesRegion region, BasinSite basin, Func<double, double, float> ground, InstanceSpec protos, double buildingScale)
        {
            Name = "HighDunes";
            R = region; _ground = ground;
            ulong t0 = Time.GetTicksMsec();
            BuildRivers();
            if (protos != null)
            {
                _mats = new Materials(null);
                var rec = region.Records((x, y) => ground(x, y), protos.Kinds, buildingScale);
                var spec = new InstanceSpec { Kinds = protos.Kinds, Protos = protos.Protos, Stride = 11, Count = rec.Length / 11 };
                // records come sorted by village; group them by kind for the table
                var rows = Enumerable.Range(0, spec.Count).OrderBy(i => rec[i * 11 + 10]).ToArray();
                var data = new float[rec.Length];
                for (int k = 0; k < rows.Length; k++) Array.Copy(rec, rows[k] * 11, data, k * 11, 11);
                foreach (var (name, id) in protos.Kinds)
                {
                    int first = Array.FindIndex(rows, r => (int)rec[r * 11 + 10] == id);
                    if (first < 0) continue;
                    int count = rows.Count(r => (int)rec[r * 11 + 10] == id);
                    spec.Groups[name] = new[] { first, count };
                }
                var table = new InstanceTable(spec, data);
                var node = new Node3D { Name = "Settlements" };
                AddChild(node);
                Instances.Build(node, table, _mats.Instanced, 93.5, 23.2, (t, i) =>
                {
                    var basis = new Basis(Vector3.Up, t.Rot(i)) * Basis.FromScale(new Vector3(t.W(i), t.H(i), t.D(i)));
                    return new Transform3D(basis, new Vector3(t.X(i), t.Z(i), -t.Y(i)));
                }, tiles: 8, half: 400, shadows: true, rangeAll: VillageRange);
                WeatherMaterials.Add(_mats.Instanced);
            }
            BuildCaravans(basin);
            BuildLabels();
            GD.Print($"[Atlas] High Dunes: {R.Rivers.Count} rivers graded ({string.Join(", ", R.Rivers.Select(r => $"{r.Id} {r.DropM:0} m drop, cut {r.MaxUphillM:0} m at ({r.UphillAt.X:0.0}, {r.UphillAt.Y:0.0})"))}), " +
                     $"{VillageCount} villages, {TownCount} market towns, ~{R.Population / 1000}k people in {Time.GetTicksMsec() - t0} ms");
        }

        // ---------------------------------------------------------------- rivers

        void BuildRivers()
        {
            var water = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/karn_ashur_water.gdshader") };
            WeatherMaterials.Add(water);
            var st = new SurfaceTool();
            st.Begin(Mesh.PrimitiveType.Triangles);
            foreach (var r in R.Rivers.Where(r => !r.Seasonal))
            {
                var pts = r.Pts;
                for (int k = 0; k + 1 < pts.Length; k++)
                {
                    var a = pts[k]; var b = pts[k + 1];
                    double dx = b.X - a.X, dy = b.Y - a.Y, len = Math.Max(1e-9, Math.Sqrt(dx * dx + dy * dy));
                    double w = 0.035 + 0.04 * k / pts.Length;                       // wider downstream
                    double nx = -dy / len * w / 2, ny = dx / len * w / 2;
                    float ya = Math.Max(_ground(a.X, a.Y), (float)R.U(Math.Max(r.BedM[k], 0))) + 0.004f;
                    float yb = Math.Max(_ground(b.X, b.Y), (float)R.U(Math.Max(r.BedM[k + 1], 0))) + 0.004f;
                    var a0 = new Vector3((float)(a.X + nx), ya, -(float)(a.Y + ny)); var a1 = new Vector3((float)(a.X - nx), ya, -(float)(a.Y - ny));
                    var b0 = new Vector3((float)(b.X + nx), yb, -(float)(b.Y + ny)); var b1 = new Vector3((float)(b.X - nx), yb, -(float)(b.Y - ny));
                    st.SetNormal(Vector3.Up);
                    st.AddVertex(a0); st.AddVertex(b0); st.AddVertex(a1);
                    st.AddVertex(a1); st.AddVertex(b0); st.AddVertex(b1);
                }
            }
            AddChild(new MeshInstance3D { Name = "Rivers", Mesh = st.Commit(), MaterialOverride = water, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
                                          VisibilityRangeEnd = 120f, VisibilityRangeEndMargin = 20f });
        }

        // ---------------------------------------------------------------- the grain route

        void BuildCaravans(BasinSite basin)
        {
            // the overland leg: Qasr Samir's harbour up the northern valleys to the basin's freight road
            var road = R.Corridor.Concat(basin.RoadPath.Reverse().Skip(1));
            if (basin.Site.Roads.TryGetValue("north_pass", out var pass))
                road = road.Concat(basin.Path(pass).Skip(1));
            _land = HighDunesRegion.Resample(road.ToArray(), 0.08);
            _landS = new double[_land.Length];
            for (int k = 1; k < _land.Length; k++) _landS[k] = _landS[k - 1] + Math.Sqrt(Math.Pow(_land[k].X - _land[k - 1].X, 2) + Math.Pow(_land[k].Y - _land[k - 1].Y, 2));

            // camel trains walking the corridor (seen close up)
            _mats ??= new Materials(null);
            var camel = Instances.Mesh(Protos.Camel);
            int trains = 16, per = 9;
            var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseCustomData = true, Mesh = camel, InstanceCount = trains * per };
            _camels = new MultiMeshInstance3D { Name = "Caravans", Multimesh = mm, MaterialOverride = _mats.Instanced, VisibilityRangeEnd = CaravanRange,
                                                CastShadow = GeometryInstance3D.ShadowCastingSetting.Off };
            AddChild(_camels);
        }

        static class Protos
        {
            // a camel in the package's unit box (length along x)
            public static readonly ProtoData Camel = new()
            {
                V = new[] { new double[] { -0.5, -0.5, 0.42 }, new double[] { 0.5, -0.5, 0.42 }, new double[] { 0.5, 0.5, 0.42 }, new double[] { -0.5, 0.5, 0.42 },
                            new double[] { -0.5, -0.5, 1 }, new double[] { 0.5, -0.5, 1 }, new double[] { 0.5, 0.5, 1 }, new double[] { -0.5, 0.5, 1 } },
                F = new List<ProtoFace>
                {
                    new() { I = new[] { 0, 1, 5, 4 }, M = "tint", C = new[] { 0.9 } }, new() { I = new[] { 1, 2, 6, 5 }, M = "tint", C = new[] { 0.85 } },
                    new() { I = new[] { 2, 3, 7, 6 }, M = "tint", C = new[] { 0.95 } }, new() { I = new[] { 3, 0, 4, 7 }, M = "tint", C = new[] { 0.88 } },
                    new() { I = new[] { 4, 5, 6, 7 }, M = "tint", C = new[] { 1.05 } },
                },
            };
        }

        void BuildLabels()
        {
            foreach (var t in R.Towns)
            {
                var l = new Label3D
                {
                    Text = t.Label, FontSize = 20, OutlineSize = 9, Modulate = new Color(1f, 0.93f, 0.8f), OutlineModulate = new Color(0.08f, 0.05f, 0.03f, 0.9f),
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, FixedSize = true, PixelSize = 0.0007f, NoDepthTest = true,
                    RenderPriority = 5, OutlineRenderPriority = 4, DoubleSided = true,
                    Position = new Vector3((float)t.X, _ground(t.X, t.Y) + 0.25f, -(float)t.Y), Visible = false,
                };
                AddChild(l);
                Labels.Add(l);
            }
        }

        // ---------------------------------------------------------------- per frame

        double _t;

        public void Tick(double delta, float windowLevel, float night)
        {
            _t += delta;
            _mats?.SetNight(windowLevel, night);
            if (_camels == null || _land == null || !_camels.Visible) return;
            var mm = _camels.Multimesh;
            int trains = 16, per = 9;
            double L = _landS[^1];
            const float camelLen = 0.0009f;
            for (int tr = 0; tr < trains; tr++)
            {
                bool north = tr % 2 == 1;                                          // half come up from the coast, half go back
                double head = ((tr / (double)trains) * L + _t * 0.012) % L;
                for (int c = 0; c < per; c++)
                {
                    double s = head - c * 0.0016;
                    if (s < 0) s += L;
                    double sd = north ? L - s : s;
                    var (x, y, hx, hy) = At(sd);
                    float yaw = Mathf.Atan2(north ? -(float)hy : (float)hy, north ? -(float)hx : (float)hx);
                    var basis = new Basis(Vector3.Up, yaw) * Basis.FromScale(new Vector3(camelLen, camelLen * 0.8f, camelLen * 0.33f));
                    double off = north ? -0.003 : 0.003;
                    var p = new Vector3((float)(x - hy * off), _ground(x, y) + 0.0002f, -(float)(y + hx * off));
                    int i = tr * per + c;
                    mm.SetInstanceTransform(i, new Transform3D(basis, p));
                    mm.SetInstanceCustomData(i, new Color(0.45f, 0.30f, 0.17f, 1f));
                }
            }
        }

        (double X, double Y, double Hx, double Hy) At(double s)
        {
            int k = Array.BinarySearch(_landS, s);
            if (k < 0) k = ~k - 1;
            k = Math.Clamp(k, 0, _land.Length - 2);
            double t = (s - _landS[k]) / Math.Max(1e-9, _landS[k + 1] - _landS[k]);
            var a = _land[k]; var b = _land[k + 1];
            double dx = b.X - a.X, dy = b.Y - a.Y, len = Math.Max(1e-9, Math.Sqrt(dx * dx + dy * dy));
            return (a.X + dx * t, a.Y + dy * t, dx / len, dy / len);
        }
    }
}
