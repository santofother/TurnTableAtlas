"""Time of day for the cinematic: sun and moon lamps from the shared sun-arc maths, a painted sky that blends
day / golden hour / night (with stars and a moon), window glow, lamps, lighthouse fires and haze.

    tod = TimeOfDay(scene, manifest)          # builds the world + lamps once
    tod.animate(lambda f: hour_at_frame, f0, f1, step=4)   # keyframes everything
"""
import math

import bpy

import cine
import lights
import sunarc
from cine import key_socket, key_value

DAY_SKY = [(0.0, (0.80, 0.84, 0.88)), (0.05, (0.62, 0.74, 0.90)), (0.30, (0.42, 0.60, 0.88)), (1.0, (0.22, 0.40, 0.80))]
DUSK_SKY = [(0.0, (0.99, 0.66, 0.40)), (0.05, (0.97, 0.58, 0.48)), (0.14, (0.74, 0.50, 0.62)),
            (0.30, (0.40, 0.38, 0.64)), (0.60, (0.18, 0.21, 0.46)), (1.0, (0.09, 0.11, 0.30))]
NIGHT_SKY = [(0.0, (0.06, 0.08, 0.15)), (0.15, (0.03, 0.045, 0.10)), (1.0, (0.008, 0.012, 0.035))]


def _n(nt, typ, loc, **kw):
    n = nt.nodes.new(typ)
    n.location = loc
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def _ramp(nt, fac, stops, loc):
    n = _n(nt, 'ShaderNodeValToRGB', loc)
    els = n.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for el, (p, c) in zip(els, stops):
        el.position = p
        el.color = (*[float(v) for v in cine.generator().lin(c)], 1.0)
    nt.links.new(fac, n.inputs['Fac'])
    return n.outputs['Color']


def _mix(nt, fac, a, b, loc, blend='MIX'):
    n = _n(nt, 'ShaderNodeMix', loc)
    n.data_type = 'RGBA'
    n.blend_type = blend
    for sock, val in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
        if isinstance(val, bpy.types.NodeSocket):
            nt.links.new(val, sock)
        else:
            sock.default_value = val
    return n.outputs[2]


def _math(nt, op, a, b, loc, clamp=False):
    n = _n(nt, 'ShaderNodeMath', loc, operation=op)
    n.use_clamp = clamp
    for s, v in ((n.inputs[0], a), (n.inputs[1], b)):
        if isinstance(v, bpy.types.NodeSocket):
            nt.links.new(v, s)
        else:
            s.default_value = v
    return n.outputs[0]


