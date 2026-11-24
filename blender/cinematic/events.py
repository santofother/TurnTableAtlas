"""Scripted events, all driven by manifest anchors (nothing hand-placed):
    chariot_race, gladiator_games, fleet_arrival, festival_night, theatre_play
Each returns a small dict of useful objects (e.g. the race leader, for the camera to follow)."""
import math

import bpy
import numpy as np

import cine
import crowds as crowds_mod
import figures


# ----------------------------------------------------------------------------------------------- helpers
def tinted_mesh(name, kind, color):
    """A prop mesh with its tint faces recoloured (for objects that aren't GN instances)."""
    me = bpy.data.meshes.get(name)
    if me is not None:
        return me
    v, f, c = figures.PROPS[kind]()
    c = [(*color, 1.0) if col[3] < 0.75 else col for col in c]
    ob = figures.to_blender(name, (v, f, c), None, [crowds_mod.figure_material()])
    me = ob.data
    bpy.data.objects.remove(ob)
    return me


def obj(name, mesh, coll):
    ob = bpy.data.objects.new(name, mesh)
    coll.objects.link(ob)
    return ob


def key_pose(ob, f, p, heading, z_extra=0.0):
    ob.location = (p[0], p[1], p[2] + z_extra)
    ob.rotation_euler = (0.0, 0.0, heading)
    ob.keyframe_insert('location', frame=f)
    ob.keyframe_insert('rotation_euler', frame=f)


def key_visible(ob, f, vis):
    ob.hide_render = ob.hide_viewport = not vis
    ob.keyframe_insert('hide_render', frame=f)
    ob.keyframe_insert('hide_viewport', frame=f)
    for fc in cine.fcurves(ob.animation_data.action):
        if fc.data_path.startswith('hide'):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def unwrap(ob):
    import ships
    ships._unwrap_heading(ob)


def venue(man, vid):
    return next(v for v in man['venues'] if v['id'] == vid)


def ellipse_of(poly):
    """Centre, axes (unit), semi-axes of a polygon (PCA) - the arena floor."""
    P = np.asarray(poly, float)[:, :2]
    c = P.mean(axis=0)
    w, V = np.linalg.eigh(np.cov((P - c).T))
    ext = [float(np.abs((P - c) @ V[:, k]).max()) for k in range(2)]
    return c, V, ext


# ----------------------------------------------------------------------------------------------- chariot race
class Track:
    """Race geometry around the spina: straight on the -n side outbound, turns round the posts."""
    def __init__(self, v):
        self.m0, self.m1 = np.array(v['turning_posts'][0][:2]), np.array(v['turning_posts'][1][:2])
        self.z = v['turning_posts'][0][2] + 0.0
        self.u = (self.m1 - self.m0) / np.linalg.norm(self.m1 - self.m0)
        self.n = np.array([-self.u[1], self.u[0]])
        self.D = float(np.linalg.norm(self.m1 - self.m0))
        self.rc = 0.95
        self.lap = 2 * self.D + 2 * math.pi * self.rc

    def pos(self, s, r):
        """Progress s (m along the r=0.95 centreline, may be negative before the first post), radius r."""
        D, rc = self.D, self.rc
        if s < 0:
            p = self.m0 + self.u * s - self.n * r
            return p, math.atan2(self.u[1], self.u[0])
        s = s % self.lap
        turn = math.pi * rc
        if s < D:
            p = self.m0 + self.u * s - self.n * r
            d = self.u
        elif s < D + turn:
            th = -math.pi / 2 + (s - D) / rc
            p = self.m1 + r * (math.cos(th) * self.u + math.sin(th) * self.n)
            d = -math.sin(th) * self.u + math.cos(th) * self.n
        elif s < 2 * D + turn:
            p = self.m1 - self.u * (s - D - turn) + self.n * r
            d = -self.u
        else:
            th = math.pi / 2 + (s - 2 * D - turn) / rc
            p = self.m0 + r * (math.cos(th) * self.u + math.sin(th) * self.n)
            d = -math.sin(th) * self.u + math.cos(th) * self.n
        return p, math.atan2(d[1], d[0])


