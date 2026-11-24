"""W4: Salmara-Calderra shared border along the Border river (docs/world_map/PLAN.md, card W4).

Where the borders come from: T_Kingdoms (textures/kingdoms_id.png, 3425 x 1785, Non-Color). R = realm id x 1/255
(0 = unclaimed; 1 Calderra, 2 Astera, 3 Salmara, ...), G = distance to the nearest border, x16 per pixel, capped at
255 (M_Terrain's S4_* nodes use it for the border line and the tinted band), B = 0. The provisional geojson it was
rasterised from isn't in the repo or FOMSMap, so the texture is the source. The painted political overlay
(FOMSMap/political-overlay) already builds regions from shared border lines and has no gap.

The gap: the Border river valley (RIVER_river_border, "Border river", with tributaries W1, W2 and an upland lake
outlet) was left unclaimed: a 10-20 px strip from the coast up to the Veryan foothills, with branches up the
tributaries into Salmara. Fix: every unclaimed land pixel in that strip goes to the nearest realm reached without
crossing the river (a flood from both banks with the rasterised river as a wall), then the river pixels themselves
go to the nearer bank. So Salmara owns the west bank, Calderra (and Astera at the north end) the east bank, and
the border line runs down the river. G is updated only where the change moves it (old G plus the change in the
distance), so the rest of the map keeps its original values.

    $BLENDER -b ~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend --python tools/kw_edits/w4_borders.py
    ... -- --dry-run     report only, save nothing
    ... -- --preview out.png   before | after picture round the river
    ... -- --report      also list every other realm pair with an unclaimed strip between them (slow)

Re-runnable: the first run copies kingdoms_id.png to textures/pre_w4/ and every run starts from that copy.
"""
import os
import shutil
import sys

import bpy
import numpy as np

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DRY = "--dry-run" in ARGS
REPORT = "--report" in ARGS
RIVER = "RIVER_river_border"
CLOSE_R = 20          # px: unclaimed land that closing realms with this disk would fill is "between" realms
MARGIN = 60           # px round the river's box that the edit may touch
SUPER = 4             # river rasterisation subsamples per pixel side
NAMES = {1: "Calderra", 2: "Astera", 3: "Salmara", 4: "Madravella", 5: "Valdora", 6: "Kervara", 7: "Dovaran Crown",
         8: "Hamen", 9: "Coastal Sultanate", 10: "High Dunes", 11: "Oasis League", 12: "Southern Salt Sultanate",
         13: "Eastern Marches", 14: "Varduun", 15: "Karn Ashur"}


def log(*a):
    print("[W4]", *a, flush=True)


def img_px(img):
    w, h = img.size
    a = np.empty(w * h * img.channels, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, img.channels)       # row 0 = bottom (y min)


def load_pristine(img, folder):
    src = bpy.path.abspath(img.filepath)
    keep = os.path.join(folder, os.path.basename(src))
    if not os.path.exists(keep):
        if DRY:
            return img_px(img).copy()
        os.makedirs(folder, exist_ok=True)
        shutil.copy2(src, keep)
        log("kept original", keep)
    tmp = bpy.data.images.load(keep, check_existing=False)
    tmp.colorspace_settings.name = "Non-Color"
    a = img_px(tmp).copy()
    bpy.data.images.remove(tmp)
    return a


def shift(a, dy, dx, fill):
    """out[r, c] = a[r - dy, c - dx] (fill outside)."""
    out = np.full_like(a, fill)
    h, w = a.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


def disk(r):
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dy * dy + dx * dx <= r * r]


def dilate(m, r):
    out = m.copy()
    for dy, dx in disk(r):
        out |= shift(m, dy, dx, False)
    return out


def erode(m, r):
    out = m.copy()
    for dy, dx in disk(r):
        out &= shift(m, dy, dx, True)
    return out


def border_dist16(rid):
    """min(255, 16 x distance to the nearest pixel of another id), brute force up to 16 px."""
    best = np.full(rid.shape, 17.0 ** 2)
    for dy in range(-16, 17):
        for dx in range(-16, 17):
            d2 = dy * dy + dx * dx
            if d2 == 0 or d2 > 16 * 16:
                continue
            other = shift(rid, dy, dx, -1)
            diff = (other != rid) & (other >= 0)
            best = np.where(diff & (d2 < best), d2, best)
    return np.minimum(255.0, np.floor(16.0 * np.sqrt(best) + 0.5))


