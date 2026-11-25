"""An inland terraced metropolis in a mountain basin ("kind": "metropolis"): Karn Ashur (generator/cities/karn_ashur.json).

Built after briefs/karn_ashur/red-cliff-metropolis/ (the concepts and 05-map-coordinates.json): two rocky snow peaks
framing a red-cliff basin, the higher western one carrying the First Flame; two snowmelt tributaries that meet below
the city and leave south; layered cliff terraces and windblown sand aprons at the mountain feet; a gentle north-west
approach for the freight caravans; and about 30 km^2 of dense two- to four-storey adobe courtyard houses on raised
terraces, with grain yards, caravanserais and the shaded market at the freight entrance, Al-Mirah's spring shrine at
the foot of the western peak, the Library on a civic terrace, bridges, canals, fields and villages downstream.

Scale: the plinth is the usual [-50, 50] model square at `model_scale` 200 (a 20 km square centred on the
settlement). Everything is laid out in real metres in the settlement's frame (+X east, +Y north, heights above sea
level) and written out at 1/MS. The layout comes from the config's `layout` block in kilometres; the same block goes
into city.json as `site`, so the Known World map patch (atlas/src/Core/BasinSite.cs) draws the same basin.

The houses, terraces, walls, awnings, domes, camels and trees are *instances*: one record each (position, size,
heading, colour, kind) in cities/<id>/instances.bin, drawn with GPU instancing by the Atlas (city view and map
miniature alike) from the prototypes in city.json `instances.protos`. In the .blend they are real meshes in the
`Instanced` collection (so the cinematic scripts render them), which the glTF export leaves out.
"""
import json
import math
import os
import time

import bpy
import numpy as np

import fantasy_capital as fc
from fantasy_capital import MB, smoothstep, points_in_poly, dist_to_polyline

ROOT_NAME = "Karn Ashur"
HALF = 50.0
MS = 200.0
R = HALF * MS
KM = 1000.0
N = 1025                     # height grid (19.5 m)
MESH_STEP = 2                # terrain mesh uses every 2nd grid line (513 x 513)
ALBEDO_PX = 4096             # painted ground (4.9 m per pixel)
VEX = 1.8                    # the diorama's vertical exaggeration of the ground about DATUM (buildings keep true heights)
DATUM = 1000.0
ANCHORS = {}
CFG = {}
LAY = {}

# ---------------------------------------------------------------- palette (sRGB)
DESERT_A = (0.80, 0.62, 0.42)
DESERT_B = (0.72, 0.54, 0.37)
DESERT_C = (0.86, 0.70, 0.50)
SAND = (0.92, 0.67, 0.38)
SAND_D = (0.84, 0.56, 0.30)
STRATA = [tuple(0.5 * c + 0.5 * m for c, m in zip(col, (0.72, 0.42, 0.27))) for col in
          [(0.66, 0.29, 0.18), (0.76, 0.42, 0.25), (0.84, 0.62, 0.42), (0.58, 0.25, 0.16), (0.72, 0.36, 0.22),
           (0.88, 0.74, 0.56), (0.62, 0.32, 0.20)]]
HIGH_ROCK = (0.50, 0.40, 0.36)
SCREE = (0.66, 0.40, 0.28)
SCREE_D = (0.56, 0.33, 0.24)
SNOW = (0.95, 0.96, 0.98)
GRAVEL = (0.70, 0.64, 0.54)
WET = (0.52, 0.48, 0.42)
RIPARIAN = (0.30, 0.42, 0.17)
CITY_DUST = (0.82, 0.70, 0.54)
ROAD = (0.88, 0.78, 0.62)
PATH = (0.93, 0.86, 0.72)
CANAL = (0.20, 0.42, 0.46)
CROPS = [(0.40, 0.55, 0.20), (0.50, 0.62, 0.24), (0.84, 0.72, 0.32), (0.76, 0.64, 0.28), (0.33, 0.50, 0.18),
         (0.62, 0.66, 0.26), (0.66, 0.50, 0.32), (0.44, 0.58, 0.22), (0.88, 0.78, 0.40)]
ORCHARD = (0.22, 0.36, 0.14)
WALLS = [(0.80, 0.62, 0.42), (0.84, 0.68, 0.48), (0.76, 0.57, 0.39), (0.88, 0.75, 0.57), (0.73, 0.52, 0.35),
         (0.82, 0.66, 0.46)]
WHITEWASH = (0.92, 0.88, 0.80)
SANDSTONE = (0.70, 0.42, 0.29)
SANDSTONE_L = (0.78, 0.52, 0.36)
CLOTH = [(0.93, 0.89, 0.79), (0.74, 0.23, 0.16), (0.86, 0.62, 0.30), (0.30, 0.34, 0.56), (0.90, 0.84, 0.70),
         (0.64, 0.30, 0.20)]
CAMEL = (0.72, 0.56, 0.38)
PALM = (0.30, 0.44, 0.18)
TREE = (0.28, 0.42, 0.16)
POPLAR = (0.36, 0.48, 0.20)
SHRUB = (0.48, 0.48, 0.30)
TRUNK = (0.36, 0.26, 0.17)
WIN_C = (0.13, 0.09, 0.07)
COURT = (0.42, 0.33, 0.24)

KINDS = {'house': 0, 'tower': 1, 'terrace': 2, 'warehouse': 3, 'wall': 4, 'awning': 5, 'dome': 6, 'camel': 7,
         'palm': 10, 'tree': 11, 'poplar': 12, 'shrub': 13}


# =============================================================================
# Config
# =============================================================================
def disp(z):
    """True elevation (metres) -> the model's exaggerated ground (metres before the 1/MS)."""
    return DATUM + (np.asarray(z, float) - DATUM) * VEX


def km(p):
    return (float(p[0]) * KM, float(p[1]) * KM)


def kmpts(pts):
    return [km(p) for p in pts]


def apply_config(cfg):
    global MS, R, ROOT_NAME
    CFG.clear()
    CFG.update(cfg)
    MS = float(cfg.get('model_scale', 200.0))
    R = HALF * MS
    global VEX
    VEX = float(cfg.get('layout', {}).get('vertical_exaggeration', VEX))
    ROOT_NAME = cfg.get('name', ROOT_NAME)
    lay = cfg['layout']
    LAY.clear()
    LAY['peaks'] = [dict(p, xy=km(p['at'])) for p in lay['peaks']]
    LAY['north_ridge'] = dict(lay['north_ridge'], xy=kmpts(lay['north_ridge']['line']))
    LAY['mesas'] = [dict(m, xy=km(m['at'])) for m in lay.get('mesas', [])]
    LAY['cliffs'] = {k: kmpts(v) for k, v in lay['cliff_zones'].items()}
    LAY['aprons'] = {k: kmpts(v) for k, v in lay['sand_aprons'].items()}
    LAY['districts'] = {k: dict(v, xy=kmpts(v['poly'])) for k, v in lay['districts'].items()}
    LAY['fields'] = {k.split(' ')[0]: kmpts(v) for k, v in lay['fields'].items()}
    rivers = {}
    for i, (k, v) in enumerate(lay['rivers'].items()):
        P0 = np.array([[p[0] * KM, p[1] * KM] for p in v['pts']])
        z0 = np.array([p[2] for p in v['pts']], float)
        c0 = cumlen(P0)
        P = meander(chaikin(P0, 2), 38.0, 520.0, 400 + i)
        cum = cumlen(P)
        # bed elevations follow the brief's points by their share of the length
        z = np.interp(cum / cum[-1], c0 / c0[-1], z0)
        rivers[k] = dict(xy=P, z=z, cum=cum, width=float(v['width_m']), fp=float(v['floodplain_m']))
    LAY['rivers'] = rivers
    LAY['canals'] = {k.split(' ')[0]: np.array(kmpts(v)) for k, v in lay['canals'].items()}
    LAY['roads'] = {k.split(' ')[0]: dict(xy=np.array(kmpts(v['pts'])), width=float(v['width_m'])) for k, v in lay['roads'].items()}
    LAY['climb'] = np.array(kmpts(lay['pilgrimage_climb']))
    LAY['places'] = {k.split(' ')[0]: dict(v, xy=km(v['at'])) for k, v in lay['places'].items()}
    LAY['freight'] = lay['freight']
    LAY['villages'] = [(p[0] * KM, p[1] * KM, int(p[2])) for p in lay['villages (added)']]
    LAY['mills'] = [km(p) for p in lay['mills (added)']]
    LAY['weirs'] = [km(p) for p in lay['weirs (added)']]


# =============================================================================
# Maths helpers
# =============================================================================
def seg_nearest(X, Y, P):
    """Distance from points (X, Y) to the polyline P (n x 2) and the arclength of the nearest point on it."""
    best = np.full(np.shape(X), np.inf)
    sb = np.zeros(np.shape(X))
    acc = 0.0
    for a, b in zip(P[:-1], P[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-9:
            continue
        L = math.sqrt(L2)
        t = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0.0, 1.0)
        d = np.hypot(X - a[0] - t * dx, Y - a[1] - t * dy)
        m = d < best
        best = np.where(m, d, best)
        sb = np.where(m, acc + t * L, sb)
        acc += L
    return best, sb


def soft_poly(X, Y, poly, fade):
    """1 inside the polygon, falling to 0 over `fade` metres outside (and easing in over fade/3 inside)."""
    inside = points_in_poly(X, Y, poly)
    d = dist_to_polyline(X, Y, poly, closed=True)
    return np.where(inside, 1.0, 1.0 - smoothstep(0.0, fade, d))


def smax(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return a * (1 - h) + b * h + k * h * (1 - h)


def smin(a, b, k):
    return -smax(-a, -b, k)


def blur1(A, r, axis):
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r + 1, r)
    P = np.pad(A, pad, mode='edge')
    c = np.cumsum(P, axis=axis)
    n = A.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def blur(A, r, passes=3):
    for _ in range(passes):
        A = blur1(blur1(A, r, 0), r, 1)
    return A


def ridged(x, y, octaves, seed):
    total = np.zeros_like(np.asarray(x, float))
    amp, freq, norm, w = 0.5, 1.0, 0.0, 1.0
    for i in range(octaves):
        v = 1.0 - np.abs(2.0 * fc.vnoise(x * freq, y * freq, seed + i * 31) - 1.0)
        v = v * v * w
        w = np.clip(v * 2.0, 0.0, 1.0)
        total = total + v * amp
        norm += amp
        amp *= 0.5
        freq *= 2.03
    return total / norm


def hash01(*ints):
    h = 2166136261
    for v in ints:
        h = ((h ^ (int(v) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    return (h & 0xFFFFFF) / float(0xFFFFFF)


def resample(P, step):
    P = np.asarray(P, float)
    out = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return np.array(out)


def chaikin(P, n):
    P = np.asarray(P, float)
    for _ in range(n):
        Q = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            Q += [0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b]
        Q.append(P[-1])
        P = np.array(Q)
    return P


def meander(P, amp, wave, seed, step=40.0):
    """Resample P and push it sideways by a smooth noise (zero at both ends)."""
    S = resample(P, step)
    s = cumlen(S)
    out = [S[0]]
    for i in range(1, len(S) - 1):
        u = S[i + 1] - S[i - 1]
        u /= max(np.linalg.norm(u), 1e-6)
        nrm = np.array([-u[1], u[0]])
        f = float(fc.fbm(np.array(s[i] / wave), np.array(seed * 1.7), 3, seed)) - 0.5
        env = min(1.0, s[i] / 600.0, (s[-1] - s[i]) / 600.0)
        out.append(S[i] + nrm * 2.0 * amp * f * env)
    out.append(S[-1])
    return np.array(out)


def cumlen(P):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])


def rect(cx, cy, w, d, ang):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + c * x - s * y, cy + s * x + c * y) for x, y in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))]


