"""Anchors: turn what the generator recorded while building into
  1. the hidden `Anchors` and `Proxies` collections in the .blend (curves, point meshes, empties, low-poly proxies)
  2. the city manifest dict written to cities/<id>/city.json (schema: docs/city_schema.md)

Runs inside Blender after fantasy_capital.build_all(). `m` is the loaded generator module, `cfg` the city config.
Everything is in the generator frame: metres, +X east, +Y north, +Z up.
"""
import math
from collections import deque

import bpy
import numpy as np

import sunarc

SCHEMA_VERSION = 1
WALK_RES = 0.1          # walkability grid (m)
TALL = 0.4              # geometry higher than this above the ground blocks walking; lower tops are walkable floors


# =============================================================================
# Small helpers
# =============================================================================
def r3(p, nd=3):
    return [round(float(c), nd) for c in p]


def poly_area(P):
    P = np.asarray(P, float)
    return 0.5 * abs(np.dot(P[:, 0], np.roll(P[:, 1], 1)) - np.dot(P[:, 1], np.roll(P[:, 0], 1)))


class Grid:
    """Walk grid over the model: blocked cells + the height of walkable floors (pavements, plinths, ribbons)."""

    def __init__(self, half, res=WALK_RES):
        self.half, self.res = half, res
        self.n = int(round(2 * half / res)) + 1
        self.blocked = np.zeros((self.n, self.n), bool)
        self.floor = np.full((self.n, self.n), -99.0, np.float32)

    def ij(self, x, y):
        return (np.round((np.asarray(x) + self.half) / self.res).astype(int),
                np.round((np.asarray(y) + self.half) / self.res).astype(int))

    def window(self, xmin, xmax, ymin, ymax):
        i0, j0 = self.ij(xmin, ymin)
        i1, j1 = self.ij(xmax, ymax)
        i0, j0 = max(int(i0), 0), max(int(j0), 0)
        i1, j1 = min(int(i1) + 1, self.n), min(int(j1) + 1, self.n)
        if i0 >= i1 or j0 >= j1:
            return None
        xs = -self.half + np.arange(i0, i1) * self.res
        ys = -self.half + np.arange(j0, j1) * self.res
        X, Y = np.meshgrid(xs, ys)
        return (slice(j0, j1), slice(i0, i1)), X, Y

    def free(self, x, y):
        i, j = self.ij(x, y)
        ok = (i >= 0) & (j >= 0) & (i < self.n) & (j < self.n)
        out = np.zeros(np.shape(i), bool)
        out[ok] = ~self.blocked[j[ok], i[ok]]
        return out

    def floor_at(self, x, y):
        i, j = self.ij(x, y)
        i = np.clip(i, 0, self.n - 1)
        j = np.clip(j, 0, self.n - 1)
        return self.floor[j, i]


def raster_poly(G, pts, blocked=None, floor_z=None, grow=0.0):
    P = np.asarray(pts, float)
    w = G.window(P[:, 0].min() - grow, P[:, 0].max() + grow, P[:, 1].min() - grow, P[:, 1].max() + grow)
    if w is None:
        return
    sl, X, Y = w
    if len(P) == 4 and grow > 0:                                    # grow a rectangle about its centre
        c = P.mean(axis=0)
        P = c + (P - c) * (1.0 + grow / max(1e-6, np.linalg.norm(P[0] - c)))
    inside = _pip(X, Y, P)
    if blocked is not None:
        G.blocked[sl] |= inside
    if floor_z is not None:
        G.floor[sl] = np.where(inside, np.maximum(G.floor[sl], floor_z), G.floor[sl])


