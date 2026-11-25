"""A floodplain capital on a great river ("kind": "metropolis", "builder": "rivercity"): Haven, capital of Hamen
(generator/cities/haven.json, briefs/haven/brief.md).

The River Flame runs north through the plinth, broad and silt-red. On its east bank the walled inner city: a dense
fabric of courtyard houses (flat-roofed and tiled), quays with arcaded stores and round granaries, Queen Meret's
inland harbour basin, the Dareth Archive, House Selenne's river shrine, and at its heart the three colossal
white-marble stepped pyramid-palaces round a ceremonial plaza on the processional way from the river gate. One stone
bridge crosses to a west-bank suburb. Erros the Founder's outer wall, a vast oval across both banks, encloses
canal-fed fields; feeder canals and sluices run on a grid in the river's own frame, the fields are strips of grain,
flax and clover in every shade from green to gold, farming villages sit on the canals, palms line the banks, and the
desert begins sharply beyond the valley edge.

Same frame and contract as generator/metropolis.py (Karn Ashur): a 20 km plinth at 1:200 centred on the settlement,
real metres while laying out, the houses, walls, pyramids, boats and trees as GPU instances (instances.bin), the
painted ground in terrain_albedo.png, true heights in terrain_height.png, and a `site` block that the Known World
patch (atlas/src/Core/BasinSite.cs) draws as the same city. It reuses metropolis.py's helpers and prototypes.
"""
import json
import math
import os
import time

import bpy
import numpy as np

import fantasy_capital as fc
from fantasy_capital import MB, smoothstep, points_in_poly, dist_to_polyline
import metropolis as mp
from metropolis import (Proto, _box_faces, resample, chaikin, cumlen, rect, mix, Raster, save_png, save_height_png,
                        fast_mesh, grid_mesh, ribbon, emit, Reserve, hash01, zone, build_graph, mat_basin_terrain, KM)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_NAME = "Haven"
HALF = 50.0
N = 1025
MESH_STEP = 2
ALBEDO_PX = 4096
WL = 4.0                     # the river's water level (true metres)
# The barges' channel: a lane each side of the middle (through the bridge's arches at +-75 m), the water gates' booms
# open across the middle, and the traffic on each lane (Atlas.Core.RiverBarges keeps every gap >= min_gap_m).
CHANNEL = {'offset_m': 75.0, 'jitter_m': 4.0, 'gate_m': 135.0,
           'down': {'speed': 0.06, 'count': 26, 'min_gap_m': 320.0, 'length_m': [38.0, 52.0]},
           'up': {'speed': 0.045, 'count': 20, 'min_gap_m': 320.0, 'length_m': [32.0, 46.0]}}
ANCHORS = {}
CFG = {}
LAY = {}

# ---------------------------------------------------------------- palette (sRGB)
SAND = (0.86, 0.68, 0.46)
SAND_D = (0.78, 0.58, 0.38)
SAND_L = (0.92, 0.78, 0.58)
ROCK = (0.62, 0.42, 0.30)
MUD = (0.46, 0.30, 0.22)
RIPARIAN = (0.26, 0.40, 0.15)
PALM_GROUND = (0.30, 0.42, 0.18)
CITY_GROUND = (0.80, 0.68, 0.52)
PAVING = (0.90, 0.84, 0.74)
ROAD = (0.86, 0.76, 0.60)
CROPS = [(0.34, 0.52, 0.16), (0.42, 0.60, 0.18), (0.52, 0.64, 0.20), (0.80, 0.70, 0.26), (0.86, 0.74, 0.30),
         (0.70, 0.62, 0.22), (0.30, 0.47, 0.15), (0.60, 0.66, 0.24), (0.90, 0.80, 0.38), (0.46, 0.56, 0.20)]
ORCHARD = (0.20, 0.34, 0.12)
MARBLE = (0.95, 0.94, 0.90)
MARBLE_SHADE = (0.88, 0.87, 0.83)
LIMESTONE = (0.86, 0.78, 0.64)
WALL_STONE = (0.80, 0.68, 0.50)
WALL_STONE_D = (0.70, 0.57, 0.41)
TERRACOTTA = (0.70, 0.31, 0.20)
GRAIN = (0.88, 0.72, 0.34)
GOLD = (0.93, 0.74, 0.30)
TIMBER = (0.42, 0.29, 0.18)
WALLS = [(0.86, 0.72, 0.52), (0.90, 0.80, 0.62), (0.82, 0.66, 0.46), (0.93, 0.86, 0.72), (0.78, 0.60, 0.42),
         (0.88, 0.76, 0.56), (0.84, 0.70, 0.50)]
WHITEWASH = (0.94, 0.91, 0.84)
CLOTH = [(0.93, 0.89, 0.79), (0.76, 0.24, 0.16), (0.88, 0.64, 0.30), (0.30, 0.42, 0.56), (0.90, 0.84, 0.70),
         (0.72, 0.30, 0.22)]
HULL = (0.46, 0.32, 0.20)
SAIL = (0.94, 0.90, 0.80)
PALM = (0.30, 0.44, 0.18)
TREE = (0.28, 0.42, 0.16)
SHRUB = (0.50, 0.48, 0.30)
WIN_C = (0.13, 0.09, 0.07)
COURT = (0.46, 0.36, 0.26)

KINDS = dict(mp.KINDS, roofhouse=8, marble=9, silo=14, boat=15, barge_grain=16, barge_empty=17)


# =============================================================================
# Config
# =============================================================================
def km(p):
    return (float(p[0]) * KM, float(p[1]) * KM)


def kmpts(pts):
    return [km(p) for p in pts]


def apply_config(cfg):
    global ROOT_NAME
    CFG.clear()
    CFG.update(cfg)
    lay = cfg['layout']
    mp.MS = float(cfg.get('model_scale', 200.0))
    mp.R = HALF * mp.MS
    mp.VEX = float(lay.get('vertical_exaggeration', 2.0))
    mp.DATUM = 0.0
    mp.ROOT_NAME = ROOT_NAME = cfg.get('name', ROOT_NAME)
    mp.KINDS = KINDS
    LAY.clear()
    rv = lay['river']
    P = chaikin(np.array(kmpts(rv['pts'])), 3)
    LAY['river'] = dict(xy=resample(P, 60.0), width=float(rv['width_m']), bed=float(rv.get('bed_m', -3.0)),
                        colour=rv.get('colour', [0.56, 0.22, 0.14]))
    LAY['frame'] = resample(chaikin(np.array(kmpts(rv['pts'])), 4), 150.0)    # the river's frame for canals and fields
    LAY['plain'] = float(lay.get('floodplain_m', 9.0))
    ic = lay['inner_city']
    LAY['inner'] = dict(ic, outline=kmpts(ic['outline']), gates={k: km(v) for k, v in ic['gates'].items()})
    LAY['pyramids'] = [dict(p, xy=km(p['at'])) for p in lay['pyramids']]
    LAY['plaza'] = dict(lay['plaza'], xy=km(lay['plaza']['at']))
    LAY['precinct'] = kmpts(lay['palace_precinct'])
    LAY['bridge'] = dict(lay['bridge'], y=lay['bridge']['y_km'] * KM)
    h = lay['harbour']
    LAY['harbour'] = (h['x0'] * KM, h['x1'] * KM, h['y0'] * KM, h['y1'] * KM)
    LAY['granaries'] = [(g[0] * KM, g[1] * KM, int(g[2])) for g in lay['granaries']]
    LAY['archive'] = dict(lay['archive'], xy=km(lay['archive']['at']))
    LAY['shrine'] = dict(lay['shrine'], xy=km(lay['shrine']['at']))
    LAY['suburb'] = kmpts(lay['west_suburb'])
    ow = lay['outer_wall']
    LAY['outer'] = dict(ow, poly=outer_oval(ow))
    LAY['edge'] = lay['valley_edge_km']
    LAY['canal_cfg'] = lay['canals']
    LAY['village_cfg'] = lay['villages']
    LAY['roads'] = {k: dict(xy=np.array(kmpts(v['pts'])), width=float(v['width_m'])) for k, v in lay['roads'].items()}
    mp.LAY.clear()
    mp.LAY['roads'] = LAY['roads']                 # metropolis.build_graph reads the road widths from here
    LAY['inner']['poly'] = inner_poly()


def outer_oval(ow):
    cx, cy = km(ow['center'])
    rx, ry = ow['rx_km'] * KM, ow['ry_km'] * KM
    pts = []
    for k in range(180):
        a = 2 * math.pi * k / 180
        wob = 1.0 + ow.get('wobble', 0.03) * (math.sin(3 * a + 0.7) * 0.6 + math.sin(5 * a + 2.1) * 0.4)
        pts.append((cx + rx * wob * math.cos(a), cy + ry * wob * math.sin(a)))
    return pts


def river_x(y):
    """The river's centre x (metres) at y (the river runs south to north, monotonic in y)."""
    P = LAY['river']['xy']
    return float(np.interp(y, P[:, 1], P[:, 0]))


def inner_poly():
    """The inner city: the landward outline, closed along the east bank (the quay's back line)."""
    ic = LAY['inner']
    out = list(ic['outline'])
    hw = LAY['river']['width'] / 2
    y0, y1 = out[0][1], out[-1][1]
    bank = [(river_x(y) + hw + ic['quay_m'], y) for y in np.linspace(y1, y0, 40)]
    return out + bank