# =============================================================================
# The ground
# =============================================================================
class Ground:
    """Heights (metres above sea level) on an N x N grid over the plinth, row 0 to the south, plus the masks the
    painter and the placement read."""

    def __init__(self):
        t0 = time.time()
        xs = np.linspace(-R, R, N)
        self.xs = xs
        self.step = xs[1] - xs[0]
        X, Y = np.meshgrid(xs, xs)
        self.X, self.Y = X, Y
        Ht, self.rd, self.bed, self.river_id = self.heights(X, Y)
        self.Ht = Ht                      # true metres (the map, the painter's thresholds)
        self.H = disp(Ht)                 # the model's ground (placement)
        gy, gx = np.gradient(Ht, self.step)
        self.gx, self.gy = gx, gy
        self.slope = np.hypot(gx, gy)
        self.secs = round(time.time() - t0, 2)

    # ---------------------------------------------------------------- the shape
    def heights(self, X, Y):
        Xk, Yk = X / KM, Y / KM
        # valleys of the three rivers (each bed eases up its banks), the smooth minimum of them
        valley = None
        rd = np.full(X.shape, np.inf)
        bedmap = np.zeros(X.shape)
        rid = np.zeros(X.shape, np.int8)
        carve = []
        for i, (k, rv) in enumerate(LAY['rivers'].items()):
            d, s = seg_nearest(X, Y, rv['xy'])
            bed = np.interp(s, rv['cum'], rv['z'])
            fp = rv['fp'] * smoothstep(1760.0, 1380.0, bed) + 32.0
            e = np.maximum(d - fp, 0.0)
            v = bed + 2.5 + 235.0 * (1.0 - np.exp(-e / 1500.0)) + 0.017 * e
            valley = v if valley is None else smin(valley, v, 45.0)
            m = d < rd
            rd = np.where(m, d, rd)
            bedmap = np.where(m, bed, bedmap)
            rid = np.where(m, i, rid)
            carve.append((d, bed, fp, rv['width']))
        # gentle undulation away from the rivers, a little higher to the north
        und = 34.0 * (fc.fbm(Xk / 2.6 + 3.1, Yk / 2.6 - 1.7, 4, 11) - 0.5) + 10.0 * (fc.fbm(Xk * 1.7, Yk * 1.7, 3, 12) - 0.5)
        valley = valley + und * smoothstep(150.0, 600.0, rd) + 9.0 * np.clip(Yk, -10, 10)
        # mesas to the south-west and south-east: flat tops, steep red edges
        for ms in LAY['mesas']:
            cx, cy = ms['xy']
            a = math.radians(ms['rot_deg'])
            u = ((X - cx) * math.cos(a) + (Y - cy) * math.sin(a)) / (ms['r_km'][0] * KM)
            w = (-(X - cx) * math.sin(a) + (Y - cy) * math.cos(a)) / (ms['r_km'][1] * KM)
            q = np.hypot(u, w) * (1.0 + 0.34 * (fc.fbm(Xk * 2.2 + 7, Yk * 2.2, 4, 21) - 0.5))
            top = ms['top_m'] + 14.0 * (fc.fbm(Xk * 3, Yk * 3, 2, 22) - 0.5)
            e = smoothstep(0.44, 1.55, q + 0.08 * np.sin(3 * u + w))
            mesa = top - (top - 900.0) * e
            valley = np.maximum(valley, mesa)
        # the high col between the peaks, behind the basin
        nr = LAY['north_ridge']
        d, along = seg_nearest(X, Y, np.array(nr['xy']))
        crest = np.interp(along, cumlen(np.array(nr['xy'])), nr['crest_m']) if 'crest_m' in nr else nr['top_m']
        t = np.clip(d / (nr['half_km'] * KM), 0.0, 1.0)
        rr = ridged(Xk / 1.3 + 4.0, Yk / 1.3, 6, 31)
        ridge = 900.0 + (crest - 900.0) * (1.0 - t) ** 1.25 + 420.0 * (rr - 0.42) * np.sin(np.pi * t) * (1 - 0.5 * t)
        valley = smax(valley, ridge, 60.0)
        # the two peaks: a cliff band at the foot, concave flanks, arêtes and gullies from warped ridged noise
        mtn = np.full(X.shape, -1e4)
        wx = X + 700.0 * (fc.fbm(Xk / 2.4, Yk / 2.4, 3, 81) - 0.5)
        wy = Y + 700.0 * (fc.fbm(Xk / 2.4 + 5, Yk / 2.4, 3, 82) - 0.5)
        for pi_, pk in enumerate(LAY['peaks']):
            cx, cy = pk['xy']
            dx, dy = X - cx, Y - cy
            d = np.hypot(dx, dy)
            th = np.arctan2(dy, dx)
            jag = pk['jag']
            fd = np.array(sorted(pk['foot_km_by_deg'], key=lambda q: q[0]), float)
            ang = np.concatenate([fd[:, 0] - 360, fd[:, 0], fd[:, 0] + 360])
            rad = np.concatenate([fd[:, 1]] * 3) * KM
            foot = np.interp(np.degrees(th), ang, rad) * (1.0 + 0.07 * (fc.fbm(Xk * 1.3 + pi_ * 9, Yk * 1.3, 3, 83 + pi_) - 0.5))
            t = np.clip(d / foot, 0.0, 1.0)
            prof = 0.24 * smoothstep(1.0, 0.86, t) + 0.76 * np.maximum(0.0, 1.0 - t / 0.9) ** (1.5 + 0.25 * jag) * (1.0 + 0.5 * t)
            top = pk['top_m']
            h = 900.0 + (top - 900.0) * prof
            sc = 1500.0 - 450.0 * jag
            rn = ridged(wx / sc + 13 * pi_, wy / sc, 6, 51 + pi_)
            amp = (420.0 + 380.0 * jag) * np.sin(np.pi * np.clip(t * 1.08, 0.0, 1.0)) ** 0.8 * (1.0 - 0.6 * t)
            h = h + amp * (rn - 0.42)
            pl = pk.get('plateau_km', 0.0) * KM
            if pl > 0:
                h = np.where(d < pl, top, np.minimum(h, top - 4.0 * smoothstep(pl, pl * 3, d)))
                h = np.where(d < pl * 2.5, np.maximum(h, top - 30.0 * smoothstep(pl, pl * 2.5, d)), h)
            else:
                h = np.minimum(h, top)
            mtn = smax(mtn, h, 120.0)
        # layered cliffs: benches and risers, strongest in the cliff zones that face the basin
        cm = np.zeros(X.shape)
        for poly in LAY['cliffs'].values():
            cm = np.maximum(cm, soft_poly(X, Y, poly, 700.0))
        self.cliff_mask = cm
        stepm = 95.0 + 35.0 * fc.fbm(Xk / 3.0, Yk / 3.0, 2, 91)
        warp = 45.0 * (fc.fbm(Xk / 0.8, Yk / 0.8, 3, 92) - 0.5)
        q = (mtn + warp) / stepm
        fq = q - np.floor(q)
        stepped = (np.floor(q) + smoothstep(0.5, 0.93, fq)) * stepm - warp
        w = cm * smoothstep(1300.0, 1420.0, mtn) * (1.0 - smoothstep(2100.0, 2450.0, mtn)) * 0.55
        mtn = mtn + (stepped - mtn) * w
        H = smax(valley, mtn, 90.0)
        # A broad north-facing saddle descends to the coast. Its benches leave room
        # for pack trains and gardens while the connecting crest rises on either side.
        pass_road = CFG['layout']['roads'].get('north_pass')
        if pass_road:
            pass_xy = LAY['roads']['north_pass']['xy']
            dist, along = seg_nearest(X, Y, pass_xy)
            floor = np.interp(along, cumlen(pass_xy), pass_road['bench_m'])
            shoulder = smoothstep(170, 1550, dist)
            H += (np.minimum(H, floor + 0.055 * dist) - H) * (1 - shoulder)
        # rivers carve their beds: a gorge on the mountain, a gravel floodplain in the basin
        for d, bed, fp, width in carve:
            bars = 1.6 * fc.fbm(X / 90.0, Y / 90.0, 3, 61)
            e = np.maximum(d - fp, 0.0)
            bank = 0.28 + 0.6 * smoothstep(1450.0, 1750.0, bed)
            c = bed + np.where(d < width * 0.5, -1.2, np.where(d < fp, 1.2 + bars, 1.2 + bars + bank * e + 0.004 * e * e))
            H = smin(H, c, 6.0)
        # sand aprons lean on the mountain feet
        am = np.zeros(X.shape)
        for poly in LAY['aprons'].values():
            am = np.maximum(am, soft_poly(X, Y, poly, 450.0))
        self.apron_mask = am
        Hb = blur(H, 14)
        dunes = 7.0 * np.sin((X * 0.78 + Y * 0.62) / 85.0 + 4.0 * fc.fbm(Xk * 2, Yk * 2, 3, 71)) * fc.fbm(Xk * 4, Yk * 4, 2, 72)
        Ha = np.maximum(H, Hb + 8.0) + dunes
        H = H + (Ha - H) * am
        # districts: smoothed benches for the terraces
        dm = np.zeros(X.shape)
        for dd in LAY['districts'].values():
            dm = np.maximum(dm, soft_poly(X, Y, dd['xy'], 250.0))
        self.district_mask = dm
        H = H + (blur(H, 6) - H) * dm * 0.75 * smoothstep(60.0, 200.0, rd)
        # the freight road keeps a gentle grade from the plinth edge into the yards
        if pass_road:
            H = self.grade_road(X, Y, H, pass_xy, 0.045, 18.0, 95.0)
        H = self.grade_road(X, Y, H, LAY['roads']['local_freight_road']['xy'], 0.035, 26.0, 110.0)
        return H, rd, bedmap, rid

    def grade_road(self, X, Y, H, P, grade, half, shoulder):
        S = resample(P, self.step)
        s = cumlen(S)
        z = self._bilinear(H, S[:, 0], S[:, 1])
        k = 31
        zp = np.pad(z, (k, k), mode='edge')
        zs = np.convolve(zp, np.ones(2 * k + 1) / (2 * k + 1), mode='same')[k:-k]
        for i in range(1, len(zs)):                              # limit the grade both ways
            zs[i] = min(max(zs[i], zs[i - 1] - grade * (s[i] - s[i - 1])), zs[i - 1] + grade * (s[i] - s[i - 1]))
        for i in range(len(zs) - 2, -1, -1):
            zs[i] = min(max(zs[i], zs[i + 1] - grade * (s[i + 1] - s[i])), zs[i + 1] + grade * (s[i + 1] - s[i]))
        d, sa = seg_nearest(X, Y, S)
        zr = np.interp(sa, s, zs)
        w = 1.0 - smoothstep(half, half + shoulder, d)
        self.road_profile = (S, s, zs)
        return H + (zr - H) * w

    def _bilinear(self, G, x, y):
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        fx = (x + R) / self.step
        fy = (y + R) / self.step
        i = np.clip(np.floor(fx).astype(int), 0, N - 2)
        j = np.clip(np.floor(fy).astype(int), 0, N - 2)
        tx = np.clip(fx - i, 0, 1)
        ty = np.clip(fy - j, 0, 1)
        return (G[j, i] * (1 - tx) + G[j, i + 1] * tx) * (1 - ty) + (G[j + 1, i] * (1 - tx) + G[j + 1, i + 1] * tx) * ty

    # ---------------------------------------------------------------- queries (metres)
    def h(self, x, y):
        return self._bilinear(self.H, x, y)

    def hs(self, x, y):
        return float(self.h(x, y))

    def ht(self, x, y):
        return float(self._bilinear(self.Ht, x, y))

    def slope_at(self, x, y):
        return self._bilinear(self.slope, x, y)

    def river_d(self, x, y):
        return self._bilinear(self.rd, x, y)

    def bed_at(self, x, y):
        return self._bilinear(self.bed, x, y)

    def up(self, A, px):
        """Upsample a grid array to px x px (bilinear), row 0 to the south."""
        u = (np.arange(px) + 0.5) / px * (N - 1)
        i = np.clip(np.floor(u).astype(int), 0, N - 2)
        t = (u - i)[None, :]
        rows = A[:, i] * (1 - t) + A[:, i + 1] * t                       # N x px
        tj = (u - i)[:, None]
        return rows[i, :] * (1 - tj) + rows[i + 1, :] * tj


# =============================================================================
# Painting the ground (the terrain albedo, also the Known World miniature's ground)
# =============================================================================
class Raster:
    """Full-resolution helpers for painting: pixel centres in metres, windowed distance fields."""

    def __init__(self, px):
        self.px = px
        self.size = 2 * R / px
        self.c = -R + (np.arange(px) + 0.5) * self.size

    def window(self, x0, x1, y0, y1):
        i0 = max(0, int((x0 + R) / self.size))
        i1 = min(self.px, int(math.ceil((x1 + R) / self.size)) + 1)
        j0 = max(0, int((y0 + R) / self.size))
        j1 = min(self.px, int(math.ceil((y1 + R) / self.size)) + 1)
        if i0 >= i1 or j0 >= j1:
            return None
        X, Y = np.meshgrid(self.c[i0:i1], self.c[j0:j1])
        return (slice(j0, j1), slice(i0, i1)), X, Y

    def dist(self, P, margin, out=None):
        """Distance to the polyline, only within `margin` (np.inf beyond)."""
        D = out if out is not None else np.full((self.px, self.px), np.inf, np.float32)
        P = np.asarray(P, float)
        for a, b in zip(P[:-1], P[1:]):
            w = self.window(min(a[0], b[0]) - margin, max(a[0], b[0]) + margin, min(a[1], b[1]) - margin, max(a[1], b[1]) + margin)
            if w is None:
                continue
            sl, X, Y = w
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = max(dx * dx + dy * dy, 1e-9)
            t = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0, 1)
            d = np.hypot(X - a[0] - t * dx, Y - a[1] - t * dy).astype(np.float32)
            D[sl] = np.minimum(D[sl], d)
        return D

    def poly(self, P, out=None, value=True):
        M = out if out is not None else np.zeros((self.px, self.px), bool)
        P = np.asarray(P, float)
        w = self.window(P[:, 0].min(), P[:, 0].max(), P[:, 1].min(), P[:, 1].max())
        if w is not None:
            sl, X, Y = w
            M[sl] |= points_in_poly(X, Y, [tuple(p) for p in P])
        return M


def mix(a, b, t):
    t = np.asarray(t, np.float32)[..., None]
    return a * (1 - t) + np.asarray(b, np.float32) * t


