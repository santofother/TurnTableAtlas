// W1: the war table the world maps lie on, in the manner of a strategy-game map room. A walnut table top running
// into a dark room, a carved, stepped frame with a gold inlay and brass-capped corner blocks round each map (the
// Known World relief gets a parchment margin inside its frame), and props on the table: candles that light at night,
// a brass compass rose, a rolled chart, wooden markers, and brass weights on the corners of the painted map.
// Everything is sized from the map so the same builder works for both frames. World frame: Godot (x, y up, -z north),
// sea level / map surface at y = 0, table top at y = TableY.
using System;
using System.Collections.Generic;
using Godot;

namespace Atlas
{
    public partial class MapTable : Node3D
    {
        public const float TableY = -0.8f;
        static readonly Color Brass = new(0.78f, 0.58f, 0.26f), Gold = new(0.95f, 0.74f, 0.33f);
        static readonly Color Room = new(0.025f, 0.017f, 0.012f);

        Node3D _kwFrame, _geoFrame;
        StaticBody3D _kwBody, _geoBody;
        ShaderMaterial _wood, _frameWood, _darkWood;
        StandardMaterial3D _brass, _gold, _wax, _parchment;
        readonly List<(OmniLight3D L, MeshInstance3D Flame, StandardMaterial3D M, float Phase)> _candles = new();
        float _t;

        public static Color RoomColor => Room;
        public int CandleCount => _candles.Count;