# =============================================================================
# The river's frame: (along, signed offset east of the river)
# =============================================================================
def frame_coords(X, Y, P=None):
    """Arclength along the river frame and the signed distance from it (+ to the east / right of the flow)."""
    P = LAY['frame'] if P is None else P
    best = np.full(np.shape(X), np.inf)
    sb = np.zeros(np.shape(X))
    side = np.zeros(np.shape(X))
    acc = 0.0
    for a, b in zip(P[:-1], P[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        L = math.sqrt(L2)
        t = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0.0, 1.0)
        ex, ey = X - a[0] - t * dx, Y - a[1] - t * dy
        d = np.hypot(ex, ey)
        m = d < best
        best = np.where(m, d, best)
        sb = np.where(m, acc + t * L, sb)
        side = np.where(m, np.sign(dy * ex - dx * ey + 1e-9), side)    # flow north: + to the east
        acc += L
    return sb, best * side


def frame_point(s, n):
    """(along, offset) -> world metres, on the smoothed frame."""
    P = LAY['frame']
    c = cumlen(P)
    s = np.clip(np.asarray(s, float), 0, c[-1])
    x = np.interp(s, c, P[:, 0])
    y = np.interp(s, c, P[:, 1])
    ds = 120.0
    x2, y2 = np.interp(np.minimum(s + ds, c[-1]), c, P[:, 0]), np.interp(np.minimum(s + ds, c[-1]), c, P[:, 1])
    x1, y1 = np.interp(np.maximum(s - ds, 0), c, P[:, 0]), np.interp(np.maximum(s - ds, 0), c, P[:, 1])
    ux, uy = x2 - x1, y2 - y1
    L = np.maximum(np.hypot(ux, uy), 1e-6)
    ux, uy = ux / L, uy / L
    return x + uy * n, y - ux * n          # right of the flow (east for a northward river)


def valley_edges(y):
    """West and east valley edges (metres x) at y: the green ends, the desert begins."""
    e = LAY['edge']
    w = e['west'] * KM + 700.0 * (fc.fbm(np.asarray(y) / 4200.0, 3.1, 3, 41) - 0.5) + 350.0 * np.sin(np.asarray(y) / 2300.0)
    ee = e['east'] * KM + 800.0 * (fc.fbm(np.asarray(y) / 4200.0, 7.7, 3, 42) - 0.5) - 300.0 * np.sin(np.asarray(y) / 2700.0 + 1.0)
    return w, ee


# =============================================================================
# The ground
# =============================================================================
class Ground(mp.Ground):
    """Heights (true metres) on an N x N grid; the model's ground is exaggerated VEX times about sea level."""

    def __init__(self):
        t0 = time.time()
        R = mp.R
        xs = np.linspace(-R, R, N)
        self.xs = xs
        self.step = xs[1] - xs[0]
        X, Y = np.meshgrid(xs, xs)
        self.X, self.Y = X, Y
        Ht = self.heights(X, Y)
        self.Ht = Ht
        self.H = mp.disp(Ht)
        gy, gx = np.gradient(Ht, self.step)
        self.gx, self.gy = gx, gy
        self.slope = np.hypot(gx, gy)
        self.bed = np.full(X.shape, LAY['river']['bed'])
        self.secs = round(time.time() - t0, 2)

    def heights(self, X, Y):
        Xk, Yk = X / KM, Y / KM
        rv = LAY['river']
        hw = rv['width'] / 2
        d, s = mp.seg_nearest(X, Y, rv['xy'])
        self.rd = d
        self.river_id = np.zeros(X.shape, np.int8)
        plain = LAY['plain'] - 0.16 * Yk + 0.5 * (fc.fbm(Xk / 1.3, Yk / 1.3, 3, 11) - 0.5)
        # levees along the banks, a low silt shelf at the water's edge
        H = plain + 1.4 * np.exp(-((d - hw - 160.0) / 230.0) ** 2)
        shelf = WL + 0.4 + (plain - WL - 0.4) * smoothstep(hw - 5.0, hw + 70.0, d)
        H = np.where(d < hw + 70.0, np.minimum(H, shelf), H)
        # the channel
        H = np.where(d < hw, rv['bed'] + (WL + 0.4 - rv['bed']) * smoothstep(hw * 0.7, hw - 5.0, d), H)
        # the inner city stands on its old mound
        cm = mp.soft_poly(X, Y, LAY['inner']['poly'], 260.0) * smoothstep(hw + 40.0, hw + 220.0, d)
        self.city_mask = cm
        H = H + 2.6 * cm
        self.suburb_mask = mp.soft_poly(X, Y, LAY['suburb'], 160.0) * smoothstep(hw + 40.0, hw + 160.0, d)
        H = H + 1.2 * self.suburb_mask
        # the desert beyond the valley edges: a sharp step up, then dunes and rocky rises
        w_e, e_e = valley_edges(Y)
        out = np.maximum(w_e - X, X - e_e)
        self.desert = smoothstep(-120.0, 260.0, out)
        dunes = 5.0 * np.sin((X * 0.62 + Y * 0.78) / 95.0 + 4.0 * fc.fbm(Xk * 2, Yk * 2, 3, 71)) * fc.fbm(Xk * 3, Yk * 3, 2, 72)
        rise = 3.0 + 0.014 * np.maximum(out, 0) + dunes + 46.0 * smoothstep(0.55, 0.85, fc.fbm(Xk / 2.2 + 4, Yk / 2.2, 4, 73)) * smoothstep(400, 2600, out)
        H = H + rise * self.desert
        # the harbour basin
        x0, x1, y0, y1 = LAY['harbour']
        hb = (X > x0) & (X < x1) & (Y > y0) & (Y < y1)
        self.harbour = hb
        H = np.where(hb, rv['bed'] + 0.5, H)
        mouth = (X > river_x(0.5 * (y0 + y1)) - 10) & (X < x0 + 5) & (Y > y0 + 0.3 * (y1 - y0)) & (Y < y1 - 0.3 * (y1 - y0))
        H = np.where(mouth, rv['bed'] + 0.5, H)
        self.harbour |= mouth
        self.district_mask = np.maximum(cm, self.suburb_mask)
        self.cliff_mask = np.zeros(X.shape)
        self.apron_mask = np.zeros(X.shape)
        return H

    def river_d(self, x, y):
        return self._bilinear(self.rd, x, y)


# =============================================================================
# Canals (the river's frame)
# =============================================================================
def make_canals():
    """Trunk canals along the river at fixed offsets and feeder canals across, every `spacing` along it, from the
    bank to the valley edge. Each is a polyline (metres); the parts in the city and the desert are cut out."""
    cc = LAY['canal_cfg']
    P = LAY['frame']
    L = cumlen(P)[-1]
    hw = LAY['river']['width'] / 2
    inner = LAY['inner']['poly']
    sub = LAY['suburb']

    def ok(x, y):
        w_e, e_e = valley_edges(y)
        if x < w_e + 150 or x > e_e - 150 or abs(x) > mp.R - 60 or abs(y) > mp.R - 60:
            return False
        if points_in_poly(np.array([x]), np.array([y]), inner)[0] or points_in_poly(np.array([x]), np.array([y]), sub)[0]:
            return False
        return True

    def split(pts):
        out, cur = [], []
        for p in pts:
            if ok(*p):
                cur.append(p)
            else:
                if len(cur) > 3:
                    out.append(np.array(cur))
                cur = []
        if len(cur) > 3:
            out.append(np.array(cur))
        return out

    canals = []
    trunks = sorted(cc['trunk_offsets_km'])
    for n0 in trunks:
        s = np.arange(0, L, 80.0)
        wig = 60.0 * np.sin(s / 1900.0 + n0)
        x, y = frame_point(s, n0 * KM + wig)
        canals += [('trunk', c) for c in split(list(zip(x, y)))]
    sp = cc['spacing_km'] * KM
    for k, s0 in enumerate(np.arange(sp * 0.5, L, sp)):
        for side in (-1, 1):
            far = (trunks[0] if side < 0 else trunks[-1]) * KM * 1.6
            n = np.arange(hw + 30.0, abs(far), 70.0) * side
            x, y = frame_point(np.full(n.shape, s0 + 90.0 * math.sin(k * 1.7)), n)
            for c in split(list(zip(x, y))):
                canals.append(('feeder', c))
    return canals


# =============================================================================
# Painting the ground
# =============================================================================
def paint_albedo(G, city, px=ALBEDO_PX):
    t0 = time.time()
    R = mp.R
    Rs = Raster(px)
    X, Y = np.meshgrid(Rs.c, Rs.c)
    X = X.astype(np.float32)
    Y = Y.astype(np.float32)
    Xk, Yk = X / KM, Y / KM
    n1 = fc.fbm(Xk / 1.8, Yk / 1.8, 4, 101).astype(np.float32)
    n2 = fc.fbm(Xk * 3.0, Yk * 3.0, 3, 102).astype(np.float32)
    n3 = fc.vnoise(X / 9.0, Y / 9.0, 103).astype(np.float32)
    # desert sand, ripples and rock
    col = mix(mix(np.full(X.shape + (3,), SAND, np.float32), SAND_D, smoothstep(0.35, 0.65, n1)), SAND_L, 0.5 * smoothstep(0.55, 0.8, n2))
    rip = 0.5 + 0.5 * np.sin((X * 0.62 + Y * 0.78) / 6.0 + 6.0 * n2)
    col *= (0.93 + 0.08 * rip + 0.06 * n3)[..., None]
    H = G.up(G.Ht, px).astype(np.float32)
    col = mix(col, ROCK, smoothstep(30.0, 52.0, H) * 0.7)
    desert = G.up(G.desert, px).astype(np.float32)
    rd = G.up(G.rd, px).astype(np.float32)
    citym = G.up(G.city_mask, px).astype(np.float32)
    sub = G.up(G.suburb_mask, px).astype(np.float32)
    green = 1.0 - desert
    # the valley's base: irrigated meadow, a little darker near the water
    meadow = np.asarray(RIPARIAN, np.float32) * (0.95 + 0.3 * n2[..., None])
    col = mix(col, meadow, green * 0.92)
    # fields: strips in the river's frame, cells between the feeder canals
    s_g, n_g = frame_coords(G.X[::4, ::4], G.Y[::4, ::4])
    Ns = s_g.shape[0]

    def up(A):
        u = (np.arange(px) + 0.5) / px * (Ns - 1)
        i = np.clip(np.floor(u).astype(int), 0, Ns - 2)
        t = (u - i)[None, :]
        rows = A[:, i] * (1 - t) + A[:, i + 1] * t
        tj = (u - i)[:, None]
        return (rows[i, :] * (1 - tj) + rows[i + 1, :] * tj).astype(np.float32)
    S = up(s_g)
    Nn = up(n_g)
    sp = LAY['canal_cfg']['spacing_km'] * KM
    u = S + 25.0 * (fc.fbm(X / 600.0, Y / 600.0, 2, 131) - 0.5)
    v = Nn + 25.0 * (fc.fbm(X / 600.0 + 5, Y / 600.0, 2, 132) - 0.5)
    PU, PV = sp / 3.0, 330.0                              # plots: three between feeders, 330 m across
    cell_u = np.floor(u / PU)
    cell_v = np.floor(v / PV)
    h0 = fc._hash(cell_u.astype(np.int64), cell_v.astype(np.int64), 160)
    strip_w = 70.0 + 70.0 * fc._hash(cell_u.astype(np.int64), cell_v.astype(np.int64), 161)
    iv = np.floor((v - cell_v * PV) / strip_w)
    h1 = fc._hash(cell_u.astype(np.int64) * 13 + iv.astype(np.int64), cell_v.astype(np.int64), 162)
    k0 = (h0 * len(CROPS)).astype(int)
    alt = np.where(h1 > 0.62, 1 + (h0 * 7).astype(int) % 3, 0)          # most strips share the plot's crop
    crop = np.asarray(CROPS, np.float32)[(k0 + alt) % len(CROPS)]
    crop *= (0.95 + 0.07 * n3 + 0.06 * (fc.fbm(X / 90.0, Y / 90.0, 2, 163) - 0.5))[..., None]
    orch = h0 > 0.93
    dots = fc.vnoise(X / 7.0, Y / 7.0, 171) > 0.45
    crop = np.where(orch[..., None], np.where(dots[..., None], np.asarray(PALM) * 0.95, np.asarray(CROPS[0]) * 1.05), crop)
    fu = u / PU - cell_u
    fv = (v - cell_v * PV) / strip_w - iv
    border = (np.minimum(fu, 1 - fu) * PU < 4.0) | (np.minimum(fv, 1 - fv) * strip_w < 1.0)
    crop = np.where(border[..., None], crop * 0.84, crop)
    hedge = (np.minimum(np.minimum(fu, 1 - fu) * PU, np.minimum((v - cell_v * PV), PV - (v - cell_v * PV))) < 6.0)
    crop = np.where(hedge[..., None], np.asarray(RIPARIAN, np.float32) * 1.1, crop)
    hw = LAY['river']['width'] / 2
    fieldw = green * smoothstep(hw + 120.0, hw + 220.0, rd) * (1 - smoothstep(0.15, 0.45, citym)) * (1 - smoothstep(0.15, 0.45, sub))
    edge_fade = smoothstep(0.0, 0.25, 1.0 - smoothstep(0.0, 0.85, desert + 0.25 * (n1 - 0.5)))
    col = mix(col, crop, fieldw * edge_fade)
    # palm groves and banks along the river
    bank = green * (1 - smoothstep(hw + 60.0, hw + 200.0, rd)) * smoothstep(hw - 10.0, hw + 30.0, rd) * (1 - citym)
    col = mix(col, np.asarray(PALM_GROUND) * (0.85 + 0.3 * n3[..., None]), bank * 0.85)
    # the red silt shelf and the river bed (under the water)
    col = mix(col, MUD, 1 - smoothstep(hw - 6.0, hw + 18.0, rd))
    # the city: dusty ground and lanes (the houses cover most of it)
    col = mix(col, CITY_GROUND, smoothstep(0.25, 0.6, citym))
    col = mix(col, CITY_GROUND, smoothstep(0.25, 0.6, sub))
    # canals: a green margin, the red water
    for kind, P in LAY['canals']:
        D = Rs.dist(P, 30.0)
        wdt = 7.0 if kind == 'trunk' else 4.5
        col = mix(col, RIPARIAN, (1.0 - smoothstep(wdt, wdt + 10.0, D)) * 0.75)
        col = mix(col, np.asarray(LAY['river']['colour']) * 0.9, 1.0 - smoothstep(wdt * 0.45, wdt * 0.6, D))
    # roads, the plaza, the processional way
    for name, rd_ in LAY['roads'].items():
        D = Rs.dist(rd_['xy'], rd_['width'])
        c = PAVING if name in ('processional_way', 'quay_road') else ROAD
        col = mix(col, c, (1.0 - smoothstep(rd_['width'] * 0.32, rd_['width'] * 0.5, D)))
    pl = LAY['plaza']
    col = mix(col, PAVING, Rs.poly(rect(pl['xy'][0], pl['xy'][1], pl['w_m'], pl['d_m'], 0.0)).astype(np.float32))
    pp = Rs.poly(LAY['precinct']).astype(np.float32)
    col = mix(col, (0.84, 0.78, 0.66), pp * 0.85)
    # the walls' footprints: the outer wall's stone and the track along its foot, the inner wall
    D = Rs.dist(LAY['outer']['poly'] + [LAY['outer']['poly'][0]], 60.0)
    col = mix(col, ROAD, (1.0 - smoothstep(14.0, 30.0, D)) * green * 0.85)
    col = mix(col, (0.78, 0.66, 0.50), 1.0 - smoothstep(6.0, 9.0, D))
    D = Rs.dist(LAY['inner']['poly'] + [LAY['inner']['poly'][0]], 40.0)
    col = mix(col, (0.80, 0.70, 0.54), 1.0 - smoothstep(8.0, 14.0, D))
    # the villages: beaten earth, threshing floors
    for (vx, vy, r) in city.village_pts:
        w = Rs.window(vx - r - 120, vx + r + 120, vy - r - 120, vy + r + 120)
        if w is None:
            continue
        sl, Xw, Yw = w
        rr = np.hypot(Xw - vx, Yw - vy) * (1.0 + 0.25 * (fc.fbm(Xw / 60.0, Yw / 60.0, 2, 190) - 0.5))
        col[sl] = mix(col[sl], ORCHARD, ((1.0 - smoothstep(r + 50, r + 100, rr)) * smoothstep(r - 10, r + 30, rr) * 0.75).astype(np.float32))
        col[sl] = mix(col[sl], (0.84, 0.72, 0.54), (1.0 - smoothstep(r * 0.85, r, rr)).astype(np.float32))
    ANCHORS['albedo_secs'] = round(time.time() - t0, 1)
    return np.clip(col, 0.0, 1.0)


# =============================================================================
# Prototypes (Haven's own, beside metropolis.py's)
# =============================================================================
def proto_roofhouse():
    """A courtyard house under a low hipped terracotta roof (the concepts' red roofs)."""
    p = Proto()
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0, 0.74, top=None))
    V = [(-0.53, -0.53, 0.74), (0.53, -0.53, 0.74), (0.53, 0.53, 0.74), (-0.53, 0.53, 0.74), (-0.2, 0.0, 1.0), (0.2, 0.0, 1.0)]
    p.add(V, [((0, 1, 5, 4), 'abs', TERRACOTTA), ((1, 2, 5), 'abs', tuple(c * 0.86 for c in TERRACOTTA)),
              ((2, 3, 4, 5), 'abs', tuple(c * 1.08 for c in TERRACOTTA)), ((3, 0, 4), 'abs', tuple(c * 0.92 for c in TERRACOTTA))])
    for x in (-0.24, 0.2):
        p.add([(x - 0.05, -0.502, 0.36), (x + 0.05, -0.502, 0.36), (x + 0.05, -0.502, 0.52), (x - 0.05, -0.502, 0.52)],
              [((0, 1, 2, 3), 'win', WIN_C)])
    return p