def paint_albedo(G, px=ALBEDO_PX, villages=()):
    """The ground colour, top-down, row 0 to the south (RGB float32 in sRGB)."""
    t0 = time.time()
    Rs = Raster(px)
    X, Y = np.meshgrid(Rs.c, Rs.c)
    X = X.astype(np.float32)
    Y = Y.astype(np.float32)
    Xk, Yk = X / KM, Y / KM
    H = G.up(G.Ht, px).astype(np.float32)
    S = G.up(G.slope, px).astype(np.float32)
    north = G.up(-G.gy / np.maximum(G.slope, 1e-3), px).astype(np.float32)     # 1 on north-facing slopes
    n1 = fc.fbm(Xk / 1.8, Yk / 1.8, 4, 101).astype(np.float32)
    n2 = fc.fbm(Xk * 3.0, Yk * 3.0, 3, 102).astype(np.float32)
    n3 = fc.vnoise(X / 9.0, Y / 9.0, 103).astype(np.float32)
    col = mix(mix(np.full(X.shape + (3,), DESERT_A, np.float32), DESERT_B, smoothstep(0.35, 0.65, n1)), DESERT_C,
              0.6 * smoothstep(0.55, 0.8, n2))
    col *= (0.94 + 0.12 * n3)[..., None]
    cliff = G.up(G.cliff_mask, px).astype(np.float32)
    apron = G.up(G.apron_mask, px).astype(np.float32)
    dist_m = G.up(G.district_mask, px).astype(np.float32)
    # red rock and its strata
    rockw = np.maximum(smoothstep(0.33, 0.62, S), cliff * smoothstep(0.16, 0.38, S))
    rockw = np.maximum(rockw, smoothstep(1800.0, 2250.0, H) * 0.85).astype(np.float32)
    k = H / 24.0 + 9.0 * fc.fbm(Xk / 1.1 + 2, Yk / 1.1, 4, 111) + 1.5 * Xk / 10.0 - 1.0 * Yk / 10.0
    band = np.floor(k).astype(np.int64) % len(STRATA)
    frac = (k - np.floor(k)).astype(np.float32)
    st = np.asarray(STRATA, np.float32)
    rock = st[band] * (1 - smoothstep(0.8, 1.0, frac))[..., None] + st[(band + 1) % len(STRATA)] * smoothstep(0.8, 1.0, frac)[..., None]
    streak = fc.vnoise(X / 14.0, Y / 14.0, 115).astype(np.float32)                 # vertical weathering on steep faces
    rock *= (0.88 + 0.22 * n3 - 0.22 * smoothstep(0.55, 1.2, S) * smoothstep(0.45, 0.8, streak))[..., None]
    scree = mix(np.full(X.shape + (3,), SCREE, np.float32), SCREE_D, smoothstep(0.35, 0.7, n2)) * (0.9 + 0.2 * n3)[..., None]
    rock = mix(scree, rock, smoothstep(0.42, 0.85, S) * (0.35 + 0.65 * cliff))
    rock = mix(rock, HIGH_ROCK, smoothstep(2450.0, 2950.0, H) * 0.85)
    col = mix(col, rock, rockw)
    # snow: lower on north faces, thin on cliffs
    line = 3010.0 - 190.0 * north + 160.0 * (n1 - 0.5)
    snow = smoothstep(line - 70.0, line + 110.0, H) * (1.0 - 0.75 * smoothstep(0.95, 1.6, S))
    snow = np.maximum(snow, smoothstep(3250.0, 3400.0, H) * 0.9)
    col = mix(col, SNOW, snow)
    # sand aprons with ripples
    rip = 0.5 + 0.5 * np.sin((X * 0.78 + Y * 0.62) / 7.0 + 6.0 * n2)
    sand = mix(np.full(X.shape + (3,), SAND, np.float32), SAND_D, 0.35 * rip + 0.3 * n1)
    col = mix(col, sand, apron * (1.0 - 0.7 * rockw) * (1.0 - snow))
    # the basin's dry benches: dusty in the districts
    col = mix(col, CITY_DUST, smoothstep(0.35, 0.75, dist_m + 0.35 * (n2 - 0.5)) * (1.0 - rockw) * 0.8)
    # rivers: green banks, gravel floodplains, wet channels
    bed = G.up(G.bed, px).astype(np.float32)
    bars = fc.fbm(X / 60.0, Y / 60.0, 3, 121).astype(np.float32)
    for rid, rv in LAY['rivers'].items():
        D = Rs.dist(rv['xy'], rv['fp'] + 260.0)
        fp = rv['fp'] * smoothstep(1760.0, 1380.0, bed) + 32.0
        green = (1.0 - smoothstep(fp + 50.0, fp + 210.0, D)) * smoothstep(fp * 0.55, fp * 0.95, D) * smoothstep(1900.0, 1700.0, bed)
        col = mix(col, np.asarray(RIPARIAN) * (0.8 + 0.4 * n3[..., None]), green * 0.9 * (1 - snow))
        grav = (1.0 - smoothstep(fp * 0.7, fp + 6.0, D)) * smoothstep(1800.0, 1600.0, bed) * (0.55 + 0.45 * smoothstep(0.3, 0.6, bars))
        gcol = mix(np.full(X.shape + (3,), GRAVEL, np.float32), RIPARIAN, 0.55 * smoothstep(0.62, 0.75, bars))
        col = mix(col, gcol, grav)
        wch = rv['width'] * (0.45 + 0.55 * smoothstep(2100.0, 1400.0, bed))
        col = mix(col, WET, (1.0 - smoothstep(wch * 0.5, wch * 0.5 + 8.0, D)) * smoothstep(2600.0, 2300.0, bed))
        del D
    # fields: strips across each field, crops by strip, thinner and drier away from the canals
    canal_d = np.full((px, px), np.inf, np.float32)
    for P in LAY['canals'].values():
        Rs.dist(P, 900.0, canal_d)
    for rv in LAY['rivers'].values():
        Rs.dist(rv['xy'], 900.0, canal_d)
    # Irrigated meadow links field blocks to the canal banks and fades onto dry benches.
    meadow = (1 - smoothstep(120, 850, canal_d)) * (1 - smoothstep(0.08, 0.23, S))
    clear_channel = smoothstep(45, 155, G.up(G.rd, px))
    meadow *= (1 - dist_m) * (1 - snow) * clear_channel
    col = mix(col, np.asarray(RIPARIAN) * (0.94 + 0.35 * n2[..., None]), 0.72 * meadow)
    fid = 0
    for name, poly in LAY['fields'].items():
        fid += 1
        Pp = np.asarray(poly)
        w = Rs.window(Pp[:, 0].min() - 10, Pp[:, 0].max() + 10, Pp[:, 1].min() - 10, Pp[:, 1].max() + 10)
        if w is None:
            continue
        sl, Xw, Yw = w
        inside = points_in_poly(Xw, Yw, poly)
        edge = dist_to_polyline(Xw, Yw, poly, closed=True)
        c0 = Pp.mean(axis=0)
        ev, evec = np.linalg.eigh(np.cov((Pp - c0).T))
        ax = evec[:, -1]
        a = math.atan2(ax[1], ax[0])
        u = (Xw - c0[0]) * math.cos(a) + (Yw - c0[1]) * math.sin(a)
        v = -(Xw - c0[0]) * math.sin(a) + (Yw - c0[1]) * math.cos(a)
        u = u + 30.0 * (fc.fbm(Xw / 700.0, Yw / 700.0, 2, 130 + fid) - 0.5)
        v = v + 30.0 * (fc.fbm(Xw / 700.0 + 5, Yw / 700.0, 2, 140 + fid) - 0.5)
        su = 46.0 + 30.0 * fc.vnoise(np.floor(v / 220.0), fid * 7.0, 150)
        iu = np.floor(u / su)
        iv = np.floor(v / 220.0)
        hsh = fc._hash(iu.astype(np.int64), iv.astype(np.int64), 160 + fid)
        crop = np.asarray(CROPS, np.float32)[(hsh * len(CROPS)).astype(int) % len(CROPS)]
        orch = hsh > 0.86
        dots = fc.vnoise(Xw / 5.0, Yw / 5.0, 170) > 0.55
        fc_col = np.where(orch[..., None], np.where(dots[..., None], np.asarray(ORCHARD) * 0.8, np.asarray(ORCHARD) * 1.25), crop)
        fu = u / su - iu
        fv = v / 220.0 - iv
        border = (np.minimum(np.minimum(fu, 1 - fu) * su, np.minimum(fv, 1 - fv) * 220.0) < 2.2)
        fc_col = np.where(border[..., None], fc_col * 0.72, fc_col)
        cd = canal_d[sl]
        dry = smoothstep(450.0, 850.0, cd) * (fc.fbm(Xw / 300.0, Yw / 300.0, 2, 180) > 0.42)
        wgt = clear_channel[sl] * inside * smoothstep(0.0, 14.0, edge) * (1.0 - 0.55 * dry) * (1.0 - rockw[sl]) * (1 - smoothstep(0.08, 0.24, S[sl])) * (1 - dist_m[sl])
        col[sl] = mix(col[sl], fc_col.astype(np.float32), wgt.astype(np.float32))
    # canals: water with a green margin
    for name, P in LAY['canals'].items():
        D = Rs.dist(P, 40.0)
        col = mix(col, RIPARIAN, (1.0 - smoothstep(4.0, 14.0, D)) * 0.8)
        col = mix(col, CANAL, 1.0 - smoothstep(2.5, 4.0, D))
    # roads, the pilgrims' climb
    for name, rd in LAY['roads'].items():
        D = Rs.dist(rd['xy'], rd['width'])
        col = mix(col, ROAD, (1.0 - smoothstep(rd['width'] * 0.32, rd['width'] * 0.5, D)) * (1 - snow))
    D = Rs.dist(LAY['climb'], 8.0)
    col = mix(col, PATH, (1.0 - smoothstep(2.2, 3.4, D)) * 0.95)
    # the villages: beaten earth and threshing floors, a ring of palm gardens
    for (vx, vy, vz) in villages:
        w = Rs.window(vx - 260, vx + 260, vy - 260, vy + 260)
        if w is None:
            continue
        sl, Xw, Yw = w
        r = np.hypot(Xw - vx, Yw - vy) * (1.0 + 0.25 * (fc.fbm(Xw / 60.0, Yw / 60.0, 2, 190) - 0.5))
        col[sl] = mix(col[sl], ORCHARD, ((1.0 - smoothstep(170.0, 230.0, r)) * smoothstep(95.0, 125.0, r) * 0.85).astype(np.float32))
        col[sl] = mix(col[sl], (0.86, 0.74, 0.56), (1.0 - smoothstep(85.0, 110.0, r)).astype(np.float32))
    ANCHORS['albedo_secs'] = round(time.time() - t0, 1)
    return np.clip(col, 0.0, 1.0)


def save_png(rgb, path):
    """rgb: px x px x 3 sRGB floats, row 0 to the south (Blender's own bottom-up order)."""
    px = rgb.shape[0]
    img = bpy.data.images.new("CAP_BasinAlbedo", px, px, alpha=False)
    rgba = np.ones((px, px, 4), np.float32)
    rgba[..., :3] = rgb
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img


def save_height_png(H, path, lo, hi):
    """16-bit heights packed in R (high byte) and G (low byte), as atlas/assets/map/known_world/height.png does.
    Row 0 of H is the south; the PNG's top row is the north."""
    n = H.shape[0]
    q = np.clip(np.round((H - lo) / (hi - lo) * 65535.0), 0, 65535).astype(np.int64)
    rgba = np.ones((n, n, 4), np.float32)
    rgba[..., 0] = (q // 256) / 255.0
    rgba[..., 1] = (q % 256) / 255.0
    rgba[..., 2] = 0.0
    img = bpy.data.images.new("CAP_BasinHeight", n, n, alpha=False)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


# =============================================================================
# Fast meshes
# =============================================================================
def fast_mesh(name, V, F, face_col, face_alpha, coll, mats, smooth=False):
    """V: (n, 3) model metres; F: list of index arrays (same length per call is not required); face_col: (f, 3)
    linear RGB; face_alpha: (f,)."""
    V = np.asarray(V, np.float32)
    sizes = np.array([len(f) for f in F], np.int64)
    loops = np.concatenate(F).astype(np.int32) if len(F) else np.zeros(0, np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.ravel())
    me.loops.add(len(loops))
    me.loops.foreach_set('vertex_index', loops)
    me.polygons.add(len(F))
    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32)
    me.polygons.foreach_set('loop_start', starts)
    me.update(calc_edges=True)
    rgba = np.ones((len(loops), 4), np.float32)
    rgba[:, :3] = np.repeat(np.asarray(face_col, np.float32), sizes, axis=0)
    rgba[:, 3] = np.repeat(np.asarray(face_alpha, np.float32), sizes)
    at = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
    at.data.foreach_set('color', rgba.ravel())
    me.polygons.foreach_set('use_smooth', np.full(len(F), smooth))
    me.validate()
    me.update()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def grid_mesh(name, Z, x0, x1, y0, y1, coll, mats, uv=True):
    n = Z.shape[0]
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    Xg, Yg = np.meshgrid(xs, ys)
    V = np.column_stack([Xg.ravel(), Yg.ravel(), Z.ravel()]).astype(np.float32)
    idx = np.arange(n * n).reshape(n, n)
    Fq = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()])
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.ravel())
    me.loops.add(Fq.size)
    me.loops.foreach_set('vertex_index', Fq.ravel().astype(np.int32))
    me.polygons.add(len(Fq))
    me.polygons.foreach_set('loop_start', (np.arange(len(Fq)) * 4).astype(np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(len(Fq), bool))
    if uv:
        lay = me.uv_layers.new(name="UVMap")
        lv = Fq.ravel()
        u = (V[lv, 0] + HALF) / (2 * HALF)
        v = (V[lv, 1] + HALF) / (2 * HALF)
        lay.data.foreach_set('uv', np.column_stack([u, v]).astype(np.float32).ravel())
    me.update()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


# =============================================================================
# Instance prototypes (unit box: x, y in [-0.5, 0.5], z in [0, 1]; faces CCW from outside, +Z up).
# Each face: (vertex indices, mode, colour) where mode 'tint' = instance colour x shade, 'abs' = the colour,
# 'win' = a window (dark; lit at night by the instance's order).
# =============================================================================
def _box_faces(x0, x1, y0, y1, z0, z1, mode='tint', shade=(0.9, 0.86, 0.94, 0.9), top=1.06, top_mode=None, top_col=None, bottom=False):
    V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    F = [((0, 1, 5, 4), mode, shade[0]), ((1, 2, 6, 5), mode, shade[1]), ((2, 3, 7, 6), mode, shade[2]),
         ((3, 0, 4, 7), mode, shade[3])]
    if top is not None:
        F.append(((4, 5, 6, 7), top_mode or mode, top_col if top_col is not None else top))
    if bottom:
        F.append(((3, 2, 1, 0), mode, 0.7))
    return V, F


class Proto:
    def __init__(self):
        self.V, self.F = [], []

    def add(self, V, F):
        b = len(self.V)
        self.V.extend(V)
        for idx, mode, c in F:
            self.F.append(([b + i for i in idx], mode, c))
        return self

    def json(self):
        out = {'v': [[round(c, 4) for c in v] for v in self.V], 'f': []}
        for idx, mode, c in self.F:
            col = [round(float(x), 4) for x in (c if isinstance(c, (tuple, list)) else (c, c, c))]
            out['f'].append({'i': idx, 'm': mode, 'c': col})
        return out


def proto_house():
    """A flat-roofed courtyard house: outer walls, a roof ring round a sunken court, two front windows."""
    p = Proto()
    cx, cy = 0.22, 0.2                      # court half sizes
    zc = 0.18                               # court floor (fraction of the height)
    V = [(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0),
         (-0.5, -0.5, 1), (0.5, -0.5, 1), (0.5, 0.5, 1), (-0.5, 0.5, 1),
         (-cx, -cy, 1), (cx, -cy, 1), (cx, cy, 1), (-cx, cy, 1),
         (-cx, -cy, zc), (cx, -cy, zc), (cx, cy, zc), (-cx, cy, zc)]
    F = [((0, 1, 5, 4), 'tint', 0.9), ((1, 2, 6, 5), 'tint', 0.84), ((2, 3, 7, 6), 'tint', 0.95), ((3, 0, 4, 7), 'tint', 0.88),
         ((4, 5, 9, 8), 'tint', 1.08), ((5, 6, 10, 9), 'tint', 1.08), ((6, 7, 11, 10), 'tint', 1.08), ((7, 4, 8, 11), 'tint', 1.08),
         ((8, 9, 13, 12), 'tint', 0.62), ((9, 10, 14, 13), 'tint', 0.55), ((10, 11, 15, 14), 'tint', 0.66), ((11, 8, 12, 15), 'tint', 0.58),
         ((12, 13, 14, 15), 'abs', COURT)]
    p.add(V, F)
    for x in (-0.24, 0.2):                  # front windows (local -y face)
        p.add([(x - 0.05, -0.502, 0.42), (x + 0.05, -0.502, 0.42), (x + 0.05, -0.502, 0.6), (x - 0.05, -0.502, 0.6)],
              [((0, 1, 2, 3), 'win', WIN_C)])
    return p


def proto_tower():
    p = Proto()
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0, 0.94, top=0.96))
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0.94, 1.0, shade=(0.98, 0.94, 1.0, 0.96), top=None))
    for (x0, y0, x1, y1) in ((-0.12, -0.503, 0.12, -0.503), (0.503, -0.12, 0.503, 0.12), (0.12, 0.503, -0.12, 0.503), (-0.503, 0.12, -0.503, -0.12)):
        p.add([(x0, y0, 0.66), (x1, y1, 0.66), (x1, y1, 0.82), (x0, y0, 0.82)], [((0, 1, 2, 3), 'win', WIN_C)])
    return p


