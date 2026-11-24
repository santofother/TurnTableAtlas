"""
Fantasy Capital - procedural mini model (100 m x 100 m) for Blender 5.x

Built from a painted reference: a crescent harbour city with twin lighthouse
moles, a cliff-top palace, colosseum, a hippodrome opening onto the harbour,
domed baths, forum & temples, theatre,
crenellated walls and gates, an aqueduct striding in from the hills, river,
farmland patchwork, forests, villas, mountains and a fleet of ships.

Usage (inside Blender):
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("fantasy_capital", "/path/to/fantasy_capital.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.build_all()

Everything lives in the "Fantasy Capital" collection; re-running rebuilds it.
Units: metres. The model spans X,Y in [-50, 50]; sea level is Z = 0.
"""
import bpy
import math
import time
import numpy as np

HALF = 50.0
ROOT_NAME = "Fantasy Capital"

# =============================================================================
# Layout (model metres; +X east, +Y north; the sea lies south and east)
# =============================================================================
COAST_LINE = [(-56, -17), (-47, -19), (-43, -21.2), (-40, -22.8), (-37, -26), (-33, -27.6),
              (-28, -27.2), (-24, -25.8), (-19.5, -22.2), (-15.6, -19.4), (-14.2, -16.6),
              (-13.6, -12), (-12.6, -7), (-10.2, -2.6), (-5.2, 0.4), (1, 1.9), (7, 1.4),
              (12, -1.2), (15.4, -6), (17, -11), (18.1, -15.6), (20.2, -19.6), (24.5, -20.4),
              (30.5, -18.4), (37.6, -12.8), (40.4, -4), (39.4, 6.5), (40.8, 15), (44, 24),
              (47, 33), (51.5, 42), (56, 47)]
COAST_POLY = COAST_LINE + [(56, 56), (-56, 56)]
HARBOR = COAST_LINE[9:22]                 # inner harbour quay line (land on the left)
HARBOR_CENTER = (2.0, -9.0)

WALL_PATH = [(-16.2, -18.4), (-19.8, -20.9), (-24, -24.2), (-28.5, -25.6), (-33, -26.0),
             (-36.4, -24.4), (-38.6, -21), (-39.6, -15), (-39.2, -7), (-37.8, 0), (-35.5, 6.5),
             (-31.5, 13), (-25.5, 18.6), (-17.5, 23.4), (-9.2, 26.6), (2, 27.8), (13.5, 26.8),
             (24, 23), (31, 17.6), (35.2, 10), (38.2, 2), (38.9, -4), (36.4, -11.4),
             (30, -16.8), (24.5, -18.8), (20.6, -18.4)]
W_MOLE = [(-15.6, -19.4), (-12, -21.4), (-7.5, -23.0), (-3.2, -23.8)]
E_MOLE = [(20.2, -19.6), (17.5, -22.6), (13, -24.2), (8.6, -24.6)]
GATES = [(2.0, 27.8), (-35.5, 6.5), (33.3, 13.4)]

RIVER = [(-43.5, 51), (-42, 45), (-45, 38), (-42.5, 31), (-44.5, 24), (-42.5, 16), (-44.8, 8),
         (-43.5, 0), (-45.2, -8), (-44.5, -14), (-46, -19.5), (-47, -24)]
AQUEDUCT = [(-50.2, 31.0), (-44, 31.6), (-36, 31.0), (-26, 30.0), (-17, 28.6), (-9.6, 27.4)]
ROADS = [
    [(2, 28.6), (1.6, 32), (-0.5, 37), (-3.5, 43), (-3, 50)],
    [(-36.3, 6.8), (-40, 9), (-43.5, 11), (-47, 14), (-50, 16)],
    [(34.2, 14.2), (36.2, 19), (38.3, 27), (41, 36), (44.5, 44), (46.5, 50)],
]
AVENUES = [  # (polyline, width) - kept free of houses
    ([(1.0, 1.6), (1.4, 7.2)], 1.3),
    ([(1.6, 19.2), (2.0, 27.8)], 1.3),
    ([(-6.5, 2.0), (-14, 4.0), (-24, 5.0), (-35.5, 6.5)], 1.0),
    ([(9.3, 12.5), (14.5, 14.8), (21.5, 18.0), (28, 17.0), (33.3, 13.4)], 1.0),
    ([(17.9, -9.2), (24, -8.3), (29.5, -8.7), (37.0, -8.0)], 0.9),       # east harbour road (south of hippodrome)
    ([(-9.6, 24.6), (-6, 20), (-1.5, 17.5)], 0.8),
    ([(-13.5, -3), (-20, -4), (-29, -6), (-37, -8)], 0.8),
    ([(12.4, -0.5), (17.5, 1.6), (24.0, 4.8)], 0.9),                    # promenade: harbour -> colosseum
]
PAVED_AVENUES = (0, 1, 3, 7)
PIERS = [((-13.0, -10.2), (-8.2, -10.8)), ((-11.1, -4.6), (-7.4, -5.4)),
         ((17.4, -13.6), (10.2, -14.6)), ((15.7, -7.6), (10.6, -8.4)),
         ((-2.5, 0.85), (-2.8, -3.0)), ((5.0, 1.35), (5.3, -2.4))]
PLATEAU = (-31.0, -18.5, 9.5, 7.5)        # palace headland ellipse (cx, cy, rx, ry)
# Hippodrome: straight (open) short end sits on the harbour quay, curved end points inland toward the colosseum
HIPPO = (15.2, -5.0, 25.0, 19.0, 5.6)     # open-end centre x, y, axis heading (deg), length, width
HIPPO_Z = 0.55                            # levelled ground height under the track


def hippo_local(x, y):
    """World XY -> hippodrome local coords (lx along the axis from the open end, ly across)."""
    x0, y0, a, _, _ = HIPPO
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    dx = np.asarray(x, float) - x0
    dy = np.asarray(y, float) - y0
    return dx * c + dy * s, -dx * s + dy * c

# =============================================================================
# Palette (sRGB)
# =============================================================================
WALL_COLS = [(0.88, 0.80, 0.64), (0.82, 0.68, 0.50), (0.92, 0.86, 0.74), (0.85, 0.71, 0.58),
             (0.78, 0.63, 0.47), (0.93, 0.89, 0.81), (0.86, 0.74, 0.62)]
ROOF_COLS = [(0.66, 0.30, 0.17), (0.72, 0.37, 0.21), (0.58, 0.25, 0.15), (0.76, 0.45, 0.28),
             (0.63, 0.34, 0.22), (0.70, 0.41, 0.29), (0.54, 0.27, 0.18)]
STONE = (0.80, 0.71, 0.56)
STONE_D = (0.67, 0.59, 0.46)
STONE_TOP = (0.74, 0.66, 0.52)
MARBLE = (0.93, 0.90, 0.83)
MARBLE_D = (0.80, 0.76, 0.68)
STUCCO = (0.90, 0.84, 0.72)
TRAV = (0.86, 0.76, 0.60)
TRAV_D = (0.72, 0.62, 0.48)
ROOF = (0.66, 0.31, 0.18)
LEAD = (0.62, 0.64, 0.66)
DARK = (0.10, 0.08, 0.07)
WIN = (0.17, 0.12, 0.09)
GRASS = (0.33, 0.45, 0.18)
POOL = (0.22, 0.62, 0.68)
GOLD = (0.85, 0.66, 0.28)
PAVE = (0.84, 0.79, 0.70)
WOOD = (0.42, 0.29, 0.17)
WOOD_D = (0.26, 0.16, 0.09)
SAIL = (0.93, 0.87, 0.74)
SAIL_RED = (0.62, 0.14, 0.08)
CYPRESS = (0.11, 0.20, 0.09)
PINE = (0.17, 0.32, 0.12)
OLIVE = (0.42, 0.52, 0.30)
OAK = (0.21, 0.36, 0.13)
ROCK = (0.55, 0.50, 0.44)


# =============================================================================
# Math helpers
# =============================================================================
def lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin4(c):
    l = lin(c[:3])
    return (float(l[0]), float(l[1]), float(l[2]), 1.0)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def points_in_poly(px, py, poly):
    px = np.asarray(px, float)
    py = np.asarray(py, float)
    inside = np.zeros(px.shape, bool)
    x0, y0 = poly[-1]
    for x1, y1 in poly:
        cond = (y1 > py) != (y0 > py)
        with np.errstate(divide='ignore', invalid='ignore'):
            xint = (x0 - x1) * (py - y1) / (y0 - y1) + x1
        inside ^= cond & (px < xint)
        x0, y0 = x1, y1
    return inside


def dist_to_polyline(px, py, pts, closed=False):
    px = np.asarray(px, float)
    py = np.asarray(py, float)
    P = np.asarray(pts, float)
    segs = list(zip(P[:-1], P[1:]))
    if closed:
        segs.append((P[-1], P[0]))
    d = np.full(px.shape, np.inf)
    for a, b in segs:
        ab = b - a
        L2 = float(ab @ ab)
        t = np.clip(((px - a[0]) * ab[0] + (py - a[1]) * ab[1]) / L2, 0.0, 1.0)
        d = np.minimum(d, np.hypot(px - (a[0] + t * ab[0]), py - (a[1] + t * ab[1])))
    return d


def _hash(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFF) / 65535.0


def vnoise(x, y, seed=0):
    xf = np.floor(x)
    yf = np.floor(y)
    tx = x - xf
    ty = y - yf
    xi = xf.astype(np.int64)
    yi = yf.astype(np.int64)
    u = tx * tx * (3 - 2 * tx)
    v = ty * ty * (3 - 2 * ty)
    a = _hash(xi, yi, seed)
    b = _hash(xi + 1, yi, seed)
    c = _hash(xi, yi + 1, seed)
    d = _hash(xi + 1, yi + 1, seed)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v


def fbm(x, y, octaves=5, seed=0):
    total = np.zeros_like(np.asarray(x, float))
    amp, freq, norm = 0.5, 1.0, 0.0
    for i in range(octaves):
        total = total + amp * vnoise(x * freq, y * freq, seed + i * 17)
        norm += amp
        amp *= 0.5
        freq *= 2.03
    return total / norm


def resample(pts, step):
    P = [np.asarray(p, float) for p in pts]
    out = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        n = max(1, int(round(np.linalg.norm(b - a) / step)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return np.array(out)


def polyline_normals(P):
    P = np.asarray(P, float)
    d = np.zeros_like(P)
    d[1:-1] = P[2:] - P[:-2]
    d[0] = P[1] - P[0]
    d[-1] = P[-1] - P[-2]
    d /= np.linalg.norm(d, axis=1)[:, None]
    return np.column_stack([-d[:, 1], d[:, 0]])      # left normals


def arclen(P):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])


def at_arc(P, s_arr, s):
    return np.array([np.interp(s, s_arr, P[:, 0]), np.interp(s, s_arr, P[:, 1])])


def rect_pts(cx, cy, w, d, ang):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + lx * c - ly * s, cy + lx * s + ly * c)
            for lx, ly in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))]


def L2W(cx, cy, ang, lx, ly):
    c, s = math.cos(ang), math.sin(ang)
    return (cx + lx * c - ly * s, cy + lx * s + ly * c)


def newell(R):
    nx = ny = nz = 0.0
    k = len(R)
    for i in range(k):
        a = R[i]
        b = R[(i + 1) % k]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx, ny, nz)


def jit(rng, c, a=0.05):
    f = 1.0 + rng.uniform(-a, a)
    return tuple(min(1.0, max(0.0, x * f * (1.0 + rng.uniform(-a / 3, a / 3)))) for x in c)


def lighten(c, k=1.08):
    return tuple(min(1.0, x * k) for x in c)