def chariot_race(man, crowds, f0, f1, laps=2, n=6, seed=3, venue_id='hippodrome'):
    v = venue(man, venue_id)
    rng = np.random.default_rng(seed)
    cine.clear_coll("CIN_Race")
    c = cine.coll("CIN_Race")
    for o in bpy.data.objects:
        if o.name.startswith("CAP_LM_Hippodrome_Chariots"):
            o.hide_render = o.hide_viewport = True
    tr = Track(v)
    gates = np.asarray(v['start_gates'])[:, :2]
    # gates on the outbound (-n) side, nearest the spina first
    side = [(float(np.dot(g - tr.m0, tr.n)), g) for g in gates]
    starts = sorted([g for d, g in side if d < 0], key=lambda g: -float(np.dot(g - tr.m0, tr.n)))[:n]
    teams = figures.TEAMS + [(0.85, 0.66, 0.28), (0.45, 0.20, 0.55)]
    dur = (f1 - f0) / cine.FPS
    start_delay = 1.5
    total = laps * tr.lap
    base_v = (total + 1.6) / (dur - start_delay - 3.0)
    riders = []
    for i, g in enumerate(starts):
        s0 = float(np.dot(g - tr.m0, tr.u))                    # negative: behind the first post
        r0 = float(-np.dot(g - tr.m0, tr.n))
        me = tinted_mesh("CIN_Chariot_%d" % i, 'chariot', teams[i % len(teams)])
        ob = obj("CIN_Chariot_%d" % i, me, c)
        riders.append(dict(ob=ob, s=s0, r=r0, v=0.0, vmax=base_v * rng.uniform(0.96, 1.05),
                           phase=rng.uniform(0, 6.28), lane_target=0.45 + 0.2 * i, done=False))
    dt = 1.0 / cine.FPS
    lead_track = {}
    finish_frame = None
    for f in range(f0, f1 + 1):
        t = (f - f0) / cine.FPS
        for k, R in enumerate(riders):
            if t > start_delay and not R['done']:
                surge = 1.0 + 0.06 * math.sin(t * 0.9 + R['phase']) + 0.03 * math.sin(t * 2.3 + R['phase'] * 2)
                R['v'] = min(R['vmax'] * surge, R['v'] + 1.6 * dt)           # accelerate out of the gates
            elif R['done']:
                R['v'] = max(0.0, R['v'] - 0.9 * dt)
            R['s'] += R['v'] * dt
            if R['s'] > total and not R['done']:
                R['done'] = True
                finish_frame = finish_frame or f
            # drift toward the inside on the straights, swing wide on the turns; overtakes happen naturally
            lp = R['s'] % tr.lap if R['s'] > 0 else 0.0
            on_turn = (tr.D < lp < tr.D + math.pi * tr.rc) or lp > 2 * tr.D + math.pi * tr.rc
            target = R['lane_target'] * (1.15 if on_turn else 0.85)
            R['r'] += (min(1.5, max(0.42, target)) - R['r']) * 0.02
            p, h = tr.pos(R['s'], R['r'])
            R['p'], R['h'] = p, h
            if f % 2 == 0 or f in (f0, f1):
                key_pose(R['ob'], f, (p[0], p[1], tr.z), h)
        lead = max(riders, key=lambda R: R['s'])
        lead_track[f] = (lead['p'], lead['h'])
    for R in riders:
        unwrap(R['ob'])
    # the crowd: full, excited, roaring at the finish
    if venue_id not in crowds.seats:
        crowds.add_seats(venue_id, fill=0.97)
    crowds.key_fill(venue_id, f0, 0.97, 0.35)
    if finish_frame:
        crowds.key_fill(venue_id, finish_frame - 24, 0.97, 0.5)
        crowds.key_fill(venue_id, finish_frame + 6, 0.97, 1.0)
        crowds.key_fill(venue_id, min(f1, finish_frame + 72), 0.97, 0.6)
    leader_track = bpy.data.objects.new("CIN_RaceLeader", None)
    c.objects.link(leader_track)
    sm = None
    for f in range(f0, f1 + 1):
        p, h = lead_track[f]
        sm = np.array(p) if sm is None else sm * 0.9 + np.array(p) * 0.1      # smoothed for the camera
        if f % 2 == 0 or f in (f0, f1):
            leader_track.location = (sm[0], sm[1], tr.z)
            leader_track.keyframe_insert('location', frame=f)
    return dict(leader=leader_track, riders=[R['ob'] for R in riders], finish=finish_frame, track=tr)


