"""Ships: traffic on the manifest's ship lanes (arrive -> dwell -> leave via `then`), fishing boats circling,
every ship bobbing and rolling (F-curve noise), and galleys rowing (oar banks driven by a shape key)."""
import math

import bpy
import numpy as np

import cine

ROW_PERIOD = 1.6          # seconds per stroke


class Lane:
    def __init__(self, ln):
        self.id, self.ln = ln['id'], ln
        P = np.asarray(ln['points'], float)
        if ln.get('loop'):
            P = np.vstack([P, P[:1]])
        self.P = cine.poly_resample(_smooth(P, closed=ln.get('loop', False)), 0.3)
        self.s = cine.arclen(self.P)
        self.L = float(self.s[-1])
        self.loop = ln.get('loop', False)

    def at(self, s):
        p, h = cine.at_arc(self.P, self.s, s, closed=self.loop)
        p2, _ = cine.at_arc(self.P, self.s, s + 0.9, closed=self.loop)
        if np.linalg.norm(p2 - p) > 1e-6:
            h = math.atan2(p2[1] - p[1], p2[0] - p[0])
        return p, h


def _smooth(P, closed=False, it=2):
    """Chaikin corner cutting so ships turn smoothly."""
    P = np.asarray(P, float)
    for _ in range(it):
        Q = [P[0]] if not closed else []
        for a, b in zip(P[:-1], P[1:]):
            Q += [a * 0.75 + b * 0.25, a * 0.25 + b * 0.75]
        if not closed:
            Q.append(P[-1])
        P = np.asarray(Q)
    return np.vstack([P, P[:1]]) if closed else P


def ship_mesh_for(kind):
    m = cine.generator()
    if kind == 'galley':
        me = bpy.data.meshes.get("CIN_Galley_NoOars")
        if me is None:
            me = m.ship_mesh('galley', oars=False, name="CIN_Galley_NoOars")
            me.materials.append(bpy.data.materials["CAP_Painted"])
        return me
    return bpy.data.meshes.get("CAP_Ship_" + kind)