        /// <param name="kw">Known World bounds in Godot xz (position = west / north corner).</param>
        /// <param name="geo">The painted map's rectangle in Godot xz.</param>
        public void Build(Rect2 kw, Rect2 geo)
        {
            Name = "MapTable";
            var shader = ResourceLoader.Load<Shader>("res://shaders/map_table.gdshader");
            var c = kw.GetCenter();
            float span = Math.Max(kw.Size.X, kw.Size.Y);
            _wood = Wood(shader, new Color(0.36f, 0.21f, 0.12f), new Color(0.13f, 0.07f, 0.04f), span * 0.04f, 1f, 0.5f);
            _wood.SetShaderParameter("vignette", 1.0f);
            _wood.SetShaderParameter("centre", c);
            _wood.SetShaderParameter("half_size", kw.Size * 0.5f);
            _wood.SetShaderParameter("room", Room);
            _frameWood = Wood(shader, new Color(0.30f, 0.16f, 0.08f), new Color(0.09f, 0.045f, 0.025f), 1e5f, 3f, 0.38f);
            _darkWood = Wood(shader, new Color(0.17f, 0.09f, 0.05f), new Color(0.06f, 0.03f, 0.02f), 1e5f, 3f, 0.42f);
            _brass = new StandardMaterial3D { AlbedoColor = Brass, Metallic = 1f, Roughness = 0.32f };
            _gold = new StandardMaterial3D { AlbedoColor = Gold, Metallic = 1f, Roughness = 0.22f };
            _wax = new StandardMaterial3D { AlbedoColor = new Color(0.93f, 0.86f, 0.72f), Roughness = 0.45f,
                                            SubsurfScatterEnabled = true, SubsurfScatterStrength = 0.6f };
            _parchment = new StandardMaterial3D
            {
                AlbedoColor = new Color(0.86f, 0.75f, 0.55f), Roughness = 0.9f,
                AlbedoTexture = new NoiseTexture2D
                {
                    Width = 512, Height = 512, Seamless = true,
                    Noise = new FastNoiseLite { NoiseType = FastNoiseLite.NoiseTypeEnum.Perlin, Frequency = 0.02f, FractalOctaves = 5 },
                    ColorRamp = new Gradient { Colors = new[] { new Color(0.62f, 0.47f, 0.28f), new Color(0.95f, 0.88f, 0.70f) }, Offsets = new[] { 0f, 1f } },
                },
                Uv1Triplanar = true, Uv1Scale = Vector3.One / (span * 0.03f), Uv1WorldTriplanar = true,
            };

            // the table: one big slab whose top fades into the room
            AddChild(new MeshInstance3D
            {
                Name = "TableTop", Mesh = new BoxMesh { Size = new Vector3(span * 9, 4, span * 9) },
                Position = new Vector3(c.X, TableY - 2, c.Y), MaterialOverride = _wood,
            });

            // Known World: parchment margin, then the frame
            float margin = span * 0.012f, rim = span * 0.03f;
            _kwFrame = new Node3D { Name = "KnownWorldFrame" };
            AddChild(_kwFrame);
            var inner = kw.Grow(margin);
            Ring(_kwFrame, kw.Grow(-0.3f), margin + 0.3f, -0.05f, TableY - 0.05f, _parchment);   // under the relief's edge
            _kwBody = Frame(_kwFrame, inner, rim, 3.0f);

            // Geography: the painted map on its own frame (the board it used to lie on)
            float grim = Math.Max(geo.Size.X, geo.Size.Y) * 0.022f;
            _geoFrame = new Node3D { Name = "GeographyFrame" };
            AddChild(_geoFrame);
            Box(_geoFrame, "Base", new Vector3(geo.Size.X + 0.2f, -TableY, geo.Size.Y + 0.2f), new Vector3(geo.GetCenter().X, TableY / 2, geo.GetCenter().Y), _darkWood);
            _geoBody = Frame(_geoFrame, geo.Grow(0.05f), grim, Math.Max(0.6f, grim * 0.12f));
            float wr = grim * 0.55f;
            foreach (var (x, z) in Corners(geo.Grow(-wr * 1.6f)))
            {
                var wgt = new Node3D { Position = new Vector3(x, 0.03f, z) };
                _geoFrame.AddChild(wgt);
                Cyl(wgt, wr, wr * 0.7f, wr * 0.35f, _brass);
                Cyl(wgt, wr * 0.3f, wr * 0.3f, wr * 0.9f, _brass, wr * 0.7f);
                Sphere(wgt, wr * 0.32f, wr * 1.65f, _gold);
            }

            // props on the table, outside the Known World frame so they show in both modes
            var outer = inner.Grow(rim);
            float u = span * 0.01f;   // prop unit (~7 on the Known World)
            var ne = new Vector2(outer.End.X, outer.Position.Y);
            var se = outer.End;
            var sw = new Vector2(outer.Position.X, outer.End.Y);
            var nw = outer.Position;
            Candles(nw + new Vector2(-4 * u, -3 * u), u, new[] { 1.0f, 0.7f, 1.35f });
            Candles(ne + new Vector2(4 * u, -3 * u), u, new[] { 1.2f, 0.85f });
            Candles(se + new Vector2(5 * u, 4 * u), u, new[] { 0.9f, 1.4f, 0.6f });
            Compass(sw + new Vector2(-6 * u, 5 * u), u * 3.2f);
            Scroll(new Vector2(c.X + outer.Size.X * 0.22f, outer.End.Y + 4 * u), u);
            Markers(new Vector2(c.X - outer.Size.X * 0.28f, outer.End.Y + 4.5f * u), u);
            GD.Print($"[Atlas] map table: frame {inner.Size.X:0}x{inner.Size.Y:0}, painted map {geo.Size.X:0}x{geo.Size.Y:0}, {_candles.Count} candles");
        }

        public void SetMode(bool knownWorld)
        {
            _kwFrame.Visible = knownWorld;
            _geoFrame.Visible = !knownWorld;
            _kwBody.CollisionLayer = knownWorld ? CityLoader.CollisionLayer : 0;
            _geoBody.CollisionLayer = knownWorld ? 0 : CityLoader.CollisionLayer;
        }