def _pip(X, Y, P):
    inside = np.zeros(X.shape, bool)
    x0, y0 = P[-1]
    for x1, y1 in P:
        cond = (y1 > Y) != (y0 > Y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xint = (x0 - x1) * (Y - y1) / (y0 - y1) + x1
        inside ^= cond & (X < xint)
        x0, y0 = x1, y1
    return inside


def mesh_world_polys(ob):
    """(polys as list of Nx3 arrays, normals Nx3) in world space; objects built by the generator have identity
    transforms, but ships etc. may not, so apply matrix_world."""
    me = ob.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    co = co @ M[:3, :3].T + M[:3, 3]
    nl = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get('normal', nl)
    nl = nl.reshape(-1, 3) @ M[:3, :3].T
    starts = np.empty(len(me.polygons), np.int32)
    tot = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('loop_start', starts)
    me.polygons.foreach_get('loop_total', tot)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    return co, lv, starts, tot, nl


# =============================================================================
# Walkability
# =============================================================================
def build_walk_grid(m, T, root, cfg):
    G = Grid(m.HALF)
    X, Y = np.meshgrid(np.linspace(-m.HALF, m.HALF, G.n), np.linspace(-m.HALF, m.HALF, G.n))
    G.floor[:] = T.h(X, Y).astype(np.float32)
    sd = T.m(T.sd, X, Y)
    G.blocked |= sd < 0.25                                           # sea / quay edge
    G.blocked |= ~m.points_in_poly(X, Y, m.WALL_PATH)                # countryside: only roads (added as 'always')
    for (cx, cy, w, d, ang, zg, zt, fl) in m.ANCHORS.get('_houses', []):
        raster_poly(G, m.rect_pts(cx, cy, w + 0.04, d + 0.04, ang), blocked=True)
    # landmark / wall / harbour geometry: tall upward faces block, low ones become walkable floor
    skip = ("CAP_Terrain", "CAP_Sea", "CAP_Base", "CAP_LighthouseFlames", "CAP_LM_Hippodrome_Chariots")
    for ob in root.all_objects:
        if ob.type != 'MESH' or ob.name.startswith(skip) or ob.name.startswith(("CAP_Houses", "CAP_Ship", "CAP_Steam",
                                                                                 "CAP_Countryside_Trees", "CAP_CityTrees")):
            continue
        co, lv, starts, tot, nl = mesh_world_polys(ob)
        for k in np.nonzero(nl[:, 2] > 0.5)[0]:
            pts = co[lv[starts[k]:starts[k] + tot[k]]]
            if poly_area(pts[:, :2]) < 0.0004:
                continue
            c = pts.mean(axis=0)
            g = float(T.h(c[0], c[1]))
            if c[2] > g + TALL:
                raster_poly(G, pts[:, :2], blocked=True)
            elif c[2] > g - 0.05:
                raster_poly(G, pts[:, :2], floor_z=float(c[2]))
    for pt in cfg.get('portals', []):                                # arches people walk through (solid in the mesh)
        w = G.window(pt['center'][0] - pt['size'][0], pt['center'][0] + pt['size'][0],
                     pt['center'][1] - pt['size'][1], pt['center'][1] + pt['size'][1])
        if w is not None:
            sl, PX, PY = w
            c, s_ = math.cos(math.radians(pt.get('angle', 0))), math.sin(math.radians(pt.get('angle', 0)))
            lx = (PX - pt['center'][0]) * c + (PY - pt['center'][1]) * s_
            ly = -(PX - pt['center'][0]) * s_ + (PY - pt['center'][1]) * c
            G.blocked[sl] &= ~((np.abs(lx) <= pt['size'][0] / 2) & (np.abs(ly) <= pt['size'][1] / 2))
    return G


# =============================================================================
# Street graph
# =============================================================================
class Graph:
    def __init__(self, G, m, snap=0.3):
        self.G, self.m, self.snap = G, m, snap
        self.nodes, self.chain, self.width = [], [], []
        self.edges = {}
        self.hash = {}

    def _cell(self, x, y):
        return (int(math.floor(x / 0.5)), int(math.floor(y / 0.5)))

    def node(self, x, y, chain, width):
        cx, cy = self._cell(x, y)
        best, bd = None, self.snap
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in self.hash.get((cx + dx, cy + dy), ()):
                    d = math.hypot(self.nodes[i][0] - x, self.nodes[i][1] - y)
                    if d < bd:
                        best, bd = i, d
        if best is not None:
            return best
        self.nodes.append((x, y))
        self.chain.append(chain)
        self.width.append(width)
        self.hash.setdefault((cx, cy), []).append(len(self.nodes) - 1)
        return len(self.nodes) - 1

    def seg_free(self, a, b, always=False):
        if always:
            return True
        t = np.linspace(0.0, 1.0, max(3, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.12) + 1))
        return bool(self.G.free(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t).all())

    def add_edge(self, i, j, w):
        if i != j:
            self.edges[(min(i, j), max(i, j))] = w

    def polyline(self, pts, step, width, chain, always=False, closed=False):
        P = np.asarray(pts, float)
        if closed:
            P = np.vstack([P, P[:1]])
        Q = self.m.resample(P, step)
        prev = None
        for q in Q:
            ok = always or bool(self.G.free(np.array([q[0]]), np.array([q[1]]))[0])
            if not ok:
                prev = None
                continue
            i = self.node(float(q[0]), float(q[1]), chain, width)
            if prev is not None and self.seg_free(self.nodes[prev], self.nodes[i], always):
                self.add_edge(prev, i, width)
            prev = i

    def cross_link(self, radius=0.8, per_node=3):
        for i, (x, y) in enumerate(self.nodes):
            cx, cy = self._cell(x, y)
            cand = []
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    for j in self.hash.get((cx + dx, cy + dy), ()):
                        if j > i and self.chain[j] != self.chain[i]:
                            d = math.hypot(self.nodes[j][0] - x, self.nodes[j][1] - y)
                            if d < radius:
                                cand.append((d, j))
            for d, j in sorted(cand)[:per_node]:
                if (i, j) not in self.edges and self.seg_free(self.nodes[i], self.nodes[j]):
                    self.add_edge(i, j, min(self.width[i], self.width[j]))

    def largest_component(self):
        adj = [[] for _ in self.nodes]
        for (a, b) in self.edges:
            adj[a].append(b)
            adj[b].append(a)
        seen = [-1] * len(self.nodes)
        comps = []
        for s in range(len(self.nodes)):
            if seen[s] >= 0 or not adj[s]:
                continue
            q = deque([s])
            seen[s] = len(comps)
            size = 0
            while q:
                u = q.popleft()
                size += 1
                for v in adj[u]:
                    if seen[v] < 0:
                        seen[v] = len(comps)
                        q.append(v)
            comps.append(size)
        if not comps:
            return [], [], comps
        best = int(np.argmax(comps))
        keep = [i for i in range(len(self.nodes)) if seen[i] == best]
        remap = {old: new for new, old in enumerate(keep)}
        edges = [(remap[a], remap[b], w) for (a, b), w in self.edges.items() if a in remap and b in remap]
        return keep, edges, sorted(comps, reverse=True)