def proto_terrace():
    p = Proto()
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0, 1, shade=(0.86, 0.8, 0.92, 0.84), top=1.04))
    return p


def proto_warehouse():
    """A long vaulted grain store (vault along local x)."""
    p = Proto()
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0, 0.62, top=None))
    n = 5
    ring = [(-0.5 * math.cos(math.pi * k / n), 0.62 + 0.38 * math.sin(math.pi * k / n)) for k in range(n + 1)]
    V, F = [], []
    for k in range(n + 1):
        y, z = ring[k]
        V += [(-0.5, y, z), (0.5, y, z)]
    for k in range(n):
        a, b = 2 * k, 2 * (k + 1)
        F.append(((a, a + 1, b + 1, b), 'tint', 1.0 + 0.04 * math.sin(math.pi * (k + 0.5) / n)))
    p.add(V, F)
    gable_w = [(-0.5, y, z) for y, z in ring]
    gable_e = [(0.5, y, z) for y, z in ring]
    p.add(gable_w, [(tuple(range(len(gable_w))), 'tint', 0.86)])
    p.add(gable_e, [(tuple(range(len(gable_e) - 1, -1, -1)), 'tint', 0.9)])
    return p


def proto_wall():
    p = Proto()
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0, 1, shade=(0.9, 0.84, 0.95, 0.88), top=1.04))
    return p


def proto_awning():
    p = Proto()
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0.86, 1.0, shade=(0.92, 0.88, 0.95, 0.9), top=1.0, bottom=True))
    for x in (-0.46, 0.46):
        for y in (-0.46, 0.46):
            p.add(*_box_faces(x - 0.015, x + 0.015, y - 0.015, y + 0.015, 0, 0.86, mode='abs',
                              shade=((0.36, 0.26, 0.17),) * 4, top=None))
    return p


def proto_dome():
    p = Proto()
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0, 0.46, top=1.04))
    n, lat = 10, 4
    V = []
    for i in range(lat):
        a = (math.pi / 2) * i / lat
        r = 0.42 * math.cos(a)
        z = 0.46 + 0.54 * math.sin(a)
        V += [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    V.append((0.0, 0.0, 1.0))
    F = []
    for i in range(lat - 1):
        for k in range(n):
            k2 = (k + 1) % n
            F.append(((i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k), 'tint', 1.1 - 0.05 * i))
    top = lat * n
    for k in range(n):
        F.append((((lat - 1) * n + k, (lat - 1) * n + (k + 1) % n, top), 'tint', 1.12))
    p.add(V, F)
    return p


def proto_camel():
    """Length along local x (head at +x)."""
    p = Proto()
    p.add(*_box_faces(-0.5, 0.22, -0.5, 0.5, 0.42, 0.78, top=1.04))
    p.add(*_box_faces(-0.22, 0.05, -0.36, 0.36, 0.78, 0.92, top=1.04))          # hump
    p.add(*_box_faces(0.22, 0.5, -0.18, 0.18, 0.62, 1.0, top=1.04))             # neck and head
    for x in (-0.4, 0.12):
        p.add(*_box_faces(x - 0.05, x + 0.05, -0.1, 0.1, 0, 0.42, shade=(0.7, 0.66, 0.72, 0.68), top=None))
    return p


def _trunk(p, top, w):
    p.add(*_box_faces(-w, w, -w, w, 0, top, mode='abs', shade=((TRUNK),) * 4, top=None))


def proto_palm():
    p = Proto()
    _trunk(p, 0.84, 0.045)
    n = 7
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        e = (-s * 0.09, c * 0.09)
        tip = (c * 0.5, s * 0.5, 0.66)
        mid = (c * 0.28, s * 0.28, 0.97)
        base = (0.0, 0.0, 0.9)
        p.add([base, (mid[0] + e[0], mid[1] + e[1], mid[2]), tip, (mid[0] - e[0], mid[1] - e[1], mid[2])],
              [((0, 1, 2, 3), 'tint', 1.0), ((3, 2, 1, 0), 'tint', 0.8)])
    return p


def _ball(p, z0, z1, r, shade=1.0):
    zc = (z0 + z1) / 2
    hz = (z1 - z0) / 2
    V = [(0, 0, z1)] + [(r * math.cos(2 * math.pi * k / 6), r * math.sin(2 * math.pi * k / 6), zc + hz * 0.25) for k in range(6)] + \
        [(r * 0.8 * math.cos(2 * math.pi * (k + 0.5) / 6), r * 0.8 * math.sin(2 * math.pi * (k + 0.5) / 6), zc - hz * 0.55) for k in range(6)] + [(0, 0, z0)]
    F = []
    for k in range(6):
        k2 = (k + 1) % 6
        F.append(((0, 1 + k, 1 + k2), 'tint', shade * 1.12))
        F.append(((1 + k, 7 + k, 1 + k2), 'tint', shade))
        F.append(((1 + k2, 7 + k, 7 + k2), 'tint', shade * 0.92))
        F.append(((7 + k, 13, 7 + k2), 'tint', shade * 0.75))
    p.add(V, F)


def proto_tree():
    p = Proto()
    _trunk(p, 0.4, 0.06)
    _ball(p, 0.3, 1.0, 0.5)
    return p


def proto_poplar():
    p = Proto()
    _trunk(p, 0.2, 0.05)
    _ball(p, 0.12, 1.0, 0.5)
    return p


def proto_shrub():
    p = Proto()
    _ball(p, 0.0, 1.0, 0.5)
    return p


PROTOS = {}


def protos():
    if not PROTOS:
        PROTOS.update({'house': proto_house(), 'tower': proto_tower(), 'terrace': proto_terrace(),
                       'warehouse': proto_warehouse(), 'wall': proto_wall(), 'awning': proto_awning(),
                       'dome': proto_dome(), 'camel': proto_camel(), 'palm': proto_palm(), 'tree': proto_tree(),
                       'poplar': proto_poplar(), 'shrub': proto_shrub()})
    return PROTOS


# =============================================================================
# Instances (real metres while laying out)
# =============================================================================
class Inst:
    def __init__(self):
        self.rows = []

    def add(self, kind, x, y, z, w, d, h, rot, col):
        if abs(x) > R - 4.0 or abs(y) > R - 4.0:          # nothing hangs off the plinth's edge
            return
        self.rows.append((float(x), float(y), float(z), float(w), float(d), float(h), float(rot),
                          float(col[0]), float(col[1]), float(col[2]), float(KINDS[kind])))

    def array(self):
        """Model metres, sorted by kind."""
        A = np.asarray(self.rows, np.float64)
        A[:, :6] /= MS
        return A[np.argsort(A[:, 10], kind='stable')].astype(np.float32)


def window_order(x, y, z, cx, cy):
    """Light-up order for a window face (model metres): hash + distance from the market, as the cities do."""
    h = np.asarray([hash01(int(a * 997), int(b * 991), int(c * 983), 7) for a, b, c in zip(x, y, z)])
    d = np.minimum(1.0, np.hypot(np.asarray(x) - cx, np.asarray(y) - cy) / 40.0)
    return np.clip(0.6 * h + 0.4 * d, 0.01, 0.98)


def instance_meshes(A, coll, mat, market_xy):
    """Turn the instance table (model metres) into real meshes for Blender (one object per kind)."""
    pr = protos()
    inv = {v: k for k, v in KINDS.items()}
    made = 0
    for kid in np.unique(A[:, 10]).astype(int):
        name = inv[kid]
        P = pr[name]
        S = A[A[:, 10] == kid]
        n = len(S)
        PV = np.asarray(P.V, np.float64)
        nv = len(PV)
        c, s = np.cos(S[:, 6]), np.sin(S[:, 6])
        lx = PV[None, :, 0] * S[:, 3:4]
        ly = PV[None, :, 1] * S[:, 4:5]
        lz = PV[None, :, 2] * S[:, 5:6]
        X = S[:, 0:1] + lx * c[:, None] - ly * s[:, None]
        Y = S[:, 1:2] + lx * s[:, None] + ly * c[:, None]
        Z = S[:, 2:3] + lz
        V = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
        tint = fc.lin(S[:, 7:10])
        F, cols, alph = [], [], []
        wins = None
        for fi, (idx, mode, col) in enumerate(P.F):
            idx = np.asarray(idx)
            F.extend(list(idx[None, :] + (np.arange(n) * nv)[:, None]))
            if mode == 'tint':
                cc = tint * float(col)
                a = np.ones(n)
            else:
                cc = np.repeat(fc.lin(np.asarray(col, float))[None, :], n, axis=0)
                a = np.ones(n)
                if mode == 'win':
                    if wins is None:
                        cx = np.asarray([P.V[i] for i in idx]).mean(axis=0)
                        wins = window_order(S[:, 0], S[:, 1], S[:, 2] + cx[2] * S[:, 5], market_xy[0], market_xy[1])
                    a = wins
            cols.append(cc)
            alph.append(a)
        # faces were appended face-major; reorder colours the same way
        fcol = np.concatenate(cols, axis=0)
        fal = np.concatenate(alph, axis=0)
        fast_mesh("CAP_Inst_" + name, V, F, np.minimum(fcol, 1.0), fal, coll, [mat])
        made += n
    return made


# =============================================================================
# Layout: the city
# =============================================================================
class Reserve:
    """Where nothing may be built: a 5 m raster over the plinth."""

    def __init__(self, res=5.0):
        self.res = res
        self.n = int(2 * R / res)
        self.m = np.zeros((self.n, self.n), bool)

    def ij(self, x, y):
        return (np.clip(((np.asarray(x) + R) / self.res).astype(int), 0, self.n - 1),
                np.clip(((np.asarray(y) + R) / self.res).astype(int), 0, self.n - 1))

    def _win(self, x0, x1, y0, y1):
        i0, j0 = self.ij(x0, y0)
        i1, j1 = self.ij(x1, y1)
        xs = -R + (np.arange(i0, i1 + 1) + 0.5) * self.res
        ys = -R + (np.arange(j0, j1 + 1) + 0.5) * self.res
        X, Y = np.meshgrid(xs, ys)
        return (slice(j0, j1 + 1), slice(i0, i1 + 1)), X, Y

    def line(self, P, half):
        P = np.asarray(P, float)
        for a, b in zip(P[:-1], P[1:]):
            sl, X, Y = self._win(min(a[0], b[0]) - half, max(a[0], b[0]) + half, min(a[1], b[1]) - half, max(a[1], b[1]) + half)
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = max(dx * dx + dy * dy, 1e-9)
            t = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0, 1)
            self.m[sl] |= np.hypot(X - a[0] - t * dx, Y - a[1] - t * dy) < half

    def poly(self, P):
        P = np.asarray(P, float)
        sl, X, Y = self._win(P[:, 0].min(), P[:, 0].max(), P[:, 1].min(), P[:, 1].max())
        self.m[sl] |= points_in_poly(X, Y, [tuple(p) for p in P])

    def rect(self, cx, cy, w, d, ang, grow=0.0):
        self.poly(rect(cx, cy, w + 2 * grow, d + 2 * grow, ang))

    def free(self, pts):
        P = np.asarray(pts, float)
        i, j = self.ij(P[:, 0], P[:, 1])
        return not self.m[j, i].any()


