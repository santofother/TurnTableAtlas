// The River Flame valley on the Known World (Atlas.Core.FlameValleyRegion): the red river on the relief, a close-up
// field overlay (plots, feeder canals and palm hedges drawn by flame_fields.gdshader, faded in as the camera comes
// down; the albedo carries the farmland from afar), the farming villages, market towns and bank palms as a
// miniature (Haven's own house prototypes), and the towns' names.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class FlameValley : Node3D
    {
        const float VillageRange = 24f, FieldRange = 9f;
        const double FieldStep = 0.08;
        public FlameValleyRegion R { get; private set; }
        public int VillageCount => R.Villages.Count;
        public int TownCount => R.Towns.Count;
        public int RiverSegments { get; private set; }
        public int FieldQuads { get; private set; }
        public int InstanceCount { get; private set; }
        public readonly List<ShaderMaterial> WeatherMaterials = new();
        public readonly List<Label3D> Labels = new();
        Materials _mats;
        ShaderMaterial _fields;
        double _metresPerUnit = 2682;
        /// <summary>Grain barges down the Flame to the sea, empty ones sailing back up (RiverBarges).</summary>
        public BargeFleet Barges { get; private set; }
        const float BargeRange = 30f;

        public void Build(FlameValleyRegion region, Func<double, double, float> ground, Func<double, double, double> reliefUnits,
                          Func<double, double, bool> inPatch, InstanceSpec protos, double buildingScale)
        {
            Name = "FlameValley";
            R = region;
            ulong t0 = Time.GetTicksMsec();
            if (buildingScale > 0) _metresPerUnit = 1.0 / buildingScale;
            BuildRivers((x, y) => Math.Max(ground(x, y), (float)reliefUnits(x, y)), inPatch);   // on the relief mesh's own surface
            BuildFields(reliefUnits, inPatch);
            if (protos != null)
            {
                _mats = new Materials(null);
                var rec = region.Records((x, y) => ground(x, y), protos.Kinds, buildingScale);
                var spec = new InstanceSpec { Kinds = protos.Kinds, Protos = protos.Protos, Stride = 11, Count = rec.Length / 11 };
                var rows = Enumerable.Range(0, spec.Count).OrderBy(i => rec[i * 11 + 10]).ToArray();
                var data = new float[rec.Length];
                for (int k = 0; k < rows.Length; k++) Array.Copy(rec, rows[k] * 11, data, k * 11, 11);
                foreach (var (name, id) in protos.Kinds)
                {
                    int first = Array.FindIndex(rows, r => (int)rec[r * 11 + 10] == id);
                    if (first < 0) continue;
                    spec.Groups[name] = new[] { first, rows.Count(r => (int)rec[r * 11 + 10] == id) };
                }
                var table = new InstanceTable(spec, data);
                var node = new Node3D { Name = "Settlements" };
                AddChild(node);
                var (count, _) = Instances.Build(node, table, _mats.Instanced, 177.0, 63.2, (t, i) =>
                {
                    var basis = new Basis(Vector3.Up, t.Rot(i)) * Basis.FromScale(new Vector3(t.W(i), t.H(i), t.D(i)));
                    return new Transform3D(basis, new Vector3(t.X(i), t.Z(i), -t.Y(i)));
                }, tiles: 10, half: 400, shadows: true, rangeAll: VillageRange);
                InstanceCount = count;
                WeatherMaterials.Add(_mats.Instanced);
            }
            BuildLabels(ground);
            GD.Print($"[Atlas] River Flame: {R.Reaches.Count} reaches ({RiverSegments} river segments), {FieldQuads} field quads, " +
                     $"{VillageCount} villages, {TownCount} market towns (~{R.Population / 1000}k people), {InstanceCount} instances in {Time.GetTicksMsec() - t0} ms");
        }

        // ---------------------------------------------------------------- the red river

        void BuildRivers(Func<double, double, float> ground, Func<double, double, bool> inPatch)
        {
            var water = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/flame_river.gdshader") };
            var (r, g, b) = R.Water;
            water.SetShaderParameter("silt", new Color((float)r, (float)g, (float)b, 1f));
            water.SetShaderParameter("metres_per_unit", (float)_metresPerUnit);
            WeatherMaterials.Add(water);
            var st = new SurfaceTool();
            st.Begin(Mesh.PrimitiveType.Triangles);
            foreach (var (id, raw, width) in R.Reaches)
            {
                if (id.StartsWith("join")) continue;                     // the patch draws its own river across its ring
                var pts = HighDunesRegion.Resample(raw, 0.03);
                double along = 0;
                for (int k = 0; k + 1 < pts.Length; k++)
                {
                    var a = pts[k]; var bb = pts[k + 1];
                    double dx = bb.X - a.X, dy = bb.Y - a.Y, len = Math.Max(1e-9, Math.Sqrt(dx * dx + dy * dy));
                    float s0 = (float)along, s1 = (float)(along + len), hw = (float)(width / 2);
                    along += len;
                    if (inPatch(a.X, a.Y) || inPatch(bb.X, bb.Y)) continue;
                    double nx = -dy / len * width / 2, ny = dx / len * width / 2;
                    float ya = Math.Max(ground(a.X, a.Y), 0f) + 0.004f, yb = Math.Max(ground(bb.X, bb.Y), 0f) + 0.004f;
                    var a0 = new Vector3((float)(a.X + nx), ya, -(float)(a.Y + ny)); var a1 = new Vector3((float)(a.X - nx), ya, -(float)(a.Y - ny));
                    var b0 = new Vector3((float)(bb.X + nx), yb, -(float)(bb.Y + ny)); var b1 = new Vector3((float)(bb.X - nx), yb, -(float)(bb.Y - ny));
                    st.SetNormal(Vector3.Up);   // UV (across, downstream) and COLOR.r 0 / 1 at the banks: the flow's frame
                    V(a0, 0, hw, s0); V(b0, 0, hw, s1); V(a1, 1, -hw, s0);
                    V(a1, 1, -hw, s0); V(b0, 0, hw, s1); V(b1, 1, -hw, s1);
                    RiverSegments++;
                }
            }
            void V(Vector3 p, float side, float across, float s)
            {
                st.SetColor(new Color(side, 0, 0));
                st.SetUV(new Vector2(across, s));
                st.AddVertex(p);
            }
            AddChild(new MeshInstance3D { Name = "Rivers", Mesh = st.Commit(), MaterialOverride = water, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
                                          VisibilityRangeEnd = 160f, VisibilityRangeEndMargin = 20f });
        }

        // ---------------------------------------------------------------- the fields, close up

        /// <summary>A grid over the farmland, sitting on the relief mesh: COLOR.r is how much is farmland, .gb the
        /// river's direction there (for the plots' lie), .a the distance to the river (units / 2).</summary>
        void BuildFields(Func<double, double, double> reliefUnits, Func<double, double, bool> inPatch)
        {
            double x0 = double.MaxValue, y0 = double.MaxValue, x1 = double.MinValue, y1 = double.MinValue;
            foreach (var (_, pts, _) in R.Reaches)
                foreach (var q in pts) { x0 = Math.Min(x0, q.X); y0 = Math.Min(y0, q.Y); x1 = Math.Max(x1, q.X); y1 = Math.Max(y1, q.Y); }
            x0 -= 2; x1 += 2; y0 = Math.Max(y0, R.D.Belt.StartY - 0.5); y1 += 0.5;
            int nx = (int)((x1 - x0) / FieldStep) + 1, ny = (int)((y1 - y0) / FieldStep) + 1;
            var wgt = new float[nx * ny];
            var dir = new Vector2[nx * ny];
            var dist = new float[nx * ny];
            var hgt = new float[nx * ny];
            Parallel.For(0, ny, j =>
            {
                double y = y1 - j * FieldStep;
                for (int i = 0; i < nx; i++)
                {
                    double x = x0 + i * FieldStep;
                    int o = j * nx + i;
                    if (inPatch(x, y)) continue;
                    double h = reliefUnits(x, y);
                    double hm = h * R.UnitM / R.Exag;
                    var (d, dx, dy, _) = R.Nearest(x, y);
                    if (d > 2.0) continue;
                    wgt[o] = (float)R.FieldWeight(x, y, hm);
                    dir[o] = new Vector2((float)dx, (float)dy);
                    dist[o] = (float)d;
                    hgt[o] = (float)h;
                }
            });
            var verts = new List<Vector3>();
            var cols = new List<Color>();
            var idx = new List<int>();
            var map = new int[nx * ny];
            Array.Fill(map, -1);
            int V(int i, int j)
            {
                int o = j * nx + i;
                if (map[o] >= 0) return map[o];
                map[o] = verts.Count;
                verts.Add(new Vector3((float)(x0 + i * FieldStep), hgt[o] + 0.0025f, -(float)(y1 - j * FieldStep)));
                cols.Add(new Color(wgt[o], dir[o].X * 0.5f + 0.5f, dir[o].Y * 0.5f + 0.5f, Math.Min(1f, dist[o] / 2f)));
                return map[o];
            }
            for (int j = 0; j + 1 < ny; j++)
                for (int i = 0; i + 1 < nx; i++)
                {
                    int a = j * nx + i, b = a + 1, c = a + nx, d = c + 1;
                    if (wgt[a] + wgt[b] + wgt[c] + wgt[d] <= 0.05f) continue;
                    if (hgt[a] <= 0 || hgt[b] <= 0 || hgt[c] <= 0 || hgt[d] <= 0) continue;
                    int va = V(i, j), vb = V(i + 1, j), vc = V(i, j + 1), vd = V(i + 1, j + 1);
                    idx.AddRange(new[] { va, vb, vd, va, vd, vc });
                    FieldQuads++;
                }
            if (FieldQuads == 0) return;
            var arrays = new Godot.Collections.Array();
            arrays.Resize((int)Mesh.ArrayType.Max);
            arrays[(int)Mesh.ArrayType.Vertex] = verts.ToArray();
            arrays[(int)Mesh.ArrayType.Normal] = Enumerable.Repeat(Vector3.Up, verts.Count).ToArray();
            arrays[(int)Mesh.ArrayType.Color] = cols.ToArray();
            arrays[(int)Mesh.ArrayType.Index] = idx.ToArray();
            var mesh = new ArrayMesh();
            mesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, arrays);
            _fields = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/flame_fields.gdshader") };
            _fields.SetShaderParameter("fade_end", FieldRange);
            WeatherMaterials.Add(_fields);
            AddChild(new MeshInstance3D { Name = "Fields", Mesh = mesh, MaterialOverride = _fields, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
                                          VisibilityRangeEnd = FieldRange + 2f });
        }

        void BuildLabels(Func<double, double, float> ground)
        {
            foreach (var t in R.Towns)
            {
                var l = new Label3D
                {
                    Text = t.Label.Replace(" (LORE?)", ""), FontSize = 20, OutlineSize = 9, Modulate = new Color(1f, 0.93f, 0.8f),
                    OutlineModulate = new Color(0.08f, 0.05f, 0.03f, 0.9f), Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, FixedSize = true,
                    PixelSize = 0.0007f, NoDepthTest = true, RenderPriority = 5, OutlineRenderPriority = 4, DoubleSided = true,
                    Position = new Vector3((float)t.X, ground(t.X, t.Y) + 0.25f, -(float)t.Y), Visible = false,
                };
                AddChild(l);
                Labels.Add(l);
            }
        }

        public void Tick(float windowLevel, float night) => _mats?.SetNight(windowLevel, night);

        // ---------------------------------------------------------------- the barges

        /// <summary>Barges along the whole river, through Haven's patch, at the miniature's scale (`metresToUnits`),
        /// riding the water surface `water` gives.</summary>
        public void BuildBarges(BasinSite patch, InstanceSpec protos, double metresToUnits, Func<double, double, float> water)
        {
            if (protos == null || !protos.Protos.ContainsKey("barge_grain")) return;
            _mats ??= new Materials(null);
            if (!WeatherMaterials.Contains(_mats.Instanced)) WeatherMaterials.Add(_mats.Instanced);
            Barges = new BargeFleet();
            AddChild(Barges);
            Barges.Build(R.Barges(patch, metresToUnits), protos, _mats.Instanced, water);
            Barges.Tick(0);
            GD.Print($"[Atlas] River Flame barges: {Barges.Count} on two lanes from the foothills to the sea");
        }

        /// <summary>Per frame: move the barges while the camera is close enough to see them.</summary>
        public void TickBarges(double t, float cameraDist)
        {
            if (Barges == null) return;
            Barges.Visible = cameraDist < BargeRange;
            if (Barges.Visible) Barges.Tick(t);
        }
    }
}