        /// <summary>Candle flicker; their light comes up with the lamps.</summary>
        public void Tick(float dt, float lamp)
        {
            _t += dt;
            foreach (var (l, f, m, ph) in _candles)
            {
                float fl = 0.88f + 0.08f * Mathf.Sin(_t * 9.1f + ph) + 0.04f * Mathf.Sin(_t * 23.7f + ph * 2f);
                l.LightEnergy = (0.15f + 2.6f * lamp) * fl;
                m.AlbedoColor = new Color(1f, 0.66f, 0.30f, Math.Min(1f, 0.55f + 0.45f * lamp) * fl);
                f.Scale = new Vector3(1, fl, 1);
            }
        }

        // ---------------------------------------------------------------- pieces

        static ShaderMaterial Wood(Shader s, Color tint, Color dark, float plank, float grain, float rough)
        {
            var m = new ShaderMaterial { Shader = s };
            m.SetShaderParameter("tint", tint);
            m.SetShaderParameter("dark", dark);
            m.SetShaderParameter("plank", plank);
            m.SetShaderParameter("grain_scale", grain);
            m.SetShaderParameter("roughness_base", rough);
            return m;
        }

        /// <summary>A stepped, carved frame round <paramref name="r"/>: plinth, moulding with a gold inlay, a raised
        /// inner lip, and corner blocks with brass caps. Returns its collision body.</summary>
        StaticBody3D Frame(Node3D parent, Rect2 r, float w, float h)
        {
            var body = new StaticBody3D { Name = "FrameCollision", CollisionLayer = CityLoader.CollisionLayer, CollisionMask = 0 };
            parent.AddChild(body);
            Ring(parent, r, w, h * 0.35f, TableY, _frameWood, body);                         // plinth
            Ring(parent, r, w * 0.30f, h, h * 0.35f, _frameWood, body);          // raised inner lip
            Ring(parent, r.Grow(w * 0.42f), w * 0.40f, h * 0.70f, h * 0.35f, _darkWood);   // outer moulding
            Ring(parent, r.Grow(w * 0.33f), w * 0.05f, h * 0.38f, h * 0.35f, _gold);         // gold inlay in the groove
            Ring(parent, r, w * 0.06f, h * 1.04f, h, _gold);                                 // gilt edge on the lip
            float cb = w * 1.25f;
            foreach (var (x, z) in Corners(r.Grow(w / 2)))
            {
                Box(parent, "Corner", new Vector3(cb, h * 1.35f - TableY, cb), new Vector3(x, (h * 1.35f + TableY) / 2, z), _darkWood);
                var cap = new Node3D { Position = new Vector3(x, h * 1.35f, z) };
                parent.AddChild(cap);
                Cyl(cap, cb * 0.36f, cb * 0.42f, cb * 0.08f, _brass);
                Sphere(cap, cb * 0.2f, cb * 0.12f, _gold);
            }
            return body;
        }

        /// <summary>A rectangular ring of width <paramref name="w"/> just outside <paramref name="r"/>, from y0 to y1.</summary>
        static void Ring(Node3D parent, Rect2 r, float w, float y1, float y0, Material mat, StaticBody3D body = null)
        {
            float h = y1 - y0, y = (y1 + y0) / 2;
            var c = r.GetCenter();
            var parts = new (Vector3 Size, Vector3 At)[]
            {
                (new Vector3(r.Size.X + 2 * w, h, w), new Vector3(c.X, y, r.Position.Y - w / 2)),
                (new Vector3(r.Size.X + 2 * w, h, w), new Vector3(c.X, y, r.End.Y + w / 2)),
                (new Vector3(w, h, r.Size.Y), new Vector3(r.Position.X - w / 2, y, c.Y)),
                (new Vector3(w, h, r.Size.Y), new Vector3(r.End.X + w / 2, y, c.Y)),
            };
            foreach (var (size, at) in parts)
            {
                Box(parent, "Ring", size, at, mat);
                body?.AddChild(new CollisionShape3D { Shape = new BoxShape3D { Size = size }, Position = at });
            }
        }

