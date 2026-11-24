"""Tile PNGs into one sheet (runs in Blender for image IO): $BLENDER -b --python tools/debug/contact_sheet.py -- out.png cols w a.png b.png ..."""
import sys, bpy, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
out, cols, W = a[0], int(a[1]), int(a[2])
tiles = []
for p in a[3:]:
    im = bpy.data.images.load(p)
    w, h = im.size
    px = np.array(im.pixels[:], np.float32).reshape(h, w, 4)
    step = max(1, w // W)
    tiles.append(px[::step, ::step][:, :W])
th = max(t.shape[0] for t in tiles)
rows = (len(tiles) + cols - 1) // cols
sheet = np.ones((rows * th, cols * W, 4), np.float32)
for i, t in enumerate(tiles):
    r, c = divmod(i, cols)
    r = rows - 1 - r
    sheet[r * th:r * th + t.shape[0], c * W:c * W + t.shape[1]] = t
im = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0], alpha=True)
im.pixels.foreach_set(sheet.ravel())
im.filepath_raw = out; im.file_format = 'PNG'; im.save()
print("[Sheet]", out)
