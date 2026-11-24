// Ambient life: walkers on the street graph (density by hour), idlers in spawn zones, venue seats, ship
// traffic + bobbing, drifting clouds, bath steam, birds, landmark labels. Simulation lives in Atlas.Core;
// this node only draws it (MultiMesh buffers written once per frame).
using System;
using System.Collections.Generic;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    /// <summary>Prop meshes from res://assets/props.glb (generator/figures.py), by name: citizen, robed, seated...</summary>
    public static class Props
    {
        static Dictionary<string, Mesh> _m;
        public static Mesh Get(string name)
        {
            if (_m == null)
            {
                _m = new();
                var root = CityLoader.LoadGlb("res://assets/props.glb");
                foreach (var mi in CityLoader.AllMeshes(root)) _m[mi.Name.ToString().Replace("PROP_", "")] = mi.Mesh;
                root.Free();
            }
            return _m.TryGetValue(name, out var m) ? m : null;
        }

        public static readonly Color[] Palette = new[] {
            (0.86, 0.82, 0.72), (0.74, 0.62, 0.44), (0.62, 0.30, 0.20), (0.36, 0.42, 0.55), (0.55, 0.50, 0.30),
            (0.80, 0.70, 0.48), (0.45, 0.32, 0.25), (0.92, 0.90, 0.86), (0.66, 0.46, 0.52), (0.40, 0.48, 0.36) }
            .Select(c => new Color((float)c.Item1, (float)c.Item2, (float)c.Item3).SrgbToLinear()).ToArray();
        public static readonly Color[] Teams = new[] { (0.78, 0.12, 0.10), (0.15, 0.30, 0.72), (0.18, 0.55, 0.20), (0.95, 0.95, 0.92), (0.85, 0.66, 0.28), (0.45, 0.20, 0.55) }
            .Select(c => new Color((float)c.Item1, (float)c.Item2, (float)c.Item3).SrgbToLinear()).ToArray();
    }

    /// <summary>A MultiMesh written from a float buffer (transform + custom data per instance).</summary>
    public sealed class Swarm
    {
        public readonly MultiMeshInstance3D Node;
        public readonly MultiMesh MM;
        readonly float[] _buf;
        public int Count;
        public readonly int Capacity;

        public Swarm(string name, Mesh mesh, Material mat, int capacity, bool shadows = false)
        {
            Capacity = capacity;
            MM = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseCustomData = true, Mesh = mesh, InstanceCount = capacity, VisibleInstanceCount = 0 };
            Node = new MultiMeshInstance3D { Name = name, Multimesh = MM, MaterialOverride = mat,
                                             CastShadow = shadows ? GeometryInstance3D.ShadowCastingSetting.On : GeometryInstance3D.ShadowCastingSetting.Off };
            Node.CustomAabb = new Aabb(new Vector3(-60, -5, -60), new Vector3(120, 40, 120));
            _buf = new float[capacity * 16];
        }

        public void Begin() => Count = 0;

        public void Add(Vector3 p, float heading, float scale, Color custom)
        {
            if (Count >= Capacity) return;
            float c = Mathf.Cos(heading) * scale, s = Mathf.Sin(heading) * scale;
            int o = Count * 16;
            _buf[o + 0] = c; _buf[o + 1] = 0; _buf[o + 2] = s; _buf[o + 3] = p.X;
            _buf[o + 4] = 0; _buf[o + 5] = scale; _buf[o + 6] = 0; _buf[o + 7] = p.Y;
            _buf[o + 8] = -s; _buf[o + 9] = 0; _buf[o + 10] = c; _buf[o + 11] = p.Z;
            _buf[o + 12] = custom.R; _buf[o + 13] = custom.G; _buf[o + 14] = custom.B; _buf[o + 15] = custom.A;
            Count++;
        }

        public void End()
        {
            MM.Buffer = _buf;
            MM.VisibleInstanceCount = Count;
        }
    }

    /// <summary>People standing on fixed points (spawn zone / seats), shown in random order up to a fill level.</summary>
    public sealed class PointCrowd
    {
        public readonly Swarm S;
        public readonly ShaderMaterial Mat;
        public double Fill, Excitement;
        public PointCrowd(string name, Mesh mesh, ShaderMaterial baseMat, IEnumerable<double[]> points, Vector3? faceCenter, int seed)
        {
            var rng = new Random(seed);
            var pts = points.Select(p => Geo.V(p)).OrderBy(_ => rng.Next()).ToList();
            Mat = (ShaderMaterial)baseMat.Duplicate();
            S = new Swarm(name, mesh, Mat, pts.Count);
            S.Begin();
            foreach (var p in pts)
            {
                float h = faceCenter.HasValue ? Mathf.Atan2(-(faceCenter.Value.Z - p.Z), faceCenter.Value.X - p.X) : (float)(rng.NextDouble() * Math.Tau);
                S.Add(p, h, 0.92f + 0.16f * (float)rng.NextDouble(), WithBob(Props.Palette[rng.Next(Props.Palette.Length)] * (0.85f + 0.3f * (float)rng.NextDouble()), 1));
            }
            S.End();
            SetFill(0);
            SetExcitement(0);
        }
        static Color WithBob(Color c, float b) => new(c.R, c.G, c.B, b);
        public void SetFill(double f) { Fill = Math.Clamp(f, 0, 1); S.MM.VisibleInstanceCount = (int)Math.Round(S.Capacity * Fill); }
        public void SetExcitement(double e) { Excitement = e; Mat.SetShaderParameter("bob", (float)(0.012 * e)); }
    }

    public partial class Life : Node3D
    {
        CityView _v;
        CityManifest _m;
        public Crowd Crowd { get; private set; }
        public ShipTraffic Traffic { get; private set; }
        Swarm[] _walk;
        public readonly Dictionary<string, PointCrowd> Zones = new();
        public readonly Dictionary<string, PointCrowd> Seats = new();
        public readonly Dictionary<string, double> ZoneOverride = new();
        readonly Dictionary<int, MeshInstance3D> _ships = new();
        readonly Stack<MeshInstance3D> _pool = new();
        readonly List<(Node3D N, Transform3D T, float Ph, bool Small)> _staticShips = new();
        readonly List<(Node3D N, Vector3 V)> _clouds = new();
        Node3D _peopleRoot, _shipsRoot, _cloudsRoot, _ambientRoot, _labelsRoot;
        Swarm _birds;
        double _hour = 12, _t;
        public double TimeScale = 1.0;

        public void Build(CityView v)
        {
            _v = v; _m = v.M;
            _peopleRoot = Add("People"); _shipsRoot = Add("Ships"); _cloudsRoot = Add("Clouds"); _ambientRoot = Add("SteamBirds"); _labelsRoot = Add("Labels");
            _labelsRoot.Visible = false;
            var g = new StreetGraph(_m.StreetGraph);
            Crowd = new Crowd(g, Math.Min(1400, g.Nodes.Length / 2 + 200), 1);
            var fig = v.City.Mats.Figure;
            _walk = new[] { new Swarm("Walkers_citizen", Props.Get("citizen"), fig, 2400), new Swarm("Walkers_robed", Props.Get("robed"), fig, 2400) };
            foreach (var s in _walk) { _peopleRoot.AddChild(s.Node); s.Node.VisibilityRangeEnd = 140; }
            int seed = 10;
            foreach (var z in _m.SpawnZones.Where(z => z.Points.Length > 0))
            {
                var pc = new PointCrowd("Zone_" + z.Id, Props.Get(seed % 2 == 0 ? "citizen" : "robed"), fig, z.Points, null, seed++);
                Zones[z.Id] = pc;
                _peopleRoot.AddChild(pc.S.Node);
            }
            foreach (var ven in _m.Venues)
            {
                var c = Geo.V(new[] { ven.Center[0], ven.Center[1], 0.0 });
                var pc = new PointCrowd("Seats_" + ven.Id, Props.Get("seated"), fig, ven.Seats, c, seed++);
                Seats[ven.Id] = pc;
                pc.SetFill(0.12);
                _peopleRoot.AddChild(pc.S.Node);
            }
            Traffic = new ShipTraffic(_m, 7);
            foreach (var mi in v.City.ByName.Values.Where(n => n.Name.ToString().StartsWith("CAP_Ship_")))
                _staticShips.Add((mi, mi.Transform, (float)GD.RandRange(0, 100), mi.Name.ToString().Contains("boat") || mi.Name.ToString().Contains("fisher")));
            BuildSteam();
            BuildBirds();
            BuildLabels();
        }

        Node3D Add(string name) { var n = new Node3D { Name = name }; AddChild(n); return n; }

        public IEnumerable<(string, Func<bool>, Action<bool>)> Layers()
        {
            yield return ("People", () => _peopleRoot.Visible, b => _peopleRoot.Visible = b);
            yield return ("Ships", () => _shipsRoot.Visible, b => _shipsRoot.Visible = b);
            yield return ("Clouds", () => _v.Weather?.Clouds.Visible ?? false, b => { if (_v.Weather != null) _v.Weather.Clouds.Visible = b; });
            yield return ("Night lights", () => _v.Lights.Visible, b => _v.Lights.Visible = b);
            yield return ("Steam and birds", () => _ambientRoot.Visible, b => _ambientRoot.Visible = b);
            yield return ("Labels", () => _labelsRoot.Visible, b => _labelsRoot.Visible = b);
        }

        public void SetHour(double h) => _hour = h;

        public override void _Process(double delta)
        {
            double dt = delta * TimeScale;
            _t += delta;
            double dens = Crowd.DensityAt(_hour);
            if (_peopleRoot.Visible)
            {
                Crowd.Step(dt, dens);
                foreach (var s in _walk) s.Begin();
                for (int i = 0; i < Crowd.W.Count; i++)
                {
                    var w = Crowd.W[i];
                    if (!w.Active) continue;
                    var (p, h) = Crowd.Pose(w);
                    var pal = Props.Palette[(i * 7 + w.Kind) % Props.Palette.Length];
                    _walk[w.Kind].Add(Geo.V(p), (float)h, 1f, new Color(pal.R, pal.G, pal.B, 1f));
                }
                foreach (var s in _walk) s.End();
                foreach (var (id, z) in Zones)
                {
                    var zd = _m.SpawnZones.First(x => x.Id == id).Density;
                    z.SetFill(ZoneOverride.TryGetValue(id, out var o) ? o : Math.Min(1, dens * zd));
                }
            }
            Traffic.Step(dt);
            UpdateShips();
            BobStaticShips();
            UpdateBirds();
        }

        void UpdateShips()
        {
            var alive = new HashSet<int>();
            float t = (float)_t;
            foreach (var s in Traffic.Ships)
            {
                if (!s.Visible) continue;
                if (!_v.City.ShipMeshes.TryGetValue(s.Kind, out var mesh)) continue;
                alive.Add(s.Id);
                if (!_ships.TryGetValue(s.Id, out var mi))
                {
                    mi = _pool.Count > 0 ? _pool.Pop() : new MeshInstance3D();
                    mi.Mesh = mesh;
                    for (int k = 0; k < mesh.GetSurfaceCount(); k++) mi.SetSurfaceOverrideMaterial(k, _v.City.Mats.Painted);
                    if (mi.GetParent() == null) _shipsRoot.AddChild(mi);
                    mi.Visible = true;
                    _ships[s.Id] = mi;
                }
                var p = Geo.V(s.Pos);
                p.Y = 0.012f * Mathf.Sin(t * 1.3f + s.Id);
                var basis = new Basis(Vector3.Up, (float)s.Heading) * new Basis(Vector3.Right, 0.025f * Mathf.Sin(t * 0.9f + s.Id * 2f));
                mi.Transform = new Transform3D(basis.Scaled(Vector3.One * (float)s.Scale), p);
            }
            foreach (var id in _ships.Keys.Where(k => !alive.Contains(k)).ToList())
            {
                var mi = _ships[id];
                mi.Visible = false;
                _pool.Push(mi);
                _ships.Remove(id);
            }
        }

        void BobStaticShips()
        {
            float t = (float)_t;
            foreach (var (n, tr, ph, small) in _staticShips)
            {
                float amp = small ? 1.4f : 1f;
                var b = tr.Basis * new Basis(Vector3.Right, 0.03f * amp * Mathf.Sin(t * 0.8f + ph)) * new Basis(Vector3.Forward, 0.015f * amp * Mathf.Sin(t * 0.6f + ph * 1.7f));
                n.Transform = new Transform3D(b, tr.Origin + Vector3.Up * 0.014f * amp * Mathf.Sin(t * 1.1f + ph));
            }
        }

        void BuildClouds()
        {
            var rng = new Random(4);
            var wind = new Vector3(1f, 0, -0.35f).Normalized() * 0.5f;
            for (int i = 0; i < 10; i++)
            {
                var c = new Node3D { Name = "Cloud" + i, Position = new Vector3((float)(rng.NextDouble() * 120 - 60), (float)(15 + rng.NextDouble() * 6), (float)(rng.NextDouble() * 120 - 60)) };
                int n = 5 + rng.Next(4);
                for (int k = 0; k < n; k++)
                {
                    float r = (float)(1.4 + rng.NextDouble() * 1.6);
                    c.AddChild(new MeshInstance3D { Mesh = new SphereMesh { Radius = r, Height = r * 1.5f, RadialSegments = 12, Rings = 6 }, MaterialOverride = _v.City.Mats.Cloud,
                                                    Position = new Vector3((float)(rng.NextDouble() * 9 - 4.5), (float)(rng.NextDouble() * 1.2 - 0.3), (float)(rng.NextDouble() * 4.4 - 2.2)),
                                                    CastShadow = GeometryInstance3D.ShadowCastingSetting.On });
                }
                _cloudsRoot.AddChild(c);
                _clouds.Add((c, wind * (float)(0.8 + 0.4 * rng.NextDouble())));
            }
        }

        void DriftClouds(float dt)
        {
            foreach (var (n, v) in _clouds)
            {
                var p = n.Position + v * dt * (float)Math.Max(1.0, Math.Min(20.0, Math.Abs(_v.Tod.Speed) * 60));
                if (p.X > 70) p.X -= 140; if (p.X < -70) p.X += 140;
                if (p.Z > 70) p.Z -= 140; if (p.Z < -70) p.Z += 140;
                n.Position = p;
            }
        }

        void BuildSteam()
        {
            foreach (var vent in _m.SteamVents)
            {
                var pm = new ParticleProcessMaterial { Direction = Vector3.Up, Spread = 12f, InitialVelocityMin = 0.12f, InitialVelocityMax = 0.25f,
                                                       Gravity = new Vector3(0.05f, 0.03f, 0f), ScaleMin = 0.5f, ScaleMax = 1.0f,
                                                       EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Sphere, EmissionSphereRadius = 0.25f };
                var curve = new Curve(); curve.AddPoint(new Vector2(0, 0.3f)); curve.AddPoint(new Vector2(1, 1.6f));
                pm.ScaleCurve = new CurveTexture { Curve = curve };
                var grad = new Gradient(); grad.SetColor(0, new Color(1, 1, 1, 0.0f)); grad.AddPoint(0.15f, new Color(1, 1, 1, 0.45f)); grad.SetColor(grad.GetPointCount() - 1, new Color(1, 1, 1, 0f));
                pm.ColorRamp = new GradientTexture1D { Gradient = grad };
                var mat = new StandardMaterial3D { BillboardMode = BaseMaterial3D.BillboardModeEnum.Particles, Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                                                   ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, VertexColorUseAsAlbedo = true, AlbedoColor = new Color(0.95f, 0.93f, 0.9f),
                                                   AlbedoTexture = SoftDot() };
                var gp = new GpuParticles3D { Amount = 18, Lifetime = 6.0, ProcessMaterial = pm, DrawPass1 = new QuadMesh { Size = Vector2.One * 0.9f, Material = mat },
                                              Position = Geo.V(vent), CastShadow = GeometryInstance3D.ShadowCastingSetting.Off, Preprocess = 6 };
                _ambientRoot.AddChild(gp);
            }
        }

        static ImageTexture _dot;
        static ImageTexture SoftDot()
        {
            if (_dot != null) return _dot;
            var img = Image.CreateEmpty(32, 32, false, Image.Format.Rgba8);
            for (int y = 0; y < 32; y++) for (int x = 0; x < 32; x++)
            {
                float d = new Vector2(x - 15.5f, y - 15.5f).Length() / 15.5f;
                img.SetPixel(x, y, new Color(1, 1, 1, Mathf.Clamp(1 - d, 0, 1) * Mathf.Clamp(1 - d, 0, 1)));
            }
            return _dot = ImageTexture.CreateFromImage(img);
        }

        void BuildBirds()
        {
            var st = new SurfaceTool();
            st.Begin(Mesh.PrimitiveType.Triangles);
            foreach (var s in new[] { -1f, 1f })
            {
                st.AddVertex(new Vector3(0.05f, 0, 0)); st.AddVertex(new Vector3(-0.03f, 0.03f, s * 0.12f)); st.AddVertex(new Vector3(-0.04f, 0, 0));
            }
            var mesh = st.Commit();
            var mat = new StandardMaterial3D { AlbedoColor = new Color(0.12f, 0.1f, 0.1f), CullMode = BaseMaterial3D.CullModeEnum.Disabled };
            _birds = new Swarm("Birds", mesh, mat, 40);
            _ambientRoot.AddChild(_birds.Node);
        }

        void UpdateBirds()
        {
            float t = (float)_t;
            _birds.Begin();
            if (_v.Tod.Daylight > 0.3)
                for (int f = 0; f < 3; f++)
                {
                    var c = new Vector3(-20 + f * 22, 7 + f, -5 - f * 9);
                    for (int i = 0; i < 12; i++)
                    {
                        float a = t * (0.25f + 0.04f * f) + i * 0.35f + f;
                        float r = 6f + 1.5f * Mathf.Sin(i * 1.7f + t * 0.3f);
                        var p = c + new Vector3(Mathf.Cos(a) * r, 0.6f * Mathf.Sin(t * 0.7f + i), Mathf.Sin(a) * r);
                        float flap = 0.6f + 0.4f * Mathf.Abs(Mathf.Sin(t * 9f + i));
                        _birds.Add(p, -a - Mathf.Pi / 2, flap * 1.6f, Colors.Black);
                    }
                }
            _birds.End();
        }

        void BuildLabels()
        {
            foreach (var lm in _m.Landmarks.Where(l => l.Id != "overview"))
                _labelsRoot.AddChild(new Label3D { Text = lm.Label, Position = Geo.V(lm.Camera.Target) + Vector3.Up * 3.2f, Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
                                                   FontSize = 48, PixelSize = 0.02f, OutlineSize = 10, NoDepthTest = true, Modulate = new Color(1f, 0.94f, 0.8f) });
        }
    }
}