# ----------------------------------------------------------------------------------------------- gladiators
def gladiator_games(man, crowds, f0, f1, pairs=5, beasts=3, beast_at=0.45, seed=5, venue_id='colosseum'):
    v = venue(man, venue_id)
    rng = np.random.default_rng(seed)
    cine.clear_coll("CIN_Games")
    c = cine.coll("CIN_Games")
    cen, V, ext = ellipse_of(v['floor_poly'])
    z = v['floor_z']
    A, B = ext[0] * 0.78, ext[1] * 0.78

    def inside(q):
        x, y = (q - cen) @ V[:, 0], (q - cen) @ V[:, 1]
        return (x / A) ** 2 + (y / B) ** 2 < 1.0

    team_cols = [(0.70, 0.14, 0.10), (0.20, 0.32, 0.62)]
    fighters = []
    for k in range(pairs):
        ang = 2 * math.pi * k / pairs + rng.uniform(-0.2, 0.2)
        home = cen + V[:, 0] * A * 0.55 * math.cos(ang) + V[:, 1] * B * 0.55 * math.sin(ang)
        a = obj("CIN_Glad_%da" % k, tinted_mesh("CIN_GladMesh_r", 'gladiator', team_cols[0]), c)
        b = obj("CIN_Glad_%db" % k, tinted_mesh("CIN_GladMesh_b", 'gladiator', team_cols[1]), c)
        fighters.append((a, b, home, rng.uniform(0, 6.28), rng.uniform(0.7, 1.3)))
    for f in range(f0, f1 + 1, 2):
        t = (f - f0) / cine.FPS
        for a, b, home, ph, w in fighters:
            drift = np.array([math.sin(t * 0.21 * w + ph), math.cos(t * 0.17 * w + ph * 2)]) * 0.35
            mid = home + drift
            th = t * 0.9 * w + ph                                  # circling each other
            gap = 0.075 + 0.04 * max(0.0, math.sin(t * 3.1 * w + ph))   # lunges close the gap
            off = np.array([math.cos(th), math.sin(th)]) * gap
            pa, pb = mid + off, mid - off
            key_pose(a, f, (pa[0], pa[1], z), math.atan2(-off[1], -off[0]))
            key_pose(b, f, (pb[0], pb[1], z), math.atan2(off[1], off[0]))
    for a, b, *_ in fighters:
        unwrap(a)
        unwrap(b)
    # beasts released from the gates, loping round the arena, chased by two venatores
    fb = f0 + int((f1 - f0) * beast_at)
    gates = [np.array(g[:2]) for g in v.get('beast_gates', [])] or [cen]
    bm = tinted_mesh("CIN_BeastMesh", 'beast', (0.70, 0.52, 0.28))
    for k in range(beasts):
        ob = obj("CIN_Beast_%d" % k, bm, c)
        g = gates[k % len(gates)]
        key_visible(ob, f0, False)
        key_visible(ob, fb + k * 10, True)
        ph = rng.uniform(0, 6.28)
        hunter = obj("CIN_Venator_%d" % k, tinted_mesh("CIN_GladMesh_g", 'gladiator', (0.85, 0.66, 0.28)), c)
        key_visible(hunter, f0, False)
        key_visible(hunter, fb + k * 10 + 36, True)
        for f in range(fb + k * 10, f1 + 1, 2):
            t = (f - fb - k * 10) / cine.FPS
            run = min(1.0, t / 1.5)
            th = ph + t * 0.55
            ring = cen + V[:, 0] * A * 0.85 * math.cos(th) + V[:, 1] * B * 0.85 * math.sin(th)
            p = g * (1 - run) + ring * run
            p2 = cen + V[:, 0] * A * 0.85 * math.cos(th + 0.05) + V[:, 1] * B * 0.85 * math.sin(th + 0.05)
            h = math.atan2(p2[1] - p[1], p2[0] - p[0]) if run >= 1 else math.atan2(ring[1] - g[1], ring[0] - g[0])
            key_pose(ob, f, (p[0], p[1], z), h)
            th_h = th - 0.35
            ph_ = cen + V[:, 0] * A * 0.8 * math.cos(th_h) + V[:, 1] * B * 0.8 * math.sin(th_h)
            key_pose(hunter, f, (ph_[0], ph_[1], z), h)
        unwrap(ob)
        unwrap(hunter)
    if venue_id not in crowds.seats:
        crowds.add_seats(venue_id, fill=0.95)
    crowds.key_fill(venue_id, fb - 12, 0.95, 0.3)
    crowds.key_fill(venue_id, fb + 12, 0.95, 1.0)
    crowds.key_fill(venue_id, fb + 96, 0.95, 0.45)
    return dict(beast_frame=fb, center=(cen[0], cen[1], z))


