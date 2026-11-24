// The Caelora world map in 3D. Two maps share one world frame, KnownWorld.blend's (1 unit = 10 miles, +X east,
// Godot -Z north, sea level 0):
//   Known World  the relief baked from the blend (tools/bake_known_world.py): its ground colour unlit on its own
//                elevation at the blend's 15x exaggeration, sea surface at 0, the blend's CAM_* cameras as views.
//   Geography    the painted Caelora map lying flat on a board, over Caelora's place on the relief, so switching
//                (M, or the buttons) keeps the camera on the same spot.
// The city view's orbit / pan / zoom rig, the shared weather (volumetric clouds, their shadows, wet ground) and time
// of day. One pin per city package (city.json world_map): hover shows its card, click opens the city.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public enum MapMode { Geography, KnownWorld }

    public partial class WorldMap : Node3D
    {
        // kept between visits (the map is rebuilt each time a city closes)
        public static MapMode LastMode = MapMode.KnownWorld;
        static readonly Dictionary<MapMode, (Vector3 T, float Y, float P, float D)> LastCam = new();
        static double _lastHour = 16.5;
        static Texture2D _geoTex, _kwTex;
        static ImageTexture _kwHeightTex;
        static float[] _kwH;
        static int _hw, _hh;
        static KnownWorldMap _kw;

        const string GeoPath = "res://assets/map/Caelora_Geography.png";
        const string KwJson = "res://assets/map/known_world/known_world.json";
        static readonly Color Accent = new(0.95f, 0.72f, 0.38f);

        AtlasRoot _root;
        public MapMode Mode { get; private set; }
        public TurntableCamera Rig { get; private set; }
        public TimeOfDay Tod { get; private set; }
        public WeatherView Weather { get; private set; }
        public KnownWorldMap Kw => _kw;
        public bool KnownWorldLoaded => _kwRoot != null;
        /// <summary>Highest point of the relief (blend units).</summary>
        public static float ReliefMax { get; private set; }
        public readonly List<MapPin3D> Pins = new();
        public event Action<MapMode> ModeChanged;

        Node3D _geoRoot, _kwRoot;
        public MapTable Table { get; private set; }
        StaticBody3D _geoBody, _kwBody;
        ShaderMaterial _paperMat, _reliefMat;
        Vector2 _geoCenter;              // blend xy of the painted map's centre
        float _geoW, _geoD;              // its size in blend units
        readonly List<(MeshInstance3D Glow, StandardMaterial3D Mat, float K)> _lights = new();
        readonly List<(Label3D L, bool Realm)> _names = new();
        bool _showNames = true;

        // overlay
        CanvasLayer _ui;
        Button _geoBtn, _kwBtn;
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
            if (Args.Has("map-mode")) LastMode = Args.Get("map-mode") is "known_world" or "kw" ? MapMode.KnownWorld : MapMode.Geography;

            // the painted map's place in the world: its centre carried onto the relief, its width from the affine
            var (cu, cv) = _kw.FromGeo(0.5, 0.5);
            var c = _kw.UvToXy(cu, cv);
            _geoCenter = new Vector2((float)c.X, (float)c.Y);
            _geoTex ??= LoadTexture(GeoPath);
            var gs = _geoTex?.GetSize() ?? new Vector2(3278, 1920);
            _geoW = (float)(_kw.Width * _kw.GeoToKw[0][0]);
            _geoD = _geoW * gs.Y / gs.X;

            Tod = new TimeOfDay { Name = "TimeOfDay", FogScale = 0.3f, Room = MapTable.RoomColor };
            AddChild(Tod);
            Tod.Setup(null, new SunDefaults { LatitudeDeg = 38, DefaultDayOfYear = 172, NorthOffsetDeg = 0 });
            Tod.Hour = Args.Has("hour") ? Args.F("hour", 16.5f) : _lastHour;
            Tod.Apply();

            Table = new MapTable();
            AddChild(Table);
            Table.Build(new Rect2((float)_kw.BoundsXy[0], -(float)_kw.BoundsXy[3], (float)_kw.Width, (float)_kw.Depth),
                        new Rect2(_geoCenter.X - _geoW / 2, -_geoCenter.Y - _geoD / 2, _geoW, _geoD));
            _paperMat = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/paper_map.gdshader") };
            _paperMat.SetShaderParameter("map_tex", _geoTex);
            _reliefMat = new ShaderMaterial { Shader = ResourceLoader.Load<Shader>("res://shaders/relief.gdshader") };
            BuildGeography();

            Rig = new TurntableCamera { Name = "Rig", MinDist = 0.8f, MaxDist = 950f, MinPitch = 5f, FlySpeed = 4f };
            AddChild(Rig);
            Rig.Cam.Far = 8000f;

            Weather = new WeatherView { Name = "Weather" };
            AddChild(Weather);
            float cx = (float)(_kw.BoundsXy[0] + _kw.Width / 2), cy = (float)(_kw.BoundsXy[1] + _kw.Depth / 2);
            Weather.Setup(root.Weather, Tod,
                new CloudScale { Base = 9, Top = 21, Center = new Vector2(cx, -cy), Half = new Vector2((float)_kw.Width / 2, (float)_kw.Depth / 2)   /* W1: clouds stay over the map, not the table */,
                                 Cell = 230, Shape = 20, Detail = 5.5f, NearFade = 1.5f, Edge = 45, FlashR = 30 },
                new[] { _paperMat, _reliefMat }, false, () => Rig.Target,
                () => Math.Clamp(Math.Abs(Tod.Speed) * 60, 1.0, 20.0));

            foreach (var m in root.Cities)
            {
                var pin = new MapPin3D { Name = "Pin_" + m.Id };
                AddChild(pin);
                pin.Build(m);
                Pins.Add(pin);
            }
            BuildOverlay();
            SetMode(LastMode, restore: true);
            if (Args.Has("view")) FlyToView(Args.Get("view"), 0.01);
        }

        // ---------------------------------------------------------------- scene

        void BuildGeography()
        {
            _geoRoot = new Node3D { Name = "Geography" };
            AddChild(_geoRoot);
            var at = new Vector3(_geoCenter.X, 0, -_geoCenter.Y);
            var boardSize = new Vector3(_geoW + 2.5f, 0.8f, _geoD + 2.5f);
            _geoRoot.AddChild(new MeshInstance3D
            {
                Name = "Paper", Mesh = new PlaneMesh { Size = new Vector2(_geoW, _geoD) }, Position = at + new Vector3(0, 0.02f, 0),
                MaterialOverride = _paperMat, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            });
            _geoBody = new StaticBody3D { Name = "GeoCollision", CollisionLayer = CityLoader.CollisionLayer, CollisionMask = 0 };
            _geoBody.AddChild(new CollisionShape3D { Shape = new BoxShape3D { Size = boardSize }, Position = at + new Vector3(0, -0.38f, 0) });
            _geoRoot.AddChild(_geoBody);
        }

        void EnsureKnownWorld()
        {
            if (_kwRoot != null) return;
            ulong t0 = Time.GetTicksMsec();
            _kwTex ??= LoadTexture(Path.Combine(_kw.Directory, _kw.Albedo));
            if (_kwH == null) LoadHeights();
            _reliefMat.SetShaderParameter("albedo_tex", _kwTex);
            _reliefMat.SetShaderParameter("height_tex", _kwHeightTex);
            _reliefMat.SetShaderParameter("size", new Vector2((float)_kw.Width, (float)_kw.Depth));
            _reliefMat.SetShaderParameter("texel", new Vector2(1f / _hw, 1f / _hh));

            _kwRoot = new Node3D { Name = "KnownWorld" };
            AddChild(_kwRoot);
            float cx = (float)(_kw.BoundsXy[0] + _kw.Width / 2), cy = (float)(_kw.BoundsXy[1] + _kw.Depth / 2);
            var at = new Vector3(cx, 0, -cy);
            var mesh = new PlaneMesh { Size = new Vector2((float)_kw.Width, (float)_kw.Depth), SubdivideWidth = 1023, SubdivideDepth = 533 };
            mesh.CustomAabb = new Aabb(new Vector3(-(float)_kw.Width / 2, -1, -(float)_kw.Depth / 2), new Vector3((float)_kw.Width, 12, (float)_kw.Depth));
            _kwRoot.AddChild(new MeshInstance3D { Name = "Relief", Mesh = mesh, Position = at, MaterialOverride = _reliefMat });

            // collision at one sample per unit: keeps the camera above the mountains, double-click focus
            int cols = (int)Math.Round(_kw.Width) + 1, rows = (int)Math.Round(_kw.Depth) + 1;
            var data = new float[cols * rows];
            for (int r = 0; r < rows; r++)
                for (int c = 0; c < cols; c++)
                    data[r * cols + c] = Math.Max(0f, HeightUv(c / (double)(cols - 1), r / (double)(rows - 1)));
            _kwBody = new StaticBody3D { Name = "KwCollision", CollisionLayer = CityLoader.CollisionLayer, CollisionMask = 0 };
            _kwBody.AddChild(new CollisionShape3D
            {
                Shape = new HeightMapShape3D { MapWidth = cols, MapDepth = rows, MapData = data },
                Position = at, Scale = new Vector3((float)_kw.Width / (cols - 1), 1, (float)_kw.Depth / (rows - 1)),
            });
            _kwRoot.AddChild(_kwBody);

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
                _kwRoot.AddChild(g);
                _lights.Add((g, mat, capital ? 1f : 0.6f));
                if (pinned.Contains(s.Id)) continue;
                var l = NameLabel(s.Name, capital ? 26 : 22, new Color(1f, 0.95f, 0.86f));
                l.Position = p + Vector3.Up * 0.4f;
                _kwRoot.AddChild(l);
                _names.Add((l, false));
            }
            var pinnedRealms = new HashSet<string>(_kw.Settlements.Where(s => pinned.Contains(s.Id) && s.Type == "capital").Select(s => s.Realm));
            foreach (var r in _kw.Realms)
            {
                if (pinnedRealms.Contains(r.Name)) continue;
                var l = NameLabel(string.Join(" ", r.Name.ToUpperInvariant().ToCharArray()), 24, new Color(0.98f, 0.86f, 0.62f));
                l.Position = KwPoint(r.Uv[0], r.Uv[1]) + Vector3.Up * 3.5f;
                l.Modulate = new Color(1, 1, 1, 0.85f);
                _kwRoot.AddChild(l);
                _names.Add((l, true));
            }
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
            var bytes = MemoryMarshal.AsBytes(_kwH.AsSpan()).ToArray();
            ReliefMax = _kwH.Max();
            _kwHeightTex = ImageTexture.CreateFromImage(Image.CreateFromData(_hw, _hh, false, Image.Format.Rf, bytes));
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
            return new Vector3((float)x, Math.Max(0f, HeightUv(u, v)), -(float)y);
        }

        /// <summary>A point on the painted map for a Geography uv.</summary>
        public Vector3 GeoPoint(double u, double v) =>
            new(_geoCenter.X + (float)(u - 0.5) * _geoW, 0.03f, -(_geoCenter.Y - (float)(v - 0.5) * _geoD));

        (double U, double V) GeoUvAt(Vector3 p) => (0.5 + (p.X - _geoCenter.X) / _geoW, 0.5 + (_geoCenter.Y + p.Z) / _geoD);

        Vector3 Carry(Vector3 t, MapMode from, MapMode to)
        {
            if (from == to) return t;
            if (from == MapMode.Geography)
            {
                var (gu, gv) = GeoUvAt(t);
                var (ku, kv) = _kw.FromGeo(gu, gv);
                return KwPoint(ku, kv);
            }
            var (u, v) = _kw.XyToUv(t.X, -t.Z);
            var g = _kw.ToGeo(u, v);
            return GeoPoint(g.U, g.V) with { Y = 0 };
        }

        Vector3 PinPoint(MapPin3D pin)
        {
            var w = pin.M.WorldMap;
            if (Mode == MapMode.Geography)
                return w?.PinUv is { Length: 2 } ? GeoPoint(w.PinUv[0], w.PinUv[1]) : GeoPoint(0.5, 0.5);
            var uv = _kw.PinFor(w);
            return uv.HasValue ? KwPoint(uv.Value.U, uv.Value.V) : KwPoint(0.5, 0.5);
        }

        // ---------------------------------------------------------------- modes and views

        public void SetMode(MapMode mode, bool restore = false)
        {
            var prev = Mode;
            bool first = restore;
            if (mode == MapMode.KnownWorld) EnsureKnownWorld();
            if (!first) LastCam[prev] = (Rig.Target, Rig.Yaw, Rig.Pitch, Rig.Dist);
            Mode = LastMode = mode;
            bool kw = mode == MapMode.KnownWorld;
            _geoRoot.Visible = !kw;
            Table.SetMode(kw);
            _geoBody.CollisionLayer = kw ? 0 : CityLoader.CollisionLayer;
            if (_kwRoot != null)
            {
                _kwRoot.Visible = kw;
                _kwBody.CollisionLayer = kw ? CityLoader.CollisionLayer : 0;
            }
            if (kw) Rig.Bounds = new Rect2((float)_kw.BoundsXy[0], -(float)_kw.BoundsXy[3], (float)_kw.Width, (float)_kw.Depth);
            else Rig.Bounds = new Rect2(_geoCenter.X - _geoW / 2, -_geoCenter.Y - _geoD / 2, _geoW, _geoD);
            foreach (var p in Pins)
            {
                p.Position = PinPoint(p);
                p.Visible = kw || p.M.WorldMap?.PinUv is { Length: 2 };   // cities off Caelora are only on the relief
            }

            if (first && LastCam.TryGetValue(mode, out var c)) Rig.Snap(c.T, c.Y, c.P, c.D);
            else if (first) DefaultView();
            else Rig.Snap(Carry(Rig.Target, prev, mode), Rig.Yaw, Rig.Pitch, Rig.Dist);
            if (_geoBtn != null) { _geoBtn.SetPressedNoSignal(!kw); _kwBtn.SetPressedNoSignal(kw); }
            FillViews();
            ModeChanged?.Invoke(mode);
            GD.Print($"[Atlas] map mode {mode}");
        }

        void DefaultView()
        {
            if (Mode == MapMode.KnownWorld && _kw.Cameras.Count > 0) { var v = _kw.Cameras[0]; Rig.Snap(Geo.V(v.Target), (float)v.Yaw, (float)v.Pitch, (float)v.Dist); }
            else Rig.Snap(new Vector3(_geoCenter.X, 0, -_geoCenter.Y + _geoD * 0.05f), -90f, 58f, _geoW * 1.02f);
        }

        IEnumerable<(string Id, string Name, CameraPreset P)> Views()
        {
            if (Mode == MapMode.KnownWorld)
                foreach (var c in _kw.Cameras) yield return (c.Id, c.Name, c.Preset);
            else
            {
                yield return ("overview", "Overview", new CameraPreset { Target = new double[] { _geoCenter.X, _geoCenter.Y - _geoD * 0.05, 0 }, Yaw = -90, Pitch = 58, Dist = _geoW * 1.02 });
                yield return ("top", "From above", new CameraPreset { Target = new double[] { _geoCenter.X, _geoCenter.Y, 0 }, Yaw = -90, Pitch = 89, Dist = _geoW * 1.1 });
                foreach (var p in Pins.Where(p => p.Visible))
                {
                    var at = PinPoint(p);
                    yield return ("city:" + p.M.Id, p.M.Name, new CameraPreset { Target = new double[] { at.X, -at.Z, 0 }, Yaw = -100, Pitch = 40, Dist = 32 });
                }
            }
        }

        public void FlyToView(string id, double seconds = 1.6)
        {
            var v = Views().FirstOrDefault(x => x.Id == id);
            if (v.P != null) Rig.FlyTo(v.P, seconds);
        }

        void FillViews()
        {
            if (_views == null) return;
            _views.Clear();
            _views.AddItem("Views…");
            foreach (var v in Views()) _views.AddItem(v.Name);
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

            if (Mode == MapMode.KnownWorld && _kwRoot != null)
            {
                float w = (float)Math.Clamp(Tod.LampLevel * (1.0 - 0.4 * Tod.Wx.Darkness), 0, 1);
                foreach (var (g, mat, kk) in _lights)
                {
                    g.Visible = w > 0.01f;
                    mat.AlbedoColor = new Color(1f, 0.62f, 0.28f, Math.Min(1f, w * kk * 1.4f));
                }
                Declutter(cam);
            }
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
            else if (e is InputEventKey k && k.Pressed && !k.Echo && k.Keycode == Key.M)
                SetMode(Mode == MapMode.Geography ? MapMode.KnownWorld : MapMode.Geography);
        }

        public override void _ExitTree()
        {
            if (Rig != null) LastCam[Mode] = (Rig.Target, Rig.Yaw, Rig.Pitch, Rig.Dist);
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

            // top right: which map, and the views
            var top = new HBoxContainer { Name = "MapSwitch" };
            top.AddThemeConstantOverride("separation", 6);
            top.SetAnchorsPreset(Control.LayoutPreset.TopRight);
            top.GrowHorizontal = Control.GrowDirection.Begin;
            top.OffsetRight = -16; top.OffsetTop = 16;
            var group = new ButtonGroup();
            _geoBtn = new Button { Text = "Geography", ToggleMode = true, ButtonGroup = group, FocusMode = Control.FocusModeEnum.None };
            _kwBtn = new Button { Text = "Known World", ToggleMode = true, ButtonGroup = group, FocusMode = Control.FocusModeEnum.None };
            _geoBtn.Pressed += () => { if (Mode != MapMode.Geography) SetMode(MapMode.Geography); };
            _kwBtn.Pressed += () => { if (Mode != MapMode.KnownWorld) SetMode(MapMode.KnownWorld); };
            _views = new OptionButton { FocusMode = Control.FocusModeEnum.None, CustomMinimumSize = new Vector2(190, 0) };
            _views.ItemSelected += i =>
            {
                if (i <= 0) return;
                var v = Views().ElementAtOrDefault((int)i - 1);
                if (v.P != null) Rig.FlyTo(v.P);
                _views.Select(0);
            };
            _weatherBtn = new Button { ToggleMode = true, FocusMode = Control.FocusModeEnum.None, CustomMinimumSize = new Vector2(150, 0) };
            top.AddChild(_weatherBtn);
            top.AddChild(_views);
            top.AddChild(_geoBtn);
            top.AddChild(_kwBtn);
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

            var hint = new Label { Text = "Drag: orbit · Right-drag: pan · Scroll / Q E: zoom · W S: up/down · A D: orbit · Double-click: focus · M: switch map · F: free-fly" };
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
