// A package's instance table (city.json "instances" + instances.bin): houses, terraces, walls, awnings, domes, camels
// and trees as one record each, drawn with GPU instancing from the prototypes in the manifest. Pure C#, no Godot.
// Records are float32, `stride` per instance: x y z (base, model metres) w d h (size) rot (radians CCW from +X)
// r g b (sRGB tint) kind. Prototypes live in a unit box (x, y in [-0.5, 0.5], z in [0, 1], manifest frame).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json.Serialization;

namespace Atlas.Core
{
    public class InstanceSpec
    {
        [JsonPropertyName("file")] public string File { get; set; }
        [JsonPropertyName("count")] public int Count { get; set; }
        [JsonPropertyName("stride")] public int Stride { get; set; } = 11;
        [JsonPropertyName("kinds")] public Dictionary<string, int> Kinds { get; set; } = new();
        /// <summary>kind name -> [first record, count] (records are sorted by kind).</summary>
        [JsonPropertyName("groups")] public Dictionary<string, int[]> Groups { get; set; } = new();
        [JsonPropertyName("protos")] public Dictionary<string, ProtoData> Protos { get; set; } = new();
    }

    public class ProtoData
    {
        [JsonPropertyName("v")] public double[][] V { get; set; }
        [JsonPropertyName("f")] public List<ProtoFace> F { get; set; }
    }

    public class ProtoFace
    {
        [JsonPropertyName("i")] public int[] I { get; set; }
        /// <summary>"tint" (instance colour x c), "abs" (the colour c), "win" (a window: c by day, lit at night).</summary>
        [JsonPropertyName("m")] public string M { get; set; }
        [JsonPropertyName("c")] public double[] C { get; set; }
    }

    public sealed class InstanceTable
    {
        public readonly InstanceSpec Spec;
        public readonly float[] Data;
        public int Count => Data.Length / Spec.Stride;

        public InstanceTable(InstanceSpec spec, float[] data) { Spec = spec; Data = data; }

        public static InstanceTable Load(string dir, InstanceSpec spec)
        {
            var bytes = System.IO.File.ReadAllBytes(Path.Combine(dir, spec.File));
            var data = new float[bytes.Length / 4];
            Buffer.BlockCopy(bytes, 0, data, 0, data.Length * 4);
            if (data.Length != spec.Count * spec.Stride)
                throw new InvalidDataException($"instances.bin has {data.Length} floats, the manifest says {spec.Count} x {spec.Stride}");
            return new InstanceTable(spec, data);
        }

        public float X(int i) => Data[i * Spec.Stride];
        public float Y(int i) => Data[i * Spec.Stride + 1];
        public float Z(int i) => Data[i * Spec.Stride + 2];
        public float W(int i) => Data[i * Spec.Stride + 3];
        public float D(int i) => Data[i * Spec.Stride + 4];
        public float H(int i) => Data[i * Spec.Stride + 5];
        public float Rot(int i) => Data[i * Spec.Stride + 6];
        public (float R, float G, float B) Srgb(int i) => (Data[i * Spec.Stride + 7], Data[i * Spec.Stride + 8], Data[i * Spec.Stride + 9]);
        public int Kind(int i) => (int)Data[i * Spec.Stride + 10];

        /// <summary>Record indices of one kind (empty if the package has none).</summary>
        public IEnumerable<int> OfKind(string kind)
        {
            if (!Spec.Groups.TryGetValue(kind, out var g)) yield break;
            for (int i = g[0]; i < g[0] + g[1]; i++) yield return i;
        }

        public int CountOf(string kind) => Spec.Groups.TryGetValue(kind, out var g) ? g[1] : 0;

        /// <summary>The light-up order of a building's windows: a hash and the distance from `centre` (a wave at dusk).</summary>
        public float WindowOrder(int i, double cx, double cy, double spread = 40.0)
        {
            uint h = unchecked((uint)(X(i) * 997) * 374761393u + (uint)(Y(i) * 991) * 668265263u + 7u * 2246822519u);
            h = unchecked((h ^ (h >> 13)) * 1274126177u);
            double hash = ((h ^ (h >> 16)) & 0xFFFF) / 65535.0;
            double d = Math.Min(1.0, Math.Sqrt((X(i) - cx) * (X(i) - cx) + (Y(i) - cy) * (Y(i) - cy)) / spread);
            return (float)Math.Clamp(0.6 * hash + 0.4 * d, 0.01, 0.98);
        }

        public static double SrgbToLinear(double c) => c <= 0.04045 ? c / 12.92 : Math.Pow((c + 0.055) / 1.055, 2.4);
    }

    /// <summary>A prototype as flat-shaded triangles in the Godot frame (x, z, -y), clockwise from outside (Godot's
    /// front faces). Vertex colour: tint faces (shade, shade, shade, 1), absolute faces (linear rgb, 0), windows
    /// (linear rgb, 0.5).</summary>
    public sealed class ProtoMesh
    {
        public readonly List<float> Pos = new(), Nrm = new(), Col = new();
        public int Triangles => Pos.Count / 9;

        public ProtoMesh(ProtoData p)
        {
            foreach (var f in p.F)
            {
                var pts = f.I.Select(k => p.V[k]).ToArray();
                // face normal (Newell) in the manifest frame
                double nx = 0, ny = 0, nz = 0;
                for (int a = 0; a < pts.Length; a++)
                {
                    var u = pts[a]; var v = pts[(a + 1) % pts.Length];
                    nx += (u[1] - v[1]) * (u[2] + v[2]); ny += (u[2] - v[2]) * (u[0] + v[0]); nz += (u[0] - v[0]) * (u[1] + v[1]);
                }
                double len = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                if (len < 1e-12) continue;
                nx /= len; ny /= len; nz /= len;
                float a4 = f.M == "tint" ? 1f : f.M == "win" ? 0.5f : 0f;
                float r, g, b;
                if (f.M == "tint") { r = g = b = (float)f.C[0]; }
                else { r = (float)InstanceTable.SrgbToLinear(f.C[0]); g = (float)InstanceTable.SrgbToLinear(f.C[1]); b = (float)InstanceTable.SrgbToLinear(f.C[2]); }
                for (int t = 1; t + 1 < pts.Length; t++)
                    foreach (var q in new[] { pts[0], pts[t + 1], pts[t] })        // reversed: Godot's front faces are clockwise
                    {
                        Pos.Add((float)q[0]); Pos.Add((float)q[2]); Pos.Add(-(float)q[1]);
                        Nrm.Add((float)nx); Nrm.Add((float)nz); Nrm.Add(-(float)ny);
                        Col.Add(r); Col.Add(g); Col.Add(b); Col.Add(a4);
                    }
            }
        }
    }
}