        static MeshInstance3D Box(Node3D parent, string name, Vector3 size, Vector3 at, Material mat)
        {
            var m = new MeshInstance3D { Name = name, Mesh = new BoxMesh { Size = size }, Position = at, MaterialOverride = mat };
            parent.AddChild(m);
            return m;
        }

        static MeshInstance3D Cyl(Node3D parent, float top, float bottom, float h, Material mat, float y = 0f)
        {
            var m = new MeshInstance3D { Mesh = new CylinderMesh { TopRadius = top, BottomRadius = bottom, Height = h, RadialSegments = 32 },
                                         Position = new Vector3(0, y + h / 2, 0), MaterialOverride = mat };
            parent.AddChild(m);
            return m;
        }

        static void Sphere(Node3D parent, float r, float y, Material mat) =>
            parent.AddChild(new MeshInstance3D { Mesh = new SphereMesh { Radius = r, Height = r * 2 }, Position = new Vector3(0, y, 0), MaterialOverride = mat });

        static IEnumerable<(float X, float Z)> Corners(Rect2 r)
        {
            yield return (r.Position.X, r.Position.Y);
            yield return (r.End.X, r.Position.Y);
            yield return (r.Position.X, r.End.Y);
            yield return (r.End.X, r.End.Y);
        }

        void Candles(Vector2 at, float u, float[] heights)
        {
            var holder = new Node3D { Name = "Candles", Position = new Vector3(at.X, TableY, at.Y) };
            AddChild(holder);
            Cyl(holder, 3.4f * u, 3.8f * u, 0.5f * u, _brass);                // dish
            Cyl(holder, 0.5f * u, 0.9f * u, 1.6f * u, _brass, 0.5f * u);     // stem
            var glow = new GradientTexture2D
            {
                Width = 64, Height = 64, Fill = GradientTexture2D.FillEnum.Radial, FillFrom = new Vector2(0.5f, 0.5f), FillTo = new Vector2(1f, 0.5f),
                Gradient = new Gradient { Colors = new[] { new Color(1, 1, 1, 1), new Color(1, 1, 1, 0) }, Offsets = new[] { 0f, 1f } },
            };
            for (int i = 0; i < heights.Length; i++)
            {
                float a = i * Mathf.Tau / heights.Length + 0.4f;
                float d = heights.Length > 1 ? 1.6f * u : 0f;
                var p = new Vector3(Mathf.Cos(a) * d, 0.5f * u, Mathf.Sin(a) * d);
                float h = heights[i] * 9f * u, r = 0.75f * u;
                var cn = new Node3D { Position = p };
                holder.AddChild(cn);
                Cyl(cn, r * 0.92f, r, h, _wax);
                var mat = new StandardMaterial3D
                {
                    ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                    BlendMode = BaseMaterial3D.BlendModeEnum.Add, BillboardMode = BaseMaterial3D.BillboardModeEnum.FixedY,
                    AlbedoTexture = glow, DisableReceiveShadows = true,
                };
                var flame = new MeshInstance3D { Name = "Flame", Mesh = new QuadMesh { Size = new Vector2(1.1f * u, 2.6f * u) }, MaterialOverride = mat,
                                                 Position = new Vector3(0, h + 1.2f * u, 0), CastShadow = GeometryInstance3D.ShadowCastingSetting.Off };
                cn.AddChild(flame);
                var light = new OmniLight3D { LightColor = new Color(1f, 0.62f, 0.32f), OmniRange = 70f * u, OmniAttenuation = 1.6f,
                                              Position = new Vector3(0, h + 1.5f * u, 0), ShadowEnabled = i == 0 };
                cn.AddChild(light);
                _candles.Add((light, flame, mat, i * 1.7f + at.X));
            }
        }

