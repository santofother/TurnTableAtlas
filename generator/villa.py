"""Landric's villa: a walled country estate, not a city (generator/cities/landric_villa.json, "kind": "estate").

Built after docs/design/landrics_villa*.md and the aerial / overhead concepts: a two-storey villa round one open
peristyle court, a walled arrival court with one lamp-lit gate, a stable range on the west wall, a kitchen garden and
a detached bathhouse with a cold spring pool and a heated pool, vineyards all round, and a small lake to the
north-east with a riding path round it. The ground floor and the upper floor are furnished, so the Atlas can lift the
roofs and the upper storey off (a cutaway): granite entry with horse inlays, great hall, private dining room with the
hearth, Landric's gallery with *Duel Before The Walls*, kitchen, stores, bedrooms.

Everything here is laid out in real metres and written out at 1/MS (the package's model_scale): the plinth is the
usual [-50, 50] model square. The estate is drawn in its own frame (the peristyle court's centre at the origin) and
moved by OFFSET onto the plinth. Same frame as every city: +X east, +Y north, +Z up, the lake's surface at 0.
"""
import json
import math
import os
import time

import bpy
import numpy as np

import fantasy_capital as fc
from fantasy_capital import MB, smoothstep, fbm, points_in_poly, dist_to_polyline, rect_pts, L2W

ROOT_NAME = "Landric Villa"
HALF = 50.0                 # model metres (the plinth)
MS = 3.0                    # model_scale: 1 model metre = MS real metres (set by apply_config)
R = HALF * MS               # plinth half size in real metres
OFFSET = (-31.0, -20.0)     # estate frame -> plinth (real metres)
TERRACE = 6.0               # ground level inside the estate wall (real metres above the lake)
FLOOR = TERRACE + 0.6       # house podium
G_H, U_H = 4.5, 4.0         # ground and upper storey heights
EAVE = FLOOR + G_H + U_H
ANCHORS = {}

# ---------------------------------------------------------------- palette (sRGB, the painted miniature look)
STONE = (0.86, 0.78, 0.63)
STONE_L = (0.93, 0.87, 0.75)
STONE_D = (0.70, 0.61, 0.48)
MARBLE = fc.MARBLE
MARBLE_D = fc.MARBLE_D
ROOF = (0.70, 0.33, 0.20)
ROOF_D = (0.58, 0.26, 0.16)
SHUTTER = (0.27, 0.36, 0.26)
WIN = fc.WIN
DARK = fc.DARK
WOOD = fc.WOOD
WOOD_D = fc.WOOD_D
GRANITE = (0.36, 0.35, 0.37)
GRANITE_D = (0.10, 0.09, 0.10)
FLOOR_C = (0.72, 0.62, 0.48)
TERRACOTTA = (0.70, 0.40, 0.25)
RUG = (0.58, 0.16, 0.12)
RUG_B = (0.80, 0.62, 0.30)
LINEN = (0.90, 0.86, 0.78)
CYPRESS = (0.12, 0.22, 0.10)
HEDGE = (0.22, 0.34, 0.14)
SOIL = (0.36, 0.25, 0.16)
POOL_COLD = (0.30, 0.62, 0.72)
POOL_HOT = (0.42, 0.62, 0.58)
GOLD = fc.GOLD
VINE_COLS = [(0.84, 0.64, 0.18), (0.86, 0.46, 0.14), (0.64, 0.60, 0.22), (0.66, 0.22, 0.12), (0.76, 0.54, 0.16)]
AUTUMN = [(0.86, 0.48, 0.14), (0.74, 0.24, 0.12), (0.88, 0.68, 0.22), (0.62, 0.42, 0.16), (0.50, 0.50, 0.20)]

# ---------------------------------------------------------------- layout (estate frame, real metres)
HOUSE = (-28.5, -30.0, 28.5, 23.5)          # outer walls: xmin, ymin, xmax, ymax
INNER = (-18.5, -13.5, 18.5, 13.5)          # court-side walls of the four ranges
COURT = (-15.0, -10.0, 15.0, 10.0)          # the open court (colonnade line)
WALL_E = [(-64, -45), (-44, -60), (12, -60), (66, -36), (66, 20), (56, 30), (-64, 30)]
GATE_E = (-30.0, -60.0)                      # the lamp-lit gate in the south wall
N_GATE_E = (-55.0, 30.0)                     # service gate to the stable path
E_GATE_E = (66.0, 0.0)                       # garden gate to the lakeside lane
STABLE = (-60.0, -28.0, -50.0, 20.0)
HAYSHED = (-60.0, -42.0, -50.0, -30.0)
GARDEN = (34.0, -24.0, 62.0, 12.0)
BATH = (36.0, 21.0, 56.0, 28.0)              # the pavilion; the two pools lie in front of it
ANNEX = (30.0, -40.0, 46.0, -32.0)
FORECOURT = [(-50, -55), (-44, -59), (12, -59), (30, -51), (30, -30), (-50, -30)]

# plinth (real metres): the lake, its riding path, the roads
LAKE_C, LAKE_R, LAKE_ANG = (72.0, 64.0), (56.0, 38.0), 25.0
HILLS = [(-150, -10, 95, 24), (-115, 125, 85, 28), (20, 160, 70, 16), (-125, -150, 70, 12), (155, -70, 60, 10),
         (150, 150, 60, 14)]
ROAD = [(-61, -80), (-60, -92), (-52, -104), (-40, -118), (-14, -132), (10, -142), (28, -150)]
LANE = [(-52, -104), (-10, -100), (45, -82), (64, -52), (62, -14), (48, 16)]
NORTH_PATH = [(-86, 10), (-86, 22), (-50, 25), (-10, 27), (12, 33)]
GARDEN_PATH = [(35, -20), (42, -20), (60, -14)]


def to_plinth(p):
    return (p[0] + OFFSET[0], p[1] + OFFSET[1])


def lake_poly(n=96):
    a = math.radians(LAKE_ANG)
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        w = 1.0 + 0.07 * math.sin(3 * t + 0.6) + 0.04 * math.sin(5 * t + 2.0)
        x, y = LAKE_R[0] * math.cos(t) * w, LAKE_R[1] * math.sin(t) * w
        out.append((LAKE_C[0] + x * math.cos(a) - y * math.sin(a), LAKE_C[1] + x * math.sin(a) + y * math.cos(a)))
    return out


def lake_ring(off, n=96):
    """A closed loop `off` metres outside the lake shore (the riding path), as a list of points."""
    P = np.array(lake_poly(n))
    c = np.array(LAKE_C)
    d = P - c
    d /= np.linalg.norm(d, axis=1)[:, None]
    return [tuple(p) for p in P + d * off]


def apply_config(cfg):
    global MS, R, OFFSET
    MS = float(cfg.get('model_scale', 3.0))
    R = HALF * MS
    lay = cfg.get('layout', {})
    if 'offset' in lay:
        OFFSET = tuple(lay['offset'])


# =============================================================================
# Terrain (real metres on a 1 m grid; written out in model metres)
# =============================================================================
class VTerrain:
    def __init__(self, n=301):
        self.n = n
        xs = np.linspace(-R, R, n)
        X, Y = np.meshgrid(xs, xs)
        self.X, self.Y = X, Y
        lake = lake_poly()
        inside = points_in_poly(X, Y, lake)
        dl = dist_to_polyline(X, Y, lake, closed=True)
        sd = np.where(inside, -dl, dl)                      # signed distance to the shore, < 0 in the lake
        base = 7.5 + 3.0 * (fbm(X * 0.010 + 3, Y * 0.010 + 1, 4, 3) - 0.5)
        for hx, hy, hr, hh in HILLS:
            base = base + hh * smoothstep(hr, 0.0, np.hypot(X - hx, Y - hy)) ** 1.6
        base = base + 1.2 * (fbm(X * 0.05, Y * 0.05, 3, 9) - 0.5)
        land = 0.5 + (base - 0.5) * smoothstep(0.0, 45.0, sd)
        z = np.where(sd > 0, land, -0.35 - 3.6 * smoothstep(0.0, 22.0, -sd))
        wall = [to_plinth(p) for p in WALL_E]
        inw = points_in_poly(X, Y, wall)
        dw = dist_to_polyline(X, Y, wall, closed=True)
        t = np.where(inw, 1.0, smoothstep(16.0, 2.0, dw))
        z = z * (1 - t) + TERRACE * t
        self.Z = z
        self.sd = sd
        self.inwall = inw
        # zone masks for the baked albedo: R vineyard soil, G rough hill grass, B paving / gravel, A dirt road
        roads = np.minimum(dist_to_polyline(X, Y, ROAD), dist_to_polyline(X, Y, LANE))
        paths = np.minimum(np.minimum(dist_to_polyline(X, Y, NORTH_PATH), dist_to_polyline(X, Y, GARDEN_PATH)),
                           np.abs(sd - 9.0))
        self.road = np.maximum(smoothstep(3.4, 2.2, roads), smoothstep(2.0, 1.1, paths) * (sd > 2))
        self.vine = np.zeros_like(z)
        court = points_in_poly(X, Y, [to_plinth(p) for p in FORECOURT])
        yard = points_in_poly(X, Y, [to_plinth(p) for p in [(-50, -30), (-28.5, -30), (-28.5, 30), (-50, 30)]])
        garden = points_in_poly(X, Y, [to_plinth(p) for p in [(30, -26), (64, -26), (64, 30), (30, 30)]])
        self.paved = (court | yard | garden).astype(float)
        self.rough = np.maximum(smoothstep(14.0, 24.0, z) * (1 - self.road), (inw & ~(court | yard | garden)).astype(float))

    def h(self, x, y):
        G = self.Z
        n = self.n
        step = 2 * R / (n - 1)
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        fx, fy = (x + R) / step, (y + R) / step
        i = np.clip(np.floor(fx).astype(int), 0, n - 2)
        j = np.clip(np.floor(fy).astype(int), 0, n - 2)
        tx, ty = np.clip(fx - i, 0, 1), np.clip(fy - j, 0, 1)
        return (G[j, i] * (1 - tx) + G[j, i + 1] * tx) * (1 - ty) + (G[j + 1, i] * (1 - tx) + G[j + 1, i + 1] * tx) * ty

    def hs(self, x, y):
        return float(self.h(x, y))


