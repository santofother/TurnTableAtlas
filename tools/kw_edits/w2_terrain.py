"""W2: reshape the Known World terrain in KnownWorld.blend (docs/world_map/PLAN.md, card W2).

1. Oravian Expanse (between Astera, Madravella and Calloway): rugged hills and low mountains, up to ~1,500 m, that
   rise towards and join the Veryan Range. River valleys, lakes and the cities stay where they are (the hills are
   masked off around them), so the blend's rivers, lakes and towns keep sitting on the ground.
2. Dovaran Crown: the islands are lifted into a rugged highland and their coasts recut as fjords (long, narrow, steep
   inlets, some branching) with skerries offshore. Dovehall's site and settlement are left untouched.

    $BLENDER -b ~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend --python tools/kw_edits/w2_terrain.py
    ... -- --dry-run     compute and write previews only, save nothing

What it edits (and saves): albedo_land.png and T_FeatureMasks alpha (the land masks: cleared in the fjords),
T_WaterData (coast distance / shallows / reef: the fjords get deep channel water instead of shore shallows),
T_TerrainData (textures/terrain_data.exr: B = elevation / 10000 m, R/G = 3.106 x its
pixel gradient, used for the material normals), T_Hero_Dovehall (textures/hero_Dovehall_z.exr: R = metres), the
TERRAIN_* / TLOD* / HERO_Dovehall meshes, and every mesh draped on the ground (roads, villages, rivers, lakes, cities,
tree canvas) by the same height change. SEA_Surface is a full plane at z = 0 and the water shader reads the same
height data, so no water object needs editing.

Re-runnable: the first run copies the edited images to textures/pre_w2/ and stores every touched mesh's original
z in a point attribute "w2_z0"; every run starts from those, so running it again gives the same result.
Back up the blend first (KnownWorld.<date>.bak.blend), as the plan says.
"""
import math
import os
import shutil
import sys

import bpy
import numpy as np

DRY = "--dry-run" in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
SEED = 2026
UNIT_M = 16093.44                    # 1 blend unit = 10 miles
B_TO_MESH = 10000.0 / UNIT_M         # T_TerrainData B -> terrain mesh local z (objects are scaled 15x in z)
GRAD_K = 3.106                       # T_TerrainData R/G = GRAD_K * np.gradient(B) (measured on the blend)

# --- Oravian Expanse: soft polygon (world units, +X east, +Y north), envelope height grows towards the Veryan
ORAV_POLY = [(94.0, 192.0), (110.0, 193.0), (127.0, 192.5), (130.5, 184.0), (129.0, 172.0), (122.0, 163.5),
             (110.0, 158.5), (99.0, 159.0), (91.5, 164.0), (89.5, 175.0), (90.5, 186.0)]
ORAV_FEATHER = 3.5
ORAV_PEAK_M = 1500.0                 # cap on the final height inside the Expanse (below the Veryan snow)
ORAV_X_MAX = 130.5                   # HERO_GreatGate starts at x 131.9: stay off it
ORAV_CITIES = ["astera", "madravella", "calloway", "ossmere", "calderra", "ruins_of_oravessa"]

# --- Dovaran Crown
DOV_BOX = (124.0, 172.0, 103.0, 141.0)   # x0, x1, y0, y1 search box; land = kingdom id 7 (T_Kingdoms)
DOV_KINGDOM_ID = 7
DOVEHALL = (146.3, 125.3)
HERO = dict(x0=141.49374389648438, y0=122.09375, sx=9.612500190734863, sy=6.412499904632568)


def log(*a):
    print("[W2]", *a, flush=True)


# ---------------------------------------------------------------- image helpers
def img_px(img):
    w, h = img.size
    a = np.empty(w * h * img.channels, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, img.channels)       # row 0 = bottom (y min)


def load_pristine(img, folder):
    """Pixels of the image as it was before W2 (copied to textures/pre_w2 on the first run)."""
    src = bpy.path.abspath(img.filepath)
    keep = os.path.join(folder, os.path.basename(src))
    if not os.path.exists(keep):
        os.makedirs(folder, exist_ok=True)
        shutil.copy2(src, keep)
        log("kept original", keep)
    tmp = bpy.data.images.load(keep, check_existing=False)
    tmp.colorspace_settings.name = "Non-Color"
    a = img_px(tmp).copy()
    bpy.data.images.remove(tmp)
    return a


