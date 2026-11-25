// Draws today's sun path over the city: a line from sunrise to sunset with markers and labels, plus the sun now.
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class SunArcGizmo : Node3D
    {
        public float Radius = 46f;
        /// <summary>Labels keep one size on screen (the Known World, where the gizmo is rescaled with the zoom).</summary>
        public bool FixedSizeLabels;
        MeshInstance3D _line, _now;
        readonly Label3D[] _labels = new Label3D[3];
        readonly MeshInstance3D[] _marks = new MeshInstance3D[3];
        ImmediateMesh _im;

        public override void _Ready()
        {
            var mat = new StandardMaterial3D { ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, AlbedoColor = new Color(1f, 0.78f, 0.3f),
                                               NoDepthTest = false, Transparency = BaseMaterial3D.TransparencyEnum.Alpha };
            _im = new ImmediateMesh();
            _line = new MeshInstance3D { Mesh = _im, MaterialOverride = mat, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off };
            AddChild(_line);
            var dot = new SphereMesh { Radius = 0.9f, Height = 1.8f, RadialSegments = 12, Rings = 6 };
            var dmat = new StandardMaterial3D { ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded, AlbedoColor = new Color(1f, 0.9f, 0.5f) };
            for (int i = 0; i < 3; i++)
            {
                _marks[i] = new MeshInstance3D { Mesh = dot, MaterialOverride = dmat, Scale = Vector3.One * 0.6f, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off };
                AddChild(_marks[i]);
                _labels[i] = new Label3D { Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, FontSize = 64, PixelSize = 0.02f,
                                           Modulate = new Color(1f, 0.95f, 0.8f), OutlineSize = 12, NoDepthTest = true };
                _labels[i].FixedSize = FixedSizeLabels;
                AddChild(_labels[i]);
            }
            _now = new MeshInstance3D { Mesh = dot, MaterialOverride = new StandardMaterial3D { ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
                                        AlbedoColor = new Color(1f, 0.55f, 0.15f) }, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off };
            AddChild(_now);
        }

        const float FixedPixelSize = 0.0003f;

        /// <summary>Scale the whole path; fixed-size labels would shrink with it, so they are scaled back.</summary>
        public void Resize(float k)
        {
            Scale = Vector3.One * k;
            if (FixedSizeLabels)
                foreach (var l in _labels) l.PixelSize = FixedPixelSize / k;
        }

        public void Rebuild(TimeOfDay tod)
        {
            if (_im == null) return;
            var arc = SunArc.Arc(tod.Latitude, tod.DayOfYear, tod.NorthOffset, 192);
            _im.ClearSurfaces();
            if (arc.Count >= 2)
            {
                _im.SurfaceBegin(Mesh.PrimitiveType.LineStrip);
                foreach (var (_, d) in arc) _im.SurfaceAddVertex(Geo.V(d) * Radius);
                _im.SurfaceEnd();
            }
            var (rise, set) = SunArc.SunriseSunset(tod.Latitude, tod.DayOfYear);
            double[] hours = { rise ?? 0, 12.0, set ?? 24 };
            string[] names = { "sunrise", "noon", "sunset" };
            for (int i = 0; i < 3; i++)
            {
                var d = Geo.V(SunArc.Direction(tod.Latitude, tod.DayOfYear, hours[i], tod.NorthOffset));
                _marks[i].Position = d * Radius;
                _labels[i].Position = d * Radius + Vector3.Up * 2.2f;
                var (el, _) = SunArc.Position(tod.Latitude, tod.DayOfYear, hours[i], tod.NorthOffset);
                _labels[i].Text = i == 1 ? $"noon {el:0}°" : $"{names[i]} {TimeOfDay.Clock(hours[i])}";
                _marks[i].Visible = _labels[i].Visible = rise.HasValue;
            }
            UpdateNow(tod);
        }

        public void UpdateNow(TimeOfDay tod)
        {
            if (_now == null) return;
            var d = Geo.V(SunArc.Direction(tod.Latitude, tod.DayOfYear, tod.Hour, tod.NorthOffset));
            _now.Position = d * Radius;
            _now.Visible = d.Y > -0.05f;
        }
    }
}
