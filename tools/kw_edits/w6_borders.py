"""W6: redraw Valdora, Kervara and the Dovaran Crown round Kervara (user's marked screenshot, 2026-11-25).

The user marked the Atlas view `--orbit=172.5,166,0,-90,62,100` (1170 x 876 window): blue = new Valdora land,
red = Kervara's new extent, green = no man's land (unclaimed, id 0: no great realm holds it). The strokes are traced
below as polygons in that screen; every id-map pixel is projected through the same camera (Geo.Orbit, Fov 40,
relief at the Atlas' exaggeration) and tested against them, so the borders land where they were drawn.

- Valdora (5) takes the two north-west lakes and the land round them, the small lake, and the south-west lobe of
  Kervara with the Dovaran peninsula and its islands (blue loops).
- Kervara (6) is the red outline: its north (green, the mountains toward the Orthean range) and the mountain notch
  south-west of the great lake (small green cross) are given up; it gains the far shore of the great lake.
- The Dovaran Crown (7) gives up its mainland east of the peninsula (green cross); it keeps Dovehall's islands.
Only unclaimed land, Kervara and Dovaran pixels change (plus the old straight Valdora bar that poked east past the
new line); Madravella and the sea are never touched. An island split by a
stroke goes whole to the realm holding most of it. Then any unclaimed sliver between realms in the edit window (land a
CLOSE_R closing fills) goes to the nearest realm, so no thin gaps are left; the wide no-man's-lands stay.
G (border distance) is moved only where the edit moves it (w4_borders.apply_window).

    $BLENDER -b ~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend --python tools/kw_edits/w6_borders.py
    ... -- --dry-run          report only
    ... -- --dump <prefix>    also write <prefix>_before.npy / _after.npy (window ids, rows from the top)
Then rebake: $BLENDER -b .../KnownWorld.blend --python tools/bake_known_world.py
Re-runnable: the first run copies kingdoms_id.png to textures/pre_w6/ and every run starts from that copy.
"""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w4_borders as w4  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DRY = "--dry-run" in ARGS
DUMP = ARGS[ARGS.index("--dump") + 1] if "--dump" in ARGS else None
w4.DRY = DRY

BOUNDS = (-185.0, -62.0, 500.0, 295.0)      # known_world.json bounds_xy
UNIT_M, EXAG = 16093.44, 15.0
VIEW = dict(target=(172.5, 166.0, 0.0), yaw=-90.0, pitch=62.0, dist=100.0, fov=40.0, w=1170, h=876)
WIN = (380, 1000, 1500, 2000)              # id-map window (rows from the top y0, y1, columns x0, x1)
CLOSE_R = 3
VALDORA, KERVARA, DOVARAN = 5, 6, 7

# screen polygons (px, from the top-left of the 1170 x 876 view)
V_LAKES = [(195, 205), (200, 140), (230, 115), (300, 110), (380, 118), (420, 133), (470, 143), (500, 165), (505, 200),
           (490, 225), (470, 240), (437, 256), (412, 266), (395, 268), (330, 270), (260, 262), (215, 235)]
V_SMALL = [(330, 270), (395, 268), (412, 266), (412, 290), (412, 340), (395, 352), (360, 352), (335, 345), (300, 330),
           (300, 280)]
V_SOUTH = [(300, 352), (335, 345), (360, 352), (395, 352), (402, 372), (420, 395), (440, 430), (465, 452), (495, 460),
           (515, 488), (503, 520), (492, 550), (492, 582), (507, 615), (530, 640), (550, 680), (556, 730), (537, 780),
           (502, 815), (466, 846), (430, 864), (385, 852), (345, 808), (322, 750), (250, 720), (230, 560), (250, 450),
           (270, 380)]
K_NEW = [(412, 266), (437, 256), (470, 263), (520, 261), (560, 265), (590, 275), (620, 290), (645, 310), (665, 322),
         (700, 326), (760, 322), (785, 308), (805, 303), (822, 315), (830, 330), (818, 347), (800, 362), (795, 382),
         (805, 402), (800, 422), (790, 442), (800, 462), (820, 482), (832, 502), (822, 522), (792, 542), (772, 562),
         (762, 582), (700, 586), (650, 592), (610, 592), (580, 577), (560, 560), (535, 540), (503, 520), (515, 488),
         (495, 460), (465, 452), (440, 430), (420, 395), (402, 372), (412, 340), (412, 290)]
# Dovaran mainland east of the blue loop (green cross); reaches past the screen edge
D_EAST = [(492, 560), (1400, 540), (1400, 1500), (570, 1500), (560, 880), (556, 730), (550, 680), (530, 640),
          (507, 615), (492, 582)]


def log(*a):
    print("[W6]", *a, flush=True)