# =============================================================================
# Mesh builder (one "Col" colour per face; shared "CAP_Painted" material)
# =============================================================================
class MB:
    def __init__(self):
        self.v, self.f, self.c, self.s, self.m = [], [], [], [], []

    def vid(self, pts):
        b = len(self.v)
        self.v.extend((float(p[0]), float(p[1]), float(p[2])) for p in pts)
        return b

    def face(self, idx, col, smooth=False, mat=0):
        self.f.append(tuple(idx))
        self.c.append(col)
        self.s.append(smooth)
        self.m.append(mat)

    def poly(self, pts, col, smooth=False, mat=0):
        b = self.vid(pts)
        self.face(range(b, b + len(pts)), col, smooth, mat)

    def poly_facing(self, pts, want, col, mat=0):
        n = newell(pts)
        if n[0] * want[0] + n[1] * want[1] + n[2] * want[2] < 0:
            pts = pts[::-1]
        self.poly(pts, col, False, mat)

    def extrude(self, ring, off, col, col_top=None, top=True, bottom=False, smooth=False, mat=0):
        R = [(float(p[0]), float(p[1]), float(p[2])) for p in ring]
        n = newell(R)
        if n[0] * off[0] + n[1] * off[1] + n[2] * off[2] < 0:
            R = R[::-1]
        k = len(R)
        T = [(p[0] + off[0], p[1] + off[1], p[2] + off[2]) for p in R]
        b = self.vid(R)
        t = self.vid(T)
        for i in range(k):
            j = (i + 1) % k
            self.face((b + i, b + j, t + j, t + i), col, smooth, mat)
        if top:
            self.face(tuple(t + i for i in range(k)), col_top if col_top is not None else col, False, mat)
        if bottom:
            self.face(tuple(b + i for i in reversed(range(k))), col, False, mat)

    def box(self, cx, cy, z0, w, d, h, ang=0.0, col=STONE, col_top=None, top=True, mat=0):
        if h <= 1e-4:
            return
        self.extrude([(x, y, z0) for x, y in rect_pts(cx, cy, w, d, ang)], (0, 0, h), col, col_top, top, mat=mat)

    def prism(self, pts2d, z0, h, col, col_top=None, top=True, mat=0):
        self.extrude([(x, y, z0) for x, y in pts2d], (0, 0, h), col, col_top, top, mat=mat)

    def cyl(self, cx, cy, z0, r, h, n=12, col=STONE, col_top=None, top=True, smooth=False, rx=None, ry=None, mat=0):
        rx = r if rx is None else rx
        ry = r if ry is None else ry
        ring = [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n), z0) for k in range(n)]
        self.extrude(ring, (0, 0, h), col, col_top, top, smooth=smooth, mat=mat)

    def hip_roof(self, cx, cy, z, w, d, ang, rh, col, ov=0.04):
        if d > w:
            w, d, ang = d, w, ang + math.pi / 2
        W, D = w / 2 + ov, d / 2 + ov
        R = W - D
        e = [L2W(cx, cy, ang, -W, -D), L2W(cx, cy, ang, W, -D), L2W(cx, cy, ang, W, D), L2W(cx, cy, ang, -W, D)]
        if R < 1e-3:
            b = self.vid([(p[0], p[1], z) for p in e] + [(cx, cy, z + rh)])
            for i in range(4):
                self.face((b + i, b + (i + 1) % 4, b + 4), col)
            return
        r0 = L2W(cx, cy, ang, -R, 0)
        r1 = L2W(cx, cy, ang, R, 0)
        b = self.vid([(p[0], p[1], z) for p in e] + [(r0[0], r0[1], z + rh), (r1[0], r1[1], z + rh)])
        E0, E1, E2, E3, R0, R1 = b, b + 1, b + 2, b + 3, b + 4, b + 5
        self.face((E0, E1, R1, R0), col)
        self.face((E1, E2, R1), col)
        self.face((E2, E3, R0, R1), col)
        self.face((E3, E0, R0), col)

    def gable_roof(self, cx, cy, z, w, d, ang, rh, col, col_gable, ov=0.04, axis='long'):
        swap = (axis == 'long' and d > w) or axis == 'y'
        if swap:
            w, d, ang = d, w, ang + math.pi / 2
        W, D = w / 2 + ov, d / 2 + ov
        e = [L2W(cx, cy, ang, -W, -D), L2W(cx, cy, ang, W, -D), L2W(cx, cy, ang, W, D), L2W(cx, cy, ang, -W, D)]
        r0 = L2W(cx, cy, ang, -W, 0)
        r1 = L2W(cx, cy, ang, W, 0)
        b = self.vid([(p[0], p[1], z) for p in e] + [(r0[0], r0[1], z + rh), (r1[0], r1[1], z + rh)])
        E0, E1, E2, E3, R0, R1 = b, b + 1, b + 2, b + 3, b + 4, b + 5
        self.face((E0, E1, R1, R0), col)
        self.face((E2, E3, R0, R1), col)
        self.face((E1, E2, R1), col_gable)
        self.face((E3, E0, R0), col_gable)

    def dome(self, cx, cy, z, r, hs, col, n=20, lat=6):
        rings = []
        for i in range(lat):
            a = (math.pi / 2) * i / lat
            rr = r * math.cos(a)
            zz = z + r * hs * math.sin(a)
            rings.append(self.vid([(cx + rr * math.cos(2 * math.pi * k / n), cy + rr * math.sin(2 * math.pi * k / n), zz)
                                   for k in range(n)]))
        top = self.vid([(cx, cy, z + r * hs)])
        for i in range(lat - 1):
            for k in range(n):
                k2 = (k + 1) % n
                self.face((rings[i] + k, rings[i] + k2, rings[i + 1] + k2, rings[i + 1] + k), col, True)
        for k in range(n):
            self.face((rings[-1] + k, rings[-1] + (k + 1) % n, top), col, True)

    def cone(self, cx, cy, z, r, h, col, n=8):
        b = self.vid([(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), z)
                      for k in range(n)] + [(cx, cy, z + h)])
        for k in range(n):
            self.face((b + k, b + (k + 1) % n, b + n), col)

    def obelisk(self, cx, cy, z, s, h, ang, col):
        bot = rect_pts(cx, cy, s, s, ang)
        top = rect_pts(cx, cy, s * 0.62, s * 0.62, ang)
        b = self.vid([(p[0], p[1], z) for p in bot] + [(p[0], p[1], z + h) for p in top] + [(cx, cy, z + h + s * 0.45)])
        for i in range(4):
            j = (i + 1) % 4
            self.face((b + i, b + j, b + 4 + j, b + 4 + i), col)
            self.face((b + 4 + i, b + 4 + j, b + 8), lighten(col, 1.15))

    def beam(self, p0, p1, t, col, t2=None, mat=0):
        p0 = np.asarray(p0, float)
        p1 = np.asarray(p1, float)
        d = p1 - p0
        L = np.linalg.norm(d)
        if L < 1e-6:
            return
        d = d / L
        up = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
        a = np.cross(d, up)
        a /= np.linalg.norm(a)
        b = np.cross(a, d)
        t2 = t if t2 is None else t2
        ring = [p0 + sa * a * t / 2 + sb * b * t2 / 2 for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        self.extrude(ring, tuple(p1 - p0), col, col, top=True, bottom=True, mat=mat)

    def window(self, cx, cy, ang, lx, ly, z, ww, wh, front, col=WIN):
        o = 0.004
        if front:
            y = ly - o
            loc = [(lx - ww / 2, y, z), (lx + ww / 2, y, z), (lx + ww / 2, y, z + wh), (lx - ww / 2, y, z + wh)]
        else:
            y = ly + o
            loc = [(lx + ww / 2, y, z), (lx - ww / 2, y, z), (lx - ww / 2, y, z + wh), (lx + ww / 2, y, z + wh)]
        self.poly([(*L2W(cx, cy, ang, a, b), zz) for a, b, zz in loc], col)

    def arch(self, p, u, n, z0, w, h, col=DARK, seg=6, off=0.006):
        hs = max(h - w / 2, 0.0)
        loc = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, hs)]
        for k in range(1, seg):
            a = math.pi * k / seg
            loc.append((w / 2 * math.cos(a), hs + w / 2 * math.sin(a)))
        loc.append((-w / 2, hs))
        pts = [(p[0] + u[0] * s + n[0] * off, p[1] + u[1] * s + n[1] * off, z0 + v) for s, v in loc]
        self.poly_facing(pts, (n[0], n[1], 0.0), col)

    def columns(self, p0, p1, n, z0, h, r, col=MARBLE, sides=7):
        for i in range(n):
            t = i / (n - 1) if n > 1 else 0.5
            self.cyl(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, z0, r, h, sides, col, top=False)

    def to_mesh(self, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        lt = np.fromiter((len(f) for f in self.f), dtype=np.int64, count=len(self.f))
        cols = lin(np.asarray(self.c, float)[:, :3]).astype(np.float32)
        rgba = np.ones((int(lt.sum()), 4), np.float32)
        rgba[:, :3] = np.repeat(cols, lt, axis=0)
        attr = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        attr.data.foreach_set('color', rgba.ravel())
        me.polygons.foreach_set('material_index', np.asarray(self.m, np.int32))
        me.polygons.foreach_set('use_smooth', np.asarray(self.s, bool))
        me.update()
        return me

    def to_object(self, name, coll, mats):
        if not self.f:
            return None
        me = self.to_mesh(name)
        for m in mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


def proto_fix(V, F, center):
    out = []
    for f in F:
        pts = [V[i] for i in f]
        n = newell(pts)
        cen = np.mean(pts, axis=0) - np.asarray(center)
        out.append(tuple(f) if n[0] * cen[0] + n[1] * cen[1] + n[2] * cen[2] >= 0 else tuple(reversed(f)))
    return out


def proto_round(n=7):
    V = [(0, 0, -1.0)]
    lats = (-0.55, 0.1, 0.68)
    for la in lats:
        rr = math.sqrt(1 - la * la)
        V += [(rr * math.cos(2 * math.pi * k / n), rr * math.sin(2 * math.pi * k / n), la) for k in range(n)]
    V.append((0, 0, 1.0))
    top = len(V) - 1
    F = []
    for k in range(n):
        k2 = (k + 1) % n
        F.append((0, 1 + k2, 1 + k))
        for r in range(2):
            a, b = 1 + r * n, 1 + (r + 1) * n
            F.append((a + k, a + k2, b + k2, b + k))
        F.append((1 + 2 * n + k, 1 + 2 * n + k2, top))
    return V, proto_fix(V, F, (0, 0, 0)), [0] * len(F)


def proto_cypress(n=6):
    V = [(0, 0, 0.0)]
    rings = ((0.08, 0.13), (0.35, 0.16), (0.72, 0.10))
    for z, r in rings:
        V += [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    V.append((0, 0, 1.0))
    top = len(V) - 1
    F = []
    for k in range(n):
        k2 = (k + 1) % n
        F.append((0, 1 + k2, 1 + k))
        for r in range(2):
            a, b = 1 + r * n, 1 + (r + 1) * n
            F.append((a + k, a + k2, b + k2, b + k))
        F.append((1 + 2 * n + k, 1 + 2 * n + k2, top))
    return V, proto_fix(V, F, (0, 0, 0.45)), [0] * len(F)


def proto_pine(n=7):
    V, F, C = [], [], []
    # trunk
    tr = [(-0.06, -0.06), (0.06, -0.06), (0.06, 0.06), (-0.06, 0.06)]
    V += [(x, y, 0.0) for x, y in tr] + [(x, y, 0.45) for x, y in tr]
    for i in range(4):
        j = (i + 1) % 4
        F.append((i, j, 4 + j, 4 + i))
        C.append(1)
    # flat umbrella canopy
    b = len(V)
    V.append((0, 0, 0.36))
    for z, r in ((0.46, 0.55), (0.64, 0.5)):
        V += [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    V.append((0, 0, 0.74))
    top = len(V) - 1
    for k in range(n):
        k2 = (k + 1) % n
        F.append((b, b + 1 + k2, b + 1 + k))
        F.append((b + 1 + k, b + 1 + k2, b + 1 + n + k2, b + 1 + n + k))
        F.append((b + 1 + n + k, b + 1 + n + k2, top))
        C += [0, 0, 0]
    F2 = proto_fix(V, F[:4], (0, 0, 0.3)) + proto_fix(V, F[4:], (0, 0, 0.7))
    return V, F2, C


def scatter(mb, proto, pos, scl, rot, cols, alt_col=WOOD_D, smooth=True):
    PV, PF, PC = proto
    PV = np.asarray(PV, float)
    for i in range(len(pos)):
        c, s = math.cos(rot[i]), math.sin(rot[i])
        V = PV * np.asarray(scl[i], float)
        X = V[:, 0] * c - V[:, 1] * s + pos[i][0]
        Y = V[:, 0] * s + V[:, 1] * c + pos[i][1]
        Z = V[:, 2] + pos[i][2]
        b = len(mb.v)
        mb.v.extend(zip(X.tolist(), Y.tolist(), Z.tolist()))
        for f, ci in zip(PF, PC):
            mb.f.append(tuple(b + k for k in f))
            mb.c.append(cols[i] if ci == 0 else alt_col)
            mb.s.append(smooth)
            mb.m.append(0)


# =============================================================================
# Terrain
# =============================================================================
def bilinear(G, x, y):
    n = G.shape[0]
    step = 2 * HALF / (n - 1)
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    fx = (x + HALF) / step
    fy = (y + HALF) / step
    i = np.clip(np.floor(fx).astype(int), 0, n - 2)
    j = np.clip(np.floor(fy).astype(int), 0, n - 2)
    tx = np.clip(fx - i, 0, 1)
    ty = np.clip(fy - j, 0, 1)
    return (G[j, i] * (1 - tx) + G[j, i + 1] * tx) * (1 - ty) + (G[j + 1, i] * (1 - tx) + G[j + 1, i + 1] * tx) * ty


class Terrain:
    def __init__(self, n=321):
        self.n = n
        xs = np.linspace(-HALF, HALF, n)
        X, Y = np.meshgrid(xs, xs)
        self.X, self.Y = X, Y
        land = points_in_poly(X, Y, COAST_POLY)
        dco = dist_to_polyline(X, Y, COAST_LINE)
        sd = np.where(land, dco, -dco)
        inside_wall = points_in_poly(X, Y, WALL_PATH)
        dwall = dist_to_polyline(X, Y, WALL_PATH)
        country = smoothstep(0.6, 4.0, dwall) * (~inside_wall)

        z = 0.35 + 0.045 * np.clip(sd, 0, 32)
        z = z + (fbm(X * 0.07, Y * 0.07, 4, 11) - 0.5) * 1.8 * country
        ridged = 1.0 - np.abs(2.0 * fbm(X * 0.045 + 7, Y * 0.045 + 3, 6, 23) - 1.0)
        z = z + smoothstep(35.0, 50.0, Y) ** 1.5 * (1.8 + 6.5 * ridged ** 1.4 + 1.5 * fbm(X * 0.15, Y * 0.15, 4, 41))
        wm = smoothstep(-38.0, -50.0, X) * smoothstep(-12.0, 4.0, Y)
        z = z + wm * (0.8 + 3.2 * fbm(X * 0.06 + 2, Y * 0.06 + 9, 5, 31))
        cx, cy, rx, ry = PLATEAU
        er = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
        z = np.maximum(z, 0.35 + 4.2 * smoothstep(1.4, 0.8, er))
        z = 0.32 + (z - 0.32) * smoothstep(0.0, 1.3, sd)
        # cliff roughness on the headland face
        cliff = (1 - smoothstep(0.0, 1.6, sd)) * smoothstep(1.5, 0.9, er) * (sd > 0)
        z = z + (fbm(X * 0.9, Y * 0.9, 3, 5) - 0.5) * 1.2 * cliff
        dr = dist_to_polyline(X, Y, RIVER)
        width = 0.9 + 0.3 * np.clip(z, 0, None)
        s = smoothstep(0.55, width + 0.55, dr)
        zl = -0.35 + (z + 0.35) * s
        seabed = -0.45 - 0.6 * smoothstep(0.0, 12.0, -sd)
        Z = np.where(sd > 0, zl, seabed)
        # level pad for the hippodrome
        hx, hy = hippo_local(X, Y)
        HL, HW = HIPPO[3], HIPPO[4]
        ddx = np.maximum(np.maximum(-0.3 - hx, hx - (HL + 0.5)), 0.0)
        ddy = np.maximum(np.abs(hy) - (HW / 2 + 0.9), 0.0)
        pad = (1.0 - smoothstep(0.0, 1.5, np.hypot(ddx, ddy))) * smoothstep(0.05, 0.7, sd)
        Z = Z * (1 - pad) + HIPPO_Z * pad
        self.Z = Z
        self.sd = sd
        self.dr = dr
        self.inside_wall = inside_wall
        self.er = er
        out = ~inside_wall
        self.farm = smoothstep(1.5, 3.5, sd) * country * (1 - smoothstep(2.6, 4.2, Z)) * smoothstep(1.4, 2.6, dr)
        self.forest = smoothstep(3.0, 4.8, Z) * out * smoothstep(1.0, 2.0, dr)
        self.city = (inside_wall & (sd > 0)).astype(float) * smoothstep(0.85, 0.97, er)
        self.sand = (sd > 0) * (1 - smoothstep(0.6, 1.8, sd)) * out * (1 - smoothstep(1.0, 2.0, Z))

    def h(self, x, y):
        return bilinear(self.Z, x, y)

    def hs(self, x, y):
        return float(self.h(x, y))

    def m(self, G, x, y):
        return bilinear(G, x, y)


def fp_ground(T, cx, cy, w, d, ang):
    pts = rect_pts(cx, cy, w, d, ang) + [(cx, cy)]
    zs = T.h([p[0] for p in pts], [p[1] for p in pts])
    return float(zs.min()), float(zs.max())


# =============================================================================
# Materials & world
# =============================================================================
def _new_mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    return m, nt


def _sock(socks, key):
    for s in socks:
        if s.identifier == key:
            return s
    return socks[key]


def _set(nt, sock, val):
    if isinstance(val, bpy.types.NodeSocket):
        nt.links.new(val, sock)
    else:
        sock.default_value = val


def _node(nt, typ, loc=(0, 0), **props):
    n = nt.nodes.new(typ)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _mix(nt, fac, a, b, blend='MIX', loc=(0, 0)):
    n = _node(nt, 'ShaderNodeMix', loc)
    n.data_type = 'RGBA'
    n.blend_type = blend
    _set(nt, _sock(n.inputs, 'Factor_Float'), fac)
    _set(nt, _sock(n.inputs, 'A_Color'), a)
    _set(nt, _sock(n.inputs, 'B_Color'), b)
    return _sock(n.outputs, 'Result_Color')


def _math(nt, op, a, b=0.0, clamp=False, loc=(0, 0)):
    n = _node(nt, 'ShaderNodeMath', loc, operation=op)
    n.use_clamp = clamp
    _set(nt, n.inputs[0], a)
    _set(nt, n.inputs[1], b)
    return n.outputs[0]


def _maprange(nt, v, a, b, c, d, loc=(0, 0)):
    n = _node(nt, 'ShaderNodeMapRange', loc)
    n.clamp = True
    _set(nt, n.inputs['Value'], v)
    n.inputs['From Min'].default_value = a
    n.inputs['From Max'].default_value = b
    n.inputs['To Min'].default_value = c
    n.inputs['To Max'].default_value = d
    return n.outputs['Result']


def _ramp(nt, fac, stops, interp='LINEAR', loc=(0, 0)):
    n = _node(nt, 'ShaderNodeValToRGB', loc)
    n.color_ramp.interpolation = interp
    els = n.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for el, (p, c) in zip(els, stops):
        el.position = p
        el.color = lin4(c)
    _set(nt, n.inputs['Fac'], fac)
    return n.outputs['Color']


def _principled(nt, loc=(300, 0)):
    out = _node(nt, 'ShaderNodeOutputMaterial', (loc[0] + 300, loc[1]))
    bs = _node(nt, 'ShaderNodeBsdfPrincipled', loc)
    nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    return bs, out


HAZE_COLOR = (0.80, 0.62, 0.66)


def haze_group():
    """Aerial-perspective node group: blends a colour toward HAZE_COLOR with view distance.
    Its 'HazeAmount' value node is set per camera by render() (0 for the top-down map)."""
    ng = bpy.data.node_groups.get("CAP_Haze")
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new("CAP_Haze", "ShaderNodeTree")
    ng.interface.new_socket(name="Color", in_out='INPUT', socket_type='NodeSocketColor')
    ng.interface.new_socket(name="Color", in_out='OUTPUT', socket_type='NodeSocketColor')
    gi = _node(ng, 'NodeGroupInput', (-600, 0))
    go = _node(ng, 'NodeGroupOutput', (400, 0))
    cam = _node(ng, 'ShaderNodeCameraData', (-600, -200))
    amt = _node(ng, 'ShaderNodeValue', (-400, -400))
    amt.name = "HazeAmount"
    amt.label = "HazeAmount"
    amt.outputs[0].default_value = 1.0
    f = _maprange(ng, cam.outputs['View Distance'], 75.0, 175.0, 0.0, 0.55, (-400, -200))
    f = _math(ng, 'MULTIPLY', f, amt.outputs[0], loc=(-200, -250))
    col = _mix(ng, f, gi.outputs[0], lin4(HAZE_COLOR), 'MIX', (100, 0))
    ng.links.new(col, go.inputs[0])
    return ng


def _haze(nt, col, loc=(100, 0)):
    g = _node(nt, 'ShaderNodeGroup', loc)
    g.node_tree = bpy.data.node_groups["CAP_Haze"]
    nt.links.new(col, g.inputs[0])
    return g.outputs[0]


def mat_painted():
    m, nt = _new_mat("CAP_Painted")
    bs, _ = _principled(nt)
    tc = _node(nt, 'ShaderNodeTexCoord', (-900, 0))
    at = _node(nt, 'ShaderNodeAttribute', (-600, 200), attribute_name='Col', attribute_type='GEOMETRY')
    nz = _node(nt, 'ShaderNodeTexNoise', (-700, -150))
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    nz.inputs['Scale'].default_value = 3.0
    nz.inputs['Detail'].default_value = 6.0
    g = _maprange(nt, nz.outputs['Fac'], 0.3, 0.7, 0.9, 1.08, (-450, -150))
    col = _mix(nt, 1.0, at.outputs['Color'], g, 'MULTIPLY', (-200, 100))
    nt.links.new(_haze(nt, col), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.78
    _sock(bs.inputs, 'Specular IOR Level').default_value = 0.35
    return m


def mat_fire():
    m, nt = _new_mat("CAP_Fire")
    bs, _ = _principled(nt)
    bs.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    _sock(bs.inputs, 'Emission Color').default_value = (1.0, 0.42, 0.08, 1.0)
    _sock(bs.inputs, 'Emission Strength').default_value = 30.0
    return m


def mat_water():
    m, nt = _new_mat("CAP_Water")
    bs, _ = _principled(nt)
    tc = _node(nt, 'ShaderNodeTexCoord', (-1000, -300))
    at = _node(nt, 'ShaderNodeAttribute', (-700, 200), attribute_name='depth', attribute_type='GEOMETRY')
    col = _ramp(nt, at.outputs['Fac'], [(0.0, (0.24, 0.64, 0.62)), (0.15, (0.12, 0.44, 0.58)),
                                        (0.5, (0.07, 0.27, 0.52)), (1.0, (0.05, 0.18, 0.42))], loc=(-400, 200))
    nt.links.new(_haze(nt, col, (-150, 200)), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.14
    bs.inputs['IOR'].default_value = 1.33
    n1 = _node(nt, 'ShaderNodeTexNoise', (-700, -300))
    nt.links.new(tc.outputs['Object'], n1.inputs['Vector'])
    n1.inputs['Scale'].default_value = 2.2
    n1.inputs['Detail'].default_value = 8.0
    n1.inputs['Roughness'].default_value = 0.62
    wv = _node(nt, 'ShaderNodeTexWave', (-700, -550))
    nt.links.new(tc.outputs['Object'], wv.inputs['Vector'])
    wv.inputs['Scale'].default_value = 0.6
    wv.inputs['Distortion'].default_value = 8.0
    wv.inputs['Detail'].default_value = 5.0
    h = _math(nt, 'ADD', n1.outputs['Fac'], _math(nt, 'MULTIPLY', wv.outputs['Fac'], 0.18, loc=(-450, -550)), loc=(-300, -400))
    bump = _node(nt, 'ShaderNodeBump', (-100, -350))
    bump.inputs['Strength'].default_value = 0.3
    bump.inputs['Distance'].default_value = 0.05
    nt.links.new(h, bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    return m


def mat_terrain():
    m, nt = _new_mat("CAP_Terrain")
    bs, _ = _principled(nt, (900, 0))
    tc = _node(nt, 'ShaderNodeTexCoord', (-1800, 0))
    obj = tc.outputs['Object']
    zone = _node(nt, 'ShaderNodeAttribute', (-1500, 500), attribute_name='zone', attribute_type='GEOMETRY')
    sep = _node(nt, 'ShaderNodeSeparateColor', (-1300, 500))
    nt.links.new(zone.outputs['Color'], sep.inputs['Color'])
    farm, forest, city, sand = sep.outputs['Red'], sep.outputs['Green'], sep.outputs['Blue'], zone.outputs['Alpha']

    # warped coordinates -> rectangular-ish field patchwork
    wn = _node(nt, 'ShaderNodeTexNoise', (-1500, 0))
    nt.links.new(obj, wn.inputs['Vector'])
    wn.inputs['Scale'].default_value = 0.05
    vs = _node(nt, 'ShaderNodeVectorMath', (-1300, 0), operation='SUBTRACT')
    nt.links.new(wn.outputs['Color'], vs.inputs[0])
    vs.inputs[1].default_value = (0.5, 0.5, 0.5)
    vsc = _node(nt, 'ShaderNodeVectorMath', (-1150, 0), operation='SCALE')
    nt.links.new(vs.outputs['Vector'], vsc.inputs[0])
    _sock(vsc.inputs, 'Scale').default_value = 7.0
    va = _node(nt, 'ShaderNodeVectorMath', (-1000, 0), operation='ADD')
    nt.links.new(vsc.outputs['Vector'], va.inputs[0])
    nt.links.new(obj, va.inputs[1])
    coords = va.outputs['Vector']
    v1 = _node(nt, 'ShaderNodeTexVoronoi', (-800, 100), feature='F1', distance='CHEBYCHEV')
    v2 = _node(nt, 'ShaderNodeTexVoronoi', (-800, -150), feature='F2', distance='CHEBYCHEV')
    for v in (v1, v2):
        nt.links.new(coords, v.inputs['Vector'])
        v.inputs['Scale'].default_value = 0.3
    sc = _node(nt, 'ShaderNodeSeparateColor', (-600, 100))
    nt.links.new(v1.outputs['Color'], sc.inputs['Color'])
    fields = _ramp(nt, sc.outputs['Red'], [
        (0.0, (0.80, 0.68, 0.33)), (0.14, (0.47, 0.54, 0.22)), (0.27, (0.66, 0.52, 0.29)),
        (0.40, (0.37, 0.45, 0.19)), (0.52, (0.86, 0.74, 0.40)), (0.63, (0.52, 0.38, 0.23)),
        (0.75, (0.60, 0.61, 0.28)), (0.87, (0.42, 0.50, 0.25))], 'CONSTANT', (-400, 100))
    edge = _maprange(nt, _math(nt, 'SUBTRACT', v2.outputs['Distance'], v1.outputs['Distance'], loc=(-600, -150)),
                     0.0, 0.05, 0.62, 1.0, (-400, -150))
    furrow = _node(nt, 'ShaderNodeTexWave', (-600, -350))
    nt.links.new(coords, furrow.inputs['Vector'])
    furrow.inputs['Scale'].default_value = 3.0
    fr = _maprange(nt, furrow.outputs['Fac'], 0.0, 1.0, 0.92, 1.04, (-400, -350))
    field = _mix(nt, 1.0, fields, edge, 'MULTIPLY', (-200, 100))
    field = _mix(nt, 1.0, field, fr, 'MULTIPLY', (-50, 100))

    dn = _node(nt, 'ShaderNodeTexNoise', (-800, 500))
    nt.links.new(obj, dn.inputs['Vector'])
    dn.inputs['Scale'].default_value = 0.6
    dn.inputs['Detail'].default_value = 8.0
    meadow = _ramp(nt, dn.outputs['Fac'], [(0.3, (0.36, 0.43, 0.18)), (0.7, (0.52, 0.53, 0.25))], loc=(-500, 500))
    forest_c = _ramp(nt, dn.outputs['Fac'], [(0.3, (0.15, 0.22, 0.10)), (0.7, (0.30, 0.34, 0.17))], loc=(-500, 700))
    rock_c = _ramp(nt, dn.outputs['Fac'], [(0.25, (0.50, 0.42, 0.33)), (0.75, (0.76, 0.64, 0.48))], loc=(-500, 900))
    city_c = _ramp(nt, dn.outputs['Fac'], [(0.3, (0.55, 0.48, 0.39)), (0.7, (0.66, 0.59, 0.48))], loc=(-500, 300))

    col = _mix(nt, farm, meadow, field, loc=(100, 300))
    col = _mix(nt, forest, col, forest_c, loc=(250, 300))
    col = _mix(nt, city, col, city_c, loc=(400, 300))
    col = _mix(nt, sand, col, (*lin4((0.84, 0.75, 0.56))[:3], 1.0), loc=(550, 300))
    geo = _node(nt, 'ShaderNodeNewGeometry', (-300, 900))
    sxyz = _node(nt, 'ShaderNodeSeparateXYZ', (-150, 900))
    nt.links.new(geo.outputs['Normal'], sxyz.inputs['Vector'])
    rockf = _maprange(nt, sxyz.outputs['Z'], 0.50, 0.70, 1.0, 0.0, (0, 900))
    col = _mix(nt, rockf, col, rock_c, loc=(700, 300))
    pz = _node(nt, 'ShaderNodeSeparateXYZ', (-150, 1100))
    nt.links.new(geo.outputs['Position'], pz.inputs['Vector'])
    under = _maprange(nt, pz.outputs['Z'], -0.05, 0.08, 1.0, 0.0, (0, 1100))
    col = _mix(nt, under, col, (*lin4((0.50, 0.46, 0.34))[:3], 1.0), loc=(800, 300))
    peak_c = _ramp(nt, dn.outputs['Fac'], [(0.3, (0.52, 0.47, 0.45)), (0.7, (0.70, 0.64, 0.60))], loc=(-500, 1100))
    peak = _maprange(nt, _math(nt, 'ADD', pz.outputs['Z'], _math(nt, 'MULTIPLY', dn.outputs['Fac'], 3.0, loc=(0, 1300)), loc=(150, 1250)),
                     8.8, 11.5, 0.0, 0.8, (300, 1250))
    col = _mix(nt, peak, col, peak_c, loc=(900, 300))
    nt.links.new(_haze(nt, col, (1000, 300)), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.92
    _sock(bs.inputs, 'Specular IOR Level').default_value = 0.2
    return m


def mat_steam():
    m, nt = _new_mat("CAP_Steam")
    out = _node(nt, 'ShaderNodeOutputMaterial', (400, 0))
    vol = _node(nt, 'ShaderNodeVolumePrincipled', (100, 0))
    nt.links.new(vol.outputs['Volume'], out.inputs['Volume'])
    vol.inputs['Color'].default_value = (0.92, 0.88, 0.85, 1.0)
    tc = _node(nt, 'ShaderNodeTexCoord', (-800, 0))
    ln = _node(nt, 'ShaderNodeVectorMath', (-600, -150), operation='LENGTH')
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    fall = _maprange(nt, ln.outputs['Value'], 0.3, 1.0, 1.0, 0.0, (-400, -150))
    nz = _node(nt, 'ShaderNodeTexNoise', (-600, 150))
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    nz.inputs['Scale'].default_value = 2.5
    nz.inputs['Detail'].default_value = 4.0
    d = _math(nt, 'MULTIPLY', _maprange(nt, nz.outputs['Fac'], 0.4, 0.7, 0.0, 1.0, (-400, 150)), fall, loc=(-200, 0))
    d = _math(nt, 'MULTIPLY', d, 1.6, loc=(-50, 0))
    nt.links.new(d, vol.inputs['Density'])
    return m


def setup_world(sun_dir):
    w = bpy.data.worlds.get("CAP_World") or bpy.data.worlds.new("CAP_World")
    try:
        w.use_nodes = True
    except Exception:
        pass
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = _node(nt, 'ShaderNodeOutputWorld', (900, 0))
    bg = _node(nt, 'ShaderNodeBackground', (700, 0))
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    tc = _node(nt, 'ShaderNodeTexCoord', (-900, 0))
    nrm = _node(nt, 'ShaderNodeVectorMath', (-700, 0), operation='NORMALIZE')
    nt.links.new(tc.outputs['Generated'], nrm.inputs[0])
    sep = _node(nt, 'ShaderNodeSeparateXYZ', (-500, 100))
    nt.links.new(nrm.outputs['Vector'], sep.inputs['Vector'])
    sky = _ramp(nt, sep.outputs['Z'], [(0.0, (0.98, 0.62, 0.36)), (0.05, (0.96, 0.58, 0.50)),
                                       (0.14, (0.70, 0.48, 0.62)), (0.3, (0.36, 0.36, 0.62)),
                                       (0.6, (0.17, 0.20, 0.45)), (1.0, (0.09, 0.11, 0.30))], loc=(-300, 150))
    dot = _node(nt, 'ShaderNodeVectorMath', (-500, -150), operation='DOT_PRODUCT')
    nt.links.new(nrm.outputs['Vector'], dot.inputs[0])
    dot.inputs[1].default_value = tuple(sun_dir)
    glow = _math(nt, 'POWER', _math(nt, 'MAXIMUM', dot.outputs['Value'], 0.0, loc=(-350, -150)), 24.0, loc=(-200, -150))
    light_col = _mix(nt, _math(nt, 'MINIMUM', glow, 1.0, loc=(0, -150)), sky, (1.0, 0.55, 0.2, 1.0), 'ADD', (200, 100))

    # painted sunset backdrop - only what the camera sees directly (screen-space gradient + clouds)
    win = _node(nt, 'ShaderNodeSeparateXYZ', (-500, 500))
    nt.links.new(tc.outputs['Window'], win.inputs['Vector'])
    back = _ramp(nt, win.outputs['Y'], [(0.0, (0.86, 0.52, 0.38)), (0.42, (0.99, 0.70, 0.40)),
                                        (0.58, (0.96, 0.56, 0.46)), (0.74, (0.66, 0.46, 0.64)),
                                        (0.88, (0.36, 0.36, 0.64)), (1.0, (0.20, 0.23, 0.52))], loc=(-300, 600))
    mp = _node(nt, 'ShaderNodeMapping', (-500, 300))
    nt.links.new(tc.outputs['Window'], mp.inputs['Vector'])
    mp.inputs['Scale'].default_value = (1.0, 4.5, 1.0)
    cn = _node(nt, 'ShaderNodeTexNoise', (-300, 300))
    nt.links.new(mp.outputs['Vector'], cn.inputs['Vector'])
    cn.inputs['Scale'].default_value = 2.2
    cn.inputs['Detail'].default_value = 7.0
    cn.inputs['Roughness'].default_value = 0.62
    cloud = _maprange(nt, cn.outputs['Fac'], 0.5, 0.66, 0.0, 1.0, (-100, 300))
    cmask = _maprange(nt, win.outputs['Y'], 0.55, 0.75, 0.0, 0.85, (-100, 450))
    cloud = _math(nt, 'MULTIPLY', cloud, cmask, loc=(50, 350))
    ccol = _ramp(nt, win.outputs['Y'], [(0.55, (1.0, 0.62, 0.38)), (0.8, (0.95, 0.52, 0.55)), (1.0, (0.62, 0.42, 0.62))], loc=(-100, 750))
    back = _mix(nt, cloud, back, ccol, 'MIX', (200, 600))
    # sun glow on the right horizon
    sxy = _node(nt, 'ShaderNodeVectorMath', (-300, 900), operation='DISTANCE')
    nt.links.new(tc.outputs['Window'], sxy.inputs[0])
    sxy.inputs[1].default_value = (0.97, 0.56, 0.0)
    sg = _math(nt, 'POWER', _maprange(nt, sxy.outputs['Value'], 0.0, 0.45, 1.0, 0.0, (-100, 900)), 2.5, loc=(50, 900))
    back = _mix(nt, sg, back, (1.0, 0.80, 0.45, 1.0), 'ADD', (350, 700))
    lp = _node(nt, 'ShaderNodeLightPath', (200, 900))
    final = _mix(nt, lp.outputs['Is Camera Ray'], light_col, back, 'MIX', (500, 300))
    nt.links.new(final, bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    return w


# =============================================================================
# Scene management
# =============================================================================
def clear_previous():
    root = bpy.data.collections.get(ROOT_NAME)
    if root:
        colls = [root] + list(root.children_recursive)
        for c in colls:
            for o in list(c.objects):
                bpy.data.objects.remove(o, do_unlink=True)
        for c in reversed(colls[1:]):
            bpy.data.collections.remove(c)
        bpy.data.collections.remove(root)
    for coll in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras):
        for d in list(coll):
            if d.users == 0 and d.name.startswith("CAP_"):
                coll.remove(d)


def remove_factory_defaults():
    removed = []
    for nm in ("Cube", "Light", "Camera"):
        o = bpy.data.objects.get(nm)
        if o is not None and o.users_collection and o.users_collection[0].name in ("Collection", "Scene Collection"):
            removed.append(nm)
            bpy.data.objects.remove(o, do_unlink=True)
    c = bpy.data.collections.get("Collection")
    if c is not None and not c.all_objects and not c.children:
        bpy.data.collections.remove(c)
    return removed


def new_coll(name, parent):
    c = bpy.data.collections.new(name)
    parent.children.link(c)
    return c


# =============================================================================
# Stage: terrain, sea, base
# =============================================================================
def build_terrain(T, coll, mats):
    n = T.n
    verts = np.column_stack([T.X.ravel(), T.Y.ravel(), T.Z.ravel()])
    idx = np.arange(n * n).reshape(n, n)
    faces = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()])
    me = bpy.data.meshes.new("CAP_Terrain")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.update()
    zone = np.column_stack([T.farm.ravel(), T.forest.ravel(), T.city.ravel(), T.sand.ravel()]).astype(np.float32)
    at = me.color_attributes.new('zone', 'FLOAT_COLOR', 'POINT')
    at.data.foreach_set('color', zone.ravel())
    me.shade_smooth()
    me.materials.append(mats['terrain'])
    ob = bpy.data.objects.new("CAP_Terrain", me)
    coll.objects.link(ob)

    # sea
    m = 101
    xs = np.linspace(-HALF, HALF, m)
    SX, SY = np.meshgrid(xs, xs)
    depth = np.clip(-T.h(SX, SY), 0.0, 1.6) / 1.6
    sv = np.column_stack([SX.ravel(), SY.ravel(), np.zeros(m * m)])
    si = np.arange(m * m).reshape(m, m)
    sf = np.column_stack([si[:-1, :-1].ravel(), si[:-1, 1:].ravel(), si[1:, 1:].ravel(), si[1:, :-1].ravel()])
    sm = bpy.data.meshes.new("CAP_Sea")
    sm.from_pydata(sv.tolist(), [], sf.tolist())
    sm.update()
    da = sm.attributes.new('depth', 'FLOAT', 'POINT')
    da.data.foreach_set('value', depth.ravel().astype(np.float32))
    sm.shade_smooth()
    sm.materials.append(mats['water'])
    so = bpy.data.objects.new("CAP_Sea", sm)
    coll.objects.link(so)

    # display base (diorama plinth)
    mb = MB()
    Z = np.maximum(T.Z, 0.0)
    xs = np.linspace(-HALF, HALF, n)
    BASE_C = (0.20, 0.13, 0.08)
    zb = -3.0
    edges = [
        ([(x, -HALF) for x in xs], Z[0, :], (0, -1, 0)),
        ([(HALF, y) for y in xs], Z[:, -1], (1, 0, 0)),
        ([(x, HALF) for x in xs], Z[-1, :], (0, 1, 0)),
        ([(-HALF, y) for y in xs], Z[:, 0], (-1, 0, 0)),
    ]
    for pts, zt, want in edges:
        for i in range(len(pts) - 1):
            q = [(pts[i][0], pts[i][1], zb), (pts[i + 1][0], pts[i + 1][1], zb),
                 (pts[i + 1][0], pts[i + 1][1], zt[i + 1]), (pts[i][0], pts[i][1], zt[i])]
            mb.poly_facing(q, want, BASE_C)
    mb.poly_facing([(-HALF, -HALF, zb), (HALF, -HALF, zb), (HALF, HALF, zb), (-HALF, HALF, zb)], (0, 0, -1), BASE_C)
    # thin brass rim
    for pts, zt, want in edges:
        pass
    mb.to_object("CAP_Base", coll, [mats['painted']])
    return ob


# =============================================================================
# Stage: walls, gates, moles, lighthouses, quays, piers
# =============================================================================
def crenellate(mb, a, b, z, side_n, inset, col=STONE, size=0.12, step=0.26):
    d = np.asarray(b, float) - np.asarray(a, float)
    L = float(np.linalg.norm(d))
    ang = math.atan2(d[1], d[0])
    nm = max(1, int(L / step))
    for k in range(nm):
        t = (k + 0.5) / nm
        p = np.asarray(a) + d * t + np.asarray(side_n) * inset
        mb.box(p[0], p[1], z, size, size * 0.9, size, ang, col)


def tower(mb, T, x, y, ang, size, top_z, rng, roof_chance=0.25):
    zg = T.hs(x, y)
    mb.box(x, y, zg - 0.6, size, size, top_z - (zg - 0.6), ang, STONE_D, STONE_TOP)
    if rng.random() < roof_chance:
        mb.hip_roof(x, y, top_z, size, size, ang, size * 0.55, jit(rng, ROOF), ov=0.06)
    else:
        corners = rect_pts(x, y, size, size, ang)
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            cen = np.array([x, y])
            mid = (np.asarray(a) + np.asarray(b)) / 2
            nrm = (cen - mid) / np.linalg.norm(cen - mid)
            crenellate(mb, a, b, top_z, nrm, 0.06, STONE_D, 0.13, 0.3)
    # arrow slits
    for lx, ly, front in ((0, -size / 2, True), (0, size / 2, False)):
        mb.window(x, y, ang, lx, ly, top_z - 0.55, 0.05, 0.16, front, DARK)


def build_walls(T, coll, mats, fire_mb, lights):
    rng = np.random.default_rng(31)
    mb = MB()
    P = resample(WALL_PATH, 0.9)
    N = polyline_normals(P)
    mid = len(P) // 2
    test = P[mid] + N[mid] * 1.5
    if points_in_poly(np.array([test[0]]), np.array([test[1]]), WALL_PATH)[0]:
        N = -N                                   # make N point outward
    zs = T.h(P[:, 0], P[:, 1])
    WALL_T, WALL_H = 0.45, 1.15
    gate_pts = [np.array(g) for g in GATES]

    def near_gate(p, r):
        return any(np.linalg.norm(p - g) < r for g in gate_pts)

    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        m = (a + b) / 2
        d = b - a
        L = float(np.linalg.norm(d))
        ang = math.atan2(d[1], d[0])
        zg = min(zs[i], zs[i + 1])
        zt = max(zs[i], zs[i + 1]) + WALL_H
        mb.box(m[0], m[1], zg - 0.6, L + 0.06, WALL_T, zt - (zg - 0.6), ang, STONE, STONE_TOP)
        if not near_gate(m, 1.0):
            n = (N[i] + N[i + 1]) / 2
            crenellate(mb, a, b, zt, n, WALL_T / 2 - 0.065)
    # towers
    s = arclen(P)
    for k, sv in enumerate(np.arange(0.0, s[-1] + 0.01, 4.6)):
        p = at_arc(P, s, sv)
        if near_gate(p, 2.2):
            continue
        j = min(int(np.searchsorted(s, sv)), len(P) - 1)
        d = P[min(j + 1, len(P) - 1)] - P[max(j - 1, 0)]
        ang = math.atan2(d[1], d[0])
        zt = T.hs(p[0], p[1]) + WALL_H + 0.8
        tower(mb, T, p[0], p[1], ang, 0.95, zt, rng)
    tower(mb, T, P[-1][0], P[-1][1], 0.3, 1.1, T.hs(*P[-1]) + WALL_H + 0.9, rng, 0.0)
    # gates
    for g in gate_pts:
        dist = np.linalg.norm(P - g, axis=1)
        j = int(np.argmin(dist))
        d = P[min(j + 1, len(P) - 1)] - P[max(j - 1, 0)]
        u = d / np.linalg.norm(d)
        ang = math.atan2(u[1], u[0])
        n = N[j]
        zg = T.hs(*g)
        for sgn in (-1, 1):
            p = g + u * sgn * 1.15
            tower(mb, T, p[0], p[1], ang, 1.3, zg + WALL_H + 1.4, rng, 0.0)
        mb.box(g[0], g[1], zg - 0.5, 1.2, 1.0, WALL_H + 0.65 + 0.5, ang, STONE, STONE_TOP)
        crenellate(mb, g - u * 0.6, g + u * 0.6, zg + WALL_H + 0.65, n, 0.42, STONE, 0.12, 0.28)
        for sgn in (-1, 1):
            mb.arch(g + n * sgn * 0.5, u, n * sgn, zg, 0.55, 0.85)
    mb.to_object("CAP_CityWalls", coll, [mats['painted']])

    # moles, riprap, lighthouses
    mb2 = MB()
    for path in (W_MOLE, E_MOLE):
        Q = resample(path, 0.8)
        NQ = polyline_normals(Q)
        for i in range(len(Q) - 1):
            a, b = Q[i], Q[i + 1]
            m = (a + b) / 2
            d = b - a
            L = float(np.linalg.norm(d))
            ang = math.atan2(d[1], d[0])
            n = (NQ[i] + NQ[i + 1]) / 2
            if np.dot(n, m - np.array(HARBOR_CENTER)) < 0:
                n = -n                            # n -> open sea
            mb2.box(m[0], m[1], -0.9, L + 0.05, 1.3, 1.4, ang, STONE_D, STONE_TOP)
            pp = m + n * 0.5
            mb2.box(pp[0], pp[1], 0.5, L + 0.05, 0.3, 0.45, ang, STONE, STONE_TOP)
            crenellate(mb2, a + n * 0.5, b + n * 0.5, 0.95, n, 0.0, STONE, 0.11, 0.3)
            for _ in range(5):
                t = rng.uniform(0, 1)
                q = a + d * t + n * rng.uniform(0.7, 1.15)
                rs = rng.uniform(0.15, 0.32)
                mb2.box(q[0], q[1], -0.4, rs, rs * rng.uniform(0.7, 1.2), rng.uniform(0.35, 0.6),
                        rng.uniform(0, 3.14), jit(rng, ROCK, 0.12))
        lighthouse(mb2, fire_mb, Q[-1][0], Q[-1][1], lights, rng)
    mb2.to_object("CAP_Moles_Lighthouses", coll, [mats['painted']])

    # quays
    mb3 = MB()
    H = resample(HARBOR, 0.6)
    NH = polyline_normals(H)                     # left = inland
    def at_water_stair(p):                       # the hippodrome's stair replaces the quay here
        hx, hy = hippo_local(p[0], p[1])
        return -3.0 < hx < 1.5 and abs(hy) < 1.9

    for i in range(len(H) - 1):
        a, b = H[i], H[i + 1]
        n = (NH[i] + NH[i + 1]) / 2
        m = (a + b) / 2 - n * 0.1
        if at_water_stair(m):
            continue
        d = b - a
        mb3.box(m[0], m[1], -0.8, float(np.linalg.norm(d)) + 0.05, 0.3, 1.21, math.atan2(d[1], d[0]), STONE_D, STONE_TOP)
    for k in range(0, len(H), 3):               # bollards
        p = H[k] + NH[k] * 0.12
        if not at_water_stair(p):
            mb3.cyl(p[0], p[1], 0.38, 0.035, 0.08, 6, WOOD_D)
    # piers
    for a, b in PIERS:
        a = np.array(a)
        b = np.array(b)
        d = b - a
        L = float(np.linalg.norm(d))
        u = d / L
        ang = math.atan2(d[1], d[0])
        m = (a + b) / 2
        mb3.box(m[0], m[1], 0.27, L, 0.55, 0.07, ang, WOOD, lighten(WOOD, 1.1))
        n = np.array([-u[1], u[0]])
        for t in np.arange(0.4, L, 0.8):
            for sgn in (-1, 1):
                p = a + u * t + n * sgn * 0.24
                mb3.cyl(p[0], p[1], -0.7, 0.035, 1.0, 6, WOOD_D)
    mb3.to_object("CAP_Quays_Piers", coll, [mats['painted']])


def lighthouse(mb, fmb, x, y, lights, rng):
    mb.box(x, y, -0.9, 1.8, 1.8, 2.1, 0.3, STONE_D, STONE_TOP)          # base to z=1.2
    for i, (a, b) in enumerate(zip(rect_pts(x, y, 1.8, 1.8, 0.3), rect_pts(x, y, 1.8, 1.8, 0.3)[1:] + rect_pts(x, y, 1.8, 1.8, 0.3)[:1])):
        cen = np.array([x, y])
        mid = (np.asarray(a) + np.asarray(b)) / 2
        crenellate(mb, a, b, 1.2, (cen - mid) / np.linalg.norm(cen - mid), 0.07, STONE_D, 0.13, 0.3)
    mb.box(x, y, 1.2, 1.15, 1.15, 1.2, 0.3, STONE, STONE_TOP)           # tier 2 to 2.4
    for lx, ly, fr in ((0, -0.575, True), (0, 0.575, False)):
        for zz in (1.55, 1.95):
            mb.window(x, y, 0.3, lx, ly, zz, 0.08, 0.16, fr, DARK)
    mb.cyl(x, y, 2.4, 0.43, 1.0, 12, MARBLE, MARBLE)                    # tower to 3.4
    mb.cyl(x, y, 3.4, 0.56, 0.08, 14, STONE_D, STONE_TOP)               # gallery
    mb.columns((x + 0.25, y), (x + 0.25, y), 1, 3.48, 0.38, 0.04, MARBLE)
    for k in range(6):
        a = 2 * math.pi * k / 6
        mb.cyl(x + 0.27 * math.cos(a), y + 0.27 * math.sin(a), 3.48, 0.035, 0.38, 5, MARBLE, top=False)
    mb.cyl(x, y, 3.86, 0.36, 0.05, 12, STONE_D, STONE_TOP)
    mb.dome(x, y, 3.91, 0.3, 0.6, LEAD, 12, 4)
    # fire bowl + flames (emissive object)
    fmb.cyl(x, y, 3.48, 0.2, 0.1, 10, (1, 0.6, 0.2))
    for k in range(5):
        a = 2 * math.pi * k / 5
        r = 0.08
        fx, fy = x + r * math.cos(a), y + r * math.sin(a)
        h = rng.uniform(0.2, 0.32)
        b = fmb.vid([(fx - 0.06, fy - 0.06, 3.56), (fx + 0.06, fy - 0.06, 3.56), (fx + 0.06, fy + 0.06, 3.56),
                     (fx - 0.06, fy + 0.06, 3.56), (fx, fy, 3.56 + h)])
        for i in range(4):
            fmb.face((b + i, b + (i + 1) % 4, b + 4), (1, 0.6, 0.2))
    lights.append((x, y, 3.75))


# =============================================================================
# Stage: city (landmarks, harbour front, houses, city trees)
# =============================================================================
class Occ:
    def __init__(self, res=0.2):
        self.res = res
        self.n = int(round(2 * HALF / res)) + 1
        c = np.linspace(-HALF, HALF, self.n)
        self.X, self.Y = np.meshgrid(c, c)
        self.B = np.zeros((self.n, self.n), bool)

    def rect(self, cx, cy, w, d, ang, margin=0.0):
        c, s = math.cos(ang), math.sin(ang)
        dx = self.X - cx
        dy = self.Y - cy
        lx = dx * c + dy * s
        ly = -dx * s + dy * c
        self.B |= (np.abs(lx) <= w / 2 + margin) & (np.abs(ly) <= d / 2 + margin)

    def circle(self, cx, cy, r):
        self.B |= (self.X - cx) ** 2 + (self.Y - cy) ** 2 <= r * r

    def ellipse(self, cx, cy, rx, ry, ang=0.0):
        c, s = math.cos(ang), math.sin(ang)
        dx = self.X - cx
        dy = self.Y - cy
        lx = dx * c + dy * s
        ly = -dx * s + dy * c
        self.B |= (lx / rx) ** 2 + (ly / ry) ** 2 <= 1.0

    def line(self, pts, hw):
        self.B |= dist_to_polyline(self.X, self.Y, pts) <= hw

    def free(self, x, y):
        i = int(round((x + HALF) / self.res))
        j = int(round((y + HALF) / self.res))
        if i < 0 or j < 0 or i >= self.n or j >= self.n:
            return False
        return not self.B[j, i]


def temple(mb, T, cx, cy, face_deg, w, l, hc, ncol=6, occ=None, roof=ROOF):
    ang = math.radians(face_deg) + math.pi / 2
    zmin, zmax = fp_ground(T, cx, cy, w + 0.6, l + 1.0, ang)
    zp = zmax + 0.3
    mb.box(cx, cy, zmin - 0.4, w + 0.25, l + 0.25, zp - (zmin - 0.4), ang, MARBLE_D, MARBLE)
    for k in range(3):
        p = L2W(cx, cy, ang, 0, -(l / 2 + 0.125 + 0.12 * k + 0.06))
        mb.box(p[0], p[1], zmin - 0.3, w * 0.75, 0.13, (zp - zmin + 0.3) * (3 - k) / 4, ang, MARBLE, MARBLE)
    r = 0.028 * hc / 0.5 if hc < 0.9 else 0.06
    inset = 0.15
    xs = np.linspace(-w / 2 + inset, w / 2 - inset, ncol)
    sp = xs[1] - xs[0]
    ns = max(3, int(round((l - 2 * inset) / sp)) + 1)
    ys = np.linspace(-l / 2 + inset, l / 2 - inset, ns)
    pos = set()
    for x in xs:
        pos.add((round(float(x), 4), round(float(ys[0]), 4)))
        pos.add((round(float(x), 4), round(float(ys[-1]), 4)))
    for y in ys:
        pos.add((round(float(xs[0]), 4), round(float(y), 4)))
        pos.add((round(float(xs[-1]), 4), round(float(y), 4)))
    for lx, ly in pos:
        p = L2W(cx, cy, ang, lx, ly)
        mb.cyl(p[0], p[1], zp, r, hc, 7, MARBLE, top=False)
    c = L2W(cx, cy, ang, 0, 0.25)
    mb.box(c[0], c[1], zp, w - 2 * inset - 0.28, l - 2 * inset - 0.7, hc, ang, STUCCO)
    door = L2W(cx, cy, ang, 0, 0.25 - (l - 2 * inset - 0.7) / 2)
    mb.window(door[0], door[1], ang, 0, 0, zp, 0.22, hc * 0.6, True, DARK)
    mb.box(cx, cy, zp + hc, w, l, 0.12, ang, MARBLE, MARBLE)
    mb.gable_roof(cx, cy, zp + hc + 0.12, w, l, ang, w * 0.2, roof, MARBLE, 0.05, 'y')
    if occ is not None:
        occ.rect(cx, cy, w + 0.6, l + 1.0, ang, 0.2)
    return zp


def tholos(mb, T, cx, cy, r, hc, occ=None):
    zmin, zmax = fp_ground(T, cx, cy, 2 * r + 0.4, 2 * r + 0.4, 0)
    zp = zmax + 0.25
    mb.cyl(cx, cy, zmin - 0.4, r + 0.2, zp - (zmin - 0.4), 18, MARBLE_D, MARBLE)
    for k in range(10):
        a = 2 * math.pi * k / 10
        mb.cyl(cx + r * math.cos(a), cy + r * math.sin(a), zp, 0.05, hc, 6, MARBLE, top=False)
    mb.cyl(cx, cy, zp, r * 0.62, hc, 14, STUCCO, top=False)
    mb.cyl(cx, cy, zp + hc, r + 0.07, 0.1, 18, MARBLE, MARBLE)
    mb.dome(cx, cy, zp + hc + 0.1, r + 0.05, 0.55, ROOF, 18, 5)
    if occ is not None:
        occ.circle(cx, cy, r + 0.6)


def colosseum(mb, T, cx, cy, a, b, ang_deg, H, occ):
    ang = math.radians(ang_deg)
    zmin, zmax = fp_ground(T, cx, cy, 2 * a, 2 * b, ang)
    z0 = zmax
    n = 60

    def ring(sc, z):
        out = []
        for k in range(n):
            t = 2 * math.pi * k / n
            p = L2W(cx, cy, ang, a * sc * math.cos(t), b * sc * math.sin(t))
            out.append((p[0], p[1], z))
        return out

    ob = mb.vid(ring(1.0, zmin - 0.5))
    ot = mb.vid(ring(1.0, z0 + H))
    for k in range(n):
        k2 = (k + 1) % n
        mb.face((ob + k, ob + k2, ot + k2, ot + k), TRAV)
    rim = mb.vid(ring(0.94, z0 + H))
    for k in range(n):
        k2 = (k + 1) % n
        mb.face((ot + k, ot + k2, rim + k2, rim + k), MARBLE_D)
    steps = [(0.94, z0 + H), (0.86, z0 + H - 0.35), (0.78, z0 + H - 0.7), (0.70, z0 + H - 1.05), (0.62, z0 + 0.55)]
    prev = rim
    for j in range(len(steps) - 1):
        s1, zt = steps[j]
        s2, zn = steps[j + 1]
        tread = mb.vid(ring(s2, zt))
        for k in range(n):
            k2 = (k + 1) % n
            mb.face((prev + k, prev + k2, tread + k2, tread + k), TRAV if j % 2 else lighten(TRAV, 1.05))
        riser = mb.vid(ring(s2, zn))
        for k in range(n):
            k2 = (k + 1) % n
            mb.face((tread + k, tread + k2, riser + k2, riser + k), TRAV_D)
        prev = riser
    pod = mb.vid(ring(0.62, z0 + 0.1))
    for k in range(n):
        k2 = (k + 1) % n
        mb.face((prev + k, prev + k2, pod + k2, pod + k), MARBLE_D)
    mb.face([pod + k for k in range(n)], (0.82, 0.71, 0.50))
    # facade: arches in three tiers, cornices
    O = ring(1.0, 0.0)
    tiers = [(z0 + 0.12, 0.5), (z0 + 0.78, 0.46), (z0 + 1.38, 0.38)]
    for k in range(n):
        p0 = np.array(O[k][:2])
        p1 = np.array(O[(k + 1) % n][:2])
        m = (p0 + p1) / 2
        d = p1 - p0
        L = float(np.linalg.norm(d))
        u = d / L
        nn = np.array([u[1], -u[0]])
        if np.dot(nn, m - np.array([cx, cy])) < 0:
            nn = -nn
        for zz, hh in tiers:
            mb.arch(m, u, nn, zz, L * 0.56, hh)
    for zc in (z0 + 0.7, z0 + 1.32, z0 + 1.86):
        bb = mb.vid(ring(1.012, zc))
        bt = mb.vid(ring(1.012, zc + 0.05))
        bi = mb.vid(ring(1.0, zc + 0.05))
        for k in range(n):
            k2 = (k + 1) % n
            mb.face((bb + k, bb + k2, bt + k2, bt + k), MARBLE_D)
            mb.face((bt + k, bt + k2, bi + k2, bi + k), MARBLE_D)
    occ.ellipse(cx, cy, a + 0.7, b + 0.7, ang)


def u_path(r, x_start, xc, step=0.55, nsemi=16):
    """U-shaped polyline in hippodrome-local coords at distance r from the axis:
    along +y from x_start to xc, round the semicircular end, back along -y to x_start."""
    n = max(1, int(round((xc - x_start) / step)))
    pts = [(x_start + (xc - x_start) * i / n, r) for i in range(n + 1)]
    for k in range(1, nsemi):
        a = math.pi / 2 - math.pi * k / nsemi
        pts.append((xc + r * math.cos(a), r * math.sin(a)))
    pts += [(xc - (xc - x_start) * i / n, -r) for i in range(n + 1)]
    return pts


def hippodrome(mb, T, occ, avenue_occ, rng, trees):
    """Chariot-racing circus. Local frame: lx runs from the open harbour end (0) to the curved end (L)."""
    x0, y0, a_deg, L, W = HIPPO
    ang = math.radians(a_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    R = W / 2
    ra = 1.75                    # half-width of the sand track
    rw = R - 0.16                # inner face of the outer wall
    xc = L - R                   # centre of the curved end (sphendone)
    x_open = 0.95                # seating starts behind the harbour towers
    z0 = HIPPO_Z + 0.05          # track level
    zb = HIPPO_Z - 0.6

    def W2(lx, ly):
        return L2W(x0, y0, ang, lx, ly)

    def wv(vx, vy):
        return (vx * ca - vy * sa, vx * sa + vy * ca)

    def band(ri, ro, xs, ztop, col, col_top, zbot=None):
        zbot = zb if zbot is None else zbot
        pts = u_path(ro, xs, xc) + u_path(ri, xs, xc)[::-1]
        mb.prism([W2(px, py) for px, py in pts], zbot, ztop - zbot, col, col_top)

    SAND = (0.86, 0.75, 0.52)
    # sand track (runs right out to the harbour end)
    mb.prism([W2(px, py) for px, py in u_path(ra + 0.01, -0.05, xc)], zb, z0 - zb, (0.78, 0.68, 0.48), SAND)
    # stepped seating (cavea) on both long sides and around the curved end
    ntier = 4
    for k in range(ntier):
        ri = ra + (rw - ra) * k / ntier
        ro = ra + (rw - ra) * (k + 1) / ntier
        band(ri, ro + 0.002, x_open, z0 + 0.22 + 0.17 * (k + 1), TRAV_D, TRAV if k % 2 else lighten(TRAV, 1.05))
    ztt = z0 + 0.22 + 0.17 * ntier
    band(rw, R, x_open, z0 + 1.18, TRAV, MARBLE_D)                                  # outer wall
    band(rw - 0.2, R + 0.04, x_open, z0 + 1.25, MARBLE, jit(rng, ROOF), z0 + 1.18)   # roofed top gallery
    for px, py in u_path(rw - 0.1, x_open, xc, 0.42):
        if py > 0 and 8.3 < px < 10.7:
            continue                                                                 # kathisma there
        q = W2(px, py)
        mb.cyl(q[0], q[1], ztt, 0.03, z0 + 1.18 - ztt, 6, MARBLE, top=False)
    # two tiers of arches round the outer facade
    op = u_path(R, x_open, xc)
    for i in range(len(op) - 1):
        (ax, ay), (bx, by) = op[i], op[i + 1]
        Lc = math.hypot(bx - ax, by - ay)
        if Lc < 0.3:
            continue
        mx, my = (ax + bx) / 2, (ay + by) / 2
        nx_, ny_ = mx - min(max(mx, x_open), xc), my
        nn = math.hypot(nx_, ny_)
        wu = wv((bx - ax) / Lc, (by - ay) / Lc)
        wn = wv(nx_ / nn, ny_ / nn)
        mb.arch(W2(mx, my), wu, wn, z0 - 0.02, Lc * 0.55, 0.5)
        mb.arch(W2(mx, my), wu, wn, z0 + 0.6, Lc * 0.42, 0.34)
    # end walls of the seating at the open end
    # harbour towers flanking the opening, each crowned by a gilded quadriga facing the sea
    for sgn in (-1, 1):
        tc_ = W2(0.45, sgn * 2.275)
        zt = z0 + 2.0
        mb.box(tc_[0], tc_[1], zb, 1.0, 1.05, zt - zb, ang, TRAV, MARBLE_D)
        mb.box(tc_[0], tc_[1], zt, 1.08, 1.13, 0.07, ang, MARBLE, MARBLE)
        for zz in (z0 + 0.25, z0 + 1.15):
            mb.arch(W2(-0.05, sgn * 2.275), wv(0, -1), wv(-1, 0), zz, 0.32, 0.55)
            mb.arch(W2(0.45, sgn * 1.75), wv(1, 0), wv(0, -sgn), zz, 0.3, 0.5)
        zq = zt + 0.07
        for oy in (-0.15, -0.05, 0.05, 0.15):
            h = W2(0.30, sgn * 2.275 + oy)
            mb.box(h[0], h[1], zq + 0.08, 0.22, 0.045, 0.08, ang, GOLD, GOLD)       # body
            mb.box(h[0], h[1], zq, 0.16, 0.03, 0.08, ang, GOLD, GOLD)               # legs
            hd = W2(0.18, sgn * 2.275 + oy)
            mb.box(hd[0], hd[1], zq + 0.14, 0.06, 0.035, 0.1, ang, GOLD, GOLD)      # neck/head
        ch = W2(0.58, sgn * 2.275)
        mb.box(ch[0], ch[1], zq, 0.14, 0.36, 0.12, ang, GOLD, GOLD)
    # monumental water stair stepping down into the harbour
    for k in range(6):
        xa, xb = -0.05 - 0.42 * (k + 1), -0.05 - 0.42 * k
        p = W2((xa + xb) / 2, 0)
        mb.box(p[0], p[1], -1.0, xb - xa + 0.01, 2 * ra, z0 - 0.14 * (k + 1) + 1.0, ang, MARBLE_D, MARBLE)
    for sgn in (-1, 1):                                   # honorific columns at the stair head
        p = W2(-0.3, sgn * (ra + 0.22))
        mb.box(p[0], p[1], -1.0, 0.36, 0.36, z0 + 1.2, ang, MARBLE_D, MARBLE)
        mb.cyl(p[0], p[1], z0 + 0.2, 0.08, 1.5, 10, MARBLE, MARBLE)
        mb.box(p[0], p[1], z0 + 1.7, 0.2, 0.2, 0.05, ang, MARBLE, MARBLE)
        mb.box(p[0], p[1], z0 + 1.75, 0.08, 0.08, 0.22, ang, GOLD, GOLD)
    # spina (central barrier) with its water channel, obelisk, monuments and turning posts
    sx0, sx1 = 3.2, xc - 1.0
    sm = W2((sx0 + sx1) / 2, 0)
    mb.box(sm[0], sm[1], zb, sx1 - sx0, 0.34, z0 + 0.14 - zb, ang, MARBLE_D, MARBLE)
    mb.box(sm[0], sm[1], z0 + 0.14, sx1 - sx0 - 0.5, 0.16, 0.02, ang, MARBLE, POOL)
    mb.box(sm[0], sm[1], z0 + 0.14, 0.42, 0.42, 0.12, ang, MARBLE_D, MARBLE)
    mb.obelisk(sm[0], sm[1], z0 + 0.26, 0.22, 1.55, ang, (0.74, 0.56, 0.50))
    for t, kind in ((0.14, 'col'), (0.3, 'statue'), (0.4, 'statue'), (0.6, 'statue'), (0.7, 'serpent'), (0.86, 'obelisk')):
        p = W2(sx0 + (sx1 - sx0) * t, 0)
        if kind == 'col':
            mb.cyl(p[0], p[1], z0 + 0.14, 0.06, 1.0, 10, MARBLE, MARBLE)
            mb.box(p[0], p[1], z0 + 1.14, 0.07, 0.07, 0.16, ang, GOLD, GOLD)
        elif kind == 'statue':
            mb.box(p[0], p[1], z0 + 0.14, 0.16, 0.16, 0.14, ang, MARBLE, MARBLE)
            mb.box(p[0], p[1], z0 + 0.28, 0.06, 0.05, 0.17, ang, GOLD, GOLD)
        elif kind == 'serpent':
            mb.cyl(p[0], p[1], z0 + 0.14, 0.045, 0.7, 8, (0.50, 0.40, 0.22), (0.5, 0.4, 0.22))
            mb.cyl(p[0], p[1], z0 + 0.84, 0.1, 0.05, 10, GOLD, GOLD)
        else:
            mb.obelisk(p[0], p[1], z0 + 0.14, 0.15, 0.95, ang, (0.70, 0.64, 0.56))
    for ex in (sx0 - 0.28, sx1 + 0.28):                   # metae
        p = W2(ex, 0)
        mb.cyl(p[0], p[1], zb, 0.22, z0 + 0.12 - zb, 12, MARBLE_D, MARBLE)
        for oy in (-0.1, 0.0, 0.1):
            q = W2(ex, oy)
            mb.cone(q[0], q[1], z0 + 0.12, 0.045, 0.42, GOLD)
    # kathisma - the imperial box, a gilded-dome pavilion over the north stands
    kc = W2(9.5, 2.62)
    zk = ztt + 0.02
    mb.box(kc[0], kc[1], zb, 1.9, 1.76, zk - zb, ang, MARBLE_D, MARBLE)
    bk = W2(9.5, 2.9)
    mb.box(bk[0], bk[1], zk, 1.9, 1.2, 0.72, ang, (0.93, 0.88, 0.80), top=False)
    mb.columns(W2(8.65, 1.8), W2(10.35, 1.8), 6, zk, 0.72, 0.04)
    pf = W2(9.5, 1.82)
    mb.box(pf[0], pf[1], zk, 1.7, 0.05, 0.12, ang, (0.45, 0.14, 0.30))
    mb.box(kc[0], kc[1], zk + 0.72, 1.98, 1.84, 0.1, ang, MARBLE, MARBLE)
    mb.cyl(kc[0], kc[1], zk + 0.82, 0.56, 0.15, 18, MARBLE, top=False)
    mb.dome(kc[0], kc[1], zk + 0.97, 0.56, 0.75, GOLD, 18, 5)
    # chariots of the four racing colours rounding the spina
    teams = [(0.78, 0.12, 0.10), (0.15, 0.30, 0.72), (0.18, 0.55, 0.20), (0.95, 0.95, 0.92)]
    for (lx, ly, d), team in zip(((6.4, 0.95, -1), (11.8, 1.0, -1), (8.6, -0.98, 1), (13.6, -0.9, 1)), teams):
        c = W2(lx, ly)
        mb.box(c[0], c[1], z0, 0.12, 0.13, 0.09, ang, team, team)
        for oy in (-0.075, -0.025, 0.025, 0.075):
            hcol = [(0.40, 0.25, 0.14), (0.15, 0.10, 0.08), (0.92, 0.90, 0.86), (0.55, 0.36, 0.20)][rng.integers(4)]
            h = W2(lx + d * 0.22, ly + oy)
            mb.box(h[0], h[1], z0 + 0.06, 0.17, 0.035, 0.06, ang, hcol, hcol)
            mb.box(h[0], h[1], z0, 0.12, 0.025, 0.06, ang, hcol, hcol)
            hd = W2(lx + d * 0.32, ly + oy)
            mb.box(hd[0], hd[1], z0 + 0.09, 0.05, 0.03, 0.07, ang, hcol, hcol)
    # cypresses round the curved end
    for a in (-70, -40, -12, 12, 40, 70):
        p = W2(xc + (R + 0.75) * math.cos(math.radians(a)), (R + 0.75) * math.sin(math.radians(a)))
        trees.append(('cypress', p[0], p[1], T.hs(*p), rng.uniform(0.7, 0.9)))
    c = W2(L / 2, 0.3)
    occ.rect(c[0], c[1], L + 0.8, W + 1.8, ang)
    c = W2(L / 2 - 1.5, 0.3)
    avenue_occ.rect(c[0], c[1], L + 3.6, W + 1.6, ang)


def baths(mb, T, cx, cy, ang_deg, occ, scale=1.0, steam=None):
    ang = math.radians(ang_deg)
    W, D = 7.0 * scale, 4.4 * scale
    zmin, zmax = fp_ground(T, cx, cy, W, D + 4.0 * scale, ang)
    z0 = zmax
    top_c = (0.82, 0.76, 0.64)
    mb.box(cx, cy, zmin - 0.4, W, D, z0 + 1.0 - (zmin - 0.4), ang, STUCCO, top_c)
    mb.box(cx, cy, z0 + 1.0, 3.6 * scale, 3.6 * scale, 0.45, ang, STUCCO, top_c)
    R = 1.45 * scale
    mb.cyl(cx, cy, z0 + 1.45, R, 0.3, 28, STUCCO, top=False)
    mb.dome(cx, cy, z0 + 1.75, R, 0.85, LEAD, 28, 7)
    mb.cyl(cx, cy, z0 + 1.75 + R * 0.85 - 0.02, 0.22 * scale, 0.12, 10, STUCCO, STUCCO)
    for sx in (-2.55 * scale, 2.55 * scale):
        p = L2W(cx, cy, ang, sx, 0.3 * scale)
        mb.cyl(p[0], p[1], z0 + 1.0, 0.75 * scale, 0.18, 18, STUCCO, top=False)
        mb.dome(p[0], p[1], z0 + 1.18, 0.75 * scale, 0.8, LEAD, 18, 5)
    # apse at back
    ap = []
    for k in range(13):
        a = math.pi * k / 12
        ap.append(L2W(cx, cy, ang, 1.1 * scale * math.cos(a), D / 2 + 1.1 * scale * math.sin(a) - 0.05))
    mb.prism(ap, zmin - 0.4, z0 + 0.85 - (zmin - 0.4), STUCCO, top_c)
    # facade windows (front = local -y)
    u = (math.cos(ang), math.sin(ang))
    nf = (math.sin(ang), -math.cos(ang))
    for k in range(9):
        lx = -W / 2 + (k + 0.5) * W / 9
        p = L2W(cx, cy, ang, lx, -D / 2)
        mb.arch(p, u, nf, z0 + 0.25, 0.32 * scale, 0.55)
    for k in range(5):
        lx = -1.8 * scale + (k + 0.5) * 3.6 * scale / 5
        p = L2W(cx, cy, ang, lx, -1.8 * scale)
        mb.arch(p, u, nf, z0 + 1.08, 0.3 * scale, 0.3)
    # pool court in front
    pc = L2W(cx, cy, ang, 0, -(D / 2 + 1.7 * scale))
    mb.box(pc[0], pc[1], zmin - 0.4, 5.2 * scale, 3.0 * scale, z0 + 0.05 - (zmin - 0.4), ang, MARBLE_D, PAVE)
    mb.box(pc[0], pc[1], z0 + 0.05, 3.8 * scale, 1.7 * scale, 0.07, ang, MARBLE, POOL)
    for sx in (-2.45 * scale, 2.45 * scale):
        p0 = L2W(cx, cy, ang, sx, -(D / 2 + 0.3 * scale))
        p1 = L2W(cx, cy, ang, sx, -(D / 2 + 3.0 * scale))
        mb.columns(p0, p1, 7, z0 + 0.05, 0.55, 0.045)
        pm = L2W(cx, cy, ang, sx, -(D / 2 + 1.65 * scale))
        mb.box(pm[0], pm[1], z0 + 0.6, 0.35, 2.9 * scale, 0.06, ang, MARBLE, ROOF)
    occ.rect(cx, cy - 0.0, W + 0.6, D + 0.6, ang)
    occ.rect(pc[0], pc[1], 5.6 * scale, 3.4 * scale, ang)
    ap_c = L2W(cx, cy, ang, 0, D / 2 + 0.6 * scale)
    occ.circle(ap_c[0], ap_c[1], 1.4 * scale)
    if steam is not None:
        steam.append((cx, cy, z0 + 1.75 + R * 0.85 + 0.2, 1.0 * scale))


def rotunda(mb, T, cx, cy, face_deg, r, occ, steam=None):
    zmin, zmax = fp_ground(T, cx, cy, 2 * r + 1.6, 2 * r + 1.6, 0)
    z0 = zmax
    mb.cyl(cx, cy, zmin - 0.4, r, z0 + 1.1 - (zmin - 0.4), 30, STUCCO, top=False)
    mb.cyl(cx, cy, z0 + 1.1, r + 0.06, 0.07, 30, MARBLE, MARBLE)
    mb.dome(cx, cy, z0 + 1.17, r, 0.72, LEAD, 30, 7)
    mb.cyl(cx, cy, z0 + 1.17 + r * 0.72 - 0.03, 0.3, 0.05, 12, MARBLE, DARK)
    f = math.radians(face_deg)
    ang = f + math.pi / 2
    pc = (cx + (r + 0.45) * math.cos(f), cy + (r + 0.45) * math.sin(f))
    mb.box(pc[0], pc[1], zmin - 0.4, 2.0, 1.2, z0 + 0.15 - (zmin - 0.4), ang, MARBLE_D, MARBLE)
    p0 = L2W(pc[0], pc[1], ang, -0.85, -0.45)
    p1 = L2W(pc[0], pc[1], ang, 0.85, -0.45)
    mb.columns(p0, p1, 6, z0 + 0.15, 0.85, 0.05)
    p0 = L2W(pc[0], pc[1], ang, -0.85, 0.05)
    p1 = L2W(pc[0], pc[1], ang, 0.85, 0.05)
    mb.columns(p0, p1, 6, z0 + 0.15, 0.85, 0.05)
    mb.box(pc[0], pc[1], z0 + 1.0, 2.0, 1.2, 0.1, ang, MARBLE, MARBLE)
    mb.gable_roof(pc[0], pc[1], z0 + 1.1, 2.0, 1.2, ang, 0.35, ROOF, MARBLE, 0.04, 'y')
    occ.circle(cx, cy, r + 0.5)
    occ.rect(pc[0], pc[1], 2.4, 1.6, ang)


def theater(mb, T, cx, cy, face_deg, R, occ):
    ang = math.radians(face_deg) + math.pi / 2
    zmin, zmax = fp_ground(T, cx, cy, 2 * R + 0.4, 2 * R + 0.4, ang)
    tiers, r0 = 6, 1.0
    for k in range(tiers):
        ri = r0 + (R - r0) * k / tiers
        ro = r0 + (R - r0) * (k + 1) / tiers
        zt = zmax + 0.12 + 0.17 * (k + 1)
        pts = [L2W(cx, cy, ang, ro * math.cos(math.pi * i / 16), ro * math.sin(math.pi * i / 16)) for i in range(17)]
        pts += [L2W(cx, cy, ang, ri * math.cos(math.pi * i / 16), ri * math.sin(math.pi * i / 16)) for i in range(16, -1, -1)]
        mb.prism(pts, zmin - 0.4, zt - (zmin - 0.4), TRAV_D, TRAV if k % 2 else lighten(TRAV, 1.05))
    pts = [L2W(cx, cy, ang, (R + 0.18) * math.cos(math.pi * i / 16), (R + 0.18) * math.sin(math.pi * i / 16)) for i in range(17)]
    pts += [L2W(cx, cy, ang, R * math.cos(math.pi * i / 16), R * math.sin(math.pi * i / 16)) for i in range(16, -1, -1)]
    mb.prism(pts, zmin - 0.4, zmax + 1.35 - (zmin - 0.4), TRAV, MARBLE_D)
    orch = [L2W(cx, cy, ang, r0 * math.cos(math.pi * i / 16), r0 * math.sin(math.pi * i / 16)) for i in range(17)]
    mb.prism(orch, zmin - 0.4, zmax + 0.12 - (zmin - 0.4), MARBLE_D, PAVE)
    sc = L2W(cx, cy, ang, 0, -0.45)
    mb.box(sc[0], sc[1], zmin - 0.4, 2 * R + 0.3, 0.55, zmax + 1.05 - (zmin - 0.4), ang, STUCCO, ROOF)
    u = (math.cos(ang), math.sin(ang))
    nb = (-math.sin(ang), math.cos(ang))
    for k in range(7):
        lx = -R + (k + 0.5) * 2 * R / 7
        p = L2W(cx, cy, ang, lx, -0.45 + 0.275)
        mb.arch(p, u, nb, zmax + 0.15, 0.28, 0.5, MARBLE_D)
        p = L2W(cx, cy, ang, lx, -0.45 - 0.275)
        mb.arch(p, u, (-nb[0], -nb[1]), zmax + 0.15, 0.25, 0.45)
    occ.rect(cx, cy + 0.0, 2 * R + 1.0, 2 * R + 1.0, ang)


def stoa(mb, T, a, b, rng, kind):
    a = np.asarray(a)
    b = np.asarray(b)
    m = (a + b) / 2
    d = b - a
    L = float(np.linalg.norm(d))
    ang = math.atan2(d[1], d[0])
    u = d / L
    nw = np.array([u[1], -u[0]])               # local -y = toward the water
    zmin, zmax = fp_ground(T, m[0], m[1], L, 1.2, ang)
    if kind == 'stoa':
        dd, h = 0.85, 0.72
        c = L2W(m[0], m[1], ang, 0, 0.18)
        mb.box(c[0], c[1], zmin - 0.4, L, dd, zmax + h - (zmin - 0.4), ang, STUCCO, top=False)
        mb.gable_roof(c[0], c[1], zmax + h, L, dd, ang, 0.2, jit(rng, ROOF), STUCCO)
        p0 = L2W(m[0], m[1], ang, -L / 2 + 0.1, -0.52)
        p1 = L2W(m[0], m[1], ang, L / 2 - 0.1, -0.52)
        mb.columns(p0, p1, max(3, int(L / 0.32)), zmax, 0.6, 0.04)
        sl = L2W(m[0], m[1], ang, 0, -0.38)
        mb.box(sl[0], sl[1], zmax + 0.6, L, 0.4, 0.06, ang, MARBLE, jit(rng, ROOF))
        for k in range(max(2, int(L / 0.5))):
            lx = -L / 2 + (k + 0.5) * L / max(2, int(L / 0.5))
            mb.window(c[0], c[1], ang, lx, -dd / 2, zmax + 0.05, 0.18, 0.38, True, DARK)
    else:
        dd, h = 1.15, 0.85
        wc = jit(rng, (0.82, 0.64, 0.44))
        mb.box(m[0], m[1], zmin - 0.4, L, dd, zmax + h - (zmin - 0.4), ang, wc, top=False)
        mb.gable_roof(m[0], m[1], zmax + h, L, dd, ang, 0.26, jit(rng, ROOF), wc)
        n = max(2, int(L / 0.42))
        for k in range(n):
            lx = -L / 2 + (k + 0.5) * L / n
            p = L2W(m[0], m[1], ang, lx, -dd / 2)
            mb.arch(p, u, nw, zmax, 0.26, 0.5)
            mb.window(m[0], m[1], ang, lx, -dd / 2, zmax + 0.6, 0.06, 0.09, True)
    return m, L, ang


def palace(mb, T, occ, trees, rng):
    ang = math.radians(15)
    cx, cy = -31.6, -17.0
    zt = fp_ground(T, cx, cy, 8, 7, ang)[1]
    W1 = (0.95, 0.92, 0.86)
    # main hall with portico
    mb.box(cx, cy, zt - 0.8, 6.2, 2.8, 2.25, ang, W1, top=False)
    mb.hip_roof(cx, cy, zt + 1.45, 6.2, 2.8, ang, 0.7, ROOF)
    for k in range(11):
        lx = -2.9 + k * 0.58
        mb.window(cx, cy, ang, lx, -1.4, zt + 0.9, 0.09, 0.2, True)
        mb.window(cx, cy, ang, lx, 1.4, zt + 0.9, 0.09, 0.2, False)
    p0 = L2W(cx, cy, ang, -2.9, -1.85)
    p1 = L2W(cx, cy, ang, 2.9, -1.85)
    mb.columns(p0, p1, 13, zt, 1.0, 0.065, MARBLE)
    pr = L2W(cx, cy, ang, 0, -1.68)
    mb.box(pr[0], pr[1], zt + 1.0, 6.2, 0.55, 0.12, ang, MARBLE, MARBLE)
    pt = L2W(cx, cy, ang, 0, -1.85)
    mb.box(pt[0], pt[1], zt - 0.5, 2.6, 0.7, 0.62, ang, MARBLE_D, MARBLE)        # front steps
    mb.gable_roof(pr[0], pr[1], zt + 1.12, 2.6, 0.6, ang, 0.38, ROOF, MARBLE, 0.04, 'y')
    # raised central block
    mb.box(cx, cy, zt + 1.45, 2.4, 1.6, 0.75, ang, W1, top=False)
    mb.hip_roof(cx, cy, zt + 2.2, 2.4, 1.6, ang, 0.5, ROOF)
    # rear hall
    rh = L2W(cx, cy, ang, -0.6, 2.35)
    mb.box(rh[0], rh[1], zt - 0.8, 4.4, 2.0, 2.9, ang, (0.90, 0.85, 0.76), top=False)
    mb.hip_roof(rh[0], rh[1], zt + 2.1, 4.4, 2.0, ang, 0.6, jit(rng, ROOF))
    # wings
    for sx in (-3.75, 3.75):
        wc = L2W(cx, cy, ang, sx, -1.5)
        mb.box(wc[0], wc[1], zt - 0.8, 1.3, 3.0, 1.95, ang, W1, top=False)
        mb.hip_roof(wc[0], wc[1], zt + 1.15, 1.3, 3.0, ang, 0.42, ROOF)
        for k in range(4):
            mb.window(wc[0], wc[1], ang, -0.45 + k * 0.3, -1.5, zt + 0.55, 0.08, 0.2, True)
    occ.ellipse(PLATEAU[0], PLATEAU[1], PLATEAU[2] * 0.92, PLATEAU[3] * 0.92)
    # gravel forecourt
    fc = L2W(cx, cy, ang, 0, -2.75)
    fz = fp_ground(T, fc[0], fc[1], 9.0, 1.1, ang)
    mb.box(fc[0], fc[1], fz[0] - 0.4, 9.0, 1.1, fz[1] + 0.03 - (fz[0] - 0.4), ang, MARBLE_D, PAVE)
    # parterre gardens east of the palace, hedged, with fountains
    for i in range(3):
        for j in range(2):
            p = L2W(cx, cy, ang, 4.75 + i * 1.3, -2.0 + j * 1.35)
            pz = fp_ground(T, p[0], p[1], 1.15, 1.15, ang)
            mb.box(p[0], p[1], pz[0] - 0.4, 1.15, 1.15, pz[1] + 0.06 - (pz[0] - 0.4), ang, (0.2, 0.32, 0.12), lighten(GRASS, 1.1))
            for lx, ly in ((-0.5, 0), (0.5, 0), (0, -0.5), (0, 0.5)):
                q = L2W(p[0], p[1], ang, lx, ly)
                mb.box(q[0], q[1], pz[1] + 0.06, 1.1 if lx == 0 else 0.07, 0.07 if lx == 0 else 1.1, 0.07, ang, (0.16, 0.27, 0.10))
            fl = [(0.80, 0.30, 0.35), (0.92, 0.78, 0.35), (0.85, 0.55, 0.75)][(i + j) % 3]
            mb.box(p[0], p[1], pz[1] + 0.06, 0.55, 0.55, 0.03, ang + 0.785, fl)
            mb.cyl(p[0], p[1], pz[1] + 0.06, 0.12, 0.08, 10, MARBLE, POOL)
    # servants' wing / barracks along the west cliff
    bw_ = L2W(cx, cy, ang, -5.6, -1.2)
    bz = fp_ground(T, bw_[0], bw_[1], 1.2, 4.8, ang)
    mb.box(bw_[0], bw_[1], bz[0] - 0.5, 1.2, 4.8, bz[1] + 0.95 - (bz[0] - 0.5), ang, (0.86, 0.78, 0.64), top=False)
    mb.gable_roof(bw_[0], bw_[1], bz[1] + 0.95, 1.2, 4.8, ang, 0.3, jit(rng, ROOF), (0.86, 0.78, 0.64))
    for k in range(7):
        q = L2W(bw_[0], bw_[1], ang, 0.6, -2.1 + k * 0.7)
        mb.arch(q, (-math.sin(ang), math.cos(ang)), (math.cos(ang), math.sin(ang)), bz[1] + 0.12, 0.2, 0.4)
    # palace chapel
    tp = L2W(cx, cy, ang, 3.6, 3.0)
    temple(mb, T, tp[0], tp[1], math.degrees(ang) - 90, 1.6, 2.3, 0.7, 4)
    # keep
    kx, ky = -36.6, -15.8
    kz = T.hs(kx, ky)
    mb.box(kx, ky, kz - 0.6, 1.5, 1.5, 3.9, ang, STONE_D, STONE_TOP)
    mb.hip_roof(kx, ky, kz + 3.3, 1.5, 1.5, ang, 0.9, ROOF, 0.08)
    for zz in (kz + 1.2, kz + 2.3):
        mb.window(kx, ky, ang, 0, -0.75, zz, 0.1, 0.22, True, DARK)
    # tholos & gardens
    tholos(mb, T, -26.2, -20.4, 0.75, 0.9)
    gc = L2W(cx, cy, ang, 0, -4.1)
    gz = fp_ground(T, gc[0], gc[1], 6.4, 2.6, ang)
    mb.box(gc[0], gc[1], gz[0] - 0.5, 6.4, 2.6, gz[1] + 0.08 - (gz[0] - 0.5), ang, MARBLE_D, GRASS)
    mb.box(gc[0], gc[1], gz[1] + 0.08, 2.2, 0.7, 0.04, ang, MARBLE, POOL)
    for side in (-1, 1):
        for k in range(7):
            p = L2W(gc[0], gc[1], ang, -2.9 + k * 0.97, side * 1.05)
            trees.append(('cypress', p[0], p[1], gz[1] + 0.06, rng.uniform(0.8, 1.05)))
    # cliff colonnade
    a, b = (-35.2, -22.6), (-27.4, -23.4)
    za = min(T.hs(*a), T.hs(*b))
    mb.columns(a, b, 18, za, 0.6, 0.045)
    d = np.subtract(b, a)
    m = (np.asarray(a) + np.asarray(b)) / 2
    mb.box(m[0], m[1], za + 0.6, float(np.linalg.norm(d)) + 0.2, 0.32, 0.06, math.atan2(d[1], d[0]), MARBLE, ROOF)
    # trees around the grounds, kept clear of buildings
    keep_out = [(cx, cy, 8.4, 4.8), (rh[0], rh[1], 5.0, 2.6), (bw_[0], bw_[1], 1.8, 5.4), (tp[0], tp[1], 2.4, 3.2),
                (fc[0], fc[1], 9.4, 1.6), (gc[0], gc[1], 6.8, 3.0)]
    placed = 0
    for k in range(400):
        x = rng.uniform(-38.5, -23.5)
        y = rng.uniform(-24.0, -12.0)
        er = math.hypot((x - PLATEAU[0]) / PLATEAU[2], (y - PLATEAU[1]) / PLATEAU[3])
        if er > 0.86:
            continue
        lx_ok = True
        for (kx, ky, kw, kd) in keep_out:
            c, s = math.cos(-ang), math.sin(-ang)
            dx, dy = x - kx, y - ky
            if abs(dx * c - dy * s) < kw / 2 and abs(dx * s + dy * c) < kd / 2:
                lx_ok = False
                break
        if not lx_ok or math.hypot(x + 26.2, y + 20.4) < 1.4 or math.hypot(x + 36.6, y + 15.8) < 1.3:
            continue
        if any(math.hypot(x - t[1], y - t[2]) < 0.45 for t in trees):
            continue
        p0 = L2W(cx, cy, ang, 4.1, -2.7)
        if 0 <= (x - p0[0]) * math.cos(ang) + (y - p0[1]) * math.sin(ang) <= 3.9 and \
                0 <= -(x - p0[0]) * math.sin(ang) + (y - p0[1]) * math.cos(ang) <= 2.7:
            continue
        trees.append(('pine' if rng.random() < 0.35 else 'cypress', x, y, T.hs(x, y), rng.uniform(0.75, 1.15)))
        placed += 1
        if placed > 45:
            break


def forum(mb, T, occ, trees, rng):
    cx, cy, W, D = 1.5, 11.0, 7.0, 7.5
    zmin, zmax = fp_ground(T, cx, cy, W + 2.2, D, 0)
    z = zmax + 0.05
    mb.box(cx, cy, zmin - 0.4, W + 2.2, D, z - (zmin - 0.4), 0, MARBLE_D, PAVE)
    for sgn in (-1, 1):
        xc = cx + sgn * (W / 2 - 0.05)
        mb.columns((xc, cy - D / 2 + 0.3), (xc, cy + D / 2 - 0.3), 13, z, 0.6, 0.045)
        xb = cx + sgn * (W / 2 + 0.72)
        mb.box(xb, cy, z, 0.55, D, 0.62, 0, STUCCO, top=False)
        mb.gable_roof(cx + sgn * (W / 2 + 0.47), cy, z + 0.62, 1.05, D, 0, 0.18, ROOF, STUCCO)
    # triumphal arch at the south entrance
    ay = cy - D / 2 - 0.1
    mb.box(cx, ay, zmin - 0.3, 1.8, 0.5, z + 1.25 - (zmin - 0.3), 0, MARBLE, MARBLE)
    mb.arch((cx, ay - 0.25), (1, 0), (0, -1), z, 0.5, 0.85)
    mb.arch((cx, ay + 0.25), (1, 0), (0, 1), z, 0.5, 0.85)
    mb.box(cx, ay, z + 1.25, 0.5, 0.25, 0.2, 0, GOLD, GOLD)
    # statue
    mb.box(cx, cy - 0.8, z, 0.35, 0.35, 0.28, 0, MARBLE, MARBLE)
    mb.box(cx, cy - 0.8, z + 0.28, 0.1, 0.08, 0.28, 0, GOLD, GOLD)
    # rostra & small shrines
    mb.box(cx - 1.8, cy + 2.2, z, 1.0, 0.5, 0.18, 0, MARBLE_D, MARBLE)
    tholos(mb, T, cx + 2.0, cy + 2.4, 0.45, 0.5)
    temple(mb, T, 1.5, 16.8, -90, 3.0, 4.0, 1.05, 6, occ)
    # basilica
    bx, by = 7.3, 11.0
    bz = fp_ground(T, bx, by, 3.4, 7.2, 0)
    mb.box(bx, by, bz[0] - 0.4, 3.3, 7.0, bz[1] + 0.85 - (bz[0] - 0.4), 0, STUCCO, top=False)
    mb.hip_roof(bx, by, bz[1] + 0.85, 3.3, 7.0, 0, 0.3, jit(rng, ROOF))
    mb.box(bx, by, bz[1] + 0.85, 1.7, 6.6, 0.65, 0, STUCCO, top=False)
    mb.gable_roof(bx, by, bz[1] + 1.5, 1.7, 6.6, 0, 0.3, ROOF, STUCCO)
    for k in range(10):
        y = by - 3.0 + k * 0.66
        mb.arch((bx - 0.85, y), (0, -1), (-1, 0), bz[1] + 1.0, 0.16, 0.3)
        mb.arch((bx + 0.85, y), (0, 1), (1, 0), bz[1] + 1.0, 0.16, 0.3)
    mb.columns((bx - 1.2, by - 3.6), (bx + 1.2, by - 3.6), 6, bz[1], 0.8, 0.05)
    occ.rect(cx, cy, W + 2.6, D + 0.6, 0)
    occ.rect(bx, by, 3.6, 7.6, 0)
    for sgn in (-1, 1):
        trees.append(('cypress', cx + sgn * 1.95, 15.0, z, 0.75))


def harbor_front(T, occ, avenue_occ, rng, mb, trees):
    P = resample(HARBOR, 0.2)
    N = polyline_normals(P)
    mid = len(P) // 2
    test = P[mid] + N[mid] * 2.0
    if T.m(T.sd, test[0], test[1]) < 0:
        N = -N
    s = arclen(P)

    def off(dist):
        return P + N * dist

    Q = off(1.8)
    sv = 1.0
    built = 0
    while sv < s[-1] - 1.2:
        s1 = min(sv + rng.uniform(2.6, 3.4), s[-1] - 1.0)
        a = at_arc(Q, s, sv)
        b = at_arc(Q, s, s1)
        m = (a + b) / 2
        sv = s1 + 0.35
        if not (avenue_occ.free(m[0], m[1]) and avenue_occ.free(a[0], a[1]) and avenue_occ.free(b[0], b[1])):
            continue
        if dist_to_polyline(np.array([m[0]]), np.array([m[1]]), WALL_PATH)[0] < 1.4:
            continue
        if np.linalg.norm(b - a) < 1.2:
            continue
        kind = 'stoa' if m[1] > -3.2 else 'warehouse'
        mm, L, ang = stoa(mb, T, a, b, rng, kind)
        occ.rect(mm[0], mm[1], L + 0.2, 1.4, ang)
        built += 1
    # market stalls & awnings along the harbour head
    awn = [(0.96, 0.93, 0.86), (0.78, 0.36, 0.28), (0.86, 0.72, 0.42), (0.94, 0.90, 0.80), (0.45, 0.52, 0.62)]
    for dist in (0.72, 1.12):
        R = off(dist)
        for k in range(0, len(R), 2):
            x, y = R[k]
            if y < -3.0 or not avenue_occ.free(x, y) or rng.random() < 0.35:
                continue
            if any(abs(x - px) < 0.5 for px in (-2.5, 5.0)) and y > -1:
                continue
            zg = T.hs(x, y)
            a = rng.uniform(0, math.pi)
            sz = rng.uniform(0.28, 0.38)
            mb.box(x, y, zg - 0.1, sz * 0.85, sz * 0.85, 0.26, a, jit(rng, (0.6, 0.45, 0.3)), top=False)
            mb.hip_roof(x, y, zg + 0.16, sz, sz, a, sz * 0.4, awn[rng.integers(len(awn))], 0.03)
    # crates / amphorae on the quays
    for dist in (0.35, 0.5):
        R = off(dist)
        for k in range(0, len(R), 3):
            if rng.random() < 0.45:
                x, y = R[k]
                if not avenue_occ.free(x, y):
                    continue
                zg = T.hs(x, y)
                sz = rng.uniform(0.06, 0.11)
                c = (0.62, 0.32, 0.18) if rng.random() < 0.5 else (0.55, 0.40, 0.25)
                mb.box(x, y, zg - 0.02, sz, sz, sz * rng.uniform(0.8, 1.6), rng.uniform(0, 3), jit(rng, c, 0.1))
    return built


def build_house(mb, rng, T, cx, cy, w, d, ang, hbias=0.0):
    pts = rect_pts(cx, cy, w, d, ang)
    zs = T.h([p[0] for p in pts] + [cx], [p[1] for p in pts] + [cy])
    zmin = float(zs.min())
    zmax = float(zs.max())
    floors = 1 + int(rng.random() < 0.72) + int(rng.random() < 0.22 + hbias)
    fh = 0.27
    h = floors * fh + rng.uniform(0.02, 0.08)
    wall = jit(rng, WALL_COLS[rng.integers(len(WALL_COLS))])
    roof = jit(rng, ROOF_COLS[rng.integers(len(ROOF_COLS))], 0.08)
    zb = zmin - 0.35
    zt = zmax + h
    rt = rng.random()
    flat = rt > 0.9
    mb.box(cx, cy, zb, w, d, zt - zb, ang, wall, lighten(wall, 0.92), top=flat)
    if rt < 0.58:
        mb.hip_roof(cx, cy, zt, w, d, ang, min(w, d) * rng.uniform(0.26, 0.36), roof)
    elif rt < 0.9:
        mb.gable_roof(cx, cy, zt, w, d, ang, min(w, d) * rng.uniform(0.28, 0.38), roof, wall)
    else:
        hx, hy = L2W(cx, cy, ang, rng.uniform(-w / 4, w / 4), rng.uniform(-d / 5, d / 5))
        mb.box(hx, hy, zt, 0.24, 0.24, 0.17, ang, wall)
        mb.hip_roof(hx, hy, zt + 0.17, 0.24, 0.24, ang, 0.1, roof, 0.02)
    for f in range(floors):
        zw = zmax + f * fh + 0.1
        nwin = max(1, int(w / 0.25))
        for k in range(nwin):
            lx = -w / 2 + (k + 0.5) * w / nwin
            mb.window(cx, cy, ang, lx, -d / 2, zw, 0.06, 0.1, True)
            mb.window(cx, cy, ang, lx, d / 2, zw, 0.06, 0.1, False)
    if rng.random() < 0.035:
        tx, ty = L2W(cx, cy, ang, rng.choice([-1, 1]) * (w / 2 - 0.17), rng.choice([-1, 1]) * (d / 2 - 0.17))
        th = h + rng.uniform(0.45, 0.8)
        mb.box(tx, ty, zb, 0.32, 0.32, zmax + th - zb, ang, wall)
        mb.hip_roof(tx, ty, zmax + th, 0.32, 0.32, ang, 0.18, roof, 0.03)
        mb.window(tx, ty, ang, 0, -0.16, zmax + th - 0.22, 0.07, 0.12, True)


def build_city(T, coll, mats, rng_seed=2024):
    rng = np.random.default_rng(rng_seed)
    t0 = time.time()
    occ = Occ(0.2)
    land = points_in_poly(occ.X, occ.Y, COAST_POLY)
    dco = dist_to_polyline(occ.X, occ.Y, COAST_LINE)
    sd = np.where(land, dco, -dco)
    occ.B |= ~points_in_poly(occ.X, occ.Y, WALL_PATH)
    occ.B |= dist_to_polyline(occ.X, occ.Y, WALL_PATH) < 0.95
    occ.B |= sd < 0.8
    occ.B |= dist_to_polyline(occ.X, occ.Y, HARBOR) < 2.45
    avenue_occ = Occ(0.2)
    for pts, wdt in AVENUES:
        occ.line(pts, wdt / 2)
        avenue_occ.line(pts, wdt / 2 + 0.1)
    for g in GATES:
        occ.circle(g[0], g[1], 2.3)

    trees = []
    steam = []
    lm = {}

    def L(name):
        lm[name] = MB()
        return lm[name]

    palace(L("Palace"), T, occ, trees, rng)
    forum(L("Forum_Temple_Basilica"), T, occ, trees, rng)
    colosseum(L("Colosseum"), T, 22.0, 10.5, 5.0, 4.0, 20, 2.0, occ)
    hippodrome(L("Hippodrome"), T, occ, avenue_occ, rng, trees)
    baths(L("Baths_West"), T, -21.5, 10.5, 10, occ, 1.0, steam)
    baths(L("Baths_East"), T, 31.6, 9.0, -90, occ, 0.6, steam)
    rotunda(L("Rotunda"), T, 25.5, -11.5, 180, 1.6, occ, steam)
    theater(L("Theatre"), T, 11.5, 18.0, -90, 3.0, occ)
    mbt = L("Temples")
    temple(mbt, T, -11.5, 17.0, -60, 2.6, 3.6, 0.95, 6, occ)
    tholos(mbt, T, -7.8, 19.6, 0.8, 0.85, occ)
    temple(mbt, T, 12.5, 6.5, -90, 2.0, 2.8, 0.75, 4, occ)
    temple(mbt, T, -17.0, 0.0, -80, 2.0, 2.8, 0.75, 4, occ)
    temple(mbt, T, 6.5, 23.0, -90, 1.9, 2.6, 0.7, 4, occ)
    tholos(mbt, T, -27.5, -3.5, 0.7, 0.7, occ)
    temple(mbt, T, 31.5, -6.0, 180, 2.0, 2.9, 0.75, 4, occ)
    # aqueduct castellum
    mc = L("Castellum")
    cz = fp_ground(T, -9.0, 25.2, 1.3, 1.0, 0)
    mc.box(-9.0, 25.2, cz[0] - 0.4, 1.3, 1.0, cz[1] + 0.95 - (cz[0] - 0.4), 0.3, STUCCO, top=False)
    mc.hip_roof(-9.0, 25.2, cz[1] + 0.95, 1.3, 1.0, 0.3, 0.3, ROOF)
    occ.rect(-9.0, 25.2, 1.6, 1.4, 0.3)
    # harbour front buildings
    hf = L("Harbour_Front")
    n_hf = harbor_front(T, occ, avenue_occ, rng, hf, trees)
    # avenue paving
    pav = L("Avenue_Paving")
    for pts, wdt in [AVENUES[i] for i in PAVED_AVENUES]:
        ribbon(pav, T, pts, wdt * 0.85, PAVE, 0.4, 0.05)
        Pp = resample(pts, 1.3)
        Np = polyline_normals(Pp)
        for k in range(1, len(Pp) - 1):
            if rng.random() < 0.8:
                for sgn in (-1, 1):
                    q = Pp[k] + Np[k] * sgn * wdt * 0.46
                    trees.append(('cypress', q[0], q[1], T.hs(*q), rng.uniform(0.55, 0.75)))

    # houses in concentric rings around the harbour
    mbh = MB()
    C = (2.0, -8.0)
    widths = np.array([0.55, 0.65, 0.75, 0.85, 0.95, 1.1, 1.3])
    wp = np.array([0.12, 0.18, 0.2, 0.18, 0.14, 0.11, 0.07])
    wp = wp / wp.sum()
    r = 3.5
    ring = 0
    count = 0
    while r < 52:
        depth = 0.70 + rng.uniform(-0.04, 0.08)
        rc = r + depth / 2
        circ = 2 * math.pi * rc
        sv = rng.uniform(0, 2.0)
        while sv < circ:
            w = float(rng.choice(widths, p=wp))
            th = (sv + w / 2) / rc
            sv += w + (0.24 if rng.random() < 0.09 else 0.03)
            cx = C[0] + rc * math.cos(th)
            cy = C[1] + rc * math.sin(th)
            ang = th + math.pi / 2
            ok = True
            for lx, ly in ((0, 0), (-w / 2 + 0.03, -depth / 2 + 0.03), (w / 2 - 0.03, -depth / 2 + 0.03),
                           (w / 2 - 0.03, depth / 2 - 0.03), (-w / 2 + 0.03, depth / 2 - 0.03)):
                px, py = L2W(cx, cy, ang, lx, ly)
                if not occ.free(px, py):
                    ok = False
                    break
            if not ok:
                continue
            if rng.random() < 0.035:
                trees.append(('pine' if rng.random() < 0.5 else 'cypress', cx, cy, T.hs(cx, cy), rng.uniform(0.6, 0.9)))
                continue
            dforum = math.hypot(cx - 1.5, cy - 11.0)
            build_house(mbh, rng, T, cx, cy, w, depth, ang, 0.18 * math.exp(-dforum / 14.0))
            count += 1
        r += depth + (0.3 if ring % 5 == 4 else 0.025)
        ring += 1

    objs = {}
    mbh.to_object("CAP_Houses", coll['city'], [mats['painted']])
    for name, b in lm.items():
        b.to_object("CAP_LM_" + name, coll['landmarks'], [mats['painted']])
    # city trees
    tm = MB()
    plant_trees(tm, trees, rng)
    tm.to_object("CAP_CityTrees", coll['city'], [mats['painted']])
    # steam plumes
    smat = mats['steam']
    for i, (x, y, z, sc) in enumerate(steam + [(-3.5, 13.5, 2.0, 0.6), (18.0, 20.5, 2.2, 0.6)]):
        me = bpy.data.meshes.new("CAP_SteamMesh_%d" % i)
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(smat)
        ob = bpy.data.objects.new("CAP_Steam_%d" % i, me)
        ob.location = (x + 0.6 * sc, y + 0.4 * sc, z + 2.2 * sc)
        ob.scale = (0.9 * sc, 0.9 * sc, 2.6 * sc)
        ob.rotation_euler = (0.25, -0.2, 0.0)
        coll['city'].objects.link(ob)
    return {"houses": count, "harbour_front": n_hf, "city_trees": len(trees), "secs": round(time.time() - t0, 2)}


def plant_trees(mb, trees, rng):
    protos = {'round': proto_round(), 'cypress': proto_cypress(), 'pine': proto_pine()}
    groups = {}
    for kind, x, y, z, s in trees:
        groups.setdefault(kind, []).append((x, y, z, s))
    for kind, items in groups.items():
        pos, scl, rot, cols = [], [], [], []
        for x, y, z, s in items:
            if kind == 'cypress':
                pos.append((x, y, z - 0.05))
                scl.append((s * 0.9, s * 0.9, s * rng.uniform(1.0, 1.35)))
                cols.append(jit(rng, CYPRESS, 0.15))
            elif kind == 'pine':
                pos.append((x, y, z - 0.05))
                scl.append((s * 0.8, s * 0.8, s * 0.9))
                cols.append(jit(rng, PINE, 0.15))
            elif kind == 'olive':
                pos.append((x, y, z + 0.12 * s))
                scl.append((0.2 * s, 0.2 * s, 0.17 * s))
                cols.append(jit(rng, OLIVE, 0.1))
            else:
                pos.append((x, y, z + 0.22 * s))
                scl.append((0.32 * s, 0.32 * s, 0.3 * s))
                cols.append(jit(rng, OAK, 0.22))
            rot.append(rng.uniform(0, 6.28))
        scatter(mb, protos['round' if kind in ('olive', 'round') else kind], pos, scl, rot, cols)


def ribbon(mb, T, pts, width, col, step=0.5, lift=0.05, min_z=-99.0):
    P = resample(pts, step)
    N = polyline_normals(P)
    Lf = P + N * width / 2
    Rt = P - N * width / 2
    zl = T.h(Lf[:, 0], Lf[:, 1]) + lift
    zr = T.h(Rt[:, 0], Rt[:, 1]) + lift
    zc = T.h(P[:, 0], P[:, 1]) + lift
    zl = np.maximum(zl, zc)
    zr = np.maximum(zr, zc)
    for i in range(len(P) - 1):
        if min(zc[i], zc[i + 1]) < min_z:
            continue
        mb.poly([(Rt[i][0], Rt[i][1], zr[i]), (Rt[i + 1][0], Rt[i + 1][1], zr[i + 1]),
                 (Lf[i + 1][0], Lf[i + 1][1], zl[i + 1]), (Lf[i][0], Lf[i][1], zl[i])], col)


# =============================================================================
# Stage: countryside (aqueduct, roads, bridge, trees, villas, rocks)
# =============================================================================
def arch_unit(mb, p, u, n, half, q, r, zb, zs, zd, th, col):
    loc = [(-q, zb), (q, zb), (q, zs)]
    for k in range(1, 7):
        a = math.pi - (math.pi / 2) * k / 6
        loc.append((q + r + r * math.cos(a), zs + r * math.sin(a)))
    loc += [(half, zd), (-half, zd), (-half, zs + r)]
    for k in range(1, 7):
        a = math.pi / 2 - (math.pi / 2) * k / 6
        loc.append((-q - r + r * math.cos(a), zs + r * math.sin(a)))
    ring = [(p[0] + u[0] * s - n[0] * th / 2, p[1] + u[1] * s - n[1] * th / 2, z) for s, z in loc]
    mb.extrude(ring, (n[0] * th, n[1] * th, 0.0), col, col, top=True)


def aqueduct(mb, T, path, z_start, z_end, step=1.15, th=0.42, col=(0.80, 0.70, 0.55)):
    P = resample(path, step)
    s = arclen(P)
    tops = z_start + (z_end - z_start) * s / s[-1]
    deck = 0.32
    for i in range(len(P)):
        d = P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
        u = d / np.linalg.norm(d)
        n = np.array([-u[1], u[0]])
        if 0 < i < len(P) - 1:
            half = (np.linalg.norm(P[i + 1] - P[i]) + np.linalg.norm(P[i] - P[i - 1])) / 4
        else:
            half = step / 2
        zg = T.hs(*P[i])
        zt = tops[i]
        zd = zt - deck
        if zd - zg < 0.5:
            mb.box(P[i][0], P[i][1], zg - 0.3, half * 2 + 0.02, th, zd - zg + 0.3, math.atan2(u[1], u[0]), col, top=False)
            continue
        r = half - 0.15
        zs = zd - r - 0.12
        if zs < zg + 0.25:
            r = max(0.12, zd - 0.12 - (zg + 0.25))
            zs = zd - r - 0.12
        q = half - r
        if zs - zg > 1.9:                                   # two tiers over deep ground
            zs2 = zg + (zs - zg) * 0.42
            zl = zs2 + r + 0.12
            arch_unit(mb, P[i], u, n, half, q, r, zg - 0.3, zs2, zl, th + 0.08, col)
            arch_unit(mb, P[i], u, n, half, q, r, zl, zs, zd, th, col)
        else:
            arch_unit(mb, P[i], u, n, half, q, r, zg - 0.3, zs, zd, th, col)
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        m = (a + b) / 2
        d = b - a
        L = float(np.linalg.norm(d))
        ang = math.atan2(d[1], d[0])
        zt = (tops[i] + tops[i + 1]) / 2
        mb.box(m[0], m[1], zt - deck, L + 0.02, th + 0.1, deck, ang, STONE_D, STONE_TOP)
        nn = np.array([-d[1], d[0]]) / L
        for sgn in (-1, 1):
            q = m + nn * sgn * (th / 2 - 0.02)
            mb.box(q[0], q[1], zt, L + 0.02, 0.07, 0.09, ang, STONE_D, STONE_TOP)
        mb.box(m[0], m[1], zt, L + 0.02, th - 0.2, 0.05, ang, POOL, (0.30, 0.55, 0.62))


def villa(mb, T, x, y, rng, trees):
    ang = rng.uniform(0, math.pi)
    w, d = rng.uniform(1.1, 1.6), rng.uniform(0.8, 1.1)
    build_house(mb, rng, T, x, y, w, d, ang, 0.0)
    if rng.random() < 0.75:
        p = L2W(x, y, ang, w / 2 + 0.35, d / 2 + 0.1)
        build_house(mb, rng, T, p[0], p[1], 0.6, rng.uniform(0.9, 1.4), ang, -0.3)
    if rng.random() < 0.5:
        p = L2W(x, y, ang, -w / 2 - 0.2, -0.1)
        build_house(mb, rng, T, p[0], p[1], 0.5, 0.6, ang, -0.5)
    for k in range(rng.integers(2, 5)):
        p = L2W(x, y, ang, rng.uniform(-1.5, 1.5), rng.choice([-1, 1]) * rng.uniform(0.9, 1.4))
        trees.append(('cypress' if rng.random() < 0.7 else 'pine', p[0], p[1], T.hs(*p), rng.uniform(0.6, 0.9)))


def build_countryside(T, coll, mats, seed=77):
    rng = np.random.default_rng(seed)
    t0 = time.time()
    # aqueduct
    am = MB()
    aqueduct(am, T, AQUEDUCT, 5.6, 3.7)
    am.to_object("CAP_Aqueduct", coll, [mats['painted']])
    # roads & bridge
    rm = MB()
    ROAD_C = (0.72, 0.60, 0.42)
    for pts in ROADS:
        ribbon(rm, T, pts, 0.55, ROAD_C, 0.5, 0.06, min_z=0.15)
    ribbon(rm, T, [(-35.5, 6.5), (-36.3, 6.8)], 0.55, ROAD_C)
    # bridge over the river on the west road
    bp = np.array([(-41.8, 10.0), (-45.6, 12.3)])
    d = bp[1] - bp[0]
    u = d / np.linalg.norm(d)
    n = np.array([-u[1], u[0]])
    zdeck = max(T.hs(*bp[0]), T.hs(*bp[1])) + 0.15
    Pb = resample(bp, 1.0)
    for i in range(len(Pb)):
        zg = T.hs(*Pb[i])
        half = 0.5 * np.linalg.norm(d) / (len(Pb) - 1)
        zd = zdeck - 0.15
        r = min(half - 0.12, max(0.12, zd - zg - 0.3))
        zs = zd - r - 0.08
        arch_unit(rm, Pb[i], u, n, half, half - r, r, zg - 0.4, zs, zd, 0.6, STONE)
    m = bp.mean(axis=0)
    rm.box(m[0], m[1], zdeck - 0.15, float(np.linalg.norm(d)) + 0.6, 0.66, 0.15, math.atan2(u[1], u[0]), STONE_D, ROAD_C)
    rm.to_object("CAP_Roads_Bridge", coll, [mats['painted']])

    # countryside occupancy
    occ = Occ(0.25)
    occ.B |= points_in_poly(occ.X, occ.Y, WALL_PATH) | (dist_to_polyline(occ.X, occ.Y, WALL_PATH) < 1.3)
    land = points_in_poly(occ.X, occ.Y, COAST_POLY)
    dco = dist_to_polyline(occ.X, occ.Y, COAST_LINE)
    occ.B |= (~land) | (dco < 1.0)
    for pts in ROADS:
        occ.line(pts, 0.55)
    occ.line(AQUEDUCT, 0.55)
    occ.line(RIVER, 1.3)

    trees = []
    vm = MB()
    # villas & farmsteads
    placed = 0
    tries = 0
    while placed < 26 and tries < 4000:
        tries += 1
        x, y = rng.uniform(-48, 48), rng.uniform(-20, 47)
        if T.m(T.farm, x, y) < 0.8 or not occ.free(x, y):
            continue
        ok = all(occ.free(x + dx, y + dy) for dx in (-1.6, 1.6) for dy in (-1.6, 1.6))
        if not ok:
            continue
        villa(vm, T, x, y, rng, trees)
        occ.circle(x, y, 2.6)
        placed += 1
    # olive groves & vineyards
    groves = 0
    vines = 0
    tries = 0
    while (groves < 16 or vines < 10) and tries < 6000:
        tries += 1
        x, y = rng.uniform(-48, 48), rng.uniform(-18, 46)
        if T.m(T.farm, x, y) < 0.85:
            continue
        w, d = rng.uniform(2.5, 5.0), rng.uniform(2.0, 3.8)
        ang = rng.uniform(-0.4, 0.4) + (math.pi / 2 if rng.random() < 0.5 else 0)
        corners = rect_pts(x, y, w, d, ang)
        if not all(occ.free(px, py) and T.m(T.farm, px, py) > 0.6 for px, py in corners + [(x, y)]):
            continue
        if groves < 16 and (vines >= 10 or rng.random() < 0.6):
            for lx in np.arange(-w / 2 + 0.25, w / 2 - 0.1, 0.55):
                for ly in np.arange(-d / 2 + 0.25, d / 2 - 0.1, 0.55):
                    px, py = L2W(x, y, ang, lx + rng.uniform(-0.05, 0.05), ly + rng.uniform(-0.05, 0.05))
                    trees.append(('olive', px, py, T.hs(px, py), rng.uniform(0.85, 1.15)))
            groves += 1
        else:
            VC = jit(rng, (0.33, 0.42, 0.17), 0.1)
            for ly in np.arange(-d / 2 + 0.15, d / 2, 0.3):
                p = L2W(x, y, ang, 0, ly)
                zg = fp_ground(T, p[0], p[1], w, 0.1, ang)
                vm.box(p[0], p[1], zg[0] - 0.05, w, 0.1, zg[1] + 0.12 - (zg[0] - 0.05), ang, VC)
            vines += 1
        occ.rect(x, y, w, d, ang, 0.3)
    # cypress avenues along the roads
    for pts in ROADS:
        Pp = resample(pts, 1.2)
        Np = polyline_normals(Pp)
        for k in range(len(Pp)):
            for sgn in (-1, 1):
                if rng.random() < 0.55:
                    q = Pp[k] + Np[k] * sgn * 0.62
                    if T.hs(*q) > 0.3 and T.m(T.dr, *q) > 1.3:
                        trees.append(('cypress', q[0], q[1], T.hs(*q), rng.uniform(0.6, 0.9)))
    # forests on hills + scattered field trees
    nf = 0
    for _ in range(26000):
        x, y = rng.uniform(-49.7, 49.7), rng.uniform(-30, 49.7)
        fo = float(T.m(T.forest, x, y))
        fa = float(T.m(T.farm, x, y))
        p = fo * 0.85 + fa * 0.012
        if rng.random() > p or not occ.free(x, y):
            continue
        z = T.hs(x, y)
        gx = T.hs(x + 0.3, y) - T.hs(x - 0.3, y)
        gy = T.hs(x, y + 0.3) - T.hs(x, y - 0.3)
        if math.hypot(gx, gy) / 0.6 > 1.4 or z < 0.3 or z > 9.0 + 1.5 * rng.random():
            continue
        r = rng.random()
        kind = 'round' if r < 0.68 else ('cypress' if r < 0.84 else 'pine')
        trees.append((kind, x, y, z, rng.uniform(0.75, 1.35)))
        nf += 1
    # river-bank trees
    Rv = resample(RIVER, 0.9)
    Nv = polyline_normals(Rv)
    for k in range(len(Rv)):
        for sgn in (-1, 1):
            if rng.random() < 0.5:
                q = Rv[k] + Nv[k] * sgn * rng.uniform(1.1, 1.8)
                z = T.hs(*q)
                if 0.1 < z < 6 and occ.free(*q):
                    trees.append(('round', q[0], q[1], z, rng.uniform(0.6, 0.9)))
    vm.to_object("CAP_Villas_Vineyards", coll, [mats['painted']])
    tm = MB()
    plant_trees(tm, trees, rng)
    tm.to_object("CAP_Countryside_Trees", coll, [mats['painted']])
    # boulders at the cliff foot
    bm_ = MB()
    rp = proto_round(6)
    pos, scl, rot, cols = [], [], [], []
    for _ in range(4000):
        x, y = rng.uniform(-42, -18), rng.uniform(-30, -17)
        sdv = float(T.m(T.sd, x, y))
        if -1.6 < sdv < 0.25:
            s = rng.uniform(0.15, 0.45)
            pos.append((x, y, rng.uniform(-0.25, 0.05)))
            scl.append((s, s * rng.uniform(0.7, 1.1), s * 0.7))
            rot.append(rng.uniform(0, 6.28))
            cols.append(jit(rng, (0.66, 0.57, 0.45), 0.12))
        if len(pos) > 160:
            break
    scatter(bm_, rp, pos, scl, rot, cols, smooth=False)
    bm_.to_object("CAP_Rocks", coll, [mats['painted']])
    return {"villas": placed, "groves": groves, "vineyards": vines, "trees": len(trees), "forest": nf,
            "secs": round(time.time() - t0, 2)}


# =============================================================================
# Stage: ships
# =============================================================================
def hull(mb, L, B, D, F, bow_rise, stern_rise, col_hull, col_deck, col_band, nx=16):
    secs = []
    for i in range(nx + 1):
        t = i / nx
        x = -L / 2 + t * L
        fb = math.sin(math.pi * (0.03 + 0.94 * t))
        fb = fb ** (0.45 if t < 0.5 else 0.85)
        bw = B / 2 * max(fb, 0.05)
        dep = D * max(math.sin(math.pi * (0.02 + 0.96 * t)) ** 0.4, 0.15)
        sh = F + bow_rise * t ** 3.5 + stern_rise * (1 - t) ** 3.5
        secs.append(mb.vid([(x, -bw, sh), (x, -bw * 0.97, 0.0), (x, -bw * 0.7, -dep * 0.7), (x, 0.0, -dep),
                            (x, bw * 0.7, -dep * 0.7), (x, bw * 0.97, 0.0), (x, bw, sh)]))
    for i in range(nx):
        a, b = secs[i], secs[i + 1]
        for k in range(6):
            col = col_band if k in (0, 5) else col_hull
            mb.face((a + k, a + k + 1, b + k + 1, b + k), col)
        mb.face((a + 0, b + 0, b + 6, a + 6), col_deck)
    mb.face([secs[0] + k for k in reversed(range(7))], col_hull)
    mb.face([secs[-1] + k for k in range(7)], col_hull)


def square_sail(mb, x, z_top, z_bot, w_top, w_bot, bulge, col, nu=5, nv=4):
    grid = []
    for j in range(nv + 1):
        v = j / nv
        z = z_top + (z_bot - z_top) * v
        w = w_top + (w_bot - w_top) * v
        row = []
        for i in range(nu + 1):
            u = i / nu
            y = -w / 2 + w * u
            row.append((x + bulge * math.sin(math.pi * u) * (0.35 + 0.65 * math.sin(math.pi * min(1.0, v * 0.9 + 0.1))), y, z))
        grid.append(mb.vid(row))
    for j in range(nv):
        for i in range(nu):
            mb.face((grid[j] + i, grid[j + 1] + i, grid[j + 1] + i + 1, grid[j] + i + 1), col)


def ship_mesh(kind):
    mb = MB()
    HULL = (0.30, 0.18, 0.10)
    DECK = (0.58, 0.43, 0.27)
    if kind == 'galley':
        L, B = 3.2, 0.56
        hull(mb, L, B, 0.13, 0.17, 0.10, 0.42, HULL, DECK, (0.55, 0.12, 0.08))
        mb.beam((L / 2 - 0.1, 0, 0.03), (L / 2 + 0.3, 0, 0.0), 0.06, (0.62, 0.48, 0.22))
        pts = [(-L / 2 + 0.02, 0, 0.59)]
        for k in range(1, 6):
            a = math.pi - k * math.pi / 5 * 0.9
            pts.append((-L / 2 + 0.17 + 0.15 * math.cos(a), 0, 0.59 + 0.15 * math.sin(a)))
        for p0, p1 in zip(pts[:-1], pts[1:]):
            mb.beam(p0, p1, 0.05, HULL)
        mb.beam((0.1, 0, 0.12), (0.1, 0, 1.5), 0.04, WOOD_D)
        mb.beam((0.13, -0.66, 1.4), (0.13, 0.66, 1.4), 0.03, WOOD_D)
        square_sail(mb, 0.15, 1.38, 0.55, 1.3, 1.15, 0.14, SAIL_RED)
        for k in range(13):
            x = -1.05 + k * 0.17
            for sgn in (-1, 1):
                mb.beam((x, sgn * 0.27, 0.12), (x - 0.12, sgn * 0.85, -0.02), 0.018, WOOD)
        for px, py in ((-1.05, -0.17), (-1.05, 0.17), (-1.45, -0.15), (-1.45, 0.15)):
            mb.beam((px, py, 0.17), (px, py, 0.46), 0.02, WOOD_D)
        mb.box(-1.25, 0, 0.46, 0.5, 0.42, 0.03, 0, SAIL, SAIL)
        for sgn in (-1, 1):
            mb.beam((-1.45, sgn * 0.28, 0.35), (-1.7, sgn * 0.33, -0.08), 0.03, WOOD_D)
        mb.beam((0.1, 0, 1.5), (L / 2, 0, 0.3), 0.008, WOOD_D)
        mb.beam((0.1, 0, 1.5), (-L / 2 + 0.2, 0, 0.6), 0.008, WOOD_D)
        mb.poly_facing([(L / 2 - 0.12, -0.19, 0.12), (L / 2 - 0.02, -0.12, 0.12), (L / 2 - 0.07, -0.16, 0.18)], (0, -1, 0), (0.9, 0.85, 0.8))
        mb.poly_facing([(L / 2 - 0.12, 0.19, 0.12), (L / 2 - 0.02, 0.12, 0.12), (L / 2 - 0.07, 0.16, 0.18)], (0, 1, 0), (0.9, 0.85, 0.8))
    elif kind in ('merchant', 'merchant2', 'moored', 'moored2'):
        big = kind in ('merchant2', 'moored2')
        L, B = (2.2, 0.7) if big else (1.7, 0.6)
        band = (0.35, 0.42, 0.55) if big else (0.62, 0.52, 0.30)
        hull(mb, L, B, 0.17, 0.2, 0.15, 0.26, (0.34, 0.21, 0.12), DECK, band)
        mb.box(-L / 2 + 0.38, 0, 0.18, 0.4, B * 0.6, 0.18, 0, (0.55, 0.38, 0.22))
        mb.gable_roof(-L / 2 + 0.38, 0, 0.36, 0.4, B * 0.6, 0, 0.08, (0.6, 0.3, 0.18), (0.55, 0.38, 0.22), 0.02, 'x')
        mh = 1.55 if big else 1.3
        mb.beam((0.05, 0, 0.15), (0.05, 0, mh), 0.04, WOOD_D)
        if kind.startswith('merchant'):
            yw = 1.1 if big else 0.95
            mb.beam((0.08, -yw / 2 - 0.05, mh - 0.1), (0.08, yw / 2 + 0.05, mh - 0.1), 0.025, WOOD_D)
            square_sail(mb, 0.1, mh - 0.12, 0.45, yw, yw * 0.9, 0.12, SAIL)
            if big:
                mb.beam((L / 2 - 0.35, 0, 0.25), (L / 2 + 0.05, 0, 0.85), 0.03, WOOD_D)
                square_sail(mb, L / 2 - 0.05, 0.78, 0.42, 0.4, 0.36, 0.06, SAIL, 3, 2)
        else:
            yw = 1.0 if big else 0.85
            mb.beam((0.08, -yw / 2, mh - 0.25), (0.08, yw / 2, mh - 0.25), 0.05, SAIL)
            mb.beam((0.08, -yw / 2, mh - 0.25), (0.08, yw / 2, mh - 0.25), 0.07, (0.85, 0.78, 0.65))
        mb.beam((0.05, 0, mh), (L / 2, 0, 0.3), 0.008, WOOD_D)
        mb.beam((0.05, 0, mh), (-L / 2 + 0.1, 0, 0.42), 0.008, WOOD_D)
        for sgn in (-1, 1):
            mb.beam((0.05, 0, mh - 0.1), (0.05, sgn * B * 0.5, 0.2), 0.006, WOOD_D)
            mb.beam((-L / 2 + 0.15, sgn * 0.2, 0.35), (-L / 2 - 0.05, sgn * 0.26, -0.08), 0.03, WOOD_D)
        for k in range(4):
            mb.cyl(0.4 + k * 0.08 - 0.1, (k % 2 - 0.5) * 0.15, 0.2, 0.035, 0.07, 6, (0.66, 0.36, 0.22))
    elif kind == 'boat':
        hull(mb, 0.5, 0.17, 0.05, 0.06, 0.03, 0.03, (0.40, 0.26, 0.15), DECK, (0.3, 0.38, 0.5))
        for sgn in (-1, 1):
            mb.beam((0.0, sgn * 0.08, 0.06), (-0.1, sgn * 0.3, -0.01), 0.012, WOOD)
    elif kind == 'fisher':
        hull(mb, 0.78, 0.25, 0.07, 0.08, 0.06, 0.05, (0.38, 0.25, 0.14), DECK, (0.75, 0.7, 0.6))
        mb.beam((0.12, 0, 0.06), (0.12, 0, 0.6), 0.02, WOOD_D)
        mb.beam((-0.3, 0.02, 0.18), (0.45, 0.02, 0.78), 0.015, WOOD_D)
        mb.poly([(-0.27, 0.03, 0.2), (0.42, 0.03, 0.75), (0.25, 0.03, 0.1)], SAIL)
    return mb.to_mesh("CAP_Ship_" + kind)


SHIP_SCALE = 1.35
SHIPS = [
    # (kind, x, y, heading_deg, scale)
    ('galley', -21.5, -33.5, 20, 1.0), ('galley', 4.5, -15.5, 92, 0.85), ('galley', 21.0, -27.5, 160, 0.9),
    ('merchant', -6.5, -9.0, 60, 0.85), ('merchant2', 9.6, -11.5, 120, 0.85), ('merchant', -1.0, -6.0, 100, 0.85),
    ('merchant', 6.2, -5.6, 80, 0.85), ('merchant2', -14.0, -28.5, 40, 1.0), ('merchant', 36.0, -31.0, 140, 1.0),
    ('merchant', -20.0, -32.5, 70, 1.0), ('merchant2', 14.0, -32.0, 110, 1.0), ('merchant', 2.4, -29.0, 88, 1.0),
    ('merchant2', 30.0, -29.0, 155, 1.0), ('merchant', -8.0, -40.0, 60, 1.0), ('merchant2', 40.0, -36.0, 125, 1.0),
    ('merchant', 24.0, -43.0, 95, 1.0), ('merchant', -44.0, -34.0, 40, 0.95), ('merchant2', 46.0, -18.0, 200, 1.0),
    ('merchant', 2.5, -11.5, 95, 0.9), ('merchant2', -4.0, -18.0, 75, 0.9), ('merchant', 8.5, -20.5, 105, 0.9),
    # moored at piers
    ('moored', -10.6, -11.5, -7, 0.9), ('moored2', -10.4, -9.7, 173, 0.85), ('moored', -9.3, -5.95, -12, 0.9),
    ('moored', -9.1, -4.15, 168, 0.85), ('moored2', 13.9, -15.45, 188, 0.85), ('moored', 13.9, -13.3, 8, 0.9),
    ('moored2', 13.2, -9.1, 189, 0.85), ('moored', 13.4, -7.2, 9, 0.9), ('moored', -3.35, -1.3, -95, 0.85),
    ('moored', -1.95, -1.5, 85, 0.85), ('moored2', 4.45, -0.7, -92, 0.8), ('moored', 6.0, -0.5, 88, 0.85),
    ('moored', -12.6, -15.2, 78, 0.9), ('galley', 11.8, -4.4, 125, 0.7), ('moored2', 9.0, -1.3, 173, 0.85),
    ('moored', -8.5, -1.5, 30, 0.85),
    # fishing boats & rowboats
    ('fisher', -30.0, -31.0, 30, 1.0), ('fisher', -46.0, -28.0, 70, 1.0), ('fisher', 36.0, -23.0, 140, 1.0),
    ('fisher', 46.5, -6.0, 100, 1.0), ('fisher', 18.0, -38.0, 50, 1.0), ('fisher', -14.0, -45.0, 10, 1.0),
    ('fisher', 33.0, -40.0, 75, 1.0), ('fisher', -37.0, -44.0, 120, 1.0), ('fisher', 47.0, 8.0, 80, 1.0),
    ('fisher', 0.0, -36.0, 160, 1.0),
]


def build_ships(T, coll, mats, seed=5):
    rng = np.random.default_rng(seed)
    meshes = {}
    for kind in ('galley', 'merchant', 'merchant2', 'moored', 'moored2', 'boat', 'fisher'):
        me = ship_mesh(kind)
        me.materials.append(mats['painted'])
        meshes[kind] = me
    placements = list(SHIPS)
    # rowboats scattered inside the harbour and along the coast
    tries = 0
    boats = 0
    while boats < 26 and tries < 3000:
        tries += 1
        x, y = rng.uniform(-12, 16), rng.uniform(-22, 0.5)
        if T.hs(x, y) > -0.3 or dist_to_polyline(np.array([x]), np.array([y]), HARBOR)[0] < 0.6:
            continue
        if any(math.hypot(x - p[1], y - p[2]) < 1.3 for p in placements):
            continue
        if any(dist_to_polyline(np.array([x]), np.array([y]), [a, b])[0] < 0.6 for a, b in PIERS):
            continue
        if any(dist_to_polyline(np.array([x]), np.array([y]), m)[0] < 1.2 for m in (W_MOLE, E_MOLE)):
            continue
        placements.append(('boat', x, y, rng.uniform(0, 360), rng.uniform(0.9, 1.1)))
        boats += 1
    for i, (kind, x, y, hd, sc) in enumerate(placements):
        ob = bpy.data.objects.new("CAP_Ship_%02d_%s" % (i, kind), meshes[kind])
        ob.location = (x, y, 0.0)
        ob.rotation_euler = (0.0, 0.0, math.radians(hd))
        sc = sc * (SHIP_SCALE if kind != 'boat' else 1.15)
        ob.scale = (sc, sc, sc)
        coll.objects.link(ob)
    return {"ships": len(placements), "boats": boats}


# =============================================================================
# Stage: lighting, cameras, render settings
# =============================================================================
def look_at(ob, target):
    from mathutils import Vector
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def build_scene(coll, lights_pts, fire_obj=None):
    from mathutils import Vector
    scene = bpy.context.scene
    el, az = math.radians(13.0), math.radians(-14.0)
    sun_dir = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    ld = bpy.data.lights.new("CAP_Sun", 'SUN')
    ld.energy = 4.2
    ld.color = (1.0, 0.74, 0.52)
    ld.angle = math.radians(1.2)
    sun = bpy.data.objects.new("CAP_Sun", ld)
    sun.rotation_euler = (-sun_dir).to_track_quat('-Z', 'Y').to_euler()
    coll.objects.link(sun)
    for i, (x, y, z) in enumerate(lights_pts):
        pl = bpy.data.lights.new("CAP_LighthouseFire_%d" % i, 'POINT')
        pl.energy = 60.0
        pl.color = (1.0, 0.55, 0.2)
        pl.shadow_soft_size = 0.15
        po = bpy.data.objects.new("CAP_LighthouseFire_%d" % i, pl)
        po.location = (x, y, z + 0.1)
        coll.objects.link(po)
    setup_world(sun_dir)
    # hero camera (matches the painting's view from the sea)
    cd = bpy.data.cameras.new("CAP_Cam_Hero")
    cd.lens = 35
    cd.clip_start = 0.5
    cd.clip_end = 1000
    cam = bpy.data.objects.new("CAP_Cam_Hero", cd)
    cam.location = (-2.0, -92.0, 40.0)
    coll.objects.link(cam)
    look_at(cam, (3.0, 2.0, 1.5))
    # orthographic map camera
    cm = bpy.data.cameras.new("CAP_Cam_TopMap")
    cm.type = 'ORTHO'
    cm.ortho_scale = 100.0
    cm.clip_end = 500
    tcam = bpy.data.objects.new("CAP_Cam_TopMap", cm)
    tcam.location = (0, 0, 120)
    coll.objects.link(tcam)
    # close-up camera over the harbour
    cc = bpy.data.cameras.new("CAP_Cam_Harbour")
    cc.lens = 40
    cc.clip_start = 0.1
    ccam = bpy.data.objects.new("CAP_Cam_Harbour", cc)
    ccam.location = (-14.0, -40.0, 12.0)
    coll.objects.link(ccam)
    look_at(ccam, (2.0, -6.0, 1.0))
    for name, loc, tgt, lens in (("CAP_Cam_Palace", (-12, -36, 10), (-31, -17, 4.5), 35),
                                 ("CAP_Cam_Countryside", (20, -10, 22), (36, 28, 2), 30),
                                 ("CAP_Cam_Hippodrome", (6.5, -15.5, 8.5), (23.0, -0.8, 0.6), 30)):
        cdx = bpy.data.cameras.new(name)
        cdx.lens = lens
        cdx.clip_start = 0.1
        ox = bpy.data.objects.new(name, cdx)
        ox.location = loc
        coll.objects.link(ox)
        look_at(ox, tgt)
    scene.camera = cam
    r = scene.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y = 1600, 800
    r.resolution_percentage = 100
    ee = scene.eevee
    for k, v in (("taa_render_samples", 64), ("use_raytracing", True), ("use_shadows", True),
                 ("shadow_resolution_scale", 1.0), ("use_fast_gi", True), ("volumetric_end", 200.0),
                 ("volumetric_tile_size", '4')):
        try:
            setattr(ee, k, v)
        except Exception:
            pass
    try:
        scene.view_settings.view_transform = 'AgX'
        for look in ('AgX - Medium High Contrast', 'Medium High Contrast', 'AgX - Base Contrast'):
            try:
                scene.view_settings.look = look
                break
            except Exception:
                pass
    except Exception:
        pass
    scene.unit_settings.system = 'METRIC'
    return cam


# =============================================================================
# Orchestration
# =============================================================================
def build_all(stages=("terrain", "walls", "city", "countryside", "ships", "scene"), remove_defaults=True):
    t0 = time.time()
    stats = {}
    if remove_defaults:
        stats["removed_defaults"] = remove_factory_defaults()
    clear_previous()
    root = bpy.data.collections.new(ROOT_NAME)
    bpy.context.scene.collection.children.link(root)
    coll = {
        'terrain': new_coll("Terrain & Sea", root),
        'walls': new_coll("Walls & Harbour", root),
        'landmarks': new_coll("Landmarks", root),
        'city': new_coll("City", root),
        'country': new_coll("Countryside", root),
        'ships': new_coll("Ships", root),
        'scene': new_coll("Lights & Cameras", root),
    }
    haze_group()
    mats = {'painted': mat_painted(), 'terrain': mat_terrain(), 'water': mat_water(),
            'fire': mat_fire(), 'steam': mat_steam()}
    T = Terrain()
    stats['terrain_secs'] = round(time.time() - t0, 2)
    fire = MB()
    lights = []
    if "terrain" in stages:
        build_terrain(T, coll['terrain'], mats)
    if "walls" in stages:
        build_walls(T, coll['walls'], mats, fire, lights)
        fob = fire.to_object("CAP_LighthouseFlames", coll['walls'], [mats['fire']])
    if "city" in stages:
        stats['city'] = build_city(T, coll, mats)
    if "countryside" in stages:
        stats['country'] = build_countryside(T, coll['country'], mats)
    if "ships" in stages:
        stats['ships'] = build_ships(T, coll['ships'], mats)
    if "scene" in stages:
        build_scene(coll['scene'], lights)
    # stats
    tri = 0
    for o in root.all_objects:
        if o.type == 'MESH':
            tri += sum(len(p.vertices) - 2 for p in o.data.polygons)
    stats['objects'] = len(root.all_objects)
    stats['approx_tris'] = tri
    stats['total_secs'] = round(time.time() - t0, 2)
    return stats


def render(path, camera="CAP_Cam_Hero", res=(1600, 800), samples=64):
    scene = bpy.context.scene
    scene.camera = bpy.data.objects[camera]
    ng = bpy.data.node_groups.get("CAP_Haze")
    if ng is not None and "HazeAmount" in ng.nodes:
        ng.nodes["HazeAmount"].outputs[0].default_value = 0.0 if scene.camera.data.type == 'ORTHO' else 1.0
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.eevee.taa_render_samples = samples
    scene.render.filepath = path
    scene.render.image_settings.file_format = 'PNG'
    sun = bpy.data.objects.get("CAP_Sun")
    saved = None
    if sun is not None and scene.camera.data.type == 'ORTHO':      # map view: high neutral sun
        saved = (tuple(sun.rotation_euler), tuple(sun.data.color), sun.data.energy)
        sun.rotation_euler = (math.radians(32), 0.0, math.radians(35))
        sun.data.color = (1.0, 0.95, 0.88)
        sun.data.energy = 4.5
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        if saved is not None:
            sun.rotation_euler, sun.data.color, sun.data.energy = saved
    return path
