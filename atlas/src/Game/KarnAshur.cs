// Karn Ashur on the Known World (card W5), as in briefs/karn_ashur/concept_valley.webp: the hero patch (the basin's own
// ground, which replaces the relief round the settlement; WorldMap sinks the relief's vertices under it) and the city
// miniature, both laid out by Atlas.Core.KarnAshurSite. Sizes are blend units; heights are the relief's (15x).
using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class KarnAshur : Node3D
    {
        public const string ViewId = "CAM_KarnAshur";
        const int QuadsPerReliefQuad = 32, HeightRes = 1024, LayoutRes = 2048, CollisionRes = 121;
        const float Sink = 0.003f, CityRange = 30f;

        // the patch's meshes and textures take a second to make: kept between visits to the map
        static KarnAshurSite _builtFor;
        static ArrayMesh _groundMesh;
        static ImageTexture _heightTex, _layoutTex;
        static float[] _collision;

        public KarnAshurSite S { get; private set; }
        /// <summary>Materials that take cloud shadows and wet ground (WeatherView sets them).</summary>
        public readonly List<ShaderMaterial> WeatherMaterials = new();
        public int FlameCount => _flames.Count;
        public int FallCount { get; private set; }

        ShaderMaterial _ground, _stone, _houses, _water, _fall, _mist, _flame;
        StandardMaterial3D _torchMat;
        MultiMeshInstance3D _torches;
        readonly List<MeshInstance3D> _flames = new();
        readonly List<(OmniLight3D L, float E)> _lights = new();

        // ---------------------------------------------------------------- helpers

        public static KarnAshurSite MakeSite(KnownWorldMap kw, ReliefSampler relief)
        {
            var s = kw.Settlement(KarnAshurSite.SettlementId);
            if (s == null) return null;
            var (x, y) = kw.UvToXy(s.Uv[0], s.Uv[1]);
            return new KarnAshurSite(relief, x, y, kw.UnitM, kw.Exaggeration);
        }

        /// <summary>Orbit preset looking north up the valley from the south rim, the concept's view.</summary>
        public static KnownWorldMap.View View(KarnAshurSite s) => new()
        {
            Id = ViewId, Name = "Karn Ashur",
            Target = new[] { s.Cx - 0.08, s.Cy + 0.12, s.Units(KarnAshurSite.FloorM) }, Yaw = -100, Pitch = 36, Dist = 3.0,
        };

        Vector3 W(double lx, double ly, double units) => new((float)(S.Cx + lx), (float)units, -(float)(S.Cy + ly));
        float G(double lx, double ly) => (float)S.Units(S.GroundM(lx, ly));
        float U(double metres) => (float)S.Units(metres);
        static Color Lin(float r, float g, float b) => new Color(r, g, b).SrgbToLinear();

        // ---------------------------------------------------------------- build

        public void Build(KarnAshurSite site, KnownWorldMap kw, Texture2D albedo)
        {
            Name = "KarnAshur";
            S = site;
            ulong t0 = Time.GetTicksMsec();
            if (_builtFor != site) MakeGround();
            _builtFor = site;
            BuildGround(kw, albedo);
            BuildWater();
            var st = new SurfaceTool();
            st.Begin(Mesh.PrimitiveType.Triangles);
            BuildWalls(st);
            BuildTemples(st);
            BuildAqueducts(st);
            BuildRoad(st);
            _stone = Mat("karn_ashur_stone");
            AddChild(City(new MeshInstance3D { Name = "Stone", Mesh = st.Commit(), MaterialOverride = _stone }));
            BuildHouses();
            BuildTrees();
            WeatherMaterials.AddRange(new[] { _ground, _stone, _houses, _water });
            GD.Print($"[Atlas] Karn Ashur: {S.Buildings.Count} buildings, {S.Trees.Count} trees, {S.Falls.Count} falls, {_flames.Count} fires in {Time.GetTicksMsec() - t0} ms");
        }

        static ShaderMaterial Mat(string shader) => new() { Shader = ResourceLoader.Load<Shader>($"res://shaders/{shader}.gdshader") };

        static GeometryInstance3D City(GeometryInstance3D g, float range = CityRange)
        {
            g.VisibilityRangeEnd = range;
            g.VisibilityRangeEndMargin = range * 0.2f;
            g.VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Self;
            return g;
        }

        void MakeGround()
        {
            int nx = (S.I1 - S.I0) * QuadsPerReliefQuad + 1, ny = (S.J1 - S.J0) * QuadsPerReliefQuad + 1;
            var h = S.SampleUnits(nx, ny, true, true);
            double sx = (S.XMax - S.XMin) / (nx - 1), sy = (S.YMax - S.YMin) / (ny - 1);
            var verts = new Vector3[nx * ny];
            var norms = new Vector3[nx * ny];
            for (int j = 0; j < ny; j++)
                for (int i = 0; i < nx; i++)
                {
                    int k = j * nx + i;
                    verts[k] = new Vector3((float)(S.XMin + i * sx), h[k], -(float)(S.YMax - j * sy));
                    float dx = (h[j * nx + Math.Min(i + 1, nx - 1)] - h[j * nx + Math.Max(i - 1, 0)]) / (float)(2 * sx);
                    float dz = (h[Math.Min(j + 1, ny - 1) * nx + i] - h[Math.Max(j - 1, 0) * nx + i]) / (float)(2 * sy);
                    norms[k] = new Vector3(-dx, 1, -dz).Normalized();
                }
            var idx = new int[(nx - 1) * (ny - 1) * 6];
            int o = 0;
            for (int j = 0; j + 1 < ny; j++)
                for (int i = 0; i + 1 < nx; i++)
                {
                    int a = j * nx + i, b = a + 1, c = a + nx, d = c + 1;   // a north-west, d south-east
                    idx[o++] = a; idx[o++] = b; idx[o++] = d;
                    idx[o++] = a; idx[o++] = d; idx[o++] = c;
                }
            var arrays = new Godot.Collections.Array();
            arrays.Resize((int)Mesh.ArrayType.Max);
            arrays[(int)Mesh.ArrayType.Vertex] = verts;
            arrays[(int)Mesh.ArrayType.Normal] = norms;
            arrays[(int)Mesh.ArrayType.Index] = idx;
            _groundMesh = new ArrayMesh();
            _groundMesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, arrays);

            var ht = S.SampleUnits(HeightRes, HeightRes, false, false);
            _heightTex = ImageTexture.CreateFromImage(Image.CreateFromData(HeightRes, HeightRes, false, Image.Format.Rf, MemoryMarshal.AsBytes(ht.AsSpan()).ToArray()));
            var lay = Image.CreateFromData(LayoutRes, LayoutRes, false, Image.Format.Rgba8, S.PaintLayout(LayoutRes));
            lay.GenerateMipmaps();
            _layoutTex = ImageTexture.CreateFromImage(lay);
            _collision = S.SampleUnits(CollisionRes, CollisionRes, true, true);
        }

        void BuildGround(KnownWorldMap kw, Texture2D albedo)
        {
            _ground = Mat("karn_ashur_ground");
            _ground.SetShaderParameter("height_tex", _heightTex);
            _ground.SetShaderParameter("layout_lin", _layoutTex);
            _ground.SetShaderParameter("layout_near", _layoutTex);
            _ground.SetShaderParameter("albedo_tex", albedo);
            _ground.SetShaderParameter("patch_min", new Vector2((float)S.XMin, -(float)S.YMax));
            _ground.SetShaderParameter("patch_size", new Vector2((float)(S.XMax - S.XMin), (float)(S.YMax - S.YMin)));
            _ground.SetShaderParameter("world_min", new Vector2((float)kw.BoundsXy[0], -(float)kw.BoundsXy[3]));
            _ground.SetShaderParameter("world_size", new Vector2((float)kw.Width, (float)kw.Depth));
            _ground.SetShaderParameter("centre", new Vector2((float)S.Cx, -(float)S.Cy));
            _ground.SetShaderParameter("fine_half", (float)KarnAshurSite.FineHalf);
            _ground.SetShaderParameter("texel", new Vector2(1f / HeightRes, 1f / HeightRes));
            _ground.SetShaderParameter("metres_per_unit", (float)(S.UnitM / S.Exag));
            _ground.SetShaderParameter("floor_m", (float)KarnAshurSite.FloorM);
            _ground.SetShaderParameter("blend_in", (float)KarnAshurSite.AlbedoIn);
            _ground.SetShaderParameter("blend_out", (float)KarnAshurSite.AlbedoOut);
            AddChild(new MeshInstance3D { Name = "Ground", Mesh = _groundMesh, MaterialOverride = _ground });

            // collision for the camera and double-click focus, finer than the map's (WorldMap clears the map's under it)
            var body = new StaticBody3D { Name = "Collision", CollisionLayer = CityLoader.CollisionLayer, CollisionMask = 0 };
            body.AddChild(new CollisionShape3D
            {
                Shape = new HeightMapShape3D { MapWidth = CollisionRes, MapDepth = CollisionRes, MapData = _collision },
                Position = new Vector3((float)(S.XMin + S.XMax) / 2, 0, -(float)(S.YMin + S.YMax) / 2),
                Scale = new Vector3((float)(S.XMax - S.XMin) / (CollisionRes - 1), 1, (float)(S.YMax - S.YMin) / (CollisionRes - 1)),
            });
            AddChild(body);
        }

        /// <summary>Patch height (blend units) under a world point, or null outside the patch.</summary>
        public float? HeightAt(double x, double y) => S.Contains(x, y) ? (float)S.MeshUnits(x, y) : null;

        // ---------------------------------------------------------------- water

        void BuildWater()
        {
            _water = Mat("karn_ashur_water");
            var st = new SurfaceTool();
            st.Begin(Mesh.PrimitiveType.Triangles);
            float y = U(KarnAshurSite.WaterM);
            const int n = 256;
            for (int i = 0; i < n; i++)
            {
                double a = -Math.PI + 2 * Math.PI * i / n, b = -Math.PI + 2 * Math.PI * (i + 1) / n;
                double ra = S.Shore(a) + 0.006, rb = S.Shore(b) + 0.006;
                st.SetNormal(Vector3.Up);
                st.AddVertex(W(0, 0, y));
                st.AddVertex(W(rb * Math.Cos(b), rb * Math.Sin(b), y));
                st.AddVertex(W(ra * Math.Cos(a), ra * Math.Sin(a), y));
            }
            AddChild(new MeshInstance3D { Name = "Lake", Mesh = st.Commit(), MaterialOverride = _water, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off });

            // waterfalls: ribbons down the cliffs, spray at the foot
            _fall = Mat("karn_ashur_fall");
            _mist = Mat("karn_ashur_fall");
            _mist.SetShaderParameter("mist", true);
            var fs = new SurfaceTool();
            fs.Begin(Mesh.PrimitiveType.Triangles);
            foreach (var f in S.Falls)
            {
                double c = Math.Cos(f.Theta), s = Math.Sin(f.Theta);
                const int m = 32;
                var left = new Vector3[m + 1]; var right = new Vector3[m + 1];
                for (int k = 0; k <= m; k++)
                {
                    double r = f.TopR + (f.FootR - f.TopR) * k / m - 0.0035, half = f.Width * (0.42 + 0.58 * k / m) / 2;
                    double lx = r * c, ly = r * s;
                    float hy = G(lx, ly) + 0.002f;
                    left[k] = W(lx - s * half, ly + c * half, Math.Max(hy, G(lx - s * half, ly + c * half) + 0.002f));
                    right[k] = W(lx + s * half, ly - c * half, Math.Max(hy, G(lx + s * half, ly - c * half) + 0.002f));
                }
                for (int k = 0; k < m; k++)
                {
                    float v0 = k / (float)m, v1 = (k + 1) / (float)m;
                    Tri(fs, (left[k], new Vector2(0, v0)), (right[k], new Vector2(1, v0)), (right[k + 1], new Vector2(1, v1)));
                    Tri(fs, (left[k], new Vector2(0, v0)), (right[k + 1], new Vector2(1, v1)), (left[k + 1], new Vector2(0, v1)));
                }
                for (int k = 0; k < 2; k++)
                {
                    double r = f.FootR - 0.01 - 0.014 * k;
                    float size = (float)f.Width * (1.3f + 0.6f * k);
                    AddChild(City(new MeshInstance3D
                    {
                        Name = "Mist", Mesh = new QuadMesh { Size = new Vector2(size, size) }, MaterialOverride = _mist,
                        Position = W(r * c, r * s, G(r * c, r * s) + size * 0.3f), CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
                    }, 45f));
                }
            }
            FallCount = S.Falls.Count;
            AddChild(City(new MeshInstance3D { Name = "Falls", Mesh = fs.Commit(), MaterialOverride = _fall, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off }, 60f));
        }

        static void Tri(SurfaceTool st, (Vector3 P, Vector2 Uv) a, (Vector3 P, Vector2 Uv) b, (Vector3 P, Vector2 Uv) c)
        {
            foreach (var (p, uv) in new[] { a, b, c }) { st.SetUV(uv); st.AddVertex(p); }
        }

        // ---------------------------------------------------------------- stone

        /// <summary>A box with its base centre at `at`, size (across x, up, along z), turned by `rot` about up.</summary>
        static void Box(SurfaceTool st, Vector3 at, Vector3 size, float rot, Color col)
        {
            var b = new Basis(Vector3.Up, rot);
            var c = at + Vector3.Up * size.Y / 2;
            Vector3 hx = b.X * size.X / 2, hy = Vector3.Up * size.Y / 2, hz = b.Z * size.Z / 2;
            Face(st, c + hx, b.X, hz, hy, col); Face(st, c - hx, -b.X, hz, hy, col);
            Face(st, c + hz, b.Z, hx, hy, col); Face(st, c - hz, -b.Z, hx, hy, col);
            Face(st, c + hy, Vector3.Up, hx, hz, col); Face(st, c - hy, Vector3.Down, hx, hz, col);
        }

        /// <summary>A quad centred at c, facing n, spanning ±u ±v (wound clockwise seen from n, Godot's front face).</summary>
        static void Face(SurfaceTool st, Vector3 c, Vector3 n, Vector3 u, Vector3 v, Color col)
        {
            Vector3 p0 = c - u - v, p1 = c + u - v, p2 = c + u + v, p3 = c - u + v;
            bool ccw = u.Cross(v).Dot(n) > 0;
            var order = ccw ? new[] { p0, p2, p1, p0, p3, p2 } : new[] { p0, p1, p2, p0, p2, p3 };
            st.SetColor(col); st.SetNormal(n);
            foreach (var p in order) st.AddVertex(p);
        }

        static readonly Color Sand = Lin(0.76f, 0.59f, 0.41f), SandDark = Lin(0.62f, 0.46f, 0.31f), SandPale = Lin(0.86f, 0.76f, 0.60f);
        static readonly Color Banner = Lin(0.62f, 0.10f, 0.08f), Tile = Lin(0.55f, 0.30f, 0.18f);

        void BuildWalls(SurfaceTool st)
        {
            const double R = KarnAshurSite.WallR;
            float wallH = 0.012f, wallT = 0.0055f, towerS = 0.0095f, towerH = 0.018f, gateS = 0.012f, gateH = 0.025f;
            var posts = new List<(double Th, bool Gate)>();
            posts.AddRange(S.WallTowers.Select(t => (t, false)));
            foreach (var g in S.Gates) { double d = 0.0125 / R; posts.Add((KarnAshurSite.Wrap(g.Theta - d), true)); posts.Add((KarnAshurSite.Wrap(g.Theta + d), true)); }
            posts.Sort((a, b) => a.Th.CompareTo(b.Th));
            for (int i = 0; i < posts.Count; i++)
            {
                var a = posts[i]; var b = posts[(i + 1) % posts.Count];
                double tb = b.Th < a.Th ? b.Th + 2 * Math.PI : b.Th;
                bool gap = a.Gate && b.Gate && tb - a.Th < 0.03 / R * 1.5;
                if (!gap)
                {
                    double tm = (a.Th + tb) / 2, len = 2 * R * Math.Sin((tb - a.Th) / 2);
                    double lx = R * Math.Cos(tm), ly = R * Math.Sin(tm);
                    float y = G(lx, ly) - Sink;
                    Box(st, W(lx, ly, y), new Vector3((float)len, wallH + Sink, wallT), (float)(tm + Math.PI / 2), Sand);
                    // merlons along the outer edge
                    int n = (int)(len / 0.0036);
                    for (int k = 0; k < n; k++)
                    {
                        double t = a.Th + (tb - a.Th) * (k + 0.5) / n, rr = R + wallT / 2 - 0.0007;
                        Box(st, W(rr * Math.Cos(t), rr * Math.Sin(t), y + wallH + Sink), new Vector3(0.0016f, 0.0018f, 0.0014f), (float)(t + Math.PI / 2), Sand);
                    }
                }
                else
                {
                    // the gate's arch: a lintel over the opening
                    double tm = (a.Th + tb) / 2, lx = R * Math.Cos(tm), ly = R * Math.Sin(tm);
                    Box(st, W(lx, ly, G(lx, ly) + 0.015f), new Vector3(0.026f, 0.007f, 0.0085f), (float)(tm + Math.PI / 2), SandDark);
                }
                double px = R * Math.Cos(a.Th), py = R * Math.Sin(a.Th);
                float s = a.Gate ? gateS : towerS, hgt = a.Gate ? gateH : towerH, gy = G(px, py) - Sink;
                Box(st, W(px, py, gy), new Vector3(s, hgt + Sink, s), (float)a.Th, a.Gate ? SandDark : Sand);
                Box(st, W(px, py, gy + hgt + Sink), new Vector3(s * 1.15f, 0.0015f, s * 1.15f), (float)a.Th, Sand);
                if (a.Gate)
                {
                    // banners hang on the outer face
                    double rb = R + s / 2 + 0.0004;
                    Box(st, W(rb * Math.Cos(a.Th), rb * Math.Sin(a.Th), gy + hgt * 0.45f), new Vector3(0.0045f, 0.009f, 0.0006f), (float)(a.Th + Math.PI / 2), Banner);
                }
                else if (i % 3 == 0)
                {
                    double rb = R + s / 2 + 0.0004;
                    Box(st, W(rb * Math.Cos(a.Th), rb * Math.Sin(a.Th), gy + towerH * 0.5f), new Vector3(0.0035f, 0.007f, 0.0005f), (float)(a.Th + Math.PI / 2), Banner);
                }
            }
            // bridges from the island to the shore on the gate axes
            foreach (var g in S.Gates)
            {
                double c = Math.Cos(g.Theta), sn = Math.Sin(g.Theta), r0 = KarnAshurSite.IslandR - 0.006, r1 = S.Shore(g.Theta) + 0.008;
                float deck = U(KarnAshurSite.WaterM) + 0.004f;
                double rm = (r0 + r1) / 2;
                Box(st, W(rm * c, rm * sn, deck - 0.002), new Vector3((float)(r1 - r0), 0.002f, 0.0062f), (float)g.Theta, SandPale);
                for (double r = r0 + 0.01; r < r1 - 0.006; r += 0.011)
                    Box(st, W(r * c, r * sn, deck - 0.012), new Vector3(0.0028f, 0.01f, 0.0058f), (float)g.Theta, SandDark);
            }
        }

        void BuildTemples(SurfaceTool st)
        {
            // the island: the great ziggurat with its south stair, and two lesser ones
            foreach (var z in S.Ziggurats)
            {
                float y0 = U(z.Z) - Sink, th = (float)z.TierH;
                for (int t = 0; t < z.Tiers; t++)
                {
                    float s = (float)(z.Base - 2 * t * z.Step);
                    Box(st, W(z.X, z.Y, y0 + t * th), new Vector3(s, th + (t == 0 ? Sink : 0), s), 0, t % 2 == 0 ? Sand : Lin(0.74f, 0.57f, 0.39f));
                    // the stair: a block filling each setback on the south face
                    float front = (float)(z.Base / 2 - t * z.Step);
                    Box(st, W(z.X, z.Y - front - z.Step / 2 + 0.0004, y0), new Vector3((float)(z.Base * 0.16), th * (t + 1) + Sink, (float)z.Step), 0, SandPale);
                }
                float top = y0 + Sink + z.Tiers * th;
                float ts = (float)(z.Base - 2 * z.Tiers * z.Step) * 0.8f;
                Box(st, W(z.X, z.Y, top), new Vector3(ts, th * 1.2f, ts * 0.8f), 0, Tile);
                AddFlame(W(z.X, z.Y, top + th * 1.2f), z.Base > 0.05 ? 0.02f : 0.011f);
                if (z.Base > 0.05) AddLight(W(z.X, z.Y, top + th * 1.2f + 0.012f), 0.3f, 0.35f);
            }
            // the Temple of the First Flame on the great peak
            double sx = S.ShrineX, sy = S.ShrineY;
            float g = U(KarnAshurSite.ShrineM) - Sink;
            float sw = 0.044f, wt = 0.0022f, wh = 0.005f;
            for (int k = 0; k < 4; k++)
            {
                double a = k * Math.PI / 2, ox = Math.Cos(a) * sw / 2, oy = Math.Sin(a) * sw / 2;
                Box(st, W(sx + ox, sy + oy, g), new Vector3(sw, wh + Sink, wt), (float)(a + Math.PI / 2), SandPale);
                double cx = sx + Math.Cos(a + Math.PI / 4) * sw * 0.707, cy = sy + Math.Sin(a + Math.PI / 4) * sw * 0.707;
                Box(st, W(cx, cy, g), new Vector3(0.006f, 0.014f + Sink, 0.006f), 0, SandPale);
                AddFlame(W(cx, cy, g + 0.014f + Sink), 0.008f);
            }
            Box(st, W(sx + 0.004, sy, g), new Vector3(0.02f, 0.01f + Sink, 0.016f), 0, SandPale);
            Box(st, W(sx + 0.004, sy, g + 0.01f + Sink), new Vector3(0.013f, 0.005f, 0.011f), 0, Sand);
            Box(st, W(sx - 0.009, sy, g), new Vector3(0.0045f, 0.022f + Sink, 0.0045f), 0, SandDark);
            AddFlame(W(sx - 0.009, sy, g + 0.022f + Sink), 0.022f);
            AddLight(W(sx - 0.009, sy, g + 0.04f), 0.3f, 0.45f);
            // gate braziers
            foreach (var gt in S.Gates)
                foreach (var side in new[] { -1, 1 })
                {
                    double t = gt.Theta + side * 0.0125 / KarnAshurSite.WallR, r = KarnAshurSite.WallR;
                    double lx = r * Math.Cos(t), ly = r * Math.Sin(t);
                    AddFlame(W(lx, ly, G(lx, ly) + 0.025f), 0.007f);
                }
        }

        void BuildAqueducts(SurfaceTool st)
        {
            foreach (var line in S.Aqueducts)
            {
                var poly = new Polyline(line.Select(p => new Vec3(p.X, p.Y, 0)).ToList());
                float top0 = G(line[0].X, line[0].Y) + 0.022f;
                float At(double s) => top0 - 0.003f * (float)(s / poly.Length);
                for (double s = 0; s < poly.Length; s += 0.0105)
                {
                    var p = poly.At(s);
                    float gy = G(p.Pos.X, p.Pos.Y) - Sink;
                    Box(st, W(p.Pos.X, p.Pos.Y, gy), new Vector3(0.0032f, At(s) - 0.003f - gy, 0.0045f), (float)p.Heading, SandDark);
                }
                var water = new SurfaceTool();
                water.Begin(Mesh.PrimitiveType.Triangles);
                const double step = 0.006;
                for (double s = 0; s < poly.Length - 1e-6; s += step)
                {
                    double e = Math.Min(poly.Length, s + step);
                    var a = poly.At(s); var b = poly.At(e);
                    double mx = (a.Pos.X + b.Pos.X) / 2, my = (a.Pos.Y + b.Pos.Y) / 2;
                    float h = At((s + e) / 2);
                    Box(st, W(mx, my, h - 0.003f), new Vector3((float)(e - s) + 0.0003f, 0.003f, 0.0052f), (float)Math.Atan2(b.Pos.Y - a.Pos.Y, b.Pos.X - a.Pos.X), Sand);
                    // the channel's water
                    var d = new Vector2((float)(b.Pos.X - a.Pos.X), (float)(b.Pos.Y - a.Pos.Y)).Normalized();
                    var nrm = new Vector2(-d.Y, d.X) * 0.0016f;
                    Vector3 p0 = W(a.Pos.X - nrm.X, a.Pos.Y - nrm.Y, At(s) + 0.0002f), p1 = W(a.Pos.X + nrm.X, a.Pos.Y + nrm.Y, At(s) + 0.0002f);
                    Vector3 p2 = W(b.Pos.X + nrm.X, b.Pos.Y + nrm.Y, At(e) + 0.0002f), p3 = W(b.Pos.X - nrm.X, b.Pos.Y - nrm.Y, At(e) + 0.0002f);
                    water.SetNormal(Vector3.Up);
                    foreach (var q in new[] { p0, p1, p2, p0, p2, p3 }) water.AddVertex(q);
                }
                AddChild(City(new MeshInstance3D { Name = "AqueductWater", Mesh = water.Commit(), MaterialOverride = _water, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off }));
            }
        }

        void BuildRoad(SurfaceTool st)
        {
            // the switchback: a paved shelf on the great peak's face, a retaining wall on the downhill side
            var road = S.Road;
            const float half = 0.0028f;
            var torches = new List<Vector3>();
            double run = 0;
            for (int i = 0; i + 1 < road.Length; i++)
            {
                var a = road[i]; var b = road[i + 1];
                double dx = b.X - a.X, dy = b.Y - a.Y, len = Math.Sqrt(dx * dx + dy * dy);
                if (len < 1e-7) continue;
                double nx = -dy / len * half, ny = dx / len * half;
                float ha = G(a.X, a.Y) + 0.0012f, hb = G(b.X, b.Y) + 0.0012f;
                Vector3 la = W(a.X + nx, a.Y + ny, ha), ra = W(a.X - nx, a.Y - ny, ha), lb = W(b.X + nx, b.Y + ny, hb), rb = W(b.X - nx, b.Y - ny, hb);
                st.SetColor(Lin(0.82f, 0.73f, 0.58f)); st.SetNormal(Vector3.Up);
                foreach (var p in new[] { la, lb, rb, la, rb, ra }) st.AddVertex(p);
                foreach (var p in new[] { la, rb, lb, la, ra, rb }) st.AddVertex(p);
                // retaining wall: from the lower edge down into the slope
                bool leftLower = G(a.X + nx * 2, a.Y + ny * 2) < G(a.X - nx * 2, a.Y - ny * 2);
                Vector3 ea = leftLower ? la : ra, eb = leftLower ? lb : rb, down = Vector3.Down * 0.012f, up = Vector3.Up * 0.0016f;
                st.SetColor(SandDark);
                var wn = (eb - ea).Cross(Vector3.Up).Normalized();
                st.SetNormal(leftLower ? -wn : wn);
                foreach (var p in new[] { ea + up, eb + up, eb + down, ea + up, eb + down, ea + down }) st.AddVertex(p);
                foreach (var p in new[] { ea + up, eb + down, eb + up, ea + up, ea + down, eb + down }) st.AddVertex(p);
                run += len;
                if (run > 0.028) { run = 0; torches.Add(ea + Vector3.Up * 0.004f); }
            }
            // torches along the road, lit after dark
            var glow = new GradientTexture2D
            {
                Width = 32, Height = 32, Fill = GradientTexture2D.FillEnum.Radial, FillFrom = new Vector2(0.5f, 0.5f), FillTo = new Vector2(1f, 0.5f),
                Gradient = new Gradient { Colors = new[] { new Color(1, 1, 1, 1), new Color(1, 1, 1, 0) }, Offsets = new[] { 0f, 1f } },
            };
            _torchMat = new StandardMaterial3D
            {
                ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                BlendMode = BaseMaterial3D.BlendModeEnum.Add, BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
                AlbedoTexture = glow, AlbedoColor = new Color(1f, 0.6f, 0.25f, 0f), DisableReceiveShadows = true,
            };
            var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, Mesh = new QuadMesh { Size = new Vector2(0.007f, 0.007f) }, InstanceCount = torches.Count };
            for (int i = 0; i < torches.Count; i++) mm.SetInstanceTransform(i, new Transform3D(Basis.Identity, torches[i]));
            _torches = new MultiMeshInstance3D { Name = "Torches", Multimesh = mm, MaterialOverride = _torchMat, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off, Visible = false };
            AddChild(City(_torches, 40f));
        }

        // ---------------------------------------------------------------- houses and trees

        static readonly Color[] HouseColours =
        {
            Lin(0.76f, 0.58f, 0.40f), Lin(0.70f, 0.52f, 0.35f), Lin(0.80f, 0.64f, 0.46f), Lin(0.66f, 0.49f, 0.33f),
            Lin(0.74f, 0.55f, 0.36f), Lin(0.84f, 0.70f, 0.52f), Lin(0.62f, 0.46f, 0.32f),
        };

        void BuildHouses()
        {
            _houses = Mat("karn_ashur_stone");
            _houses.SetShaderParameter("windows", true);
            _houses.SetShaderParameter("sink", Sink);
            var list = S.Buildings;
            var mm = new MultiMesh
            {
                TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseColors = true, UseCustomData = true,
                Mesh = new BoxMesh { Size = Vector3.One }, InstanceCount = list.Count,
            };
            var gardens = list.Where(b => b.Garden).ToList();
            var gm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseColors = true, Mesh = new BoxMesh { Size = Vector3.One }, InstanceCount = gardens.Count };
            int gi = 0;
            for (int i = 0; i < list.Count; i++)
            {
                var b = list[i];
                float h = (float)b.H + Sink, y = U(b.Z) - Sink;
                var basis = new Basis(Vector3.Up, (float)b.Rot) * Basis.FromScale(new Vector3((float)b.W, h, (float)b.D));
                mm.SetInstanceTransform(i, new Transform3D(basis, W(b.X, b.Y, y + h / 2)));
                var col = HouseColours[b.Seed % HouseColours.Length];
                if (b.Kind == KarnAshurSite.Kind.Tower) col = col.Lerp(HouseColours[5], 0.4f);
                mm.SetInstanceColor(i, col);
                mm.SetInstanceCustomData(i, new Color((float)b.W, h, (float)b.D, (b.Seed % 1000) / 1000f));
                if (b.Garden)
                {
                    var gb = new Basis(Vector3.Up, (float)b.Rot) * Basis.FromScale(new Vector3((float)b.W * 0.8f, 0.0012f, (float)b.D * 0.8f));
                    gm.SetInstanceTransform(gi, new Transform3D(gb, W(b.X, b.Y, y + h + 0.0006f)));
                    gm.SetInstanceColor(gi++, Lin(0.25f + 0.08f * (b.Seed % 7) / 7f, 0.40f, 0.15f));
                }
            }
            AddChild(City(new MultiMeshInstance3D { Name = "Houses", Multimesh = mm, MaterialOverride = _houses }));
            var leaf = new StandardMaterial3D { VertexColorUseAsAlbedo = true, Roughness = 0.95f };
            AddChild(City(new MultiMeshInstance3D { Name = "RoofGardens", Multimesh = gm, MaterialOverride = leaf }));
        }

        void BuildTrees()
        {
            var leaf = new StandardMaterial3D { VertexColorUseAsAlbedo = true, Roughness = 0.95f };
            foreach (bool cypress in new[] { false, true })
            {
                var list = S.Trees.Where(t => t.Cypress == cypress).ToList();
                Mesh mesh = cypress
                    ? new CylinderMesh { TopRadius = 0f, BottomRadius = 1f, Height = 1f, RadialSegments = 6, Rings = 1 }
                    : new SphereMesh { Radius = 1f, Height = 2f, RadialSegments = 7, Rings = 4 };
                var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseColors = true, Mesh = mesh, InstanceCount = list.Count };
                for (int i = 0; i < list.Count; i++)
                {
                    var t = list[i];
                    float y = U(t.Z);
                    var basis = cypress ? Basis.FromScale(new Vector3((float)t.R, (float)t.H, (float)t.R))
                                        : Basis.FromScale(new Vector3((float)t.R, (float)t.H * 0.5f, (float)t.R));
                    float cy = cypress ? y + (float)t.H / 2 - 0.0005f : y + (float)t.H * 0.5f;
                    mm.SetInstanceTransform(i, new Transform3D(basis, W(t.X, t.Y, cy)));
                    float k = (float)((t.X * 9137.1 + t.Y * 4517.3) % 1.0 + 1.0) % 1f;
                    mm.SetInstanceColor(i, cypress ? Lin(0.14f + 0.04f * k, 0.25f + 0.05f * k, 0.12f)
                                                   : Lin(0.22f + 0.12f * k, 0.36f + 0.1f * k, 0.13f + 0.04f * k));
                }
                AddChild(City(new MultiMeshInstance3D { Name = cypress ? "Cypresses" : "Trees", Multimesh = mm, MaterialOverride = leaf }));
            }
        }

        // ---------------------------------------------------------------- fire and light

        void AddFlame(Vector3 at, float size)
        {
            _flame ??= Mat("karn_ashur_flame");
            var f = new MeshInstance3D
            {
                Name = "Flame", Mesh = new QuadMesh { Size = new Vector2(size * 0.55f, size), CenterOffset = new Vector3(0, size / 2, 0) },
                MaterialOverride = _flame, Position = at, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            };
            AddChild(City(f, 60f));
            _flames.Add(f);
        }

        void AddLight(Vector3 at, float range, float energy)
        {
            var l = new OmniLight3D { Name = "Fire", Position = at, OmniRange = range, LightColor = new Color(1f, 0.62f, 0.3f), LightEnergy = energy, ShadowEnabled = false };
            l.DistanceFadeEnabled = true; l.DistanceFadeBegin = 30f; l.DistanceFadeLength = 10f;
            AddChild(l);
            _lights.Add((l, energy));
        }

        /// <summary>Per frame: lamps and windows after dark, fires always burning.</summary>
        public void Tick(float night, float daylight)
        {
            _houses.SetShaderParameter("night", night);
            _fall.SetShaderParameter("daylight", daylight);
            _mist.SetShaderParameter("daylight", daylight);
            _flame?.SetShaderParameter("strength", 0.65f + 0.7f * night);
            foreach (var (l, e) in _lights) l.LightEnergy = e * (0.35f + 1.6f * night);
            _torches.Visible = night > 0.02f;
            _torchMat.AlbedoColor = new Color(1f, 0.6f, 0.25f, Math.Min(1f, night * 1.3f));
        }
    }
}