def offset_line(m, pts, dist, step=0.4):
    P = m.resample(pts, step)
    return P + m.polyline_normals(P) * dist


def build_street_graph(m, T, G, cfg):
    g = Graph(G, m)
    chain = 0
    for pts, w in m.AVENUES:
        g.polyline(pts, 0.7, w, chain)
        chain += 1
    for pts in m.ROADS:                                            # country roads: walkable by definition
        g.polyline(pts, 1.0, 0.55, chain, always=True)
        chain += 1
    for gt in m.ANCHORS.get('_gates', []):                        # through each gate: road <-> inner avenue
        p, n = np.array(gt['pos'][:2]), np.array(gt['n_out'])
        g.polyline([p - n * 2.2, p + n * 1.6], 0.5, 0.8, chain, always=True)
        chain += 1
    C = m.ANCHORS.get('_ring_center', (2.0, -8.0))
    for r in m.ANCHORS.get('_ring_streets', []):
        nseg = max(24, int(2 * math.pi * r / 0.7))
        ring = [(C[0] + r * math.cos(2 * math.pi * k / nseg), C[1] + r * math.sin(2 * math.pi * k / nseg)) for k in range(nseg)]
        g.polyline(ring, 0.7, 0.3, chain, closed=True)
        chain += 1
    for k in range(60):                                            # radial lanes (keep the free fragments)
        a = 2 * math.pi * k / 60
        g.polyline([(C[0] + 3.0 * math.cos(a), C[1] + 3.0 * math.sin(a)), (C[0] + 52 * math.cos(a), C[1] + 52 * math.sin(a))],
                   0.6, 0.25, chain)
        chain += 1
    for d in (0.55, 1.05):                                         # harbour promenade
        g.polyline(offset_line(m, m.HARBOR, d), 0.7, 0.8, chain)
        chain += 1
    P = m.resample(m.WALL_PATH, 0.5)                               # pomerium path inside the walls
    N = m.polyline_normals(P)
    mid = len(P) // 2
    if not m.points_in_poly(np.array([P[mid][0] + N[mid][0]]), np.array([P[mid][1] + N[mid][1]]), m.WALL_PATH)[0]:
        N = -N
    g.polyline(P + N * 0.75, 0.7, 0.6, chain)
    chain += 1
    for name, pts in cfg.get('extra_walkways', {}).items():
        g.polyline(pts, 0.6, 0.8, chain)
        chain += 1
    for v in m.ANCHORS.get('venues', {}).values():                # paths linking each venue's entrances
        ents = [e[:2] for e in v.get('entrances', [])]
        if len(ents) > 2:
            g.polyline(ents if v.get('type') != 'arena' else ents[:1] + ents[4:5] + ents[1:2] + ents[5:6] + ents[2:3]
                       + ents[6:7] + ents[3:4] + ents[7:8], 0.6, 0.8, chain, closed=v.get('type') == 'arena')
            chain += 1
    g.cross_link()
    keep, edges, comps = g.largest_component()
    nodes = []
    for i in keep:
        x, y = g.nodes[i]
        z = max(float(T.h(x, y)), float(G.floor_at(x, y))) + 0.01
        nodes.append([round(x, 3), round(y, 3), round(z, 3)])
    return {'nodes': nodes, 'edges': [[a, b, round(float(w), 2)] for a, b, w in edges]}, comps