def mat_estate_terrain():
    """CAP_Terrain for an estate: autumn meadow, vineyard soil, rough hill grass, gravel, dirt roads, lake bed."""
    _n, _r, _m, _x = fc._node, fc._ramp, fc._maprange, fc._mix
    m, nt = fc._new_mat("CAP_Terrain")
    bs, _ = fc._principled(nt, (900, 0))
    tc = _n(nt, 'ShaderNodeTexCoord', (-1800, 0))
    obj = tc.outputs['Object']
    zone = _n(nt, 'ShaderNodeAttribute', (-1500, 500), attribute_name='zone', attribute_type='GEOMETRY')
    sep = _n(nt, 'ShaderNodeSeparateColor', (-1300, 500))
    nt.links.new(zone.outputs['Color'], sep.inputs['Color'])
    vine, rough, paved, road = sep.outputs['Red'], sep.outputs['Green'], sep.outputs['Blue'], zone.outputs['Alpha']
    dn = _n(nt, 'ShaderNodeTexNoise', (-800, 500))
    nt.links.new(obj, dn.inputs['Vector'])
    dn.inputs['Scale'].default_value = 0.35
    dn.inputs['Detail'].default_value = 8.0
    fn = _n(nt, 'ShaderNodeTexNoise', (-800, 200))
    nt.links.new(obj, fn.inputs['Vector'])
    fn.inputs['Scale'].default_value = 4.0
    fn.inputs['Detail'].default_value = 4.0
    meadow = _r(nt, dn.outputs['Fac'], [(0.3, (0.47, 0.47, 0.22)), (0.55, (0.60, 0.55, 0.27)), (0.75, (0.66, 0.56, 0.30))], loc=(-500, 500))
    soil = _r(nt, fn.outputs['Fac'], [(0.3, (0.40, 0.31, 0.21)), (0.7, (0.50, 0.40, 0.27))], loc=(-500, 300))
    rough_c = _r(nt, dn.outputs['Fac'], [(0.3, (0.33, 0.36, 0.18)), (0.7, (0.46, 0.44, 0.24))], loc=(-500, 700))
    gravel = _r(nt, fn.outputs['Fac'], [(0.3, (0.70, 0.64, 0.53)), (0.7, (0.80, 0.74, 0.62))], loc=(-500, 100))
    dirt = _r(nt, fn.outputs['Fac'], [(0.3, (0.62, 0.50, 0.36)), (0.7, (0.72, 0.60, 0.44))], loc=(-500, -100))
    col = _x(nt, rough, meadow, rough_c, loc=(100, 300))
    col = _x(nt, vine, col, soil, loc=(250, 300))
    col = _x(nt, paved, col, gravel, loc=(400, 300))
    col = _x(nt, road, col, dirt, loc=(550, 300))
    geo = _n(nt, 'ShaderNodeNewGeometry', (-300, 900))
    pz = _n(nt, 'ShaderNodeSeparateXYZ', (-150, 1100))
    nt.links.new(geo.outputs['Position'], pz.inputs['Vector'])
    shore = _m(nt, pz.outputs['Z'], 0.05, 0.35, 1.0, 0.0, (0, 1100))
    col = _x(nt, shore, col, (*fc.lin4((0.62, 0.56, 0.42))[:3], 1.0), loc=(700, 300))
    deep = _m(nt, pz.outputs['Z'], -0.2, -1.0, 0.0, 1.0, (0, 1250))
    col = _x(nt, deep, col, (*fc.lin4((0.30, 0.32, 0.26))[:3], 1.0), loc=(800, 300))
    nt.links.new(fc._haze(nt, col, (850, 300)), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.92
    fc._sock(bs.inputs, 'Specular IOR Level').default_value = 0.2
    return m


def build_terrain(T, coll, mats):
    n = T.n
    k = 1.0 / MS
    verts = np.column_stack([T.X.ravel() * k, T.Y.ravel() * k, T.Z.ravel() * k])
    idx = np.arange(n * n).reshape(n, n)
    faces = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()])
    me = bpy.data.meshes.new("CAP_Terrain")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.update()
    zone = np.column_stack([T.vine.ravel(), T.rough.ravel(), T.paved.ravel(), T.road.ravel()]).astype(np.float32)
    at = me.color_attributes.new('zone', 'FLOAT_COLOR', 'POINT')
    at.data.foreach_set('color', zone.ravel())
    me.shade_smooth()
    me.materials.append(mats['terrain'])
    ob = bpy.data.objects.new("CAP_Terrain", me)
    coll.objects.link(ob)

    # the lake (named CAP_Sea: the Atlas draws it with its water shader, depth in the vertex colour)
    lp = np.array(lake_poly())
    x0, y0 = lp.min(axis=0) - 6
    x1, y1 = lp.max(axis=0) + 6
    m = 81
    SX, SY = np.meshgrid(np.linspace(x0, x1, m), np.linspace(y0, y1, m))
    depth = np.clip(-T.h(SX, SY) / 4.0, 0.0, 1.0)
    sv = np.column_stack([SX.ravel() * k, SY.ravel() * k, np.zeros(m * m)])
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

    # display base (the plinth's sides)
    mb = MB()
    Z = T.Z * k
    xs = np.linspace(-HALF, HALF, n)
    BASE_C = (0.20, 0.13, 0.08)
    zb = -3.0
    edges = [([(x, -HALF) for x in xs], Z[0, :], (0, -1, 0)), ([(HALF, y) for y in xs], Z[:, -1], (1, 0, 0)),
             ([(x, HALF) for x in xs], Z[-1, :], (0, 1, 0)), ([(-HALF, y) for y in xs], Z[:, 0], (-1, 0, 0))]
    for pts, zt, want in edges:
        for i in range(len(pts) - 1):
            q = [(pts[i][0], pts[i][1], zb), (pts[i + 1][0], pts[i + 1][1], zb),
                 (pts[i + 1][0], pts[i + 1][1], zt[i + 1]), (pts[i][0], pts[i][1], zt[i])]
            mb.poly_facing(q, want, BASE_C)
    mb.poly_facing([(-HALF, -HALF, zb), (HALF, -HALF, zb), (HALF, HALF, zb), (-HALF, HALF, zb)], (0, 0, -1), BASE_C)
    mb.to_object("CAP_Base", coll, [mats['painted']])
    return ob


# =============================================================================
# Output helpers
# =============================================================================
def emit(mb, name, coll, mats, estate=True):
    """Write an MB built in real metres (estate frame when `estate`) as a model-metre object."""
    if not mb.f:
        return None
    ox, oy = OFFSET if estate else (0.0, 0.0)
    k = 1.0 / MS
    mb.v = [((x + ox) * k, (y + oy) * k, z * k) for x, y, z in mb.v]
    return mb.to_object(name, coll, mats)


def P(p, z=None):
    """Estate point -> model-metre point (for anchors and the manifest)."""
    x, y = to_plinth(p)
    zz = p[2] if z is None and len(p) > 2 else (z if z is not None else 0.0)
    return [round(x / MS, 3), round(y / MS, 3), round(zz / MS, 3)]


class Lights:
    def __init__(self):
        self.L = []

    def add(self, p, kind, strength, order=None, estate=True):
        x, y = to_plinth(p[:2]) if estate else p[:2]
        e = {'pos': [round(x / MS, 3), round(y / MS, 3), round(p[2] / MS, 3)], 'kind': kind, 'strength': strength}
        if order is not None:
            e['order'] = round(float(order), 3)
        self.L.append(e)


# =============================================================================
# Building pieces (estate frame, real metres)
# =============================================================================
def unit(a, b):
    d = np.subtract(b, a).astype(float)
    L = float(np.linalg.norm(d))
    return d / L, L


def wall_seg(mb, a, b, z0, h, th, col, openings=(), top_col=None):
    """Straight wall on the centre line a->b with openings [(s0, s1, z_lo, z_hi)] (metres from a)."""
    u, L = unit(a, b)
    ang = math.atan2(u[1], u[0])

    def piece(s0, s1, zb, hh):
        if s1 - s0 < 1e-3 or hh < 1e-3:
            return
        m = np.asarray(a, float) + u * (s0 + s1) / 2
        mb.box(m[0], m[1], zb, s1 - s0, th, hh, ang, col, top_col)
    s = 0.0
    for o0, o1, zl, zh in sorted(openings):
        o0, o1 = max(o0, s), min(o1, L)
        piece(s, o0, z0, h)
        piece(o0, o1, z0, zl - z0)
        piece(o0, o1, zh, z0 + h - zh)
        s = o1
    piece(s, L, z0, h)


def glass(mb, c, u, n, z, w, h, arched=False, wins=None, dark=False):
    """A window face on a wall's outer surface (c = point on the surface, u along, n out). Glows at night."""
    loc = [(-w / 2, 0.0), (w / 2, 0.0)]
    if arched:
        hs = h - w / 2
        loc.append((w / 2, hs))
        for k in range(1, 8):
            a = math.pi * k / 8
            loc.append((w / 2 * math.cos(a), hs + w / 2 * math.sin(a)))
        loc.append((-w / 2, hs))
    else:
        loc += [(w / 2, h), (-w / 2, h)]
    pts = [(c[0] + u[0] * s + n[0] * 0.012, c[1] + u[1] * s + n[1] * 0.012, z + v) for s, v in loc]
    nn = fc.newell(pts)
    if nn[0] * n[0] + nn[1] * n[1] < 0:
        pts = pts[::-1]
    if dark:
        mb.poly(pts, DARK)
        return
    alpha = fc.window_alpha(*np.mean(pts, axis=0))
    mb.poly(pts, WIN, alpha=alpha)
    if wins is not None:
        wins.append(((c[0] + n[0] * 0.4, c[1] + n[1] * 0.4, z + h * 0.5), alpha))


def window_dressing(mb, c, u, n, z, w, h, shutters=True, arched=False):
    ang = math.atan2(u[1], u[0])
    sill = np.asarray(c) + np.asarray(n) * 0.1
    mb.box(sill[0], sill[1], z - 0.14, w + 0.35, 0.28, 0.14, ang, STONE_L)
    if not arched:
        mb.box(sill[0], sill[1], z + h, w + 0.35, 0.24, 0.22, ang, STONE_L)
    if shutters:
        for s in (-1, 1):
            q = np.asarray(c) + np.asarray(n) * 0.05 + np.asarray(u) * s * (w * 0.75 + 0.06)
            mb.box(q[0], q[1], z, w / 2, 0.07, h, ang, SHUTTER)