def raster_mesh(ob, W, H, loc, sc, x0, y0, w, h):
    """Mask (h, w) of window pixels any of whose SUPER^2 subsamples fall inside one of the mesh's faces."""
    M = ob.matrix_world
    v = np.array([(M @ x.co)[:2] for x in ob.data.vertices])
    px = (v[:, 0] * sc[0] + loc[0]) * W - x0          # column, window space
    py = (v[:, 1] * sc[1] + loc[1]) * H - y0          # row from the bottom, window space
    mask = np.zeros((h, w), bool)
    off = (np.arange(SUPER) + 0.5) / SUPER
    for poly in ob.data.polygons:
        P = np.stack([px[list(poly.vertices)], py[list(poly.vertices)]], 1)
        c0, c1 = int(np.floor(P[:, 0].min())), int(np.ceil(P[:, 0].max()))
        r0, r1 = int(np.floor(P[:, 1].min())), int(np.ceil(P[:, 1].max()))
        c0, r0 = max(c0, 0), max(r0, 0)
        c1, r1 = min(c1, w), min(r1, h)
        if c1 <= c0 or r1 <= r0:
            continue
        rr, cc = np.mgrid[r0:r1, c0:c1]
        sy = (rr[..., None, None] + off[:, None]).astype(float)
        sx = (cc[..., None, None] + off[None, :]).astype(float)
        sy, sx = np.broadcast_arrays(sy, sx)
        inside = np.zeros(sx.shape, bool)
        n = len(P)
        for i in range(n):
            xa, ya = P[i]
            xb, yb = P[(i + 1) % n]
            cross = ((ya > sy) != (yb > sy)) & (sx < (xb - xa) * (sy - ya) / (yb - ya + 1e-12) + xa)
            inside ^= cross
        mask[r0:r1, c0:c1] |= inside.any(axis=(2, 3))
    return mask


def flood(lab, target, wall):
    """Grow realm ids (lab > 0) into target pixels, 4-connected, never through wall. Returns the new labels."""
    lab = lab.copy()
    todo = target & ~wall & (lab == 0)
    for _ in range(10000):
        if not todo.any():
            break
        grew = False
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = shift(lab, dy, dx, 0)
            take = todo & (nb > 0)
            if take.any():
                lab[take] = nb[take]
                todo &= ~take
                grew = True
        if not grew:
            break
    return lab


def internal_gaps(rid, land):
    """Unclaimed land that closing the claimed area with a CLOSE_R disk fills: strips between realms."""
    claimed = rid > 0
    closed = erode(dilate(claimed, CLOSE_R), CLOSE_R)
    return land & ~claimed & closed