def random_walks(graph, n_walks=260, min_len=25.0, seed=3):
    """Long non-backtracking walks over the graph (for the Blender crowd curves)."""
    rng = np.random.default_rng(seed)
    N = np.asarray(graph['nodes'], float)
    adj = [[] for _ in range(len(N))]
    for a, b, _ in graph['edges']:
        adj[a].append(b)
        adj[b].append(a)
    walks = []
    for _ in range(n_walks):
        u = int(rng.integers(len(N)))
        prev, path, L = -1, [u], 0.0
        for _step in range(400):
            nb = [v for v in adj[u] if v != prev] or adj[u]
            if not nb:
                break
            v = int(nb[rng.integers(len(nb))])
            L += float(np.linalg.norm(N[v, :2] - N[u, :2]))
            prev, u = u, v
            path.append(u)
            if L > min_len and rng.random() < 0.02:
                break
        if L > 6.0:
            walks.append(N[path].tolist())
    return walks


# =============================================================================
# Zones, lanes, lights, landmarks
# =============================================================================
def sample_zone(G, T, poly, n, rng, z_lift=0.01, exclude=None):
    P = np.asarray(poly, float)
    xmin, ymin = P.min(axis=0)
    xmax, ymax = P.max(axis=0)
    out = []
    for _ in range(n * 40):
        x, y = rng.uniform(xmin, xmax), rng.uniform(ymin, ymax)
        if not _pip(np.array([[x]]), np.array([[y]]), P)[0, 0] or not G.free(np.array([x]), np.array([y]))[0]:
            continue
        if exclude is not None and math.hypot(x - exclude[0], y - exclude[1]) < exclude[2]:
            continue
        z = max(float(T.h(x, y)), float(G.floor_at(x, y))) + z_lift
        out.append([round(x, 3), round(y, 3), round(z, 3)])
        if len(out) >= n:
            break
    return out


def strip_poly(m, pts, d0, d1, step=0.6):
    a = offset_line(m, pts, d0, step)
    b = offset_line(m, pts, d1, step)
    return np.vstack([a, b[::-1]]).tolist()