# ----------------------------------------------------------------------------------------------- fleet arrival
def berths(man, n, clearance=1.7):
    """Free water spots a little off the harbour quays, away from moored/anchored ships and rowboats."""
    m = cine.generator()
    P = cine.poly_resample(np.asarray(m.HARBOR, float), 0.5)
    N = m.polyline_normals(P)
    occupied = [np.array(s['pos'][:2]) for s in man['moorings'] + man['anchored_ships'] + man['boats']]
    T = None
    out = []
    for i in range(0, len(P), 3):
        for d in (2.0, -2.0):
            q = P[i] + N[i] * d
            if m.points_in_poly(np.array([q[0]]), np.array([q[1]]), m.COAST_POLY)[0]:
                continue                                       # that side is land
            if all(np.linalg.norm(q - o) > clearance for o in occupied + out):
                out.append(q)
            break
    hc = np.array(m.HARBOR_CENTER)
    out.sort(key=lambda q: float(np.linalg.norm(q - hc)))
    return out[:n], P, N


def fleet_arrival(man, crowds, ships, f0, f1, n=5, seed=9):
    rng = np.random.default_rng(seed)
    import ships as ships_mod
    lane = ships.lanes['harbour_in']
    targets, _, _ = berths(man, n)
    kinds = ['galley', 'galley', 'merchant2', 'merchant', 'merchant2', 'galley'][:n]
    dur = (f1 - f0) / cine.FPS
    spacing = 3.4
    speed = (lane.L * 0.92 + spacing * n) / (dur * 0.72)
    fleet = []
    for k in range(n):
        tgt = targets[k % len(targets)]
        ob = ships._new_ship(kinds[k], cine.generator().SHIP_SCALE * rng.uniform(0.9, 1.0))
        s_lag = -spacing * k
        h_prev, vis_prev = 0.0, None
        for f in range(f0, f1 + 1, 2):
            t = (f - f0) / cine.FPS
            s = s_lag + speed * t
            vis = s >= 0
            if vis != vis_prev:
                key_visible(ob, f, vis)
                vis_prev = vis
            if s < lane.L * 0.72:
                p, h = lane.at(max(0.0, s))
            else:
                # leave the lane and glide to the berth, slowing down (ease-out)
                p_off, h_off = lane.at(lane.L * 0.72)
                d_rest = float(np.linalg.norm(tgt - p_off))
                u = min(1.0, (s - lane.L * 0.72) / max(1e-6, d_rest * 1.6))
                e = 1 - (1 - u) ** 2
                p = p_off * (1 - e) + tgt * e
                h = math.atan2(tgt[1] - p_off[1], tgt[0] - p_off[0]) if u < 0.97 else h_prev
            h_prev = h
            key_pose(ob, f, (p[0], p[1], 0.0), h)
        ships_mod._unwrap_heading(ob)
        ships.moving.append(ob)
        if kinds[k] == 'galley':
            ships_mod.oar_object(ob, ships.coll, f0, f1, rng.random())
        fleet.append(ob)
    # the quays fill with people come to watch
    paths = crowds_mod.cine_curve("CIN_StreamPaths_quay", _paths_to(man, [t for t in targets], 36), cine.coll("CIN_Crowds"))
    crowds.add_stream("quay_in", paths, 500, 0.0, dur * 0.6)
    for zid in ('harbour_quay', 'market'):
        if zid in crowds.idlers:
            ob = crowds.idlers[zid]
            import gn
            gn.key_input(ob, "Fill", 0.45, f0)
            gn.key_input(ob, "Fill", 1.0, f0 + int((f1 - f0) * 0.7))
    return dict(fleet=fleet, lead=fleet[0])


