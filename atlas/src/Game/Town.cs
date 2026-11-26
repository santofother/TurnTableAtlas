// A town package on the Known World as a miniature (Corivessa Port, Corivessa): the package's own city.glb laid onto
// the relief round its pin by TownSite, so the map shows the same harbour, walls and palace the city view opens.
// The model's baked ground fades into the map's colour at the square's edge, and its harbour or river water shows only
// where the map itself is land. Lit windows and fires after dark.
using System;
using System.Collections.Generic;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class Town : Node3D
    {
        /// <summary>Orbit distance beyond which the miniature is not drawn (the Valdoran marches view is at 34).</summary>
        const float MiniRange = 48f;
        const int GridN = 161;
        /// <summary>The model's open water (its bay) is drawn out to this share of its half extent, the harbour inside
        /// the moles; a shallow channel (a river through the town) out to <see cref="RiverReach"/>. Beyond, the map's
        /// own coast and rivers take over.</summary>
        const double WaterReach = 0.5, RiverReach = 0.74, RiverDepth = -0.5;
        /// <summary>Meshes are laid out once and kept between visits to the map (keyed by city id).</summary>
        static readonly Dictionary<string, (TownSite Site, List<(ArrayMesh Mesh, string Name)> Parts, ArrayMesh Ground, ArrayMesh Water, Texture2D Albedo)> Cache = new();

        public TownSite S { get; private set; }
        public CityManifest M { get; private set; }
        public string ViewId => "CAM_Town_" + M.Id;
        public int MiniMeshes { get; private set; }
        public readonly List<ShaderMaterial> WeatherMaterials = new();
        Materials _mats;

        /// <summary>The town packages that ask for a miniature (city.json `world_map.miniature`).</summary>
        public static bool Wants(CityManifest m) => !m.IsEstate && !m.IsMetropolis && m.WorldMap?.Miniature != null && m.Files.ContainsKey("model");

        /// <summary>Orbit preset: from the south-west, the whole town in view.</summary>
        public KnownWorldMap.View View()
        {
            double h = S.GroundAt(S.Cx, S.Cy) ?? 0;
            return new() { Id = ViewId, Name = M.Name, Target = new[] { S.Cx, S.Cy, h }, Yaw = -110, Pitch = 36, Dist = S.Half * 2.8 };
        }

        public void Build(CityManifest m, KnownWorldMap kw, ReliefSampler relief, Texture2D mapAlbedo, Texture2D heights)
        {
            Name = "Town_" + m.Id;
            M = m;
            ulong t0 = Time.GetTicksMsec();
            if (!Cache.TryGetValue(m.Id, out var c))
            {
                var uv = kw.PinFor(m.WorldMap);
                if (!uv.HasValue) return;
                var (x, y) = kw.UvToXy(uv.Value.U, uv.Value.V);
                c = Load(m, x, y, kw.UnitM, relief);
                if (c.Site == null) return;
                Cache[m.Id] = c;
            }
            S = c.Site;

            _mats = new Materials(null);
            WeatherMaterials.Add(_mats.Painted);
            var ground = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/town_ground.gdshader") };
            ground.SetShaderParameter("town_tex", c.Albedo);
            ground.SetShaderParameter("albedo_tex", mapAlbedo);
            ground.SetShaderParameter("height_tex", heights);
            ground.SetShaderParameter("world_min", new Vector2((float)kw.BoundsXy[0], -(float)kw.BoundsXy[3]));
            ground.SetShaderParameter("world_size", new Vector2((float)kw.Width, (float)kw.Depth));
            ground.SetShaderParameter("centre", new Vector2((float)S.Cx, -(float)S.Cy));
            ground.SetShaderParameter("half_size", (float)S.Half);
            WeatherMaterials.Add(ground);
            Add("Ground", c.Ground, ground, false);
            if (c.Water != null)
            {
                var water = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/karn_ashur_water.gdshader") };
                WeatherMaterials.Add(water);
                Add("Water", c.Water, water, false);
            }
            foreach (var (mesh, name) in c.Parts)
            {
                var mi = Add(name, mesh, null, !name.Contains("Flames"));
                for (int s = 0; s < mesh.GetSurfaceCount(); s++) mi.SetSurfaceOverrideMaterial(s, _mats.ForGltf(mesh.SurfaceGetName(s)));
                MiniMeshes++;
            }
            GD.Print($"[Atlas] town {m.Id}: miniature x{m.WorldMap.Miniature.Exaggeration:0} ({S.Half * 2:0.000} units across), {MiniMeshes} meshes in {Time.GetTicksMsec() - t0} ms");
        }

        MeshInstance3D Add(string name, Mesh mesh, Material mat, bool shadow)
        {
            var mi = new MeshInstance3D
            {
                Name = name, Mesh = mesh, MaterialOverride = mat, VisibilityRangeEnd = MiniRange, VisibilityRangeEndMargin = MiniRange * 0.2f,
                VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Self,
                CastShadow = shadow ? GeometryInstance3D.ShadowCastingSetting.On : GeometryInstance3D.ShadowCastingSetting.Off,
            };
            AddChild(mi);
            return mi;
        }

        /// <summary>Windows and fires after dark (the same levels the city view uses).</summary>
        public void SetNight(float windowLevel, float lampLevel) => _mats?.SetNight(windowLevel, lampLevel);

        /// <summary>The miniature's ground (blend units) under a world point, or null off its square.</summary>
        public float? HeightAt(double x, double y) => S?.GroundAt(x, y) is { } h ? (float)h : null;

        // ---------------------------------------------------------------- layout

        /// <summary>One glTF surface in the model's frame (metres, z up: x east, y north).</summary>
        sealed class Surface
        {
            public Vector3[] V, N; public Color[] C; public Vector2[] Uv; public int[] I; public string Mat;
        }

        static (TownSite, List<(ArrayMesh, string)>, ArrayMesh, ArrayMesh, Texture2D) Load(CityManifest m, double cx, double cy, double unitM, ReliefSampler relief)
        {
            var root = CityLoader.LoadGlb(m.FilePath("model"));
            var meshes = new List<(string Name, List<Surface> Surfaces)>();
            foreach (var mi in CityLoader.AllMeshes(root))
            {
                string n = mi.Name.ToString();
                if (n == "CAP_Base") continue;
                var t = CityLoader.LocalToRoot(mi, root);
                var list = new List<Surface>();
                for (int s = 0; s < mi.Mesh.GetSurfaceCount(); s++)
                {
                    var a = mi.Mesh.SurfaceGetArrays(s);
                    var v = a[(int)Mesh.ArrayType.Vertex].AsVector3Array();
                    var nr = a[(int)Mesh.ArrayType.Normal].VariantType == Variant.Type.Nil ? null : a[(int)Mesh.ArrayType.Normal].AsVector3Array();
                    var surf = new Surface
                    {
                        // glTF: +x east, +y up, -z north
                        V = v.Select(p => { var w = t * p; return new Vector3(w.X, -w.Z, w.Y); }).ToArray(),
                        N = nr?.Select(q => t.Basis * q).ToArray(),
                        C = a[(int)Mesh.ArrayType.Color].VariantType == Variant.Type.Nil ? null : a[(int)Mesh.ArrayType.Color].AsColorArray(),
                        Uv = a[(int)Mesh.ArrayType.TexUV].VariantType == Variant.Type.Nil ? null : a[(int)Mesh.ArrayType.TexUV].AsVector2Array(),
                        I = a[(int)Mesh.ArrayType.Index].VariantType == Variant.Type.Nil ? Enumerable.Range(0, v.Length).ToArray() : a[(int)Mesh.ArrayType.Index].AsInt32Array(),
                        Mat = mi.Mesh.SurfaceGetMaterial(s)?.ResourceName ?? "",
                    };
                    list.Add(surf);
                }
                meshes.Add((n, list));
            }
            root.Free();
            var terrain = meshes.FirstOrDefault(x => x.Name == "CAP_Terrain").Surfaces;
            if (terrain == null) { GD.PushWarning($"[Atlas] town {m.Id}: no CAP_Terrain in its model"); return (null, null, null, null, null); }
            double half = m.Extent[2];
            var grid = TownSite.GridFromPoints(terrain.SelectMany(s => s.V).Select(p => ((double)p.X, (double)p.Y, (double)p.Z)), half, GridN);
            var site = new TownSite(m.Id, relief.Coarse, cx, cy, unitM, m.ModelScale, half, grid, m.WorldMap.Miniature.Exaggeration);

            Vector3 Map(Vector3 p) { var (x, y, h) = site.Place(p.X, p.Y, p.Z); return new Vector3((float)x, (float)h, -(float)y); }

            var parts = new List<(ArrayMesh, string)>();
            ArrayMesh ground = null, water = null;
            foreach (var (name, surfaces) in meshes)
            {
                if (name == "CAP_Sea")
                {
                    water = WaterMesh(site, surfaces, Map, (x, y) => relief.Fine(x, y) > 0);
                    continue;
                }
                var mesh = new ArrayMesh();
                foreach (var s in surfaces)
                {
                    var verts = s.V.Select(Map).ToArray();
                    var norms = name == "CAP_Terrain" ? Normals(verts, s.I) : s.N;   // the model's axes are the map's
                    var idx = name == "CAP_Terrain" ? s.I : Thinned(site, name, s);
                    if (idx.Length > 0) AddSurface(mesh, verts, norms, s.C, s.Uv, idx, s.Mat);   // a grove past the edge is gone
                }
                if (name == "CAP_Terrain") ground = mesh; else if (mesh.GetSurfaceCount() > 0) parts.Add((mesh, name));
            }
            var albedo = LoadTex(m.FilePath("terrain_albedo"));
            return (site, parts, ground, water, albedo);
        }

        /// <summary>A surface's triangles that stand on the map: ships always, roads out to near the edge, the rest of
        /// the countryside thinning out towards it (TownSite.KeepAtEdge).</summary>
        static int[] Thinned(TownSite site, string name, Surface s)
        {
            if (name.StartsWith("CAP_Ship_")) return s.I;
            var keep = new List<int>(s.I.Length);
            for (int k = 0; k + 2 < s.I.Length; k += 3)
            {
                var c = (s.V[s.I[k]] + s.V[s.I[k + 1]] + s.V[s.I[k + 2]]) / 3;
                bool ok = name.Contains("Roads")
                    ? Math.Max(Math.Abs(c.X), Math.Abs(c.Y)) < 0.9 * site.ModelHalf
                    : site.KeepAtEdge(c.X, c.Y);
                if (ok) { keep.Add(s.I[k]); keep.Add(s.I[k + 1]); keep.Add(s.I[k + 2]); }
            }
            return keep.ToArray();
        }

        /// <summary>The model's water where the map is land (a river, a harbour basin cut into the coast): over the map's
        /// own sea (as its pixels show it) it would only cover the sea already drawn there.</summary>
        static ArrayMesh WaterMesh(TownSite site, List<Surface> surfaces, Func<Vector3, Vector3> map, Func<double, double, bool> mapIsLand)
        {
            var verts = new List<Vector3>();
            foreach (var s in surfaces)
                for (int k = 0; k + 2 < s.I.Length; k += 3)
                {
                    var tri = new[] { s.V[s.I[k]], s.V[s.I[k + 1]], s.V[s.I[k + 2]] };
                    if (tri.All(p => site.ModelGround(p.X, p.Y) > 0.05)) continue;   // under the model's land
                    if (tri.All(p => Math.Max(Math.Abs(p.X), Math.Abs(p.Y)) > (site.ModelGround(p.X, p.Y) > RiverDepth ? RiverReach : WaterReach) * site.ModelHalf))
                        continue;                                                       // past the harbour or the river's reach
                    var w = tri.Select(map).ToArray();
                    if (!w.Any(p => mapIsLand(p.X, -p.Z))) continue;                  // over the map's sea
                    verts.AddRange(w);
                }
            if (verts.Count == 0) return null;
            var mesh = new ArrayMesh();
            var arr = Enumerable.Range(0, verts.Count).ToArray();
            AddSurface(mesh, verts.ToArray(), verts.Select(_ => Vector3.Up).ToArray(), null, null, arr, "CAP_Water");
            return mesh;
        }

        static void AddSurface(ArrayMesh mesh, Vector3[] v, Vector3[] n, Color[] c, Vector2[] uv, int[] idx, string mat)
        {
            var arrays = new Godot.Collections.Array();
            arrays.Resize((int)Mesh.ArrayType.Max);
            arrays[(int)Mesh.ArrayType.Vertex] = v;
            if (n != null) arrays[(int)Mesh.ArrayType.Normal] = n;
            if (c != null) arrays[(int)Mesh.ArrayType.Color] = c;
            if (uv != null) arrays[(int)Mesh.ArrayType.TexUV] = uv;
            arrays[(int)Mesh.ArrayType.Index] = idx;
            mesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, arrays);
            mesh.SurfaceSetName(mesh.GetSurfaceCount() - 1, mat);
        }

        /// <summary>Smooth normals of the laid-out ground (the relief's slopes and the model's hills together).</summary>
        static Vector3[] Normals(Vector3[] v, int[] idx)
        {
            var n = new Vector3[v.Length];
            for (int k = 0; k + 2 < idx.Length; k += 3)
            {
                int a = idx[k], b = idx[k + 1], c = idx[k + 2];
                var f = (v[c] - v[a]).Cross(v[b] - v[a]);
                n[a] += f; n[b] += f; n[c] += f;
            }
            for (int i = 0; i < n.Length; i++) n[i] = n[i].LengthSquared() > 0 ? n[i].Normalized() : Vector3.Up;
            if (n.Length > 0 && n.Average(q => q.Y) < 0) for (int i = 0; i < n.Length; i++) n[i] = -n[i];
            return n;
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