def build_spawn_zones(m, T, G, cfg, venues):
    rng = np.random.default_rng(11)
    zones = []
    for z in cfg.get('spawn_zones', []):
        if z['shape'] == 'rect':
            poly = m.rect_pts(z['center'][0], z['center'][1], z['size'][0], z['size'][1], math.radians(z.get('angle', 0)))
        elif z['shape'] == 'circle':
            poly = [(z['center'][0] + z['radius'] * math.cos(2 * math.pi * k / 16),
                     z['center'][1] + z['radius'] * math.sin(2 * math.pi * k / 16)) for k in range(16)]
        elif z['shape'] == 'harbour_strip':
            poly = strip_poly(m, m.HARBOR, z['from'], z['to'])
        else:
            poly = z['poly']
        pts = sample_zone(G, T, poly, z.get('points', 80), rng, exclude=z.get('exclude'))
        zones.append({'id': z['id'], 'poly': [r3(p, 2) for p in poly], 'density': z.get('density', 1.0),
                      'points': pts})
    for gt in m.ANCHORS.get('_gates', []):
        p = np.array(gt['pos'][:2])
        for side, sgn in (('in', -1), ('out', 1)):
            c = p + np.array(gt['n_out']) * sgn * 1.6
            poly = [(c[0] + 1.1 * math.cos(2 * math.pi * k / 12), c[1] + 1.1 * math.sin(2 * math.pi * k / 12)) for k in range(12)]
            zones.append({'id': 'gate_%d_%s' % (len(zones), side), 'poly': [r3(q, 2) for q in poly], 'density': 0.5,
                          'points': sample_zone(G, T, poly, 20, rng) if side == 'in' else
                          [[round(float(q[0]), 3), round(float(q[1]), 3), round(float(T.h(q[0], q[1])) + 0.01, 3)]
                           for q in poly[::2]]})
    return zones


def build_ship_lanes(m, T, cfg):
    lanes, report = [], []
    static = [(x, y) for (_n, kind, x, y, _h, _s) in m.ANCHORS.get('_ships', [])]
    for ln in cfg.get('ship_lanes', []):
        P = m.resample(ln['points'], 0.5)
        depth_ok = float(T.h(P[:, 0], P[:, 1]).max())
        clr = min((math.hypot(px - sx, py - sy) for px, py in P for sx, sy in static), default=99)
        report.append((ln['id'], round(depth_ok, 2), round(clr, 2)))
        lanes.append({'id': ln['id'], 'points': [r3(p, 2) for p in ln['points']], 'loop': ln.get('loop', False),
                      'kinds': ln.get('kinds', ['merchant']), 'speed': ln.get('speed', 1.2), 'dwell_s': ln.get('dwell_s', 0), 'then': ln.get('then'),
                      'every_s': ln.get('every_s', 60)})
    return lanes, report


def build_moorings(m, cfg):
    hc = np.array(m.HARBOR_CENTER)
    out = {'moorings': [], 'anchored': [], 'boats': []}
    for name, kind, x, y, hd, sc in m.ANCHORS.get('_ships', []):
        rec = {'object': name, 'kind': kind, 'pos': [round(x, 3), round(y, 3), 0.0], 'heading_deg': round(hd, 1),
               'scale': round(sc * (m.SHIP_SCALE if kind != 'boat' else 1.15), 3)}
        if kind == 'boat':
            out['boats'].append(rec)
        elif kind.startswith('moored') or (np.linalg.norm(np.array([x, y]) - hc) < 13.5 and y > -24.0):
            out['moorings'].append(rec)
        else:
            out['anchored'].append(rec)
    return out


def build_berths(m, man_ships, n=12, clearance=1.7):
    """Free water spots a little off the harbour quays (for arriving fleets), nearest the harbour centre first."""
    P = m.resample(m.HARBOR, 0.5)
    N = m.polyline_normals(P)
    occupied = [np.array(s['pos'][:2]) for s in man_ships]
    out = []
    for i in range(0, len(P), 3):
        for d in (2.0, -2.0):
            q = P[i] + N[i] * d
            if m.points_in_poly(np.array([q[0]]), np.array([q[1]]), m.COAST_POLY)[0]:
                continue
            if all(np.linalg.norm(q - o) > clearance for o in occupied + out):
                out.append(q)
            break
    hc = np.array(m.HARBOR_CENTER)
    out.sort(key=lambda q: float(np.linalg.norm(q - hc)))
    return [r3(q, 2) for q in out[:n]]