def _paths_to(man, targets_xy, n_paths, seed=4):
    """Street paths ending on the quay nearest each target (reuses the venue stream machinery)."""
    fake = {'street_graph': man['street_graph'],
            'venues': [{'id': '_quay', 'entrances': []}]}
    N = np.asarray(man['street_graph']['nodes'], float)
    ents = []
    for t in targets_xy:
        i = int(np.argmin(np.linalg.norm(N[:, :2] - t, axis=1)))
        ents.append(N[i].tolist())
    fake['venues'][0]['entrances'] = ents
    import crowds as cm
    ob = cm.stream_paths(fake, '_quay', n_paths=n_paths, seed=seed, name="CIN_tmp_quay")
    polys = [[(p.co[0], p.co[1], p.co[2]) for p in sp.points] for sp in ob.data.splines]
    bpy.data.objects.remove(ob, do_unlink=True)
    return polys


# ----------------------------------------------------------------------------------------------- festival
def festival_night(man, crowds, f0, f1, rows=26, seed=6):
    """Torch-lit procession along the 'procession' route + lanterns strung over the forum."""
    rng = np.random.default_rng(seed)
    cine.clear_coll("CIN_Festival")
    c = cine.coll("CIN_Festival")
    route = np.asarray(man['routes']['procession'], float)
    route = cine.poly_resample(route, 0.2)
    s_arr = cine.arclen(route)
    L = float(s_arr[-1])
    dur = (f1 - f0) / cine.FPS
    speed = 0.16
    torch_mesh = tinted_mesh("CIN_TorchMesh", 'torch_bearer', (0.92, 0.90, 0.86))
    robes = [tinted_mesh("CIN_Robe_%d" % i, 'robed', col) for i, col in enumerate(figures.PALETTE[:6])]
    walkers = []
    for r in range(rows):
        for lane in (-1, 0, 1):
            mesh = torch_mesh if (lane != 0 or r % 4 == 0) else robes[rng.integers(len(robes))]
            ob = obj("CIN_Proc_%02d_%d" % (r, lane + 1), mesh, c)
            walkers.append((ob, r, lane))
    lead0 = min(L * 0.35, speed * dur * 0.3 + 6.0)
    for f in range(f0, f1 + 1, 2):
        t = (f - f0) / cine.FPS
        head = lead0 + speed * t
        for ob, r, lane in walkers:
            s = head - r * 0.17
            if s < 0:
                s = 0.0
            p, h = cine.at_arc(route[:, :2], s_arr, min(s, L - 0.01))
            nrm = np.array([-math.sin(h), math.cos(h)])
            q = p + nrm * lane * 0.075
            z = float(np.interp(s, s_arr, route[:, 2]))
            key_pose(ob, f, (q[0], q[1], z), h, 0.003 * abs(math.sin(t * 9 + r)))
    for ob, *_ in walkers:
        unwrap(ob)
    # flames on the torches glow: an emissive bead per torch bearer, parented
    flame = cine.mat_emit("CIN_TorchFlame", (1.0, 0.6, 0.22), 40.0)
    V, F = cine.octa((0.012, 0.018, 0.135), 0.011)
    fm = bpy.data.meshes.new("CIN_FlameBead")
    fm.from_pydata(V, [], F)
    fm.materials.append(flame)
    for ob, r, lane in walkers:
        if ob.data == torch_mesh:
            fb = obj(ob.name + "_flame", fm, c)
            fb.parent = ob
    # a few real lights travel with the procession
    for k in range(4):
        ld = bpy.data.lights.new("CIN_ProcLight_%d" % k, 'POINT')
        ld.energy, ld.color, ld.shadow_soft_size = 3.5, (1.0, 0.6, 0.25), 0.2
        lo = obj("CIN_ProcLight_%d" % k, ld, c)
        lo.parent = walkers[min(len(walkers) - 1, k * 18)][0]
        lo.location = (0, 0, 0.35)
    # lanterns strung across the forum (catenaries between its colonnades)
    forum = next((z for z in man['spawn_zones'] if z['id'] == 'forum'), None)
    if forum:
        P = np.asarray(forum['poly'])
        xs = np.linspace(P[:, 0].min() + 0.4, P[:, 0].max() - 0.4, 2)
        zbase = float(np.mean([p[2] for p in forum['points']])) + 0.75
        lan = cine.mat_emit("CIN_Lantern", (1.0, 0.45, 0.2), 25.0)
        LV, LF = [], []
        cols = [(1.0, 0.45, 0.2), (1.0, 0.8, 0.35), (0.95, 0.3, 0.25)]
        for y in np.linspace(P[:, 1].min() + 0.5, P[:, 1].max() - 0.5, 7):
            for k in range(14):
                u = k / 13
                x = xs[0] + (xs[1] - xs[0]) * u
                zz = zbase - 0.25 * math.sin(math.pi * u)
                v_, f_ = cine.octa((x, y, zz), 0.03)
                b = len(LV)
                LV += v_
                LF += [tuple(b + i for i in face) for face in f_]
        cine.mesh_object("CIN_Lanterns", LV, LF, c, [lan])
    head = bpy.data.objects.new("CIN_ProcHead", None)
    c.objects.link(head)
    for f in range(f0, f1 + 1, 4):
        t = (f - f0) / cine.FPS
        s = min(L - 0.01, lead0 + speed * t - 1.2)
        p, h = cine.at_arc(route[:, :2], s_arr, s)
        head.location = (p[0], p[1], float(np.interp(s, s_arr, route[:, 2])))
        head.keyframe_insert('location', frame=f)
    return dict(head=head, walkers=[w[0] for w in walkers])


