"""Ambient extras (PLAN 2.8): bird flocks wheeling over the city by day, and ox-carts plodding along the country
roads. Driven by the manifest (roads = street-graph edges outside the walls) and the generator layout."""
import math

import bpy
import numpy as np

import cine
import crowds as crowds_mod
import figures


def cart_prop():
    p = figures.P()
    wood, wheel, ox = (0.45, 0.31, 0.18), (0.26, 0.17, 0.10), (0.62, 0.50, 0.36)
    p.box(-0.05, 0.0, 0.035, 0.16, 0.10, 0.06, wood)
    p.box(-0.05, 0.0, 0.095, 0.15, 0.09, 0.035, (0.72, 0.62, 0.40))                  # load (hay / sacks)
    for s in (-1, 1):
        p.box(-0.05, s * 0.058, 0.0, 0.07, 0.012, 0.07, wheel)
    p.box(0.07, 0.0, 0.05, 0.10, 0.01, 0.01, wood)                                    # shaft
    p.box(0.17, 0.0, 0.035, 0.11, 0.045, 0.05, ox)
    for x in (0.13, 0.21):
        for y in (-0.015, 0.015):
            p.box(x, y, 0.0, 0.012, 0.012, 0.04, ox)
    p.box(0.235, 0.0, 0.06, 0.03, 0.03, 0.03, ox)
    p.box(0.0, 0.0, 0.13, 0.02, 0.02, 0.035, figures.TINT, tint=True)                 # driver
    p.ball(0.0, 0.0, 0.17, 0.009, figures.SKIN)
    return p.out()


def bird_flocks(f0, f1, flocks=3, birds=12, seed=12):
    cine.clear_coll("CIN_Birds")
    c = cine.coll("CIN_Birds")
    rng = np.random.default_rng(seed)
    mat = cine.mat_principled("CIN_Bird", (0.10, 0.09, 0.09), 0.9)
    for k in range(flocks):
        V, F = [], []
        for i in range(birds):
            a = 2 * math.pi * i / birds + rng.uniform(-0.2, 0.2)
            r = rng.uniform(4.5, 7.5)
            x, y, z = r * math.cos(a), r * math.sin(a), rng.uniform(-0.6, 0.6)
            tx, ty = -math.sin(a), math.cos(a)                     # tangent = flight direction
            nx, ny = math.cos(a), math.sin(a)
            b = len(V)
            V += [(x + tx * 0.06, y + ty * 0.06, z), (x - tx * 0.03 + nx * 0.12, y - ty * 0.03 + ny * 0.12, z + 0.03),
                  (x - tx * 0.04, y - ty * 0.04, z), (x - tx * 0.03 - nx * 0.12, y - ty * 0.03 - ny * 0.12, z + 0.03)]
            F += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
        ob = cine.mesh_object("CIN_Flock_%d" % k, V, F, c, [mat])
        piv = bpy.data.objects.new("CIN_FlockPivot_%d" % k, None)
        c.objects.link(piv)
        piv.location = (rng.uniform(-25, 25), rng.uniform(-15, 20), rng.uniform(7, 11))
        ob.parent = piv
        spd = rng.uniform(0.25, 0.4) * (1 if k % 2 else -1)
        for f in (f0, f1):
            piv.rotation_euler = (0.0, 0.0, spd * (f - f0) / cine.FPS)
            piv.keyframe_insert('rotation_euler', frame=f)
        cine.set_interp(piv, 'LINEAR')
        cine.add_noise(piv, 'location', 2, 0.6, 90.0, k * 10.0)
    return c


def carts(man, f0, f1, n=6, seed=13, speed=0.18):
    """Carts going back and forth along country roads (street-graph chains outside the walls)."""
    m = cine.generator()
    roads = [r for r in m.ROADS if len(r) >= 2]
    if not roads:
        return None
    cine.clear_coll("CIN_Carts")
    c = cine.coll("CIN_Carts")
    rng = np.random.default_rng(seed)
    T_h = None
    N = np.asarray(man['street_graph']['nodes'], float)
    mesh_ob = figures.to_blender("CIN_CartMesh", cart_prop(), None, [crowds_mod.figure_material()])
    mesh = mesh_ob.data
    bpy.data.objects.remove(mesh_ob)
    for k in range(n):
        road = np.asarray(roads[k % len(roads)], float)
        P = cine.poly_resample(road, 0.4)
        # road height from the nearest street-graph node (the roads are part of the graph)
        z = np.array([N[int(np.argmin(np.linalg.norm(N[:, :2] - p, axis=1))), 2] for p in P])
        P3 = np.column_stack([P, z])
        s_arr = cine.arclen(P3)
        L = float(s_arr[-1])
        ob = bpy.data.objects.new("CIN_Cart_%d" % k, mesh)
        c.objects.link(ob)
        off = rng.uniform(0, 2 * L)
        spd = speed * rng.uniform(0.8, 1.2)
        side = 0.12 * (1 if k % 2 else -1)
        for f in range(f0, f1 + 1, 6):
            u = (off + spd * (f - f0) / cine.FPS) % (2 * L)
            s = L - abs(u - L)
            fwd = u < L
            p, h = cine.at_arc(P3[:, :2], s_arr, s)
            h = h if fwd else h + math.pi
            q = p + np.array([-math.sin(h), math.cos(h)]) * side
            zz = float(np.interp(s, s_arr, P3[:, 2]))
            ob.location = (q[0], q[1], zz)
            ob.rotation_euler = (0.0, 0.0, h)
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('rotation_euler', frame=f)
        import ships
        ships._unwrap_heading(ob)
    return c


def add(man, f0, f1, daylight=True):
    try:
        if daylight:
            bird_flocks(f0, f1)
        carts(man, f0, f1)
    except Exception as e:                       # extras must never break a shot
        print("[Cine] extras skipped:", e)
