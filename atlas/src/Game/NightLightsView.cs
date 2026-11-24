// Night lights: one MultiMesh of glow billboards (windows light in their manifest order, lamps and torches with
// the dusk level) plus a few real OmniLights (lighthouses, gate torches) that flicker.
using System;
using System.Collections.Generic;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class NightLightsView : Node3D
    {
        readonly List<(OmniLight3D L, float E)> _omni = new();
        float _lamp;

        public void Build(CityManifest m, Materials mats)
        {
            var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseCustomData = true,
                                     InstanceCount = m.NightLights.Count, Mesh = new QuadMesh { Size = Vector2.One } };
            for (int i = 0; i < m.NightLights.Count; i++)
            {
                var l = m.NightLights[i];
                float kind = l.Kind switch { "window" => 0, "lamp" => 1, "torch" => 2, _ => 3 };
                float size = l.Kind switch { "window" => 0.22f, "lamp" => 0.32f, "torch" => 0.5f, _ => 1.6f };
                mm.SetInstanceTransform(i, new Transform3D(Basis.Identity.Scaled(Vector3.One * size), Geo.V(l.Pos)));
                mm.SetInstanceCustomData(i, new Color(kind, (float)l.Order, (float)Math.Max(0.35, l.Strength), 0));
                if (l.Kind == "lighthouse" || (l.Kind == "torch" && l.Strength >= 0.8 && _omni.Count < 10))
                {
                    float e = l.Kind == "lighthouse" ? 3.0f : 0.7f;
                    var o = new OmniLight3D { Position = Geo.V(l.Pos), LightColor = new Color(1f, 0.58f, 0.25f), OmniRange = l.Kind == "lighthouse" ? 9f : 3f,
                                              OmniAttenuation = 1.4f, ShadowEnabled = false, LightEnergy = 0 };
                    AddChild(o);
                    _omni.Add((o, e));
                }
            }
            AddChild(new MultiMeshInstance3D { Name = "Glows", Multimesh = mm, MaterialOverride = mats.Glow,
                                               CastShadow = GeometryInstance3D.ShadowCastingSetting.Off });
        }

        public void SetLevel(float lamp) => _lamp = lamp;

        public override void _Process(double delta)
        {
            float t = (float)Time.GetTicksMsec() / 1000f;
            for (int i = 0; i < _omni.Count; i++)
            {
                var (l, e) = _omni[i];
                float flick = 0.85f + 0.15f * Mathf.Sin(t * 11f + i * 2.3f) * Mathf.Sin(t * 4.3f + i);
                l.LightEnergy = e * _lamp * flick;
                l.Visible = _lamp > 0.02f;
            }
        }
    }
}
