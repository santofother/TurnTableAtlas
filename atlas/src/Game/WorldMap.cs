// The Caelora world map: a zoomable, pannable painted map with a pin per city package (city.json
// world_map.pin_uv). Hover shows the city's thumbnail card; click opens the city. New package = new pin.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class WorldMap : CanvasLayer
    {
        AtlasRoot _root;
        Control _view;
        TextureRect _map;
        Vector2 _texSize;
        float _scale = 1f, _fit = 1f;
        Vector2 _offset;
        bool _drag;
        readonly List<(MapPin Pin, CityManifest M)> _pins = new();
        PanelContainer _card;
        TextureRect _cardThumb;
        Label _cardTitle, _cardInfo;
        static readonly Color Accent = new(0.95f, 0.72f, 0.38f);

        public void Build(AtlasRoot root)
        {
            _root = root;
            var bg = new ColorRect { Color = new Color(0.10f, 0.09f, 0.08f) };
            bg.SetAnchorsPreset(Control.LayoutPreset.FullRect);
            AddChild(bg);
            _view = new Control { Name = "View", ClipContents = true, MouseFilter = Control.MouseFilterEnum.Stop };
            _view.SetAnchorsPreset(Control.LayoutPreset.FullRect);
            _view.GuiInput += OnInput;
            AddChild(_view);
            var tex = LoadTexture("res://assets/map/CaeloraMapv3.png");
            _texSize = tex?.GetSize() ?? new Vector2(1639, 960);
            _map = new TextureRect { Texture = tex, ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize, StretchMode = TextureRect.StretchModeEnum.Scale,
                                     MouseFilter = Control.MouseFilterEnum.Ignore, TextureFilter = CanvasItem.TextureFilterEnum.LinearWithMipmaps };
            _view.AddChild(_map);
            BuildCard();
            foreach (var m in root.Cities)
            {
                var pin = new MapPin { Text = m.Name, TooltipText = "" };
                pin.MouseEntered += () => ShowCard(m, pin);
                pin.MouseExited += () => { if (_card != null) _card.Visible = false; };
                var id = m.Id;
                pin.Pressed += () => _root.OpenCity(id);
                _view.AddChild(pin);
                _pins.Add((pin, m));
            }
            var title = new Label { Text = "Caelora · Turntable Atlas" };
            title.AddThemeFontSizeOverride("font_size", 30);
            title.AddThemeColorOverride("font_color", Accent);
            title.AddThemeConstantOverride("outline_size", 8);
            title.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0, 0.8f));
            title.Position = new Vector2(24, 16);
            AddChild(title);
            var sub = new Label { Text = $"{root.Cities.Count} {(root.Cities.Count == 1 ? "city" : "cities")} · click a pin to visit · wheel to zoom, drag to pan" };
            sub.AddThemeConstantOverride("outline_size", 6);
            sub.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0, 0.8f));
            sub.Position = new Vector2(26, 58);
            AddChild(sub);
            MoveChild(_card, GetChildCount() - 1);
            _view.Resized += Fit;
            Callable.From(Fit).CallDeferred();
        }

        static Texture2D LoadTexture(string res)
        {
            if (ResourceLoader.Exists(res)) return GD.Load<Texture2D>(res);
            var p = ProjectSettings.GlobalizePath(res);
            if (!File.Exists(p)) return null;
            var img = Image.LoadFromFile(p);
            img.GenerateMipmaps();
            return ImageTexture.CreateFromImage(img);
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
            AddChild(_card);
        }

        void ShowCard(CityManifest m, MapPin pin)
        {
            if (_card == null || _view == null) return;
            var thumb = m.Files.TryGetValue("thumb", out var t) ? Path.Combine(m.Directory, t) : null;
            _cardThumb.Texture = thumb != null && File.Exists(thumb) ? ImageTexture.CreateFromImage(Image.LoadFromFile(thumb)) : null;
            _cardTitle.Text = m.Name;
            var events = string.Join(", ", m.Events.Select(e => e.Replace('_', ' ')));
            _cardInfo.Text = $"{Math.Abs(m.Sun.LatitudeDeg):0}°{(m.Sun.LatitudeDeg >= 0 ? "N" : "S")} · {m.Venues.Count} venues · seats {m.Venues.Sum(v => v.Capacity):N0}\nEvents: {events}\nClick to visit";
            var p = pin.Position + new Vector2(28, -90);
            var vs = _view.Size;
            if (p.X + 344 > vs.X) p.X = pin.Position.X - 360;
            p.Y = Math.Clamp(p.Y, 10, Math.Max(10, vs.Y - 300));
            _card.Position = p;
            _card.Visible = true;
        }

        void Fit()
        {
            var vs = _view.Size;
            if (vs.X < 10) return;
            _fit = Math.Min(vs.X / _texSize.X, vs.Y / _texSize.Y);
            _scale = _fit;
            _offset = (vs - _texSize * _scale) / 2;
            Layout();
        }

        void Layout()
        {
            _map.Position = _offset;
            _map.Size = _texSize * _scale;
            foreach (var (pin, m) in _pins)
            {
                var uv = new Vector2((float)m.WorldMap.PinUv[0], (float)m.WorldMap.PinUv[1]);
                pin.Position = _offset + uv * _texSize * _scale - new Vector2(12, 12);
            }
        }

        void OnInput(InputEvent e)
        {
            if (e is InputEventMouseButton mb)
            {
                if (mb.ButtonIndex == MouseButton.WheelUp && mb.Pressed) ZoomAt(mb.Position, 1.15f);
                else if (mb.ButtonIndex == MouseButton.WheelDown && mb.Pressed) ZoomAt(mb.Position, 1 / 1.15f);
                else if (mb.ButtonIndex == MouseButton.Left || mb.ButtonIndex == MouseButton.Right) _drag = mb.Pressed;
                if (mb.DoubleClick) Fit();
            }
            else if (e is InputEventMagnifyGesture mg) ZoomAt(mg.Position, mg.Factor);
            else if (e is InputEventPanGesture pg) { _offset -= pg.Delta * 12; Layout(); }
            else if (e is InputEventMouseMotion mm && _drag) { _offset += mm.Relative; Layout(); }
        }

        void ZoomAt(Vector2 at, float f)
        {
            float ns = Math.Clamp(_scale * f, _fit * 0.8f, _fit * 6f);
            f = ns / _scale;
            _offset = at - (at - _offset) * f;
            _scale = ns;
            Layout();
        }
    }

    /// <summary>A city pin: a gold disc with a pulsing ring and the city name.</summary>
    public partial class MapPin : Button
    {
        float _t;
        public override void _Ready()
        {
            Flat = true;
            CustomMinimumSize = new Vector2(24, 24);
            Size = new Vector2(24, 24);
            MouseDefaultCursorShape = CursorShape.PointingHand;
            var name = Text;
            Text = "";
            var l = new Label { Text = name, Position = new Vector2(28, -2), MouseFilter = MouseFilterEnum.Ignore };
            l.AddThemeFontSizeOverride("font_size", 18);
            l.AddThemeConstantOverride("outline_size", 8);
            l.AddThemeColorOverride("font_outline_color", new Color(0.1f, 0.06f, 0.03f, 0.95f));
            l.AddThemeColorOverride("font_color", new Color(1f, 0.92f, 0.75f));
            AddChild(l);
        }

        public override void _Process(double delta) { _t += (float)delta; QueueRedraw(); }

        public override void _Draw()
        {
            var c = new Vector2(12, 12);
            float pulse = (_t * 0.8f) % 1f;
            DrawCircle(c, 10 + 10 * pulse, new Color(0.95f, 0.72f, 0.38f, 0.5f * (1 - pulse)));
            DrawCircle(c, 8, new Color(0.15f, 0.08f, 0.04f));
            DrawCircle(c, 6, IsHovered() ? new Color(1f, 0.85f, 0.5f) : new Color(0.92f, 0.66f, 0.28f));
        }
    }
}
