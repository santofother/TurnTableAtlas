// Manifest frame (+X east, +Y north, +Z up) <-> Godot frame (+X east, +Y up, -Z north): godot = (x, z, -y).
using Atlas.Core;
using Godot;

namespace Atlas
{
    public static class Geo
    {
        public static Vector3 V(double[] p) => new((float)p[0], p.Length > 2 ? (float)p[2] : 0f, -(float)p[1]);
        public static Vector3 V(Vec3 p) => new((float)p.X, (float)p.Z, -(float)p.Y);
        public static Vector3 V2(double[] p, float y) => new((float)p[0], y, -(float)p[1]);

        /// <summary>Rotation about Godot +Y for a manifest heading (radians CCW from +X): the same angle.</summary>
        public static float Yaw(double headingRad) => (float)headingRad;

        /// <summary>Landmark camera convention: offset from the target for yaw/pitch (degrees) and distance.</summary>
        public static Vector3 Orbit(float yawDeg, float pitchDeg, float dist)
        {
            float y = Mathf.DegToRad(yawDeg), p = Mathf.DegToRad(pitchDeg);
            return new Vector3(dist * Mathf.Cos(p) * Mathf.Cos(y), dist * Mathf.Sin(p), -dist * Mathf.Cos(p) * Mathf.Sin(y));
        }
    }

    /// <summary>Command-line options after `--` (e.g. --city=fantasy_capital --hour=19.5 --quit-after=5 --shots=3,6).</summary>
    public static class Args
    {
        static System.Collections.Generic.Dictionary<string, string> _a;
        public static System.Collections.Generic.Dictionary<string, string> All
        {
            get
            {
                if (_a != null) return _a;
                _a = new();
                foreach (var s in OS.GetCmdlineUserArgs())
                {
                    var t = s.TrimStart('-');
                    int i = t.IndexOf('=');
                    if (i < 0) _a[t] = "1"; else _a[t[..i]] = t[(i + 1)..];
                }
                return _a;
            }
        }
        public static string Get(string k, string def = null) => All.TryGetValue(k, out var v) ? v : def;
        public static bool Has(string k) => All.ContainsKey(k);
        public static float F(string k, float def) => All.TryGetValue(k, out var v) && float.TryParse(v, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var f) ? f : def;
    }
}
