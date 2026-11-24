// The Known World relief, baked from KnownWorld.blend (10 miles per unit, sea level at zero).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class WorldMap : Node3D
    {
        // kept between visits (the map is rebuilt each time a city closes)
        static (Vector3 Target, float Yaw, float Pitch, float Distance)? _lastCamera;
        static double _lastHour = 16.5;
        static Texture2D _kwTex;
        static ImageTexture _kwHeightTex;
        /// <summary>The relief's heights with each basin's own ground written in under its patch: the terrain-following fog
        /// measures from this (else it would fill a basin that stands above the baked relief).</summary>
        static ImageTexture _fogHeightTex;
        static float[] _kwH;
        static int _hw, _hh;
        static KnownWorldMap _kw;
        static ReliefSampler _sampler;
        /// <summary>Metropolis basins (Karn Ashur) by package id, and the High Dunes round them; kept between visits.</summary>
        static readonly Dictionary<string, BasinSite> _basinSites = new();
        static HighDunesRegion _highDunes;
        /// <summary>Country estates' hero patches (Landric's villa), by city id; kept between visits.</summary>
        static readonly Dictionary<string, EstateSite> _estateSites = new();
        // the relief mesh's quads (its PlaneMesh subdivisions + 1); hero patches meet its triangles at their edges
        const int ReliefQuadsX = 1024, ReliefQuadsY = 534;

        const string KwJson = "res://assets/map/known_world/known_world.json";
        static readonly Color Accent = new(0.95f, 0.72f, 0.38f);

        AtlasRoot _root;
        public TurntableCamera Rig { get; private set; }
        public TimeOfDay Tod { get; private set; }
        public WeatherView Weather { get; private set; }
        public KnownWorldMap Kw => _kw;
        /// <summary>Highest point of the relief (blend units).</summary>
        public static float ReliefMax { get; private set; }
        public readonly List<MapPin3D> Pins = new();

        public MapTable Table { get; private set; }
        /// <summary>Metropolis basins on the map (Karn Ashur): the package's own ground and city as a miniature.</summary>
        public readonly List<Basin> Basins = new();
        /// <summary>The High Dunes round Karn Ashur: rivers, villages, market towns, the grain route.</summary>
        public HighDunes Dunes { get; private set; }
        public static HighDunesRegion Region => _highDunes;
        /// <summary>Estates standing on the map as miniatures of their packages.</summary>
        public readonly List<Estate> Estates = new();
        readonly HashSet<MeshInstance3D> _basinGlows = new();
        public WorldShipping Shipping { get; private set; }
        ShaderMaterial _reliefMat;
        ShaderMaterial _fogMat;
        readonly List<(MeshInstance3D Glow, StandardMaterial3D Mat, float K)> _lights = new();
        readonly List<(Label3D L, bool Realm)> _names = new();
        bool _showNames = true;

        // overlay
        CanvasLayer _ui;
        OptionButton _views;
        Button _weatherBtn;
        /// <summary>The weather drop-down's controls.</summary>
        public WeatherPanel WeatherControls { get; private set; }
        HSlider _time;
        Label _clock;
        Button _play;
        bool _syncing;
        PanelContainer _card;
        TextureRect _cardThumb;
        Label _cardTitle, _cardInfo;
        MapPin3D _hover;
        Vector2 _pressAt;

        public void Build(AtlasRoot root)
        {
            _root = root;
            _kw ??= KnownWorldMap.Load(ProjectSettings.GlobalizePath(KwJson));
            Tod = new TimeOfDay { Name = "TimeOfDay", FogScale = 0.3f, Room = MapTable.RoomColor };
            AddChild(Tod);
            Tod.Setup(null, new SunDefaults { LatitudeDeg = 38, DefaultDayOfYear = 172, NorthOffsetDeg = 0 });
            Tod.Hour = Args.Has("hour") ? Args.F("hour", 16.5f) : _lastHour;
            Tod.Apply();

            Table = new MapTable();
            AddChild(Table);
            var bounds = new Rect2((float)_kw.BoundsXy[0], -(float)_kw.BoundsXy[3], (float)_kw.Width, (float)_kw.Depth);
            Table.Build(bounds);
            _reliefMat = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/relief.gdshader") };
            BuildRelief();
            BuildRegionalFog(bounds);

            Rig = new TurntableCamera { Name = "Rig", MinDist = 0.8f, MaxDist = 950f, MinPitch = 5f, FlySpeed = 4f, Bounds = bounds };
            AddChild(Rig);
            Rig.Cam.Far = 8000f;

            Weather = new WeatherView { Name = "Weather" };
            AddChild(Weather);
            float cx = (float)(_kw.BoundsXy[0] + _kw.Width / 2), cy = (float)(_kw.BoundsXy[1] + _kw.Depth / 2);
            Weather.Setup(root.Weather, Tod,
                new CloudScale { Base = 9, Top = 21, Center = new Vector2(cx, -cy), Half = new Vector2((float)_kw.Width / 2, (float)_kw.Depth / 2)   /* W1: clouds stay over the map, not the table */,
                                 Cell = 230, Shape = 20, Detail = 5.5f, NearFade = 1.5f, Edge = 45, FlashR = 30 },
                new[] { _reliefMat }.Concat(Basins.SelectMany(b => b.WeatherMaterials)).Concat(Dunes?.WeatherMaterials ?? new List<ShaderMaterial>())
                    .Concat(Estates.SelectMany(e => e.WeatherMaterials)), false, () => Rig.Target,
                () => Math.Clamp(Math.Abs(Tod.Speed) * 60, 1.0, 20.0));

            foreach (var m in root.Cities)
            {
                var pin = new MapPin3D { Name = "Pin_" + m.Id };
                AddChild(pin);
                pin.Build(m);
                var uv = _kw.PinFor(m.WorldMap);
                if (uv.HasValue) pin.Position = KwPoint(uv.Value.U, uv.Value.V);
                pin.Visible = uv.HasValue;
                Pins.Add(pin);
            }
            Shipping = new WorldShipping();
            AddChild(Shipping);
            Shipping.Build(this);
            foreach (var b in Basins)   // FIX(karn_ashur): the basin's view, and the High Dunes round it
                if (!_kw.Cameras.Any(c => c.Id == Basin.ViewId)) _kw.Cameras.Add(Basin.View(b.S));
            if (Dunes != null && !_kw.Cameras.Any(c => c.Id == HighDunesViewId))
                _kw.Cameras.Add(new KnownWorldMap.View { Id = HighDunesViewId, Name = "The High Dunes", Target = new[] { 94.0, 31.0, 0.5 }, Yaw = -98, Pitch = 40, Dist = 62 });
            foreach (var e in Estates)
                if (!_kw.Cameras.Any(c => c.Id == e.ViewId)) _kw.Cameras.Add(e.View());
            BuildOverlay();
            FillViews();
            if (_lastCamera is { } last) Rig.Snap(last.Target, last.Yaw, last.Pitch, last.Distance);
            else if (_kw.Cameras.FirstOrDefault() is { } overview)
                Rig.Snap(Geo.V(overview.Target), (float)overview.Yaw, (float)overview.Pitch, (float)overview.Dist);
            else Rig.Snap(new Vector3(cx, 0, -cy), -90f, 58f, bounds.Size.X);
            if (Args.Has("view")) FlyToView(Args.Get("view"), 0.01);
            if (Args.Get("orbit") is { } orbit)   // --orbit=x,y,z,yaw,pitch,dist (blend xy, height in units): a fixed shot
            {
                var o = orbit.Split(',').Select(t => double.Parse(t, System.Globalization.CultureInfo.InvariantCulture)).ToArray();
                Rig.Snap(Geo.V(new[] { o[0], o[1], o[2] }), (float)o[3], (float)o[4], (float)o[5]);
            }
        }

        void BuildRegionalFog(Rect2 bounds)
        {
            const float bottom = -0.5f;
            float top = ReliefMax + 7f;
            _fogMat = new ShaderMaterial
            {
                Shader = ResourceLoader.Load<Shader>("res://shaders/regional_fog.gdshader"),
                RenderPriority = 8, // Below the cloud layer and the Calderra pin label.
            };
            _fogMat.SetShaderParameter("height_tex", _fogHeightTex ?? _kwHeightTex);   // FIX(karn_ashur)
            _fogMat.SetShaderParameter("noise_tex", CloudLayer.WeatherTexture);
            _fogMat.SetShaderParameter("box_min", new Vector3(bounds.Position.X, bottom, bounds.Position.Y));
            _fogMat.SetShaderParameter("box_max", new Vector3(bounds.End.X, top, bounds.End.Y));
            var center = bounds.GetCenter();
            AddChild(new MeshInstance3D
            {
                Name = "RegionalFog", Position = new Vector3(center.X, (bottom + top) / 2, center.Y),
                Mesh = new BoxMesh { Size = new Vector3(bounds.Size.X, top - bottom, bounds.Size.Y) },
                MaterialOverride = _fogMat, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            });
        }

        public const string HighDunesViewId = "CAM_HighDunes";

        void BuildRelief()
        {
            ulong t0 = Time.GetTicksMsec();
            // --karn-ashur=off shows the baked relief alone where a basin stands; --high-dunes=off leaves the region as baked
            var metros = Args.Get("karn-ashur") == "off" ? new List<CityManifest>() : _root.Cities.Where(c => c.IsMetropolis).ToList();
            if (_kwH == null)
            {
                LoadHeights();
                // FIX(karn_ashur): the High Dunes' rivers are graded and carved, its other summits capped, before the relief
                // texture and the sampler are made (a basin's ring eases onto the carved relief)
                var raw = new ReliefSampler(_kwH, _hw, _hh, _kw.BoundsXy, ReliefQuadsX, ReliefQuadsY);
                var pre = metros.Select(m => Basin.MakeSite(m, _kw, raw)).Where(b => b != null).ToList();
                var hd = Path.Combine(_kw.Directory, "high_dunes.json");
                if (pre.Count > 0 && Args.Get("high-dunes") != "off" && File.Exists(hd))
                {
                    _highDunes = new HighDunesRegion(HighDunesData.Load(hd), _kw.UnitM, _kw.Exaggeration);
                    _highDunes.LinkOutlet(pre[0].OutletEnd);
                    _highDunes.LinkRoad(pre[0].RoadEnd, pre[0].Contains);
                    _highDunes.EditHeights(_kwH, _hw, _hh, _kw.BoundsXy, (x, y) => pre.Any(b => b.Contains(x, y)));
                }
                MakeHeightTexture();
            }
            _sampler ??= new ReliefSampler(_kwH, _hw, _hh, _kw.BoundsXy, ReliefQuadsX, ReliefQuadsY);
            foreach (var m in metros.Where(c => !_basinSites.ContainsKey(c.Id)))
                if (Basin.MakeSite(m, _kw, _sampler) is { } bs)
                {
                    if (_highDunes?.TributaryEntry is { } te && bs.Contains(te.X, te.Y)) bs.SetTributary(te);
                    _basinSites[m.Id] = bs;
                }
            var basinSites = metros.Where(m => _basinSites.ContainsKey(m.Id)).Select(m => _basinSites[m.Id]).ToList();
            if (_fogHeightTex == null && basinSites.Count > 0)
            {
                var fh = (float[])_kwH.Clone();
                double x0 = _kw.BoundsXy[0], y1 = _kw.BoundsXy[3], px = _kw.Width / (_hw - 1), py = _kw.Depth / (_hh - 1);
                foreach (var bs in basinSites)
                    for (int j = Math.Max(0, (int)((y1 - bs.YMax) / py)); j <= Math.Min(_hh - 1, (int)((y1 - bs.YMin) / py) + 1); j++)
                        for (int i = Math.Max(0, (int)((bs.XMin - x0) / px)); i <= Math.Min(_hw - 1, (int)((bs.XMax - x0) / px) + 1); i++)
                        {
                            double x = x0 + i * px, y = y1 - j * py;
                            if (bs.Contains(x, y)) fh[j * _hw + i] = (float)bs.MeshUnits(x, y);
                        }
                _fogHeightTex = ImageTexture.CreateFromImage(Image.CreateFromData(_hw, _hh, false, Image.Format.Rf, MemoryMarshal.AsBytes(fh.AsSpan()).ToArray()));
            }
            if (_kwTex == null)
            {
                var img = LoadImage(Path.Combine(_kw.Directory, _kw.Albedo));
                if (img != null && _highDunes != null)
                {
                    bool InBasin(double x, double y) => basinSites.Any(b => b.Contains(x, y));
                    _highDunes.PlaceSettlements((x, y) => _highDunes.M(_sampler.Fine(x, y)), InBasin);
                    img.Convert(Image.Format.Rgba8);
                    var px = img.GetData();
                    _highDunes.PaintAlbedo(px, img.GetWidth(), img.GetHeight(), _kw.BoundsXy, (x, y) => _highDunes.M(_sampler.Fine(x, y)), InBasin);
                    img = Image.CreateFromData(img.GetWidth(), img.GetHeight(), false, Image.Format.Rgba8, px);
                }
                if (img != null) { img.GenerateMipmaps(); _kwTex = ImageTexture.CreateFromImage(img); }
            }
            if (Args.Get("estates") != "off")      // --estates=off: the relief alone where an estate stands
                foreach (var m in _root.Cities.Where(c => c.IsEstate && !_estateSites.ContainsKey(c.Id)))
                    if (Estate.MakeSite(m, _kw, _sampler) is { } es) _estateSites[m.Id] = es;
            var estateSites = Args.Get("estates") == "off" ? new List<EstateSite>()
                : _root.Cities.Where(c => _estateSites.ContainsKey(c.Id)).Select(c => _estateSites[c.Id]).Take(1).ToList();   // one hole2 for now
            if (estateSites.Count > 0)
            {
                var (a0, b0, a1, b1) = estateSites[0].HoleUv;
                _reliefMat.SetShaderParameter("hole2", new Vector4((float)a0, (float)b0, (float)a1, (float)b1));
            }
            if (basinSites.Count > 0)
            {
                var (u0, v0, u1, v1) = basinSites[0].HoleUv;   // the patch covers these vertices: sink them out of sight
                _reliefMat.SetShaderParameter("hole", new Vector4((float)u0, (float)v0, (float)u1, (float)v1));
            }
            _reliefMat.SetShaderParameter("albedo_tex", _kwTex);
            _reliefMat.SetShaderParameter("height_tex", _kwHeightTex);
            _reliefMat.SetShaderParameter("size", new Vector2((float)_kw.Width, (float)_kw.Depth));
            _reliefMat.SetShaderParameter("texel", new Vector2(1f / _hw, 1f / _hh));

            var relief = new Node3D { Name = "KnownWorld" };
            AddChild(relief);
            float cx = (float)(_kw.BoundsXy[0] + _kw.Width / 2), cy = (float)(_kw.BoundsXy[1] + _kw.Depth / 2);
            var at = new Vector3(cx, 0, -cy);
            var mesh = new PlaneMesh { Size = new Vector2((float)_kw.Width, (float)_kw.Depth), SubdivideWidth = ReliefQuadsX - 1, SubdivideDepth = ReliefQuadsY - 1 };
            mesh.CustomAabb = new Aabb(new Vector3(-(float)_kw.Width / 2, -1, -(float)_kw.Depth / 2), new Vector3((float)_kw.Width, 12, (float)_kw.Depth));
            relief.AddChild(new MeshInstance3D { Name = "Relief", Mesh = mesh, Position = at, MaterialOverride = _reliefMat });
            foreach (var bs in basinSites)
            {
                var b = new Basin();
                AddChild(b);
                b.Build(bs, _root.Cities.First(c => c.Id == bs.Id), _kw, _kwTex);
                Basins.Add(b);
            }
            if (_highDunes != null)
            {
                Dunes = new HighDunes();
                AddChild(Dunes);
                var metro = _root.Cities.FirstOrDefault(c => c.IsMetropolis);
                double f = metro?.WorldMap?.Miniature?.Exaggeration ?? 4;
                Dunes.Build(_highDunes, _kw, (x, y) => GroundAt(x, y), metro?.Instances, f / _kw.UnitM);
            }
            foreach (var es in estateSites)
            {
                var est = new Estate();
                AddChild(est);
                est.Build(es, _root.Cities.First(c => c.Id == es.Id), _kw, _kwTex);
                Estates.Add(est);
            }

            // collision at one sample per unit: keeps the camera above the mountains, double-click focus
            int cols = (int)Math.Round(_kw.Width) + 1, rows = (int)Math.Round(_kw.Depth) + 1;
            var data = new float[cols * rows];
            for (int r = 0; r < rows; r++)
                for (int c = 0; c < cols; c++)
                {
                    double u = c / (double)(cols - 1), v = r / (double)(rows - 1);
                    float h = Math.Max(0f, HeightUv(u, v));
                    var (x, y) = _kw.UvToXy(u, v);
                    foreach (var bs in basinSites)                       // a basin's own collision lies on top here
                        if (bs.Contains(x, y))
                            h = Math.Max(Math.Abs(x - bs.Cx), Math.Abs(y - bs.Cy)) < bs.PatchHalf - 1.0 ? -1f : Math.Min(h, (float)bs.MeshUnits(x, y)) - 0.05f;
                    foreach (var es in estateSites)       // an estate's own collision lies on top here
                        if (es.Contains(x, y)) h = Math.Min(h, (float)es.MeshUnits(x, y)) - 0.05f;
                    data[r * cols + c] = h;
                }
            var body = new StaticBody3D { Name = "KwCollision", CollisionLayer = CityLoader.CollisionLayer, CollisionMask = 0 };
            body.AddChild(new CollisionShape3D
            {
                Shape = new HeightMapShape3D { MapWidth = cols, MapDepth = rows, MapData = data },
                Position = at, Scale = new Vector3((float)_kw.Width / (cols - 1), 1, (float)_kw.Depth / (rows - 1)),
            });
            relief.AddChild(body);

            // settlements: warm lights after dark, and names (realms and the towns no city package stands for)
            var glow = new GradientTexture2D
            {
                Width = 64, Height = 64, Fill = GradientTexture2D.FillEnum.Radial, FillFrom = new Vector2(0.5f, 0.5f), FillTo = new Vector2(1f, 0.5f),
                Gradient = new Gradient { Colors = new[] { new Color(1, 1, 1, 1), new Color(1, 1, 1, 0) }, Offsets = new[] { 0f, 1f } },
            };
            var pinned = new HashSet<string>(_root.Cities.Select(m => m.WorldMap?.Settlement).Where(s => s != null));
            foreach (var s in _kw.Settlements)
            {
                var p = KwPoint(s.Uv[0], s.Uv[1]);
                bool capital = s.Type == "capital";
                var mat = new StandardMaterial3D
                {
                    ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                    BlendMode = BaseMaterial3D.BlendModeEnum.Add, BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
                    AlbedoTexture = glow, AlbedoColor = new Color(1f, 0.62f, 0.28f, 0f), DisableReceiveShadows = true,
                };
                float size = capital ? 4.5f : 2.6f;
                var g = new MeshInstance3D { Name = "Light_" + s.Id, Mesh = new QuadMesh { Size = new Vector2(size, size) }, MaterialOverride = mat,
                                             Position = p + Vector3.Up * 0.15f, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off, Visible = false };
                relief.AddChild(g);
                _lights.Add((g, mat, capital ? 1f : 0.6f));
                if (basinSites.Any(b => b.Site.Anchor == s.Id)) _basinGlows.Add(g);
                if (pinned.Contains(s.Id)) continue;
                var l = NameLabel(s.Name, capital ? 26 : 22, new Color(1f, 0.95f, 0.86f));
                l.Position = p + Vector3.Up * 0.4f;
                relief.AddChild(l);
                _names.Add((l, false));
            }
            var pinnedRealms = new HashSet<string>(_kw.Settlements.Where(s => pinned.Contains(s.Id) && s.Type == "capital").Select(s => s.Realm));
            foreach (var r in _kw.Realms)
            {
                if (pinnedRealms.Contains(r.Name)) continue;
                var l = NameLabel(string.Join(" ", r.Name.ToUpperInvariant().ToCharArray()), 24, new Color(0.98f, 0.86f, 0.62f));
                l.Position = KwPoint(r.Uv[0], r.Uv[1]) + Vector3.Up * 3.5f;
                l.Modulate = new Color(1, 1, 1, 0.85f);
                relief.AddChild(l);
                _names.Add((l, true));
            }
            if (Dunes != null) foreach (var l in Dunes.Labels) _names.Add((l, false));   // the High Dunes' market towns
            GD.Print($"[Atlas] known world loaded: {_hw}x{_hh} heights, {_kw.Settlements.Count} settlements, {_kw.Cameras.Count} views in {Time.GetTicksMsec() - t0} ms");
        }

        static Label3D NameLabel(string text, int size, Color col) => new()
        {
            Text = text, FontSize = size, OutlineSize = 10, Modulate = col, OutlineModulate = new Color(0.08f, 0.05f, 0.03f, 0.9f),
            Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, FixedSize = true, PixelSize = 0.0007f, NoDepthTest = true,
            RenderPriority = 5, OutlineRenderPriority = 4, DoubleSided = true,
        };

        static void LoadHeights()
        {
            var img = Image.LoadFromFile(Path.Combine(_kw.Directory, _kw.Height));
            img.Convert(Image.Format.Rgba8);
            _hw = img.GetWidth(); _hh = img.GetHeight();
            var px = img.GetData();
            _kwH = new float[_hw * _hh];
            for (int i = 0; i < _kwH.Length; i++)
                _kwH[i] = (float)_kw.Units(_kw.Metres(px[i * 4], px[i * 4 + 1]));
        }

        static void MakeHeightTexture()
        {
            var bytes = MemoryMarshal.AsBytes(_kwH.AsSpan()).ToArray();
            ReliefMax = _kwH.Max();
            _kwHeightTex = ImageTexture.CreateFromImage(Image.CreateFromData(_hw, _hh, false, Image.Format.Rf, bytes));
        }

        static Image LoadImage(string path)
        {
            if (!File.Exists(path)) { GD.PushWarning($"[Atlas] missing map texture {path}"); return null; }
            return Image.LoadFromFile(path);
        }

        /// <summary>The ground (blend units) at a world point: a basin's or an estate's patch, else the relief.</summary>
        public float GroundAt(double x, double y)
        {
            foreach (var b in Basins) if (b.HeightAt(x, y) is { } bh) return bh;
            foreach (var e in Estates) if (e.HeightAt(x, y) is { } eh) return eh;
            return Math.Max(0f, HeightUv((x - _kw.BoundsXy[0]) / _kw.Width, (_kw.BoundsXy[3] - y) / _kw.Depth));
        }

        static Texture2D LoadTexture(string pathOrRes)
        {
            if (pathOrRes.StartsWith("res://") && ResourceLoader.Exists(pathOrRes)) return GD.Load<Texture2D>(pathOrRes);
            var p = pathOrRes.StartsWith("res://") ? ProjectSettings.GlobalizePath(pathOrRes) : pathOrRes;
            if (!File.Exists(p)) { GD.PushWarning($"[Atlas] missing map texture {p}"); return null; }
            var img = Image.LoadFromFile(p);
            img.GenerateMipmaps();
            return ImageTexture.CreateFromImage(img);
        }

        // ---------------------------------------------------------------- frames

        /// <summary>Relief height (blend units, sea &lt; 0) at a Known World uv, bilinear.</summary>
        public float HeightUv(double u, double v)
        {
            if (_kwH == null) return 0f;
            double x = Math.Clamp(u, 0, 1) * (_hw - 1), y = Math.Clamp(v, 0, 1) * (_hh - 1);
            int x0 = (int)x, y0 = (int)y, x1 = Math.Min(x0 + 1, _hw - 1), y1 = Math.Min(y0 + 1, _hh - 1);
            float fx = (float)(x - x0), fy = (float)(y - y0);
            float a = Mathf.Lerp(_kwH[y0 * _hw + x0], _kwH[y0 * _hw + x1], fx), b = Mathf.Lerp(_kwH[y1 * _hw + x0], _kwH[y1 * _hw + x1], fx);
            return Mathf.Lerp(a, b, fy);
        }

        /// <summary>A point on the relief's surface (sea level over water) for a Known World uv.</summary>
        public Vector3 KwPoint(double u, double v)
        {
            var (x, y) = _kw.UvToXy(u, v);
            float h = HeightUv(u, v);
            foreach (var b in Basins)
                if (b.HeightAt(x, y) is { } bh) h = bh;
            foreach (var e in Estates)
                if (e.HeightAt(x, y) is { } eh) h = eh;
            return new Vector3((float)x, Math.Max(0f, h), -(float)y);
        }

        public void FlyToView(string id, double seconds = 1.6)
        {
            var v = _kw.Cameras.FirstOrDefault(x => x.Id == id);
            if (v != null) Rig.FlyTo(v.Preset, seconds);
        }

        void FillViews()
        {
            if (_views == null) return;
            _views.Clear();
            _views.AddItem("Views…");
            foreach (var v in _kw.Cameras) _views.AddItem(v.Name);
            _views.Select(0);
        }

        // ---------------------------------------------------------------- per frame

        public override void _Process(double delta)
        {
            float dt = (float)delta;
            var cam = Rig.Cam;
            cam.Near = Math.Clamp(Rig.Dist * 0.002f, 0.02f, 1.0f);
            Tod.SunLight.DirectionalShadowMaxDistance = Math.Clamp(Rig.Dist * 2.4f, 12f, 1400f);
            _lastHour = Tod.Hour;
            float night = (float)Tod.LampLevel;
            Table.Tick(dt, night);
            foreach (var e in Estates) e.SetNight((float)Tod.WindowLevel, night);
            // close to an estate the camera may come down to its miniature
            Rig.MinDist = Estates.Any(e => new Vector2(Rig.Target.X - (float)e.S.Cx, -Rig.Target.Z - (float)e.S.Cy).Length() < 1.2f) ? 0.12f
                        : Basins.Any(b => b.S.OnPlinth(Rig.Target.X, -Rig.Target.Z)) ? 0.25f : 0.8f;   // FIX(karn_ashur): down to the houses
            _fogMat.SetShaderParameter("daylight", (float)Tod.Daylight);
            _fogMat.SetShaderParameter("weather_fog", (float)_root.Weather.Current.Fog);
            float k = Math.Clamp(Rig.Dist * 0.024f, 0.03f, 16f);
            var mouse = GetViewport().GetMousePosition();
            MapPin3D hover = null;
            float best = 30f;
            foreach (var p in Pins)
            {
                p.Tick(dt, k, night, p == _hover);
                var head = p.Head;
                if (!p.Visible || cam.IsPositionBehind(head)) continue;
                float d = cam.UnprojectPosition(head).DistanceTo(mouse);
                if (d < best) { best = d; hover = p; }
            }
            if (_card != null && _card.Visible && _card.GetGlobalRect().HasPoint(mouse)) hover = _hover;
            if (hover != _hover)
            {
                _hover = hover;
                if (hover != null) ShowCard(hover); else _card.Visible = false;
                Input.SetDefaultCursorShape(hover != null ? Input.CursorShape.PointingHand : Input.CursorShape.Arrow);
            }
            if (_hover != null) PlaceCard(cam.UnprojectPosition(_hover.Head));

            Shipping.Tick(delta, Rig.Dist, night);
            float glow = (float)Math.Clamp(Tod.LampLevel * (1.0 - 0.4 * Tod.Wx.Darkness), 0, 1);
            foreach (var (g, mat, strength) in _lights)
            {
                // Karn Ashur lights its own windows and fires close up: its map glow fades out as the camera comes in
                float near = _basinGlows.Contains(g) ? Mathf.SmoothStep(5f, 16f, Rig.Dist) : 1f;
                g.Visible = glow * near > 0.01f;
                mat.AlbedoColor = new Color(1f, 0.62f, 0.28f, Math.Min(1f, glow * strength * near * 1.4f));
            }
            foreach (var b in Basins) b.Tick((float)Tod.WindowLevel, night);
            Dunes?.Tick(delta, Rig.Dist, (float)Tod.WindowLevel, night);
            Declutter(cam);
            if (!_syncing && _time != null && Tod.Speed != 0) { _syncing = true; _time.Value = Tod.Hour; _syncing = false; }
            if (_clock != null) _clock.Text = TimeOfDay.Clock(Tod.Hour);
            if (_weatherBtn != null) _weatherBtn.Text = $"Weather: {Atlas.Core.Weather.Label(_root.Weather.Kind)} {(_weatherBtn.ButtonPressed ? "▴" : "▾")}";
        }

        readonly List<Rect2> _taken = new();

        /// <summary>Show the names that fit: city pins first, then realms, then towns, skipping any that would overlap
        /// one already shown on screen.</summary>
        void Declutter(Camera3D cam)
        {
            _taken.Clear();
            var vs = GetViewport().GetVisibleRect();
            foreach (var p in Pins)
                if (p.Visible && !cam.IsPositionBehind(p.Head)) _taken.Add(LabelRect(cam.UnprojectPosition(p.Head) - new Vector2(0, 20), p.M.Name.Length, 15f));
            foreach (bool realmPass in new[] { true, false })
                foreach (var (l, realm) in _names)
                {
                    if (realm != realmPass) continue;
                    bool want = _showNames && (realm ? Rig.Dist is > 60f and < 650f : Rig.Dist < 160f) && !cam.IsPositionBehind(l.GlobalPosition);
                    if (want)
                    {
                        var r = LabelRect(cam.UnprojectPosition(l.GlobalPosition), l.Text.Length, l.FontSize * 0.42f);
                        want = vs.Intersects(r) && !_taken.Any(t => t.Intersects(r));
                        if (want) _taken.Add(r);
                    }
                    l.Visible = want;
                }
        }

        static Rect2 LabelRect(Vector2 at, int chars, float charW) => new(at.X - chars * charW / 2 - 4, at.Y - 13, chars * charW + 8, 26);

        public override void _UnhandledInput(InputEvent e)
        {
            if (e is InputEventMouseButton mb && mb.ButtonIndex == MouseButton.Left)
            {
                if (mb.DoubleClick)
                {
                    var p = Rig.Pick(mb.Position);
                    if (p.HasValue) Rig.FocusOn(p.Value);
                }
                else if (mb.Pressed) _pressAt = mb.Position;
                else if (_hover != null && mb.Position.DistanceTo(_pressAt) < 6f)
                {
                    var id = _hover.M.Id;
                    Input.SetDefaultCursorShape(Input.CursorShape.Arrow);
                    Callable.From(() => _root.OpenCity(id)).CallDeferred();
                }
            }
        }

        public override void _ExitTree()
        {
            if (Rig != null) _lastCamera = (Rig.Target, Rig.Yaw, Rig.Pitch, Rig.Dist);
            Input.SetDefaultCursorShape(Input.CursorShape.Arrow);
        }

        // ---------------------------------------------------------------- overlay

        void BuildOverlay()
        {
            _ui = new CanvasLayer { Name = "MapUI", Layer = 10 };
            AddChild(_ui);
            var title = new Label { Text = "Caelora · Turntable Atlas" };
            title.AddThemeFontSizeOverride("font_size", 30);
            title.AddThemeColorOverride("font_color", Accent);
            title.AddThemeConstantOverride("outline_size", 8);
            title.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0, 0.8f));
            title.Position = new Vector2(24, 16);
            _ui.AddChild(title);
            int n = _root.Cities.Count;
            var sub = new Label { Text = $"{n} {(n == 1 ? "city" : "cities")} · click a pin to visit" };
            sub.AddThemeConstantOverride("outline_size", 6);
            sub.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0, 0.8f));
            sub.Position = new Vector2(26, 58);
            _ui.AddChild(sub);

            // top right: weather and camera presets
            var top = new HBoxContainer { Name = "MapControls" };
            top.AddThemeConstantOverride("separation", 6);
            top.SetAnchorsPreset(Control.LayoutPreset.TopRight);
            top.GrowHorizontal = Control.GrowDirection.Begin;
            top.OffsetRight = -16; top.OffsetTop = 16;
            _views = new OptionButton { FocusMode = Control.FocusModeEnum.None, CustomMinimumSize = new Vector2(190, 0) };
            _views.ItemSelected += i =>
            {
                if (i <= 0) return;
                Rig.FlyTo(_kw.Cameras[(int)i - 1].Preset);
                _views.Select(0);
            };
            _weatherBtn = new Button { ToggleMode = true, FocusMode = Control.FocusModeEnum.None, CustomMinimumSize = new Vector2(150, 0) };
            top.AddChild(_weatherBtn);
            top.AddChild(_views);
            _ui.AddChild(top);

            // weather drop-down under the top bar
            var wbox = new PanelContainer { Name = "WeatherBox", Visible = false };
            wbox.AddThemeStyleboxOverride("panel", new StyleBoxFlat { BgColor = new Color(0.08f, 0.07f, 0.06f, 0.86f), CornerRadiusTopLeft = 8, CornerRadiusTopRight = 8,
                CornerRadiusBottomLeft = 8, CornerRadiusBottomRight = 8, ContentMarginLeft = 12, ContentMarginRight = 12, ContentMarginTop = 10, ContentMarginBottom = 10 });
            wbox.SetAnchorsPreset(Control.LayoutPreset.TopRight);
            wbox.GrowHorizontal = Control.GrowDirection.Begin;
            wbox.OffsetRight = -16; wbox.OffsetTop = 58; wbox.CustomMinimumSize = new Vector2(360, 0);
            var wcol = new VBoxContainer();
            wbox.AddChild(wcol);
            var wtitle = new Label { Text = "WEATHER" };
            wtitle.AddThemeFontSizeOverride("font_size", 13);
            wtitle.AddThemeColorOverride("font_color", Accent);
            wcol.AddChild(wtitle);
            WeatherControls = new WeatherPanel { Name = "WeatherPanel" };
            wcol.AddChild(WeatherControls);
            WeatherControls.Build(_root.Weather);
            _ui.AddChild(wbox);
            _weatherBtn.Toggled += on => wbox.Visible = on;
            if (Args.Has("weather-panel")) { _weatherBtn.ButtonPressed = true; }

            // bottom left: time of day
            var panel = new PanelContainer { Name = "TimePanel" };
            panel.AddThemeStyleboxOverride("panel", new StyleBoxFlat { BgColor = new Color(0.08f, 0.07f, 0.06f, 0.78f), CornerRadiusTopLeft = 8, CornerRadiusTopRight = 8,
                CornerRadiusBottomLeft = 8, CornerRadiusBottomRight = 8, ContentMarginLeft = 10, ContentMarginRight = 10, ContentMarginTop = 6, ContentMarginBottom = 6 });
            panel.SetAnchorsPreset(Control.LayoutPreset.BottomLeft);
            panel.GrowVertical = Control.GrowDirection.Begin;
            panel.OffsetLeft = 16; panel.OffsetTop = -84; panel.OffsetBottom = -40;
            var row = new HBoxContainer();
            row.AddThemeConstantOverride("separation", 10);
            panel.AddChild(row);
            _clock = new Label { Text = TimeOfDay.Clock(Tod.Hour), CustomMinimumSize = new Vector2(52, 0) };
            _clock.AddThemeColorOverride("font_color", Accent);
            row.AddChild(_clock);
            _time = new HSlider { MinValue = 0, MaxValue = 24, Step = 0.05, Value = Tod.Hour, CustomMinimumSize = new Vector2(260, 0), FocusMode = Control.FocusModeEnum.None };
            _time.ValueChanged += v => { if (_syncing) return; Tod.Hour = v; Tod.Apply(); };
            row.AddChild(_time);
            _play = new Button { Text = "▶ Play", ToggleMode = true, FocusMode = Control.FocusModeEnum.None };
            _play.Toggled += on => { Tod.Speed = on ? 0.4 : 0; _play.Text = on ? "❚❚ Pause" : "▶ Play"; };
            row.AddChild(_play);
            var names = new CheckBox { Text = "Names", ButtonPressed = true, FocusMode = Control.FocusModeEnum.None };
            names.Toggled += on => _showNames = on;
            row.AddChild(names);
            _ui.AddChild(panel);

            var hint = new Label { Text = "Drag: orbit · Right-drag: pan · Scroll / Q E: zoom · W S: up/down · A D: orbit · Double-click: focus · F: free-fly" };
            hint.AddThemeFontSizeOverride("font_size", 13);
            hint.AddThemeColorOverride("font_color", new Color(1, 1, 1, 0.75f));
            hint.AddThemeConstantOverride("outline_size", 5);
            hint.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0, 0.7f));
            hint.SetAnchorsPreset(Control.LayoutPreset.BottomLeft);
            hint.OffsetLeft = 18; hint.OffsetTop = -30;
            _ui.AddChild(hint);
            BuildCard();
        }

        void BuildCard()
        {
            _card = new PanelContainer { Visible = false, MouseFilter = Control.MouseFilterEnum.Ignore };
            _card.AddThemeStyleboxOverride("panel", new StyleBoxFlat { BgColor = new Color(0.08f, 0.07f, 0.06f, 0.92f), CornerRadiusTopLeft = 8, CornerRadiusTopRight = 8,
                CornerRadiusBottomLeft = 8, CornerRadiusBottomRight = 8, ContentMarginLeft = 10, ContentMarginRight = 10, ContentMarginTop = 8, ContentMarginBottom = 8,
                BorderColor = Accent, BorderWidthBottom = 1, BorderWidthTop = 1, BorderWidthLeft = 1, BorderWidthRight = 1 });
            var col = new VBoxContainer { MouseFilter = Control.MouseFilterEnum.Ignore };
            _card.AddChild(col);
            _cardThumb = new TextureRect { CustomMinimumSize = new Vector2(320, 160), ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                                           StretchMode = TextureRect.StretchModeEnum.KeepAspectCovered, MouseFilter = Control.MouseFilterEnum.Ignore };
            col.AddChild(_cardThumb);
            _cardTitle = new Label();
            _cardTitle.AddThemeFontSizeOverride("font_size", 20);
            _cardTitle.AddThemeColorOverride("font_color", Accent);
            col.AddChild(_cardTitle);
            _cardInfo = new Label { CustomMinimumSize = new Vector2(320, 0), AutowrapMode = TextServer.AutowrapMode.WordSmart };
            col.AddChild(_cardInfo);
            _ui.AddChild(_card);
        }

        void ShowCard(MapPin3D pin)
        {
            var m = pin.M;
            var thumb = m.Files.TryGetValue("thumb", out var t) ? Path.Combine(m.Directory, t) : null;
            _cardThumb.Texture = thumb != null && File.Exists(thumb) ? ImageTexture.CreateFromImage(Image.LoadFromFile(thumb)) : null;
            _cardTitle.Text = m.Name;
            var events = string.Join(", ", m.Events.Select(e => e.Replace('_', ' ')));
            _cardInfo.Text = $"{Math.Abs(m.Sun.LatitudeDeg):0}°{(m.Sun.LatitudeDeg >= 0 ? "N" : "S")} · {m.Venues.Count} venues · seats {m.Venues.Sum(v => v.Capacity):N0}\nEvents: {events}\nClick to visit";
            _card.Visible = true;
        }

        void PlaceCard(Vector2 at)
        {
            var vs = GetViewport().GetVisibleRect().Size;
            var size = _card.GetCombinedMinimumSize();
            var p = at + new Vector2(26, -size.Y / 2);
            if (p.X + size.X > vs.X - 10) p.X = at.X - size.X - 26;
            p.Y = Math.Clamp(p.Y, 10, Math.Max(10, vs.Y - size.Y - 10));
            _card.Position = p;
        }
    }

    /// <summary>A city pin standing on the map: a bronze pole, a glowing gold head, a pulsing ring and the name.
    /// It keeps its size on screen as the camera zooms (WorldMap scales it with the orbit distance).</summary>
    public partial class MapPin3D : Node3D
    {
        public CityManifest M { get; private set; }
        StandardMaterial3D _headMat, _ringMat;
        MeshInstance3D _ring;
        Node3D _body;
        Label3D _label;
        float _t;

        public Vector3 Head => GlobalPosition + Vector3.Up * _body.Scale.Y;

        public void Build(CityManifest m)
        {
            M = m;
            var gold = new Color(0.92f, 0.66f, 0.28f);
            _body = new Node3D { Name = "Body" };
            AddChild(_body);
            _body.AddChild(new MeshInstance3D
            {
                Name = "Pole", Mesh = new CylinderMesh { TopRadius = 0.04f, BottomRadius = 0.07f, Height = 0.9f, RadialSegments = 10 },
                Position = new Vector3(0, 0.46f, 0),
                MaterialOverride = new StandardMaterial3D { AlbedoColor = new Color(0.32f, 0.2f, 0.1f), Metallic = 0.6f, Roughness = 0.4f },
            });
            _headMat = new StandardMaterial3D { AlbedoColor = gold, Metallic = 0.4f, Roughness = 0.35f, EmissionEnabled = true, Emission = gold, EmissionEnergyMultiplier = 0.6f };
            _body.AddChild(new MeshInstance3D { Name = "Head", Mesh = new SphereMesh { Radius = 0.24f, Height = 0.48f }, Position = new Vector3(0, 1f, 0), MaterialOverride = _headMat });
            _ringMat = new StandardMaterial3D { ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                                                AlbedoColor = new Color(gold, 0.6f), DisableReceiveShadows = true };
            _ring = new MeshInstance3D { Name = "Ring", Mesh = new TorusMesh { InnerRadius = 0.5f, OuterRadius = 0.6f, Rings = 32, RingSegments = 6 },
                                         Position = new Vector3(0, 0.02f, 0), MaterialOverride = _ringMat, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off };
            _body.AddChild(_ring);
            // the name is not scaled with the body: a fixed-size label stays the same size on screen
            _label = new Label3D
            {
                Name = "Name", Text = m.Name, FontSize = 34, OutlineSize = 12, PixelSize = 0.0007f, FixedSize = true,
                Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, NoDepthTest = true, RenderPriority = 10, OutlineRenderPriority = 9,
                Modulate = new Color(1f, 0.92f, 0.75f), OutlineModulate = new Color(0.1f, 0.06f, 0.03f, 0.95f),
                Position = new Vector3(0, 1.22f, 0),
            };
            AddChild(_label);
        }

        public void Tick(float dt, float scale, float night, bool hovered)
        {
            _t += dt;
            float k = scale * (hovered ? 1.15f : 1f);
            _body.Scale = Vector3.One * k;
            _label.Position = new Vector3(0, 1.3f * k, 0);
            float pulse = (_t * 0.7f) % 1f;
            _ring.Scale = Vector3.One * (1f + 1.6f * pulse);
            _ringMat.AlbedoColor = new Color(0.95f, 0.72f, 0.38f, 0.6f * (1f - pulse));
            _headMat.EmissionEnergyMultiplier = 0.5f + 2.5f * night + (hovered ? 1.5f : 0f);
        }
    }
}
