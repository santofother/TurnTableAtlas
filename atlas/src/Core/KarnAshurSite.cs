// Karn Ashur on the Known World map (card W5): the green sheltered basin at the heart of the High Dunes massif, laid out
// after briefs/karn_ashur/concept_valley.webp. Pure layout, no Godot:
//   - the basin's ground, a hero patch that replaces the coarse relief round the settlement: a valley floor ringed by
//     cliffs (higher and snowier to the north, with waterfalls), a low pass to the south, and the great peak, a spur on
//     the west wall whose summit carries the Temple of the First Flame. It meets the relief mesh exactly at its edge.
//   - where the city's parts stand: the round walled inner city with its lake (Al-Mirah's spring, LORE?), the island
//     with a stepped ziggurat, fields and canals; the dense sandstone outer city; aqueducts on arches fed by the falls;
//     the switchback road up the great peak; farmsteads, orchards and trees.
//   - the ground layout (fields, water, paving, roads) painted into a texture for the Atlas's ground shader.
// Lengths are blend units (1 = 10 miles), local to the basin centre (the settlement), +x east, +y north; angles are
// radians counter-clockwise from east. Heights are metres; the Atlas draws them at the relief's exaggeration (15x).
// The city is a miniature, about six times its true size, so that its streets and houses read on the map.
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace Atlas.Core
{
    public sealed class KarnAshurSite
    {
        public const string SettlementId = "settlement:karn_ashur";

        // heights (metres). The temple's summit keeps the lore's ~3,700 m.
        public const double FloorM = 2900, WaterM = 2896, IslandM = 2906, ShrineM = 3700, TalusM = 90;
        // radii (blend units from the basin centre)
        public const double IslandR = 0.105, LakeR = 0.215, WallR = 0.36, CityR = 0.64;
        public const double SpurR = 0.40, SummitR = 0.03;
        /// <summary>The basin's ground reaches the relief's heights at BlendOut; its colour turns into the baked map's
        /// between AlbedoIn and AlbedoOut. The patch is a square of at least ±PatchHalf.</summary>
        public const double BlendOut = 3.2, AlbedoIn = 1.7, AlbedoOut = 2.7, PatchHalf = 3.6;
        /// <summary>Half size of the square the ground layout texture covers.</summary>
        public const double FineHalf = 1.35;
        public static readonly double[] RingStreets = { 0.455, 0.545 };
        /// <summary>The gorge through the southern rim, where the road leaves the valley.</summary>
        public const double PassDeg = 268;
        const double Deg = Math.PI / 180.0;

        public enum Kind { House, Tower, Villa, Farm }
        public readonly record struct Building(double X, double Y, double W, double D, double H, double Rot, Kind Kind, bool Garden, double Z, uint Seed);
        public readonly record struct Tree(double X, double Y, double R, double H, bool Cypress, double Z);
        public sealed record Fall(double Theta, double Width, double TopR, double FootR);
        public sealed record Ziggurat(double X, double Y, double Base, int Tiers, double TierH, double Step, double Z);
        public sealed record Gate(double Theta);

        public readonly double Cx, Cy, UnitM, Exag;
        public readonly ReliefSampler Relief;
        /// <summary>Relief grid lines that bound the patch (i across from the west, j down from the north).</summary>
        public readonly int I0, I1, J0, J1;
        /// <summary>The patch in world xy.</summary>
        public readonly double XMin, XMax, YMin, YMax;
        /// <summary>The great peak's summit (local).</summary>
        public readonly double ShrineX, ShrineY;

        public readonly List<Building> Buildings = new();
        public readonly List<Tree> Trees = new();
        public readonly List<double> WallTowers = new();          // angles
        public readonly List<Gate> Gates = new();
        public readonly List<Ziggurat> Ziggurats = new();
        public readonly List<Fall> Falls = new();
        public readonly List<(double X, double Y)[]> Aqueducts = new();
        public readonly List<(double X, double Y)[]> Streams = new();
        public readonly List<(double X, double Y, double R)> Pools = new();
        public readonly List<(double X, double Y, double R)> Hamlets = new();
        /// <summary>The switchback road from the city's edge to the summit, and the lane that joins it to the west avenue.</summary>
        public (double X, double Y)[] Road { get; private set; }
        public (double X, double Y)[] Approach { get; private set; }

        public KarnAshurSite(ReliefSampler relief, double cx, double cy, double unitM, double exag)
        {
            Relief = relief; Cx = cx; Cy = cy; UnitM = unitM; Exag = exag;
            I0 = (int)Math.Floor((cx - PatchHalf - relief.X0) / relief.Dx);
            I1 = (int)Math.Ceiling((cx + PatchHalf - relief.X0) / relief.Dx);
            J0 = (int)Math.Floor((relief.YTop - (cy + PatchHalf)) / relief.Dy);
            J1 = (int)Math.Ceiling((relief.YTop - (cy - PatchHalf)) / relief.Dy);
            XMin = relief.GridX(I0); XMax = relief.GridX(I1);
            YMax = relief.GridY(J0); YMin = relief.GridY(J1);
            ShrineX = 0.92 * Math.Cos(150 * Deg); ShrineY = 0.92 * Math.Sin(150 * Deg);
            foreach (var (deg, w) in new[] { (97.0, 0.05), (82.0, 0.03), (113.0, 0.032), (40.0, 0.038), (8.0, 0.03), (236.0, 0.028) })
            {
                double th = Wrap(deg * Deg), rc = FootR(th);
                Falls.Add(new Fall(th, w, rc + 0.9 * CliffW(th), rc + 0.006));
            }
            BuildLuts();
            Generate();
        }

        // ---------------------------------------------------------------- units and lookups

        public double Units(double metres) => metres / UnitM * Exag;
        public double Metres(double units) => units * UnitM / Exag;
        public bool Contains(double x, double y) => x > XMin && x < XMax && y > YMin && y < YMax;
        /// <summary>uv rect of the relief mesh's vertices that lie strictly inside the patch (u0, v0, u1, v1, from the top-left).</summary>
        public (double U0, double V0, double U1, double V1) HoleUv =>
            ((I0 + 0.5) / Relief.Nx, (J0 + 0.5) / Relief.Ny, (I1 - 0.5) / Relief.Nx, (J1 - 0.5) / Relief.Ny);

        const int LutN = 2048;
        double[] _foot, _cliff, _crest, _shore, _outer;

        void BuildLuts()
        {
            _foot = new double[LutN + 1]; _cliff = new double[LutN + 1]; _crest = new double[LutN + 1];
            _shore = new double[LutN + 1]; _outer = new double[LutN + 1];
            for (int i = 0; i <= LutN; i++)
            {
                double th = -Math.PI + 2 * Math.PI * i / LutN;
                _foot[i] = FootR(th); _cliff[i] = CliffW(th); _crest[i] = CrestBaseM(th);
                _shore[i] = ShoreRaw(th); _outer[i] = OuterRaw(th);
            }
        }

        static double Lut(double[] t, double th)
        {
            double f = (th + Math.PI) / (2 * Math.PI) * LutN;
            int i = Math.Clamp((int)f, 0, LutN - 1);
            return t[i] + (t[i + 1] - t[i]) * (f - i);
        }

        /// <summary>Radius of the cliff foot (the valley floor's edge): wider up the northern arm and the north-east bay.</summary>
        public static double FootR(double th) =>
            0.86 + 0.28 * Bump(th, 97 * Deg, 20 * Deg) + 0.12 * Bump(th, 36 * Deg, 15 * Deg) + 0.06 * Bump(th, 268 * Deg, 10 * Deg) + 0.045 * Wobble(th, 1);
        static double CliffW(double th) => 0.42 + 0.06 * Wobble(th, 2) + 0.2 * Bump(th, 268 * Deg, 12 * Deg);
        static double CrestBaseM(double th) => 3650 + 550 * Math.Sin(th) + 150 * Wobble(th, 3) - 700 * Bump(th, PassDeg * Deg, 9 * Deg);
        static double ShoreRaw(double th) => LakeR + 0.016 * Math.Sin(3 * th + 0.7) + 0.011 * Math.Sin(5 * th + 2.1) + 0.006 * Math.Sin(8 * th + 1.0);
        static double OuterRaw(double th) => CityR + 0.045 * Wobble(th, 7) + 0.07 * Bump(th, 270 * Deg, 12 * Deg) + 0.04 * Bump(th, 90 * Deg, 10 * Deg);

        public double Foot(double th) => Lut(_foot, th);
        /// <summary>The lake's shore radius.</summary>
        public double Shore(double th) => Lut(_shore, th);
        /// <summary>The outer city's edge radius.</summary>
        public double Outer(double th) => Lut(_outer, th);

        // ---------------------------------------------------------------- ground

        double ReliefM(double lx, double ly) => Metres(Relief.Fine(Cx + lx, Cy + ly));

        /// <summary>Ground height in metres at a local point (the relief's per-pixel heights beyond the basin).</summary>
        public double GroundM(double lx, double ly)
        {
            double r = Math.Sqrt(lx * lx + ly * ly);
            if (r >= BlendOut) return ReliefM(lx, ly);
            double th = Math.Atan2(ly, lx);
            double rc = Lut(_foot, th), h;
            if (r < rc) h = FloorAt(lx, ly, r, rc, Lut(_shore, th));
            else
            {
                double w = Lut(_cliff, th), rt = rc + w;
                double t = Math.Min(1.0, (r - rc) / w);
                const double foot = FloorM + TalusM;
                double pass = Bump(th, PassDeg * Deg, 8 * Deg);
                double crest = Math.Max(foot + 80 - 120 * pass, Lut(_crest, th) + JagM(lx, ly, th) - NotchM(th) * SmoothStep(0.45, 1.0, t));
                double gully = (Ridged3(Math.Cos(th) * 11, Math.Sin(th) * 11, r * 4, 4, 5) - 0.4 + 0.5 * (Ridged3(Math.Cos(th) * 29, Math.Sin(th) * 29, r * 9, 2, 6) - 0.4)) * (1 - pass);
                if (r < rt)
                {
                    double p = 0.5 * SmoothStep(0, 1, t) + 0.5 * Math.Pow(t, 0.75);
                    p += 0.012 * Math.Sin(t * 31 + 3 * Fbm(lx * 3, ly * 3, 2, 31)) * Math.Sin(Math.PI * t);   // ledges
                    h = foot + (crest - foot) * p + 260 * gully * Math.Sin(Math.PI * Math.Min(1, t * 1.15));
                }
                else
                {
                    // the outer flank: falls away quickly below the crest, then eases onto the massif, with spurs and gullies
                    // the massif's arms (Jebel Samir to the north-east, the low ridge to the west-south-west) fall away
                    // slowly; between them the flank drops fast into the desert
                    double arm = Math.Max(Bump(th, 45 * Deg, 22 * Deg), Bump(th, 205 * Deg, 18 * Deg));
                    double spur = Math.Clamp(0.75 * arm + 0.25 * (0.5 + 0.5 * Fbm(Math.Cos(th) * 2.2 + 5, Math.Sin(th) * 2.2 - 2, 3, 71)), 0, 1);
                    double u = Math.Clamp((r - rt) / (BlendOut - rt), 0, 1), f = 1 - Math.Pow(1 - u, 0.8 + 2.4 * (1 - spur));
                    h = crest + (ReliefM(lx, ly) - crest) * f + 150 * gully * Math.Sin(Math.PI * u) * (1 - u) * (1 - u);
                }
            }
            return Math.Max(h, SpurM(lx, ly));
        }

        double FloorAt(double lx, double ly, double r, double rc, double shore)
        {
            double h = FloorM + 9 * Fbm(lx * 7, ly * 7, 3, 21);
            double talus = SmoothStep(rc - 0.12, rc, r);
            h += TalusM * talus * talus;
            h += (IslandM - h) * (1 - SmoothStep(IslandR - 0.004, IslandR + 0.004, r));
            double lake = SmoothStep(IslandR - 0.004, IslandR + 0.008, r) * (1 - SmoothStep(shore - 0.008, shore + 0.004, r));
            return h + (WaterM - 16 - h) * lake;
        }

        /// <summary>The great peak: a smooth cone on the west wall, flat on top for the temple.</summary>
        double SpurM(double lx, double ly)
        {
            double dx = lx - ShrineX, dy = ly - ShrineY, d = Math.Sqrt(dx * dx + dy * dy);
            if (d >= SpurR) return double.NegativeInfinity;
            double q = Math.Clamp((d - SummitR) / (SpurR - SummitR), 0, 1);
            return FloorM + (ShrineM - FloorM) * Math.Pow(0.5 + 0.5 * Math.Cos(Math.PI * q), 1.25);
        }

        static double JagM(double lx, double ly, double th)
        {
            double a = (240 + 340 * Math.Max(0, Math.Sin(th))) * (1 - 0.85 * Bump(th, 268 * Deg, 12 * Deg));
            return a * (Ridged(lx * 3.4 + 7, ly * 3.4 - 3, 5, 11) - 0.3) + 220 * Fbm(lx * 1.4, ly * 1.4, 3, 12);
        }

        double NotchM(double th)
        {
            double n = 0;
            foreach (var f in Falls) n += 260 * Bump(th, f.Theta, f.Width / Math.Max(0.5, f.TopR) * 1.2);
            return n;
        }

        /// <summary>The patch mesh's height (blend units) at a world point: the basin, eased onto the relief mesh's own
        /// triangles near the patch edge so the two meet without a seam.</summary>
        public double MeshUnits(double x, double y)
        {
            double design = Units(GroundM(x - Cx, y - Cy));
            double e = Math.Min(Math.Min(x - XMin, XMax - x), Math.Min(y - YMin, YMax - y));
            double b = 1 - SmoothStep(0, 0.6, e);
            return b > 0 ? design + (Relief.Coarse(x, y) - design) * b : design;
        }

        /// <summary>Heights (blend units) on a grid over the patch, row 0 to the north. corners: samples on the grid
        /// lines (a mesh); otherwise at cell centres (a texture). mesh: the seam-matched mesh surface, else the ground.</summary>
        public float[] SampleUnits(int nx, int ny, bool corners, bool mesh)
        {
            var a = new float[nx * ny];
            double sx = (XMax - XMin) / (corners ? nx - 1 : nx), sy = (YMax - YMin) / (corners ? ny - 1 : ny), o = corners ? 0 : 0.5;
            Parallel.For(0, ny, j =>
            {
                double y = YMax - (j + o) * sy;
                for (int i = 0; i < nx; i++)
                {
                    double x = XMin + (i + o) * sx;
                    a[j * nx + i] = (float)(mesh ? MeshUnits(x, y) : Units(GroundM(x - Cx, y - Cy)));
                }
            });
            return a;
        }

        /// <summary>Largest rise or fall (metres) across a footprint of half size s.</summary>
        public double Relief4(double lx, double ly, double s)
        {
            double a = GroundM(lx - s, ly), b = GroundM(lx + s, ly), c = GroundM(lx, ly - s), d = GroundM(lx, ly + s);
            return Math.Max(Math.Max(a, b), Math.Max(c, d)) - Math.Min(Math.Min(a, b), Math.Min(c, d));
        }

        // ---------------------------------------------------------------- the city

        void Generate()
        {
            var rng = new Rng(20261124);
            foreach (var deg in new[] { 0.0, 90.0, 180.0, 270.0 }) Gates.Add(new Gate(Wrap(deg * Deg)));
            for (int k = 0; k < 44; k++)
            {
                double th = Wrap((k + 0.5) * 2 * Math.PI / 44);
                if (Gates.Exists(g => AngDist(th, g.Theta) < 4.5 * Deg)) continue;
                WallTowers.Add(th);
            }
            Ziggurats.Add(new Ziggurat(0, 0.004, 0.086, 5, 0.0095, 0.0068, IslandM));
            Ziggurats.Add(new Ziggurat(-0.066, -0.012, 0.032, 3, 0.0075, 0.0052, IslandM));
            Ziggurats.Add(new Ziggurat(0.066, -0.012, 0.032, 3, 0.0075, 0.0052, IslandM));

            BuildRoad();
            BuildWater(rng);
            BuildOuterCity(rng);
            BuildInnerCity(rng);
            BuildFarms(rng);
            BuildTrees(rng);
        }

        void BuildRoad()
        {
            // legs across the great peak's face toward the city, each a little higher; Chaikin rounds the hairpins
            double a0 = Math.Atan2(-ShrineY, -ShrineX);
            const int legs = 8;
            double d0 = SpurR * 0.93, d1 = SummitR + 0.008;
            var pts = new List<Vec3>();
            for (int k = 0; k < legs; k++)
            {
                double da = d0 - (d0 - d1) * k / legs, db = d0 - (d0 - d1) * (k + 1) / legs;
                double amp = 0.55 * (0.4 + 0.6 * da / d0);
                for (int s = (k == 0 ? 0 : 1); s <= 14; s++)
                {
                    double f = s / 14.0, d = da + (db - da) * f;
                    double side = (k % 2 == 0 ? -1 : 1) * (1 - 2 * f) * amp;
                    pts.Add(new Vec3(ShrineX + d * Math.Cos(a0 + side), ShrineY + d * Math.Sin(a0 + side), 0));
                }
            }
            pts.Add(new Vec3(ShrineX + 0.5 * SummitR * Math.Cos(a0), ShrineY + 0.5 * SummitR * Math.Sin(a0), 0));
            Road = Polyline.Chaikin(pts, false, 2).ConvertAll(p => (p.X, p.Y)).ToArray();
            var start = Road[0];
            Approach = Bezier((-0.50, 0.0), (-0.57, 0.035), (start.X, start.Y), 16);
        }

        void BuildWater(Rng rng)
        {
            // three falls feed aqueducts that carry their water over the outer city to the inner wall
            foreach (var f in Falls) Pools.Add((Math.Cos(f.Theta) * (f.FootR - 0.018), Math.Sin(f.Theta) * (f.FootR - 0.018), 0.013));
            var feeds = new[] { 97 * Deg, 8 * Deg, 236 * Deg };
            var intakes = new List<(double X, double Y)>();
            foreach (var th0 in feeds)
            {
                double th = Wrap(th0), ri = Outer(th) + 0.065;
                var a = (Math.Cos(th) * ri, Math.Sin(th) * ri);
                double te = th + 2.5 * Deg, re = WallR + 0.006, rm = (ri + re) / 2, tm = th + 3.5 * Deg;
                var e = (Math.Cos(te) * re, Math.Sin(te) * re);
                var m = (Math.Cos(tm) * rm, Math.Sin(tm) * rm);
                Aqueducts.Add(Bezier(a, m, e, 28));
                intakes.Add(a);
                Pools.Add((a.Item1, a.Item2, 0.011));
            }
            // a stream from each fall's pool, meandering to the nearest intake
            foreach (var f in Falls)
            {
                int best = 0;
                for (int i = 1; i < feeds.Length; i++)
                    if (AngDist(f.Theta, Wrap(feeds[i])) < AngDist(f.Theta, Wrap(feeds[best]))) best = i;
                double r0 = f.FootR - 0.018;
                var p0 = (X: Math.Cos(f.Theta) * r0, Y: Math.Sin(f.Theta) * r0);
                var p1 = intakes[best];
                double dx = p1.X - p0.X, dy = p1.Y - p0.Y, len = Math.Sqrt(dx * dx + dy * dy);
                double nx = -dy / len, ny = dx / len, ph = rng.Next() * 6.28;
                int n = Math.Max(8, (int)(len / 0.004));
                var line = new (double X, double Y)[n + 1];
                for (int i = 0; i <= n; i++)
                {
                    double s = i / (double)n, off = 0.013 * Math.Sin(Math.PI * s) * Math.Sin(2 * Math.PI * s * len / 0.11 + ph);
                    line[i] = (p0.X + dx * s + nx * off, p0.Y + dy * s + ny * off);
                }
                Streams.Add(line);
            }
        }

        /// <summary>True where a street, the wall, an aqueduct, a stream, a pool or the road keep a footprint of radius
        /// `clear` from standing.</summary>
        public bool Blocked(double lx, double ly, double clear)
        {
            double r = Math.Sqrt(lx * lx + ly * ly), th = Math.Atan2(ly, lx);
            if (Math.Abs(r - WallR) < 0.024 + clear) return true;                               // wall and ring road
            foreach (var g in Gates)
            {
                double d = AngDist(th, g.Theta);
                if (d < Math.PI / 2 && r * Math.Sin(d) < 0.0055 + clear) return true;           // avenues and causeways
                double gx = Math.Cos(g.Theta) * (WallR + 0.045), gy = Math.Sin(g.Theta) * (WallR + 0.045);
                if (Hyp(lx - gx, ly - gy) < 0.03 + clear) return true;                           // gate squares
            }
            if (r > WallR)
            {
                for (int k = 0; k < 4; k++)
                {
                    double d = AngDist(th, Wrap((45 + 90 * k) * Deg));
                    if (d < Math.PI / 2 && r * Math.Sin(d) < 0.0035 + clear) return true;      // diagonal streets
                }
                foreach (var rs in RingStreets) if (Math.Abs(r - rs) < 0.003 + clear) return true;
            }
            foreach (var a in Aqueducts) if (DistToLine(lx, ly, a) < 0.004 + clear) return true;
            foreach (var s in Streams) if (DistToLine(lx, ly, s) < 0.004 + clear) return true;
            foreach (var p in Pools) if (Hyp(lx - p.X, ly - p.Y) < p.R + clear) return true;
            if (DistToLine(lx, ly, Approach) < 0.004 + clear || DistToLine(lx, ly, Road) < 0.004 + clear) return true;
            return false;
        }

        void BuildOuterCity(Rng rng)
        {
            for (int ring = 0; ; ring++)
            {
                double r0 = WallR + 0.031 + ring * 0.0118;
                if (r0 > 0.80) break;
                int n = (int)(2 * Math.PI * r0 / 0.0121);
                for (int i = 0; i < n; i++)
                {
                    double th = Wrap(-Math.PI + (i + 0.5 + rng.Range(-0.12, 0.12)) / n * 2 * Math.PI);
                    double r = r0 + rng.Range(-0.0012, 0.0012), ro = Outer(th);
                    double keep = (ro + 0.015 - r) / 0.05, roll = rng.Next(), skip = rng.Next();
                    double lx = r * Math.Cos(th), ly = r * Math.Sin(th);
                    if (keep > 0 && roll <= keep && skip < 0.12)
                    {
                        // a courtyard: now and then a palm or a cypress in it
                        if (skip < 0.05 && !Blocked(lx, ly, 0.003) && Relief4(lx, ly, 0.006) < 14) AddTree(rng, lx, ly, skip < 0.015, 0.9);
                        continue;
                    }
                    if (keep <= 0 || roll > keep) continue;
                    if (Blocked(lx, ly, 0.004) || Relief4(lx, ly, 0.006) > 14) continue;
                    bool tower = rng.Next() < 0.06;
                    double w = tower ? 0.0056 : 0.0074 + 0.003 * rng.Next(), d = tower ? 0.0056 : 0.0066 + 0.0026 * rng.Next();
                    double near = 1 + 0.35 * (1 - Math.Clamp((r - WallR) / 0.25, 0, 1)), q = rng.Next();
                    double h = tower ? 0.014 + 0.006 * rng.Next() : (0.0042 + 0.0065 * q * q) * near;
                    bool garden = !tower && rng.Next() < 0.09;
                    Buildings.Add(new Building(lx, ly, w, d, h, th + Math.PI / 2 + rng.Range(-0.04, 0.04),
                                               tower ? Kind.Tower : Kind.House, garden, GroundM(lx, ly), rng.U()));
                }
            }
        }

        void BuildInnerCity(Rng rng)
        {
            // villas along the four causeways between the lake and the wall
            foreach (var g in Gates)
                for (double s = Shore(g.Theta) + 0.024; s < WallR - 0.02; s += 0.016)
                    foreach (var side in new[] { -1.0, 1.0 })
                    {
                        if (rng.Next() > 0.65) continue;
                        double c = Math.Cos(g.Theta), sn = Math.Sin(g.Theta);
                        double lx = c * s - sn * side * 0.0105, ly = sn * s + c * side * 0.0105;
                        Buildings.Add(new Building(lx, ly, 0.008, 0.0068, 0.0042 + 0.002 * rng.Next(), g.Theta + Math.PI / 2,
                                                   Kind.Villa, rng.Next() < 0.3, GroundM(lx, ly), rng.U()));
                    }
        }

        void BuildFarms(Rng rng)
        {
            for (int k = 0; k < 400 && Hamlets.Count < 30; k++)
            {
                double th = Wrap(rng.Range(-Math.PI, Math.PI)), lo = Outer(th) + 0.05, hi = Foot(th) - 0.05;
                double r = rng.Range(lo, hi);
                if (hi <= lo) continue;
                double hx = r * Math.Cos(th), hy = r * Math.Sin(th);
                if (Blocked(hx, hy, 0.012) || Relief4(hx, hy, 0.012) > 20 || Hamlets.Exists(h => Hyp(h.X - hx, h.Y - hy) < 0.06)) continue;
                Hamlets.Add((hx, hy, 0.016));
                int n = 3 + (int)(rng.Next() * 4);
                for (int i = 0; i < n; i++)
                {
                    double a = rng.Range(0, 2 * Math.PI), d = rng.Range(0.002, 0.014);
                    double lx = hx + d * Math.Cos(a), ly = hy + d * Math.Sin(a);
                    if (Blocked(lx, ly, 0.003) || Relief4(lx, ly, 0.005) > 14) continue;
                    Buildings.Add(new Building(lx, ly, 0.006 + 0.002 * rng.Next(), 0.0052 + 0.0016 * rng.Next(), 0.0034 + 0.0016 * rng.Next(),
                                               th + rng.Range(-0.5, 0.5), Kind.Farm, false, GroundM(lx, ly), rng.U()));
                }
            }
        }

        void AddTree(Rng rng, double lx, double ly, bool cypress, double scale = 1)
        {
            double r = (cypress ? 0.0016 : 0.0026 + 0.0014 * rng.Next()) * scale;
            double h = (cypress ? 0.0095 + 0.003 * rng.Next() : 0.0048 + 0.0022 * rng.Next()) * scale;
            Trees.Add(new Tree(lx, ly, r, h, cypress, GroundM(lx, ly)));
        }

        void BuildTrees(Rng rng)
        {
            // rows along the canals and the causeways
            for (int k = 0; k < 8; k++)
            {
                double th = Wrap((22.5 + 45 * k) * Deg), c = Math.Cos(th), s = Math.Sin(th);
                for (double r = Shore(th) + 0.016; r < WallR - 0.012; r += 0.0075)
                    foreach (var side in new[] { -0.0042, 0.0042 })
                        AddTree(rng, c * r - s * side, s * r + c * side, false, 0.9);
            }
            // the lake shore, the island garden
            for (double th = -Math.PI; th < Math.PI; th += 0.03)
            {
                double r = Shore(th) + 0.007;
                if (Gates.Exists(g => AngDist(th, g.Theta) * r < 0.008)) continue;
                AddTree(rng, r * Math.Cos(th), r * Math.Sin(th), rng.Next() < 0.25);
                if (rng.Next() < 0.5) { double r2 = r + 0.008; AddTree(rng, r2 * Math.Cos(th + 0.012), r2 * Math.Sin(th + 0.012), false, 0.85); }
            }
            for (double th = -Math.PI; th < Math.PI; th += 0.11)
            {
                if (Gates.Exists(g => AngDist(th, g.Theta) < 0.09)) continue;
                double r = IslandR - 0.009;
                AddTree(rng, r * Math.Cos(th), r * Math.Sin(th), true);
            }
            // along the avenues out to the cliffs
            foreach (var g in Gates)
            {
                double c = Math.Cos(g.Theta), s = Math.Sin(g.Theta);
                for (double r = Outer(g.Theta) + 0.03; r < Foot(g.Theta) - 0.03; r += 0.011)
                    foreach (var side in new[] { -0.0085, 0.0085 })
                        if (rng.Next() < 0.8) AddTree(rng, c * r - s * side, s * r + c * side, g.Theta > 0 && g.Theta < 2);
            }
            // orchards in the farmland, trees round the fields inside the wall, woods on the talus under the cliffs
            for (double y = -1.25; y < 1.25; y += 0.0062)
                for (double x = -1.25; x < 1.25; x += 0.0062)
                {
                    double jx = x + rng.Range(-0.0012, 0.0012), jy = y + rng.Range(-0.0012, 0.0012);
                    double r = Hyp(jx, jy), th = Math.Atan2(jy, jx), roll = rng.Next();
                    if (r < WallR) continue;
                    double rc = Foot(th);
                    if (r > Outer(th) + 0.025 && r < rc - 0.02)
                    {
                        if (FarmField(jx, jy) >= 201 && roll < 0.85 && !Blocked(jx, jy, 0.003)) AddTree(rng, jx, jy, false, 0.85);
                    }
                    else if (r >= rc - 0.08 && r < rc + 0.06)
                    {
                        double dens = 0.6 * (Fbm(jx * 12, jy * 12, 3, 41) + 0.35) * (1 - SmoothStep(rc, rc + 0.06, r));
                        if (roll < dens && !Blocked(jx, jy, 0.003)) AddTree(rng, jx, jy, rng.Next() < 0.15, 0.95);
                    }
                }
        }

        // ---------------------------------------------------------------- ground layout texture

        /// <summary>Field id under a local point in the farmland outside the city: 1..200 a crop, 201+ an orchard.</summary>
        public static int FarmField(double lx, double ly)
        {
            double r = Hyp(lx, ly) + 0.018 * Fbm(lx * 5, ly * 5, 2, 51);
            double th = Math.Atan2(ly, lx) + 0.06 * Fbm(lx * 4 + 3, ly * 4, 2, 52);
            int ring = (int)Math.Floor((r - 0.6) / 0.048);
            int ns = Math.Max(12, (int)Math.Round(2 * Math.PI * Math.Max(r, 0.3) / 0.062));
            int sec = (int)Math.Floor((th + Math.PI) / (2 * Math.PI) * ns);
            uint h = Hash(ring, sec, 2);
            return (h & 1023) < 205 ? 201 + (int)(h >> 10) % 50 : 1 + (int)(h >> 10) % 200;
        }

        /// <summary>The ground layout over the square ±FineHalf round the centre, res x res RGBA, row 0 to the north:
        /// R water, G field id (0 none or a field edge, 1..200 crops, 201+ gardens and orchards), B paving, A road.</summary>
        public byte[] PaintLayout(int res)
        {
            var img = new byte[res * res * 4];
            double px = 2 * FineHalf / res;
            Parallel.For(0, res, py =>
            {
                double ly = FineHalf - (py + 0.5) * px;
                for (int ix = 0; ix < res; ix++)
                {
                    double lx = -FineHalf + (ix + 0.5) * px;
                    double r = Hyp(lx, ly), th = Math.Atan2(ly, lx);
                    double shore = Shore(th), ro = Outer(th), rc = Foot(th);
                    double water = 0, pave = 0, road = 0;
                    int field = 0;
                    double Cov(double d) => Math.Clamp(0.5 + d / px, 0, 1);                  // coverage of an edge d inside
                    // lake and island
                    water = Math.Max(water, Math.Min(Cov(r - IslandR), Cov(shore - r)));
                    if (r < IslandR) { pave = Cov(IslandR - 0.016 - r); if (pave < 1) field = 220; }
                    // inner fields, canals, causeways, the lake promenade
                    if (r > shore && r < WallR)
                    {
                        if (r > shore + 0.012 && r < WallR - 0.008) field = InnerField(r, th, shore, px);
                        else if (r <= shore + 0.012) field = 230;
                        road = Math.Max(road, Math.Min(Cov(r - shore - 0.0035), Cov(shore + 0.0075 - r)));
                        for (int k = 0; k < 8; k++)
                        {
                            double d = AngDist(th, Wrap((22.5 + 45 * k) * Deg));
                            if (d < Math.PI / 2 && r < WallR - 0.006) water = Math.Max(water, Cov(0.0017 - r * Math.Sin(d)));
                        }
                    }
                    // gate axes: causeways inside, avenues through the city, lanes out to the cliffs (the south one over the pass)
                    for (int k = 0; k < 4; k++)
                    {
                        double gth = Wrap(k * 90 * Deg), d = AngDist(th, gth);
                        if (d >= Math.PI / 2 || r < shore) continue;
                        double hw = r < WallR ? 0.0028 : r < ro + 0.01 ? 0.0045 : 0.003;
                        double end = k == 3 ? 1.65 : Foot(gth) - 0.02;
                        if (r < end) road = Math.Max(road, Cov(hw - r * Math.Sin(d)));
                    }
                    // the wall band, the ring road, the outer city with its streets
                    if (Math.Abs(r - WallR) < 0.0065) pave = Math.Max(pave, Cov(0.0065 - Math.Abs(r - WallR)));
                    if (r > WallR + 0.006 && r < WallR + 0.017) road = Math.Max(road, Math.Min(Cov(r - WallR - 0.006), Cov(WallR + 0.017 - r)));
                    double edge = ro + 0.012 + 0.008 * Fbm(lx * 30, ly * 30, 2, 61);
                    if (r > WallR)
                    {
                        pave = Math.Max(pave, Cov(edge - r));
                        if (r < edge)
                        {
                            for (int k = 0; k < 4; k++)
                            {
                                double d = AngDist(th, Wrap((45 + 90 * k) * Deg));
                                if (d < Math.PI / 2) road = Math.Max(road, Cov(0.0028 - r * Math.Sin(d)));
                            }
                            foreach (var rs in RingStreets) road = Math.Max(road, Cov(0.0024 - Math.Abs(r - rs)));
                        }
                    }
                    // farmland out to the cliff foot
                    if (r > edge + 0.008 && r < rc - 0.004)
                    {
                        field = FarmField(lx, ly);
                        if (FieldEdge(lx, ly, px)) field = 0;
                    }
                    // nothing is laid out on the great peak's slopes, but the temple has its platform
                    if (SpurM(lx, ly) > FloorM + 30) { field = 0; pave = 0; road = 0; }
                    pave = Math.Max(pave, Cov(SummitR - Hyp(lx - ShrineX, ly - ShrineY)));
                    int o = (py * res + ix) * 4;
                    img[o] = (byte)(water * 255 + 0.5);
                    img[o + 1] = (byte)field;
                    img[o + 2] = (byte)(pave * 255 + 0.5);
                    img[o + 3] = (byte)(road * 255 + 0.5);
                }
            });
            // lines and discs stamped on top
            foreach (var s in Streams) Stamp(img, res, s, 0.0022, 0);
            foreach (var p in Pools) Disc(img, res, p.X, p.Y, p.R, 0);
            foreach (var h in Hamlets) Disc(img, res, h.X, h.Y, h.R, 2, 0.6);
            Stamp(img, res, Approach, 0.0028, 3);
            return img;
        }

        static int InnerField(double r, double th, double shore, double px)
        {
            double r0 = shore + 0.012, rr = (r - r0) / 0.03;
            int ring = (int)Math.Floor(rr);
            int ns = Math.Max(8, (int)Math.Round(2 * Math.PI * (r0 + (ring + 0.5) * 0.03) / 0.038));
            double sf = (th + Math.PI) / (2 * Math.PI) * ns + ring * 0.37;
            int sec = (int)Math.Floor(sf);
            double edge = Math.Min(Math.Min(rr - ring, ring + 1 - rr) * 0.03, Math.Min(sf - sec, sec + 1 - sf) / ns * 2 * Math.PI * r);
            if (edge < 0.0009 + px * 0.5) return 0;
            return 1 + (int)(Hash(ring, sec, 3) % 200);
        }

        static bool FieldEdge(double lx, double ly, double px)
        {
            int f = FarmField(lx, ly);
            double e = 0.0011 + px * 0.5;
            return FarmField(lx + e, ly) != f || FarmField(lx - e, ly) != f || FarmField(lx, ly + e) != f || FarmField(lx, ly - e) != f;
        }

        static void Stamp(byte[] img, int res, (double X, double Y)[] line, double half, int ch)
        {
            for (int i = 0; i + 1 < line.Length; i++)
            {
                double dx = line[i + 1].X - line[i].X, dy = line[i + 1].Y - line[i].Y, len = Hyp(dx, dy);
                int n = Math.Max(1, (int)(len / (half * 0.5)));
                for (int k = 0; k < n; k++) Disc(img, res, line[i].X + dx * k / n, line[i].Y + dy * k / n, half, ch);
            }
        }

        static void Disc(byte[] img, int res, double cx, double cy, double rad, int ch, double value = 1)
        {
            double px = 2 * FineHalf / res;
            int x0 = (int)Math.Floor((cx - rad + FineHalf) / px) - 1, x1 = (int)Math.Ceiling((cx + rad + FineHalf) / px) + 1;
            int y0 = (int)Math.Floor((FineHalf - cy - rad) / px) - 1, y1 = (int)Math.Ceiling((FineHalf - cy + rad) / px) + 1;
            for (int y = Math.Max(0, y0); y <= Math.Min(res - 1, y1); y++)
                for (int x = Math.Max(0, x0); x <= Math.Min(res - 1, x1); x++)
                {
                    double lx = -FineHalf + (x + 0.5) * px, ly = FineHalf - (y + 0.5) * px;
                    double c = Math.Clamp(0.5 + (rad - Hyp(lx - cx, ly - cy)) / px, 0, 1) * value;
                    int o = (y * res + x) * 4 + ch;
                    img[o] = Math.Max(img[o], (byte)(c * 255 + 0.5));
                }
        }

        // ---------------------------------------------------------------- maths

        public static double SmoothStep(double a, double b, double x)
        {
            double t = Math.Clamp((x - a) / (b - a), 0, 1);
            return t * t * (3 - 2 * t);
        }

        static double Hyp(double x, double y) => Math.Sqrt(x * x + y * y);
        public static double Wrap(double a) => Math.IEEERemainder(a, 2 * Math.PI);
        public static double AngDist(double a, double b) => Math.Abs(Math.IEEERemainder(a - b, 2 * Math.PI));
        static double Bump(double th, double c, double w) { double d = AngDist(th, c) / w; return Math.Exp(-d * d); }

        static double Wobble(double th, int seed)
        {
            double s = 0;
            for (int k = 2; k <= 7; k++) s += Math.Sin(k * th + 6.2831853 * (Hash(k, seed, 99) & 0xFFFF) / 65536.0) / k;
            return s / 1.59;
        }

        public static double DistToLine(double x, double y, (double X, double Y)[] line)
        {
            double best = double.MaxValue;
            for (int i = 0; i + 1 < line.Length; i++)
            {
                double ax = line[i].X, ay = line[i].Y, bx = line[i + 1].X - ax, by = line[i + 1].Y - ay;
                double t = Math.Clamp(((x - ax) * bx + (y - ay) * by) / Math.Max(1e-12, bx * bx + by * by), 0, 1);
                best = Math.Min(best, Hyp(x - ax - bx * t, y - ay - by * t));
            }
            return best;
        }

        static (double X, double Y)[] Bezier((double X, double Y) a, (double X, double Y) m, (double X, double Y) b, int n)
        {
            var p = new (double X, double Y)[n + 1];
            for (int i = 0; i <= n; i++)
            {
                double t = i / (double)n, u = 1 - t;
                p[i] = (u * u * a.X + 2 * u * t * m.X + t * t * b.X, u * u * a.Y + 2 * u * t * m.Y + t * t * b.Y);
            }
            return p;
        }

        static uint Hash(int x, int y, int seed)
        {
            unchecked
            {
                uint h = (uint)x * 374761393u + (uint)y * 668265263u + (uint)seed * 2246822519u;
                h = (h ^ (h >> 13)) * 1274126177u;
                return h ^ (h >> 16);
            }
        }

        static uint Hash3(int x, int y, int z, int seed) => Hash(x, unchecked(y * 31 + z * 1013), seed);
        static double Fade(double t) => t * t * (3 - 2 * t);

        static double Value(double x, double y, int seed)
        {
            int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y);
            double fx = Fade(x - xi), fy = Fade(y - yi);
            double a = Hash(xi, yi, seed) / 4294967296.0, b = Hash(xi + 1, yi, seed) / 4294967296.0;
            double c = Hash(xi, yi + 1, seed) / 4294967296.0, d = Hash(xi + 1, yi + 1, seed) / 4294967296.0;
            return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
        }

        static double Value3(double x, double y, double z, int seed)
        {
            int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y), zi = (int)Math.Floor(z);
            double fx = Fade(x - xi), fy = Fade(y - yi), fz = Fade(z - zi);
            double L(int i, int j, int k) => Hash3(xi + i, yi + j, zi + k, seed) / 4294967296.0;
            double x00 = L(0, 0, 0) + (L(1, 0, 0) - L(0, 0, 0)) * fx, x10 = L(0, 1, 0) + (L(1, 1, 0) - L(0, 1, 0)) * fx;
            double x01 = L(0, 0, 1) + (L(1, 0, 1) - L(0, 0, 1)) * fx, x11 = L(0, 1, 1) + (L(1, 1, 1) - L(0, 1, 1)) * fx;
            double y0 = x00 + (x10 - x00) * fy, y1 = x01 + (x11 - x01) * fy;
            return y0 + (y1 - y0) * fz;
        }

        /// <summary>Fractal value noise, about -1..1.</summary>
        static double Fbm(double x, double y, int oct, int seed)
        {
            double s = 0, a = 0.5, n = 0;
            for (int o = 0; o < oct; o++) { s += (2 * Value(x, y, seed + o) - 1) * a; n += a; a *= 0.5; x *= 2.03; y *= 2.03; }
            return s / n;
        }

        /// <summary>Ridged multifractal, 0..1: sharp crests.</summary>
        static double Ridged(double x, double y, int oct, int seed)
        {
            double s = 0, a = 0.5, wgt = 1, n = 0;
            for (int o = 0; o < oct; o++)
            {
                double v = 1 - Math.Abs(2 * Value(x, y, seed + o) - 1);
                v *= v * wgt;
                wgt = Math.Clamp(v * 2, 0, 1);
                s += v * a; n += a; a *= 0.5; x *= 2.03; y *= 2.03;
            }
            return s / n;
        }

        static double Ridged3(double x, double y, double z, int oct, int seed)
        {
            double s = 0, a = 0.5, wgt = 1, n = 0;
            for (int o = 0; o < oct; o++)
            {
                double v = 1 - Math.Abs(2 * Value3(x, y, z, seed + o) - 1);
                v *= v * wgt;
                wgt = Math.Clamp(v * 2, 0, 1);
                s += v * a; n += a; a *= 0.5; x *= 2.03; y *= 2.03; z *= 2.03;
            }
            return s / n;
        }

        sealed class Rng
        {
            ulong _s;
            public Rng(ulong seed) { _s = seed * 0x9E3779B97F4A7C15UL + 1; }
            public double Next() { _s ^= _s << 13; _s ^= _s >> 7; _s ^= _s << 17; return (_s >> 11) * (1.0 / (1UL << 53)); }
            public double Range(double a, double b) => a + (b - a) * Next();
            public uint U() => (uint)(Next() * uint.MaxValue);
        }
    }
}