def facade(mb, a, b, n, z, w, h, spacing, wins, skip=(), arched=False, shutters=True, margin=2.5):
    """A row of windows along the outer face a->b (outward normal n), centred, `spacing` apart."""
    u, L = unit(a, b)
    k = max(1, int((L - 2 * margin) // spacing) + 1)
    s0 = (L - (k - 1) * spacing) / 2
    for i in range(k):
        s = s0 + i * spacing
        if any(lo <= s <= hi for lo, hi in skip):
            continue
        c = np.asarray(a, float) + u * s
        glass(mb, c, u, n, z, w, h, arched, wins)
        window_dressing(mb, c, u, n, z, w, h, shutters, arched)


def lantern(mb, fire, p, lights, kind='lamp', strength=0.35, post=0.0, estate=True):
    x, y, z = p
    if post > 0:
        mb.box(x, y, z, 0.16, 0.16, post, 0.0, (0.15, 0.12, 0.10))
        z += post
    mb.box(x, y, z, 0.34, 0.34, 0.06, 0.0, (0.15, 0.12, 0.10))
    mb.box(x, y, z + 0.06, 0.26, 0.26, 0.36, 0.0, (1.0, 0.78, 0.42), top=False)
    mb.cone(x, y, z + 0.42, 0.24, 0.2, (0.15, 0.12, 0.10), n=4)
    fire.box(x, y, z + 0.12, 0.12, 0.12, 0.2, 0.0, (1.0, 0.6, 0.2))
    lights.add((x, y, z + 0.25), kind, strength, estate=estate)


def statue(mb, x, y, z, face, rng, col=MARBLE):
    mb.box(x, y, z, 0.8, 0.8, 1.0, face, STONE_L)
    mb.box(x, y, z + 1.0, 0.9, 0.9, 0.08, face, MARBLE_D)
    z += 1.08
    c = jit = fc.jit(rng, col, 0.03)
    for s in (-1, 1):
        q = L2W(x, y, face, 0.0, s * 0.11)
        mb.box(q[0], q[1], z, 0.16, 0.18, 0.85, face, c)
    mb.box(x, y, z + 0.85, 0.24, 0.44, 0.62, face, c)
    mb.cyl(x, y, z + 1.47, 0.13, 0.26, 6, c)
    pose = rng.uniform(-0.5, 0.7)
    for s in (-1, 1):
        sh = L2W(x, y, face, 0.0, s * 0.27)
        hand = L2W(x, y, face, 0.25 * pose * s, s * (0.34 + 0.2 * (pose > 0) * (s > 0)))
        top = z + 1.4
        mb.beam((sh[0], sh[1], top), (hand[0], hand[1], top - 0.55 + (0.75 if pose > 0.4 and s > 0 else 0)), 0.11, jit)


def horse(mb, x, y, z, hd, col, mane=(0.10, 0.08, 0.07), head_down=False):
    W = lambda lx, ly, lz: (*L2W(x, y, hd, lx, ly), z + lz)
    c, s = math.cos(hd), math.sin(hd)
    mb.box(x, y, z + 0.9, 1.7, 0.56, 0.62, hd, col)
    for lx in (-0.66, 0.62):
        for ly in (-0.17, 0.17):
            mb.beam(W(lx, ly, 0.95), W(lx, ly, 0.0), 0.13, col)
    if head_down:
        mb.beam(W(0.7, 0, 1.35), W(1.2, 0, 0.85), 0.3, col)
        mb.beam(W(1.15, 0, 0.9), W(1.4, 0, 0.35), 0.22, col)
    else:
        mb.beam(W(0.72, 0, 1.3), W(1.05, 0, 1.95), 0.3, col)
        mb.beam(W(1.0, 0, 1.95), W(1.45, 0, 1.68), 0.22, col)
        mb.beam(W(0.75, 0, 1.6), W(0.98, 0, 2.02), 0.08, mane)
    mb.beam(W(-0.85, 0, 1.42), W(-1.05, 0, 0.75), 0.1, mane)


def table(mb, x, y, z, w, d, ang, col=WOOD, chairs=0):
    mb.box(x, y, z + 0.7, w, d, 0.08, ang, col)
    for sx in (-1, 1):
        for sy in (-1, 1):
            q = L2W(x, y, ang, sx * (w / 2 - 0.15), sy * (d / 2 - 0.15))
            mb.box(q[0], q[1], z, 0.1, 0.1, 0.7, ang, WOOD_D)
    if chairs:
        n = chairs
        for i in range(n):
            lx = -w / 2 + w * (i + 0.5) / n
            for sy in (-1, 1):
                q = L2W(x, y, ang, lx, sy * (d / 2 + 0.45))
                mb.box(q[0], q[1], z, 0.45, 0.45, 0.45, ang, WOOD_D)
                q2 = L2W(x, y, ang, lx, sy * (d / 2 + 0.66))
                mb.box(q2[0], q2[1], z + 0.45, 0.45, 0.06, 0.55, ang, WOOD_D)


def rug(mb, x, y, z, w, d, ang, col=RUG, border=RUG_B):
    mb.poly([(*p, z + 0.02) for p in rect_pts(x, y, w, d, ang)], border)
    mb.poly([(*p, z + 0.03) for p in rect_pts(x, y, w - 0.5, d - 0.5, ang)], col)


def hearth(mb, fire, c, u, n, z, w=2.4, smoke_top=None):
    """A fireplace against a wall (c on the wall's inner face, n into the room); a fire in its mouth."""
    ang = math.atan2(u[1], u[0])
    q = np.asarray(c) + np.asarray(n) * 0.35
    mb.box(q[0], q[1], z, w + 0.6, 0.7, 1.5, ang, STONE_L)
    mb.box(q[0], q[1], z + 1.5, w + 0.9, 0.8, 0.18, ang, STONE)
    mb.box(q[0], q[1], z + 1.68, w * 0.7, 0.5, 1.3, ang, STONE)
    m = np.asarray(c) + np.asarray(n) * 0.71
    pts = [(m[0] - u[0] * w / 2, m[1] - u[1] * w / 2, z), (m[0] + u[0] * w / 2, m[1] + u[1] * w / 2, z),
           (m[0] + u[0] * w / 2, m[1] + u[1] * w / 2, z + 1.1), (m[0] - u[0] * w / 2, m[1] - u[1] * w / 2, z + 1.1)]
    mb.poly_facing(pts, (n[0], n[1], 0), (0.12, 0.08, 0.06))
    f = np.asarray(c) + np.asarray(n) * 0.75
    for k in range(3):
        o = (k - 1) * w * 0.22
        fire.cone(f[0] + u[0] * o, f[1] + u[1] * o, z + 0.05, 0.22, 0.55 + 0.15 * (k == 1), (1.0, 0.55, 0.15), n=5)


def barrel(mb, x, y, z, r=0.38, h=0.95):
    mb.cyl(x, y, z, r, h, 8, WOOD, (0.48, 0.34, 0.20))
    mb.cyl(x, y, z + h * 0.2, r + 0.02, 0.06, 8, (0.20, 0.18, 0.16), top=False)
    mb.cyl(x, y, z + h * 0.75, r + 0.02, 0.06, 8, (0.20, 0.18, 0.16), top=False)


def amphora(mb, x, y, z):
    mb.cyl(x, y, z, 0.12, 0.15, 6, TERRACOTTA)
    mb.cyl(x, y, z + 0.15, 0.26, 0.55, 7, TERRACOTTA)
    mb.cone(x, y, z + 0.7, 0.26, 0.25, TERRACOTTA, n=7)
    mb.cyl(x, y, z + 0.85, 0.06, 0.2, 5, TERRACOTTA)


def bed(mb, x, y, z, ang, blanket):
    mb.box(x, y, z, 2.1, 1.6, 0.45, ang, WOOD_D)
    mb.box(x, y, z + 0.45, 2.0, 1.5, 0.15, ang, LINEN)
    q = L2W(x, y, ang, -0.25, 0.0)
    mb.box(q[0], q[1], z + 0.6, 1.4, 1.55, 0.06, ang, blanket)
    p = L2W(x, y, ang, 0.75, 0.0)
    mb.box(p[0], p[1], z + 0.6, 0.35, 1.2, 0.12, ang, (0.96, 0.94, 0.90))
    h = L2W(x, y, ang, 1.02, 0.0)
    mb.box(h[0], h[1], z, 0.1, 1.6, 1.2, ang, WOOD_D)


def pot_tree(mb, trees, x, y, z, fruit=(0.92, 0.62, 0.12)):
    mb.cyl(x, y, z, 0.38, 0.6, 8, TERRACOTTA, (0.30, 0.22, 0.14))
    trees.append(('round', (x, y, z + 0.6), (0.75, 0.75, 1.0), (0.22, 0.38, 0.14)))
    for k in range(4):
        a = k * 1.7
        mb.box(x + 0.5 * math.cos(a), y + 0.5 * math.sin(a), z + 1.3 + 0.2 * (k % 2), 0.12, 0.12, 0.12, 0.0, fruit)


def horse_inlay(mb, cx, cy, z, size, mirror, col=GRANITE_D):
    S = [(0.20, 0.00), (0.28, 0.00), (0.32, 0.25), (0.40, 0.30), (0.42, 0.02), (0.50, 0.02), (0.50, 0.33),
         (0.62, 0.50), (0.78, 0.62), (0.92, 0.62), (0.95, 0.70), (0.85, 0.72), (0.80, 0.80), (0.88, 0.95),
         (0.80, 1.00), (0.70, 0.92), (0.66, 0.86), (0.62, 0.78), (0.56, 0.72), (0.52, 0.78), (0.48, 0.88),
         (0.42, 0.86), (0.46, 0.74), (0.40, 0.62), (0.30, 0.55), (0.15, 0.45), (0.05, 0.50), (0.02, 0.42),
         (0.10, 0.35), (0.22, 0.30)]
    pts = [(cx + (0.5 - x if mirror else x - 0.5) * size, cy + (y - 0.5) * size, z) for x, y in S]
    if fc.newell(pts)[2] < 0:
        pts = pts[::-1]
    mb.poly(pts, col)


# =============================================================================
# The house
# =============================================================================
def build_house(T, coll, mats, lights, wins, trees, rng, fire, steam):
    """Ground floor (walls, rooms, furniture), upper floor, roofs and the peristyle, as separate objects."""
    g, up, rf = MB(), MB(), MB()
    x0, y0, x1, y1 = HOUSE
    ix0, iy0, ix1, iy1 = INNER
    th = 0.6
    zf, zu = FLOOR, FLOOR + G_H
    DOOR = 2.7

    # podium and floors
    g.box((x0 + x1) / 2, (y0 + y1) / 2, TERRACE - 0.2, x1 - x0 + 1.2, y1 - y0 + 1.2, FLOOR - TERRACE + 0.2, 0.0, STONE_D, STONE)
    rooms = {   # name: (xmin, ymin, xmax, ymax, floor colour)
        'great_hall': (x0, y0, -7, iy0, (0.74, 0.60, 0.44)),
        'entry': (-7, y0, 7, iy0, GRANITE),
        'dining': (7, y0, 19, iy0, (0.70, 0.52, 0.38)),
        'pantry': (19, y0, x1, iy0, FLOOR_C),
        'kitchen': (ix1, iy0, x1, 1.0, (0.62, 0.55, 0.46)),
        'stores': (ix1, 1.0, x1, iy1, (0.60, 0.53, 0.44)),
        'sitting': (x0, iy0, ix0, 0.0, (0.70, 0.56, 0.42)),
        'library': (x0, 0.0, ix0, iy1, (0.66, 0.50, 0.36)),
        'stair': (x0, iy1, ix0, y1, FLOOR_C),
        'gallery': (ix0, iy1, ix1, y1, (0.80, 0.74, 0.64)),
        'study': (ix1, iy1, x1, y1, (0.70, 0.56, 0.42)),
    }
    for nm, (a, b, c, d, col) in rooms.items():
        g.poly([(a, b, zf + 0.01), (c, b, zf + 0.01), (c, d, zf + 0.01), (a, d, zf + 0.01)], col)
    ANCHORS['rooms'] = {k: v[:4] for k, v in rooms.items()}

    # granite entry: border and two rearing horses facing each other (the wayfinding inlays)
    g.poly([(-5.5, -27.0, zf + 0.02), (5.5, -27.0, zf + 0.02), (5.5, -16.5, zf + 0.02), (-5.5, -16.5, zf + 0.02)], GRANITE_D)
    g.poly([(-5.1, -26.6, zf + 0.025), (5.1, -26.6, zf + 0.025), (5.1, -16.9, zf + 0.025), (-5.1, -16.9, zf + 0.025)], (0.52, 0.50, 0.50))
    horse_inlay(g, -2.1, -21.8, zf + 0.03, 3.8, False)
    horse_inlay(g, 2.1, -21.8, zf + 0.03, 3.8, True)
    for yy in (-12.6, 12.6):                            # small horses at the peristyle doors: the way on
        horse_inlay(g, 0.0, yy, zf + 0.03, 1.1, yy > 0, GRANITE_D)

    # ---- outer walls, both storeys, with doors
    def outer(a, b, n, doors=()):
        u, L = unit(a, b)
        ops = [(s - w / 2, s + w / 2, zf, zf + hh) for s, w, hh in doors]
        wall_seg(g, a, b, TERRACE, zf + G_H - TERRACE, th, STONE, ops)
        wall_seg(up, a, b, zu, U_H, th, STONE, (), STONE_L)
    h2 = th / 2
    S_a, S_b = (x0, y0 + h2), (x1, y0 + h2)
    outer(S_a, S_b, (0, -1), [(x0 * -1 + 0.0, 3.0, 3.6)])          # front door at x = 0
    outer((x1 - h2, y0), (x1 - h2, y1), (1, 0), [(28.5, 1.8, 2.6)])  # kitchen door to the garden
    outer((x1, y1 - h2), (x0, y1), (0, 1))
    outer((x0 + h2, y1), (x0 + h2, y0), (-1, 0), [(29.5, 2.0, 2.8)])  # west door to the stable yard
    # ---- court-side walls
    def inner(a, b, doors=()):
        ops = [(s - w / 2, s + w / 2, zf, zf + 2.8) for s, w in doors]
        wall_seg(g, a, b, zf, G_H, 0.5, STONE_L, ops)
        wall_seg(up, a, b, zu, U_H, 0.5, STONE_L, (), STONE_L)
    inner((ix0, iy0), (ix1, iy0), [(18.5, 3.0), (31.0, 1.8)])         # entry back door; pantry? no: dining side door
    inner((ix1, iy0), (ix1, iy1), [(7.5, 1.8), (21.5, 1.8)])          # kitchen, stores
    inner((ix1, iy1), (ix0, iy1), [(18.5, 3.2)])                      # the gallery's door
    inner((ix0, iy1), (ix0, iy0), [(7.5, 1.8), (20.0, 1.8)])          # library, sitting room
    # ---- partitions (ground floor)
    def part(a, b, doors=(), m=g, z=zf, h=G_H):
        ops = [(s - w / 2, s + w / 2, z, z + 2.6) for s, w in doors]
        wall_seg(m, a, b, z, h, 0.35, (0.90, 0.84, 0.72), ops)
    part((-7, y0 + th), (-7, iy0), [(8.0, 2.2)])
    part((7, y0 + th), (7, iy0), [(8.0, 2.2)])
    part((19, y0 + th), (19, iy0), [(6.0, 1.6)])
    part((ix1 + 0.25, 1.0), (x1 - th, 1.0), [(5.0, 1.6)])
    part((x0 + th, 0.0), (ix0 - 0.25, 0.0), [(5.0, 1.6)])
    part((ix0, iy1 + 0.25), (ix0, y1 - th), [])
    part((ix1, iy1 + 0.25), (ix1, y1 - th), [(5.0, 1.8)])
    part((x0 + th, iy0), (ix0, iy0), [(5.0, 1.8)])
    part((ix1, iy0), (x1 - th, iy0), [(5.0, 1.8)])
    part((x0 + th, iy1), (ix0, iy1), [(5.0, 1.8)])
    part((ix1, iy1), (x1 - th, iy1), [(5.0, 1.8)])

    # ---- windows (outer faces)
    facade(g, (x0, y0), (-8.5, y0), (0, -1), zf + 0.5, 2.0, 3.4, 5.8, wins, arched=True, shutters=False)
    facade(g, (8.5, y0), (x1, y0), (0, -1), zf + 0.9, 1.3, 2.0, 5.2, wins)
    facade(up, (x0, y0), (x1, y0), (0, -1), zu + 0.9, 1.2, 1.9, 4.6, wins, skip=[(24.0, 33.0)])
    facade(g, (x1, y0), (x1, y1), (1, 0), zf + 0.9, 1.2, 1.9, 4.8, wins, skip=[(27.0, 30.0)])
    facade(up, (x1, y0), (x1, y1), (1, 0), zu + 0.9, 1.2, 1.9, 4.8, wins)
    facade(g, (x1, y1), (x0, y1), (0, 1), zf + 0.6, 1.6, 3.2, 5.0, wins, arched=True, shutters=False, margin=11)
    facade(up, (x1, y1), (x0, y1), (0, 1), zu + 0.9, 1.2, 1.9, 4.8, wins)
    facade(g, (x0, y1), (x0, y0), (-1, 0), zf + 0.9, 1.2, 1.9, 4.8, wins, skip=[(27.5, 31.5)])
    facade(up, (x0, y1), (x0, y0), (-1, 0), zu + 0.9, 1.2, 1.9, 4.8, wins)
    for a, b, n in (((ix0, iy0), (ix1, iy0), (0, 1)), ((ix1, iy0), (ix1, iy1), (-1, 0)),
                    ((ix1, iy1), (ix0, iy1), (0, -1)), ((ix0, iy1), (ix0, iy0), (1, 0))):
        aa = np.asarray(a, float) + np.asarray(n) * 0.25
        bb = np.asarray(b, float) + np.asarray(n) * 0.25
        facade(up, aa, bb, n, zu + 0.8, 1.1, 1.8, 4.6, wins, shutters=True)
    # front portico: four columns, entablature, pediment, steps
    pz = FLOOR
    for xx in (-5.0, -1.7, 1.7, 5.0):
        g.cyl(xx, -33.0, pz, 0.36, 5.4, 10, MARBLE, top=False)
        g.box(xx, -33.0, pz + 5.4, 0.9, 0.9, 0.3, 0.0, MARBLE_D)
        g.box(xx, -33.0, pz, 0.9, 0.9, 0.25, 0.0, MARBLE_D)
    g.box(0.0, -32.0, FLOOR - 0.6, 12.6, 4.6, 0.6, 0.0, STONE_D, STONE_L)
    for k in range(3):
        g.box(0.0, -34.6 - 0.6 * k, TERRACE, 9.0 + 0.6 * k, 0.9, 0.2 * (3 - k), 0.0, STONE_L)
    rf.box(0.0, -31.9, pz + 5.7, 12.4, 4.4, 0.7, 0.0, STONE_L)
    rf.gable_roof(0.0, -31.9, pz + 6.4, 12.8, 4.6, 0.0, 2.0, ROOF, MARBLE, ov=0.05, axis='y')
    tymp = [(-5.6, -34.15, pz + 6.45), (5.6, -34.15, pz + 6.45), (0.0, -34.15, pz + 8.2)]
    rf.poly_facing(tymp, (0, -1, 0), STONE_D)
    for s in (-1, 1):                                   # door lamps
        lantern(g, fire, (s * 2.4, -30.5, FLOOR + 2.6), lights)

    # ---- the peristyle: stylobate, columns, architrave, lean-to roof, statues, the court garden
    cx0, cy0, cx1, cy1 = COURT
    zc = FLOOR + 0.01
    g.poly([(cx0, cy0, zc), (cx1, cy0, zc), (cx1, cy1, zc), (cx0, cy1, zc)], (0.80, 0.76, 0.66))
    for a, b in (((cx0, cy0), (cx1, cy0)), ((cx1, cy0), (cx1, cy1)), ((cx1, cy1), (cx0, cy1)), ((cx0, cy1), (cx0, cy0))):
        wall_seg(g, a, b, FLOOR, 0.22, 1.1, MARBLE_D, (), MARBLE)            # stylobate
    for a, b, c, d in ((ix0, iy0, ix1, cy0 - 0.5), (ix0, cy1 + 0.5, ix1, iy1), (ix0, cy0, cx0 - 0.5, cy1), (cx1 + 0.5, cy0, ix1, cy1)):
        g.poly([(a, b, FLOOR + 0.015), (c, b, FLOOR + 0.015), (c, d, FLOOR + 0.015), (a, d, FLOOR + 0.015)], (0.86, 0.82, 0.74))
    cols = []
    for k in range(13):
        x = cx0 + (cx1 - cx0) * k / 12
        cols += [(x, cy0), (x, cy1)]
    for k in range(1, 8):
        y = cy0 + (cy1 - cy0) * k / 8
        cols += [(cx0, y), (cx1, y)]
    hc = 3.6
    for x, y in cols:
        g.box(x, y, FLOOR, 0.62, 0.62, 0.22, 0.0, MARBLE_D)
        g.cyl(x, y, FLOOR + 0.22, 0.22, hc - 0.44, 10, MARBLE, top=False)
        g.box(x, y, FLOOR + hc - 0.22, 0.6, 0.6, 0.22, 0.0, MARBLE_D)
    ANCHORS['columns'] = len(cols)
    for a, b in (((cx0, cy0), (cx1, cy0)), ((cx1, cy0), (cx1, cy1)), ((cx1, cy1), (cx0, cy1)), ((cx0, cy1), (cx0, cy0))):
        u, L = unit(a, b)
        m = (np.asarray(a) + np.asarray(b)) / 2
        g.box(m[0], m[1], FLOOR + hc, L + 0.6, 0.6, 0.5, math.atan2(u[1], u[0]), MARBLE, MARBLE_D)
    # walkway roof: from the range walls (zu - 0.1) down to the architrave
    zr0, zr1 = zu - 0.1, FLOOR + hc + 0.5
    O = [(ix0 + 0.25, iy0 + 0.25), (ix1 - 0.25, iy0 + 0.25), (ix1 - 0.25, iy1 - 0.25), (ix0 + 0.25, iy1 - 0.25)]
    I = [(cx0 - 0.5, cy0 - 0.5), (cx1 + 0.5, cy0 - 0.5), (cx1 + 0.5, cy1 + 0.5), (cx0 - 0.5, cy1 + 0.5)]
    for i in range(4):
        j = (i + 1) % 4
        q = [(*O[i], zr0), (*O[j], zr0), (*I[j], zr1), (*I[i], zr1)]
        col = fc.jit(rng, ROOF, 0.05)
        rf.poly_facing(q, (0, 0, 1), col)
        rf.poly_facing(q[::-1], (0, 0, -1), (0.62, 0.50, 0.38))
    # statues: in the walkway bays, facing the court (Oravessan statues, after the chapter)
    st = []
    for x in (-12.5, -7.5, 7.5, 12.5):
        st += [(x, -11.9, math.pi / 2), (x, 11.9, -math.pi / 2)]
    for y in (-5.0, 5.0):
        st += [(-16.9, y, 0.0), (16.9, y, math.pi)]
    for x, y, a in st:
        statue(g, x, y, FLOOR, a, rng)
    ANCHORS['statues'] = len(st)
    # court garden: cross paths, four beds, fountain, potted lemon trees
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx, by = sx * 7.6, sy * 5.1
            g.box(bx, by, zc, 12.0, 7.2, 0.3, 0.0, HEDGE, (0.32, 0.44, 0.18))
            for k in range(3):
                trees.append(('round', (bx + (k - 1) * 3.6, by, zc + 0.3), (0.5, 0.5, 0.6), (0.62, 0.20, 0.18) if k == 1 else (0.30, 0.42, 0.16)))
    g.cyl(0, 0, zc, 2.6, 0.5, 20, MARBLE, MARBLE_D)
    g.cyl(0, 0, zc + 0.01, 2.3, 0.5, 20, POOL_COLD, POOL_COLD)
    g.cyl(0, 0, zc + 0.5, 0.6, 0.6, 10, MARBLE)
    pot_tree(g, trees, 0.0, 0.0, zc + 1.1)
    for x, y in ((-13.6, -8.6), (13.6, -8.6), (-13.6, 8.6), (13.6, 8.6)):
        pot_tree(g, trees, x, y, zc + 0.3)
    for x, y in ((-12.0, -11.8), (12.0, 11.8), (-16.8, 9.0), (16.8, -9.0)):   # candle lanterns in the walkway
        lantern(g, fire, (x, y, FLOOR), lights, 'lamp', 0.22, post=1.4)

    # ---- rooms: furniture and fittings
    # great hall: long table, fireplace on the west wall, tapestries
    table(g, -17.5, -22.0, zf, 11.0, 2.2, 0.0, chairs=8)
    rug(g, -17.5, -22.0, zf, 15.0, 6.0, 0.0)
    hearth(g, fire, (x0 + th, -22.0), (0, 1), (1, 0), zf, 3.0)
    for xx in (-23.0, -12.0):
        g.box(xx, iy0 - 0.25, zf + 1.2, 3.4, 0.06, 2.6, 0.0, (0.46, 0.18, 0.16))
    # private dining: table for the family, the hearth (Ignara's offering)
    table(g, 13.0, -22.5, zf, 4.6, 1.8, 0.0, chairs=3)
    rug(g, 13.0, -22.5, zf, 7.5, 5.0, 0.0, (0.30, 0.22, 0.42))
    hearth(g, fire, (13.0, iy0 - 0.3), (1, 0), (0, -1), zf, 2.2)
    for k in range(5):
        g.cyl(11.2 + 0.9 * k, -22.5, zf + 0.78, 0.18, 0.04, 8, (0.88, 0.86, 0.80))
    g.cyl(13.0, -22.5, zf + 0.78, 0.14, 0.3, 6, (0.45, 0.12, 0.18))
    # pantry and kitchen
    for k in range(4):
        barrel(g, 21.0 + 1.6 * (k % 2), -28.0 + 2.6 * (k // 2), zf)
    g.box(27.4, -22.0, zf, 1.0, 6.0, 2.2, 0.0, WOOD_D)
    hearth(g, fire, (x1 - th, -9.0), (0, 1), (-1, 0), zf, 2.6)
    table(g, 22.6, -6.0, zf, 4.0, 1.4, math.pi / 2)
    for k in range(5):
        g.box(22.6 + rng.uniform(-0.4, 0.4), -7.6 + 0.8 * k, zf + 0.78, 0.3, 0.3, 0.14, 0.0, fc.jit(rng, (0.62, 0.48, 0.24), 0.2))
    g.box(19.3, -6.0, zf, 0.9, 7.0, 2.0, 0.0, WOOD_D)
    for k in range(6):                                  # stores: barrels and amphorae
        barrel(g, 20.2 + 1.5 * (k % 3), 3.0 + 1.6 * (k // 3), zf)
    for k in range(10):
        amphora(g, 20.0 + 0.8 * (k % 5), 10.6 + 0.9 * (k // 5), zf)
    for k in range(6):
        g.box(26.5, 3.0 + 1.6 * k, zf, 1.1, 1.0, 0.55, rng.uniform(0, 1), (0.74, 0.64, 0.44))
    # sitting room and library (west range)
    rug(g, -23.5, -7.0, zf, 6.0, 6.0, 0.0, (0.24, 0.30, 0.44))
    for k in range(3):
        g.box(-26.6, -10.5 + 3.5 * k, zf, 1.0, 2.6, 0.5, 0.0, (0.42, 0.20, 0.16))
    table(g, -23.0, -7.0, zf, 1.6, 1.0, 0.0)
    for k in range(5):
        y = 1.8 + 2.3 * k
        g.box(x0 + th + 0.3, y, zf, 0.6, 2.0, 2.8, 0.0, WOOD_D)
        for j in range(4):
            g.box(x0 + th + 0.62, y, zf + 0.35 + 0.65 * j, 0.06, 1.8, 0.4, 0.0, fc.jit(rng, (0.50, 0.28, 0.18), 0.35))
    table(g, -23.0, 7.0, zf, 2.6, 1.4, math.pi / 2, chairs=1)
    # stair hall: a stair up the west wall
    for k in range(14):
        g.box(-26.7, 15.0 + 0.55 * k, zf, 2.2, 0.55, 0.32 * (k + 1), 0.0, STONE_L)
    # study / household shrine (NE)
    table(g, 23.5, 18.5, zf, 2.4, 1.2, 0.0, chairs=1)
    g.box(27.4, 18.5, zf, 0.5, 4.0, 2.6, 0.0, WOOD_D)
    # Landric's gallery: paintings along the north wall, busts, candle stands, and the Duel at the west end
    gal_y = y1 - th
    for k in range(7):
        x = -14.0 + 4.6 * k
        if abs(x) < 2:
            continue
        w, h = rng.uniform(1.6, 2.4), rng.uniform(1.2, 1.8)
        g.box(x, gal_y - 0.05, zf + 1.5, w + 0.25, 0.08, h + 0.25, 0.0, GOLD)
        g.poly_facing([(x - w / 2, gal_y - 0.1, zf + 1.6), (x + w / 2, gal_y - 0.1, zf + 1.6), (x + w / 2, gal_y - 0.1, zf + 1.6 + h),
                       (x - w / 2, gal_y - 0.1, zf + 1.6 + h)], (0, -1, 0), fc.jit(rng, (0.42, 0.40, 0.30), 0.4))
    for k in range(4):
        x = -11.0 + 7.3 * k
        g.box(x, iy1 + 1.2, zf, 0.6, 0.6, 1.2, 0.0, MARBLE_D)
        g.cyl(x, iy1 + 1.2, zf + 1.2, 0.2, 0.45, 6, MARBLE)
    dw = ix0 + 0.3                                      # the Duel Before The Walls: west end wall, lit by candles
    g.box(dw + 0.05, 18.5, zf + 0.6, 0.1, 7.4, 4.0, 0.0, GOLD)
    cv = lambda yy, zz: (dw + 0.12, yy, zf + zz)
    g.poly_facing([cv(15.0, 0.8), cv(22.0, 0.8), cv(22.0, 4.4), cv(15.0, 4.4)], (1, 0, 0), (0.56, 0.62, 0.72))
    g.poly_facing([(dw + 0.13, 15.0, zf + 0.8), (dw + 0.13, 22.0, zf + 0.8), (dw + 0.13, 22.0, zf + 1.8), (dw + 0.13, 15.0, zf + 1.8)], (1, 0, 0), (0.48, 0.38, 0.24))
    wall_pts = [(15.0, 2.2), (22.0, 2.2), (22.0, 3.0)] + [(22.0 - 0.5 * k, 3.0 + 0.25 * (k % 2)) for k in range(1, 14)] + [(15.0, 3.0)]
    g.poly_facing([(dw + 0.14, yy, zf + zz) for yy, zz in wall_pts], (1, 0, 0), (0.70, 0.62, 0.48))
    for yy, col in ((17.6, (0.55, 0.12, 0.10)), (19.4, (0.16, 0.22, 0.46))):
        g.poly_facing([(dw + 0.15, yy - 0.3, zf + 1.2), (dw + 0.15, yy + 0.3, zf + 1.2), (dw + 0.15, yy + 0.25, zf + 2.6),
                       (dw + 0.15, yy - 0.25, zf + 2.6)], (1, 0, 0), col)
    g.cyl(dw + 0.16, 18.4, zf + 2.0, 0.35, 0.02, 10, GOLD)     # the Aegis
    for yy in (14.6, 22.4):
        g.cyl(dw + 0.8, yy, zf, 0.08, 1.6, 5, (0.25, 0.20, 0.14))
        fire.cone(dw + 0.8, yy, zf + 1.6, 0.07, 0.2, (1.0, 0.7, 0.3), n=4)
        lights.add((dw + 0.8, yy, zf + 1.75), 'lamp', 0.18)
    ANCHORS['aegis_painting'] = (dw + 1.0, 18.5, zf + 2.4)

    # ---- upper floor: slab, bedrooms, beds
    slab = [((x0, y0, x1, iy0)), ((x0, iy1, x1, y1)), ((x0, iy0, ix0, iy1)), ((ix1, iy0, x1, iy1))]
    for a, b, c, d in slab:
        up.box((a + c) / 2, (b + d) / 2, zu - 0.25, c - a, d - b, 0.25, 0.0, (0.60, 0.50, 0.40), (0.72, 0.62, 0.48))
    for a, b in (((-9.0, iy1), (-9.0, y1 - th)), ((0.0, iy1), (0.0, y1 - th)), ((9.0, iy1), (9.0, y1 - th)),
                 ((ix0, iy1), (ix0, y1 - th)), ((ix1, iy1), (ix1, y1 - th)),
                 ((x0 + th, 0.0), (ix0, 0.0)), ((ix1, 0.0), (x1 - th, 0.0)),
                 ((-7.0, y0 + th), (-7.0, iy0)), ((7.0, y0 + th), (7.0, iy0)),
                 ((x0 + th, iy0), (ix0, iy0)), ((ix1, iy0), (x1 - th, iy0)), ((x0 + th, iy1), (ix0, iy1)), ((ix1, iy1), (x1 - th, iy1))):
        part(a, b, [(1.6, 1.2)], m=up, z=zu, h=U_H)
    blankets = [(0.55, 0.14, 0.12), (0.22, 0.30, 0.52), (0.36, 0.44, 0.22), (0.62, 0.48, 0.18), (0.42, 0.20, 0.40)]
    beds = [(-13.8, 20.2, math.pi / 2), (-4.5, 20.2, math.pi / 2), (4.5, 20.2, math.pi / 2), (13.8, 20.2, math.pi / 2),
            (-23.5, 20.0, math.pi / 2), (23.5, 20.0, math.pi / 2), (-23.5, -9.0, 0.0), (-23.5, 9.0, 0.0),
            (23.5, -9.0, math.pi), (23.5, 9.0, math.pi), (-17.5, -26.5, -math.pi / 2), (16.0, -26.5, -math.pi / 2),
            (0.0, -26.5, -math.pi / 2)]
    for i, (x, y, a) in enumerate(beds):
        bed(up, x, y, zu, a, blankets[i % len(blankets)])
        rug(up, *L2W(x, y, a, -1.0, 0.0), zu, 2.4, 3.2, a, blankets[(i + 2) % len(blankets)], RUG_B)
        q = L2W(x, y, a, -1.8, 1.4)
        up.box(q[0], q[1], zu, 1.0, 0.6, 0.6, a, WOOD)

    # ---- the ring roof (outer eaves, a ridge on each range's mid line, eaves over the walkway), chimneys
    ov = 0.7
    oe = [(x0 - ov, y0 - ov), (x1 + ov, y0 - ov), (x1 + ov, y1 + ov), (x0 - ov, y1 + ov)]
    rg = [((x0 + ix0) / 2, (y0 + iy0) / 2), ((x1 + ix1) / 2, (y0 + iy0) / 2), ((x1 + ix1) / 2, (y1 + iy1) / 2), ((x0 + ix0) / 2, (y1 + iy1) / 2)]
    ie = [(ix0 + 0.5, iy0 + 0.5), (ix1 - 0.5, iy0 + 0.5), (ix1 - 0.5, iy1 - 0.5), (ix0 + 0.5, iy1 - 0.5)]
    zr = EAVE + 3.4
    for i in range(4):
        j = (i + 1) % 4
        rf.poly_facing([(*oe[i], EAVE), (*oe[j], EAVE), (*rg[j], zr), (*rg[i], zr)], (0, 0, 1), fc.jit(rng, ROOF, 0.06))
        rf.poly_facing([(*ie[i], EAVE), (*ie[j], EAVE), (*rg[j], zr), (*rg[i], zr)], (0, 0, 1), fc.jit(rng, ROOF, 0.06))
        rf.poly_facing([(*oe[i], EAVE), (*oe[j], EAVE), (*ie[j], EAVE), (*ie[i], EAVE)], (0, 0, -1), (0.55, 0.42, 0.30))
        rf.beam((*rg[i], zr + 0.05), (*rg[j], zr + 0.05), 0.35, ROOF_D)
        for e in (oe, ie):                                # hip ridges
            rf.beam((*e[i], EAVE + 0.05), (*rg[i], zr + 0.05), 0.28, ROOF_D)
    # tile courses: thin darker lines across each slope (read as tiles from close by)
    for i in range(4):
        j = (i + 1) % 4
        for e in (oe, ie):
            for t in np.linspace(0.12, 0.88, 7):
                a = np.asarray(e[i]) + (np.asarray(rg[i]) - np.asarray(e[i])) * t
                b = np.asarray(e[j]) + (np.asarray(rg[j]) - np.asarray(e[j])) * t
                z = EAVE + (zr - EAVE) * t + 0.03
                rf.beam((a[0], a[1], z), (b[0], b[1], z), 0.08, ROOF_D, t2=0.05)
    for x, y in ((x0 + 0.8, -22.0), (13.0, iy0 - 0.8), (x1 - 0.8, -9.0), (-13.8, y1 - 1.5), (13.8, y1 - 1.5),
                 (-23.5, -9.0), (23.5, 9.0), (x1 - 1.5, -26.0)):
        hz = zr + 1.3 if abs(y) < 12 or abs(x) < 20 else EAVE + 3.0
        rf.box(x, y, EAVE - 0.5, 1.0, 1.0, hz - EAVE + 0.5, 0.0, STONE_L)
        rf.box(x, y, hz, 1.25, 1.25, 0.18, 0.0, STONE_D)
        rf.hip_roof(x, y, hz + 0.18, 1.1, 1.1, 0.0, 0.4, ROOF_D)
    # lamps along the front at both storeys, as in the concept's dusk
    for x in (-21.0, -14.5, 10.5, 16.0, 21.5):
        lantern(g, fire, (x, y0 - 0.45, FLOOR + 3.4), lights, 'lamp', 0.3)
    emit(g, "CAP_V_Ground", coll, [mats['painted']])
    emit(up, "CAP_V_Upper", coll, [mats['painted']])
    emit(rf, "CAP_V_Roof_House", coll, [mats['painted']])


def build_outbuildings(T, coll, mats, lights, wins, trees, rng, fire, steam):
    g, rf = MB(), MB()
    Z = TERRACE
    # ---- stables: a long range on the west wall, stall doors to the yard, horses inside, hay loft
    sx0, sy0, sx1, sy1 = STABLE
    h = 4.2
    wall_seg(g, (sx0, sy0), (sx0, sy1), Z, h, 0.5, STONE)
    wall_seg(g, (sx0, sy1), (sx1, sy1), Z, h, 0.5, STONE)
    wall_seg(g, (sx1, sy0), (sx0, sy0), Z, h, 0.5, STONE)
    doors = [(4.0 + 6.0 * k - 1.2, 4.0 + 6.0 * k + 1.2, Z, Z + 2.9) for k in range(8)]
    wall_seg(g, (sx1, sy0), (sx1, sy1), Z, h, 0.5, STONE, doors)
    g.poly([(sx0, sy0, Z + 0.02), (sx1, sy0, Z + 0.02), (sx1, sy1, Z + 0.02), (sx0, sy1, Z + 0.02)], (0.62, 0.52, 0.32))
    hcols = [(0.40, 0.24, 0.13), (0.55, 0.32, 0.16), (0.82, 0.80, 0.76), (0.14, 0.10, 0.09), (0.62, 0.42, 0.24), (0.48, 0.44, 0.40)]
    for k in range(8):
        y = sy0 + 4.0 + 6.0 * k
        for yy in (y - 3.0,):
            wall_seg(g, (sx0 + 0.25, yy), (sx0 + 6.0, yy), Z, 1.7, 0.18, WOOD)
        g.box(sx0 + 0.8, y + 1.6, Z, 0.8, 1.2, 0.8, 0.0, (0.82, 0.70, 0.36))       # manger hay
        if k < 6:
            horse(g, sx0 + 3.4, y, Z, math.pi + rng.uniform(-0.2, 0.2), hcols[k], head_down=(k % 3 == 1))
        glass(g, (sx0 - 0.25, y), (0, -1), (-1, 0), Z + 2.4, 0.9, 0.8, wins=wins)
        lantern(g, fire, (sx1 + 0.4, y + 3.0, Z + 2.9), lights, 'lamp', 0.25) if k % 2 == 0 else None
    rf.gable_roof((sx0 + sx1) / 2, (sy0 + sy1) / 2, Z + h, sx1 - sx0 + 0.8, sy1 - sy0 + 0.6, 0.0, 2.6, ROOF, STONE, ov=0.45, axis='y')
    for k in range(3):
        rf.box(sx0 + 2.5, sy0 + 8 + 16 * k, Z + h + 1.0, 1.4, 1.4, 2.4, 0.0, STONE_L)          # vents / cupolas
        rf.hip_roof(sx0 + 2.5, sy0 + 8 + 16 * k, Z + h + 3.4, 1.8, 1.8, 0.0, 0.8, ROOF_D)
    # hay shed (open sided) and the tack yard: cart, trough
    hx0, hy0, hx1, hy1 = HAYSHED
    for x in (hx0 + 0.5, hx1 - 0.5):
        for y in (hy0 + 0.5, (hy0 + hy1) / 2, hy1 - 0.5):
            g.box(x, y, Z, 0.4, 0.4, 3.6, 0.0, WOOD_D)
    rf.gable_roof((hx0 + hx1) / 2, (hy0 + hy1) / 2, Z + 3.6, hx1 - hx0 + 0.8, hy1 - hy0 + 0.8, 0.0, 1.8, ROOF_D, WOOD, axis='y')
    for k in range(12):
        g.box(hx0 + 2.0 + 2.2 * (k % 3), hy0 + 2.0 + 1.6 * ((k // 3) % 2), Z + 0.9 * (k // 6), 2.0, 1.4, 0.9, 0.0,
              fc.jit(rng, (0.84, 0.72, 0.38), 0.06))
    cart(g, -44.0, -12.0, Z, 0.4)
    g.box(-48.5, 2.0, Z, 1.0, 4.0, 0.8, 0.0, STONE_D)
    g.box(-48.5, 2.0, Z + 0.79, 0.8, 3.8, 0.02, 0.0, POOL_COLD)
    horse(g, -46.5, -38.0, Z, 0.9, hcols[1])                 # arrivals being led to the stable
    horse(g, -43.0, -40.5, Z, 1.1, hcols[2])

    # ---- the court wall, coping, pilasters, red vine; the gates
    W = WALL_E + [WALL_E[0]]
    gates = [(GATE_E, 4.4), (N_GATE_E, 3.0), (E_GATE_E, 2.4)]
    for a, b in zip(W[:-1], W[1:]):
        u, L = unit(a, b)
        ops = []
        for gp, gw in gates:
            s = float(np.dot(np.subtract(gp, a), u))
            w = np.subtract(gp, a)
            dl = abs(float(u[0] * w[1] - u[1] * w[0]))
            if -0.1 < s < L + 0.1 and dl < 0.5:
                ops.append((s - gw / 2, s + gw / 2, Z, Z + 9))
        wall_seg(g, a, b, Z - 0.5, 3.5, 0.75, STONE, ops, STONE_L)
        for o0, o1, _, _ in [(0, 0, 0, 0)] + ops:
            pass
        n = max(1, int(L // 9.0))
        for k in range(n + 1):
            s = L * k / n
            if any(o0 - 1.2 < s < o1 + 1.2 for o0, o1, _, _ in ops):
                continue
            p = np.asarray(a) + u * s
            g.box(p[0], p[1], Z - 0.5, 1.1, 1.1, 4.2, math.atan2(u[1], u[0]), STONE_L, STONE_D)
        for k in range(int(L // 6)):
            if rng.random() < 0.45:
                s = rng.uniform(1, L - 1)
                if any(o0 - 1 < s < o1 + 1 for o0, o1, _, _ in ops):
                    continue
                p = np.asarray(a) + u * s
                for side in (-1, 1):
                    q = p + np.array([-u[1], u[0]]) * side * 0.42
                    g.box(q[0], q[1], Z + rng.uniform(0.4, 1.4), rng.uniform(1.0, 2.6), 0.12, rng.uniform(0.8, 2.0),
                          math.atan2(u[1], u[0]), fc.jit(rng, (0.62, 0.18, 0.10), 0.15))
    # main gate: piers with ball finials, an arch with a pediment, iron gates ajar, lamps
    gx, gy = GATE_E
    for s in (-1, 1):
        g.box(gx + s * 3.0, gy, Z - 0.5, 1.6, 1.6, 5.2, 0.0, STONE_L, STONE_D)
        g.cyl(gx + s * 3.0, gy, Z + 4.7, 0.42, 0.5, 10, STONE_L)
        lantern(g, fire, (gx + s * 3.0, gy - 1.1, Z + 3.0), lights, 'torch', 0.8)
        g.box(gx + s * 1.3, gy - 1.0 + 0.0, Z, 0.12, 2.3, 2.8, s * 0.5, (0.12, 0.10, 0.10))
    g.box(gx, gy, Z + 4.7, 7.6, 1.6, 0.8, 0.0, STONE_L)
    rf.gable_roof(gx, gy, Z + 5.5, 8.0, 2.2, 0.0, 1.3, ROOF, STONE_L, axis='x')
    for gp, gw in gates[1:]:
        for s in (-1, 1):
            q = (gp[0] + s * (gw / 2 + 0.5), gp[1]) if gp is N_GATE_E else (gp[0], gp[1] + s * (gw / 2 + 0.5))
            g.box(q[0], q[1], Z - 0.5, 1.1, 1.1, 4.4, 0.0, STONE_L)
            g.cyl(q[0], q[1], Z + 3.9, 0.3, 0.4, 8, STONE_L)
    lantern(g, fire, (E_GATE_E[0] + 0.9, E_GATE_E[1] + 1.9, Z + 2.8), lights, 'lamp', 0.3)

    # ---- forecourt paving, planter, drive, cypresses
    g.poly([(x, y, Z + 0.03) for x, y in FORECOURT], (0.76, 0.69, 0.57))
    for k in range(18):
        y = -58 + 1.6 * k                                    # drive from the gate to the steps
        x = gx + (0.0 - gx) * min(1.0, k / 12.0)
        g.box(x, y, Z + 0.035, 3.6, 1.6, 0.03, 0.0, (0.84, 0.78, 0.66))
    g.cyl(0.0, -46.0, Z, 3.6, 0.45, 20, STONE_L, (0.30, 0.40, 0.16))
    g.cyl(0.0, -46.0, Z + 0.45, 1.0, 0.7, 10, STONE_L)
    trees.append(('round', (0.0, -46.0, Z + 1.15), (1.2, 1.2, 0.9), (0.70, 0.16, 0.12)))
    for x in (-3.0, 3.0):
        for y in (-48.5, -43.5):
            trees.append(('round', (x, y, Z + 0.45), (0.6, 0.6, 0.5), (0.74, 0.20, 0.14)))
    for x, y in ((-36.0, -57.0), (-24.0, -57.0), (-46.0, -50.0), (-14.0, -40.0), (14.0, -40.0), (24.0, -48.0),
                 (-36.0, -32.0), (26.0, -33.0), (-30.0, 27.0), (30.0, 27.0), (-48.0, 24.0), (33.0, 16.0)):
        trees.append(('cypress', (x, y, Z), (1.1, 1.1, rng.uniform(9.0, 12.0)), CYPRESS))
    for x, y in ((-40.0, -50.0), (20.0, -55.0), (64.0 - 6, -30.0), (-60.0, 26.0)):
        trees.append(('round', (x, y, Z), (3.2, 3.2, 3.6), AUTUMN[rng.integers(len(AUTUMN))]))

    # ---- kitchen garden: beds with crops, trellises, hedges, gravel paths
    gx0, gy0, gx1, gy1 = GARDEN
    g.poly([(gx0, gy0, Z + 0.03), (gx1, gy0, Z + 0.03), (gx1, gy1, Z + 0.03), (gx0, gy1, Z + 0.03)], (0.74, 0.68, 0.56))
    for bx in (41.0, 55.0):
        for by in (-17.0, -7.5, 4.5):
            g.box(bx, by, Z, 11.4, 8.4, 0.42, 0.0, HEDGE, (0.28, 0.40, 0.16))
            g.box(bx, by, Z + 0.01, 10.4, 7.4, 0.42, 0.0, SOIL, SOIL)
            kind = int(rng.integers(3))
            for r in range(5):
                yy = by - 2.8 + 1.4 * r
                if kind == 0:                       # cabbages
                    for c in range(8):
                        g.cyl(bx - 4.3 + 1.22 * c, yy, Z + 0.42, 0.42, 0.32, 6, fc.jit(rng, (0.38, 0.55, 0.30), 0.1))
                elif kind == 1:                     # beans on trellises
                    g.beam((bx - 4.4, yy, Z + 0.42), (bx + 4.4, yy, Z + 0.42), 0.35, (0.30, 0.48, 0.18), 0.6)
                    for c in range(5):
                        x = bx - 4.4 + 2.2 * c
                        g.beam((x, yy - 0.4, Z + 0.4), (x, yy, Z + 2.2), 0.06, WOOD)
                        g.beam((x, yy + 0.4, Z + 0.4), (x, yy, Z + 2.2), 0.06, WOOD)
                    g.beam((bx - 4.4, yy, Z + 2.2), (bx + 4.4, yy, Z + 2.2), 0.06, WOOD)
                else:                               # rows of greens, a few pumpkins
                    g.box(bx, yy, Z + 0.42, 9.0, 0.6, 0.35, 0.0, fc.jit(rng, (0.48, 0.58, 0.24), 0.12))
                    if r % 2 == 0:
                        g.cyl(bx + rng.uniform(-4, 4), yy + 0.5, Z + 0.42, 0.3, 0.3, 6, (0.88, 0.48, 0.12))
    g.box(48.0, 10.5, Z, 2.0, 0.6, 0.5, 0.0, STONE_L)
    amphora(g, 61.0, -22.5, Z)
    amphora(g, 35.5, 10.5, Z)

    # ---- the bathhouse: arcaded pavilion, the cold spring pool and the fire-heated pool, firebox, two statues
    bx0, by0, bx1, by1 = BATH
    g.box((bx0 + bx1) / 2, 20.0, Z, bx1 - bx0 + 2.0, 17.0, 0.5, 0.0, STONE_D, MARBLE_D)
    zb = Z + 0.5
    wall_seg(g, (bx0, by1), (bx1, by1), zb, 4.6, 0.5, STONE)
    wall_seg(g, (bx0, by0), (bx0, by1), zb, 4.6, 0.5, STONE)
    wall_seg(g, (bx1, by0), (bx1, by1), zb, 4.6, 0.5, STONE)
    for k in range(6):                                  # front arcade piers
        x = bx0 + (bx1 - bx0) * k / 5
        g.box(x, by0, zb, 0.9, 0.9, 3.6, 0.0, STONE_L)
    g.box((bx0 + bx1) / 2, by0, zb + 3.6, bx1 - bx0 + 0.9, 0.9, 1.0, 0.0, STONE_L)
    for k in range(5):
        x = bx0 + (bx1 - bx0) * (k + 0.5) / 5
        glass(g, (x, by0 - 0.46), (1, 0), (0, -1), zb + 3.0, 2.2, 0.55, dark=True)
    rf.hip_roof((bx0 + bx1) / 2, (by0 + by1) / 2, zb + 4.6, bx1 - bx0 + 1.6, by1 - by0 + 1.6, 0.0, 2.4, ROOF)
    g.box((bx0 + bx1) / 2, by1 - 2.0, zb, 14.0, 1.4, 0.45, 0.0, MARBLE_D)              # changing bench
    pools = {'cold_pool': (41.0, 15.5, POOL_COLD), 'heated_pool': (51.0, 15.5, POOL_HOT)}
    for k, (px, py, pc) in pools.items():
        g.box(px, py, zb - 0.02, 8.0, 6.2, 0.35, 0.0, MARBLE, MARBLE)
        g.box(px, py, zb - 0.01, 7.0, 5.2, 0.28, 0.0, pc, pc)
        ANCHORS[k] = (px, py, zb + 0.3)
    steam.append((51.0, 15.5, zb + 0.4))
    g.box(57.5, 14.0, Z, 2.2, 2.2, 1.8, 0.0, STONE_D)                                 # the firebox
    g.poly_facing([(56.39, 13.3, Z + 0.2), (56.39, 14.7, Z + 0.2), (56.39, 14.7, Z + 1.1), (56.39, 13.3, Z + 1.1)], (-1, 0, 0), (0.12, 0.08, 0.06))
    fire.cone(56.2, 14.0, Z + 0.25, 0.35, 0.7, (1.0, 0.5, 0.15), n=5)
    lights.add((56.0, 14.0, Z + 0.8), 'torch', 0.6)
    ANCHORS['bath_fire'] = (56.0, 14.0, Z + 0.8)
    ANCHORS['bath_entry'] = (46.0, 10.6, Z)
    for s in (-1, 1):
        statue(g, 46.0 + s * 2.4, 10.6, Z, math.pi / 2, rng)
    lantern(g, fire, (bx0 + 1.0, by0 - 0.6, zb + 2.6), lights)
    lantern(g, fire, (bx1 - 1.0, by0 - 0.6, zb + 2.6), lights)

    # ---- household annex (SE): a small two-room house with a chimney
    ax0, ay0, ax1, ay1 = ANNEX
    for a, b in (((ax0, ay0), (ax1, ay0)), ((ax1, ay0), (ax1, ay1)), ((ax1, ay1), (ax0, ay1)), ((ax0, ay1), (ax0, ay0))):
        wall_seg(g, a, b, Z, 3.6, 0.5, STONE, [(7.0, 8.4, Z, Z + 2.4)] if a == (ax1, ay1) else [])
    g.poly([(ax0, ay0, Z + 0.03), (ax1, ay0, Z + 0.03), (ax1, ay1, Z + 0.03), (ax0, ay1, Z + 0.03)], FLOOR_C)
    facade(g, (ax0, ay0), (ax1, ay0), (0, -1), Z + 0.9, 1.1, 1.5, 4.2, wins)
    rf.hip_roof((ax0 + ax1) / 2, (ay0 + ay1) / 2, Z + 3.6, ax1 - ax0 + 1.2, ay1 - ay0 + 1.2, 0.0, 2.0, ROOF)
    rf.box(ax1 - 2.0, ay1 - 2.0, Z + 3.0, 1.0, 1.0, 3.6, 0.0, STONE_L)
    for k in range(2):
        bed(g, ax0 + 2.0 + 9.0 * k, ay1 - 2.0, Z, 0.0, (0.48, 0.40, 0.30))
    hearth(g, fire, (ax1 - 2.0, ay1 - 0.25), (1, 0), (0, -1), Z, 1.4)
    emit(g, "CAP_V_Grounds", coll, [mats['painted']])
    emit(rf, "CAP_V_Roof_Outbuildings", coll, [mats['painted']])


def cart(mb, x, y, z, ang):
    mb.box(x, y, z + 0.9, 3.0, 1.6, 0.6, ang, WOOD, (0.36, 0.26, 0.16))
    for s in (-1, 1):
        c = L2W(x, y, ang, 0.0, s * 0.9)
        u = (math.cos(ang), math.sin(ang))
        ring = [(c[0] + u[0] * 0.8 * math.cos(2 * math.pi * k / 10), c[1] + u[1] * 0.8 * math.cos(2 * math.pi * k / 10),
                 z + 0.8 + 0.8 * math.sin(2 * math.pi * k / 10)) for k in range(10)]
        mb.extrude(ring, (-u[1] * 0.12 * s, u[0] * 0.12 * s, 0.0), WOOD_D, WOOD_D, top=True, bottom=True)
    p = L2W(x, y, ang, 2.6, 0.0)
    mb.beam(L2W(x, y, ang, 1.4, 0.0) + (z + 1.0,), (p[0], p[1], z + 0.4), 0.12, WOOD_D)
    for k in range(3):
        q = L2W(x, y, ang, -0.8 + 0.8 * k, 0.0)
        mb.box(q[0], q[1], z + 1.5, 0.7, 1.1, 0.5, ang + 0.2 * k, (0.84, 0.72, 0.38))


# =============================================================================
# Land: vineyards, trees, rocks, the lakeside lane with lamp posts, the jetty
# =============================================================================
PARCELS = [   # plinth rect (x0, y0, x1, y1) and row heading (deg)
    (-150, -150, 150, -88, 8.0), (-150, -88, -98, 150, 92.0), (-98, 14, 12, 150, 28.0), (42, -88, 150, 4, 96.0),
    (36, 112, 150, 150, 0.0),
]


def build_land(T, coll, mats, lights, trees, rng, fire):
    vines = {}
    k = 0
    wall = [to_plinth(p) for p in WALL_E]
    lake = lake_poly()
    vine_mask = np.zeros_like(T.Z)
    for (x0, y0, x1, y1, hd) in PARCELS:
        a = math.radians(hd)
        u = np.array([math.cos(a), math.sin(a)])
        n = np.array([-u[1], u[0]])
        c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
        half = math.hypot(x1 - x0, y1 - y0) / 2
        for off in np.arange(-half, half, 2.8):
            ss = np.arange(-half, half, 1.5)
            pts = c + n * off + ss[:, None] * u
            X, Y = pts[:, 0], pts[:, 1]
            ok = (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & (np.abs(X) < R - 3) & (np.abs(Y) < R - 3)
            ok &= dist_to_polyline(X, Y, wall, closed=True) > 7.0
            ok &= ~points_in_poly(X, Y, wall)
            dl = dist_to_polyline(X, Y, lake, closed=True)
            ok &= (dl > 15.0) & ~points_in_poly(X, Y, lake)
            ok &= np.minimum(dist_to_polyline(X, Y, ROAD), dist_to_polyline(X, Y, LANE)) > 5.0
            ok &= np.minimum(dist_to_polyline(X, Y, NORTH_PATH), dist_to_polyline(X, Y, GARDEN_PATH)) > 3.5
            ok &= fbm(X * 0.02 + 5, Y * 0.02 + 2, 3, 13) > 0.36            # meadow clearings
            runs, cur = [], []
            for i in range(len(ok)):
                if ok[i]:
                    cur.append(pts[i])
                elif cur:
                    runs.append(cur)
                    cur = []
            if cur:
                runs.append(cur)
            for run in runs:
                if len(run) < 4:
                    continue
                col0 = VINE_COLS[int(abs(off * 0.37 + hd)) % len(VINE_COLS)]
                for i in range(0, len(run) - 1, 2):
                    p, q = run[i], run[min(i + 2, len(run) - 1)]
                    if np.allclose(p, q):
                        continue
                    m = (p + q) / 2
                    key = (int((m[0] + R) // 60), int((m[1] + R) // 60))
                    mb = vines.setdefault(key, MB())
                    z = T.hs(m[0], m[1])
                    col = fc.jit(rng, col0, 0.1)
                    L = float(np.linalg.norm(q - p))
                    mb.box(m[0], m[1], z, L + 0.2, 0.8, 1.2, a, (0.42, 0.32, 0.18), col)
                    mb.box(m[0], m[1], z + 0.55, L, 1.0, 0.55, a, col, fc.lighten(col, 1.08))
                    k += 1
                for e in (run[0], run[-1]):
                    mb = vines.setdefault((int((e[0] + R) // 60), int((e[1] + R) // 60)), MB())
                    mb.box(e[0], e[1], T.hs(e[0], e[1]), 0.18, 0.18, 1.7, a, WOOD_D)
                # paint the soil under the rows into the terrain mask
                rp = np.array(run)
                ii = np.clip(((rp[:, 0] + R)).astype(int), 0, T.n - 1)
                jj = np.clip(((rp[:, 1] + R)).astype(int), 0, T.n - 1)
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        vine_mask[np.clip(jj + dj, 0, T.n - 1), np.clip(ii + di, 0, T.n - 1)] = 1.0
    T.vine = vine_mask
    T.rough = T.rough * (1 - vine_mask)
    for (i, j), mb in sorted(vines.items()):
        emit(mb, "CAP_V_Vines_%d_%d" % (i, j), coll, [mats['painted']], estate=False)
    ANCHORS['vine_pieces'] = k

    # land outside the wall: trees, rocks, lamp posts and fence along the lane, a jetty
    lm = MB()
    for p in fc.resample(LANE[2:], 18.0):
        q = (p[0] + 3.2, p[1] + 1.0)
        lantern(lm, fire, (q[0], q[1], T.hs(*q)), lights, 'lamp', 0.3, post=2.6, estate=False) if abs(q[0]) < R - 3 else None
    ring = lake_ring(13.0)
    fence = fc.resample(ring + [ring[0]], 3.0)
    for i in range(len(fence) - 1):
        a, b = fence[i], fence[i + 1]
        if a[1] > 75 and a[0] > 60:                      # leave the north shore open (meadow and trees)
            continue
        za, zb = T.hs(*a), T.hs(*b)
        lm.box(a[0], a[1], za, 0.14, 0.14, 1.1, 0.0, WOOD)
        lm.beam((a[0], a[1], za + 0.95), (b[0], b[1], zb + 0.95), 0.08, WOOD)
        if i % 7 == 0:
            lantern(lm, fire, (a[0], a[1], za), lights, 'lamp', 0.25, post=2.4, estate=False)
    # jetty and a rowboat on the south-west shore
    jp = np.array(lake_ring(-2.0, 96)[60])
    c = np.array(LAKE_C)
    d = (c - jp) / np.linalg.norm(c - jp)
    ang = math.atan2(d[1], d[0])
    s0 = jp - d * 6
    for i in range(6):
        p = s0 + d * (2.0 * i)
        lm.box(p[0], p[1], 0.25, 2.2, 1.8, 0.18, ang, WOOD)
        for s in (-1, 1):
            q = p + np.array([-d[1], d[0]]) * s * 0.9
            lm.box(q[0], q[1], -1.0, 0.18, 0.18, 1.6, 0.0, WOOD_D)
    bt = s0 + d * 11.0 + np.array([-d[1], d[0]]) * 2.2
    lm.box(bt[0], bt[1], -0.05, 3.6, 1.2, 0.35, ang, (0.50, 0.33, 0.18), (0.30, 0.20, 0.12))
    ANCHORS['jetty'] = (float(jp[0]), float(jp[1]))
    # rocks on the shore and by the road
    for i in range(70):
        th = rng.uniform(0, 2 * math.pi)
        p = np.array(lake_ring(rng.uniform(-1.0, 4.0), 360)[int(th / (2 * math.pi) * 360) % 360])
        if rng.random() < 0.35:
            p = np.array(ROAD[int(rng.integers(len(ROAD) - 1)) + 1]) + rng.uniform(-9, 9, 2)
        s = rng.uniform(0.6, 1.8)
        trees.append(('rock', (p[0], p[1], T.hs(*p) - 0.2), (s * 1.3, s, s * 0.7), fc.jit(rng, (0.62, 0.58, 0.52), 0.12), 'plinth'))
    # trees: cypress lines along the road and lake lane, autumn groves on the meadow, round the lake and hills
    for path, step in ((ROAD[1:], 14.0), (LANE[1:4], 16.0)):
        for i, p in enumerate(fc.resample(path, step)):
            for s in (-1, 1):
                q = p + np.array([rng.uniform(-1, 1), 0]) + np.array([s * 6.0, 0.0])
                if abs(q[0]) < R - 3 and abs(q[1]) < R - 3 and (i + (s > 0)) % 2 == 0:
                    trees.append(('cypress', (q[0], q[1], T.hs(*q)), (1.2, 1.2, rng.uniform(9, 13)), CYPRESS, 'plinth'))
    placed = 0
    for i in range(2000):
        if placed >= 230:
            break
        x, y = rng.uniform(-R + 4, R - 4, 2)
        if T.inwall[int(y + R), int(x + R)] or T.vine[int(y + R), int(x + R)] > 0.5 or T.hs(x, y) < 0.8:
            continue
        if min(dist_to_polyline(np.array([x]), np.array([y]), ROAD)[0], dist_to_polyline(np.array([x]), np.array([y]), LANE)[0]) < 5:
            continue
        if abs(T.sd[int(y + R), int(x + R)] - 9.0) < 3.0:      # keep the riding path clear
            continue
        if fbm(x * 0.02 + 1, y * 0.02 + 7, 3, 21) < 0.42 and T.sd[int(y + R), int(x + R)] > 26:
            continue
        s = rng.uniform(2.6, 4.6)
        if rng.random() < 0.18:
            trees.append(('cypress', (x, y, T.hs(x, y)), (1.2, 1.2, rng.uniform(8, 12)), CYPRESS, 'plinth'))
        else:
            trees.append(('round', (x, y, T.hs(x, y)), (s, s, s * rng.uniform(0.9, 1.2)), AUTUMN[int(rng.integers(len(AUTUMN)))], 'plinth'))
        placed += 1
    emit(lm, "CAP_V_Lakeside", coll, [mats['painted']], estate=False)


def plant(trees, coll, mats, rng):
    """Every tree / shrub / rock collected above, as one object per frame (estate or plinth)."""
    protos = {'round': fc.proto_round(), 'cypress': fc.proto_cypress(), 'rock': fc.proto_round(6)}
    for frame in ('estate', 'plinth'):
        mb = MB()
        for t in trees:
            fr = t[4] if len(t) > 4 else 'estate'
            if fr != frame:
                continue
            kind, pos, scl, col = t[:4]
            if kind == 'round':
                trunk_h = scl[2] * 0.3
                mb.box(pos[0], pos[1], pos[2], 0.2 * scl[0] ** 0.5, 0.2 * scl[0] ** 0.5, trunk_h + 0.2, 0.0, WOOD_D)
                p = (pos[0], pos[1], pos[2] + trunk_h + scl[2] * 0.6)
                c0 = fc.jit(rng, col, 0.08)
                fc.scatter(mb, protos['round'], [p], [(scl[0] * 0.7, scl[1] * 0.7, scl[2] * 0.6)], [rng.uniform(0, 6.3)], [c0])
                if scl[0] > 1.5:                                   # a second, smaller lobe: less of a lollipop
                    a = rng.uniform(0, 6.3)
                    q = (p[0] + 0.45 * scl[0] * math.cos(a), p[1] + 0.45 * scl[0] * math.sin(a), p[2] + 0.25 * scl[2])
                    fc.scatter(mb, protos['round'], [q], [(scl[0] * 0.45, scl[1] * 0.45, scl[2] * 0.4)], [a], [fc.lighten(c0, 1.08)])
            elif kind == 'cypress':
                fc.scatter(mb, protos['cypress'], [pos], [(scl[2] * 0.16, scl[2] * 0.16, scl[2])], [rng.uniform(0, 6.3)], [fc.jit(rng, col, 0.08)])
            else:
                fc.scatter(mb, protos['rock'], [pos], [scl], [rng.uniform(0, 6.3)], [col], smooth=False)
        emit(mb, "CAP_V_Trees_" + frame, coll, [mats['painted']], estate=(frame == 'estate'))


# =============================================================================
# Orchestration
# =============================================================================
def build_all():
    t0 = time.time()
    stats = {}
    ANCHORS.clear()
    stats['removed_defaults'] = fc.remove_factory_defaults()
    fc.ROOT_NAME, saved = ROOT_NAME, fc.ROOT_NAME
    fc.clear_previous()
    fc.ROOT_NAME = saved
    root = bpy.data.collections.new(ROOT_NAME)
    bpy.context.scene.collection.children.link(root)
    coll = {k: fc.new_coll(v, root) for k, v in (('terrain', "Terrain & Lake"), ('house', "Villa"),
                                                   ('grounds', "Grounds"), ('land', "Vineyards & Land"),
                                                   ('scene', "Lights & Cameras"))}
    fc.haze_group()
    mats = {'painted': fc.mat_painted(), 'terrain': mat_estate_terrain(), 'water': fc.mat_water(), 'fire': fc.mat_fire()}
    fc.WINDOW_ALPHA_CENTER = GATE_E                    # the dusk lamp wave starts at the gate
    T = VTerrain()
    rng = np.random.default_rng(1180)
    lights, wins, trees, steam = Lights(), [], [], []
    fire = MB()
    fire_land = MB()
    ANCHORS.update({'_T': T, '_root': root, '_lights': lights, '_wins': wins, '_steam': steam})
    build_house(T, coll['house'], mats, lights, wins, trees, rng, fire, steam)
    build_outbuildings(T, coll['grounds'], mats, lights, wins, trees, rng, fire, steam)
    build_land(T, coll['land'], mats, lights, trees, rng, fire_land)
    build_terrain(T, coll['terrain'], mats)        # after the land: the vineyards paint the soil mask
    plant(trees, coll['land'], mats, rng)
    emit(fire, "CAP_V_Flames", coll['house'], [mats['fire']])
    emit(fire_land, "CAP_V_Flames_Land", coll['land'], [mats['fire']], estate=False)
    # cameras: the hero view is the aerial concept's (high, from the south-west, over the gate)
    gx, gy = to_plinth(GATE_E)
    tgt = to_plinth((4.0, -6.0))
    fc.HERO_CAM = ((gx / MS - 22.0, gy / MS - 30.0, 32.0), (tgt[0] / MS, tgt[1] / MS, 2.0))
    fc.CAMERAS = []
    fc.build_scene(coll['scene'], [])
    tri = 0
    for o in root.all_objects:
        if o.type == 'MESH':
            tri += sum(len(p.vertices) - 2 for p in o.data.polygons)
    stats.update({'objects': len(root.all_objects), 'approx_tris': tri, 'windows': len(wins),
                  'lights': len(lights.L), 'vine_pieces': ANCHORS.get('vine_pieces'), 'trees': len(trees),
                  'columns': ANCHORS.get('columns'), 'statues': ANCHORS.get('statues'), 'total_secs': round(time.time() - t0, 2)})
    return stats


# =============================================================================
# Manifest (city.json v1 with the estate extras: kind, anchors, terrain_grid)
# =============================================================================
def floor_z(T, x, y):
    """Walking height (real metres) at a plinth point: house floors, the court, else the ground."""
    ex, ey = x - OFFSET[0], y - OFFSET[1]
    x0, y0, x1, y1 = HOUSE
    if x0 <= ex <= x1 and y0 <= ey <= y1:
        cx0, cy0, cx1, cy1 = COURT
        if cx0 < ex < cx1 and cy0 < ey < cy1:
            return FLOOR
        return FLOOR
    if -5.5 <= ex <= 5.5 and -37.0 <= ey <= y0:        # the portico steps
        return TERRACE + (FLOOR - TERRACE) * max(0.0, min(1.0, (ey + 37.0) / 3.0))
    return T.hs(x, y)


def walk_lines():
    """Walkable polylines in plinth real metres (estate points are moved by OFFSET)."""
    E = lambda pts: [to_plinth(p) for p in pts]
    x0, y0, x1, y1 = HOUSE
    loop = [(-16.75, -11.75), (16.75, -11.75), (16.75, 11.75), (-16.75, 11.75), (-16.75, -11.75)]
    return {
        'lagoon_loop': lake_ring(9.0, 120) + [lake_ring(9.0, 120)[0]],
        'peristyle': E(loop),
        'road': [to_plinth((GATE_E[0], GATE_E[1] - 1.5))] + ROAD[1:],
        'lane': LANE,
        'drive': E([(GATE_E[0], GATE_E[1] - 1.5), (GATE_E[0], -56.0), (-12.0, -48.0), (0.0, -40.0), (0.0, -36.5),
                    (0.0, -30.5), (0.0, -21.0), (0.0, -13.5), (0.0, -11.75)]),
        'great_hall': E([(0.0, -21.0), (-7.0, -22.0), (-17.5, -19.0), (-24.0, -22.0)]),
        'dining': E([(0.0, -21.0), (7.0, -22.0), (10.0, -19.6), (16.0, -19.6)]),
        'gallery': E([(0.0, 11.75), (0.0, 13.5), (0.0, 17.0), (-16.0, 17.0)]) ,
        'gallery_e': E([(0.0, 17.0), (16.0, 17.0)]),
        'kitchen': E([(16.75, -6.0), (18.5, -6.0), (23.0, -3.0), (x1 + 1.0, -1.5), (37.0, -1.5), (48.0, -1.5), (48.0, 10.0),
                      (46.0, 13.0), (46.0, 20.0)]),
        'garden_gate': E([(48.0, -1.5), (62.0, 0.0), (E_GATE_E[0] + 2.0, 0.0)]) + GARDEN_PATH[1:],
        'west': E([(-16.75, -6.0), (-18.5, -6.0), (-23.5, -6.0), (x0 - 1.0, -6.0), (-40.0, -6.0)]),
        'stables': E([(GATE_E[0], -56.0), (-40.0, -46.0), (-46.0, -30.0), (-46.0, -6.0), (-46.0, 20.0), (N_GATE_E[0], 27.0),
                      (N_GATE_E[0], 31.5)]) + NORTH_PATH[1:],
        'west_link': E([(-40.0, -6.0), (-46.0, -6.0)]),
    }


def build_graph(T, lines, step=3.0, snap=4.0):
    nodes, edges = [], []

    def node_at(p, allow_snap):
        if allow_snap and nodes:
            N = np.array([n[:2] for n in nodes])
            d = np.linalg.norm(N - np.asarray(p[:2]), axis=1)
            i = int(np.argmin(d))
            if d[i] < snap:
                return i
        nodes.append((float(p[0]), float(p[1]), floor_z(T, p[0], p[1]) + 0.02))
        return len(nodes) - 1

    for name, pts in lines.items():
        P = fc.resample([tuple(p) for p in pts], step)
        if np.linalg.norm(P[-1] - np.asarray(pts[-1][:2])) > 0.3:
            P = np.vstack([P, np.asarray(pts[-1][:2])])
        idx = []
        for i, p in enumerate(P):
            idx.append(node_at(p, i == 0 or i == len(P) - 1))
        for a, b in zip(idx[:-1], idx[1:]):
            if a != b:
                edges.append([a, b, 1.2 if name in ('road', 'lane') else 0.8])
    k = 1.0 / MS
    return {'nodes': [[round(x * k, 3), round(y * k, 3), round(z * k, 3)] for x, y, z in nodes],
            'edges': [[a, b, round(w * k, 3)] for a, b, w in edges]}


def zone(T, rng, zid, poly_e, n, density, estate=True):
    poly = [to_plinth(p) for p in poly_e] if estate else poly_e
    P = np.array(poly)
    pts = []
    for _ in range(n * 40):
        if len(pts) >= n:
            break
        x, y = rng.uniform(P[:, 0].min(), P[:, 0].max()), rng.uniform(P[:, 1].min(), P[:, 1].max())
        if points_in_poly(np.array([x]), np.array([y]), poly)[0]:
            pts.append([round(x / MS, 3), round(y / MS, 3), round((floor_z(T, x, y) + 0.02) / MS, 3)])
    return {'id': zid, 'poly': [[round(x / MS, 3), round(y / MS, 3)] for x, y in poly], 'density': density, 'points': pts}


def build_manifest(cfg, report):
    import anchors as A
    import sunarc
    T = ANCHORS['_T']
    rng = np.random.default_rng(23)
    graph = build_graph(T, walk_lines())
    report['street_graph'] = {'nodes': len(graph['nodes']), 'edges': len(graph['edges'])}
    def route(pts_e, estate=True):
        return A.graph_route(graph, [[(to_plinth(p) if estate else p)[0] / MS, (to_plinth(p) if estate else p)[1] / MS] for p in pts_e])
    ring = lake_ring(9.0, 12)
    routes = {
        'road_to_gate': route([ROAD[-1], ROAD[2], to_plinth((GATE_E[0], GATE_E[1] - 1.5))], False),
        'stable_route': route([(GATE_E[0], -56.0), (-46.0, -30.0), (-46.0, 15.0)]),
        'supper': route([(0.0, -36.5), (0.0, -21.0), (16.0, -19.6)]),
        'peristyle_loop': route([(0.0, -11.75), (16.75, -11.75), (16.75, 11.75), (0.0, 11.75), (-16.75, 11.75), (-16.75, -11.75), (0.0, -11.75)]),
        'gallery_walk': route([(16.0, -19.6), (7.0, -22.0), (0.0, -13.5), (-16.75, -11.75), (-16.75, 11.75), (0.0, 13.5), (-16.0, 17.0)]),
        'garden_to_bath': route([(-16.0, 17.0), (0.0, 11.75), (16.75, 0.0), (16.75, -6.0), (37.0, -1.5), (48.0, 10.0), (46.0, 20.0)]),
        'lagoon_riding_loop': route([(GATE_E[0], -56.0), (-46.0, 15.0), (N_GATE_E[0], 31.5)] , True) [:-1]
                              + route([to_plinth((N_GATE_E[0], 31.5))] + ring + [ring[0]], False),
    }
    for rid, pts in routes.items():
        report.setdefault('routes', {})[rid] = {'points': len(pts), 'length_m': round(A.polylen(pts) * MS, 1)}
    zones = [
        zone(T, rng, 'arrival_court', [(-44, -56), (10, -56), (24, -50), (24, -38), (-44, -38)], 14, 0.35),
        zone(T, rng, 'stable_yard', [(-49, -28), (-32, -28), (-32, 18), (-49, 18)], 8, 0.5),
        zone(T, rng, 'peristyle', [(-18, -13), (18, -13), (18, -10.6), (-18, -10.6)], 6, 0.3),
        zone(T, rng, 'kitchen_garden', [(35, -23), (61, -23), (61, 11), (35, 11)], 6, 0.4),
        zone(T, rng, 'vineyard_south', [(-120, -140), (120, -140), (120, -100), (-120, -100)], 10, 0.3, estate=False),
    ]
    lights = ANCHORS['_lights'].L
    for p, alpha in ANCHORS['_wins']:
        x, y = to_plinth(p[:2])
        lights.append({'pos': [round(x / MS, 3), round(y / MS, 3), round(p[2] / MS, 3)], 'kind': 'window', 'strength': 0.25,
                       'order': round(float(alpha), 3)})
    anchors = {
        'gate_stop': P((GATE_E[0], GATE_E[1] + 2.0, TERRACE)),
        'arrival_court': P((-14.0, -46.0, TERRACE)),
        'stable_door': P((-49.5, -6.0, TERRACE)),
        'entry_hall': P((0.0, -21.0, FLOOR)),
        'private_dining': P((13.0, -22.5, FLOOR)),
        'hearth_offer': P((13.0, -14.6, FLOOR)),
        'kitchen_service': P((22.6, -6.0, FLOOR)),
        'gallery_entry': P((0.0, 13.5, FLOOR)),
        'aegis_painting': P(ANCHORS['aegis_painting']),
        'bath_entry': P(ANCHORS['bath_entry']),
        'cold_pool': P(ANCHORS['cold_pool']),
        'heated_pool': P(ANCHORS['heated_pool']),
        'bath_fire': P(ANCHORS['bath_fire']),
        'jetty': [round(ANCHORS['jetty'][0] / MS, 3), round(ANCHORS['jetty'][1] / MS, 3), 0.1],
    }
    # landmark cameras (target in model metres; dist in model metres)
    def cam(lid, label, p, dist, yaw, pitch):
        return {'id': lid, 'label': label, 'camera': {'target': p, 'dist': dist, 'yaw': yaw, 'pitch': pitch}}
    court = P((0.0, 0.0, FLOOR))
    landmarks = [
        cam('overview', "The estate", P((10.0, 10.0, TERRACE)), 62.0, -105.0, 34.0),
        cam('arrival', "Return to the Villa: the gate", P((GATE_E[0] + 6, GATE_E[1] + 8, TERRACE + 2)), 16.0, -110.0, 24.0),
        cam('peristyle', "The peristyle and its statues", court, 13.0, -65.0, 48.0),
        cam('gallery', "Landric's gallery: Duel Before The Walls", P((-12.0, 18.5, FLOOR + 2.0)), 7.0, -20.0, 58.0),
        cam('dining', "The private dining room", P((13.0, -21.0, FLOOR)), 7.0, -110.0, 62.0),
        cam('bathhouse', "The cold spring and the heated pool", P((46.0, 17.0, TERRACE)), 10.0, -95.0, 38.0),
        cam('stables', "The stables", P((-52.0, -4.0, TERRACE + 1)), 13.0, 10.0, 40.0),
        cam('lake', "The lake and the riding path", [round(LAKE_C[0] / MS, 2), round(LAKE_C[1] / MS, 2), 0.0], 34.0, -125.0, 30.0),
    ]
    # the ground as a height grid (model metres), for the Known World miniature to stand on
    n = 65
    xs = np.linspace(-R, R, n)
    GX, GY = np.meshgrid(xs, xs)
    grid = (T.h(GX, GY) / MS).round(3)
    sun = cfg['sun']
    rise, sset = sunarc.sunrise_sunset(sun['latitude_deg'], sun['default_day_of_year'])
    man = {
        'id': cfg['id'], 'name': cfg['name'], 'version': 1, 'kind': 'estate',
        'model_scale': MS, 'extent': [-HALF, -HALF, HALF, HALF], 'sea_level': 0.0,
        'world_map': cfg['world_map'],
        'sun': dict(sun, sunrise_h=round(rise, 3), sunset_h=round(sset, 3)),
        'files': {'model': 'city.glb', 'proxies': 'proxies.glb', 'terrain_albedo': 'terrain_albedo.png', 'thumb': 'thumb.png'},
        'street_graph': graph,
        'spawn_zones': zones,
        'ship_lanes': [], 'moorings': [], 'anchored_ships': [], 'boats': [], 'berths': [],
        'venues': [],
        'routes': routes,
        'night_lights': lights,
        'landmarks': landmarks,
        'steam_vents': [P(p) for p in ANCHORS['_steam']],
        'events': [],
        'anchors': anchors,
        'cutaway': {'roofs': ['CAP_V_Roof_'], 'upper': ['CAP_V_Upper']},
        'terrain_grid': {'n': n, 'z': grid.ravel().tolist()},
    }
    return man


def write_proxies(root):
    T = ANCHORS['_T']
    Pc = bpy.data.collections.new("Proxies")
    root.children.link(Pc)
    n = 101
    xs = np.linspace(-R, R, n)
    X, Y = np.meshgrid(xs, xs)
    Z = T.h(X, Y)
    k = 1.0 / MS
    verts = np.column_stack([X.ravel() * k, Y.ravel() * k, Z.ravel() * k])
    idx = np.arange(n * n).reshape(n, n)
    faces = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()])
    me = bpy.data.meshes.new("CAP_Proxy_Terrain")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    Pc.objects.link(bpy.data.objects.new("CAP_Proxy_Terrain", me))
    mb = MB()
    x0, y0, x1, y1 = HOUSE
    ix0, iy0, ix1, iy1 = INNER
    for a, b, c, d in ((x0, y0, x1, iy0), (x0, iy1, x1, y1), (x0, iy0, ix0, iy1), (ix1, iy0, x1, iy1)):
        mb.box((a + c) / 2, (b + d) / 2, TERRACE, c - a, d - b, EAVE + 2.0 - TERRACE, 0.0, (0.5, 0.5, 0.5))
    for a, b, c, d in (STABLE, HAYSHED, BATH, ANNEX):
        mb.box((a + c) / 2, (b + d) / 2, TERRACE, c - a, d - b, 5.0, 0.0, (0.5, 0.5, 0.5))
    W = WALL_E + [WALL_E[0]]
    for a, b in zip(W[:-1], W[1:]):
        u, L = unit(a, b)
        m = (np.asarray(a) + np.asarray(b)) / 2
        mb.box(m[0], m[1], TERRACE - 0.5, L, 0.8, 3.6, math.atan2(u[1], u[0]), (0.5, 0.5, 0.5))
    emit(mb, "CAP_Proxy_Buildings", Pc, [])
    Pc.hide_render = True
    Pc.hide_viewport = True
    return Pc