def build_night_lights(m, T, rng):
    L = []
    for (x, y, z) in m.ANCHORS.get('_lighthouses', []):
        L.append({'pos': r3((x, y, z + 0.1)), 'kind': 'lighthouse', 'strength': 1.0})
    for k, (x, y, zt) in enumerate(m.ANCHORS.get('_towers', [])):
        if k % 2 == 0:
            L.append({'pos': r3((x, y, zt + 0.12)), 'kind': 'torch', 'strength': 0.5})
    for gt in m.ANCHORS.get('_gates', []):
        p, u, n = np.array(gt['pos'][:2]), np.array(gt['u']), np.array(gt['n_out'])
        for s in (-1, 1):
            q = p + u * s * 0.55 + n * 0.62
            L.append({'pos': r3((q[0], q[1], gt['pos'][2] + 0.95)), 'kind': 'torch', 'strength': 0.8})
    for idx in m.PAVED_AVENUES:
        pts, w = m.AVENUES[idx]
        P = m.resample(pts, 2.6)
        N = m.polyline_normals(P)
        for k in range(len(P)):
            for s in (-1, 1):
                q = P[k] + N[k] * s * w * 0.5
                L.append({'pos': r3((q[0], q[1], float(T.h(q[0], q[1])) + 0.32)), 'kind': 'lamp', 'strength': 0.35})
    houses = [h for h in m.ANCHORS.get('_houses', []) if m.points_in_poly(np.array([h[0]]), np.array([h[1]]), m.WALL_PATH)[0]]
    for k in rng.choice(len(houses), size=min(600, len(houses)), replace=False):
        cx, cy, w, d, ang, zg, zt, fl = houses[int(k)]
        f = int(rng.integers(fl))
        q = m.L2W(cx, cy, ang, 0.0, -d / 2 - 0.02)
        z = zg + f * 0.27 + 0.15
        L.append({'pos': r3((q[0], q[1], z)), 'kind': 'window', 'strength': 0.25,
                  'order': round(m.window_alpha(q[0], q[1], z), 3)})
    return L


def polylen(P):
    P = np.asarray(P, float)
    return float(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1).sum()) if len(P) > 1 else 0.0


def graph_route(graph, waypoints):
    """Shortest path over the street graph through the waypoints (each snapped to its nearest node)."""
    import heapq
    N = np.asarray(graph['nodes'], float)
    adj = [[] for _ in range(len(N))]
    for a, b, _w in graph['edges']:
        d = float(np.linalg.norm(N[a, :2] - N[b, :2]))
        adj[a].append((b, d))
        adj[b].append((a, d))
    snap = [int(np.argmin(np.linalg.norm(N[:, :2] - np.asarray(w[:2]), axis=1))) for w in waypoints]
    path = [snap[0]]
    for s, t in zip(snap[:-1], snap[1:]):
        dist, prev, pq = {s: 0.0}, {}, [(0.0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == t:
                break
            if d > dist.get(u, 1e18):
                continue
            for v, w in adj[u]:
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v], prev[v] = nd, u
                    heapq.heappush(pq, (nd, v))
        seg, u = [], t
        while u != s and u in prev:
            seg.append(u)
            u = prev[u]
        path += seg[::-1]
    return [r3(N[i]) for i in path]


def obj_bbox(names):
    pts = []
    for nm in names:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'MESH':
            continue
        co = np.empty(len(ob.data.vertices) * 3, np.float32)
        ob.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        pts.append(co @ M[:3, :3].T + M[:3, 3])
    if not pts:
        return None
    P = np.vstack(pts)
    return P.min(axis=0), P.max(axis=0)


def build_landmarks(cfg):
    out = []
    for lm in cfg.get('landmarks', []):
        bb = obj_bbox(lm.get('objects', []))
        if bb is None and 'target' not in lm:
            continue
        if 'target' in lm:
            tgt = lm['target']
            size = lm.get('size', 8.0)
        else:
            lo, hi = bb
            tgt = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2] + (hi[2] - lo[2]) * 0.35]
            size = float(max(hi[0] - lo[0], hi[1] - lo[1]))
        out.append({'id': lm['id'], 'label': lm['label'],
                    'camera': {'target': r3(tgt), 'dist': round(lm.get('dist', max(6.0, size * 1.5)), 2),
                               'yaw': lm.get('yaw', -90), 'pitch': lm.get('pitch', 32)}})
    return out


def jsonable_venue(v):
    out = {}
    for k, val in v.items():
        if k == 'seat_tiers':
            out[k] = [{'ring': [r3(p) for p in t['ring']], 'capacity': int(t['capacity'])} for t in val]
        elif isinstance(val, (list, tuple)) and val and isinstance(val[0], (list, tuple, np.ndarray)):
            out[k] = [r3(p) for p in val]
        elif isinstance(val, (list, tuple, np.ndarray)) and len(val) in (2, 3) and not isinstance(val[0], str):
            out[k] = r3(val)
        elif isinstance(val, float):
            out[k] = round(val, 3)
        else:
            out[k] = val
    return out


