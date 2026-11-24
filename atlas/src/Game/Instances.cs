// Draws a package's instance table (Atlas.Core.InstanceTable) with GPU instancing: one MultiMesh per prototype and
// map tile, so the far tiles are culled. Used by the city view (model frame, as the glb) and, through `place`, by the
// Known World's basin miniature (which re-seats every instance on its own ground at its own scale).
using System;
using System.Collections.Generic;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public static class Instances
    {
        static readonly Dictionary<string, float> RangeByKind = new() { ["camel"] = 22f, ["shrub"] = 45f, ["awning"] = 50f };

        static readonly Dictionary<ProtoData, ArrayMesh> _meshes = new();

        public static ArrayMesh Mesh(ProtoData p)
        {
            if (_meshes.TryGetValue(p, out var m)) return m;
            var pm = new ProtoMesh(p);
            int n = pm.Pos.Count / 3;
            var v = new Vector3[n]; var nr = new Vector3[n]; var c = new Color[n];
            for (int i = 0; i < n; i++)
            {
                v[i] = new Vector3(pm.Pos[3 * i], pm.Pos[3 * i + 1], pm.Pos[3 * i + 2]);
                nr[i] = new Vector3(pm.Nrm[3 * i], pm.Nrm[3 * i + 1], pm.Nrm[3 * i + 2]);
                c[i] = new Color(pm.Col[4 * i], pm.Col[4 * i + 1], pm.Col[4 * i + 2], pm.Col[4 * i + 3]);
            }
            var arrays = new Godot.Collections.Array();
            arrays.Resize((int)Godot.Mesh.ArrayType.Max);
            arrays[(int)Godot.Mesh.ArrayType.Vertex] = v;
            arrays[(int)Godot.Mesh.ArrayType.Normal] = nr;
            arrays[(int)Godot.Mesh.ArrayType.Color] = c;
            m = new ArrayMesh();
            m.AddSurfaceFromArrays(Godot.Mesh.PrimitiveType.Triangles, arrays);
            _meshes[p] = m;
            return m;
        }

        /// <summary>A placement: model record -> (godot transform). The default is the city view's frame.</summary>
        public delegate Transform3D Place(InstanceTable t, int i);

        public static Transform3D ModelFrame(InstanceTable t, int i)
        {
            var basis = new Basis(Vector3.Up, t.Rot(i)) * Basis.FromScale(new Vector3(t.W(i), t.H(i), t.D(i)));
            return new Transform3D(basis, new Vector3(t.X(i), t.Z(i), -t.Y(i)));
        }

        /// <summary>Build the instance nodes under `parent`. Returns (instances, triangles drawn).</summary>
        public static (int Count, long Tris) Build(Node3D parent, InstanceTable t, Material mat, double cx, double cy, Place place = null,
                                                   int tiles = 4, double half = 50, float rangeScale = 1f, bool shadows = true, float rangeAll = 0f,
                                                   ICollection<string> skipKinds = null)
        {
            place ??= ModelFrame;
            int total = 0; long tris = 0;
            foreach (var (kind, proto) in t.Spec.Protos)
            {
                if (t.CountOf(kind) == 0 || (skipKinds != null && skipKinds.Contains(kind))) continue;
                var mesh = Mesh(proto);
                int ptris = mesh.SurfaceGetArrayLen(0) / 3;
                var buckets = new Dictionary<int, List<int>>();
                foreach (int i in t.OfKind(kind))
                {
                    int tx = Math.Clamp((int)((t.X(i) + half) / (2 * half) * tiles), 0, tiles - 1);
                    int ty = Math.Clamp((int)((t.Y(i) + half) / (2 * half) * tiles), 0, tiles - 1);
                    int key = ty * tiles + tx;
                    if (!buckets.TryGetValue(key, out var list)) buckets[key] = list = new List<int>();
                    list.Add(i);
                }
                foreach (var (key, list) in buckets)
                {
                    var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseCustomData = true, Mesh = mesh, InstanceCount = list.Count };
                    var buf = new float[list.Count * 16];
                    for (int k = 0; k < list.Count; k++)
                    {
                        int i = list[k];
                        var xf = place(t, i);
                        var b = xf.Basis;
                        int o = k * 16;
                        buf[o + 0] = b.X.X; buf[o + 1] = b.Y.X; buf[o + 2] = b.Z.X; buf[o + 3] = xf.Origin.X;
                        buf[o + 4] = b.X.Y; buf[o + 5] = b.Y.Y; buf[o + 6] = b.Z.Y; buf[o + 7] = xf.Origin.Y;
                        buf[o + 8] = b.X.Z; buf[o + 9] = b.Y.Z; buf[o + 10] = b.Z.Z; buf[o + 11] = xf.Origin.Z;
                        var (r, g, bl) = t.Srgb(i);
                        buf[o + 12] = (float)InstanceTable.SrgbToLinear(r);
                        buf[o + 13] = (float)InstanceTable.SrgbToLinear(g);
                        buf[o + 14] = (float)InstanceTable.SrgbToLinear(bl);
                        buf[o + 15] = t.WindowOrder(i, cx, cy);
                    }
                    mm.Buffer = buf;
                    var node = new MultiMeshInstance3D
                    {
                        Name = $"CAP_Inst_{kind}_{key}", Multimesh = mm, MaterialOverride = mat,
                        CastShadow = shadows && kind != "camel" ? GeometryInstance3D.ShadowCastingSetting.On : GeometryInstance3D.ShadowCastingSetting.Off,
                    };
                    float range = RangeByKind.TryGetValue(kind, out var rk) ? rk * rangeScale : 0f;
                    if (rangeAll > 0) range = range > 0 ? Math.Min(range, rangeAll) : rangeAll;
                    if (range > 0)
                    {
                        node.VisibilityRangeEnd = range;
                        node.VisibilityRangeEndMargin = range * 0.2f;
                        node.VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Self;
                    }
                    parent.AddChild(node);
                    total += list.Count;
                    tris += (long)list.Count * ptris;
                }
            }
            return (total, tris);
        }
    }
}