class City:
    def __init__(self, G):
        self.G = G
        self.I = Inst()
        self.rng = np.random.default_rng(1124)
        self.res = Reserve()
        self.lights = []           # (x, y, z metres, kind, strength)
        self.bridges = []          # (a, b, z_deck, width)
        self.mb = MB()             # real geometry (metres), for the glb: bridges, mills, weirs, the flame
        self.fire = MB()
        self.water = []            # extra water discs (x, y, r, z)
        self.stats = {}
        self.blocks = 0
        self.zone_pts = {}

    # ------------------------------------------------------------ helpers
    def wall_col(self, x, y):
        r = self.rng.random()
        if r < 0.07:
            c = WHITEWASH
        elif r < 0.15:
            c = SANDSTONE_L
        else:
            c = WALLS[int(self.rng.integers(len(WALLS)))]
        j = self.rng.normal(0, 0.022, 3)
        return tuple(np.clip(np.asarray(c) + j, 0, 1))

    def ground_box(self, cx, cy, w, d, ang):
        pts = rect(cx, cy, w, d, ang) + [(cx, cy)]
        z = self.G.h([p[0] for p in pts], [p[1] for p in pts])
        return float(z.min()), float(z.max()), float(z[-1])

    def light(self, x, y, z, kind, strength):
        self.lights.append((x, y, z, kind, strength))

    # ------------------------------------------------------------ reserves
    def reserve_all(self):
        G = self.G
        for rv in LAY['rivers'].values():
            # keep houses out of the floodplains (wider where the floodplain is wide)
            S = resample(rv['xy'], 60.0)
            ss = cumlen(S)
            for i, (a, b) in enumerate(zip(S[:-1], S[1:])):
                bed = float(np.interp(ss[i], rv['cum'], rv['z']))
                fp = rv['fp'] * float(smoothstep(1760.0, 1380.0, bed)) + 32.0
                self.res.line([a, b], fp + 45.0)
        for P in LAY['canals'].values():
            self.res.line(P, 12.0)
        for name, rd in LAY['roads'].items():
            self.res.line(rd['xy'], rd['width'] * 0.5 + 5.0)
        self.res.line(LAY['climb'], 10.0)

    # ------------------------------------------------------------ landmarks of the freight terrace
    def caravanserai(self, x, y, rot_deg, size=88.0):
        a = math.radians(rot_deg)
        z0, z1, zc = self.ground_box(x, y, size + 10, size + 10, a)
        top = z1 + 0.4
        self.I.add('terrace', x, y, z0 - 2.0, size + 8, size + 8, top - z0 + 2.0, a, SANDSTONE)
        th, hh = 13.0, 8.5
        col = self.wall_col(x, y)
        c, s = math.cos(a), math.sin(a)

        def L(u, v):
            return x + c * u - s * v, y + s * u + c * v
        half = size / 2
        for (u, v, w, d) in ((0, -half + th / 2, size, th), (0, half - th / 2, size, th),
                             (-half + th / 2, 0, th, size - 2 * th), (half - th / 2, 0, th, size - 2 * th)):
            if v < -half + th:                                 # the gate side (local -y) has a gap
                for su in (-1, 1):
                    px, py = L(su * (size / 4 + 4), v)
                    self.I.add('house', px, py, top, size / 2 - 8, d, hh, a, col)
                gx, gy = L(0, v - 1.0)
                self.I.add('tower', gx, gy, top, 16.0, d + 4, hh + 4.5, a, SANDSTONE_L)
                self.light(*L(0, v - th / 2 - 2), top + 6.0, 'torch', 0.9)
            else:
                px, py = L(u, v)
                self.I.add('house', px, py, top, w, d, hh, a, col)
        for su in (-1, 1):
            for sv in (-1, 1):
                px, py = L(su * (half - 5), sv * (half - 5))
                self.I.add('tower', px, py, top, 11, 11, hh + 3.5, a, col)
        # the court: camels and their loads under shade cloths
        for k in range(int(self.rng.integers(10, 22))):
            u, v = self.rng.uniform(-half + th + 4, half - th - 4, 2)
            px, py = L(u, v)
            self.I.add('camel', px, py, top, 2.7, 0.9, 2.2, a + self.rng.normal(0, 0.6), np.clip(np.asarray(CAMEL) + self.rng.normal(0, 0.05, 3), 0, 1))
        for k in range(3):
            px, py = L(self.rng.uniform(-20, 20), self.rng.uniform(-20, 20))
            self.I.add('awning', px, py, top, 9, 7, 3.2, a, CLOTH[int(self.rng.integers(len(CLOTH)))])
        self.light(x, y, top + 4, 'lamp', 0.5)
        self.res.rect(x, y, size, size, a, 8.0)
        self.zone_pts.setdefault('caravan_yards', []).append((x, y, top))

    def granary(self, x, y, nrows, wk, dk):
        w, d = wk * KM, dk * KM
        z0, z1, zc = self.ground_box(x, y, w, d, 0.0)
        top = z1 + 0.3
        self.I.add('terrace', x, y, z0 - 2, w + 6, d + 6, top - z0 + 2, 0.0, SANDSTONE)
        for (cx, cy, ww, dd) in ((x, y - d / 2, w, 3), (x, y + d / 2, w, 3), (x - w / 2, y, 3, d), (x + w / 2, y, 3, d)):
            self.I.add('wall', cx, cy, top, ww, dd, 4.5, 0.0, SANDSTONE_L)
        pitch = (d - 16) / max(1, nrows)
        for r in range(nrows):
            yy = y - d / 2 + 8 + pitch * (r + 0.5)
            n = max(1, int((w - 16) / 64))
            for k in range(n):
                xx = x - w / 2 + 8 + (w - 16) * (k + 0.5) / n
                self.I.add('warehouse', xx, yy, top, (w - 16) / n - 6, min(16.0, pitch - 8), 10.0, 0.0,
                           np.clip(np.asarray(WALLS[k % len(WALLS)]) * 1.02, 0, 1))
        for k in range(int(w * d / 900)):
            px, py = x + self.rng.uniform(-w / 2 + 6, w / 2 - 6), y + self.rng.uniform(-d / 2 + 6, d / 2 - 6)
            self.I.add('camel', px, py, top, 2.7, 0.9, 2.2, self.rng.uniform(0, 6.3), CAMEL)
        self.res.rect(x, y, w, d, 0.0, 6.0)
        self.light(x, y - d / 2, top + 5, 'lamp', 0.5)
        self.zone_pts.setdefault('grain_yards', []).append((x, y, top))

    def animal_yard(self, x, y, wk, dk):
        w, d = wk * KM, dk * KM
        z0, z1, zc = self.ground_box(x, y, w, d, 0.0)
        nx, ny = max(2, int(w / 45)), max(2, int(d / 40))
        for i in range(nx + 1):
            xx = x - w / 2 + w * i / nx
            self.I.add('wall', xx, y, self.G.hs(xx, y) - 0.5, 1.4, d, 2.0, 0.0, SANDSTONE_L)
        for j in range(ny + 1):
            yy = y - d / 2 + d * j / ny
            self.I.add('wall', x, yy, self.G.hs(x, yy) - 0.5, w, 1.4, 2.0, 0.0, SANDSTONE_L)
        for k in range(int(w * d / 260)):
            px, py = x + self.rng.uniform(-w / 2 + 3, w / 2 - 3), y + self.rng.uniform(-d / 2 + 3, d / 2 - 3)
            self.I.add('camel', px, py, self.G.hs(px, py), 2.7, 0.9, 2.2, self.rng.uniform(0, 6.3),
                       np.clip(np.asarray(CAMEL) * self.rng.uniform(0.75, 1.1), 0, 1))
        self.res.rect(x, y, w, d, 0.0, 4.0)
        self.zone_pts.setdefault('animal_yards', []).append((x, y, zc))

    def market(self, x, y, wk, dk, rot_deg):
        w, d = wk * KM, dk * KM
        a = math.radians(rot_deg)
        c, s = math.cos(a), math.sin(a)
        z0, z1, zc = self.ground_box(x, y, w, d, a)
        top = zc + 0.3
        self.I.add('terrace', x, y, z0 - 2, w + 4, d + 4, top - z0 + 2, a, SANDSTONE)
        # halls round the edge, awning rows inside, a fountain in the middle fed by Al-Mirah's rill
        for (u, v, ww, dd) in ((0, -d / 2 + 7, w, 14), (0, d / 2 - 7, w, 14), (-w / 2 + 7, 0, 14, d - 28), (w / 2 - 7, 0, 14, d - 28)):
            n = max(1, int(max(ww, dd) / 34))
            for k in range(n):
                f = (k + 0.5) / n - 0.5
                uu, vv = (u + f * ww, v) if ww > dd else (u, v + f * dd)
                self.I.add('house', x + c * uu - s * vv, y + s * uu + c * vv, top, (ww / n - 2) if ww > dd else dd - 2,
                           dd - 2 if ww > dd else (dd / n - 2), 7.5 + self.rng.uniform(0, 2), a, self.wall_col(x, y))
        for u in np.arange(-w / 2 + 24, w / 2 - 22, 13.0):
            for v in np.arange(-d / 2 + 24, d / 2 - 22, 10.0):
                if abs(u) < 14 and abs(v) < 12:
                    continue
                if self.rng.random() < 0.12:
                    continue
                px, py = x + c * u - s * v, y + s * u + c * v
                self.I.add('awning', px, py, top, 11.0, 8.0, 3.4 + self.rng.uniform(-0.3, 0.4), a,
                           CLOTH[int(self.rng.integers(len(CLOTH)))])
                if self.rng.random() < 0.25:
                    self.light(px, py, top + 2.5, 'lamp', 0.35)
        self.water.append((x, y, 6.0, top + 0.6))
        self.res.rect(x, y, w, d, a, 6.0)
        self.zone_pts.setdefault('market', []).append((x, y, top))
        self.market_xy = (x, y, top)

    # ------------------------------------------------------------ civic and sacred
    def library(self):
        x, y = LAY['places']['library']['xy']
        a = math.radians(8.0)
        w, d = 230.0, 160.0
        z0, z1, zc = self.ground_box(x, y, w, d, a)
        top = z1 + 6.0
        self.I.add('terrace', x, y, z0 - 2, w, d, top - z0 + 2, a, SANDSTONE)
        c, s = math.cos(a), math.sin(a)

        def L(u, v):
            return x + c * u - s * v, y + s * u + c * v
        self.I.add('house', *L(0, 30), top, 120.0, 52.0, 15.0, a, WHITEWASH)          # the reading halls round their court
        self.I.add('dome', *L(0, 30), top, 36.0, 36.0, 34.0, a, (0.86, 0.80, 0.70))
        for su in (-1, 1):
            self.I.add('tower', *L(su * 70, 30), top, 14.0, 14.0, 24.0, a, SANDSTONE_L)
            self.I.add('house', *L(su * 58, -34), top, 60.0, 26.0, 9.0, a, WHITEWASH)
        for k in range(14):                                   # the colonnaded walk to the street
            u = -60 + 120 * k / 13
            self.I.add('wall', *L(u, -62), top, 1.6, 1.6, 6.0, a, (0.92, 0.88, 0.80))
        for k in range(10):
            px, py = L(self.rng.uniform(-90, 90), self.rng.uniform(-70, -48))
            self.tree('palm', px, py, top, 1.0)
        self.I.add('terrace', *L(0, -d / 2 - 10), z0 - 1, 60.0, 22.0, top - z0 - 1.5, a, SANDSTONE_L)   # the stair
        self.res.rect(x, y, w, d, a, 10.0)
        for k in range(8):
            self.light(*L(-60 + 120 * k / 7, -62), top + 5, 'lamp', 0.45)
        self.zone_pts['library'] = [(x, y - 40, top)]
        self.library_top = top

    def al_mirah(self):
        x, y = LAY['places']['al_mirah']['xy']
        z0, z1, zc = self.ground_box(x, y, 70, 50, 0.3)
        top = zc + 0.5
        self.I.add('terrace', x, y, z0 - 1.5, 74, 54, top - z0 + 1.5, 0.3, SANDSTONE)
        for (u, v, w, d) in ((0, -25, 70, 1.6), (0, 25, 70, 1.6), (-35, 0, 1.6, 50), (35, 0, 1.6, 50)):
            c, s = math.cos(0.3), math.sin(0.3)
            self.I.add('wall', x + c * u - s * v, y + s * u + c * v, top, w, d, 2.4, 0.3, SANDSTONE_L)
        self.I.add('dome', x - 12, y + 4, top, 13.0, 13.0, 12.0, 0.3, WHITEWASH)
        self.water.append((x + 10, y - 3, 11.0, top + 0.3))
        for k in range(9):
            a = self.rng.uniform(0, 6.3)
            r = self.rng.uniform(15, 30)
            self.tree('palm', x + 10 + r * math.cos(a), y - 3 + r * math.sin(a) * 0.7, None, self.rng.uniform(0.9, 1.25))
        self.res.rect(x, y, 70, 50, 0.3, 10.0)
        self.light(x - 12, y + 4, top + 7, 'torch', 0.8)
        self.light(x + 10, y - 3, top + 2, 'lamp', 0.5)
        self.zone_pts['al_mirah'] = [(x, y, top)]
        self.mirah_top = top

    def first_flame(self):
        x, y = LAY['places']['first_flame']['xy']
        top = self.G.hs(x, y) + 0.5
        self.I.add('terrace', x, y, top - 8, 54, 40, 8.0, 0.4, SANDSTONE)
        c, s = math.cos(0.4), math.sin(0.4)
        self.I.add('house', x - s * 9, y + c * 9, top, 26, 14, 8.0, 0.4, (0.86, 0.80, 0.70))
        for k in range(8):
            u = -18 + 36 * k / 7
            for v in (-12.0, 3.0):
                self.I.add('wall', x + c * u - s * v, y + s * u + c * v, top, 1.3, 1.3, 6.5, 0.4, (0.90, 0.86, 0.78))
        self.I.add('tower', x, y - 4, top, 5.0, 5.0, 2.2, 0.4, (0.36, 0.30, 0.26))       # the fire bowl's plinth
        self.flame(x, y - 4, top + 2.2, 4.0, 11.0)
        self.light(x, y - 4, top + 8, 'lighthouse', 1.0)
        self.zone_pts['first_flame'] = [(x, y - 14, top)]
        self.flame_top = top

    def flame(self, x, y, z, r, h):
        n = 9
        for k in range(3):
            rr = r * (1 - 0.25 * k)
            hh = h * (1 - 0.22 * k)
            a0 = k * 0.7
            ring = [(x + rr * math.cos(a0 + 2 * math.pi * i / n) * (0.8 + 0.3 * ((i * 7) % 3) / 2), y + rr * math.sin(a0 + 2 * math.pi * i / n), z) for i in range(n)]
            b = self.fire.vid(ring + [(x + 0.2 * k, y - 0.15 * k, z + hh)])
            for i in range(n):
                self.fire.face((b + i, b + (i + 1) % n, b + n), (1.0, 0.55, 0.15))

    def way_shrines(self):
        P = LAY['climb']
        for k in range(1, len(P) - 1):
            x, y = P[k]
            z = self.G.hs(x, y)
            self.I.add('tower', x + 7, y + 5, z - 1, 6.0, 6.0, 8.0, 0.5, SANDSTONE_L)
            self.light(x + 7, y + 5, z + 7.5, 'torch', 0.85 if k % 2 else 0.6)
        S = resample(P, 160.0)
        for p in S[1:-1]:
            z = self.G.hs(p[0], p[1])
            self.light(p[0], p[1], z + 1.5, 'torch', 0.4)

    # ------------------------------------------------------------ bridges, mills, weirs
    def bridges_all(self):
        roads = [rd['xy'] for k, rd in LAY['roads'].items() if k != 'spring_way']
        made = []
        for rid, rv in LAY['rivers'].items():
            Rr = rv['xy']
            for P in roads:
                for a, b in zip(P[:-1], P[1:]):
                    for c, d in zip(Rr[:-1], Rr[1:]):
                        p = seg_inter(a, b, c, d)
                        if p is None:
                            continue
                        bed = float(np.interp(seg_nearest(np.array([p[0]]), np.array([p[1]]), Rr)[1][0], rv['cum'], rv['z']))
                        if bed > 1700:
                            continue
                        u = (b - a) / np.linalg.norm(b - a)
                        fp = rv['fp'] * float(smoothstep(1760.0, 1380.0, bed)) + 32.0
                        half = min(fp * 1.05 + 25.0, 330.0)
                        made.append((p, u, bed, half, rid))
        for p, u, bed, half, rid in made:
            self.bridge(p, u, bed, half)
        self.stats['bridges'] = len(made)

    def bridge(self, p, u, bed, half):
        G = self.G
        a = p - u * half
        b = p + u * half
        za, zb = G.hs(*a), G.hs(*b)
        deck = max(float(disp(bed)) + 10.0, min(za, zb) + 0.5)
        n = max(3, int(2 * half / 21.0))
        nrm = np.array([-u[1], u[0]])
        wdt = 9.0
        ang = math.atan2(u[1], u[0])
        col = SANDSTONE_L
        # the deck as an instance (the map draws it too), piers and arches as real geometry
        self.I.add('terrace', p[0], p[1], deck - 1.4, 2 * half + 6, wdt, 1.4, ang, col)
        for side in (-1, 1):
            q = p + nrm * side * (wdt / 2 - 0.4)
            self.I.add('wall', q[0], q[1], deck, 2 * half + 6, 0.8, 1.1, ang, SANDSTONE)
        span = 2 * half / n
        for k in range(n + 1):
            c = a + u * span * k
            zg = G.hs(*c)
            if zg < deck - 2.0:
                self.mb.box(c[0], c[1], zg - 1.0, 3.6, wdt - 0.4, deck - 1.4 - zg + 1.0, ang, SANDSTONE)
        for k in range(n):
            c0 = a + u * span * k
            c1 = a + u * span * (k + 1)
            zg = min(G.hs(*c0), G.hs(*c1))
            if zg > deck - 3.0:
                continue
            # the spandrel between two piers, its arch cut out (one face each side)
            m = 7
            for side in (-1, 1):
                off = nrm * side * (wdt / 2 - 0.2)
                ring = []
                for i in range(m + 1):
                    t = i / m
                    q = c0 + (c1 - c0) * t + off
                    zt = deck - 1.4
                    zb_ = zt - (deck - 1.4 - zg) * (1 - 0.55 * math.sin(math.pi * t))
                    ring.append((q[0], q[1], zb_))
                ring += [(c1[0] + off[0], c1[1] + off[1], deck - 1.4), (c0[0] + off[0], c0[1] + off[1], deck - 1.4)]
                self.mb.poly_facing(ring, (off[0], off[1], 0.0), SANDSTONE)
        self.res.line([a, b], wdt)
        self.bridges.append((a, b, deck, wdt))
        self.light(p[0], p[1], deck + 3, 'lamp', 0.4)

    def mills(self):
        for (x, y) in LAY['mills']:
            z = self.G.hs(x, y)
            self.I.add('house', x + 9, y + 6, z, 14, 10, 7.0, 0.2, self.wall_col(x, y))
            # the water wheel
            n = 12
            r = 4.2
            ring = [(x + 1.0, y + r * math.cos(2 * math.pi * k / n), z + 3.0 + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
            self.mb.extrude(ring, (1.0, 0, 0), WOOD_C, WOOD_C)
            self.light(x + 9, y, z + 4, 'lamp', 0.35)
        self.stats['mills'] = len(LAY['mills'])

    def weirs(self):
        for (x, y) in LAY['weirs']:
            rv = min(LAY['rivers'].values(), key=lambda r: seg_nearest(np.array([x]), np.array([y]), r['xy'])[0][0])
            d, s = seg_nearest(np.array([x]), np.array([y]), rv['xy'])
            k = int(np.searchsorted(rv['cum'], s[0]) - 1)
            k = max(0, min(k, len(rv['xy']) - 2))
            u = rv['xy'][k + 1] - rv['xy'][k]
            u /= np.linalg.norm(u)
            nrm = np.array([-u[1], u[0]])
            bed = float(np.interp(s[0], rv['cum'], rv['z']))
            ang = math.atan2(nrm[1], nrm[0]) + 0.35          # a little across the flow, as weirs are set
            L = rv['width'] + 30.0
            zb = float(disp(bed))
            self.I.add('wall', x, y, zb - 2.0, L, 3.0, 3.6, ang, SANDSTONE)
            self.foam.append((x, y, zb + 1.7, L, ang))
        self.stats['weirs'] = len(LAY['weirs'])

    # ------------------------------------------------------------ the city blocks
    def districts(self):
        G = self.G
        houses = 0
        for did, dd in LAY['districts'].items():
            poly = dd['xy']
            Pp = np.asarray(poly)
            a = math.radians(dd['angle_deg'])
            cu, su = math.cos(a), math.sin(a)
            c0 = Pp.mean(axis=0)
            U = (Pp[:, 0] - c0[0]) * cu + (Pp[:, 1] - c0[1]) * su
            V = -(Pp[:, 0] - c0[0]) * su + (Pp[:, 1] - c0[1]) * cu
            bw, bd = 56.0, 44.0
            lane, main = 7.0, 15.0
            pu, pv = bw + lane, bd + lane
            iu = 0
            u = U.min() - bw
            while u < U.max() + bw:
                wide_u = (iu % 5 == 4)
                v = V.min() - bd + (pv * 0.37 if iu % 2 else 0.0)
                iv = 0
                while v < V.max() + bd:
                    wide_v = (iv % 6 == 5)
                    uu = u + 9.0 * (fc.vnoise(np.array(u / 300.0), np.array(v / 300.0), 201) - 0.5)
                    vv = v + 9.0 * (fc.vnoise(np.array(u / 300.0 + 7), np.array(v / 300.0), 202) - 0.5)
                    cx = c0[0] + uu * cu - vv * su
                    cy = c0[1] + uu * su + vv * cu
                    ang = a + 0.05 * (fc.vnoise(np.array(cx / 900.0), np.array(cy / 900.0), 203) - 0.5) * 2
                    houses += self.block(cx, cy, bw - (6.0 if wide_u else 0.0), bd - (6.0 if wide_v else 0.0), float(ang), poly, did)
                    v += pv
                    iv += 1
                u += pu
                iu += 1
        self.stats['houses_city'] = houses
        self.stats['blocks'] = self.blocks

    def block(self, cx, cy, bw, bd, ang, poly, did):
        corners = rect(cx, cy, bw, bd, ang)
        inside = points_in_poly(np.array([p[0] for p in corners] + [cx]), np.array([p[1] for p in corners] + [cy]), poly)
        if inside.sum() < 4 or not inside[-1]:
            return 0
        if not self.res.free(corners + [(cx, cy)] + rect(cx, cy, bw * 0.5, bd * 0.5, ang)):
            return 0
        z0, z1, zc = self.ground_box(cx, cy, bw, bd, ang)
        if z1 - z0 > 26.0:
            return 0
        self.blocks += 1
        rng = self.rng
        if z1 - z0 > 1.2:
            top = z1 + 0.3
            self.I.add('terrace', cx, cy, z0 - 2.0, bw + 1.0, bd + 1.0, top - z0 + 2.0, ang, SANDSTONE if rng.random() < 0.55 else SANDSTONE_L)
        else:
            top = zc
        c, s = math.cos(ang), math.sin(ang)
        r = rng.random()
        if r < 0.006:                                      # a neighbourhood shrine in its court
            self.I.add('dome', cx, cy, top, 18, 18, 18 + rng.uniform(0, 6), ang, WHITEWASH if rng.random() < 0.5 else SANDSTONE_L)
            for (u, v, w, d) in ((0, -bd / 2 + 1, bw, 1.4), (0, bd / 2 - 1, bw, 1.4), (-bw / 2 + 1, 0, 1.4, bd), (bw / 2 - 1, 0, 1.4, bd)):
                self.I.add('wall', cx + c * u - s * v, cy + s * u + c * v, top, w, d, 3.2, ang, SANDSTONE_L)
            for k in range(3):
                u, v = rng.uniform(-bw / 2 + 6, bw / 2 - 6), rng.uniform(-bd / 2 + 6, -12)
                self.tree('palm', cx + c * u - s * v, cy + s * u + c * v, top, 0.9)
            self.light(cx, cy, top + 6, 'lamp', 0.4)
            return 0
        if r < 0.025:                                      # a little square with trees
            for k in range(4):
                u, v = rng.uniform(-bw / 2 + 5, bw / 2 - 5), rng.uniform(-bd / 2 + 5, bd / 2 - 5)
                self.tree('tree' if rng.random() < 0.6 else 'palm', cx + c * u - s * v, cy + s * u + c * v, top, 0.9)
            return 0
        n = 0
        for row in (-1, 1):
            d = bd / 2 - 0.4
            v = row * bd / 4
            u = -bw / 2
            while u < bw / 2 - 6:
                w = min(rng.uniform(11.0, 20.0), bw / 2 - u)
                if bw / 2 - (u + w) < 8:
                    w = bw / 2 - u
                uc = u + w / 2
                px, py = cx + c * uc - s * v, cy + s * uc + c * v
                q = rng.random()
                if q < 0.03:
                    self.tree('palm' if rng.random() < 0.6 else 'tree', px, py, top, 0.85)
                elif q < 0.09:
                    hh = rng.uniform(14.5, 19.0)
                    self.I.add('tower', px, py, top, min(w - 2, 9.0), min(d - 2, 9.0), hh, ang + (0 if row < 0 else math.pi), self.wall_col(px, py))
                    n += 1
                else:
                    st = rng.choice([1, 2, 2, 2, 3, 3, 4], p=[0.12, 0.17, 0.17, 0.17, 0.14, 0.13, 0.10])
                    hh = st * 3.3 + 1.0 + rng.uniform(-0.3, 0.4)
                    self.I.add('house', px, py, top, w - rng.uniform(0.4, 1.4), d - rng.uniform(0.2, 1.0), hh,
                               ang + (0 if row < 0 else math.pi), self.wall_col(px, py))
                    n += 1
                u += w
        if self.rng.random() < 0.08:
            self.light(cx, cy, top + 5, 'lamp', 0.3)
        return n

    # ------------------------------------------------------------ villages downstream
    def villages(self):
        G = self.G
        made = 0
        for (vx, vy, n) in LAY['villages']:
            # nudge onto dry ground above the floodplain
            best = None
            for k in range(160):
                x = vx + self.rng.normal(0, 120 + 6 * k) if k else vx
                y = vy + self.rng.normal(0, 120 + 6 * k) if k else vy
                rd = float(G.river_d(x, y))
                sl = float(G.slope_at(x, y))
                in_field = any(points_in_poly(np.array([x]), np.array([y]), f)[0] for f in LAY['fields'].values())
                if self.res.free([(x, y)]) and rd > 260 and sl < 0.12 and not in_field:
                    best = (x, y)
                    break
            if best is None:
                continue
            x0, y0 = best
            ang0 = self.rng.uniform(0, math.pi)
            placed = 0
            # the walled core (a ksar): wall, corner towers, a packed block of houses inside
            side = 60.0 + 2.6 * math.sqrt(n)
            zc = G.hs(x0, y0)
            c, s = math.cos(ang0), math.sin(ang0)
            for (u, v, w, d) in ((0, -side / 2, side, 2.2), (0, side / 2, side, 2.2), (-side / 2, 0, 2.2, side), (side / 2, 0, 2.2, side)):
                self.I.add('wall', x0 + c * u - s * v, y0 + s * u + c * v, zc - 1.5, w, d, 7.5, ang0, SANDSTONE_L)
            for su in (-1, 1):
                for sv in (-1, 1):
                    self.I.add('tower', x0 + c * su * side / 2 - s * sv * side / 2, y0 + s * su * side / 2 + c * sv * side / 2, zc - 1.5, 7.5, 7.5, 12.5, ang0, SANDSTONE_L)
            for i in range(4):
                for j in range(4):
                    u, v = -side / 2 + side * (i + 0.5) / 4, -side / 2 + side * (j + 0.5) / 4
                    if self.rng.random() < 0.15:
                        continue
                    self.I.add('house', x0 + c * u - s * v, y0 + s * u + c * v, zc - 1.0, side / 4 - 1.2, side / 4 - 1.2,
                               self.rng.choice([5.2, 8.5, 8.5, 11.8]), ang0, self.wall_col(x0, y0))
                    placed += 1
            self.res.rect(x0, y0, side, side, ang0, 4.0)
            for k in range(n * 4):
                if placed >= n:
                    break
                r = side * 0.55 + 12.5 * math.sqrt(k + 1) * self.rng.uniform(0.85, 1.15)
                th = k * 2.399 + self.rng.normal(0, 0.15)
                x, y = x0 + r * math.cos(th), y0 + r * math.sin(th)
                w, d = self.rng.uniform(9, 15), self.rng.uniform(9, 14)
                pts = rect(x, y, w, d, ang0)
                if not self.res.free(pts):
                    continue
                z0, z1, zc = self.ground_box(x, y, w, d, ang0)
                if z1 - z0 > 6:
                    continue
                kind = 'tower' if self.rng.random() < 0.05 else 'house'
                hh = self.rng.choice([4.3, 4.3, 7.6]) if kind == 'house' else self.rng.uniform(10, 13)
                self.I.add(kind, x, y, z0 - 0.5, w if kind == 'house' else 7, d if kind == 'house' else 7, hh + (zc - z0) + 0.5,
                           ang0 + self.rng.choice([0, math.pi / 2, math.pi]), self.wall_col(x, y))
                self.res.rect(x, y, w, d, ang0, 2.0)
                placed += 1
            for k in range(int(n * 1.6)):
                a = self.rng.uniform(0, 6.3)
                rr = self.rng.uniform(100, 220)
                x, y = x0 + rr * math.cos(a), y0 + rr * math.sin(a)
                if self.res.free([(x, y)]):
                    self.tree('palm' if self.rng.random() < 0.6 else 'tree', x, y, None, self.rng.uniform(0.85, 1.2))
            if self.rng.random() < 0.8:
                self.light(x0, y0, G.hs(x0, y0) + 5, 'lamp', 0.4)
            self.zone_pts.setdefault('villages', []).append((x0, y0, G.hs(x0, y0)))
            made += placed
        self.stats['houses_villages'] = made

    # ------------------------------------------------------------ caravans on the freight road
    def caravans(self):
        S, s, zs = self.G.road_profile
        L = s[-1]
        groups = 0
        for g0 in np.linspace(300.0, L * 0.42, 9):
            n = int(self.rng.integers(8, 17))
            for k in range(n):
                sk = g0 + k * 4.2
                i = int(np.searchsorted(s, sk))
                if i <= 0 or i >= len(S):
                    continue
                u = S[i] - S[i - 1]
                ang = math.atan2(u[1], u[0])
                nrm = np.array([-u[1], u[0]]) / max(np.linalg.norm(u), 1e-6)
                p = S[i] + nrm * (3.0 if groups % 2 else -3.0)
                self.I.add('camel', p[0], p[1], float(np.interp(sk, s, zs)), 2.7, 0.9, 2.2, ang if groups % 2 == 0 else ang + math.pi,
                           np.clip(np.asarray(CAMEL) * self.rng.uniform(0.8, 1.1), 0, 1))
            groups += 1
        self.stats['caravans'] = groups

    # ------------------------------------------------------------ trees
    def tree(self, kind, x, y, z, scale):
        dims = {'palm': (7.5, 13.0), 'tree': (8.0, 9.0), 'poplar': (4.2, 15.0), 'shrub': (3.0, 2.0)}[kind]
        col = {'palm': PALM, 'tree': TREE, 'poplar': POPLAR, 'shrub': SHRUB}[kind]
        if z is None:
            z = self.G.hs(x, y)
        w = dims[0] * scale * self.rng.uniform(0.85, 1.15)
        self.I.add(kind, x, y, z - 0.3, w, w, dims[1] * scale * self.rng.uniform(0.85, 1.15), self.rng.uniform(0, 6.3),
                   np.clip(np.asarray(col) * self.rng.uniform(0.8, 1.15), 0, 1))

    def vegetation(self):
        G = self.G
        rng = self.rng
        n0 = len(self.I.rows)
        # poplars and orchard trees along the rivers' banks (outside the floodplain, below the mountains)
        for rid, rv in LAY['rivers'].items():
            S = resample(rv['xy'], 16.0)
            ss = cumlen(S)
            for i, p in enumerate(S[:-1]):
                bed = float(np.interp(ss[i], rv['cum'], rv['z']))
                if bed > 1650:
                    continue
                u = S[i + 1] - p
                u /= max(np.linalg.norm(u), 1e-6)
                nrm = np.array([-u[1], u[0]])
                fp = rv['fp'] * float(smoothstep(1760.0, 1380.0, bed)) + 32.0
                for side in (-1, 1):
                    for band in range(3):
                        if rng.random() > (0.7 - 0.2 * band):
                            continue
                        q = p + nrm * side * (fp + 12 + band * 14 + rng.normal(0, 4)) + u * rng.normal(0, 5)
                        if not self.res.free([q]) and band > 0:
                            continue
                        kind = 'poplar' if band == 0 and rng.random() < 0.6 else ('palm' if rng.random() < 0.45 else 'tree')
                        self.tree(kind, q[0], q[1], None, rng.uniform(0.8, 1.2))
        # palms along the canals
        for name, P in LAY['canals'].items():
            S = resample(P, 13.0)
            for i, p in enumerate(S[:-1]):
                u = S[i + 1] - p
                u /= max(np.linalg.norm(u), 1e-6)
                nrm = np.array([-u[1], u[0]])
                for side in (-1, 1):
                    if rng.random() < 0.55:
                        q = p + nrm * side * rng.uniform(7, 11)
                        if G.ht(*q) < 1900:
                            self.tree('palm' if rng.random() < 0.7 else 'tree', q[0], q[1], None, rng.uniform(0.8, 1.15))
        # orchards and palm groves inside the fields, near the water
        for name, poly in LAY['fields'].items():
            Pp = np.asarray(poly)
            xs = rng.uniform(Pp[:, 0].min(), Pp[:, 0].max(), 9000)
            ys = rng.uniform(Pp[:, 1].min(), Pp[:, 1].max(), 9000)
            m = points_in_poly(xs, ys, poly)
            m &= (G._bilinear(G.rd, xs, ys) > 95) & (G._bilinear(G.district_mask, xs, ys) < 0.15)
            for x, y in zip(xs[m], ys[m]):
                if G.slope_at(x, y) > 0.22 or not self.res.free([(x, y)]):
                    continue
                g = fc.vnoise(np.array(x / 260.0), np.array(y / 260.0), 301)
                if g > 0.66:
                    self.tree('tree' if g < 0.8 else 'palm', x, y, None, rng.uniform(0.75, 1.0))
        # desert shrubs, sparse
        xs = rng.uniform(-R, R, 26000)
        ys = rng.uniform(-R, R, 26000)
        for x, y in zip(xs, ys):
            h = G.hs(x, y)
            if G.ht(x, y) > 2300 or G.slope_at(x, y) > 0.45 or not self.res.free([(x, y)]):
                continue
            if float(G.district_mask[int((y + R) / G.step), int((x + R) / G.step)]) > 0.2:
                continue
            if rng.random() < 0.35:
                self.tree('shrub', x, y, h, rng.uniform(0.7, 1.6))
        self.stats['trees'] = len(self.I.rows) - n0

    # ------------------------------------------------------------ everything
    def build(self):
        t0 = time.time()
        self.foam = []
        self.reserve_all()
        fr = LAY['freight']
        self.market(*fr['market'])
        for (x, y, r) in fr['caravanserais']:
            self.caravanserai(x * KM, y * KM, r)
        for (x, y, n, w, d) in fr['granaries']:
            self.granary(x * KM, y * KM, n, w, d)
        for (x, y, w, d) in fr['animal_yards']:
            self.animal_yard(x * KM, y * KM, w, d)
        self.library()
        self.al_mirah()
        self.first_flame()
        self.way_shrines()
        self.bridges_all()
        self.mills()
        self.weirs()
        self.districts()
        self.villages()
        self.caravans()
        self.vegetation()
        self.stats['instances'] = len(self.I.rows)
        self.stats['city_secs'] = round(time.time() - t0, 1)


WOOD_C = (0.40, 0.28, 0.17)


def seg_inter(a, b, c, d):
    a, b, c, d = (np.asarray(p, float) for p in (a, b, c, d))
    r = b - a
    s = d - c
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if 0 <= t <= 1 and 0 <= u <= 1:
        return a + r * t
    return None


# =============================================================================
# Water geometry
# =============================================================================
def ribbon(P, z_of, width, step=14.0):
    """A flat strip along P (metres): returns verts, quads."""
    S = resample(P, step)
    ss = cumlen(S)
    V, F = [], []
    for i, p in enumerate(S):
        u = S[min(i + 1, len(S) - 1)] - S[max(i - 1, 0)]
        u /= max(np.linalg.norm(u), 1e-6)
        nrm = np.array([-u[1], u[0]])
        w = width(ss[i]) if callable(width) else width
        z = z_of(ss[i], p)
        a = p + nrm * w / 2
        b = p - nrm * w / 2
        V += [(a[0], a[1], z), (b[0], b[1], z)]
        if i:
            k = 2 * i
            F.append((k - 2, k - 1, k + 1, k))
    return V, F


def build_water(G, city, coll, mat):
    V, F, D = [], [], []

    def add(v, f, depth):
        b = len(V)
        V.extend(v)
        F.extend([tuple(b + i for i in q) for q in f])
        D.extend([depth] * len(v))
    for rid, rv in LAY['rivers'].items():
        w0 = rv['width']
        v, f = ribbon(rv['xy'], lambda s, p, rv=rv: float(disp(np.interp(s, rv['cum'], rv['z']))) + 0.6,
                      lambda s, rv=rv, w0=w0: w0 * 0.8 * (0.45 + 0.55 * float(smoothstep(2100.0, 1400.0, np.interp(s, rv['cum'], rv['z'])))), 12.0)
        add(v, f, 0.12)
    for name, P in LAY['canals'].items():
        v, f = ribbon(P, lambda s, p: G.hs(p[0], p[1]) + 0.35, 6.0, 12.0)
        add(v, f, 0.05)
    for (x, y, r, z) in city.water:
        n = 20
        b = len(V)
        ring = [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
        add(ring + [(x, y, z)], [(k, (k + 1) % n, n, n) for k in range(n)], 0.08)
    k = 1.0 / MS
    Vm = np.asarray(V, float) * k
    me = bpy.data.meshes.new("CAP_Sea_Rivers")
    me.from_pydata(Vm.tolist(), [], [tuple(dict.fromkeys(f)) for f in F])
    me.update()
    rgba = np.ones((len(V), 4), np.float32)
    rgba[:, 0] = D
    a = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    a.data.foreach_set('color', rgba.ravel())
    da = me.attributes.new('depth', 'FLOAT', 'POINT')
    da.data.foreach_set('value', np.asarray(D, np.float32))
    me.materials.append(mat)
    ob = bpy.data.objects.new("CAP_Sea_Rivers", me)
    coll.objects.link(ob)
    # foam over the weirs (painted white strips)
    mb = MB()
    for (x, y, z, L, ang) in city.foam:
        mb.box(x, y, z - 0.2, L, 5.0, 0.35, ang, (0.93, 0.95, 0.96))
    emit(mb, "CAP_Weir_Foam", coll, [bpy.data.materials["CAP_Painted"]])
    return ob


def emit(mb, name, coll, mats):
    if not mb.f:
        return None
    k = 1.0 / MS
    mb.v = [(x * k, y * k, z * k) for x, y, z in mb.v]
    return mb.to_object(name, coll, mats)


# =============================================================================
# Materials
# =============================================================================
def mat_basin_terrain(img):
    _n = fc._node
    m, nt = fc._new_mat("CAP_Terrain")
    bs, _ = fc._principled(nt, (600, 0))
    tex = _n(nt, 'ShaderNodeTexImage', (-400, 0))
    tex.image = img
    tex.interpolation = 'Linear'
    uv = _n(nt, 'ShaderNodeUVMap', (-700, 0))
    uv.uv_map = "UVMap"
    nt.links.new(uv.outputs['UV'], tex.inputs['Vector'])
    nt.links.new(fc._haze(nt, tex.outputs['Color'], (300, 0)), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.92
    fc._sock(bs.inputs, 'Specular IOR Level').default_value = 0.2
    return m


# =============================================================================
# Orchestration
# =============================================================================
def build_all(out_dir=None):
    t0 = time.time()
    stats = {}
    ANCHORS.clear()
    stats['removed_defaults'] = fc.remove_factory_defaults()
    fc.ROOT_NAME, saved = ROOT_NAME, fc.ROOT_NAME
    fc.clear_previous()
    fc.ROOT_NAME = saved
    root = bpy.data.collections.new(ROOT_NAME)
    bpy.context.scene.collection.children.link(root)
    coll = {k: fc.new_coll(v, root) for k, v in (('terrain', "Terrain & Water"), ('city', "City (real geometry)"),
                                                   ('inst', "Instanced"), ('scene', "Lights & Cameras"))}
    fc.haze_group()
    mats = {'painted': fc.mat_painted(), 'water': fc.mat_water(), 'fire': fc.mat_fire()}
    G = Ground()
    stats['ground_secs'] = G.secs
    stats['height_m'] = [round(float(G.Ht.min())), round(float(G.Ht.max()))]
    city = City(G)
    city.build()
    stats.update(city.stats)
    # the painted ground (also the package's terrain_albedo.png)
    rgb = paint_albedo(G, villages=city.zone_pts.get('villages', []))
    stats['albedo_secs'] = ANCHORS['albedo_secs']
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cities", CFG['id'])
    os.makedirs(out_dir, exist_ok=True)
    alb_path = os.path.join(out_dir, "terrain_albedo.png")
    img = save_png(rgb, alb_path)
    del rgb
    mats['terrain'] = mat_basin_terrain(img)
    k = 1.0 / MS
    Hm = G.H[::MESH_STEP, ::MESH_STEP] * k
    ter = grid_mesh("CAP_Terrain", Hm, -HALF, HALF, -HALF, HALF, coll['terrain'], [mats['terrain']])
    ter["albedo_png"] = alb_path
    build_water(G, city, coll['terrain'], mats['water'])
    # the plinth's sides
    mb = MB()
    Z = G.H[::MESH_STEP, ::MESH_STEP] * k
    n = Z.shape[0]
    xs = np.linspace(-HALF, HALF, n)
    zb = float(G.H.min()) * k - 3.0
    BASE_C = (0.22, 0.13, 0.08)
    for pts, zt, want in (([(x, -HALF) for x in xs], Z[0, :], (0, -1, 0)), ([(HALF, y) for y in xs], Z[:, -1], (1, 0, 0)),
                          ([(x, HALF) for x in xs], Z[-1, :], (0, 1, 0)), ([(-HALF, y) for y in xs], Z[:, 0], (-1, 0, 0))):
        for i in range(len(pts) - 1):
            q = [(pts[i][0], pts[i][1], zb), (pts[i + 1][0], pts[i + 1][1], zb), (pts[i + 1][0], pts[i + 1][1], zt[i + 1]), (pts[i][0], pts[i][1], zt[i])]
            mb.poly_facing(q, want, BASE_C)
    mb.to_object("CAP_Base", coll['terrain'], [mats['painted']])
    # real geometry: bridges' piers and arches, mill wheels, the flame
    emit(city.mb, "CAP_KA_Structures", coll['city'], [mats['painted']])
    emit(city.fire, "CAP_KA_Flame", coll['city'], [mats['fire']])
    # the instances: the table for the Atlas, real meshes for Blender
    A = city.I.array()
    ANCHORS.update({'_G': G, '_city': city, '_root': root, '_inst': A})
    mx, my, mz = city.market_xy
    stats['instance_tris'] = 0
    instance_meshes(A, coll['inst'], mats['painted'], (mx / MS, my / MS))
    # cameras: the hero view is the metropolitan aerial's (from the south-south-east, looking north-west)
    fc.HERO_CAM = ((30.0, -84.0, 46.0), (-6.0, 4.0, 7.0))
    fc.CAMERAS = [("CAP_Cam_" + c[0], c[1], c[2], c[3]) for c in camera_list(G, city)]
    fc.build_scene(coll['scene'], [])
    tri = 0
    for o in root.all_objects:
        if o.type == 'MESH':
            tri += sum(len(p.vertices) - 2 for p in o.data.polygons)
    kinds = {k: int((A[:, 10] == v).sum()) for k, v in KINDS.items()}
    stats.update({'objects': len(root.all_objects), 'approx_tris_blend': tri, 'instances_by_kind': kinds,
                  'population_estimate': population(A), 'total_secs': round(time.time() - t0, 1)})
    return stats


def population(A):
    """Rough residents: 4.5 people per storey of each house (towers count as two households)."""
    h = A[A[:, 10] == KINDS['house'], 5] * MS
    t = A[A[:, 10] == KINDS['tower']]
    return int(round(float(np.sum(np.maximum(1, np.round((h - 1.0) / 3.3))) * 4.5 + len(t) * 9)))


# =============================================================================
# Cameras (the same presets in Blender and in the Atlas)
# =============================================================================
def cam_preset(G, lid, label, xy_km, dist_m, yaw, pitch, z_lift=0.0):
    x, y = xy_km[0] * KM, xy_km[1] * KM
    z = G.hs(x, y) + z_lift
    return {'id': lid, 'label': label, 'camera': {'target': [round(x / MS, 3), round(y / MS, 3), round(z / MS, 3)],
                                                  'dist': round(dist_m / MS, 3), 'yaw': yaw, 'pitch': pitch}}


def landmark_list(G):
    return [
        cam_preset(G, 'overview', "Karn Ashur and its basin", (0.0, 0.6), 30000, -72, 40),
        cam_preset(G, 'caravan_arrival', "The caravan arrival: the freight road and the grain yards", (-3.25, 1.5), 1250, -166, 9, 25),
        cam_preset(G, 'terraces', "The terraced neighbourhoods", (-1.7, -0.5), 3000, -40, 27),
        cam_preset(G, 'downstream', "Downstream over the farming villages", (1.0, -7.9), 3300, 100, 20, 30),
        cam_preset(G, 'market', "The shaded market", (-2.42, 1.72), 700, -105, 36),
        cam_preset(G, 'al_mirah', "Al-Mirah's spring", (-3.54, 2.66), 520, -120, 30),
        cam_preset(G, 'pilgrimage', "The pilgrims' climb to the First Flame", (-4.5, 4.3), 4200, -58, 18, 200),
        cam_preset(G, 'first_flame', "The First Flame", (-5.31, 6.36), 900, -55, 20),
        cam_preset(G, 'library', "The Library of Karn Ashur", (-2.1, 0.23), 650, -75, 32),
        cam_preset(G, 'confluence', "The confluence and the bridges", (0.2, -3.9), 1900, -135, 30),
        cam_preset(G, 'east_peak', "The eastern peak", tuple(CFG['layout']['places']['east_peak']['at']), 7500, -110, 16, 400),
    ]


def camera_list(G, city):
    out = []
    for lm in landmark_list(G):
        c = lm['camera']
        y, p = math.radians(c['yaw']), math.radians(c['pitch'])
        t = c['target']
        pos = (t[0] + c['dist'] * math.cos(p) * math.cos(y), t[1] + c['dist'] * math.cos(p) * math.sin(y), t[2] + c['dist'] * math.sin(p))
        out.append((lm['id'].title().replace('_', ''), pos, t, 30 if lm['id'] in ('overview', 'downstream') else 35))
    return out


# =============================================================================
# Manifest
# =============================================================================
def walk_lines():
    lines = {k: rd['xy'] for k, rd in LAY['roads'].items() if k != 'spring_way'}
    lines['spring_way'] = LAY['roads']['spring_way']['xy']
    lines['climb'] = LAY['climb']
    return lines


def build_graph(G, city, lines, step=90.0, snap=60.0):
    nodes, edges = [], []

    def node_at(p, end):
        if nodes:
            Nn = np.array([n[:2] for n in nodes])
            d = np.linalg.norm(Nn - np.asarray(p[:2]), axis=1)
            i = int(np.argmin(d))
            if d[i] < (snap * 5 if end else snap):         # a line's ends join the network further off
                return i
        z = G.hs(p[0], p[1])
        for a, b, deck, w in city.bridges:                        # on a bridge: walk on the deck
            if dist_to_polyline(np.array([p[0]]), np.array([p[1]]), [tuple(a), tuple(b)])[0] < w:
                z = max(z, deck)
        nodes.append((float(p[0]), float(p[1]), z + 0.4))
        return len(nodes) - 1

    for name, pts in lines.items():
        P = resample(pts, step)
        idx = [node_at(p, i == 0 or i == len(P) - 1) for i, p in enumerate(P)]
        wm = LAY['roads'][name]['width'] if name in LAY['roads'] else 5.0
        for a, b in zip(idx[:-1], idx[1:]):
            if a != b:
                edges.append([a, b, wm])
    # keep the largest connected piece
    adj = {i: set() for i in range(len(nodes))}
    for a, b, _ in edges:
        adj[a].add(b)
        adj[b].add(a)
    seen, best = set(), []
    for s0 in range(len(nodes)):
        if s0 in seen:
            continue
        comp, stack = [], [s0]
        seen.add(s0)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        if len(comp) > len(best):
            best = comp
    keep = sorted(best)
    remap = {o: i for i, o in enumerate(keep)}
    k = 1.0 / MS
    return {'nodes': [[round(nodes[i][0] * k, 3), round(nodes[i][1] * k, 3), round(nodes[i][2] * k, 3)] for i in keep],
            'edges': [[remap[a], remap[b], round(w * k, 3)] for a, b, w in edges if a in remap and b in remap]}


def zone(G, rng, zid, pts_m, n, density, spread=60.0):
    pts = []
    for (x, y, z) in pts_m:
        for _ in range(max(1, n // len(pts_m))):
            px, py = x + rng.normal(0, spread), y + rng.normal(0, spread)
            pts.append([round(px / MS, 3), round(py / MS, 3), round((max(z, G.hs(px, py)) + 0.3) / MS, 3)])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = spread * 2 / MS
    poly = [[min(xs) - pad, min(ys) - pad], [max(xs) + pad, min(ys) - pad], [max(xs) + pad, max(ys) + pad], [min(xs) - pad, max(ys) + pad]]
    return {'id': zid, 'poly': [[round(a, 3), round(b, 3)] for a, b in poly], 'density': density, 'points': pts}


def site_block(G):
    """The basin layout for the Known World patch (kilometres, settlement frame), straight from the config."""
    lay = CFG['layout']
    clean = lambda d: {k.split(' ')[0]: v for k, v in d.items()}
    return {
        'anchor': CFG['world_map']['settlement'], 'units': 'km',
        'plinth_half_km': R / KM,
        'peaks': lay['peaks'], 'cliff_zones': lay['cliff_zones'], 'sand_aprons': lay['sand_aprons'],
        'districts': {k: v['poly'] for k, v in lay['districts'].items()},
        'fields': clean(lay['fields']),
        'rivers': {k: v['pts'] for k, v in lay['rivers'].items()},
        'canals': clean(lay['canals']),
        'roads': {k.split(' ')[0]: v['pts'] for k, v in lay['roads'].items()},
        'pilgrimage_climb': lay['pilgrimage_climb'],
        'places': {k.split(' ')[0]: v for k, v in lay['places'].items()},
        'villages': [[p[0], p[1]] for p in lay['villages (added)']],
        'freight_entry_km': lay['roads']['local_freight_road']['pts'][0],
        'outlet_km': lay['rivers']['southern_outlet']['pts'][-1][:2],
    }


def build_manifest(cfg, report):
    import anchors as A_
    import sunarc
    G = ANCHORS['_G']
    city = ANCHORS['_city']
    rng = np.random.default_rng(23)
    graph = build_graph(G, city, walk_lines())
    report['street_graph'] = {'nodes': len(graph['nodes']), 'edges': len(graph['edges'])}

    def route(pts_km):
        return A_.graph_route(graph, [[p[0] * KM / MS, p[1] * KM / MS] for p in pts_km])
    pl = LAY['places']
    routes = {
        'pilgrimage': route([(-2.42, 1.72), (-3.22, 1.97), (-3.54, 2.66)] + [tuple(np.asarray(p) / KM) for p in LAY['climb'][1:]]),
        'caravan_arrival': route([(-10.0, 0.9), (-6.5, 1.08), (-4.41, 1.65), (-3.2, 1.48), (-2.42, 1.72)]),
        'downstream': route([(1.45, -1.55), (1.9, -2.6), (2.1, -4.15), (1.1, -5.6), (2.75, -7.25), (4.15, -10.0)]),
        'library_to_market': route([(-2.1, 0.23), (-1.3, 0.25), (-1.15, 1.4), (-2.42, 1.72)]),
    }
    for rid, pts in routes.items():
        report.setdefault('routes', {})[rid] = {'points': len(pts), 'length_m': round(A_.polylen(pts) * MS, 1)}
    zp = city.zone_pts
    zones = [zone(G, rng, 'market', zp['market'], 40, 0.9, 40), zone(G, rng, 'caravan_yards', zp['caravan_yards'], 40, 0.7, 25),
             zone(G, rng, 'grain_yards', zp['grain_yards'], 24, 0.6, 40), zone(G, rng, 'al_mirah', zp['al_mirah'], 16, 0.6, 14),
             zone(G, rng, 'library', zp['library'], 14, 0.5, 25), zone(G, rng, 'first_flame', zp['first_flame'], 8, 0.4, 6),
             zone(G, rng, 'villages', zp['villages'], 40, 0.4, 50)]
    lights = []
    for (x, y, z, kind, s) in city.lights:
        lights.append({'pos': [round(x / MS, 3), round(y / MS, 3), round(z / MS, 3)], 'kind': kind, 'strength': s})
    sun = cfg['sun']
    rise, sset = sunarc.sunrise_sunset(sun['latitude_deg'], sun['default_day_of_year'])
    n = 65
    xs = np.linspace(-R, R, n)
    GX, GY = np.meshgrid(xs, xs)
    grid = (G.h(GX, GY) / MS).round(3)
    lo, hi = float(G.Ht.min()) - 10.0, float(G.Ht.max()) + 10.0
    save_height_png(G.Ht, os.path.join(ROOT, "cities", cfg['id'], "terrain_height.png"), lo, hi)
    A = ANCHORS['_inst']
    A.tofile(os.path.join(ROOT, "cities", cfg['id'], "instances.bin"))
    groups = {}
    inv = {v: k for k, v in KINDS.items()}
    for kid in np.unique(A[:, 10]).astype(int):
        idx = np.nonzero(A[:, 10] == kid)[0]
        groups[inv[kid]] = [int(idx[0]), int(len(idx))]
    landmarks = landmark_list(G)
    man = {
        'id': cfg['id'], 'name': cfg['name'], 'version': 1, 'kind': 'metropolis',
        'model_scale': MS, 'extent': [-HALF, -HALF, HALF, HALF], 'sea_level': 0.0,
        'world_map': cfg['world_map'],
        'sun': dict(sun, sunrise_h=round(rise, 3), sunset_h=round(sset, 3)),
        'files': {'model': 'city.glb', 'proxies': 'proxies.glb', 'terrain_albedo': 'terrain_albedo.png', 'thumb': 'thumb.png',
                  'terrain_height': 'terrain_height.png', 'instances': 'instances.bin'},
        'street_graph': graph,
        'spawn_zones': zones,
        'ship_lanes': [], 'moorings': [], 'anchored_ships': [], 'boats': [], 'berths': [],
        'venues': [],
        'routes': routes,
        'night_lights': lights,
        'landmarks': landmarks,
        'steam_vents': [],
        'events': cfg.get('events', []),
        'anchors': {k: [round(v['xy'][0] / MS, 3), round(v['xy'][1] / MS, 3), round(G.hs(*v['xy']) / MS, 3)] for k, v in pl.items()},
        'terrain_grid': {'n': n, 'z': grid.ravel().tolist()},
        'terrain_height': {'file': 'terrain_height.png', 'n': int(G.H.shape[0]), 'min_m': round(lo, 2), 'max_m': round(hi, 2),
                           'model_vertical_exaggeration': VEX, 'model_datum_m': DATUM},
        'instances': {'file': 'instances.bin', 'count': int(len(A)), 'stride': 11,
                      'fields': ['x', 'y', 'z', 'w', 'd', 'h', 'rot', 'r', 'g', 'b', 'kind'],
                      'kinds': KINDS, 'groups': groups, 'protos': {k: p.json() for k, p in protos().items()}},
        'site': site_block(G),
        'stats': {k: v for k, v in report.get('generator', {}).items()},
    }
    report['instances'] = {k: v[1] for k, v in groups.items()}
    report['night_lights'] = len(lights)
    return man


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_proxies(root):
    G = ANCHORS['_G']
    Pc = bpy.data.collections.new("Proxies")
    root.children.link(Pc)
    n = 129
    xs = np.linspace(-R, R, n)
    X, Y = np.meshgrid(xs, xs)
    Z = G.h(X, Y) / MS
    grid_mesh("CAP_Proxy_Terrain", Z, -HALF, HALF, -HALF, HALF, Pc, [], uv=False)
    # the big terraces and buildings (picking, camera collision)
    A = ANCHORS['_inst']
    big = A[(A[:, 10] == KINDS['terrace']) & (A[:, 3] * A[:, 4] * MS * MS > 2500)]
    mb = MB()
    for r in big:
        mb.box(r[0], r[1], r[2], r[3], r[4], r[5], r[6], (0.5, 0.5, 0.5))
    mb.to_object("CAP_Proxy_Terraces", Pc, [])
    Pc.hide_render = True
    Pc.hide_viewport = True
    return Pc