def camera():
    v = VIEW
    t = np.array(v["target"])
    y, p = math.radians(v["yaw"]), math.radians(v["pitch"])
    c = t + v["dist"] * np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    f = (c - t) / np.linalg.norm(c - t)
    r = np.cross([0.0, 0.0, 1.0], f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    fy = (v["h"] / 2) / math.tan(math.radians(v["fov"] / 2))
    return c, f, r, u, fy


def project(x, y, z):
    c, f, r, u, fy = camera()
    P = np.stack([x, y, z], -1) - c
    zc = -(P @ f)
    return VIEW["w"] / 2 + fy * (P @ r) / zc, VIEW["h"] / 2 - fy * (P @ u) / zc


def inside(sx, sy, poly):
    P = np.array(poly, float)
    out = np.zeros(sx.shape, bool)
    for i in range(len(P)):
        xa, ya = P[i]
        xb, yb = P[(i + 1) % len(P)]
        out ^= ((ya > sy) != (yb > sy)) & (sx < (xb - xa) * (sy - ya) / (yb - ya + 1e-12) + xa)
    return out


def components(mask):
    """8-connected components of mask: label array (0 = none) and count."""
    lab = np.zeros(mask.shape, np.int32)
    n = 0
    for y, x in zip(*np.nonzero(mask)):
        if lab[y, x]:
            continue
        n += 1
        stack = [(y, x)]
        lab[y, x] = n
        while stack:
            cy, cx = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n
                        stack.append((ny, nx))
    return lab, n


def relabel(old, land, metres):
    """New ids for the window (rows from the top)."""
    h, w = old.shape
    y0, x0 = WIN[0], WIN[2]
    rows, cols = np.mgrid[0:h, 0:w]
    x = BOUNDS[0] + (x0 + cols + 0.5) * 0.2
    y = BOUNDS[3] - (y0 + rows + 0.5) * 0.2
    sx, sy = project(x, y, np.maximum(metres, 0.0) / UNIT_M * EXAG)
    V = inside(sx, sy, V_LAKES) | inside(sx, sy, V_SMALL) | inside(sx, sy, V_SOUTH)
    K = inside(sx, sy, K_NEW) & ~V
    D = inside(sx, sy, D_EAST) & ~V & ~K
    free = ((old == 0) & land) | (old == KERVARA) | (old == DOVARAN)
    new = old.copy()
    new[(old == KERVARA) & ~V & ~K] = 0
    new[(old == DOVARAN) & D] = 0
    new[V & free] = VALDORA
    new[K & free] = KERVARA
    bar = K & (old == VALDORA) & ~V          # the old straight Valdora bar east of the new line follows the line
    new[bar] = KERVARA

    # islands cut by a stroke go whole to the realm holding most of them
    isl, n = components(land & np.isin(new, (VALDORA, DOVARAN)) & ~np.isin(old, (KERVARA,)))
    for i in range(1, n + 1):
        m = isl == i
        if m.sum() > 4000:          # the mainland, not an island
            continue
        ids, cnt = np.unique(new[m], return_counts=True)
        if len(ids) > 1:
            new[m] = ids[np.argmax(cnt)]
    return new


def close_slivers(rid, land):
    """Unclaimed land a CLOSE_R closing of the claimed area fills goes to the nearest realm (4-connected flood)."""
    claimed = rid > 0
    gap = land & ~claimed & w4.erode(w4.dilate(claimed, CLOSE_R), CLOSE_R)
    if not gap.any():
        return rid, 0
    return w4.flood(rid, gap, np.zeros_like(gap)), int(gap.sum())


def main():
    keep = os.path.join(bpy.path.abspath("//"), "textures", "pre_w6")
    img = bpy.data.images["T_Kingdoms"]
    px = w4.load_pristine(img, keep)                 # rows bottom-up
    H, W = px.shape[:2]
    rid = np.round(px[..., 0] * 255).astype(np.int32)
    G = np.round(px[..., 1] * 255).astype(np.int32)
    td = w4.img_px(bpy.data.images["T_TerrainData"])
    metres_all = td[..., 2] * 10000.0
    land_all = td[..., 2] > 0.0

    y0, y1, x0, x1 = WIN
    b0, b1 = H - y1, H - y0                         # the same window, bottom-up rows
    old = rid[b0:b1, x0:x1][::-1].copy()            # rows from the top
    land = land_all[b0:b1, x0:x1][::-1]
    new = relabel(old, land, metres_all[b0:b1, x0:x1][::-1])
    new, n = close_slivers(new, land)
    log(f"slivers closed: {n} px")
    for k in (VALDORA, KERVARA, DOVARAN, 0):
        a, b = int((old == k).sum()), int((new == k).sum())
        log(f"  {w4.NAMES.get(k, 'unclaimed'):14s} {a:6d} -> {b:6d} px ({b - a:+d})")
    if DUMP:
        np.save(DUMP + "_before.npy", old)
        np.save(DUMP + "_after.npy", new)
        log("dumped", DUMP)

    changed = int(w4.apply_window(rid, G, b0, b1, x0, x1, new[::-1]))
    log(f"G changed on {changed} px")
    if DRY:
        log("dry run: nothing saved")
        return
    px[..., 0] = rid / 255.0
    px[..., 1] = G / 255.0
    img.pixels.foreach_set(np.ascontiguousarray(px).ravel())
    img.update()
    img.save()
    log("saved", bpy.path.abspath(img.filepath))
    bpy.context.scene["kw_w6_borders"] = "applied (tools/kw_edits/w6_borders.py)"
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


if __name__ == "__main__":
    main()