        void Compass(Vector2 at, float r)
        {
            var n = new Node3D { Name = "Compass", Position = new Vector3(at.X, TableY, at.Y) };
            AddChild(n);
            Cyl(n, r, r * 1.05f, r * 0.08f, _brass);
            Cyl(n, r * 0.9f, r * 0.9f, r * 0.02f, _parchment, r * 0.08f);
            float y = r * 0.1f;
            // eight points: long cardinal, short ordinal; a diamond is a box turned 45° inside a stretched parent
            for (int i = 0; i < 8; i++)
            {
                bool card = i % 2 == 0;
                float len = card ? r * 0.85f : r * 0.5f;
                var arm = new Node3D { RotationDegrees = new Vector3(0, i * 45f, 0), Position = new Vector3(0, y, 0) };
                n.AddChild(arm);
                var stretch = new Node3D { Scale = new Vector3(1, 1, len / (r * 0.09f * 1.4142f)), Position = new Vector3(0, 0, -len / 2) };
                arm.AddChild(stretch);
                var mat = i == 0 ? new StandardMaterial3D { AlbedoColor = new Color(0.55f, 0.08f, 0.06f), Roughness = 0.4f } : (card ? _gold : (Material)_darkWood);
                stretch.AddChild(new MeshInstance3D { Mesh = new BoxMesh { Size = new Vector3(r * 0.09f, r * 0.03f, r * 0.09f) }, RotationDegrees = new Vector3(0, 45, 0),
                                                       MaterialOverride = mat });
            }
            Sphere(n, r * 0.07f, y + r * 0.02f, _gold);
        }

        void Scroll(Vector2 at, float u)
        {
            var n = new Node3D { Name = "Scroll", Position = new Vector3(at.X, TableY, at.Y), RotationDegrees = new Vector3(0, 12, 0) };
            AddChild(n);
            var body = new MeshInstance3D { Mesh = new CylinderMesh { TopRadius = 1.4f * u, BottomRadius = 1.4f * u, Height = 22 * u },
                                            RotationDegrees = new Vector3(0, 0, 90), Position = new Vector3(0, 1.4f * u, 0), MaterialOverride = _parchment };
            n.AddChild(body);
            foreach (float s in new[] { -1f, 1f })
                n.AddChild(new MeshInstance3D { Mesh = new CylinderMesh { TopRadius = 0.5f * u, BottomRadius = 0.5f * u, Height = 3.5f * u },
                                                RotationDegrees = new Vector3(0, 0, 90), Position = new Vector3(s * 12.6f * u, 1.4f * u, 0), MaterialOverride = _darkWood });
            n.AddChild(new MeshInstance3D { Mesh = new CylinderMesh { TopRadius = 1.48f * u, BottomRadius = 1.48f * u, Height = 1.2f * u },
                                            RotationDegrees = new Vector3(0, 0, 90), Position = new Vector3(2 * u, 1.4f * u, 0),
                                            MaterialOverride = new StandardMaterial3D { AlbedoColor = new Color(0.45f, 0.06f, 0.05f), Roughness = 0.7f } });
        }

        void Markers(Vector2 at, float u)
        {
            var cols = new[] { new Color(0.55f, 0.08f, 0.06f), new Color(0.12f, 0.22f, 0.45f), new Color(0.85f, 0.78f, 0.6f), new Color(0.15f, 0.32f, 0.16f) };
            var rng = new RandomNumberGenerator { Seed = 11 };
            for (int i = 0; i < 9; i++)
            {
                var n = new Node3D { Name = "Marker", Position = new Vector3(at.X + rng.RandfRange(-9, 9) * u, TableY, at.Y + rng.RandfRange(-3, 3) * u) };
                AddChild(n);
                var mat = new StandardMaterial3D { AlbedoColor = cols[i % cols.Length], Roughness = 0.5f };
                Cyl(n, 1.0f * u, 1.25f * u, 0.5f * u, mat);
                Cyl(n, 0.45f * u, 0.7f * u, 2.2f * u, mat, 0.5f * u);
                Sphere(n, 0.65f * u, 3.2f * u, mat);
            }
        }
    }
}
