"""People: walkers on the street graph's walk paths, idlers in spawn zones, seated spectators, and one-way
streams toward venue entrances. All Geometry Nodes, driven by keyframed modifier inputs (Density / Fill /
Excitement), so a shot can thin the streets at night or fill a venue before an event.

Figures come from generator/figures.py; the per-person clothing colour is a 'tint' point attribute read by the
CIN_Figure material through the instancer.
"""
import math

import bpy
import numpy as np

import cine
import figures
import gn
from gn import GN

FIG_SPEED = 0.13          # m/s at 1:15 - a stroll for the miniature people


def figure_material():
    m = bpy.data.materials.get("CIN_Figure")
    if m is not None:
        return m
    m = bpy.data.materials.new("CIN_Figure")
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get("Principled BSDF")
    col = nt.nodes.new('ShaderNodeAttribute')
    col.attribute_name, col.attribute_type = 'Col', 'GEOMETRY'
    tint = nt.nodes.new('ShaderNodeAttribute')
    tint.attribute_name, tint.attribute_type = 'tint', 'INSTANCER'
    lt = nt.nodes.new('ShaderNodeMath')
    lt.operation = 'LESS_THAN'
    nt.links.new(col.outputs['Alpha'], lt.inputs[0])
    lt.inputs[1].default_value = 0.75
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(lt.outputs[0], mix.inputs[0])
    nt.links.new(col.outputs['Color'], mix.inputs[6])
    nt.links.new(tint.outputs['Color'], mix.inputs[7])
    nt.links.new(mix.outputs[2], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.9
    return m


def proto_collection(name, kinds):
    """An unlinked collection of prop objects used as instances."""
    c = bpy.data.collections.get(name)
    if c is not None:
        return c
    c = bpy.data.collections.new(name)
    c.use_fake_user = True
    mat = figure_material()
    for k in kinds:
        ob = figures.to_blender("CIN_Prop_" + k, figures.PROPS[k], None, [mat])
        c.objects.link(ob)
    return c


def _palette_tint(g, seed, ident=None):
    """Random clothing colour from a small earthy palette (stored on points as 'tint')."""
    pal = [cine.generator().lin(c) for c in figures.PALETTE]
    k = g.rand('INT', 0, len(pal) - 1, seed, ident)
    # build the palette as a chain of switches on k (10 entries: cheap)
    out = g.combine(*[float(v) for v in pal[0]])
    for i, c in enumerate(pal[1:], start=1):
        sw = g.node('GeometryNodeSwitch', input_type='VECTOR')
        g.set(g.i(sw, 'Switch'), g.compare('EQUAL', k, i, 'INT'))
        g.set(g.i(sw, 'False'), out)
        g.set(g.i(sw, 'True'), g.combine(*[float(v) for v in c]))
        out = g.o(sw, 'Output')
    jitter = g.rand('FLOAT', 0.85, 1.12, seed + 1, ident)
    return g.vmath('SCALE', out, scale=jitter)


def walkers_group():
    """Ping-pong walkers on the splines of a curve object (each agent: random spline, offset, speed)."""
    g = GN("CIN_Walkers")
    paths = g.input("Paths", 'NodeSocketObject')
    figs = g.input("Figures", 'NodeSocketCollection')
    count = g.input("Count", 'NodeSocketInt', 1200, 0, 100000)
    dens = g.input("Density", 'NodeSocketFloat', 1.0, 0.0, 1.0)
    speed = g.input("Speed", 'NodeSocketFloat', FIG_SPEED, 0.0, 10.0)
    seed = g.input("Seed", 'NodeSocketInt', 1)
    spread = g.input("Spread", 'NodeSocketFloat', 0.09, 0.0, 2.0)
    oi = g.wire(g.node('GeometryNodeObjectInfo', transform_space='ORIGINAL'), Object=paths)
    curves = g.o(oi, 'Geometry')
    pts = g.wire(g.node('GeometryNodePoints'), Count=count)
    ds = g.node('GeometryNodeAttributeDomainSize', component='CURVE')
    g.set(g.i(ds, 'Geometry'), curves)
    nspl = g.o(ds, 'Spline Count')
    ci = g.rand('INT', 0, g.math('SUBTRACT', nspl, 1.0), seed)
    sl = g.node('GeometryNodeSplineLength')
    si = g.node('GeometryNodeSampleIndex', data_type='FLOAT', domain='CURVE')
    g.wire(si, Geometry=curves, Value=g.o(sl, 'Length'), Index=ci)
    L = g.o(si, 'Value')
    off = g.rand('FLOAT', 0.0, 1.0, g.math('ADD', seed, 11.0))
    spd = g.math('MULTIPLY', speed, g.rand('FLOAT', 0.7, 1.3, g.math('ADD', seed, 12.0)))
    t = g.time()
    twoL = g.math('MULTIPLY', L, 2.0)
    u = g.math('FLOORED_MODULO', g.math('ADD', g.math('MULTIPLY', off, twoL), g.math('MULTIPLY', t, spd)), twoL)
    s = g.math('SUBTRACT', L, g.math('ABSOLUTE', g.math('SUBTRACT', u, L)))
    fwd = g.math('SUBTRACT', 1.0, g.math('MULTIPLY', g.compare('GREATER_THAN', u, L), 2.0))   # +1 out, -1 back
    sc = g.node('GeometryNodeSampleCurve', mode='LENGTH', use_all_curves=False)
    g.wire(sc, Curves=curves, Length=s, Curve__Index=ci)
    tang = g.vmath('SCALE', g.o(sc, 'Tangent'), scale=fwd)
    side = g.vmath('NORMALIZE', g.vmath('CROSS_PRODUCT', tang, (0.0, 0.0, 1.0)))
    lat = g.vmath('SCALE', side, scale=g.math('MULTIPLY', spread, g.rand('FLOAT', -1.0, 1.0, g.math('ADD', seed, 13.0))))
    bob = g.math('MULTIPLY', g.math('ABSOLUTE', g.math('SINE', g.math('ADD', g.math('MULTIPLY', t, 11.0),
                                                                        g.rand('FLOAT', 0.0, 6.28, g.math('ADD', seed, 14.0))))), 0.004)
    pos = g.vmath('ADD', g.vmath('ADD', g.o(sc, 'Position'), lat), g.combine(0.0, 0.0, bob))
    sp = g.wire(g.node('GeometryNodeSetPosition'), Geometry=g.o(pts), Position=pos)
    geo = g.store(sp.outputs[0], 'tint', _palette_tint(g, 31), 'FLOAT_VECTOR')
    sel = g.compare('LESS_THAN', g.rand('FLOAT', 0.0, 1.0, g.math('ADD', seed, 15.0)), dens)
    ci_ = g.wire(g.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL'), Collection=figs)
    g.i(ci_, 'Separate Children').default_value = True
    g.i(ci_, 'Reset Children').default_value = True
    iop = g.node('GeometryNodeInstanceOnPoints')
    g.wire(iop, Points=geo, Selection=sel, Instance=g.o(ci_), Pick__Instance=True,
           Instance__Index=g.rand('INT', 0, 7, g.math('ADD', seed, 16.0)), Rotation=g.align_x(tang),
           Scale=g.rand('FLOAT', 0.9, 1.1, g.math('ADD', seed, 17.0)))
    g.output(iop.outputs[0])
    return g.ng


def point_crowd_group():
    """People standing on the points of a mesh (spawn zones, seats): shown when rank < Fill; face a centre or
    mill around; Excitement makes them jump/cheer."""
    g = GN("CIN_PointCrowd")
    src = g.input("Points", 'NodeSocketObject')
    figs = g.input("Figures", 'NodeSocketCollection')
    fill = g.input("Fill", 'NodeSocketFloat', 1.0, 0.0, 1.0)
    exc = g.input("Excitement", 'NodeSocketFloat', 0.0, 0.0, 1.0)
    face = g.input("FaceCenter", 'NodeSocketBool', False)
    center = g.input("Center", 'NodeSocketVector', (0.0, 0.0, 0.0))
    mill = g.input("Mill", 'NodeSocketFloat', 0.06, 0.0, 1.0)
    seed = g.input("Seed", 'NodeSocketInt', 3)
    oi = g.wire(g.node('GeometryNodeObjectInfo', transform_space='ORIGINAL'), Object=src)
    pts = g.wire(g.node('GeometryNodeMeshToPoints'), Mesh=g.o(oi, 'Geometry'))
    rank = g.named('rank')
    t = g.time()
    ph = g.math('MULTIPLY', rank, 97.0)
    wander = g.combine(g.math('MULTIPLY', g.math('SINE', g.math('ADD', g.math('MULTIPLY', t, 0.23), ph)), mill),
                       g.math('MULTIPLY', g.math('COSINE', g.math('ADD', g.math('MULTIPLY', t, 0.17), ph)), mill), 0.0)
    wander = g.vmath('SCALE', wander, scale=g.math('SUBTRACT', 1.0, face))
    jump = g.math('MULTIPLY', exc, g.math('MULTIPLY', g.math('ABSOLUTE', g.math('SINE', g.math('ADD', g.math('MULTIPLY', t, 7.0),
                                                                                                    g.math('MULTIPLY', rank, 61.0)))), 0.014))
    p = g.node('GeometryNodeInputPosition')
    pos = g.vmath('ADD', g.vmath('ADD', g.o(p), wander), g.combine(0.0, 0.0, jump))
    sp = g.wire(g.node('GeometryNodeSetPosition'), Geometry=g.o(pts), Position=pos)
    geo = g.store(sp.outputs[0], 'tint', _palette_tint(g, 41), 'FLOAT_VECTOR')
    to_c = g.vmath('MULTIPLY', g.vmath('SUBTRACT', center, g.o(p)), (1.0, 1.0, 0.0))
    yaw = g.math('ADD', g.math('MULTIPLY', rank, 40.0), g.math('MULTIPLY', g.math('SINE', g.math('ADD', g.math('MULTIPLY', t, 0.4), ph)), 0.5))
    rnd_dir = g.combine(g.math('COSINE', yaw), g.math('SINE', yaw), 0.0)
    sw = g.node('GeometryNodeSwitch', input_type='VECTOR')
    g.set(g.i(sw, 'Switch'), face)
    g.set(g.i(sw, 'False'), rnd_dir)
    g.set(g.i(sw, 'True'), to_c)
    ci_ = g.wire(g.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL'), Collection=figs)
    g.i(ci_, 'Separate Children').default_value = True
    g.i(ci_, 'Reset Children').default_value = True
    iop = g.node('GeometryNodeInstanceOnPoints')
    g.wire(iop, Points=geo, Selection=g.compare('LESS_THAN', rank, fill), Instance=g.o(ci_), Pick__Instance=True,
           Instance__Index=g.rand('INT', 0, 7, seed), Rotation=g.align_x(g.o(sw, 'Output')),
           Scale=g.rand('FLOAT', 0.92, 1.08, g.math('ADD', seed, 1.0)))
    g.output(iop.outputs[0])
    return g.ng


def streamers_group():
    """One-way walkers: agent i starts at Start + rand*Window, walks its spline to the end (an entrance), vanishes."""
    g = GN("CIN_Streamers")
    paths = g.input("Paths", 'NodeSocketObject')
    figs = g.input("Figures", 'NodeSocketCollection')
    count = g.input("Count", 'NodeSocketInt', 400, 0, 100000)
    start = g.input("Start", 'NodeSocketFloat', 0.0)
    window = g.input("Window", 'NodeSocketFloat', 30.0)
    speed = g.input("Speed", 'NodeSocketFloat', FIG_SPEED * 1.3)
    reverse = g.input("Reverse", 'NodeSocketBool', False)
    seed = g.input("Seed", 'NodeSocketInt', 5)
    oi = g.wire(g.node('GeometryNodeObjectInfo', transform_space='ORIGINAL'), Object=paths)
    curves = g.o(oi, 'Geometry')
    pts = g.wire(g.node('GeometryNodePoints'), Count=count)
    ds = g.node('GeometryNodeAttributeDomainSize', component='CURVE')
    g.set(g.i(ds, 'Geometry'), curves)
    ci = g.rand('INT', 0, g.math('SUBTRACT', g.o(ds, 'Spline Count'), 1.0), seed)
    sl = g.node('GeometryNodeSplineLength')
    si = g.node('GeometryNodeSampleIndex', data_type='FLOAT', domain='CURVE')
    g.wire(si, Geometry=curves, Value=g.o(sl, 'Length'), Index=ci)
    L = g.o(si, 'Value')
    t0 = g.math('ADD', start, g.math('MULTIPLY', window, g.rand('FLOAT', 0.0, 1.0, g.math('ADD', seed, 1.0))))
    spd = g.math('MULTIPLY', speed, g.rand('FLOAT', 0.75, 1.25, g.math('ADD', seed, 2.0)))
    t = g.time()
    walked = g.math('MULTIPLY', g.math('SUBTRACT', t, t0), spd)
    s = g.math('ADD', g.math('MULTIPLY', reverse, g.math('SUBTRACT', L, g.math('MULTIPLY', walked, 2.0))), walked)
    vis = g.math('MULTIPLY', g.compare('GREATER_THAN', walked, 0.0), g.compare('LESS_THAN', walked, L))
    sc = g.node('GeometryNodeSampleCurve', mode='LENGTH', use_all_curves=False)
    g.wire(sc, Curves=curves, Length=s, Curve__Index=ci)
    tang = g.vmath('SCALE', g.o(sc, 'Tangent'), scale=g.math('SUBTRACT', 1.0, g.math('MULTIPLY', reverse, 2.0)))
    side = g.vmath('NORMALIZE', g.vmath('CROSS_PRODUCT', tang, (0.0, 0.0, 1.0)))
    lat = g.vmath('SCALE', side, scale=g.rand('FLOAT', -0.1, 0.1, g.math('ADD', seed, 3.0)))
    bob = g.math('MULTIPLY', g.math('ABSOLUTE', g.math('SINE', g.math('ADD', g.math('MULTIPLY', t, 11.0),
                                                                        g.rand('FLOAT', 0.0, 6.28, g.math('ADD', seed, 4.0))))), 0.004)
    pos = g.vmath('ADD', g.vmath('ADD', g.o(sc, 'Position'), lat), g.combine(0.0, 0.0, bob))
    sp = g.wire(g.node('GeometryNodeSetPosition'), Geometry=g.o(pts), Position=pos)
    geo = g.store(sp.outputs[0], 'tint', _palette_tint(g, 51), 'FLOAT_VECTOR')
    ci_ = g.wire(g.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL'), Collection=figs)
    g.i(ci_, 'Separate Children').default_value = True
    g.i(ci_, 'Reset Children').default_value = True
    iop = g.node('GeometryNodeInstanceOnPoints')
    g.wire(iop, Points=geo, Selection=g.compare('GREATER_THAN', vis, 0.5), Instance=g.o(ci_), Pick__Instance=True,
           Instance__Index=g.rand('INT', 0, 7, g.math('ADD', seed, 5.0)), Rotation=g.align_x(tang))
    g.output(iop.outputs[0])
    return g.ng


def density_at(hour):
    """How busy the streets are (0..1) by hour: up at dawn, busy late morning and evening, near-empty at night."""
    h = hour % 24
    day = cine.smoothstep(5.0, 8.5, h) * (1.0 - cine.smoothstep(21.0, 23.5, h))
    siesta = 1.0 - 0.25 * math.exp(-((h - 14.5) / 1.6) ** 2)
    return 0.06 + 0.94 * day * siesta


class Crowds:
    def __init__(self, man):
        self.man = man
        cine.clear_coll("CIN_Crowds")
        self.coll = cine.coll("CIN_Crowds")
        self.walk_figs = proto_collection("CIN_Figs_Walk", ['citizen', 'robed'])
        self.seat_figs = proto_collection("CIN_Figs_Seat", ['seated'])
        self.idle_figs = proto_collection("CIN_Figs_Idle", ['citizen', 'robed'])
        self.walkers = None
        self.idlers = {}
        self.seats = {}
        self.streams = {}

    def _holder(self, name):
        me = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, me)
        self.coll.objects.link(ob)
        return ob

    def add_walkers(self, count=1400, speed=FIG_SPEED, seed=1):
        ob = self._holder("CIN_Walkers")
        gn.add_modifier(ob, walkers_group(), {"Paths": bpy.data.objects["ANC_WalkPaths"], "Figures": self.walk_figs,
                                              "Count": count, "Speed": speed, "Seed": seed})
        self.walkers = ob
        return ob

    def add_idlers(self, zone_ids=None, fill=0.7):
        ng = bpy.data.node_groups.get("CIN_PointCrowd") or point_crowd_group()
        for z in self.man['spawn_zones']:
            if zone_ids is not None and z['id'] not in zone_ids:
                continue
            src = bpy.data.objects.get("ANC_Spawn_" + z['id'])
            if src is None:
                continue
            ob = self._holder("CIN_Idle_" + z['id'])
            gn.add_modifier(ob, ng, {"Points": src, "Figures": self.idle_figs, "Fill": fill * z['density'],
                                     "Seed": len(self.idlers) + 3})
            self.idlers[z['id']] = ob
        return self.idlers

    def add_seats(self, venue_id, fill=0.0):
        ng = bpy.data.node_groups.get("CIN_PointCrowd") or point_crowd_group()
        v = next(v for v in self.man['venues'] if v['id'] == venue_id)
        src = bpy.data.objects["ANC_Seats_" + venue_id]
        zc = float(np.mean([t['ring'][0][2] for t in v['seat_tiers']]))
        ob = self._holder("CIN_Seats_" + venue_id)
        gn.add_modifier(ob, ng, {"Points": src, "Figures": self.seat_figs, "Fill": fill, "FaceCenter": True,
                                 "Center": (v['center'][0], v['center'][1], zc), "Mill": 0.0, "Seed": 9})
        self.seats[venue_id] = ob
        return ob

    def add_stream(self, name, paths_obj, count, start_s, window_s, reverse=False, figs=None):
        ob = self._holder("CIN_Stream_" + name)
        gn.add_modifier(ob, streamers_group(), {"Paths": paths_obj, "Figures": figs or self.walk_figs, "Count": count,
                                                "Start": start_s, "Window": window_s, "Reverse": reverse,
                                                "Seed": 20 + len(self.streams)})
        self.streams[name] = ob
        return ob

    def key_density(self, frame, hour=None, value=None):
        d = density_at(hour) if value is None else value
        if self.walkers is not None:
            gn.key_input(self.walkers, "Density", d, frame)
        for zid, ob in self.idlers.items():
            z = next(z for z in self.man['spawn_zones'] if z['id'] == zid)
            gn.key_input(ob, "Fill", min(1.0, d * z['density']), frame)

    def key_fill(self, venue_id, frame, fill, excitement=None):
        gn.key_input(self.seats[venue_id], "Fill", fill, frame)
        if excitement is not None:
            gn.key_input(self.seats[venue_id], "Excitement", excitement, frame)


def stream_paths(man, venue_id, n_paths=40, seed=2, min_len=8.0, name=None):
    """Curves from random street nodes to a venue's entrances along the street graph (for Crowds.add_stream)."""
    import heapq
    N = np.asarray(man['street_graph']['nodes'], float)
    adj = [[] for _ in range(len(N))]
    for a, b, _w in man['street_graph']['edges']:
        d = float(np.linalg.norm(N[a, :2] - N[b, :2]))
        adj[a].append((b, d))
        adj[b].append((a, d))
    v = next(v for v in man['venues'] if v['id'] == venue_id)
    targets = [int(np.argmin(np.linalg.norm(N[:, :2] - np.asarray(e[:2]), axis=1))) for e in v['entrances']]
    # one multi-source Dijkstra from all entrances; walking a path back from a node gives its route in
    dist, prev, pq = {}, {}, []
    for t in targets:
        dist[t] = 0.0
        heapq.heappush(pq, (0.0, t))
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        for w_, wd in adj[u]:
            nd = d + wd
            if nd < dist.get(w_, 1e18):
                dist[w_], prev[w_] = nd, u
                heapq.heappush(pq, (nd, w_))
    rng = np.random.default_rng(seed)
    cands = [i for i, d in dist.items() if min_len < d < 45.0]
    paths = []
    for i in rng.choice(cands, size=min(n_paths, len(cands)), replace=False):
        path, u = [int(i)], int(i)
        while u in prev:
            u = prev[u]
            path.append(u)
        ent = min(v['entrances'], key=lambda e: np.linalg.norm(N[u, :2] - np.asarray(e[:2])))
        paths.append(N[path].tolist() + [list(ent)])
    c = cine.coll("CIN_Crowds")
    return cine_curve(name or ("CIN_StreamPaths_" + venue_id), paths, c)


def cine_curve(name, polylines, coll):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    for pts in polylines:
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for p, q in zip(sp.points, pts):
            p.co = (q[0], q[1], q[2], 1.0)
    ob = bpy.data.objects.new(name, cu)
    coll.objects.link(ob)
    ob.hide_render = True
    return ob