# =============================================================================
# Manifest
# =============================================================================
def build_manifest(m, cfg, report):
    T, root = m.ANCHORS['_T'], m.ANCHORS['_root']
    rng = np.random.default_rng(17)
    G = build_walk_grid(m, T, root, cfg)
    graph, comps = build_street_graph(m, T, G, cfg)
    report['street_graph'] = {'nodes': len(graph['nodes']), 'edges': len(graph['edges']), 'components': comps[:6]}
    venues = [jsonable_venue(v) for v in m.ANCHORS.get('venues', {}).values()]
    zones = build_spawn_zones(m, T, G, cfg, venues)
    lanes, lane_report = build_ship_lanes(m, T, cfg)
    report['ship_lanes(max_depth,clearance)'] = lane_report
    ships = build_moorings(m, cfg)
    lights = build_night_lights(m, T, rng)
    routes = {}
    for rid, waypoints in cfg.get('routes', {}).items():
        path = graph_route(graph, waypoints)
        report.setdefault('routes', {})[rid] = {'points': len(path), 'length_m': round(polylen(path), 1)}
        routes[rid] = path
    sun = cfg['sun']
    rise, sset = sunarc.sunrise_sunset(sun['latitude_deg'], sun['default_day_of_year'])
    man = {
        'id': cfg['id'], 'name': cfg['name'], 'version': SCHEMA_VERSION,
        'model_scale': cfg.get('model_scale', 15), 'extent': [-m.HALF, -m.HALF, m.HALF, m.HALF], 'sea_level': 0.0,
        'world_map': cfg['world_map'],
        'sun': dict(sun, sunrise_h=round(rise, 3), sunset_h=round(sset, 3)),
        'files': {'model': 'city.glb', 'proxies': 'proxies.glb', 'terrain_albedo': 'terrain_albedo.png', 'thumb': 'thumb.png'},
        'street_graph': graph,
        'spawn_zones': zones,
        'ship_lanes': lanes,
        'moorings': ships['moorings'], 'anchored_ships': ships['anchored'], 'boats': ships['boats'],
        'berths': build_berths(m, ships['moorings'] + ships['anchored'] + ships['boats']),
        'venues': venues,
        'routes': routes,
        'night_lights': lights,
        'landmarks': build_landmarks(cfg),
        'steam_vents': [r3(p) for p in m.ANCHORS.get('_steam', [])],
        'events': cfg.get('events', []),
    }
    return man, G, graph


# =============================================================================
# Blender side: Anchors + Proxies collections
# =============================================================================
def _curve(name, polylines, coll, cyclic=False):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    for pts in polylines:
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for p, q in zip(sp.points, pts):
            p.co = (q[0], q[1], q[2] if len(q) > 2 else 0.0, 1.0)
        sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    coll.objects.link(ob)
    return ob