def proto_marble():
    """A pyramid tier: a dressed block with a band of doorways (the occupied halls), lit at night."""
    p = Proto()
    p.add(*_box_faces(-0.5, 0.5, -0.5, 0.5, 0, 1, shade=(0.93, 0.86, 0.97, 0.9), top=1.03))
    for (ax, ay, nx, ny) in ((0, -0.502, 1, 0), (0.502, 0, 0, 1), (0, 0.502, -1, 0), (-0.502, 0, 0, -1)):
        for k in range(5):
            t = -0.36 + 0.18 * k
            cx, cy = ax + nx * t, ay + ny * t
            p.add([(cx - nx * 0.03, cy - ny * 0.03, 0.18), (cx + nx * 0.03, cy + ny * 0.03, 0.18),
                   (cx + nx * 0.03, cy + ny * 0.03, 0.62), (cx - nx * 0.03, cy - ny * 0.03, 0.62)],
                  [((0, 1, 2, 3), 'win', WIN_C)])
    return p


def proto_silo():
    """A round granary: a drum and a domed cap."""
    p = Proto()
    n = 12
    ring0 = [(0.5 * math.cos(2 * math.pi * k / n), 0.5 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    V = [(x, y, 0.0) for x, y in ring0] + [(x, y, 0.66) for x, y in ring0]
    F = [((k, (k + 1) % n, n + (k + 1) % n, n + k), 'tint', 0.84 + 0.16 * math.cos(2 * math.pi * (k + 0.5) / n - 0.8)) for k in range(n)]
    p.add(V, F)
    V, F = [], []
    lat = 3
    for i in range(lat + 1):
        a = (math.pi / 2) * i / (lat + 1)
        r = 0.5 * math.cos(a)
        z = 0.66 + 0.34 * math.sin(a)
        V += [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    V.append((0, 0, 1.0))
    for i in range(lat):
        for k in range(n):
            k2 = (k + 1) % n
            F.append(((i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k), 'tint', 1.06 - 0.04 * i))
    top = (lat + 1) * n
    for k in range(n):
        F.append(((lat * n + k, lat * n + (k + 1) % n, top), 'tint', 1.1))
    p.add(V, F)
    return p


def proto_boat():
    """A river barge (length along local x, bow at +x) with a mast and a square sail across it."""
    p = Proto()
    V = [(-0.5, -0.32, 0.12), (0.34, -0.5, 0.12), (0.5, 0.0, 0.2), (0.34, 0.5, 0.12), (-0.5, 0.32, 0.12),
         (-0.44, -0.24, 0.0), (0.3, -0.36, 0.0), (0.42, 0.0, 0.05), (0.3, 0.36, 0.0), (-0.44, 0.24, 0.0)]
    F = [((5, 6, 1, 0), 'tint', 0.8), ((6, 7, 2, 1), 'tint', 0.76), ((7, 8, 3, 2), 'tint', 0.84), ((8, 9, 4, 3), 'tint', 0.8),
         ((9, 5, 0, 4), 'tint', 0.7), ((0, 1, 2, 3, 4), 'tint', 1.12)]
    p.add(V, F)
    p.add(*_box_faces(-0.3, -0.04, -0.22, 0.22, 0.12, 0.22, top=1.0))                           # the cargo
    p.add(*_box_faces(0.04, 0.08, -0.02, 0.02, 0.12, 1.0, mode='abs', shade=((0.32, 0.22, 0.14),) * 4, top=None))
    p.add([(0.06, -0.46, 0.38), (0.06, 0.46, 0.38), (0.06, 0.42, 0.98), (0.06, -0.42, 0.98)],
          [((0, 1, 2, 3), 'abs', SAIL), ((3, 2, 1, 0), 'abs', tuple(c * 0.86 for c in SAIL))])
    return p


def _hull(p, deck=0.16):
    """A flat-bottomed river barge's hull (length along local x, bow at +x) with a raised stern and a plank deck."""
    V = [(-0.5, -0.42, deck), (0.36, -0.5, deck), (0.5, 0.0, deck + 0.06), (0.36, 0.5, deck), (-0.5, 0.42, deck),
         (-0.46, -0.34, 0.0), (0.32, -0.4, 0.0), (0.44, 0.0, 0.04), (0.32, 0.4, 0.0), (-0.46, 0.34, 0.0)]
    F = [((5, 6, 1, 0), 'tint', 0.8), ((6, 7, 2, 1), 'tint', 0.74), ((7, 8, 3, 2), 'tint', 0.86), ((8, 9, 4, 3), 'tint', 0.8),
         ((9, 5, 0, 4), 'tint', 0.7), ((0, 1, 2, 3, 4), 'abs', TIMBER)]
    p.add(V, F)
    # gunwales: a dark rail round the deck
    for (x0, x1, y0, y1) in ((-0.5, 0.36, -0.47, -0.41), (-0.5, 0.36, 0.41, 0.47)):
        p.add(*_box_faces(x0, x1, y0, y1, deck, deck + 0.04, mode='abs', shade=((0.30, 0.20, 0.12),) * 4, top=None))
    # the stern deckhouse and the steering oar
    p.add(*_box_faces(-0.49, -0.36, -0.26, 0.26, deck, deck + 0.13, top=1.0))
    p.add(*_box_faces(-0.53, -0.47, -0.02, 0.02, deck - 0.12, deck + 0.18, mode='abs', shade=((0.30, 0.20, 0.12),) * 4, top=None))


def _heap(p, cx, rx, ry, z0, h, col):
    """A heap of loose grain: an oval mound of eight faces round a ridge."""
    n = 8
    ring = [(cx + rx * math.cos(2 * math.pi * k / n), ry * math.sin(2 * math.pi * k / n), z0) for k in range(n)]
    mid = [(cx + 0.62 * rx * math.cos(2 * math.pi * (k + 0.5) / n), 0.62 * ry * math.sin(2 * math.pi * (k + 0.5) / n), z0 + 0.62 * h) for k in range(n)]
    V = ring + mid + [(cx - 0.2 * rx, 0.0, z0 + h), (cx + 0.2 * rx, 0.0, z0 + h)]
    F = []
    for k in range(n):
        lit = 0.9 + 0.12 * math.cos(2 * math.pi * (k + 0.5) / n - 2.2)
        c = tuple(min(1.0, v * lit) for v in col)
        F.append(((k, (k + 1) % n, n + k), 'abs', c))
        F.append((((k + 1) % n, n + (k + 1) % n, n + k), 'abs', c))
        top = 2 * n + (1 if math.cos(2 * math.pi * (k + 0.5) / n) > 0 else 0)
        F.append(((n + k, n + (k + 1) % n, top), 'abs', tuple(min(1.0, v * (lit + 0.06)) for v in col)))
    F.append(((2 * n, 2 * n + 1, n + 2), 'abs', col))          # close the ridge's ends
    F.append(((2 * n + 1, 2 * n, n + 6), 'abs', col))
    p.add(V, F)


def proto_barge_grain():
    """A grain barge low in the water bound downstream: three golden heaps of wheat on deck, the mast lowered along it.
    Scaled by (length, 0.3 x length, 0.5 x length)."""
    p = Proto()
    _hull(p)
    for cx, rx in ((-0.18, 0.17), (0.06, 0.15), (0.27, 0.12)):
        _heap(p, cx, rx, 0.38, 0.2, 0.34 if cx < 0.2 else 0.28, GRAIN)
    # sheaves bound at the deck's edge, and the mast lying on the heaps
    for k in range(5):
        x = -0.3 + 0.14 * k
        for sy in (-1, 1):
            p.add(*_box_faces(x - 0.04, x + 0.04, sy * 0.36 - 0.04, sy * 0.36 + 0.04, 0.18, 0.27, mode='abs', shade=((0.80, 0.64, 0.30),) * 4, top_col=(0.90, 0.75, 0.38)))
    p.add(*_box_faces(-0.34, 0.42, -0.015, 0.015, 0.52, 0.55, mode='abs', shade=((0.32, 0.22, 0.14),) * 4, top=None))
    return p


def proto_barge_empty():
    """An empty barge sailing back upstream on the north wind: a bare deck, a tall mast, a broad square sail.
    Scaled by (length, 0.3 x length, 0.5 x length)."""
    p = Proto()
    _hull(p)
    for x in (-0.2, 0.0, 0.2):                                                      # deck beams and hatch boards
        p.add(*_box_faces(x - 0.03, x + 0.03, -0.4, 0.4, 0.16, 0.19, mode='abs', shade=((0.36, 0.25, 0.15),) * 4, top=None))
    p.add(*_box_faces(0.06, 0.1, -0.03, 0.03, 0.16, 1.0, mode='abs', shade=((0.32, 0.22, 0.14),) * 4, top=None))
    p.add(*_box_faces(0.1, 0.12, -0.62, 0.62, 0.92, 0.95, mode='abs', shade=((0.32, 0.22, 0.14),) * 4, top=None))   # the yard
    # the sail: bellied forward (the wind from astern, from the north, as they sail south)
    p.add([(0.12, -0.6, 0.92), (0.12, 0.6, 0.92), (0.2, 0.56, 0.62), (0.2, -0.56, 0.62), (0.13, 0.52, 0.34), (0.13, -0.52, 0.34)],
          [((0, 1, 2, 3), 'abs', SAIL), ((3, 2, 4, 5), 'abs', tuple(c * 0.95 for c in SAIL)),
           ((3, 2, 1, 0), 'abs', tuple(c * 0.84 for c in SAIL)), ((5, 4, 2, 3), 'abs', tuple(c * 0.8 for c in SAIL))])
    return p


PROTOS = {}


def protos():
    if not PROTOS:
        PROTOS.update(mp.protos())
        PROTOS.update({'roofhouse': proto_roofhouse(), 'marble': proto_marble(), 'silo': proto_silo(), 'boat': proto_boat(),
                       'barge_grain': proto_barge_grain(), 'barge_empty': proto_barge_empty()})
        mp.PROTOS.update(PROTOS)
    return PROTOS


# =============================================================================
# The city
# =============================================================================
class City(mp.City):
    def __init__(self, G):
        super().__init__(G)
        self.rng = np.random.default_rng(2611)
        self.village_pts = []
        self.foam = []
        self.boats = 0
        self.pyramid_tops = {}
        self.booms = []           # the water gates' booms either side of the channel (metres)
        self.piers = []           # the bridge's piers and cutwaters: (x, y, half x, half y)
        self.moored = []          # moored barges: (xy, length)
        self.traffic = None

    def wall_col(self, x, y):
        r = self.rng.random()
        c = WHITEWASH if r < 0.1 else WALLS[int(self.rng.integers(len(WALLS)))]
        return tuple(np.clip(np.asarray(c) + self.rng.normal(0, 0.02, 3), 0, 1))

    def house(self, x, y, z, w, d, h, ang, col=None, tiled=None):
        col = col or self.wall_col(x, y)
        if tiled is None:
            tiled = self.rng.random() < 0.38
        if tiled:
            self.I.add('roofhouse', x, y, z, w, d, h * 1.18, ang, col)
        else:
            self.I.add('house', x, y, z, w, d, h, ang, col)

    # ------------------------------------------------------------ reserves
    def reserve_all(self):
        rv = LAY['river']
        self.res.line(rv['xy'], rv['width'] / 2 + LAY['inner']['quay_m'] - 6.0)
        x0, x1, y0, y1 = LAY['harbour']
        self.res.poly([(x0 - 30, y0 - 30), (x1 + 30, y0 - 30), (x1 + 30, y1 + 30), (x0 - 30, y1 + 30)])
        self.res.poly([(river_x(y0) , y0 + 200), (x0, y0 + 200), (x0, y1 - 200), (river_x(y1), y1 - 200)])
        for kind, P in LAY['canals']:
            self.res.line(P, 14.0)
        for name, rd in LAY['roads'].items():
            self.res.line(rd['xy'], rd['width'] * 0.5 + 4.0)
        pl = LAY['plaza']
        self.res.rect(pl['xy'][0], pl['xy'][1], pl['w_m'], pl['d_m'], 0.0, 10.0)
        for p in LAY['pyramids']:
            self.res.rect(p['xy'][0], p['xy'][1], p['base_m'], p['base_m'], 0.0, 40.0)
            if p.get('royal'):                                  # the royal court inside its own wall
                side = p['base_m'] + 2 * p['royal']['court_m']
                self.res.rect(p['xy'][0], p['xy'][1], side, side, 0.0, 30.0)
        ii = LAY['inner']['poly']
        for a, b in zip(ii, ii[1:] + ii[:1]):
            self.res.line([a, b], 16.0)

    # ------------------------------------------------------------ the pyramids
    def pyramid(self, p):
        x, y = p['xy']
        b, Ht, T = float(p['base_m']), float(p['height_m']), int(p['tiers'])
        z0 = self.G.hs(x, y)
        top_side = 0.24 * b
        th = Ht / T
        face = {'west': math.pi, 'east': 0.0, 'north': math.pi / 2, 'south': -math.pi / 2}[p.get('stair_face', 'west')]
        ux, uy = math.cos(face), math.sin(face)
        # a low podium, the tiers
        self.I.add('marble', x, y, z0 - 2.0, b + 34, b + 34, 3.2, 0.0, MARBLE_SHADE)
        royal = p.get('royal')
        for k in range(T):
            side = b - (b - top_side) * k / max(1, T - 1)
            z = z0 + 1.2 + k * th
            self.I.add('marble', x, y, z, side, side, th + 0.4, 0.0, MARBLE if k % 2 == 0 else MARBLE_SHADE)
            if royal:
                # a gilded frieze round each tier's brow, and a colonnade along the terrace above it
                for (cu, cv, w, d) in ((0, -1, side + 1.2, 1.4), (0, 1, side + 1.2, 1.4), (-1, 0, 1.4, side + 1.2), (1, 0, 1.4, side + 1.2)):
                    self.I.add('wall', x + cu * side / 2, y + cv * side / 2, z + th - 1.6, w, d, 2.4, 0.0, GOLD)
                nxt = b - (b - top_side) * (k + 1) / max(1, T - 1) if k + 1 < T else side * 0.8
                ring = (side + nxt) / 4 + 1.5                   # half-way across the terrace
                if ring - nxt / 2 > 5.0:
                    nc = max(4, int(2 * ring / 16.0))
                    for c in range(nc + 1):
                        t = -ring + 2 * ring * c / nc
                        for (cx_, cy_) in ((x + t, y - ring), (x + t, y + ring), (x - ring, y + t), (x + ring, y + t)):
                            if abs(cx_ - x - ux * ring) < 0.1 * b and abs(cy_ - y - uy * ring) < 0.1 * b:
                                continue                        # the stair passes through
                            self.I.add('wall', cx_, cy_, z + th + 0.2, 2.2, 2.2, 8.0, 0.0, MARBLE)
            for c in range(4):                                         # lamps at the tier corners
                a = math.pi / 4 + c * math.pi / 2
                if k % 2 == 1:
                    self.light(x + side * 0.5 * math.cos(a) * 1.414, y + side * 0.5 * math.sin(a) * 1.414, z + th + 1.0, 'lamp', 0.5)
        # the great stair up the face: one flight per tier, broad at the foot
        sw = 0.17 * b
        for k in range(T):
            side = b - (b - top_side) * k / max(1, T - 1)
            nxt = b - (b - top_side) * (k + 1) / max(1, T - 1) if k + 1 < T else side
            r0 = side / 2 + 0.06 * b                     # the stair reaches out past the tier's edge
            r1 = nxt / 2
            for j in range(6):
                t = j / 6.0
                r = r0 + (r1 - r0) * t
                rr = r0 + (r1 - r0) * (t + 1 / 6.0)
                cx, cy = x + ux * (r + rr) / 2, y + uy * (r + rr) / 2
                z = z0 + 1.2 + k * th
                self.I.add('marble', cx, cy, z - 0.5, abs(rr - r) * abs(ux) + sw * abs(uy) + 0.5, abs(rr - r) * abs(uy) + sw * abs(ux) + 0.5,
                           th * (j + 1) / 6.0 + 0.5, 0.0, MARBLE_SHADE)
            for side_s in (-1, 1):                     # torches up the stair's sides
                q = (x + ux * r0 - uy * side_s * sw * 0.55, y + uy * r0 + ux * side_s * sw * 0.55)
                self.light(q[0], q[1], z0 + 1.2 + k * th + 3.0, 'torch', 0.6)
        # the summit hall: the palace's upper court, a colonnade and a tiled roof
        zt = z0 + 1.2 + T * th
        hall = top_side * 0.62
        if royal:
            # the throne hall: a white palace court under a great gilded dome, gilded pavilions at its corners
            self.I.add('house', x, y, zt, hall * 1.15, hall * 1.15, 18.0, face, WHITEWASH)
            self.I.add('dome', x, y, zt + 17.5, hall * 0.5, hall * 0.5, hall * 0.42, 0.0, GOLD)
            for c in range(4):
                a = math.pi / 4 + c * math.pi / 2
                qx, qy = x + hall * 0.5 * math.cos(a) * 1.414, y + hall * 0.5 * math.sin(a) * 1.414
                self.I.add('tower', qx, qy, zt, 12.0, 12.0, 26.0, 0.0, MARBLE)
                self.I.add('dome', qx, qy, zt + 25.5, 12.5, 12.5, 11.0, 0.0, GOLD)
                self.light(qx, qy, zt + 30.0, 'torch', 0.9)
        else:
            self.I.add('roofhouse', x, y, zt, hall, hall * 0.72, 16.0, face + math.pi / 2, WHITEWASH, )
        for k in range(10):
            t = -0.45 + 0.1 * k
            for sv in (-1, 1):
                cx = x + (-uy) * t * top_side * 0.9 + ux * sv * top_side * 0.42
                cy = y + ux * t * top_side * 0.9 + uy * sv * top_side * 0.42
                self.I.add('wall', cx, cy, zt, 1.8, 1.8, 9.0, 0.0, MARBLE)
        self.light(x, y, zt + 18.0, 'lamp', 1.0)
        self.light(x + ux * hall * 0.6, y + uy * hall * 0.6, zt + 4.0, 'torch', 0.9)
        self.pyramid_tops[p['id']] = (x, y, zt + (hall * 0.42 + 17.5 if royal else 0.0))
        self.zone_pts.setdefault('pyramid_steps', []).append((x + ux * (b / 2 + 40), y + uy * (b / 2 + 40), z0))
        if royal:
            self.royal_court(p, z0, face)

    def royal_court(self, p, z0, face):
        """The royal palace's own walled court round the Great Pyramid: a high white wall with towers and gilded
        crowns, a pylon gate on the processional way (and lesser gates on the other three sides), colonnades round the
        inside, gardens of palms, long pools on the cross axes, an avenue of obelisks to the stair, the courtiers' halls."""
        x, y = p['xy']
        rc = p['royal']
        b = float(p['base_m'])
        half = b / 2 + rc['court_m']
        H = rc['wall_h_m']
        ux, uy = math.cos(face), math.sin(face)
        WHITE_WALL = (0.93, 0.90, 0.83)
        corners = [(x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half)]
        gates = {f: (x + math.cos(a) * half, y + math.sin(a) * half) for f, a in (('west', math.pi), ('east', 0.0), ('north', math.pi / 2), ('south', -math.pi / 2))}
        front = min(gates, key=lambda f: math.hypot(gates[f][0] - (x + ux * half), gates[f][1] - (y + uy * half)))
        for a, bb in zip(corners, corners[1:] + corners[:1]):
            self.wall_line([a, bb], H, 12.0, WHITE_WALL, towers=rc['tower_every_m'], tower_h=H * 1.35,
                           gaps=[g for g in gates.values()], gap_r=55.0, gatehouses=False)
            # merlons along the wall walk
            L = math.hypot(bb[0] - a[0], bb[1] - a[1])
            ang = math.atan2(bb[1] - a[1], bb[0] - a[0])
            for t in np.arange(6.0, L - 6.0, 9.0):
                q = (a[0] + (bb[0] - a[0]) * t / L, a[1] + (bb[1] - a[1]) * t / L)
                if min(math.hypot(q[0] - g[0], q[1] - g[1]) for g in gates.values()) < 60:
                    continue
                self.I.add('wall', q[0], q[1], self.G.hs(*q) + H - 0.2, 4.0, 12.4, 3.2, ang, WHITE_WALL)
        for (cx, cy) in corners:                               # corner bastions with gilded crowns
            z = self.G.hs(cx, cy)
            self.I.add('tower', cx, cy, z - 1.5, 34, 34, H * 1.6 + 1.5, 0.0, WHITE_WALL)
            self.I.add('wall', cx, cy, z + H * 1.6 - 0.5, 35.5, 35.5, 2.6, 0.0, GOLD)
            self.light(cx, cy, z + H * 1.6 + 3, 'torch', 1.0)
        for f, (gx, gy) in gates.items():
            z = self.G.hs(gx, gy)
            big = f == front
            nx, ny = (gx - x) / half, (gy - y) / half              # out of the court
            tx, ty = -ny, nx                                       # along the wall
            ang = math.atan2(ty, tx)
            w, hh = (46.0, H * 2.0) if big else (30.0, H * 1.5)
            for sd in (-1, 1):                                     # the pylon's two towers
                qx, qy = gx + tx * sd * (w * 0.5 + 24), gy + ty * sd * (w * 0.5 + 24)
                self.I.add('tower', qx, qy, z - 1.5, 44 if big else 30, 34 if big else 26, hh + 1.5, ang, WHITE_WALL)
                self.I.add('wall', qx, qy, z + hh - 0.5, 45.5 if big else 31.5, 35.5 if big else 27.5, 2.8, ang, GOLD)
                self.light(qx + nx * 20, qy + ny * 20, z + 8, 'torch', 1.0)
            self.I.add('wall', gx, gy, z + hh * 0.62, w + 14, 18, hh * 0.3, ang, WHITE_WALL)     # the lintel
            self.I.add('wall', gx + nx * 9.5, gy + ny * 9.5, z + hh * 0.62 + hh * 0.12, w, 1.2, 3.0, ang, GOLD)
            if big:                                                # banners before the gate, the sphinx-less approach
                for sd in (-1, 1):
                    for j in range(3):
                        qx = gx + nx * (40 + 30 * j) + tx * sd * 40
                        qy = gy + ny * (40 + 30 * j) + ty * sd * 40
                        self.I.add('tower', qx, qy, self.G.hs(qx, qy), 3.0, 3.0, 26.0, 0.0, MARBLE)
                        self.I.add('wall', qx + tx * sd * 3.2, qy + ty * sd * 3.2, self.G.hs(qx, qy) + 13, 0.6, 5.0, 11.0, ang + math.pi / 2, (0.62, 0.12, 0.16))
                        self.light(qx, qy, self.G.hs(qx, qy) + 27, 'lamp', 0.6)
        zc = self.G.hs(x, y)
        # the court's paving, and the avenue from the pylon to the foot of the stair
        self.I.add('terrace', x, y, zc - 1.6, 2 * half - 20, 2 * half - 20, 2.0, 0.0, (0.91, 0.87, 0.79))
        fx, fy = gates[front]
        foot = (x + ux * (b / 2 + 20), y + uy * (b / 2 + 20))
        L = math.hypot(foot[0] - fx, foot[1] - fy)
        ang = math.atan2(foot[1] - fy, foot[0] - fx)
        self.I.add('terrace', (fx + foot[0]) / 2, (fy + foot[1]) / 2, zc - 1.2, L, 64.0, 2.0, ang, (0.95, 0.93, 0.88))
        px, py = -math.sin(ang), math.cos(ang)
        for t in np.arange(25.0, L - 10.0, 22.0):
            for sd in (-1, 1):
                qx, qy = fx + (foot[0] - fx) * t / L + px * sd * 40, fy + (foot[1] - fy) * t / L + py * sd * 40
                self.I.add('tower', qx, qy, zc + 0.6, 4.2, 4.2, 30.0, 0.0, MARBLE)
                self.I.add('dome', qx, qy, zc + 30.4, 4.4, 4.4, 4.0, 0.0, GOLD)
                self.light(qx, qy, zc + 34, 'lamp', 0.5)
        # colonnades round the inside of the wall
        inner = half - 26.0
        for (a, bb) in zip([(x - inner, y - inner), (x + inner, y - inner), (x + inner, y + inner), (x - inner, y + inner)],
                           [(x + inner, y - inner), (x + inner, y + inner), (x - inner, y + inner), (x - inner, y - inner)]):
            Lc = math.hypot(bb[0] - a[0], bb[1] - a[1])
            angc = math.atan2(bb[1] - a[1], bb[0] - a[0])
            for t in np.arange(10.0, Lc - 5.0, 12.0):
                q = (a[0] + (bb[0] - a[0]) * t / Lc, a[1] + (bb[1] - a[1]) * t / Lc)
                if min(math.hypot(q[0] - g[0], q[1] - g[1]) for g in gates.values()) < 70:
                    continue
                self.I.add('wall', q[0], q[1], zc + 0.4, 2.4, 2.4, 11.0, 0.0, MARBLE)
            mid = ((a[0] + bb[0]) / 2, (a[1] + bb[1]) / 2)
            self.I.add('terrace', mid[0], mid[1], zc + 11.2, Lc + 8, 16.0, 1.6, angc, MARBLE_SHADE)   # the colonnade's roof
        # long pools on the cross axes and gardens of palms between the colonnade and the pyramid's podium
        for f, (gx, gy) in gates.items():
            if f == front:
                continue
            nx, ny = (gx - x) / half, (gy - y) / half
            for j in range(3):
                r0 = b / 2 + 40 + j * 34
                if r0 > inner - 20:
                    break
                self.water.append((x + nx * r0, y + ny * r0, 20.0, zc + 0.8))
        for k in range(900):
            qx, qy = x + self.rng.uniform(-inner + 12, inner - 12), y + self.rng.uniform(-inner + 12, inner - 12)
            if max(abs(qx - x), abs(qy - y)) < b / 2 + 30:
                continue
            if abs((qx - x) * px + (qy - y) * py) < 70 and (qx - x) * ux + (qy - y) * uy > 0:
                continue                                        # the avenue
            if min(abs(qx - x), abs(qy - y)) < 26:
                continue                                        # the pools' axes
            self.tree('palm' if self.rng.random() < 0.7 else 'tree', qx, qy, zc + 0.4, self.rng.uniform(0.95, 1.25))
        # the courtiers' halls in the corners
        for (cu, cv) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            qx, qy = x + cu * (inner - 46), y + cv * (inner - 46)
            if max(abs(qx - x), abs(qy - y)) < b / 2 + 40:
                continue
            self.I.add('house', qx, qy, zc + 0.4, 62, 48, 15.0, 0.0, WHITEWASH)
            self.I.add('dome', qx, qy, zc + 15.0, 18, 18, 14, 0.0, GOLD)
        for (cx, cy) in corners:
            self.zone_pts.setdefault('pyramid_steps', []).append(((cx + x) / 2, (cy + y) / 2, zc))

    def plaza(self):
        pl = LAY['plaza']
        x, y = pl['xy']
        z = self.G.hs(x, y)
        self.I.add('terrace', x, y, z - 1.5, pl['w_m'], pl['d_m'], 2.1, 0.0, PAVING)
        # obelisks of the founders along the processional way, a pool, plane trees
        for k in range(6):
            px = x - pl['w_m'] * 0.42 + k * pl['w_m'] * 0.84 / 5
            for sv in (-1, 1):
                self.I.add('tower', px, y + sv * 44, z + 0.6, 4.0, 4.0, 22.0, 0.0, MARBLE)
                self.light(px, y + sv * 44, z + 23, 'lamp', 0.4)
        self.water.append((x - pl['w_m'] * 0.18, y, 26.0, z + 0.8))
        for k in range(26):
            u, v = self.rng.uniform(-0.45, 0.45) * pl['w_m'], self.rng.choice([-1, 1]) * self.rng.uniform(0.32, 0.46) * pl['d_m']
            self.tree('palm' if k % 3 else 'tree', x + u, y + v, z + 0.6, 1.0)
        self.zone_pts['plaza'] = [(x, y, z + 0.6)]
        # the precinct wall round the palaces
        P = LAY['precinct']
        for a, b in zip(P, P[1:] + P[:1]):
            self.wall_line([a, b], 8.0, 4.0, WALL_STONE, towers=240.0, tower_h=13.0, gaps=[LAY['plaza']['xy']], gap_r=120.0)

    # ------------------------------------------------------------ walls
    def wall_line(self, pts, h, th, col, towers=200.0, tower_h=None, gaps=(), gap_r=60.0, skip=None, gatehouses=True):
        P = resample(np.asarray(pts, float), 30.0)
        s = cumlen(P)
        made = 0
        for a, b in zip(P[:-1], P[1:]):
            m = (a + b) / 2
            if any(math.hypot(m[0] - g[0], m[1] - g[1]) < gap_r for g in gaps):
                continue
            if skip is not None and skip(m[0], m[1]):
                continue
            L = float(np.linalg.norm(b - a))
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            z = min(self.G.hs(*a), self.G.hs(*b))
            self.I.add('wall', m[0], m[1], z - 1.5, L + 1.0, th, h + 1.5, ang, col)
            made += 1
        th_h = tower_h or h * 1.45
        for sk in np.arange(towers * 0.5, s[-1], towers):
            q = np.array([np.interp(sk, s, P[:, 0]), np.interp(sk, s, P[:, 1])])
            if any(math.hypot(q[0] - g[0], q[1] - g[1]) < gap_r for g in gaps):
                continue
            if skip is not None and skip(q[0], q[1]):
                continue
            i = min(int(np.searchsorted(s, sk)), len(P) - 1)
            u = P[i] - P[max(i - 1, 0)]
            ang = math.atan2(u[1], u[0])
            z = self.G.hs(*q)
            self.I.add('tower', q[0], q[1], z - 1.5, th * 2.1, th * 2.1, th_h + 1.5, ang, col)
        for g in (gaps if gatehouses else ()):                            # a gatehouse: two towers flanking the road
            if dist_to_polyline(np.array([g[0]]), np.array([g[1]]), [tuple(p) for p in P])[0] > gap_r:
                continue
            i = int(np.argmin(np.hypot(P[:, 0] - g[0], P[:, 1] - g[1])))
            u = P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
            u = u / max(np.linalg.norm(u), 1e-6)
            ang = math.atan2(u[1], u[0])
            for sd in (-1, 1):
                q = (g[0] + u[0] * sd * (gap_r * 0.55), g[1] + u[1] * sd * (gap_r * 0.55))
                z = self.G.hs(*q)
                self.I.add('tower', q[0], q[1], z - 1.5, th * 2.8, th * 2.8, th_h * 1.25 + 1.5, ang, col)
                self.light(q[0], q[1], z + th_h * 1.25 + 1, 'torch', 0.9)
            self.I.add('wall', g[0], g[1], self.G.hs(*g) + h * 0.7, gap_r * 0.9, th * 1.3, h * 0.45, ang, col)   # the lintel
        return made

    def inner_walls(self):
        ic = LAY['inner']
        P = ic['poly']
        gates = list(ic['gates'].values())
        n_out = len(ic['outline'])
        land = P[:n_out]
        self.wall_line(land, ic['wall_h_m'], 9.0, WALL_STONE, towers=ic['tower_every_m'], gaps=gates, gap_r=70.0)
        # the river front: a lower quay wall behind the quay, broken by the river gate, the bridge and the harbour
        x0, x1, y0, y1 = LAY['harbour']
        by = LAY['bridge']['y']

        def skip(x, y):
            return (y0 - 40 < y < y1 + 40) or abs(y - by) < 50
        river_side = P[n_out - 1:] + [P[0]]
        self.wall_line(river_side, 9.0, 7.0, WALL_STONE_D, towers=260.0, gaps=[ic['gates']['river_gate']], gap_r=70.0, skip=skip)
        for k, g in ic['gates'].items():
            self.zone_pts.setdefault('gates', []).append((g[0], g[1], self.G.hs(*g)))

    def outer_wall(self):
        ow = LAY['outer']
        P = ow['poly'] + [ow['poly'][0]]
        hw = LAY['river']['width'] / 2
        gates = []
        for name, rd in LAY['roads'].items():
            for a, b in zip(rd['xy'][:-1], rd['xy'][1:]):
                for c, d in zip(P[:-1], P[1:]):
                    q = mp.seg_inter(a, b, c, d)
                    if q is not None:
                        gates.append((float(q[0]), float(q[1])))

        def in_river(x, y):
            return self.G.river_d(x, y) < hw + 30.0
        self.wall_line(P, ow['wall_h_m'], ow.get('thick_m', 10.0), WALL_STONE, towers=ow['tower_every_m'], gaps=gates, gap_r=70.0, skip=in_river)
        # the water gates: a tower on each bank and a low boom across
        RP = LAY['river']['xy']
        for c, d in zip(P[:-1], P[1:]):
            q = None
            for k in range(len(RP) - 1):
                q = mp.seg_inter(c, d, RP[k], RP[k + 1])
                if q is not None:
                    break
            if q is None:
                continue
            u = np.asarray(d) - np.asarray(c)
            u = u / np.linalg.norm(u)
            ang = math.atan2(u[1], u[0])
            for sd in (-1, 1):
                p = q + u * sd * (hw + 30.0)
                z = self.G.hs(*p)
                self.I.add('tower', p[0], p[1], z - 2.0, 26, 26, 26, ang, WALL_STONE)
                self.light(p[0], p[1], z + 25, 'torch', 0.9)
            # the boom from each bank, leaving the barges' channel open between two chain towers
            g = CHANNEL['gate_m']
            for sd in (-1, 1):
                a, b = q + u * sd * g, q + u * sd * (hw + 20.0)
                m = (a + b) / 2
                L = float(np.linalg.norm(b - a))
                self.I.add('wall', m[0], m[1], mp.disp(WL) - 2.0, L, 3.0, 3.4, ang, WALL_STONE_D)
                self.foam.append((m[0], m[1], mp.disp(WL) + 0.4, L - 20.0, ang))
                self.I.add('tower', a[0], a[1], mp.disp(WL) - 2.0, 9.0, 9.0, 12.0, ang, WALL_STONE)
                self.booms.append((a, b))
        self.stats['outer_gates'] = len(gates)

    # ------------------------------------------------------------ the river front
    def quays(self):
        """Arcaded stores along the quay, awnings of the market, cranes, the round granaries."""
        rv = LAY['river']
        hw = rv['width'] / 2
        ic = LAY['inner']
        x0, x1, y0, y1 = LAY['harbour']
        by = LAY['bridge']['y']
        ya, yb = ic['outline'][0][1] * 1.0, ic['outline'][-1][1] * 1.0
        for y in np.arange(ya + 40, yb - 40, 34.0):
            if y0 - 60 < y < y1 + 60 or abs(y - by) < 40 or abs(y - ic['gates']['river_gate'][1]) < 60:
                continue
            xr = river_x(y) + hw
            z = self.G.hs(xr + 70, y)
            self.I.add('warehouse', xr + ic['quay_m'] - 14, y, z, 30.0, 22.0, 10.5, math.pi / 2, (0.86, 0.74, 0.56))
            if self.rng.random() < 0.35:
                self.I.add('awning', xr + 36, y + self.rng.uniform(-8, 8), z, 12, 9, 3.4, 0.0, CLOTH[int(self.rng.integers(len(CLOTH)))])
            if self.rng.random() < 0.25:
                self.light(xr + 30, y, z + 4, 'lamp', 0.4)
        self.zone_pts['quays'] = [(river_x(y) + hw + 40, y, self.G.hs(river_x(y) + hw + 40, y)) for y in np.linspace(ya + 200, yb - 200, 12)]
        # the granaries: rows of round silos on the quay's landward side
        n_sil = 0
        for (gx, gy, n) in LAY['granaries']:
            z0, z1, zc = self.ground_box(gx, gy, 80, n * 15, 0.0)
            for k in range(n):
                for col_ in (-1, 1):
                    sx, sy = gx + col_ * 17.0, gy - n * 15.0 + k * 30.0 + 15
                    self.I.add('silo', sx, sy, z1, 28.0, 28.0, 30.0, 0.0, (0.88, 0.78, 0.60))
                    n_sil += 1
            self.I.add('wall', gx, gy, z1, 70, n * 30.0 + 10, 3.0, 0.0, (0.80, 0.68, 0.50))
            self.res.rect(gx, gy, 80, n * 30.0 + 20, 0.0, 6.0)
            self.zone_pts.setdefault('granaries', []).append((gx + 50, gy, zc))
        self.stats['silos'] = n_sil
        self.market_xy = (river_x(0.0) + hw + 60, -500.0, self.G.hs(river_x(0.0) + hw + 60, -500.0))

    def harbour(self):
        x0, x1, y0, y1 = LAY['harbour']
        zq = self.G.hs(x1 + 40, (y0 + y1) / 2)
        for (cx, cy, w, d) in (((x0 + x1) / 2, y0 - 6, x1 - x0, 12), ((x0 + x1) / 2, y1 + 6, x1 - x0, 12), (x1 + 6, (y0 + y1) / 2, 12, y1 - y0)):
            self.I.add('wall', cx, cy, mp.disp(LAY['river']['bed']), w, d, zq - mp.disp(LAY['river']['bed']) + 0.5, 0.0, WALL_STONE_D)
        # the long sheds round it (the "renewal"): slipways and stores
        for y in np.arange(y0 + 40, y1 - 30, 70.0):
            self.I.add('warehouse', x1 + 46, y, zq, 60, 30, 13, 0.0, (0.84, 0.72, 0.54))
        for x in np.arange(x0 + 50, x1 - 30, 74.0):
            for yy, rot in ((y0 - 40, math.pi / 2), (y1 + 40, math.pi / 2)):
                self.I.add('warehouse', x, yy, zq, 56, 34, 12, rot, (0.82, 0.70, 0.52))
        wl = mp.disp(WL) + 0.3
        # berths in rows along the basin: each boat has its own slot, so none lie on top of another
        for by_ in np.arange(y0 + 40, y1 - 30, 30.0):
            for bx in np.arange(x0 + 60, x1 - 40, 44.0):
                if self.rng.random() > 0.22:
                    continue
                ang = self.rng.choice([0.0, math.pi]) + self.rng.normal(0, 0.03)
                if self.rng.random() < 0.4:
                    self.I.add('barge_grain', bx, by_, wl - 0.6, 34.0, 10.2, 17.0, ang, HULL)
                else:
                    self.I.add('boat', bx, by_, wl, 30.0, 9.0, 15.0, ang, HULL)
                self.boats += 1
        self.zone_pts['harbour'] = [(x1 + 30, (y0 + y1) / 2, zq)]

    def river_boats(self):
        """Barges moored along both banks (grain-laden at the granaries' quays), each with its own stretch of bank and
        clear of the channel, the bridge and the water gates. The barges under way are the manifest's river_traffic."""
        rv = LAY['river']
        hw = rv['width'] / 2
        P = rv['xy']
        s = cumlen(P)
        wl = mp.disp(WL) + 0.3
        by = LAY['bridge']['y']
        x0, x1, y0, y1 = LAY['harbour']
        taken = {-1: [], 1: []}
        for k in range(320):
            sk = self.rng.uniform(300, s[-1] - 300)
            side = int(self.rng.choice([-1, 1]))
            L = self.rng.uniform(26, 40)
            if any(abs(sk - t) < (L + lt) / 2 + 12 for t, lt in taken[side]):
                continue
            i = min(int(np.searchsorted(s, sk)), len(P) - 1)
            u = P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
            u = u / max(np.linalg.norm(u), 1e-6)
            nrm = np.array([u[1], -u[0]])                       # right of the flow: east
            q = np.array([np.interp(sk, s, P[:, 0]), np.interp(sk, s, P[:, 1])]) + nrm * side * (hw - 0.15 * L - 9.0)
            if max(abs(q[0]), abs(q[1])) > mp.R - 300 or abs(q[1] - by) < 90:
                continue
            if any(dist_to_polyline(np.array([q[0]]), np.array([q[1]]), [tuple(a), tuple(b)])[0] < 70 for a, b in self.booms):
                continue
            if side > 0 and y0 - 80 < q[1] < y1 + 80:          # the harbour's mouth
                continue
            granary = side > 0 and any(abs(q[1] - gy) < n * 15 + 80 for gx, gy, n in LAY['granaries'])
            ang = math.atan2(u[1], u[0]) + (0.0 if self.rng.random() < 0.5 else math.pi)
            col = tuple(np.clip(np.asarray(HULL) * self.rng.uniform(0.8, 1.2), 0, 1))
            if granary or self.rng.random() < 0.3:              # loading at the granaries, or waiting to sail
                self.I.add('barge_grain', q[0], q[1], wl - 0.6, L, L * 0.3, L * 0.5, ang, col)
            else:                                               # unloaded, the sail furled low
                self.I.add('boat', q[0], q[1], wl, L, L * 0.3, L * 0.22, ang, col)
            taken[side].append((sk, L))
            self.moored.append((q, L))
            self.boats += 1
        self.stats['boats'] = self.boats
        self.stats['moored_barges'] = len(self.moored)

    def barge_lanes(self):
        """The channel's two lanes (Atlas RiverBarges): laden barges downstream on the east side of the middle, empty
        ones upstream on the west, CHANNEL['offset_m'] out, through the bridge's arches and the water gates' channel.
        Checked here against the banks, the bridge piers, the booms and the moored barges."""
        rv = LAY['river']
        hw = rv['width'] / 2
        P = resample(rv['xy'], 20.0)
        u = np.gradient(P, axis=0)
        u /= np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-9)
        right = np.column_stack([u[:, 1], -u[:, 0]])
        off = CHANNEL['offset_m']
        inside = (np.abs(P[:, 0]) < mp.R - 250) & (np.abs(P[:, 1]) < mp.R - 250)
        east, west = (P + right * off)[inside], (P - right * off)[inside]
        lmax = max(CHANNEL['down']['length_m'][1], CHANNEL['up']['length_m'][1])
        side_room = 0.15 * lmax + CHANNEL['jitter_m'] + 3.0            # half a beam, the jitter, a margin
        for name, lane in (('downstream', east), ('upstream', west)):
            S = resample(lane, 5.0)
            x, y = S[:, 0], S[:, 1]
            d = self.G.river_d(x, y)
            if d.max() > hw - 40:
                raise ValueError(f"{name} lane runs {d.max():.0f} m off the river's middle (half-width {hw:.0f})")
            for (px, py, hx, hy) in self.piers:
                near = np.abs(y - py) < hy + lmax / 2
                if near.any() and (np.abs(x[near] - px) - hx).min() < side_room:
                    raise ValueError(f"{name} lane grazes a bridge pier at x {px:.0f}: {(np.abs(x[near] - px) - hx).min():.1f} m")
            for a, b in self.booms:
                g = dist_to_polyline(x, y, [tuple(a), tuple(b)]).min()
                if g < side_room + 2:
                    raise ValueError(f"{name} lane grazes a water gate's boom: {g:.1f} m")
            for q, L in self.moored:
                g = np.hypot(x - q[0], y - q[1]).min()
                if g < 0.15 * L + side_room + 10:
                    raise ValueError(f"{name} lane runs into a moored barge: {g:.1f} m")
        MS = mp.MS

        def lane(name, pts, laden, spec, seed):
            return {'id': name, 'laden': laden, 'points': (np.asarray(pts) / MS).round(3).tolist(), 'speed': spec['speed'],
                    'count': spec['count'], 'min_gap': round(spec['min_gap_m'] / MS, 3),
                    'length': [round(v / MS, 3) for v in spec['length_m']], 'jitter': round(CHANNEL['jitter_m'] / MS, 3), 'seed': seed}
        self.traffic = {'z': round(float(mp.disp(WL)) / MS, 4), 'beam': 0.3, 'height': 0.5,
                        'lanes': [lane('downstream', east, True, CHANNEL['down'], 3), lane('upstream', west[::-1], False, CHANNEL['up'], 5)]}
        self.stats['barge_lanes_km'] = round(float(cumlen(east)[-1]) / 1000, 1)

    def bridge_main(self):
        rv = LAY['river']
        y = LAY['bridge']['y']
        hw = rv['width'] / 2
        xr = river_x(y)
        a = np.array([xr - hw - 70.0, y])
        b = np.array([xr + hw + 70.0, y])
        za, zb = self.G.hs(*a), self.G.hs(*b)
        deck = max(za, zb) + 4.0
        wdt = LAY['bridge']['width_m']
        L = float(b[0] - a[0])
        self.I.add('wall', (a[0] + b[0]) / 2, y, deck - 1.6, L + 10, wdt, 1.6, 0.0, LIMESTONE)
        for sd in (-1, 1):
            self.I.add('wall', (a[0] + b[0]) / 2, y + sd * (wdt / 2 - 0.5), deck, L + 10, 1.0, 1.3, 0.0, WALL_STONE)
        n = 14
        span = L / n
        bedz = float(mp.disp(rv['bed']))
        for k in range(n + 1):
            cx = a[0] + span * k
            zg = min(self.G.hs(cx, y), deck - 2)
            self.mb.box(cx, y, bedz - 1.0, 5.5, wdt - 0.4, deck - 1.6 - bedz + 1.0, 0.0, LIMESTONE)
            self.piers.append((cx, y, 2.75, wdt / 2))
            if 0 < k < n:
                self.mb.box(cx, y, bedz, 7.5, wdt + 1.0, mp.disp(WL + 0.6) - bedz, 0.0, WALL_STONE_D)     # cutwaters
                self.piers.append((cx, y, 3.75, wdt / 2 + 0.5))
        for k in range(n):
            c0, c1 = a[0] + span * k, a[0] + span * (k + 1)
            for sd in (-1, 1):
                ring = []
                for i in range(9):
                    t = i / 8
                    zb_ = deck - 1.6 - (deck - 1.6 - mp.disp(WL + 0.4)) * (1 - 0.92 * math.sin(math.pi * t))
                    ring.append((c0 + (c1 - c0) * t, y + sd * (wdt / 2 - 0.2), zb_))
                ring += [(c1, y + sd * (wdt / 2 - 0.2), deck - 1.6), (c0, y + sd * (wdt / 2 - 0.2), deck - 1.6)]
                self.mb.poly_facing(ring, (0.0, sd, 0.0), LIMESTONE)
        for k in range(0, n + 1, 2):
            self.light(a[0] + span * k, y + wdt / 2, deck + 3, 'lamp', 0.45)
        self.res.line([a, b], wdt)
        self.bridges.append((a, b, deck, wdt))
        self.zone_pts['bridge'] = [((a[0] + b[0]) / 2, y, deck)]
        self.stats['bridge_m'] = round(L)

    def archive_and_shrine(self):
        ar = LAY['archive']
        x, y = ar['xy']
        z0, z1, zc = self.ground_box(x, y, 220, 160, 0.0)
        top = z1 + 3.0
        self.I.add('terrace', x, y, z0 - 2, 230, 170, top - z0 + 2, 0.0, LIMESTONE)
        for (u, v, w, d) in ((0, -62, 200, 30), (0, 62, 200, 30), (-86, 0, 30, 96), (86, 0, 30, 96)):
            self.I.add('house', x + u, y + v, top, w, d, 15.0, 0.0, WHITEWASH)
        self.I.add('dome', x, y + 10, top, 44, 44, 38, 0.0, (0.90, 0.86, 0.78))
        for k in range(8):
            self.light(x - 90 + k * 26, y - 80, top + 4, 'lamp', 0.4)
        self.res.rect(x, y, 230, 170, 0.0, 12.0)
        self.zone_pts['archive'] = [(x, y - 100, top)]
        sh = LAY['shrine']
        x, y = sh['xy']
        z = self.G.hs(x, y)
        self.I.add('terrace', x, y, z - 2.5, 70, 46, 3.4, 0.0, LIMESTONE)
        self.I.add('dome', x, y, z + 0.9, 18, 18, 17, 0.0, WHITEWASH)
        for k in range(8):
            self.I.add('wall', x - 28 + k * 8, y - 20, z + 0.9, 1.4, 1.4, 6.0, 0.0, MARBLE)
        for k in range(9):
            self.tree('palm', x + self.rng.uniform(-40, 40), y + self.rng.uniform(26, 60), None, 1.1)
        self.light(x, y, z + 12, 'torch', 0.8)
        self.zone_pts['shrine'] = [(x, y + 30, z + 1)]

    # ------------------------------------------------------------ the city blocks
    def fill(self, poly, angle, density, did, bw=54.0, bd=42.0, lane=7.0):
        Pp = np.asarray(poly)
        cu, su = math.cos(angle), math.sin(angle)
        c0 = Pp.mean(axis=0)
        U = (Pp[:, 0] - c0[0]) * cu + (Pp[:, 1] - c0[1]) * su
        V = -(Pp[:, 0] - c0[0]) * su + (Pp[:, 1] - c0[1]) * cu
        pu, pv = bw + lane, bd + lane
        houses = 0
        iu = 0
        u = U.min() - bw
        while u < U.max() + bw:
            v = V.min() - bd
            iv = 0
            while v < V.max() + bd:
                wide = (iu % 6 == 5) or (iv % 7 == 6)
                cx = c0[0] + u * cu - v * su
                cy = c0[1] + u * su + v * cu
                if self.rng.random() < density:
                    houses += self.block(cx, cy, bw - (8.0 if wide else 0.0), bd - (8.0 if wide else 0.0), angle, poly, did)
                elif points_in_poly(np.array([cx]), np.array([cy]), poly)[0] and self.res.free([(cx, cy)]):
                    for k in range(4):                         # a garden court of palms and fruit trees
                        self.tree('palm' if k % 2 else 'tree', cx + self.rng.uniform(-18, 18), cy + self.rng.uniform(-14, 14), None, 0.9)
                v += pv
                iv += 1
            u += pu
            iu += 1
        return houses

    def block(self, cx, cy, bw, bd, ang, poly, did):
        corners = rect(cx, cy, bw, bd, ang)
        inside = points_in_poly(np.array([p[0] for p in corners] + [cx]), np.array([p[1] for p in corners] + [cy]), poly)
        if inside.sum() < 4 or not inside[-1]:
            return 0
        if not self.res.free(corners + [(cx, cy)]):
            return 0
        z = self.G.hs(cx, cy)
        self.blocks += 1
        rng = self.rng
        c, s = math.cos(ang), math.sin(ang)
        r = rng.random()
        if r < 0.012:                                      # a neighbourhood shrine or bathhouse
            self.I.add('dome', cx, cy, z, 20, 20, 17 + rng.uniform(0, 6), ang, WHITEWASH)
            for k in range(3):
                u, v = rng.uniform(-bw / 2 + 6, bw / 2 - 6), rng.uniform(-bd / 2 + 4, -bd / 4)
                self.tree('palm', cx + c * u - s * v, cy + s * u + c * v, z, 0.9)
            self.light(cx, cy, z + 6, 'lamp', 0.4)
            return 0
        if r < 0.03:                                       # a little garden square
            for k in range(5):
                u, v = rng.uniform(-bw / 2 + 5, bw / 2 - 5), rng.uniform(-bd / 2 + 5, bd / 2 - 5)
                self.tree('tree' if rng.random() < 0.5 else 'palm', cx + c * u - s * v, cy + s * u + c * v, z, 0.9)
            return 0
        if r < 0.045:                                      # a market court with awnings
            for k in range(6):
                u, v = rng.uniform(-bw / 2 + 6, bw / 2 - 6), rng.uniform(-bd / 2 + 6, bd / 2 - 6)
                self.I.add('awning', cx + c * u - s * v, cy + s * u + c * v, z, 9, 7, 3.3, ang, CLOTH[int(rng.integers(len(CLOTH)))])
            self.zone_pts.setdefault('markets', []).append((cx, cy, z))
            return 0
        n = 0
        tiled = rng.random() < 0.42                         # whole blocks tend to share a roof style
        for row in (-1, 1):
            d = bd / 2 - 0.4
            v = row * bd / 4
            u = -bw / 2
            while u < bw / 2 - 6:
                w = min(rng.uniform(13.0, 23.0), bw / 2 - u)
                if bw / 2 - (u + w) < 8:
                    w = bw / 2 - u
                uc = u + w / 2
                px, py = cx + c * uc - s * v, cy + s * uc + c * v
                q = rng.random()
                if q < 0.03:
                    self.tree('palm', px, py, z, 0.85)
                elif q < 0.06:
                    self.I.add('tower', px, py, z, min(w - 2, 8.0), min(d - 2, 8.0), rng.uniform(13.0, 17.0), ang, self.wall_col(px, py))
                    n += 1
                else:
                    st = rng.choice([1, 2, 3, 4], p=[0.22, 0.45, 0.23, 0.10])
                    hh = st * 3.3 + 1.0 + rng.uniform(-0.3, 0.4)
                    self.house(px, py, z, w - rng.uniform(0.4, 1.2), d - rng.uniform(0.2, 1.0), hh,
                               ang + (0 if row < 0 else math.pi), tiled=(tiled if rng.random() < 0.85 else not tiled))
                    n += 1
                u += w
        if rng.random() < 0.07:
            self.light(cx, cy, z + 5, 'lamp', 0.3)
        return n

    def districts(self):
        a = math.radians(-6.0)
        self.stats['houses_inner'] = self.fill(LAY['inner']['poly'], a, 0.93, 'inner')
        self.stats['houses_suburb'] = self.fill(LAY['suburb'], math.radians(-4.0), 0.9, 'suburb', bw=48.0, bd=40.0, lane=9.0)
        self.stats['blocks'] = self.blocks

    # ------------------------------------------------------------ the countryside
    def villages(self):
        cfg = LAY['village_cfg']
        G = self.G
        hw = LAY['river']['width'] / 2
        cand = []
        canals = LAY['canals']
        for kind, P in canals:
            S = resample(P, 260.0)
            for p in S[1:-1]:
                cand.append(p)
        self.rng.shuffle(cand)
        picked = []
        gap = cfg['min_gap_km'] * KM
        for p in cand:
            if len(picked) >= cfg['count']:
                break
            x, y = float(p[0]), float(p[1])
            if G.river_d(x, y) < hw + 260 or float(G._bilinear(G.district_mask, x, y)) > 0.05 or float(G._bilinear(G.desert, x, y)) > 0.1:
                continue
            if any(math.hypot(x - a, y - b) < gap for a, b, _ in picked):
                continue
            off = 40.0
            picked.append((x + off, y + off, 0))
        made = 0
        for (x0, y0, _) in picked:
            n = int(self.rng.integers(14, 42))
            ang0 = self.rng.uniform(-0.2, 0.2)
            placed = 0
            rmax = 30.0
            for k in range(n * 4):
                if placed >= n:
                    break
                r = 9.0 * math.sqrt(k + 1) * self.rng.uniform(0.85, 1.15)
                th = k * 2.399 + self.rng.normal(0, 0.12)
                x, y = x0 + r * math.cos(th), y0 + r * math.sin(th)
                w, d = self.rng.uniform(9, 15), self.rng.uniform(8, 13)
                pts = rect(x, y, w, d, ang0)
                if not self.res.free(pts):
                    continue
                z = G.hs(x, y)
                if k == 0:                                  # the dovecote tower
                    self.I.add('tower', x, y, z, 7, 7, 13, ang0, WHITEWASH)
                else:
                    self.house(x, y, z, w, d, self.rng.choice([4.3, 4.3, 7.6]), ang0 + self.rng.choice([0, math.pi / 2]))
                self.res.rect(x, y, w, d, ang0, 2.0)
                placed += 1
                rmax = max(rmax, r)
            for k in range(int(n * 1.2)):
                a = self.rng.uniform(0, 6.3)
                rr = self.rng.uniform(rmax + 10, rmax + 70)
                x, y = x0 + rr * math.cos(a), y0 + rr * math.sin(a)
                if self.res.free([(x, y)]):
                    self.tree('palm' if self.rng.random() < 0.75 else 'tree', x, y, None, self.rng.uniform(0.85, 1.2))
            if self.rng.random() < 0.85:
                self.light(x0, y0, G.hs(x0, y0) + 5, 'lamp', 0.4)
            self.village_pts.append((x0, y0, rmax + 15))
            self.zone_pts.setdefault('villages', []).append((x0, y0, G.hs(x0, y0)))
            made += placed
        self.stats['villages'] = len(picked)
        self.stats['houses_villages'] = made

    def sluices(self):
        hw = LAY['river']['width'] / 2
        n = 0
        for kind, P in LAY['canals']:
            if kind != 'feeder':
                continue
            p = P[0]
            if self.G.river_d(*p) > hw + 120:
                continue
            u = P[1] - P[0]
            ang = math.atan2(u[1], u[0]) + math.pi / 2
            z = self.G.hs(*p)
            self.I.add('wall', p[0], p[1], z - 3.0, 22, 6, 6.5, ang, WALL_STONE_D)
            for sd in (-1, 1):
                self.I.add('tower', p[0] + math.cos(ang) * sd * 12, p[1] + math.sin(ang) * sd * 12, z - 2, 5, 5, 8.5, ang, WALL_STONE)
            n += 1
        self.stats['sluices'] = n

    def vegetation(self):
        G = self.G
        rng = self.rng
        n0 = len(self.I.rows)
        rv = LAY['river']
        hw = rv['width'] / 2
        # palms along the banks, in bands (thick outside the city)
        S = resample(rv['xy'], 11.0)
        for i, p in enumerate(S[:-1]):
            u = S[i + 1] - p
            u /= max(np.linalg.norm(u), 1e-6)
            nrm = np.array([-u[1], u[0]])
            for side in (-1, 1):
                for band in range(5):
                    if rng.random() > (0.8 - 0.13 * band):
                        continue
                    q = p + nrm * side * (hw + 24 + band * 22 + rng.normal(0, 6)) + u * rng.normal(0, 4)
                    if not self.res.free([q]) or G._bilinear(G.district_mask, q[0], q[1]) > 0.2:
                        continue
                    self.tree('palm' if rng.random() < 0.8 else 'tree', q[0], q[1], None, rng.uniform(0.85, 1.25))
        # palms along the canals
        for kind, P in LAY['canals']:
            S = resample(P, 16.0 if kind == 'trunk' else 22.0)
            for i, p in enumerate(S[:-1]):
                u = S[i + 1] - p
                u /= max(np.linalg.norm(u), 1e-6)
                nrm = np.array([-u[1], u[0]])
                for side in (-1, 1):
                    if rng.random() < (0.55 if kind == 'trunk' else 0.3):
                        q = p + nrm * side * rng.uniform(9, 14)
                        if self.res.free([q]):
                            self.tree('palm' if rng.random() < 0.7 else 'tree', q[0], q[1], None, rng.uniform(0.8, 1.15))
        # date groves scattered in the fields
        R = mp.R
        xs = rng.uniform(-R, R, 14000)
        ys = rng.uniform(-R, R, 14000)
        for x, y in zip(xs, ys):
            if G._bilinear(G.desert, x, y) > 0.2 or G._bilinear(G.district_mask, x, y) > 0.1 or G.river_d(x, y) < hw + 100:
                continue
            g = fc.vnoise(np.array(x / 340.0), np.array(y / 340.0), 301)
            if g > 0.7 and self.res.free([(x, y)]):
                self.tree('palm', x, y, None, rng.uniform(0.85, 1.1))
        # desert scrub
        xs = rng.uniform(-R, R, 16000)
        ys = rng.uniform(-R, R, 16000)
        for x, y in zip(xs, ys):
            if G._bilinear(G.desert, x, y) < 0.8:
                continue
            if rng.random() < 0.3:
                self.tree('shrub', x, y, None, rng.uniform(0.7, 1.5))
        self.stats['trees'] = len(self.I.rows) - n0

    def tree(self, kind, x, y, z, scale):
        dims = {'palm': (7.5, 13.0), 'tree': (8.0, 9.0), 'poplar': (4.2, 15.0), 'shrub': (3.0, 2.0)}[kind]
        col = {'palm': PALM, 'tree': TREE, 'poplar': TREE, 'shrub': SHRUB}[kind]
        if z is None:
            z = self.G.hs(x, y)
        w = dims[0] * scale * self.rng.uniform(0.85, 1.15)
        self.I.add(kind, x, y, z - 0.3, w, w, dims[1] * scale * self.rng.uniform(0.85, 1.15), self.rng.uniform(0, 6.3),
                   np.clip(np.asarray(col) * self.rng.uniform(0.8, 1.15), 0, 1))

    # ------------------------------------------------------------ everything
    def build(self):
        t0 = time.time()
        self.reserve_all()
        for p in LAY['pyramids']:
            self.pyramid(p)
        self.plaza()
        self.archive_and_shrine()
        self.quays()
        self.harbour()
        self.bridge_main()
        self.inner_walls()
        self.outer_wall()
        self.sluices()
        self.districts()
        self.villages()
        self.river_boats()
        self.barge_lanes()
        self.vegetation()
        self.stats['instances'] = len(self.I.rows)
        self.stats['city_secs'] = round(time.time() - t0, 1)


# =============================================================================
# Water (the red river, the canals, the harbour, pools)
# =============================================================================
def mat_river_water():
    """metropolis/fantasy_capital water, coloured by the Flame's silt (the Atlas reads the vertex colour)."""
    m = fc.mat_water()
    nt = m.node_tree
    for n in nt.nodes:
        if n.type == 'VALTORGB':
            c = LAY['river']['colour']
            stops = [(0.0, (c[0] * 1.15, c[1] * 1.15, c[2] * 1.1)), (0.15, tuple(c)), (0.5, (c[0] * 0.85, c[1] * 0.8, c[2] * 0.8)), (1.0, (c[0] * 0.7, c[1] * 0.65, c[2] * 0.65))]
            for el, (pos, col) in zip(n.color_ramp.elements, stops):
                el.position = pos
                el.color = (*fc.lin(np.asarray(col)), 1.0)
    return m


def flow_strip(P, z, width, step, across):
    """A strip of water along P (metres, in the direction of flow) with `across` + 1 vertices across it: the vertices,
    quads, UVs (signed distance from the middle, distance downstream; model units) and depth (shallow at the banks)."""
    S = resample(np.asarray(P, float), step)
    ss = cumlen(S)
    V, F, UV, D = [], [], [], []
    n = across + 1
    for i, p in enumerate(S):
        u = S[min(i + 1, len(S) - 1)] - S[max(i - 1, 0)]
        u = u / max(np.linalg.norm(u), 1e-6)
        left = np.array([-u[1], u[0]])
        for j in range(n):
            t = j / across
            o = (0.5 - t) * width
            q = p + left * o
            V.append((q[0], q[1], z))
            UV.append((o / mp.MS, -ss[i] / mp.MS))          # glTF flips V (1 - v): the Atlas reads 1 + distance downstream
            D.append(0.04 + 0.36 * math.sin(math.pi * t) ** 0.6 if across > 1 else 0.05)
        if i:
            b, a = n * i, n * (i - 1)
            F += [(a + j, a + j + 1, b + j + 1, b + j) for j in range(across)]
    return V, F, UV, D


def build_water(G, city, coll, mat):
    """The river and the canals carry flow UVs (Col.b = 0 marks flowing water for the Atlas's water shader: U across,
    V downstream, in model units); the harbour basin and the pools lie still."""
    V, F, D, UV, FL = [], [], [], [], []

    def add(v, f, depth, uv=None, flowing=False):
        b = len(V)
        V.extend(v)
        F.extend([tuple(b + i for i in q) for q in f])
        D.extend(depth if isinstance(depth, list) else [depth] * len(v))
        UV.extend(uv if uv is not None else [(0.0, 0.0)] * len(v))
        FL.extend([0.0 if flowing else 1.0] * len(v))
    rv = LAY['river']
    wl = float(mp.disp(WL))
    v, f, uv, d = flow_strip(rv['xy'], wl, rv['width'] * 1.03, 30.0, 6)
    add(v, f, d, uv, True)
    for kind, P in LAY['canals']:
        v, f = ribbon(P, lambda s, p: G.hs(p[0], p[1]) + 0.35, 7.0 if kind == 'trunk' else 4.5, 20.0)
        add(v, f, 0.05)
    x0, x1, y0, y1 = LAY['harbour']
    xr = river_x((y0 + y1) / 2)
    add([(xr, y0 + 0.3 * (y1 - y0), wl), (x1, y0, wl), (x1, y1, wl), (xr, y1 - 0.3 * (y1 - y0), wl)], [(0, 1, 2, 3)], 0.2)
    add([(x0, y0, wl), (x1, y0, wl), (x1, y1, wl), (x0, y1, wl)], [(0, 1, 2, 3)], 0.2)
    n_silt = len(V)
    for (x, y, r, z) in city.water:
        n = 20
        ring = [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
        add(ring + [(x, y, z)], [(k, (k + 1) % n, n, n) for k in range(n)], 0.08)
    k = 1.0 / mp.MS
    Vm = np.asarray(V, float) * k
    me = bpy.data.meshes.new("CAP_Sea_Rivers")
    me.from_pydata(Vm.tolist(), [], [tuple(dict.fromkeys(f)) for f in F])
    me.update()
    rgba = np.ones((len(V), 4), np.float32)
    rgba[:, 0] = D
    rgba[:n_silt, 1] = 0.0                            # G = 1 - silt: the Atlas's water shader turns it red (pools stay clear)
    rgba[:, 2] = FL                                   # B = 0: flowing (the shader runs the silt and ripples downstream)
    a = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    a.data.foreach_set('color', rgba.ravel())
    da = me.attributes.new('depth', 'FLOAT', 'POINT')
    da.data.foreach_set('value', np.asarray(D, np.float32))
    lay = me.uv_layers.new(name="UVMap")
    li = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', li)
    lay.data.foreach_set('uv', np.asarray(UV, np.float32)[li].ravel())
    me.materials.append(mat)
    ob = bpy.data.objects.new("CAP_Sea_Rivers", me)
    coll.objects.link(ob)
    mb = MB()
    for (x, y, z, L, ang) in city.foam:
        mb.box(x, y, z - 0.2, L, 6.0, 0.35, ang, (0.86, 0.76, 0.66))
    emit(mb, "CAP_Weir_Foam", coll, [bpy.data.materials["CAP_Painted"]])
    return ob


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
    mats = {'painted': fc.mat_painted(), 'fire': fc.mat_fire()}
    mats['water'] = mat_river_water()
    protos()
    G = Ground()
    stats['ground_secs'] = G.secs
    stats['height_m'] = [round(float(G.Ht.min())), round(float(G.Ht.max()))]
    LAY['canals'] = make_canals()
    stats['canals'] = len(LAY['canals'])
    city = City(G)
    city.build()
    stats.update(city.stats)
    rgb = paint_albedo(G, city)
    stats['albedo_secs'] = ANCHORS['albedo_secs']
    out_dir = out_dir or os.path.join(ROOT, "cities", CFG['id'])
    os.makedirs(out_dir, exist_ok=True)
    alb_path = os.path.join(out_dir, "terrain_albedo.png")
    img = save_png(rgb, alb_path)
    del rgb
    mats['terrain'] = mat_basin_terrain(img)
    k = 1.0 / mp.MS
    Hm = G.H[::MESH_STEP, ::MESH_STEP] * k
    ter = grid_mesh("CAP_Terrain", Hm, -HALF, HALF, -HALF, HALF, coll['terrain'], [mats['terrain']])
    ter["albedo_png"] = alb_path
    build_water(G, city, coll['terrain'], mats['water'])
    mb = MB()
    Z = G.H[::MESH_STEP, ::MESH_STEP] * k
    n = Z.shape[0]
    xs = np.linspace(-HALF, HALF, n)
    zb = float(G.H.min()) * k - 3.0
    BASE_C = (0.30, 0.20, 0.13)
    for pts, zt, want in (([(x, -HALF) for x in xs], Z[0, :], (0, -1, 0)), ([(HALF, y) for y in xs], Z[:, -1], (1, 0, 0)),
                          ([(x, HALF) for x in xs], Z[-1, :], (0, 1, 0)), ([(-HALF, y) for y in xs], Z[:, 0], (-1, 0, 0))):
        for i in range(len(pts) - 1):
            q = [(pts[i][0], pts[i][1], zb), (pts[i + 1][0], pts[i + 1][1], zb), (pts[i + 1][0], pts[i + 1][1], zt[i + 1]), (pts[i][0], pts[i][1], zt[i])]
            mb.poly_facing(q, want, BASE_C)
    mb.to_object("CAP_Base", coll['terrain'], [mats['painted']])
    emit(city.mb, "CAP_HV_Structures", coll['city'], [mats['painted']])
    A = city.I.array()
    ANCHORS.update({'_G': G, '_city': city, '_root': root, '_inst': A})
    mx, my, mz = city.market_xy
    mp.instance_meshes(A, coll['inst'], mats['painted'], (mx / mp.MS, my / mp.MS))
    fc.HERO_CAM = ((32.0, -86.0, 40.0), (6.0, 2.0, 2.0))
    fc.CAMERAS = camera_list(G)
    fc.build_scene(coll['scene'], [])
    tri = 0
    for o in root.all_objects:
        if o.type == 'MESH':
            tri += sum(len(p.vertices) - 2 for p in o.data.polygons)
    kinds = {kk: int((A[:, 10] == v).sum()) for kk, v in KINDS.items()}
    stats.update({'objects': len(root.all_objects), 'approx_tris_blend': tri, 'instances_by_kind': kinds,
                  'population_estimate': population(A), 'total_secs': round(time.time() - t0, 1)})
    return stats


def population(A):
    """Residents: 4.5 people per storey of each house (towers count as two households)."""
    MS = mp.MS
    h = np.concatenate([A[A[:, 10] == KINDS['house'], 5] * MS, A[A[:, 10] == KINDS['roofhouse'], 5] * MS / 1.18])
    t = A[A[:, 10] == KINDS['tower']]
    return int(round(float(np.sum(np.maximum(1, np.round((h - 1.0) / 3.3))) * 4.5 + len(t) * 9)))


# =============================================================================
# Cameras
# =============================================================================
def landmark_list(G):
    cp = mp.cam_preset
    py = {p['id']: p['at'] for p in CFG['layout']['pyramids']}
    by = LAY['bridge']['y'] / KM
    return [
        cp(G, 'overview', "Haven and the River Flame", (1.0, 0.0), 30000, -80, 38),
        cp(G, 'pyramids', "The three white pyramids of the Amaranth palaces", (2.9, -0.55), 3500, 176, 24, 40),
        cp(G, 'great_pyramid', "The royal palace: the Great Pyramid in its walled court", tuple(py['great_pyramid']), 1500, 180, 20, 90),
        cp(G, 'river_front', "The red river, the quays and the granaries", (0.9, -2.2), 2600, -170, 20),
        cp(G, 'barges', "Grain barges down the river, empty ones sailing back up", (river_x(-2.6 * KM) / KM, -2.6), 520, -150, 24),
        cp(G, 'bridge', "The stone bridge to the west bank", (0.3, by), 1500, -120, 16),
        cp(G, 'harbour', "Queen Meret's harbour basin", (1.3, 2.3), 1100, -160, 30),
        cp(G, 'outer_wall', "Erros's outer wall and the walled fields", (6.5, -6.0), 4200, -60, 22),
        cp(G, 'fields', "Canals and fields on the west bank", (-4.0, 3.0), 3600, 160, 24),
        cp(G, 'inner_city', "The inner city's rooftops", (4.2, 2.4), 1500, -120, 34),
    ]


def camera_list(G):
    out = []
    for lm in landmark_list(G):
        c = lm['camera']
        y, p = math.radians(c['yaw']), math.radians(c['pitch'])
        t = c['target']
        pos = (t[0] + c['dist'] * math.cos(p) * math.cos(y), t[1] + c['dist'] * math.cos(p) * math.sin(y), t[2] + c['dist'] * math.sin(p))
        out.append(("CAP_Cam_" + lm['id'].title().replace('_', ''), pos, t, 30 if lm['id'] == 'overview' else 35))
    return out


# =============================================================================
# Manifest
# =============================================================================
def walk_lines():
    return {k: rd['xy'] for k, rd in LAY['roads'].items()}


def site_block(G):
    lay = CFG['layout']
    rv = lay['river']
    return {
        'anchor': CFG['world_map']['settlement'], 'units': 'km', 'kind': 'floodplain',
        'plinth_half_km': mp.R / KM,
        'peaks': [], 'cliff_zones': {}, 'sand_aprons': {},
        'districts': {'inner': [[round(x / KM, 3), round(y / KM, 3)] for x, y in LAY['inner']['poly']], 'suburb': lay['west_suburb']},
        'fields': {},
        'rivers': {'flame': [[p[0], p[1], 1.0] for p in rv['pts']]},
        'canals': {},
        'roads': {k: v['pts'] for k, v in lay['roads'].items()},
        'places': {p['id']: {'at': p['at'], 'label': p['label']} for p in lay['pyramids']},
        'villages': [[round(x / KM, 3), round(y / KM, 3)] for x, y, _ in ANCHORS['_city'].village_pts],
        'freight_entry_km': lay['roads']['west_road']['pts'][-1],
        'inlet_km': rv['pts'][0][:2],
        'outlet_km': rv['pts'][-1][:2],
        'river_width_km': rv['width_m'] / KM,
        'water_colour': rv.get('colour'),
        'outer_wall': [[round(x / KM, 3), round(y / KM, 3)] for x, y in LAY['outer']['poly']],
    }


def build_manifest(cfg, report):
    import anchors as A_
    import sunarc
    G = ANCHORS['_G']
    city = ANCHORS['_city']
    MS = mp.MS
    rng = np.random.default_rng(23)
    graph = build_graph(G, city, walk_lines())
    report['street_graph'] = {'nodes': len(graph['nodes']), 'edges': len(graph['edges'])}

    def route(pts_km):
        return A_.graph_route(graph, [[p[0] * KM / MS, p[1] * KM / MS] for p in pts_km])
    lay = cfg['layout']
    by = lay['bridge']['y_km']
    routes = {
        'procession': route([(0.62, 0.25), (1.9, 0.25), (3.1, 0.25)]),
        'bridge_crossing': route([(-3.5, -1.2), (-0.35, -1.35), (0.62, -1.4), (0.55, 0.25)]),
        'grain_road': route([(3.3, -10.0), (2.9, -6.5), (2.6, -4.2)]),
        'quays': route([(0.95, -3.4), (0.62, -1.4), (0.55, 0.25), (0.45, 2.0), (0.62, 3.3)]),
    }
    for rid, pts in routes.items():
        report.setdefault('routes', {})[rid] = {'points': len(pts), 'length_m': round(A_.polylen(pts) * MS, 1)}
    zp = city.zone_pts
    zones = [zone(G, rng, 'plaza', zp['plaza'], 40, 0.9, 120), zone(G, rng, 'quays', zp['quays'], 48, 0.8, 40),
             zone(G, rng, 'granaries', zp['granaries'], 20, 0.6, 40), zone(G, rng, 'harbour', zp['harbour'], 16, 0.6, 50),
             zone(G, rng, 'pyramid_steps', zp['pyramid_steps'], 24, 0.6, 25), zone(G, rng, 'gates', zp['gates'], 24, 0.6, 30),
             zone(G, rng, 'archive', zp['archive'], 10, 0.4, 25), zone(G, rng, 'shrine', zp['shrine'], 10, 0.4, 15),
             zone(G, rng, 'villages', zp['villages'], 40, 0.4, 40)]
    if zp.get('markets'):
        zones.append(zone(G, rng, 'markets', zp['markets'][:40], 40, 0.7, 20))
    lights = [{'pos': [round(x / MS, 3), round(y / MS, 3), round(z / MS, 3)], 'kind': kind, 'strength': s}
              for (x, y, z, kind, s) in city.lights]
    sun = cfg['sun']
    rise, sset = sunarc.sunrise_sunset(sun['latitude_deg'], sun['default_day_of_year'])
    n = 65
    xs = np.linspace(-mp.R, mp.R, n)
    GX, GY = np.meshgrid(xs, xs)
    grid = (G.h(GX, GY) / MS).round(3)
    lo, hi = float(G.Ht.min()) - 2.0, float(G.Ht.max()) + 2.0
    save_height_png(G.Ht, os.path.join(ROOT, "cities", cfg['id'], "terrain_height.png"), lo, hi)
    A = ANCHORS['_inst']
    A.tofile(os.path.join(ROOT, "cities", cfg['id'], "instances.bin"))
    groups = {}
    inv = {v: k for k, v in KINDS.items()}
    for kid in np.unique(A[:, 10]).astype(int):
        idx = np.nonzero(A[:, 10] == kid)[0]
        groups[inv[kid]] = [int(idx[0]), int(len(idx))]
    anchors = {}
    for pid, (x, y, z) in city.pyramid_tops.items():
        anchors[pid] = [round(x / MS, 3), round(y / MS, 3), round(z / MS, 3)]
    mx, my, mz = city.market_xy
    anchors['great_market'] = [round(mx / MS, 3), round(my / MS, 3), round(mz / MS, 3)]
    for key in ('plaza', 'harbour', 'bridge', 'archive', 'shrine'):
        x, y, z = zp[key][0]
        anchors[key] = [round(x / MS, 3), round(y / MS, 3), round(z / MS, 3)]
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
        'landmarks': landmark_list(G),
        'steam_vents': [],
        'events': cfg.get('events', []),
        'anchors': anchors,
        'terrain_grid': {'n': n, 'z': grid.ravel().tolist()},
        'terrain_height': {'file': 'terrain_height.png', 'n': int(G.H.shape[0]), 'min_m': round(lo, 2), 'max_m': round(hi, 2),
                           'model_vertical_exaggeration': mp.VEX, 'model_datum_m': mp.DATUM},
        'instances': {'file': 'instances.bin', 'count': int(len(A)), 'stride': 11,
                      'fields': ['x', 'y', 'z', 'w', 'd', 'h', 'rot', 'r', 'g', 'b', 'kind'],
                      'kinds': KINDS, 'groups': groups, 'protos': {k: p.json() for k, p in protos().items()}},
        'site': site_block(G),
        'river_traffic': city.traffic,
        'stats': {k: v for k, v in report.get('generator', {}).items()},
    }
    report['instances'] = {k: v[1] for k, v in groups.items()}
    report['night_lights'] = len(lights)
    return man


def write_proxies(root):
    G = ANCHORS['_G']
    Pc = bpy.data.collections.new("Proxies")
    root.children.link(Pc)
    n = 129
    xs = np.linspace(-mp.R, mp.R, n)
    X, Y = np.meshgrid(xs, xs)
    Z = G.h(X, Y) / mp.MS
    grid_mesh("CAP_Proxy_Terrain", Z, -HALF, HALF, -HALF, HALF, Pc, [], uv=False)
    A = ANCHORS['_inst']
    big = A[np.isin(A[:, 10], [KINDS['marble'], KINDS['terrace']]) & (A[:, 3] * A[:, 4] * mp.MS * mp.MS > 2500)]
    mb = MB()
    for r in big:
        mb.box(r[0], r[1], r[2], r[3], r[4], r[5], r[6], (0.5, 0.5, 0.5))
    mb.to_object("CAP_Proxy_Terraces", Pc, [])
    Pc.hide_render = True
    Pc.hide_viewport = True
    return Pc