def oar_object(parent, coll, f0, f1, phase):
    m = cine.generator()
    base = m.galley_oar_bank(0.0)
    fwd = m.galley_oar_bank(1.0)
    me = base.to_mesh("CIN_Oars_%s" % parent.name)
    me.materials.append(bpy.data.materials["CAP_Painted"])
    ob = bpy.data.objects.new("CIN_Oars_%s" % parent.name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.shape_key_add(name="Basis")
    sk = ob.shape_key_add(name="Stroke")
    sk.data.foreach_set('co', np.asarray(fwd.v, np.float32).ravel())
    per = ROW_PERIOD * cine.FPS
    f = f0 - int(phase * per)
    while f <= f1:
        for frac, val in ((0.0, 0.0), (0.55, 1.0)):
            sk.value = val
            sk.keyframe_insert('value', frame=int(f + frac * per))
        f += per
    return ob


class Ships:
    def __init__(self, man, f0, f1, seed=7, time_scale=1.0):
        self.man, self.f0, self.f1 = man, f0, f1
        self.ts = time_scale
        self.rng = np.random.default_rng(seed)
        cine.clear_coll("CIN_Ships")
        self.coll = cine.coll("CIN_Ships")
        self.lanes = {ln['id']: Lane(ln) for ln in man['ship_lanes']}
        self.moving = []

    def sec(self, f):
        return (f - self.f0) / cine.FPS * self.ts

    def _new_ship(self, kind, scale):
        me = ship_mesh_for(kind)
        ob = bpy.data.objects.new("CIN_Ship_%03d_%s" % (len(self.moving), kind), me)
        self.coll.objects.link(ob)
        ob.scale = (scale, scale, scale)
        return ob

    def route_pos(self, lane, t, t0, speed):
        """Position on a lane (and its `then` continuation after dwell) at time t; None if not on the water."""
        s = (t - t0) * speed
        if s < 0:
            return None
        if s <= lane.L:
            return lane.at(s)
        nxt = self.lanes.get(lane.ln.get('then') or '')
        if nxt is None:
            return None
        dwell = lane.ln.get('dwell_s', 0.0)
        t_arr = t0 + lane.L / speed
        if t < t_arr + dwell:
            return lane.at(lane.L - 1e-3)
        s2 = (t - t_arr - dwell) * speed
        if s2 > nxt.L:
            return None
        return nxt.at(s2)

    def traffic(self, density=1.0, step=4, only=None):
        self._placed_boats(step)
        dur = self.sec(self.f1)
        for lid, lane in self.lanes.items():
            if only and lid not in only:
                continue
            ln = lane.ln
            if lane.loop:
                for k in range(2 if density > 0.5 else 1):
                    self._loop_boat(lane, k, step)
                continue
            if ln.get('every_s', 0) <= 0 or any(l.ln.get('then') == lid for l in self.lanes.values()):
                continue                          # continuation lanes are driven by their parent
            every = ln['every_s'] / max(density, 0.05)
            total = lane.L / ln['speed'] + ln.get('dwell_s', 0) + (self.lanes[ln['then']].L / ln['speed'] if ln.get('then') else 0)
            t0 = -total + self.rng.uniform(0, every)
            while t0 < dur:
                self._lane_ship(lane, t0, step)
                t0 += every * self.rng.uniform(0.75, 1.25)

    def _placed_boats(self, step):
        frames = sorted(set(range(self.f0, self.f1 + 1, step)) | {self.f1})
        for key in ('moorings', 'anchored_ships', 'boats'):
            for ship in self.man.get(key, []):
                v = ship.get('voyage')
                ob = bpy.data.objects.get(ship['object'])
                if not v or ob is None:
                    continue
                dwell = v['dwell_s']
                points = np.asarray(v['points'], float)
                if not dwell:
                    points = np.vstack((points, points[0]))
                arcs = cine.arclen(points)
                period = dwell + arcs[-1] / v['speed']
                berth_heading = math.radians(ship['heading_deg'])
                for frame in frames:
                    elapsed = (self.sec(frame) + v['phase_s']) % period
                    p, heading = points[0], berth_heading
                    if elapsed >= dwell:
                        dist = (elapsed - dwell) * v['speed']
                        p, heading = cine.at_arc(points, arcs, dist, closed=not dwell)
                        ahead, _ = cine.at_arc(points, arcs, dist + 0.35, closed=not dwell)
                        behind, _ = cine.at_arc(points, arcs, dist - 0.35, closed=not dwell)
                        delta = ahead - behind
                        if np.linalg.norm(delta) > 1e-6:
                            heading = math.atan2(delta[1], delta[0])
                        if dwell:
                            blend = min(1.0, min(dist, arcs[-1] - dist) / 1.5)
                            heading = berth_heading + math.remainder(heading - berth_heading, math.tau) * blend
                    ob.location = (*p, ship['pos'][2])
                    ob.rotation_euler = (0.0, 0.0, heading)
                    ob.keyframe_insert('location', frame=frame)
                    ob.keyframe_insert('rotation_euler', frame=frame)
                _unwrap_heading(ob)
                cine.set_interp(ob)
                self.moving.append(ob)

    def _lane_ship(self, lane, t0, step, kind=None, speed=None):
        ln = lane.ln
        kind = kind or str(self.rng.choice(ln['kinds']))
        speed = speed or ln['speed'] * self.rng.uniform(0.9, 1.1)
        sc = self.rng.uniform(0.85, 1.0) * cine.generator().SHIP_SCALE
        ob = None
        visible_prev = None
        for f in list(range(self.f0, self.f1 + 1, step)) + [self.f1]:
            r = self.route_pos(lane, self.sec(f), t0, speed)
            vis = r is not None
            if not vis and ob is None:
                continue
            if ob is None:
                ob = self._new_ship(kind, sc)
                if f > self.f0:
                    ob.hide_render = ob.hide_viewport = True
                    ob.keyframe_insert('hide_render', frame=self.f0)
                    ob.keyframe_insert('hide_viewport', frame=self.f0)
            if vis:
                p, h = r
                ob.location = (p[0], p[1], 0.0)
                ob.rotation_euler = (0.0, 0.0, h)
                ob.keyframe_insert('location', frame=f)
                ob.keyframe_insert('rotation_euler', frame=f)
            if vis != visible_prev:
                ob.hide_render = ob.hide_viewport = not vis
                ob.keyframe_insert('hide_render', frame=f)
                ob.keyframe_insert('hide_viewport', frame=f)
                visible_prev = vis
        if ob is not None:
            _unwrap_heading(ob)
            self.moving.append(ob)
            if kind == 'galley':
                oar_object(ob, self.coll, self.f0, self.f1, self.rng.random())
        return ob

    def _loop_boat(self, lane, k, step):
        sc = cine.generator().SHIP_SCALE * 0.9
        ob = self._new_ship('fisher', sc)
        off = lane.L * k / 2 + self.rng.uniform(0, 3)
        spd = lane.ln['speed']
        for f in list(range(self.f0, self.f1 + 1, step)) + [self.f1]:
            p, h = lane.at(off + self.sec(f) * spd)
            ob.location = (p[0], p[1], 0.0)
            ob.rotation_euler = (0.0, 0.0, h)
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('rotation_euler', frame=f)
        _unwrap_heading(ob)
        self.moving.append(ob)

    def bob_all(self):
        """Bobbing/rolling on every ship (static ones get a keyframe first so the noise has a curve to sit on)."""
        ships = [o for o in bpy.data.objects if (o.name.startswith("CAP_Ship_") or o.name.startswith("CIN_Ship_"))
                 and o.type == 'MESH']
        for i, ob in enumerate(ships):
            if ob.animation_data is None or ob.animation_data.action is None:
                ob.keyframe_insert('location', frame=self.f0)
                ob.keyframe_insert('rotation_euler', frame=self.f0)
            small = 'boat' in ob.name or 'fisher' in ob.name
            ph = i * 17.3
            cine.add_noise(ob, 'location', 2, 0.012 if small else 0.018, 22.0, ph)
            cine.add_noise(ob, 'rotation_euler', 0, 0.05 if small else 0.03, 30.0, ph + 5)
            cine.add_noise(ob, 'rotation_euler', 1, 0.025 if small else 0.015, 38.0, ph + 9)
        for o in self.moving:
            for fc in cine.fcurves(o.animation_data.action):
                if fc.data_path.startswith('hide'):
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
        return len(ships)

    def hide_static(self, names):
        for n in names:
            o = bpy.data.objects.get(n)
            if o is not None:
                o.hide_render = o.hide_viewport = True


def _unwrap_heading(ob):
    """Keep rotation Z continuous across +-pi so interpolation never spins the ship the long way round."""
    for fc in cine.fcurves(ob.animation_data.action):
        if fc.data_path == 'rotation_euler' and fc.array_index == 2:
            prev = None
            for kp in fc.keyframe_points:
                v = kp.co[1]
                if prev is not None:
                    while v - prev > math.pi:
                        v -= 2 * math.pi
                    while v - prev < -math.pi:
                        v += 2 * math.pi
                kp.co[1] = v
                kp.handle_left[1] = v
                kp.handle_right[1] = v
                prev = v
            fc.update()