def report_pairs(rid, land):
    """Each realm pair with unclaimed strips between them (whole map; slow brute-force morphology)."""
    gaps = internal_gaps(rid, land)
    # label 8-connected components with a simple flood
    seen = np.zeros(gaps.shape, bool)
    rows = []
    ys, xs = np.nonzero(gaps)
    for y, x in zip(ys, xs):
        if seen[y, x]:
            continue
        stack = [(y, x)]
        seen[y, x] = True
        comp = []
        while stack:
            cy, cx = stack.pop()
            comp.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < gaps.shape[0] and 0 <= nx < gaps.shape[1] and gaps[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(comp) < 50:
            continue
        cy, cx = np.array(comp).T
        nb = set()
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                yy = np.clip(cy + dy, 0, rid.shape[0] - 1)
                xx = np.clip(cx + dx, 0, rid.shape[1] - 1)
                nb.update(int(k) for k in np.unique(rid[yy, xx]) if k > 0)
        if len(nb) >= 2:
            rows.append((len(comp), sorted(NAMES.get(k, str(k)) for k in nb), int(cx.min()), int(cx.max()),
                         int(rid.shape[0] - 1 - cy.max()), int(rid.shape[0] - 1 - cy.min())))
    for n, nb, a, b, c, d in sorted(rows, reverse=True):
        log(f"  gap {n:5d} px between {' / '.join(nb)}  (px x {a}-{b}, y {c}-{d} from the top)")
    return rows


def save_preview(path, before, after, river, land):
    """Before | after realm ids round the river (debug), 3x."""
    pal = np.array([[.8, .8, .8], [.86, .59, .24], [.67, .47, .7], [.51, .63, .35]] + [[.5, .5, .5]] * 12)
    tiles = []
    for ids in (before, after):
        t = pal[np.clip(ids, 0, 15)]
        t[~land] = [.12, .2, .35]
        t[land & (ids == 0)] = [.95, .95, .9]
        t[river] = t[river] * 0.4 + np.array([0, 0, .6])
        tiles.append(t)
    a = np.concatenate([tiles[0], np.ones((tiles[0].shape[0], 4, 3)), tiles[1]], 1).repeat(3, 0).repeat(3, 1)
    h, w = a.shape[:2]
    im = bpy.data.images.new("w4_preview", w, h, alpha=True)
    im.pixels.foreach_set(np.concatenate([a, np.ones((h, w, 1))], 2).astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    log("preview", path)


def main():
    keep = os.path.join(bpy.path.abspath("//"), "textures", "pre_w4")
    img = bpy.data.images["T_Kingdoms"]
    px = load_pristine(img, keep)
    H, W = px.shape[:2]
    rid = np.round(px[..., 0] * 255).astype(np.int32)
    G = np.round(px[..., 1] * 255).astype(np.int32)
    td = img_px(bpy.data.images["T_TerrainData"])
    if td.shape[:2] != (H, W):
        raise SystemExit(f"T_TerrainData {td.shape[:2]} != T_Kingdoms {(H, W)}")
    land = td[..., 2] > 0.0
    wuv = bpy.data.materials["M_Terrain_Fast"].node_tree.nodes["WorldUV"]
    loc = list(wuv.inputs["Location"].default_value)
    sc = list(wuv.inputs["Scale"].default_value)

    # window round the river
    ob = bpy.data.objects[RIVER]
    v = np.array([(ob.matrix_world @ x.co)[:2] for x in ob.data.vertices])
    cx = (v[:, 0] * sc[0] + loc[0]) * W
    cy = (v[:, 1] * sc[1] + loc[1]) * H
    x0, x1 = max(int(cx.min()) - MARGIN, 0), min(int(cx.max()) + MARGIN, W)
    y0, y1 = max(int(cy.min()) - MARGIN, 0), min(int(cy.max()) + MARGIN, H)
    win = (slice(y0, y1), slice(x0, x1))
    r, ld = rid[win], land[win]
    river = raster_mesh(ob, W, H, loc, sc, x0, y0, x1 - x0, y1 - y0)
    log(f"window x {x0}-{x1}, y {y0}-{y1} (bottom-up); river {river.sum()} px")

    # the strip: unclaimed land between realms, in the components the river runs through
    gaps = internal_gaps(r, ld)
    strip = np.zeros_like(gaps)
    seed = gaps & dilate(river, 2)
    strip |= seed
    for _ in range(4000):
        grown = strip | (gaps & (shift(strip, 1, 0, False) | shift(strip, -1, 0, False)
                                 | shift(strip, 0, 1, False) | shift(strip, 0, -1, False)))
        if (grown == strip).all():
            break
        strip = grown
    nb_before = {int(k) for k in np.unique(r[dilate(strip, 2)]) if k > 0}
    log(f"strip {strip.sum()} px, bordering {[NAMES[k] for k in sorted(nb_before)]}")

    # banks first (the river is a wall), then the river itself from the nearer bank
    lab = flood(r, strip, river)
    lab = flood(lab, strip, np.zeros_like(river))
    left = strip & (lab == 0)
    if left.any():
        log(f"WARNING {left.sum()} strip px not reached")
    for k in sorted(nb_before):
        n = int((strip & (lab == k)).sum())
        if n:
            log(f"  {NAMES[k]} +{n} px")

    # G: keep the original values, plus the change in the distance the edit causes
    pad = 17
    wy0, wy1, wx0, wx1 = max(y0 - pad, 0), min(y1 + pad, H), max(x0 - pad, 0), min(x1 + pad, W)
    big_old = rid[wy0:wy1, wx0:wx1].copy()
    big_new = big_old.copy()
    big_new[y0 - wy0:y1 - wy0, x0 - wx0:x1 - wx0] = lab
    d_old = border_dist16(big_old)           # sea is id 0 too, so the coast counts as a border (as in the original)
    d_new = border_dist16(big_new)
    g = G[wy0:wy1, wx0:wx1].astype(float)
    changed = big_old != big_new
    g_new = np.where(changed, d_new, np.clip(g + (d_new - d_old), 0, 255))
    log(f"G changed on {(np.round(g_new) != g).sum()} px")

    rid_new = rid.copy()
    rid_new[win] = lab
    G_new = G.copy()
    G_new[wy0:wy1, wx0:wx1] = np.round(g_new).astype(np.int32)

    # Salmara and Calderra must now touch along the river with nothing unclaimed between them
    r2 = rid_new[win]
    touch = ((r2 == 3) & (shift(r2, 0, 1, 0) == 1)) | ((r2 == 1) & (shift(r2, 0, 1, 0) == 3))
    log(f"Salmara|Calderra contact px (horizontal) {int(touch.sum())}, before "
        f"{int((((r == 3) & (shift(r, 0, 1, 0) == 1)) | ((r == 1) & (shift(r, 0, 1, 0) == 3))).sum())}")
    log(f"unclaimed strip px left: {int((internal_gaps(r2, ld) & dilate(river, 2)).sum())}")

    if REPORT:
        log("other realm pairs with an unclaimed strip between them (after W4):")
        report_pairs(rid_new, land)

    if "--preview" in ARGS:
        save_preview(ARGS[ARGS.index("--preview") + 1], r, lab, river, ld)
    if DRY:
        log("dry run: nothing saved")
        return
    px[..., 0] = rid_new / 255.0
    px[..., 1] = G_new / 255.0
    img.pixels.foreach_set(np.ascontiguousarray(px).ravel())
    img.update()
    img.save()
    log("saved", bpy.path.abspath(img.filepath))
    bpy.context.scene["kw_w4_borders"] = "applied (tools/kw_edits/w4_borders.py)"
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
