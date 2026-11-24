// A country estate on the Known World (Landric's villa): its hero patch (EstateSite: the plinth's ground and hills
// round it, sunk into the relief like Karn Ashur's) with the package's own city.glb standing on it as a miniature,
// so the map shows the same house, lake and vineyards the city view opens. Lit windows and fires after dark.
using System;
using System.Collections.Generic;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class Estate : Node3D
    {
        const int QuadsPerReliefQuad = 96, CollisionRes = 97;
        const float MiniRange = 16f;
        /// <summary>Meshes and textures are kept between visits to the map (keyed by estate id).</summary>
        static readonly Dictionary<string, (ArrayMesh Ground, float[] Collision, List<(Mesh Mesh, Transform3D T, string Name, Material[] Mats)> Mini, Texture2D Albedo)> Cache = new();

        public EstateSite S { get; private set; }
        public CityManifest M { get; private set; }
        public string ViewId => "CAM_Estate_" + M.Id;
        public int MiniMeshes { get; private set; }
        public readonly List<ShaderMaterial> WeatherMaterials = new();
        Materials _mats;
        ShaderMaterial _ground;

        public static EstateSite MakeSite(CityManifest m, KnownWorldMap kw, ReliefSampler relief)
        {
            if (!m.IsEstate || m.Terrain == null) return null;
            var uv = kw.PinFor(m.WorldMap);
            if (!uv.HasValue) return null;
            var (x, y) = kw.UvToXy(uv.Value.U, uv.Value.V);
            var mini = m.WorldMap.Miniature ?? new MapMiniature();
            return new EstateSite(m.Id, relief, x, y, kw.UnitM, kw.Exaggeration, m.ModelScale, m.Extent[2], m.Terrain, mini.Exaggeration, mini.HillsRadius);
        }

        /// <summary>Orbit preset: the aerial concept's view, from the south-west over the gate.</summary>
        public KnownWorldMap.View View() => new()
        {
            Id = ViewId, Name = M.Name, Target = new[] { S.Cx, S.Cy, S.Base + 0.01 }, Yaw = -115, Pitch = 34, Dist = 0.55,
        };

        public void Build(EstateSite site, CityManifest m, KnownWorldMap kw, Texture2D albedo)
        {
            Name = "Estate_" + m.Id;
            S = site; M = m;
            ulong t0 = Time.GetTicksMsec();
            if (!Cache.TryGetValue(m.Id, out var c))
            {
                c = (MakeGround(), S.SampleMesh(CollisionRes, CollisionRes), LoadMiniature(), LoadTex(m.FilePath("terrain_albedo")));
                Cache[m.Id] = c;
            }
            _ground = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/estate_ground.gdshader") };
            _ground.SetShaderParameter("estate_tex", c.Albedo);
            _ground.SetShaderParameter("albedo_tex", albedo);
            _ground.SetShaderParameter("world_min", new Vector2((float)kw.BoundsXy[0], -(float)kw.BoundsXy[3]));
            _ground.SetShaderParameter("world_size", new Vector2((float)kw.Width, (float)kw.Depth));
            _ground.SetShaderParameter("centre", new Vector2((float)S.Cx, -(float)S.Cy));
            _ground.SetShaderParameter("half_size", (float)S.Half);
            _ground.SetShaderParameter("hills_r", (float)S.HillsR);
            _ground.SetShaderParameter("blend_out", (float)(S.PatchHalf - EstateSite.EdgeBlend));
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

            // the lake: one sheet at the model's z = 0 over the plinth (the land stands above it everywhere else)
            var water = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/karn_ashur_water.gdshader") };
            WeatherMaterials.Add(water);
            float h = (float)S.Half;
            AddChild(new MeshInstance3D
            {
                Name = "Lake", Mesh = new PlaneMesh { Size = new Vector2(2 * h, 2 * h) }, MaterialOverride = water,
                Position = new Vector3((float)S.Cx, (float)S.Base + 0.0004f, -(float)S.Cy), CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            });

            // the miniature: the package's own model at the patch's scale
            _mats = new Materials(null);
            var mini = new Node3D { Name = "Miniature", Position = new Vector3((float)S.Cx, (float)S.Base, -(float)S.Cy), Scale = Vector3.One * (float)S.S };
            AddChild(mini);
            foreach (var (mesh, t, name, mats) in c.Mini)
            {
                var mi = new MeshInstance3D { Name = name, Mesh = mesh, Transform = t, VisibilityRangeEnd = MiniRange, VisibilityRangeEndMargin = MiniRange * 0.25f,
                                              VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Self };
                for (int s = 0; s < mats.Length; s++) mi.SetSurfaceOverrideMaterial(s, _mats.ForGltf(mats[s]?.ResourceName ?? ""));
                mi.CastShadow = name.StartsWith("CAP_V_Flames") ? GeometryInstance3D.ShadowCastingSetting.Off : GeometryInstance3D.ShadowCastingSetting.On;
                mini.AddChild(mi);
                MiniMeshes++;
            }
            WeatherMaterials.Add(_mats.Painted);
            GD.Print($"[Atlas] estate {m.Id}: patch {S.PatchHalf * 2:0.00} units, miniature x{(m.WorldMap.Miniature?.Exaggeration ?? 12):0} ({S.Half * 2:0.000} units across), {MiniMeshes} meshes in {Time.GetTicksMsec() - t0} ms");
        }

        /// <summary>Windows and fires after dark (the same levels the city view uses).</summary>
        public void SetNight(float windowLevel, float lampLevel) => _mats?.SetNight(windowLevel, lampLevel);

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
                    int a = j * nx + i, b = a + 1, c = a + nx, d = c + 1;   // same diagonal as the relief's PlaneMesh
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

        /// <summary>The package's city.glb without its terrain, lake and plinth (the patch draws those).</summary>
        List<(Mesh, Transform3D, string, Material[])> LoadMiniature()
        {
            var list = new List<(Mesh, Transform3D, string, Material[])>();
            var root = CityLoader.LoadGlb(M.FilePath("model"));
            foreach (var mi in CityLoader.AllMeshes(root))
            {
                string n = mi.Name.ToString();
                if (n == "CAP_Terrain" || n == "CAP_Sea" || n == "CAP_Base") continue;
                var mats = Enumerable.Range(0, mi.Mesh.GetSurfaceCount()).Select(s => mi.Mesh.SurfaceGetMaterial(s)).ToArray();
                list.Add((mi.Mesh, CityLoader.LocalToRoot(mi, root), n, mats));
            }
            root.Free();
            return list;
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
