"""Reshape the southern Veryan foreland after W2-W4, then run bake_known_world.py.
Run with Blender -b KnownWorld.blend --python-exit-code 1 --python <this script>.
The baseline blend and terrain EXR are backed up alongside the source on the first run.
"""
import os
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils.kdtree import KDTree

sys.path.insert(0, os.path.dirname(__file__))
import w2_terrain as terrain

BOX = (82, 161, 155, 201)
step = terrain.smoothstep


def fault(x, y, trace, scarp, backslope, height):
    """Finite arcuate ridge with a steep south face, long dip slope and plunging ends."""
    along, crest = np.array(trace).T
    offset = y - np.interp(x, along, crest) - 0.34 * np.sin(x * 0.83)
    width = np.where(offset < 0, scarp, backslope)
    ends = step(along[0], along[0] + 4, x) * step(along[-1], along[-1] - 4, x)
    saddles = 0.60 + 0.40 * terrain.fbm(x, y, 57, 3, 0.32)
    return height * ends * saddles * np.exp(-(offset / width) ** 2)


def remodel(x, y, old, original):
    # Fade the widespread W2 uplift back to the pre-W2 surface in the foreland.
    basin = step(1, 0.74, np.hypot((x-110)/28, (y-179)/22))
    # Preserve the Veryan crest where it curves south into the northern edge of the basin.
    basin *= 1 - step(190, 198, y) * step(1300, 2700, original)
    broad = 100 + 65 * terrain.fbm(x, y, 27, 3, 0.09)
    plain = broad + 0.17 * (original - broad)
    relief = fault(x, y, [(83,193),(93,190),(102,191),(110,194),(121,193),(130,197)], 1.15, 3.0, 940)
    relief += fault(x, y, [(86,185),(94,186),(100,185),(108,187)], 0.85, 1.8, 490)
    for cx, cy, h in [(116.3,184.0,550), (126.4,176.0,690)]:
        relief += h * np.exp(-(((x-cx)/1.3)**2 + ((y-cy-0.35*(x-cx))/0.9)**2))
    change = basin * (plain - old) + relief
    # Imbricate ridges sweeping NE across Valdora's plains towards the eastern highlands.
    change += fault(x, y, [(125,170),(131,175),(137,181),(145,184),(153,188)], 1.4, 3.3, 1680)
    change += fault(x, y, [(133,177),(139,183),(147,188),(155,190),(160,193)], 1.1, 2.7, 1260)
    change += fault(x, y, [(122,163),(127,166),(132,171),(139,174)], 0.95, 2.2, 980)
    # Protect the Great Gate's high-resolution inset, smoothly around its footprint.
    gate = np.hypot(np.maximum.reduce([131.875-x, x-157.525, x*0]),
                    np.maximum.reduce([163.675-y, y-179.725, y*0]))
    edge = np.minimum.reduce([x-BOX[0], BOX[1]-x, y-BOX[2], BOX[3]-y])
    return change * step(0, 2, gate) * step(0, 2, edge) * step(5, 75, old)


def corridor_weight(x, y, names):
    points = terrain.mesh_points(names, BOX, 0.10)
    tree = KDTree(len(points))
    for i, (px, py) in enumerate(points):
        tree.insert((px, py, 0), i)
    tree.balance()
    distance = np.array([tree.find((px, py, 0))[2] for px, py in zip(x.flat, y.flat)]).reshape(x.shape)
    weight = step(0.20, 1.25, distance)
    for ob in bpy.data.objects:
        if ob.name.startswith("CITY_"):
            weight *= step(0.6, 2, np.hypot(x-ob.location.x, y-ob.location.y))
    return weight


def main():
    blend = Path(bpy.data.filepath)
    backup = blend.with_suffix(".pre_s12.bak.blend")
    if not backup.exists():
        shutil.copy2(blend, backup)
    textures = blend.parent / "textures"
    image = bpy.data.images["T_TerrainData"]
    data = terrain.load_pristine(image, textures / "pre_s12")
    if not (textures / "pre_w2" / Path(image.filepath).name).is_file():
        raise RuntimeError("Missing pre-W2 terrain baseline")
    original = terrain.load_pristine(image, textures / "pre_w2")
    grid = terrain.Grid(*image.size)
    r0, r1, c0, c1 = grid.window(BOX)
    rows, cols = np.mgrid[r0:r1, c0:c1]
    x, y = grid.to_world(cols, rows)
    region = np.s_[r0:r1, c0:c1]
    old = data[region][..., 2] * 10000
    change = remodel(x, y, old, original[region][..., 2]*10000)
    lakes = [o.name for o in bpy.data.objects if o.name.startswith("LAKE")]
    rivers = [o.name for o in bpy.data.objects if o.name.startswith("RIVER")]
    # Lower riverbeds with the surrounding basin. Only uplift needs to fade out
    # at rivers, otherwise an old river elevation stands proud of the new plain.
    dz = np.where(change > 0, change * corridor_weight(x, y, rivers), change)
    dz *= corridor_weight(x, y, lakes)
    for name, cx, cy in [('Astera',103,184), ('Madravella',122,180), ('Valdora uplands',141,184)]:
        area = np.hypot(x-cx, y-cy) < 6
        print(name, '90th percentile elevation (m)', np.percentile(old[area],90), np.percentile((old+dz)[area],90))
    delta = dz / 10000
    data[region][..., 2] += delta
    data[region][..., 0] += terrain.GRAD_K * np.gradient(delta, axis=1)
    data[region][..., 1] += terrain.GRAD_K * np.gradient(delta, axis=0)

    def mesh_delta(wx, wy):
        col, row = grid.to_pix(wx, wy)
        return terrain.bilinear(dz, col-c0, row-r0) / terrain.UNIT_M

    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.name.startswith(("TERRAIN_", "TLOD", "RIVER", "LAKE", "DECOR_", "TREES_Canvas")):
            terrain.shift_mesh(ob, mesh_delta, [BOX], "s12_z0")
    image.pixels.foreach_set(np.ascontiguousarray(data).ravel())
    image.update()
    image.save()
    bpy.ops.wm.save_mainfile()


if __name__ == "__main__":
    main()