def bilinear(grid, gx, gy):
    """Sample grid (h, w) at fractional pixel coords (gx = column, gy = row, pixel centres at integers)."""
    h, w = grid.shape
    gx = np.clip(gx, 0, w - 1.001)
    gy = np.clip(gy, 0, h - 1.001)
    x0 = np.floor(gx).astype(int)
    y0 = np.floor(gy).astype(int)
    fx = gx - x0
    fy = gy - y0
    return (grid[y0, x0] * (1 - fx) * (1 - fy) + grid[y0, x0 + 1] * fx * (1 - fy)
            + grid[y0 + 1, x0] * (1 - fx) * fy + grid[y0 + 1, x0 + 1] * fx * fy)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- noise
def _hash(ix, iy, seed):
    n = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return n - np.floor(n)


def vnoise(x, y, seed):
    ix = np.floor(x)
    iy = np.floor(y)
    fx = x - ix
    fy = y - iy
    ux = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    uy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    a = _hash(ix, iy, seed)
    b = _hash(ix + 1, iy, seed)
    c = _hash(ix, iy + 1, seed)
    d = _hash(ix + 1, iy + 1, seed)
    return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy      # 0..1


def fbm(x, y, seed, octaves=4, freq=1.0):
    s, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        s = s + amp * vnoise(x * freq, y * freq, seed + o * 17)
        tot += amp
        amp *= 0.5
        freq *= 2.03
    return s / tot


def ridged(x, y, seed, octaves=5, freq=1.0, stretch=1.0):
    """Ridged multifractal, 0..~1; stretch > 1 elongates ridges north-south."""
    wx = x + 0.9 * (fbm(x, y, seed + 101, 3, freq * 0.5) - 0.5) / freq
    wy = y + 0.9 * (fbm(x, y, seed + 202, 3, freq * 0.5) - 0.5) / freq
    s, amp, tot, prev = 0.0, 1.0, 0.0, 1.0
    f = freq
    for o in range(octaves):
        n = vnoise(wx * f, wy * f / stretch, seed + o * 31)
        r = 1.0 - np.abs(2.0 * n - 1.0)
        r = r * r
        s = s + amp * r * (0.5 + 0.5 * prev)
        prev = r
        tot += amp
        amp *= 0.5
        f *= 2.1
    return s / tot