def _points(name, pts, coll, attrs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts], [], [])
    for an, (typ, vals) in (attrs or {}).items():
        a = me.attributes.new(an, typ, 'POINT')
        a.data.foreach_set('value', np.asarray(vals, np.float32 if typ == 'FLOAT' else np.int32))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def write_blend_anchors(m, man, root):
    for nm in ("Anchors", "Proxies"):
        old = bpy.data.collections.get(nm)
        if old is not None:
            for o in list(old.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(old)
    A = bpy.data.collections.new("Anchors")
    root.children.link(A)
    rng = np.random.default_rng(5)
    walks = random_walks(man['street_graph'])
    _curve("ANC_WalkPaths", walks, A)
    N = man['street_graph']['nodes']
    _curve("ANC_StreetGraph", [[N[a], N[b]] for a, b, _ in man['street_graph']['edges']], A)
    for ln in man['ship_lanes']:
        _curve("ANC_Lane_" + ln['id'], [[(p[0], p[1], 0.0) for p in ln['points']]], A, ln['loop'])
    for rid, pts in man['routes'].items():
        _curve("ANC_Route_" + rid, [pts], A)
    for v in man['venues']:
        seats, tier = [], []
        for ti, t in enumerate(v.get('seat_tiers', [])):
            seats += t['ring']
            tier += [ti] * len(t['ring'])
        if seats:
            _points("ANC_Seats_" + v['id'], seats, A,
                    {'rank': ('FLOAT', rng.random(len(seats))), 'tier': ('INT', tier)})
        if 'track_centerline' in v:
            _curve("ANC_Race_" + v['id'], [v['track_centerline']], A, cyclic=True)
    kinds = {'window': 0, 'lamp': 1, 'torch': 2, 'lighthouse': 3}
    NL = man['night_lights']
    _points("ANC_NightLights", [l['pos'] for l in NL], A,
            {'kind': ('INT', [kinds[l['kind']] for l in NL]), 'strength': ('FLOAT', [l['strength'] for l in NL]),
             'order': ('FLOAT', [l.get('order', 0.0) for l in NL])})
    for z in man['spawn_zones']:
        if z['points']:
            _points("ANC_Spawn_" + z['id'], z['points'], A, {'rank': ('FLOAT', rng.random(len(z['points'])))})
    for i, mo in enumerate(man['moorings']):
        e = bpy.data.objects.new("ANC_Mooring_%02d" % i, None)
        e.location = mo['pos']
        e.rotation_euler = (0, 0, math.radians(mo['heading_deg']))
        e.empty_display_type = 'SINGLE_ARROW'
        A.objects.link(e)
    for lm in man['landmarks']:
        c = lm['camera']
        e = bpy.data.objects.new("ANC_Cam_" + lm['id'], None)
        e.location = cam_position(c)
        e.empty_display_type = 'CONE'
        e["target"] = c['target']
        A.objects.link(e)
    A.hide_render = True
    A.hide_viewport = True
    return A


def cam_position(c):
    """Landmark camera convention (both outputs): yaw = deg CCW from +X of the camera around the target, pitch above."""
    y, p = math.radians(c['yaw']), math.radians(c['pitch'])
    t = c['target']
    return (t[0] + c['dist'] * math.cos(p) * math.cos(y), t[1] + c['dist'] * math.cos(p) * math.sin(y),
            t[2] + c['dist'] * math.sin(p))


def write_proxies(m, root):
    T = m.ANCHORS['_T']
    P = bpy.data.collections.new("Proxies")
    root.children.link(P)
    # low-poly terrain (~20k tris)
    n = 101
    xs = np.linspace(-m.HALF, m.HALF, n)
    X, Y = np.meshgrid(xs, xs)
    Z = T.h(X, Y)
    verts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    idx = np.arange(n * n).reshape(n, n)
    faces = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()])
    me = bpy.data.meshes.new("CAP_Proxy_Terrain")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    P.objects.link(bpy.data.objects.new("CAP_Proxy_Terrain", me))
    # buildings: one box per house, an oriented box per landmark part
    mb = m.MB()
    for (cx, cy, w, d, ang, zg, zt, fl) in m.ANCHORS.get('_houses', []):
        mb.box(cx, cy, zg - 0.3, w, d, zt - zg + 0.3 + min(w, d) * 0.3, ang, (0.5, 0.5, 0.5))
    for ob in root.all_objects:
        if ob.type == 'MESH' and ob.name.startswith("CAP_LM_") and "Paving" not in ob.name and "Chariots" not in ob.name:
            lo, hi = obj_bbox([ob.name])
            mb.box((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2], hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 0.0, (0.5, 0.5, 0.5))
    mb.to_object("CAP_Proxy_Buildings", P, [])
    # walls: simplified boxes every ~3 m
    W = m.resample(m.WALL_PATH, 3.0)
    wb = m.MB()
    for a, b in zip(W[:-1], W[1:]):
        mid = (a + b) / 2
        d = b - a
        z0 = float(min(T.h(a[0], a[1]), T.h(b[0], b[1])))
        wb.box(mid[0], mid[1], z0 - 0.5, float(np.linalg.norm(d)) + 0.1, 0.6, 2.0, math.atan2(d[1], d[0]), (0.5, 0.5, 0.5))
    wb.to_object("CAP_Proxy_Walls", P, [])
    P.hide_render = True
    P.hide_viewport = True
    return P
