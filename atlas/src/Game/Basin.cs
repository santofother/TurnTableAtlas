// A metropolis's basin on the Known World (Karn Ashur): the hero patch laid out by Atlas.Core.BasinSite from the
// package itself. The package's own ground (its true heights at the relief's 15x, its painted albedo) on the plinth,
// the ring easing it onto the relief, the rivers, canals and the outlet's water, the package's instance table
// (houses, terraces, caravanserais, trees, camels) re-seated on the map's ground at the miniature's scale, and the
// fires: the First Flame on the western summit, Al-Mirah's lamps, the torches up the pilgrims' climb.
using System;
using System.Collections.Generic;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class Basin : Node3D
    {
        public const string ViewId = "CAM_KarnAshur";
        /// <summary>FIX(haven): each basin has its own view (Karn Ashur keeps its id).</summary>
        public static string ViewIdFor(BasinSite s) => s.Floodplain ? "CAM_" + string.Concat(s.Id.Split('_').Select(w => char.ToUpperInvariant(w[0]) + w[1..])) : ViewId;
        const int QuadsPerReliefQuad = 28, CollisionRes = 129;
        const float CityRange = 34f;

        // meshes and tables take a moment: kept between visits to the map (by package id)
        static readonly Dictionary<string, (ArrayMesh Ground, float[] Collision, Texture2D Albedo, InstanceTable Table)> Cache = new();

        public BasinSite S { get; private set; }
        public CityManifest M { get; private set; }
        public int InstanceCount { get; private set; }
        public int RiverRibbons { get; private set; }
        public Vector3 FlamePosition { get; private set; }
        public readonly List<ShaderMaterial> WeatherMaterials = new();
        Materials _mats;
        ShaderMaterial _ground, _flame;
        StandardMaterial3D _lampMat;
        MultiMeshInstance3D _lamps;
        readonly List<(OmniLight3D L, float E)> _fires = new();

        /// <summary>The package's true heights (terrain_height.png: 16 bit in R/G, row 0 to the north), in metres.</summary>
        public static float[] LoadHeights(CityManifest m, out int n)
        {
            var th = m.TerrainHeight;
            var path = System.IO.Path.Combine(m.Directory, th.File);
            var img = Image.LoadFromFile(path);
            img.Convert(Image.Format.Rgba8);
            n = img.GetWidth();
            var px = img.GetData();
            var a = new float[n * n];
            for (int i = 0; i < a.Length; i++) a[i] = (float)(th.MinM + (px[i * 4] * 256 + px[i * 4 + 1]) / 65535.0 * (th.MaxM - th.MinM));
            return a;
        }

        public static BasinSite MakeSite(CityManifest m, KnownWorldMap kw, ReliefSampler relief)
        {
            if (!m.IsMetropolis || m.Site == null || m.TerrainHeight == null) return null;
            var uv = kw.PinFor(m.WorldMap);
            if (!uv.HasValue) return null;
            var (x, y) = kw.UvToXy(uv.Value.U, uv.Value.V);
            var heights = LoadHeights(m, out int n);
            var mini = m.WorldMap.Miniature ?? new MapMiniature { Exaggeration = 4 };
            return new BasinSite(m.Id, m.Site, heights, n, relief, x, y, kw.UnitM, kw.Exaggeration, mini.Exaggeration, mini.PatchHalf,
                                 m.ModelScale, m.TerrainHeight.ModelVex, m.TerrainHeight.ModelDatumM);
        }

        /// <summary>Orbit preset: the metropolitan aerial's view, from the south-south-east up the basin to the two peaks.</summary>
        public static KnownWorldMap.View View(BasinSite s, string name = null)
        {
            if (s.Floodplain)   // FIX(haven): from the south-west over the red river to the city and its pyramids
            {
                var (hx, hy) = s.KmToWorld(1.5, 0.5);
                return new() { Id = ViewIdFor(s), Name = name ?? s.Id, Target = new[] { hx, hy, s.GroundUnits(hx, hy) }, Yaw = -112, Pitch = 32, Dist = 14.5 };
            }
            var (x, y) = s.KmToWorld(-0.6, 0.4);
            return new() { Id = ViewId, Name = "Karn Ashur", Target = new[] { x, y, s.GroundUnits(x, y) }, Yaw = -84, Pitch = 34, Dist = 18.5 };
        }

        public void Build(BasinSite site, CityManifest m, KnownWorldMap kw, Texture2D albedo, Texture2D reliefHeight)
        {
            Name = "Basin_" + m.Id;
            S = site; M = m;
            ulong t0 = Time.GetTicksMsec();
            if (!Cache.TryGetValue(m.Id, out var c))
            {
                c = (MakeGround(), S.SampleMesh(CollisionRes, CollisionRes), LoadTex(m.FilePath("terrain_albedo")),
                     m.Instances != null ? InstanceTable.Load(m.Directory, m.Instances) : null);
                Cache[m.Id] = c;
            }
            _ground = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/basin_ground.gdshader") };
            _ground.SetShaderParameter("basin_tex", c.Albedo);
            _ground.SetShaderParameter("albedo_tex", albedo);
            _ground.SetShaderParameter("relief_height", reliefHeight);
            _ground.SetShaderParameter("world_min", new Vector2((float)kw.BoundsXy[0], -(float)kw.BoundsXy[3]));
            _ground.SetShaderParameter("world_size", new Vector2((float)kw.Width, (float)kw.Depth));
            _ground.SetShaderParameter("centre", new Vector2((float)S.Cx, -(float)S.Cy));
            _ground.SetShaderParameter("half_size", (float)S.Half);
            _ground.SetShaderParameter("blend_out", (float)(S.PatchHalf - BasinSite.EdgeBlend));
            _ground.SetShaderParameter("metres_per_unit", (float)(S.UnitM / S.Exag));
            AddChild(new MeshInstance3D { Name = "Ground", Mesh = c.Ground, MaterialOverride = _ground });
            WeatherMaterials.Add(_ground);

            var body = new StaticBody3D { Name = "Collision", CollisionLayer = CityLoader.CollisionLayer, CollisionMask = 0 };
            body.AddChild(new CollisionShape3D
            {
                Shape = new HeightMapShape3D { MapWidth = CollisionRes, MapDepth = CollisionRes, MapData = c.Collision },
                Position = new Vector3((float)(S.XMin + S.XMax) / 2, 0, -(float)(S.YMin + S.YMax) / 2),
                Scale = new Vector3((float)(S.XMax - S.XMin) / (CollisionRes - 1), 1, (float)(S.YMax - S.YMin) / (CollisionRes - 1)),
            });
            AddChild(body);

            BuildWater();
            _mats = new Materials(null);
            if (c.Table != null)
            {
                var root = new Node3D { Name = "Miniature" };
                AddChild(root);
                var mk = m.Anchors.TryGetValue("great_market", out var a) ? a : new double[] { 0, 0 };
                var (count, _) = Instances.Build(root, c.Table, _mats.Instanced, mk[0], mk[1], PlaceOnMap, tiles: 6, rangeAll: CityRange,
                                                     skipKinds: new[] { "terrace", "boat" });   // the map's own ground carries the houses
                InstanceCount = count;
                WeatherMaterials.Add(_mats.Instanced);
            }
            BuildFires();
            GD.Print($"[Atlas] basin {m.Id}: patch {S.PatchHalf * 2:0.0} units, plinth {S.Half * 2:0.00} units (x{S.F:0} true size), {InstanceCount} instances, {RiverRibbons} water ribbons in {Time.GetTicksMsec() - t0} ms");
        }

        /// <summary>An instance of the package seated on the map's ground: the miniature's scale across, its own height
        /// above the highest ground under it, its foot down to the lowest (the map's relief is steeper than the model's).</summary>
        Transform3D PlaceOnMap(InstanceTable t, int i)
        {
            double s = S.SModel;
            var (x, y) = S.ModelToWorld(t.X(i), t.Y(i));
            double w = t.W(i) * s, d = t.D(i) * s, h = t.H(i) * s;
            double c = Math.Cos(t.Rot(i)), sn = Math.Sin(t.Rot(i));
            double lo = double.MaxValue, hi = double.MinValue;
            foreach (var (u, v) in new[] { (0.0, 0.0), (0.5, 0.5), (-0.5, 0.5), (0.5, -0.5), (-0.5, -0.5) })
            {
                double g = S.GroundUnits(x + c * u * w - sn * v * d, y + sn * u * w + c * v * d);
                lo = Math.Min(lo, g); hi = Math.Max(hi, g);
            }
            bool tree = t.Kind(i) >= 10 && t.Kind(i) <= 13;   // FIX(haven): silos and boats are kinds 14, 15
            double z0 = tree ? lo + 0.3 * (hi - lo) : lo - 0.0004;
            double hh = tree ? h : h + (hi - lo) + 0.0004;
            var basis = new Basis(Vector3.Up, t.Rot(i)) * Basis.FromScale(new Vector3((float)w, (float)Math.Max(hh, 1e-5), (float)d));
            return new Transform3D(basis, new Vector3((float)x, (float)z0, -(float)y));
        }

        void BuildWater()
        {
            var water = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/karn_ashur_water.gdshader") };
            WeatherMaterials.Add(water);
            if (S.Site.WaterColour is { Length: 3 } wc)   // FIX(haven): the River Flame's silt red
                water.SetShaderParameter("silt", new Color((float)wc[0], (float)wc[1], (float)wc[2], 1f));
            double riverW = S.Site.RiverWidthKm > 0 ? S.Site.RiverWidthKm * S.S : 0;
            var st = new SurfaceTool();
            st.Begin(Mesh.PrimitiveType.Triangles);
            foreach (var (id, pts) in S.Site.Rivers)
            {
                var path = pts.Select(p => (S.KmToWorld(p[0], p[1]), p.Length > 2 ? p[2] : double.NaN)).ToList();
                Ribbon(st, path.Select(q => q.Item1).ToArray(), k => double.IsNaN(path[Math.Min(k, path.Count - 1)].Item2)
                       ? -1 : S.Units(path[Math.Min(k, path.Count - 1)].Item2 + 1.2), riverW > 0 ? riverW : id == "southern_outlet" ? 0.016 : 0.011);
                RiverRibbons++;
            }
            foreach (var (id, pts) in S.Site.Canals)
            {
                Ribbon(st, S.Path(pts), _ => -1, 0.0035);
                RiverRibbons++;
            }
            Ribbon(st, S.OutletPath, _ => -1, S.Floodplain ? FlameValleyRegion.TrunkWidth : 0.036);
            RiverRibbons++;
            if (S.InletPath.Length > 1) { Ribbon(st, S.InletPath, _ => -1, FlameValleyRegion.TrunkWidth); RiverRibbons++; }
            if (S.TributaryPath.Length > 1) { Ribbon(st, S.TributaryPath, _ => -1, 0.042); RiverRibbons++; }
            AddChild(new MeshInstance3D { Name = "Water", Mesh = st.Commit(), MaterialOverride = water, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off });
        }

        /// <summary>A flat strip along a world path; height from `bed(k)` (blend units) or, if negative, the ground.</summary>
        void Ribbon(SurfaceTool st, (double X, double Y)[] raw, Func<int, double> bed, double width)
        {
            var pts = HighDunesRegion.Resample(raw, 0.01);
            // the brief's bed heights are per original vertex: interpolate them by the share of the length
            var bedPer = new double[pts.Length];
            var sRaw = new double[raw.Length];
            for (int k = 1; k < raw.Length; k++) sRaw[k] = sRaw[k - 1] + Math.Sqrt(Math.Pow(raw[k].X - raw[k - 1].X, 2) + Math.Pow(raw[k].Y - raw[k - 1].Y, 2));
            double s = 0;
            for (int k = 0; k < pts.Length; k++)
            {
                if (k > 0) s += Math.Sqrt(Math.Pow(pts[k].X - pts[k - 1].X, 2) + Math.Pow(pts[k].Y - pts[k - 1].Y, 2));
                int j = Math.Clamp(Array.BinarySearch(sRaw, s) is var b && b < 0 ? ~b - 1 : b, 0, raw.Length - 1);
                double b0 = bed(j), b1 = bed(Math.Min(j + 1, raw.Length - 1));
                double t = j + 1 < raw.Length ? Math.Clamp((s - sRaw[j]) / Math.Max(1e-9, sRaw[j + 1] - sRaw[j]), 0, 1) : 0;
                double g = S.MeshUnits(pts[k].X, pts[k].Y);
                bedPer[k] = b0 < 0 || b1 < 0 ? g + 0.0008 : Math.Max(b0 + (b1 - b0) * t, g + 0.0004);
            }
            for (int k = 0; k + 1 < pts.Length; k++)
            {
                var a = pts[k]; var b = pts[k + 1];
                double dx = b.X - a.X, dy = b.Y - a.Y, len = Math.Max(1e-9, Math.Sqrt(dx * dx + dy * dy));
                double nx = -dy / len * width / 2, ny = dx / len * width / 2;
                var a0 = new Vector3((float)(a.X + nx), (float)bedPer[k], -(float)(a.Y + ny));
                var a1 = new Vector3((float)(a.X - nx), (float)bedPer[k], -(float)(a.Y - ny));
                var b0 = new Vector3((float)(b.X + nx), (float)bedPer[k + 1], -(float)(b.Y + ny));
                var b1 = new Vector3((float)(b.X - nx), (float)bedPer[k + 1], -(float)(b.Y - ny));
                st.SetNormal(Vector3.Up);
                st.AddVertex(a0); st.AddVertex(b0); st.AddVertex(a1);
                st.AddVertex(a1); st.AddVertex(b0); st.AddVertex(b1);
            }
        }

        void BuildFires()
        {
            if (!S.Site.Places.ContainsKey("first_flame")) { BuildLamps(); return; }   // FIX(haven): only Karn Ashur's flame
            // the First Flame on the western summit: a flame you can see from the regional view, and its light
            var (fx, fy, fh) = S.Place("first_flame");
            FlamePosition = new Vector3((float)fx, (float)fh, -(float)fy);
            _flame = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/karn_ashur_flame.gdshader") };
            float size = 0.028f;
            AddChild(new MeshInstance3D
            {
                Name = "FirstFlame", Mesh = new QuadMesh { Size = new Vector2(size * 0.55f, size), CenterOffset = new Vector3(0, size / 2, 0) },
                MaterialOverride = _flame, Position = FlamePosition, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            });
            AddFire(FlamePosition + Vector3.Up * 0.02f, 0.9f, 1.2f);
            var (mx, my, mh) = S.Place("al_mirah");
            AddFire(new Vector3((float)mx, (float)mh + 0.01f, -(float)my), 0.25f, 0.4f);
            BuildLamps();
        }

        void BuildLamps()
        {
            // the package's night lights (lamps, torches up the climb, caravanserai gates), seated on the map's ground
            var glow = new GradientTexture2D
            {
                Width = 32, Height = 32, Fill = GradientTexture2D.FillEnum.Radial, FillFrom = new Vector2(0.5f, 0.5f), FillTo = new Vector2(1f, 0.5f),
                Gradient = new Gradient { Colors = new[] { new Color(1, 1, 1, 1), new Color(1, 1, 1, 0) }, Offsets = new[] { 0f, 1f } },
            };
            _lampMat = new StandardMaterial3D
            {
                ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                BlendMode = BaseMaterial3D.BlendModeEnum.Add, BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
                AlbedoTexture = glow, AlbedoColor = new Color(1f, 0.6f, 0.25f, 0f), DisableReceiveShadows = true,
            };
            var lights = M.NightLights;
            var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, Mesh = new QuadMesh { Size = new Vector2(0.006f, 0.006f) }, InstanceCount = lights.Count };
            for (int i = 0; i < lights.Count; i++)
            {
                var (x, y) = S.ModelToWorld(lights[i].Pos[0], lights[i].Pos[1]);
                float k = lights[i].Kind == "torch" ? 1.4f : lights[i].Kind == "lighthouse" ? 4f : 1f;
                mm.SetInstanceTransform(i, new Transform3D(Basis.Identity.Scaled(Vector3.One * k), new Vector3((float)x, (float)S.GroundUnits(x, y) + 0.004f, -(float)y)));
            }
            _lamps = new MultiMeshInstance3D { Name = "Lamps", Multimesh = mm, MaterialOverride = _lampMat, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off, Visible = false };
            _lamps.VisibilityRangeEnd = 60f;
            AddChild(_lamps);
        }

        void AddFire(Vector3 at, float range, float energy)
        {
            var l = new OmniLight3D { Name = "Fire", Position = at, OmniRange = range, LightColor = new Color(1f, 0.62f, 0.3f), LightEnergy = energy, ShadowEnabled = false };
            l.DistanceFadeEnabled = true; l.DistanceFadeBegin = 40f; l.DistanceFadeLength = 12f;
            AddChild(l);
            _fires.Add((l, energy));
        }

        /// <summary>Per frame: windows and lamps after dark, the flame always burning.</summary>
        public void Tick(float windowLevel, float night)
        {
            _mats?.SetNight(windowLevel, night);
            _flame?.SetShaderParameter("strength", 0.65f + 0.7f * night);
            float t = Time.GetTicksMsec() / 1000f;
            for (int i = 0; i < _fires.Count; i++)
            {
                var (l, e) = _fires[i];
                l.LightEnergy = e * (0.35f + 1.6f * night) * (0.88f + 0.12f * Mathf.Sin(t * 9f + i * 2.1f));
            }
            _lamps.Visible = night > 0.02f;
            _lampMat.AlbedoColor = new Color(1f, 0.6f, 0.25f, Math.Min(1f, night * 1.3f));
        }

        /// <summary>Patch height (blend units) under a world point, or null outside the patch.</summary>
        public float? HeightAt(double x, double y) => S.Contains(x, y) ? (float)S.MeshUnits(x, y) : null;

        ArrayMesh MakeGround()
        {
            int nx = (S.I1 - S.I0) * QuadsPerReliefQuad + 1, ny = (S.J1 - S.J0) * QuadsPerReliefQuad + 1;
            var hgt = S.SampleMesh(nx, ny);
            double sx = (S.XMax - S.XMin) / (nx - 1), sy = (S.YMax - S.YMin) / (ny - 1);
            var verts = new Vector3[nx * ny];
            var norms = new Vector3[nx * ny];
            for (int j = 0; j < ny; j++)
                for (int i = 0; i < nx; i++)
                {
                    int k = j * nx + i;
                    verts[k] = new Vector3((float)(S.XMin + i * sx), hgt[k], -(float)(S.YMax - j * sy));
                    float dx = (hgt[j * nx + Math.Min(i + 1, nx - 1)] - hgt[j * nx + Math.Max(i - 1, 0)]) / (float)(2 * sx);
                    float dz = (hgt[Math.Min(j + 1, ny - 1) * nx + i] - hgt[Math.Max(j - 1, 0) * nx + i]) / (float)(2 * sy);
                    norms[k] = new Vector3(-dx, 1, -dz).Normalized();
                }
            var idx = new int[(nx - 1) * (ny - 1) * 6];
            int o = 0;
            for (int j = 0; j + 1 < ny; j++)
                for (int i = 0; i + 1 < nx; i++)
                {
                    int a = j * nx + i, b = a + 1, c = a + nx, d = c + 1;   // the relief PlaneMesh's diagonal
                    idx[o++] = a; idx[o++] = b; idx[o++] = d;
                    idx[o++] = a; idx[o++] = d; idx[o++] = c;
                }
            var arrays = new Godot.Collections.Array();
            arrays.Resize((int)Mesh.ArrayType.Max);
            arrays[(int)Mesh.ArrayType.Vertex] = verts;
            arrays[(int)Mesh.ArrayType.Normal] = norms;
            arrays[(int)Mesh.ArrayType.Index] = idx;
            var mesh = new ArrayMesh();
            mesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, arrays);
            return mesh;
        }

        static Texture2D LoadTex(string path)
        {
            if (!System.IO.File.Exists(path)) return null;
            var img = Image.LoadFromFile(path);
            img.GenerateMipmaps();
            return ImageTexture.CreateFromImage(img);
        }
    }
}