# ---------------------------------------------------------------- geometry helpers
def poly_sdist(px, py, poly):
    """Signed distance to a polygon (negative inside)."""
    P = np.array(poly)
    d = np.full(px.shape, np.inf)
    inside = np.zeros(px.shape, bool)
    n = len(P)
    for i in range(n):
        ax, ay = P[i]
        bx, by = P[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        t = np.clip(((px - ax) * ex + (py - ay) * ey) / (ex * ex + ey * ey), 0, 1)
        d = np.minimum(d, np.hypot(px - ax - t * ex, py - ay - t * ey))
        cond = ((ay > py) != (by > py)) & (px < (bx - ax) * (py - ay) / (by - ay + 1e-12) + ax)
        inside ^= cond
    return np.where(inside, -d, d)


def nearest_dist(qx, qy, pts, chunk=4096):
    """Distance from each query point to the nearest of pts (N, 2); brute force in chunks."""
    out = np.full(qx.shape, 1e9, dtype=np.float32)
    if len(pts) == 0:
        return out
    q = np.stack([qx.ravel(), qy.ravel()], 1).astype(np.float32)
    o = out.ravel()
    P = pts.astype(np.float32)
    for i in range(0, len(q), chunk):
        dq = q[i:i + chunk, None, :] - P[None, :, :]
        o[i:i + chunk] = np.sqrt((dq * dq).sum(-1).min(1))
    return o.reshape(qx.shape)


def mesh_points(names, box, step=0.05):
    """World XY of the given meshes' vertices inside box, thinned to one per step-cell."""
    x0, x1, y0, y1 = box
    pts = []
    for nm in names:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != "MESH":
            continue
        co = np.empty(len(ob.data.vertices) * 3, dtype=np.float32)
        ob.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        w = co @ M[:3, :3].T + M[:3, 3]
        m = (w[:, 0] > x0) & (w[:, 0] < x1) & (w[:, 1] > y0) & (w[:, 1] < y1)
        pts.append(w[m, :2])
    if not pts:
        return np.zeros((0, 2))
    p = np.concatenate(pts)
    if len(p) == 0:
        return p
    _, idx = np.unique(np.round(p / step).astype(np.int64), axis=0, return_index=True)
    return p[idx]


# ---------------------------------------------------------------- the map grid
class Grid:
    def __init__(self, w, h):
        m = bpy.data.materials["M_Terrain"].node_tree.nodes["WorldUV"]
        self.loc = list(m.inputs["Location"].default_value)
        self.sc = list(m.inputs["Scale"].default_value)
        self.w, self.h = w, h
        self.px = 1.0 / (self.sc[0] * w)         # units per pixel (x)
        self.py = 1.0 / (self.sc[1] * h)

    def to_pix(self, x, y):
        """World -> fractional pixel coords (column, row from the bottom), pixel centres at integers."""
        return (x * self.sc[0] + self.loc[0]) * self.w - 0.5, (y * self.sc[1] + self.loc[1]) * self.h - 0.5

    def to_world(self, c, r):
        return ((c + 0.5) / self.w - self.loc[0]) / self.sc[0], ((r + 0.5) / self.h - self.loc[1]) / self.sc[1]

    def window(self, box, pad=2):
        c0, r0 = self.to_pix(box[0], box[2])
        c1, r1 = self.to_pix(box[1], box[3])
        return (max(int(r0) - pad, 0), min(int(r1) + pad, self.h), max(int(c0) - pad, 0), min(int(c1) + pad, self.w))


# ---------------------------------------------------------------- 1. Oravian Expanse
def oravian(x, y, e, prot):
    """New elevation (m) at world points x, y with old elevation e (m); prot(x, y) -> 0 at rivers/lakes/towns, 1 away."""
    sd = poly_sdist(x, y, ORAV_POLY)
    mask = smoothstep(ORAV_FEATHER, -ORAV_FEATHER, sd) * smoothstep(ORAV_X_MAX, ORAV_X_MAX - 3.0, x)
    mask *= smoothstep(0.0, 60.0, e)                                    # never raise the sea or the shore line
    north = smoothstep(158.0, 191.0, y)                                 # higher towards the Veryan Range
    env = 850.0 + 950.0 * north
    r = ridged(x, y, SEED, octaves=5, freq=0.6, stretch=1.6)
    broad = fbm(x, y, SEED + 7, 3, 0.12)                                # massifs and saddles
    rn = np.clip((r - 0.18) / 0.45, 0.0, 1.0) ** 1.4                    # sharp ridges, deep cuts between them
    h = env * np.clip((0.04 + 0.96 * rn) * (0.55 + 0.9 * broad), 0, 1.3)
    delta = mask * prot * h
    # cap: don't raise past ~1,500 m, never lower what is already higher (the Veryan foothills)
    target = e + delta
    soft = np.where(target > ORAV_PEAK_M - 250.0,
                    ORAV_PEAK_M - 250.0 + 250.0 * np.tanh((target - (ORAV_PEAK_M - 250.0)) / 250.0), target)
    return np.maximum(e, np.minimum(target, soft))


# ---------------------------------------------------------------- 2. Dovaran Crown fjords
class Fjords:
    def __init__(self, G, e, kid, prot_pts):
        rng = np.random.default_rng(SEED)
        r0, r1, c0, c1 = G.window(DOV_BOX, pad=6)
        self.win = (r0, r1, c0, c1)
        sub_e = e[r0:r1, c0:c1]
        sub_k = kid[r0:r1, c0:c1]
        rr, cc = np.mgrid[r0:r1, c0:c1]
        X, Y = G.to_world(cc, rr)
        self.G = G
        # Dovaran land: above sea and within 2 px of kingdom 7 (the id map is a little shy at the coast)
        k7 = sub_k == DOV_KINGDOM_ID
        for _ in range(2):
            k7 = k7 | np.roll(k7, 1, 0) | np.roll(k7, -1, 0) | np.roll(k7, 1, 1) | np.roll(k7, -1, 1)
        inbox = (X > DOV_BOX[0]) & (X < DOV_BOX[1]) & (Y > DOV_BOX[2]) & (Y < DOV_BOX[3])
        land = (sub_e > 0) & k7 & inbox
        self.land = land
        # coast pixels (land next to sea) and distances in / out
        sea = ~(sub_e > 0)
        coast = land & (np.roll(sea, 1, 0) | np.roll(sea, -1, 0) | np.roll(sea, 1, 1) | np.roll(sea, -1, 1))
        cpts = np.stack([X[coast], Y[coast]], 1)
        dist = nearest_dist(X, Y, cpts)
        self.din = np.where(land, dist, 0.0)                # units inland from the coast
        near = (~land) & (dist < 2.0) & inbox
        self.dout = np.where(near, dist, 99.0)              # units offshore (Dovaran waters only)
        self.dov_water = near
        log(f"Dovaran: {land.sum()} land px, {coast.sum()} coast px, max inland {self.din.max():.2f} u")

        # islands (4-connected components)
        lab = np.zeros(land.shape, int)
        n = 0
        for (i, j) in zip(*np.nonzero(land)):
            if lab[i, j]:
                continue
            n += 1
            stack = [(i, j)]
            lab[i, j] = n
            while stack:
                a, b = stack.pop()
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    p, q = a + da, b + db
                    if 0 <= p < land.shape[0] and 0 <= q < land.shape[1] and land[p, q] and not lab[p, q]:
                        lab[p, q] = n
                        stack.append((p, q))
        # gradient of the inland distance (points inland), for steering
        gy, gx = np.gradient(self.din)
        self.gx, self.gy = gx, gy

        def din_at(x, y):
            c, r = G.to_pix(x, y)
            return bilinear(self.din, c - c0, r - r0)

        def grad_at(x, y):
            c, r = G.to_pix(x, y)
            vx = bilinear(gx, c - c0, r - r0) / G.px
            vy = bilinear(gy, c - c0, r - r0) / G.py
            n_ = math.hypot(vx, vy) + 1e-9
            return vx / n_, vy / n_

        self.din_at = din_at
        prot = prot_pts
        segs = []          # (ax, ay, bx, by, half-width at a, half-width at b, depth factor)
        others = np.zeros((0, 2))
        heads = 0
        for isl in range(1, n + 1):
            m = lab == isl
            maxin = float(self.din[m].max())
            if maxin < 0.35:
                continue                                    # islets: skerry-sized, leave them
            ic = coast & m
            ci = np.argwhere(ic)
            rng.shuffle(ci)
            spacing = 1.9 if maxin > 1.5 else 1.35
            starts = []
            for (i, j) in ci:
                sx, sy = X[i, j], Y[i, j]
                if math.hypot(sx - DOVEHALL[0], sy - DOVEHALL[1]) < 1.6:
                    continue
                if all(math.hypot(sx - a, sy - b) >= spacing for a, b in starts):
                    starts.append((sx, sy))
            for (sx, sy) in starts:
                L = maxin * rng.uniform(1.0, 1.8) if maxin > 1.5 else maxin * rng.uniform(0.7, 1.2)
                L = min(L, 5.5)
                hw0 = rng.uniform(0.21, 0.27) if maxin > 1.5 else rng.uniform(0.16, 0.2)
                arms = [(sx, sy, None, L, hw0, 1.0)]
                first = len(segs)
                while arms:
                    ax, ay, d0, L_, w0, depthmul = arms.pop()
                    dx, dy = grad_at(ax, ay) if d0 is None else d0
                    # start offshore so the mouth opens to the sea
                    if d0 is None:
                        ax, ay = ax - dx * 0.35, ay - dy * 0.35
                    travelled, step = 0.0, 0.05
                    turn = rng.uniform(-1, 1)
                    branched = False
                    while travelled < L_:
                        t = travelled / L_
                        gxv, gyv = grad_at(ax, ay)
                        turn = 0.85 * turn + 0.15 * rng.normal() * 2.2
                        ang = math.atan2(dy, dx) + turn * 0.22
                        ndx, ndy = math.cos(ang), math.sin(ang)
                        ndx, ndy = 0.75 * ndx + 0.25 * gxv, 0.75 * ndy + 0.25 * gyv
                        nn = math.hypot(ndx, ndy) + 1e-9
                        dx, dy = ndx / nn, ndy / nn
                        bx, by = ax + dx * step, ay + dy * step
                        if din_at(bx, by) > 0.6 * maxin and travelled > 0.4:
                            break                           # don't cut the island in two
                        if math.hypot(bx - DOVEHALL[0], by - DOVEHALL[1]) < 1.1:
                            break
                        if len(prot) and np.min(np.hypot(prot[:, 0] - bx, prot[:, 1] - by)) < 0.15:
                            break                           # keep off lakes and villages
                        if len(others) and travelled > 0.3 and np.min(np.hypot(others[:, 0] - bx, others[:, 1] - by)) < 0.75:
                            break                           # keep clear of the other fjords
                        wa = w0 * (1 - 0.5 * t)
                        wb = w0 * (1 - 0.5 * min(1.0, (travelled + step) / L_))
                        segs.append((ax, ay, bx, by, wa, wb, depthmul))
                        ax, ay = bx, by
                        travelled += step
                        if not branched and depthmul == 1.0 and 0.3 < t < 0.7 and rng.random() < 0.025:
                            branched = True
                            side = rng.choice([-1, 1])
                            ba = math.atan2(dy, dx) + side * rng.uniform(0.7, 1.1)
                            arms.append((ax, ay, (math.cos(ba), math.sin(ba)), (L_ - travelled) * rng.uniform(0.4, 0.7),
                                         wa * 0.75, 0.8))
                    heads += 1
                if len(segs) > first:
                    others = np.concatenate([others, np.array(segs[first:])[:, 2:4]])
        self.segs = np.array(segs, dtype=np.float64).reshape(-1, 7)
        log(f"fjords: {heads} arms, {len(self.segs)} segments")

        # skerries: rocky islets scattered in Dovaran's near-shore waters
        cand = np.argwhere(self.dov_water & (self.dout > 0.12) & (self.dout < 1.3))
        pick = cand[rng.choice(len(cand), size=min(260, len(cand)), replace=False)]
        sk = []
        for (i, j) in pick:
            x_, y_ = X[i, j] + rng.uniform(-0.1, 0.1), Y[i, j] + rng.uniform(-0.1, 0.1)
            if math.hypot(x_ - DOVEHALL[0], y_ - DOVEHALL[1]) < 1.0:
                continue
            big = rng.random() < 0.2
            sk.append((x_, y_, rng.uniform(0.09, 0.16) if big else rng.uniform(0.025, 0.07), rng.uniform(25, 140)))
        # a few at fjord mouths
        for s in self.segs[::40]:
            if rng.random() < 0.5:
                sk.append((s[0] + rng.uniform(-0.25, 0.25), s[1] + rng.uniform(-0.25, 0.25), rng.uniform(0.03, 0.08),
                           rng.uniform(20, 80)))
        self.sk = np.array(sk).reshape(-1, 4)
        log(f"skerries: {len(self.sk)}")

    def fields(self, x, y):
        """Fjord cut (0..1, channel weight), fjord bed (m), skerry height (m, -inf where none)."""
        cut = np.zeros(x.shape)
        bed = np.zeros(x.shape)
        s = self.segs
        if len(s):
            # bounding-box prefilter
            bx0, bx1, by0, by1 = x.min() - 0.5, x.max() + 0.5, y.min() - 0.5, y.max() + 0.5
            m = (np.minimum(s[:, 0], s[:, 2]) < bx1) & (np.maximum(s[:, 0], s[:, 2]) > bx0) & \
                (np.minimum(s[:, 1], s[:, 3]) < by1) & (np.maximum(s[:, 1], s[:, 3]) > by0)
            for ax, ay, bx_, by_, wa, wb, dm in s[m]:
                ex, ey = bx_ - ax, by_ - ay
                L2 = ex * ex + ey * ey
                t = np.clip(((x - ax) * ex + (y - ay) * ey) / L2, 0, 1)
                d = np.hypot(x - ax - t * ex, y - ay - t * ey)
                hw = wa + (wb - wa) * t
                c = 1.0 - smoothstep(hw * 0.55, hw + 0.045, d)          # steep walls
                cut = np.maximum(cut, c)
                bed = np.minimum(bed, -(150.0 + 250.0 * dm) * c)
        sk = np.full(x.shape, -1e9)
        for sx, sy, r, hgt in self.sk:
            if sx + r < x.min() or sx - r > x.max() or sy + r < y.min() or sy - r > y.max():
                continue
            d = np.hypot(x - sx, y - sy) / r
            sk = np.maximum(sk, np.where(d < 1.6, -60.0 + (hgt + 60.0) * (1.0 - np.minimum(d, 1.6) ** 2 / 1.0), -1e9))
        return cut, bed, sk

    def apply(self, x, y, e, prot):
        """New elevation (m) at world points; e = old elevation (m)."""
        G = self.G
        r0, r1, c0, c1 = self.win
        c, r = G.to_pix(x, y)
        din = bilinear(self.din, c - c0, r - r0)
        dout = bilinear(np.minimum(self.dout, 3.0), c - c0, r - r0)
        landish = bilinear(self.land.astype(np.float64), c - c0, r - r0)
        dd = np.hypot(x - DOVEHALL[0], y - DOVEHALL[1])
        # highland: rugged, rising quickly from the shore, lower around Dovehall
        rg = ridged(x, y, SEED + 50, octaves=5, freq=0.9, stretch=1.0)
        amp = 280.0 + 420.0 * fbm(x, y, SEED + 60, 3, 0.35)
        lift = amp * (0.3 + 0.85 * rg) * smoothstep(0.0, 0.45, din) * smoothstep(0.2, 0.7, landish)
        lift *= smoothstep(0.0, 40.0, e) * smoothstep(0.6, 2.2, dd) * prot
        e1 = e + lift
        cut, bed, sk = self.fields(x, y)
        cut = cut * smoothstep(0.8, 1.2, dd)
        e2 = e1 + (np.minimum(e1, bed) - e1) * cut
        offshore = smoothstep(0.05, 0.15, dout) * (landish < 0.5)
        e3 = np.where((offshore > 0.5) & (sk > e2), sk, e2)
        return e3


# ---------------------------------------------------------------- mesh update
def shift_mesh(ob, dz_world_fn, box_list, baseline_attr="w2_z0"):
    """z = z0 + local dz at each vertex, with a separate baseline attribute per edit."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    att = me.attributes.get(baseline_attr)
    if att is None:
        if DRY:
            z0 = co[:, 2].copy()
        else:
            att = me.attributes.new(baseline_attr, "FLOAT", "POINT")
            att.data.foreach_set("value", co[:, 2])
            z0 = co[:, 2].copy()
    else:
        z0 = np.empty(n, dtype=np.float32)
        att.data.foreach_get("value", z0)
    # all draped meshes share the terrain's frame (location 0, unrotated; their stored 15x z scale is not in effect:
    # matrix_world is identity), so the same local dz keeps them on the ground
    w = co
    dz = np.zeros(n)
    sel = np.zeros(n, bool)
    for (x0, x1, y0, y1) in box_list:
        sel |= (w[:, 0] > x0) & (w[:, 0] < x1) & (w[:, 1] > y0) & (w[:, 1] < y1)
    if sel.any():
        dz[sel] = dz_world_fn(w[sel, 0], w[sel, 1])
    new = z0 + dz
    changed = float(np.abs(new - co[:, 2]).max()) if n else 0.0
    if not DRY:
        co[:, 2] = new
        me.vertices.foreach_set("co", co.ravel())
        me.update()
    return changed, int((np.abs(dz) > 1e-6).sum())


# ---------------------------------------------------------------- main
def main():
    root = bpy.path.abspath("//")
    keep = os.path.join(root, "textures", "pre_w2")
    td_img = bpy.data.images["T_TerrainData"]
    hero_img = bpy.data.images["T_Hero_Dovehall"]
    td = load_pristine(td_img, keep)
    hero = load_pristine(hero_img, keep)
    kid = np.round(img_px(bpy.data.images["T_Kingdoms"])[..., 0] * 255).astype(int)
    H, W = td.shape[:2]
    G = Grid(W, H)
    e_old = td[..., 2] * 10000.0
    log(f"T_TerrainData {W}x{H}, {G.px:.3f} u/px; hero {hero.shape[1]}x{hero.shape[0]}")

    # things the new relief must leave alone: rivers, lakes, towns, villages
    river_names = [o.name for o in bpy.data.objects if o.name.startswith("RIVER_")]
    lake_names = [o.name for o in bpy.data.objects if o.name.startswith(("LAKE_", "LAKES_"))]
    orav_box = (82.0, 136.0, 150.0, 199.0)
    pr_major = mesh_points(river_names, orav_box, 0.06)
    pr_minor = mesh_points(["RIVERS_Minor"], orav_box, 0.06)
    pl = mesh_points(lake_names, orav_box, 0.08)
    towns = np.array([tuple(bpy.data.objects["CITY_" + c].location[:2]) for c in ORAV_CITIES
                      if "CITY_" + c in bpy.data.objects])
    log(f"Oravian protect points: {len(pr_major)} river, {len(pr_minor)} minor river, {len(pl)} lake, {len(towns)} towns")

    # ---- Oravian on the T_TerrainData grid (protect fields at pixel res; heights supersampled 3x3)
    r0, r1, c0, c1 = G.window(orav_box)
    rr, cc = np.mgrid[r0:r1, c0:c1]
    X, Y = G.to_world(cc, rr)
    prot = (smoothstep(0.2, 1.3, nearest_dist(X, Y, pr_major)) * smoothstep(0.06, 0.45, nearest_dist(X, Y, pr_minor))
            * smoothstep(0.3, 1.2, nearest_dist(X, Y, pl)) * smoothstep(0.6, 2.0, nearest_dist(X, Y, towns)))

    def prot_orav(x, y):
        c, r = G.to_pix(x, y)
        return bilinear(prot, c - c0, r - r0)

    def super_delta(fn, win):
        a0, a1, b0, b1 = win
        acc = np.zeros((a1 - a0, b1 - b0))
        for oy in (-1 / 3, 0, 1 / 3):
            for ox in (-1 / 3, 0, 1 / 3):
                rr_, cc_ = np.mgrid[a0:a1, b0:b1].astype(np.float64)
                rr_ += oy
                cc_ += ox
                x, y = G.to_world(cc_, rr_)
                e = bilinear(e_old, cc_, rr_)
                acc += fn(x, y, e) - e
        return acc / 9.0

    d_orav = super_delta(lambda x, y, e: oravian(x, y, e, prot_orav(x, y)), (r0, r1, c0, c1))
    e_new = e_old.copy()
    e_new[r0:r1, c0:c1] += d_orav
    log(f"Oravian: raised {int((d_orav > 1).sum())} px, max +{d_orav.max():.0f} m, "
        f"peak now {e_new[r0:r1, c0:c1][d_orav > 1].max():.0f} m")

    # ---- Dovaran fjords
    dov_box = DOV_BOX
    dpr = mesh_points(["DECOR_villages"] + lake_names, dov_box, 0.05)
    F = Fjords(G, e_old, kid, dpr)
    dr0, dr1, dc0, dc1 = F.win
    rr, cc = np.mgrid[dr0:dr1, dc0:dc1]
    X, Y = G.to_world(cc, rr)
    dprot = smoothstep(0.08, 0.5, nearest_dist(X, Y, mesh_points(river_names + ["RIVERS_Minor"] + lake_names, dov_box, 0.05)))

    def prot_dov(x, y):
        c, r = G.to_pix(x, y)
        return bilinear(dprot, c - dc0, r - dr0)

    d_dov = super_delta(lambda x, y, e: F.apply(x, y, e, prot_dov(x, y)), F.win)
    e_new[dr0:dr1, dc0:dc1] += d_dov
    sub_old = e_old[dr0:dr1, dc0:dc1]
    sub_new = e_new[dr0:dr1, dc0:dc1]
    log(f"Dovaran: land px {int((sub_old > 0).sum())} -> {int((sub_new > 0).sum())}, "
        f"newly sea {int(((sub_old > 0) & (sub_new <= 0)).sum())}, newly land {int(((sub_old <= 0) & (sub_new > 0)).sum())}, "
        f"peak {sub_new.max():.0f} m")

    # ---- hero patch (Dovehall close-up), same fields at its own resolution
    hh, hw = hero.shape[:2]
    hr, hc = np.mgrid[0:hh, 0:hw]
    HX = HERO["x0"] + (hc + 0.5) * HERO["sx"] / hw
    HY = HERO["y0"] + (hr + 0.5) * HERO["sy"] / hh
    he_old = hero[..., 0].astype(np.float64)
    valid = he_old > -5000                                     # very low values mark the patch's own skirt
    he_new = np.where(valid, F.apply(HX, HY, he_old, prot_dov(HX, HY)), he_old)
    log(f"hero: land px {int((he_old > 0).sum())} -> {int((he_new > 0).sum())}, peak {he_new.max():.0f} m")

    # ---- write the images (R/G slope channels follow the height change)
    dB = (e_new - e_old) / 10000.0
    out = td.copy()
    out[..., 2] = td[..., 2] + dB
    out[..., 0] = td[..., 0] + GRAD_K * np.gradient(dB, axis=1)
    out[..., 1] = td[..., 1] + GRAD_K * np.gradient(dB, axis=0)
    hout = hero.copy()
    hout[..., 0] = he_new

    # land/sea masks: the terrain shader keeps land colour where albedo_land alpha x T_FeatureMasks alpha ("inland")
    # says land, whatever the height; clear both where the new height is under the sea (the fjords)
    masks = []
    for name in ("albedo_land.png", "T_FeatureMasks"):
        img = bpy.data.images[name]
        m = load_pristine(img, keep)
        if m.shape[:2] != e_new.shape:
            raise RuntimeError(f"{name}: size {m.shape[:2]} differs from T_TerrainData")
        wet = (e_new < 0.0) & (e_old >= 0.0)
        m[..., 3] = np.where(wet, 0.0, m[..., 3])
        masks.append((img, m))
        log(f"{name}: alpha cleared on {int(wet.sum())} px")
    # water: T_WaterData (2x the terrain grid) R = distance from the coast (0 at the shore, ~1 open sea), G = turquoise
    # shallows, B = reef. The fjords are deep: give them mid-channel water, no shallows, no reef
    wimg = bpy.data.images["T_WaterData"]
    wd = load_pristine(wimg, keep)
    wh, ww = wd.shape[:2]
    sy, sx = H / wh, W / ww
    rr2, cc2 = np.mgrid[0:wh, 0:ww]
    cc2 = (cc2 + 0.5) * sx - 0.5
    rr2 = (rr2 + 0.5) * sy - 0.5
    near = np.zeros((wh, ww), bool)
    for (a0, a1, b0, b1) in (G.window(DOV_BOX, pad=6), G.window(orav_box)):
        sub = (rr2 >= a0) & (rr2 < a1) & (cc2 >= b0) & (cc2 < b1)
        near |= sub
    idx = np.nonzero(near)
    en = bilinear(e_new, cc2[idx], rr2[idx])
    eo = bilinear(e_old, cc2[idx], rr2[idx])
    depth = np.clip(-en / 250.0, 0.0, 1.0)
    fj = (en < -5.0) & (eo > -5.0)
    sel = (idx[0][fj], idx[1][fj])
    wd[sel[0], sel[1], 0] = np.maximum(wd[sel[0], sel[1], 0], 0.35 + 0.35 * depth[fj])
    wd[sel[0], sel[1], 1] = 0.0
    wd[sel[0], sel[1], 2] = 0.0
    masks.append((wimg, wd))
    log(f"T_WaterData: {int(fj.sum())} px set to fjord water")

    # ---- meshes: delta lookup in world space
    dB_m = e_new - e_old

    def dz_world(x, y):
        c, r = G.to_pix(x, y)
        d = bilinear(dB_m, c, r)
        inh = (x >= HERO["x0"]) & (x <= HERO["x0"] + HERO["sx"]) & (y >= HERO["y0"]) & (y <= HERO["y0"] + HERO["sy"])
        if inh.any():
            hd = he_new - he_old
            gx = (x[inh] - HERO["x0"]) / HERO["sx"] * hw - 0.5
            gy = (y[inh] - HERO["y0"]) / HERO["sy"] * hh - 0.5
            d[inh] = bilinear(np.where(valid, hd, 0.0), gx, gy)
        return d / UNIT_M                                       # metres -> mesh z (1 unit = 10 mi)

    boxes = [orav_box, (DOV_BOX[0] - 1, DOV_BOX[1] + 1, DOV_BOX[2] - 1, DOV_BOX[3] + 1)]
    targets = [o for o in bpy.data.objects if o.type == "MESH" and (
        o.name.startswith(("TERRAIN_", "TLOD", "HERO_Dovehall", "RIVER", "LAKE", "DECOR_", "CITY_", "TREES_Canvas")))]
    moved = 0
    for ob in targets:
        if ob.name == "HERO_Dovehall":
            # the patch's own grid: z from its own (edited) height
            me = ob.data
            n = len(me.vertices)
            co = np.empty(n * 3, dtype=np.float32)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            att = me.attributes.get("w2_z0")
            if att is None:
                z0 = co[:, 2].copy()
                if not DRY:
                    att = me.attributes.new("w2_z0", "FLOAT", "POINT")
                    att.data.foreach_set("value", z0)
            else:
                z0 = np.empty(n, dtype=np.float32)
                att.data.foreach_get("value", z0)
            gx = np.round((co[:, 0] - HERO["x0"]) / HERO["sx"] * hw - 0.5).astype(int).clip(0, hw - 1)
            gy = np.round((co[:, 1] - HERO["y0"]) / HERO["sy"] * hh - 0.5).astype(int).clip(0, hh - 1)
            d = np.where(valid, he_new - he_old, 0.0)[gy, gx]
            if not DRY:
                co[:, 2] = z0 + d / UNIT_M
                me.vertices.foreach_set("co", co.ravel())
                me.update()
            log(f"mesh HERO_Dovehall: {int((np.abs(d) > 0.5).sum())} verts moved")
            continue
        ch, nv = shift_mesh(ob, dz_world, boxes)
        if nv:
            moved += 1
    log(f"meshes shifted: {moved} of {len(targets)}")

    if DRY:
        S = os.environ.get("W2_PREVIEW_DIR")
        if S:
            np.save(os.path.join(S, "td_new.npy"), out)
            np.save(os.path.join(S, "hero_new.npy"), hout)
            log("dry run: previews in", S)
        return

    for img, arr in [(td_img, out), (hero_img, hout)] + masks:
        img.pixels.foreach_set(np.ascontiguousarray(arr).ravel())
        img.update()
        img.save()
        log("saved", bpy.path.abspath(img.filepath))
    bpy.context.scene["kw_w2_terrain"] = "applied (tools/kw_edits/w2_terrain.py)"
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


if __name__ == "__main__":
    main()