def build_world():
    w = bpy.data.worlds.get("CIN_World") or bpy.data.worlds.new("CIN_World")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    ctl = {}
    for i, nm in enumerate(("Day", "Dusk", "Night")):
        v = _n(nt, 'ShaderNodeValue', (-1400, 600 - 120 * i))
        v.name = v.label = nm
        ctl[nm] = v
    for nm, y in (("SunDir", 200), ("MoonDir", 0)):
        c = _n(nt, 'ShaderNodeCombineXYZ', (-1400, y))
        c.name = c.label = nm
        ctl[nm] = c
    tc = _n(nt, 'ShaderNodeTexCoord', (-1600, -300))
    view = _n(nt, 'ShaderNodeVectorMath', (-1400, -300), operation='NORMALIZE')
    nt.links.new(tc.outputs['Generated'], view.inputs[0])
    sep = _n(nt, 'ShaderNodeSeparateXYZ', (-1200, -300))
    nt.links.new(view.outputs[0], sep.inputs[0])
    up = _math(nt, 'MAXIMUM', sep.outputs['Z'], 0.0, (-1050, -300))
    day = _ramp(nt, up, DAY_SKY, (-850, 400))
    dusk = _ramp(nt, up, DUSK_SKY, (-850, 150))
    night = _ramp(nt, up, NIGHT_SKY, (-850, -100))
    col = _mix(nt, ctl["Day"].outputs[0], night, day, (-500, 200))
    col = _mix(nt, ctl["Dusk"].outputs[0], col, dusk, (-300, 200))
    # sun glow
    dsun = _n(nt, 'ShaderNodeVectorMath', (-1000, -550), operation='DOT_PRODUCT')
    nt.links.new(view.outputs[0], dsun.inputs[0])
    nt.links.new(ctl["SunDir"].outputs[0], dsun.inputs[1])
    g = _math(nt, 'POWER', _math(nt, 'MAXIMUM', dsun.outputs['Value'], 0.0, (-850, -550)), 18.0, (-700, -550))
    disc = _math(nt, 'GREATER_THAN', dsun.outputs['Value'], 0.9993, (-700, -650))
    glow_amt = _math(nt, 'MULTIPLY', _math(nt, 'ADD', g, _math(nt, 'MULTIPLY', disc, 6.0, (-550, -650)), (-450, -600)),
                     _math(nt, 'ADD', ctl["Dusk"].outputs[0], _math(nt, 'MULTIPLY', ctl["Day"].outputs[0], 0.35, (-550, -750)),
                           (-450, -700)), (-300, -600))
    col = _mix(nt, _math(nt, 'MINIMUM', glow_amt, 1.0, (-150, -600)), col, (1.0, 0.62, 0.30, 1.0), (0, 200), 'ADD')
    # stars and moon (camera rays only)
    st = _n(nt, 'ShaderNodeTexVoronoi', (-1000, -900))
    st.inputs['Scale'].default_value = 140.0
    nt.links.new(view.outputs[0], st.inputs['Vector'])
    star = _math(nt, 'LESS_THAN', st.outputs['Distance'], 0.045, (-800, -900))
    star = _math(nt, 'MULTIPLY', star, _math(nt, 'MULTIPLY', ctl["Night"].outputs[0], up, (-800, -1000)), (-650, -950))
    dm = _n(nt, 'ShaderNodeVectorMath', (-1000, -1150), operation='DOT_PRODUCT')
    nt.links.new(view.outputs[0], dm.inputs[0])
    nt.links.new(ctl["MoonDir"].outputs[0], dm.inputs[1])
    moon = _math(nt, 'GREATER_THAN', dm.outputs['Value'], 0.9990, (-800, -1150))
    mglow = _math(nt, 'POWER', _math(nt, 'MAXIMUM', dm.outputs['Value'], 0.0, (-800, -1250)), 60.0, (-650, -1250))
    moon = _math(nt, 'MULTIPLY', _math(nt, 'ADD', _math(nt, 'MULTIPLY', moon, 3.0, (-500, -1150)),
                                       _math(nt, 'MULTIPLY', mglow, 0.25, (-500, -1250)), (-350, -1200)),
                 ctl["Night"].outputs[0], (-200, -1200))
    cam_col = _mix(nt, _math(nt, 'MINIMUM', _math(nt, 'ADD', star, moon, (-100, -1000)), 3.0, (50, -1000)),
                   col, (0.9, 0.92, 1.0, 1.0), (200, -300), 'ADD')
    # lighting rays: same sky, but night ambient is lifted a little so the city reads
    amb = _mix(nt, ctl["Night"].outputs[0], col, (0.035, 0.045, 0.085, 1.0), (200, 100), 'LIGHTEN')
    lp = _n(nt, 'ShaderNodeLightPath', (200, 450))
    fin = _mix(nt, lp.outputs['Is Camera Ray'], amb, cam_col, (450, 200))
    bg = _n(nt, 'ShaderNodeBackground', (650, 200))
    nt.links.new(fin, bg.inputs['Color'])
    bg.name = "Bg"
    out = _n(nt, 'ShaderNodeOutputWorld', (850, 200))
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    bpy.context.scene.world = w
    ctl["Bg"] = bg
    return w, ctl


def bloom(scene, strength=0.55, threshold=1.0):
    """Compositor (Blender 5 node-group API): render layers -> glare (bloom) -> output."""
    ng = bpy.data.node_groups.get("CIN_Compositor") or bpy.data.node_groups.new("CIN_Compositor", "CompositorNodeTree")
    ng.nodes.clear()
    if not ng.interface.items_tree:
        ng.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new('CompositorNodeRLayers')
    gl = ng.nodes.new('CompositorNodeGlare')
    for val in ('Bloom', 'BLOOM'):
        try:
            gl.inputs['Type'].default_value = val
            break
        except Exception:
            pass
    gl.inputs['Threshold'].default_value = threshold
    gl.inputs['Strength'].default_value = strength
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
    ng.links.new(gl.outputs['Image'], out.inputs[0])
    scene.compositing_node_group = ng
    try:
        scene.render.use_compositing = True
    except Exception:
        pass
    return ng


