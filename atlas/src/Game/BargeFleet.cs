// Barges under way on Haven's River Flame (Atlas.Core.RiverBarges): grain barges heaped with wheat running downstream to
// the sea, empty barges sailing back up. Drawn as two MultiMeshes of the package's own prototypes (barge_grain,
// barge_empty), their transforms set every frame. Used by the city view (lanes from city.json, model frame) and by the
// Known World (lanes along the whole Flame, at the miniature's scale, riding the drawn water).
using System;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class BargeFleet : Node3D
    {
        BargeLane[] _lanes = Array.Empty<BargeLane>();
        MultiMeshInstance3D _laden, _empty;
        float[] _ladenBuf, _emptyBuf;
        Func<double, double, float> _water;
        double _scale, _beam, _height;
        Color _hull;
        public int Count => _lanes.Sum(l => l.Count);
        public int Afloat { get; private set; }
        public double Time { get; private set; }

        /// <param name="lengthScale">frame units per lane unit for the barge's size (1 where the lanes carry lengths in the frame)</param>
        /// <param name="water">the water's surface (Godot y) under a point of the lanes' frame</param>
        public void Build(BargeLane[] lanes, InstanceSpec spec, Material mat, Func<double, double, float> water, double beam = 0.3, double height = 0.5,
                          double lengthScale = 1, float range = 0f)
        {
            Name = "Barges";
            _lanes = lanes;
            _water = water;
            _scale = lengthScale; _beam = beam; _height = height;
            _hull = new Color(0.46f, 0.32f, 0.2f);
            _laden = Make("Laden", spec, "barge_grain", lanes.Where(l => l.Laden).Sum(l => l.Count), mat, range, out _ladenBuf);
            _empty = Make("Empty", spec, "barge_empty", lanes.Where(l => !l.Laden).Sum(l => l.Count), mat, range, out _emptyBuf);
        }

        MultiMeshInstance3D Make(string name, InstanceSpec spec, string kind, int n, Material mat, float range, out float[] buf)
        {
            buf = new float[n * 16];
            if (n == 0 || spec?.Protos == null || !spec.Protos.TryGetValue(kind, out var proto)) return null;
            var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseCustomData = true, Mesh = Instances.Mesh(proto), InstanceCount = n };
            var node = new MultiMeshInstance3D
            {
                Name = name, Multimesh = mm, MaterialOverride = mat, CastShadow = GeometryInstance3D.ShadowCastingSetting.On,
                CustomAabb = new Aabb(new Vector3(-1e5f, -1e3f, -1e5f), new Vector3(2e5f, 2e3f, 2e5f)),   // they roam the whole river
            };
            if (range > 0) { node.VisibilityRangeEnd = range; node.VisibilityRangeEndMargin = range * 0.2f; }
            AddChild(node);
            return node;
        }

        /// <summary>Place every barge for time t (seconds).</summary>
        public void Tick(double t)
        {
            Time = t;
            int il = 0, ie = 0, vis = 0;
            foreach (var lane in _lanes)
                for (int k = 0; k < lane.Count; k++)
                {
                    var b = lane.At(k, t);
                    var buf = b.Laden ? _ladenBuf : _emptyBuf;
                    int o = (b.Laden ? il++ : ie++) * 16;
                    if (!b.Visible) { Array.Clear(buf, o, 12); continue; }
                    vis++;
                    double L = b.Length * _scale;
                    float w = (float)L, d = (float)(L * _beam), h = (float)(L * _height);
                    float y = _water(b.X, b.Y) - 0.05f * h;                 // a little below the surface: the hull sits in it
                    float sway = (float)(0.012 * Math.Sin(t * 0.7 + k * 1.9));
                    var basis = new Basis(Vector3.Up, (float)b.Heading) * new Basis(Vector3.Right, sway) * Basis.FromScale(new Vector3(w, h, d));
                    buf[o + 0] = basis.X.X; buf[o + 1] = basis.Y.X; buf[o + 2] = basis.Z.X; buf[o + 3] = (float)b.X;
                    buf[o + 4] = basis.X.Y; buf[o + 5] = basis.Y.Y; buf[o + 6] = basis.Z.Y; buf[o + 7] = y;
                    buf[o + 8] = basis.X.Z; buf[o + 9] = basis.Y.Z; buf[o + 10] = basis.Z.Z; buf[o + 11] = -(float)b.Y;
                    float tone = 0.85f + 0.3f * (float)((k * 0.618034) % 1.0);
                    buf[o + 12] = (float)InstanceTable.SrgbToLinear(_hull.R * tone);
                    buf[o + 13] = (float)InstanceTable.SrgbToLinear(_hull.G * tone);
                    buf[o + 14] = (float)InstanceTable.SrgbToLinear(_hull.B * tone);
                    buf[o + 15] = 0.99f;
                }
            Afloat = vis;
            if (_laden != null) _laden.Multimesh.Buffer = _ladenBuf;
            if (_empty != null) _empty.Multimesh.Buffer = _emptyBuf;
        }

        /// <summary>Barge positions in Godot space right now (for the self-test).</summary>
        public Vector3[] Positions() => _lanes.SelectMany(l => l.All(Time)).Where(b => b.Visible)
                                               .Select(b => new Vector3((float)b.X, _water(b.X, b.Y), -(float)b.Y)).ToArray();
    }
}
