// Shared sun-arc maths: C# port of generator/sunarc.py. Both are checked against tests/sunarc_cases.json.
// World frame (manifest): +X east, +Y north, +Z up. Use Geo.ToGodot for Godot's (x, z, -y).
using System;

namespace Atlas.Core
{
    public readonly struct Vec3
    {
        public readonly double X, Y, Z;
        public Vec3(double x, double y, double z) { X = x; Y = y; Z = z; }
        public static Vec3 operator +(Vec3 a, Vec3 b) => new(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
        public static Vec3 operator -(Vec3 a, Vec3 b) => new(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
        public static Vec3 operator *(Vec3 a, double s) => new(a.X * s, a.Y * s, a.Z * s);
        public double Length => Math.Sqrt(X * X + Y * Y + Z * Z);
        public double Length2D => Math.Sqrt(X * X + Y * Y);
        public override string ToString() => $"({X:0.###}, {Y:0.###}, {Z:0.###})";
    }

    public static class SunArc
    {
        const double Deg = Math.PI / 180.0;

        public static double DeclinationDeg(double dayOfYear) => 23.44 * Math.Sin(Deg * (360.0 / 365.0 * (dayOfYear - 81)));

        /// <summary>(elevation, azimuth) in degrees; azimuth from north, clockwise, plus the north offset, in [0, 360).</summary>
        public static (double Elevation, double Azimuth) Position(double latDeg, double dayOfYear, double hour, double northOffsetDeg = 0)
        {
            double phi = latDeg * Deg, dec = DeclinationDeg(dayOfYear) * Deg, h = 15.0 * (hour - 12.0) * Deg;
            double s = Math.Sin(phi) * Math.Sin(dec) + Math.Cos(phi) * Math.Cos(dec) * Math.Cos(h);
            double el = Math.Asin(Math.Clamp(s, -1.0, 1.0)) / Deg;
            double az = Math.Atan2(Math.Sin(h), Math.Cos(h) * Math.Sin(phi) - Math.Tan(dec) * Math.Cos(phi)) / Deg + 180.0;
            az = ((az + northOffsetDeg) % 360.0 + 360.0) % 360.0;
            return (el, az);
        }

        /// <summary>Unit vector toward the sun in the manifest frame (+X east, +Y north, +Z up).</summary>
        public static Vec3 Direction(double latDeg, double dayOfYear, double hour, double northOffsetDeg = 0)
        {
            var (el, az) = Position(latDeg, dayOfYear, hour, northOffsetDeg);
            double e = el * Deg, a = az * Deg;
            return new Vec3(Math.Cos(e) * Math.Sin(a), Math.Cos(e) * Math.Cos(a), Math.Sin(e));
        }

        /// <summary>Solar hours of sunrise/sunset; (null, null) in polar night, (0, 24) in midnight sun.</summary>
        public static (double? Rise, double? Set) SunriseSunset(double latDeg, double dayOfYear)
        {
            double phi = latDeg * Deg, dec = DeclinationDeg(dayOfYear) * Deg;
            double c = -Math.Tan(phi) * Math.Tan(dec);
            if (c >= 1.0) return (null, null);
            if (c <= -1.0) return (0.0, 24.0);
            double h0 = Math.Acos(c) / Deg / 15.0;
            return (12.0 - h0, 12.0 + h0);
        }

        static double Smooth(double t) { t = Math.Clamp(t, 0.0, 1.0); return t * t * (3 - 2 * t); }

        public static double Daylight(double elevationDeg) => Smooth((elevationDeg + 6.0) / 14.0);
        public static double NightLevel(double elevationDeg) => 0.9 * Smooth((4.0 - elevationDeg) / 12.0);
        public static double Dusk(double elevationDeg) { double d = (elevationDeg - 2.0) / 7.0; return Math.Exp(-d * d); }

        public static double Lateness(double hour)
        {
            double h = ((hour - 12.0) % 24.0 + 24.0) % 24.0;
            double a = Math.Clamp((h - 10.5) / 2.5, 0, 1), b = Math.Clamp((h - 16.0) / 1.5, 0, 1);
            return (a * a * (3 - 2 * a)) * (1.0 - b * b * (3 - 2 * b));
        }

        public static double WindowLevel(double elevationDeg, double hour) => NightLevel(elevationDeg) * (1.0 - 0.6 * Lateness(hour));

        /// <summary>Points along today's sun path (manifest frame, unit vectors) for the arc gizmo; only those above the horizon.</summary>
        public static System.Collections.Generic.List<(double Hour, Vec3 Dir)> Arc(double latDeg, double dayOfYear, double northOffsetDeg, int steps = 96)
        {
            var list = new System.Collections.Generic.List<(double, Vec3)>();
            for (int i = 0; i <= steps; i++)
            {
                double h = 24.0 * i / steps;
                var d = Direction(latDeg, dayOfYear, h, northOffsetDeg);
                if (d.Z > -0.02) list.Add((h, d));
            }
            return list;
        }
    }
}