# ----------------------------------------------------------------------------------------------- theatre
def theatre_play(man, crowds, f0, f1, seed=8, venue_id='theatre'):
    v = venue(man, venue_id)
    rng = np.random.default_rng(seed)
    cine.clear_coll("CIN_Play")
    c = cine.coll("CIN_Play")
    stage = np.asarray(v['stage'], float)[:, :2]
    cen = stage.mean(axis=0)
    rad = float(np.linalg.norm(stage - cen, axis=1).max()) * 0.75
    z = v['stage_z']
    chorus = [obj("CIN_Chorus_%d" % k, tinted_mesh("CIN_ChorusMesh", 'robed', (0.92, 0.90, 0.86)), c) for k in range(8)]
    actors = [obj("CIN_Actor_%d" % k, tinted_mesh("CIN_ActorMesh_%d" % k, 'robed', col), c)
              for k, col in enumerate([(0.62, 0.14, 0.12), (0.18, 0.30, 0.62), (0.85, 0.66, 0.28)])]
    focus = np.array(v['center'][:2])
    for f in range(f0, f1 + 1, 2):
        t = (f - f0) / cine.FPS
        for k, ob in enumerate(chorus):
            th = t * 0.35 + 2 * math.pi * k / len(chorus)
            p = cen + np.array([math.cos(th), math.sin(th)]) * rad * 0.8
            key_pose(ob, f, (p[0], p[1], z), th + math.pi / 2, 0.004 * abs(math.sin(t * 6 + k)))
        for k, ob in enumerate(actors):
            beat = int(t / 3.0 + k) % 3
            mark = cen + np.array([math.cos(beat * 2.1 + k), math.sin(beat * 2.1 + k)]) * rad * 0.35
            key_pose(ob, f, (mark[0], mark[1], z), math.atan2(focus[1] - mark[1], focus[0] - mark[0]) + math.pi)
    for ob in chorus + actors:
        unwrap(ob)
    if venue_id not in crowds.seats:
        crowds.add_seats(venue_id, fill=0.9)
    crowds.key_fill(venue_id, f0, 0.9, 0.0)
    crowds.key_fill(venue_id, f1 - 48, 0.9, 0.05)
    crowds.key_fill(venue_id, f1 - 12, 0.9, 0.9)
    return dict(center=(cen[0], cen[1], z))