class TimeOfDay:
    def __init__(self, scene, man, day_of_year=None, latitude=None, north_offset=None):
        self.scene, self.man = scene, man
        s = man['sun']
        self.lat = s['latitude_deg'] if latitude is None else latitude
        self.doy = s['default_day_of_year'] if day_of_year is None else day_of_year
        self.north = s.get('north_offset_deg', 0.0) if north_offset is None else north_offset
        self.world, self.ctl = build_world()
        self.sun = bpy.data.objects.get("CAP_Sun")
        if self.sun is None:
            ld = bpy.data.lights.new("CAP_Sun", 'SUN')
            self.sun = bpy.data.objects.new("CAP_Sun", ld)
            scene.collection.objects.link(self.sun)
        self.sun.data.angle = math.radians(1.5)
        md = bpy.data.lights.get("CIN_Moon") or bpy.data.lights.new("CIN_Moon", 'SUN')
        self.moon = bpy.data.objects.get("CIN_Moon") or bpy.data.objects.new("CIN_Moon", md)
        if self.moon.name not in scene.collection.objects:
            scene.collection.objects.link(self.moon)
        md.color = (0.62, 0.72, 1.0)
        md.angle = math.radians(2.0)
        pm = bpy.data.materials.get("CAP_Painted")
        self.night_node = pm.node_tree.nodes.get("NightLevel") if pm else None
        ng = bpy.data.node_groups.get("CAP_Haze")
        self.haze = ng.nodes.get("HazeAmount") if ng else None
        fm = bpy.data.materials.get("CAP_Fire")
        self.fire = None
        if fm:
            for n in fm.node_tree.nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    self.fire = n.inputs['Emission Strength']
        self.lamps = lights.NightLights(scene, man)
        bloom(scene)

    def state(self, hour):
        el, az = sunarc.sun_position(self.lat, self.doy, hour, self.north)
        d = sunarc.sun_direction(self.lat, self.doy, hour, self.north)
        md = sunarc.sun_direction(self.lat, (self.doy + 182) % 365 + 1, (hour + 12.4) % 24, self.north)
        day, dusk = sunarc.daylight(el), sunarc.dusk(el)
        warm = cine.smoothstep(2.0, 35.0, el)
        return dict(el=el, az=az, dir=d, moon=md, day=day, dusk=dusk, night=1.0 - cine.smoothstep(-10.0, 1.0, el),
                    win=sunarc.window_level(el, hour), lamp=sunarc.night_level(el),
                    sun_energy=4.6 * cine.smoothstep(-3.0, 9.0, el),
                    sun_color=(1.0, 0.55 + 0.38 * warm, 0.30 + 0.55 * warm),
                    moon_energy=0.2 * (1.0 - cine.smoothstep(-8.0, 2.0, el)) * cine.smoothstep(-0.05, 0.25, md[2]))

    def key(self, frame, hour):
        from mathutils import Vector
        st = self.state(hour)
        sd = Vector(st['dir'])
        self.sun.rotation_euler = (-sd).to_track_quat('-Z', 'Y').to_euler()
        self.sun.keyframe_insert('rotation_euler', frame=frame)
        key_value(self.sun.data, 'energy', st['sun_energy'], frame)
        key_value(self.sun.data, 'color', st['sun_color'], frame)
        mdv = Vector(st['moon'])
        self.moon.rotation_euler = (-mdv).to_track_quat('-Z', 'Y').to_euler()
        self.moon.keyframe_insert('rotation_euler', frame=frame)
        key_value(self.moon.data, 'energy', st['moon_energy'], frame)
        for nm in ("Day", "Dusk", "Night"):
            key_socket(self.ctl[nm].outputs[0], st[nm.lower()], frame)
        for i in range(3):
            key_socket(self.ctl["SunDir"].inputs[i], st['dir'][i], frame)
            key_socket(self.ctl["MoonDir"].inputs[i], st['moon'][i], frame)
        if self.night_node is not None:
            key_socket(self.night_node.outputs[0], st['win'], frame)
        if self.haze is not None:
            key_socket(self.haze.outputs[0], 0.15 + 0.85 * max(st['day'], st['dusk'] * 0.8), frame)
        if self.fire is not None:
            key_socket(self.fire, 4.0 + 30.0 * st['lamp'], frame)
        self.lamps.key(frame, st)
        return st

    def animate(self, hour_fn, f0, f1, step=4):
        for f in list(range(f0, f1 + 1, step)) + ([f1] if (f1 - f0) % step else []):
            self.key(f, hour_fn(f))
        for idb in (self.sun, self.sun.data, self.moon, self.moon.data, self.world.node_tree,
                    bpy.data.materials.get("CAP_Painted").node_tree, bpy.data.node_groups.get("CAP_Haze")):
            cine.set_interp(idb, 'LINEAR')
        self.lamps.finish()

    def fixed(self, hour, frame=1):
        return self.key(frame, hour)
