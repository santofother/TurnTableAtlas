"""W3: sea colour round the Dovaran Crown (docs/world_map/PLAN.md, card W3).

The dark sea rectangle west of Dovehall is the HERO_Dovehall patch's footprint. Inside each hero box M_Water takes
the sea-floor elevation from the hero height texture (S11H_Tex*, R = metres) instead of T_TerrainData, and the
hero textures' sea pixels are ~10x deeper than the base terrain (e.g. -10,400 m against -950 m). The water colour is
a ramp on log depth (and the turquoise shallows need < 160 m), so the box read as a dark, halo-less patch.

Fix at the source: every sea pixel (R < 0) of each hero texture gets the base terrain's elevation at that point
(T_TerrainData B x 10000, bilinear), kept at least SHORE_M below the surface so the hero's own finer coastline stays
water. Land pixels are untouched. The water shader then sees the same depth gradient inside and outside the box.

    $BLENDER -b ~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend --python tools/kw_edits/w3_sea.py
    ... -- --dry-run     report only, save nothing

Re-runnable: the first run copies each edited texture to textures/pre_w3/ and every run starts from that copy.
Run it after tools/kw_edits/w2_terrain.py if W2 is ever re-run (W2 rewrites hero_Dovehall_z.exr from pre_w2).
"""
import os
import shutil
import sys

import bpy
import numpy as np

DRY = "--dry-run" in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
SHORE_M = 8.0          # minimum depth for a hero sea pixel (the hero coast is finer than the base terrain's)
# M_Water's per-hero nodes: S11H_U0i / S11H_U i (x0, sx), S11H_V0i / S11H_V i (y0, sy), S11H_Tex i
HEROES = (0, 1)


def log(*a):
    print("[W3]", *a, flush=True)


def img_px(img):
    w, h = img.size
    a = np.empty(w * h * img.channels, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, img.channels)       # row 0 = bottom (y min)


def load_pristine(img, folder):
    """Pixels of the image as it was before W3 (copied to textures/pre_w3 on the first run)."""
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


def bilinear(grid, gx, gy):
    h, w = grid.shape
    gx = np.clip(gx, 0, w - 1.001)
    gy = np.clip(gy, 0, h - 1.001)
    x0 = np.floor(gx).astype(int)
    y0 = np.floor(gy).astype(int)
    fx = gx - x0
    fy = gy - y0
    return (grid[y0, x0] * (1 - fx) * (1 - fy) + grid[y0, x0 + 1] * fx * (1 - fy)
            + grid[y0 + 1, x0] * (1 - fx) * fy + grid[y0 + 1, x0 + 1] * fx * fy)


def main():
    keep = os.path.join(bpy.path.abspath("//"), "textures", "pre_w3")
    nodes = bpy.data.materials["M_Water"].node_tree.nodes
    wuv = nodes["WorldUV"]
    loc = list(wuv.inputs["Location"].default_value)
    sc = list(wuv.inputs["Scale"].default_value)
    td = img_px(bpy.data.images["T_TerrainData"])
    TH, TW = td.shape[:2]
    base = td[..., 2] * 10000.0

    edited = []
    for i in HEROES:
        x0 = nodes[f"S11H_U0{i}"].inputs[1].default_value
        sx = nodes[f"S11H_U{i}"].inputs[1].default_value
        y0 = nodes[f"S11H_V0{i}"].inputs[1].default_value
        sy = nodes[f"S11H_V{i}"].inputs[1].default_value
        img = nodes[f"S11H_Tex{i}"].image
        px = load_pristine(img, keep)
        h, w = px.shape[:2]
        rr, cc = np.mgrid[0:h, 0:w].astype(np.float64)
        x = x0 + (cc + 0.5) / w * sx
        y = y0 + (rr + 0.5) / h * sy
        b = bilinear(base, (x * sc[0] + loc[0]) * TW - 0.5, (y * sc[1] + loc[1]) * TH - 0.5)
        r = px[..., 0]
        sea = r < 0.0
        new = np.where(sea, np.minimum(b, -SHORE_M), r)
        if sea.any():
            log(f"{img.name}: {sea.sum()} sea px of {sea.size}; depth median {np.median(-r[sea]):.0f} m -> "
                f"{np.median(-new[sea]):.0f} m (base {np.median(-b[sea]):.0f} m), "
                f"max {(-r[sea]).max():.0f} -> {(-new[sea]).max():.0f} m")
        else:
            log(f"{img.name}: no sea pixels")
            continue
        px[..., 0] = new.astype(np.float32)
        edited.append((img, px))

    if DRY:
        log("dry run: nothing saved")
        return
    for img, px in edited:
        img.pixels.foreach_set(np.ascontiguousarray(px).ravel())
        img.update()
        img.save()
        log("saved", bpy.path.abspath(img.filepath))
    bpy.context.scene["kw_w3_sea"] = "applied (tools/kw_edits/w3_sea.py)"
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
