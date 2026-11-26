"""Debug: build a city (no save) and draw its anchors over the walk grid -> PNG. Usage:
   $BLENDER -b --factory-startup --python tools/debug/anchor_map.py -- <city_id> <out.png>"""
import sys, os, json, math
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "generator"))
import bpy, fantasy_capital as m, anchors
argv = sys.argv[sys.argv.index('--') + 1:]
cid, out = argv[0], argv[1]
cfg = json.load(open(os.path.join(ROOT, "generator", "cities", cid + ".json")))
if hasattr(m, "apply_config"): m.apply_config(cfg)
m.build_all()
rep = {}
man, G, graph = anchors.build_manifest(m, cfg, rep)
S = 1400
img = np.zeros((S, S, 3), np.float32)
T = m.ANCHORS['_T']
xs = np.linspace(-50, 50, S)
X, Y = np.meshgrid(xs, xs)
land = T.m(T.sd, X, Y) > 0
img[..., 0] = np.where(land, 0.35, 0.08); img[..., 1] = np.where(land, 0.33, 0.15); img[..., 2] = np.where(land, 0.28, 0.3)
blk = ~G.free(X, Y)
img[blk & land] = (0.6, 0.55, 0.5)
def px(x, y): return int((x + 50) / 100 * (S - 1)), int((y + 50) / 100 * (S - 1))
def dot(x, y, c, r=1):
    i, j = px(x, y)
    img[max(0, j - r):j + r + 1, max(0, i - r):i + r + 1] = c
def line(a, b, c, r=0):
    n = int(max(2, math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
    for t in np.linspace(0, 1, n): dot(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, c, r)
N = graph['nodes']
for a, b, w in graph['edges']: line(N[a], N[b], (0.9, 0.15, 0.1))
for z in man['spawn_zones']:
    for p in z['points']: dot(p[0], p[1], (0.2, 0.5, 1.0), 1)
for ln in man['ship_lanes']:
    P = ln['points'] + (ln['points'][:1] if ln['loop'] else [])
    for a, b in zip(P[:-1], P[1:]): line(a, b, (0.0, 1.0, 1.0), 1)
for s in m.ANCHORS.get('_ships', []): dot(s[2], s[3], (1, 1, 1), 3)
for rid, P in man['routes'].items():
    for a, b in zip(P[:-1], P[1:]): line(a, b, (1.0, 0.9, 0.1), 1)
for v in man['venues']:
    for t in v['seat_tiers']:
        for p in t['ring'][::3]: dot(p[0], p[1], (0.7, 0.2, 0.9), 0)
    for p in v.get('entrances', []): dot(p[0], p[1], (0.1, 1, 0.2), 3)
    if 'track_centerline' in v:
        P = v['track_centerline']
        for a, b in zip(P, P[1:] + P[:1]): line(a, b, (1, 0.5, 0), 0)
for l in man['night_lights']:
    if l['kind'] != 'window': dot(l['pos'][0], l['pos'][1], (1, 1, 0.6), 1)
# lane clearances
for ln in cfg['ship_lanes']:
    P = m.resample(ln['points'], 0.5)
    worst = min(((math.hypot(px_ - s[2], py_ - s[3]), s[0], round(px_, 1), round(py_, 1)) for px_, py_ in P for s in m.ANCHORS['_ships']))
    print("[Dbg] lane", ln['id'], "closest", worst)
for rid, pts in []:
    P = m.resample(pts, 0.4)
    bad = P[~G.free(P[:, 0], P[:, 1])]
    print("[Dbg] route", rid, "blocked at", np.round(bad, 1).tolist())
im = bpy.data.images.new("dbg", S, S, alpha=False)
rgba = np.ones((S, S, 4), np.float32); rgba[..., :3] = img
im.pixels.foreach_set(rgba.ravel())
im.filepath_raw = out; im.file_format = 'PNG'; im.save()
print("[Dbg] wrote", out)
