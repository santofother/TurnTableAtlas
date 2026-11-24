"""Night lights from the manifest: emissive lamp/torch beads (one mesh) plus a handful of real point lights
(lighthouses, gate torches) that flicker. Windows are lit by the CAP_Painted NightLevel (see sky.py)."""
import math

import bpy

import cine


class NightLights:
    def __init__(self, scene, man):
        cine.clear_coll("CIN_NightLights")
        self.coll = cine.coll("CIN_NightLights")
        V, F = [], []
        for l in man['night_lights']:
            if l['kind'] not in ('lamp', 'torch'):
                continue
            v, f = cine.octa(l['pos'], 0.035 if l['kind'] == 'lamp' else 0.05)
            b = len(V)
            V += v
            F += [tuple(b + i for i in face) for face in f]
        self.mat = cine.mat_emit("CIN_LampGlow", (1.0, 0.58, 0.22), 0.0)
        self.bead = cine.mesh_object("CIN_LampBeads", V, F, self.coll, [self.mat])
        self.strength = self.mat.node_tree.nodes['Emission'].inputs['Strength']
        self.points = []
        for l in man['night_lights']:
            if l['kind'] == 'lighthouse' or (l['kind'] == 'torch' and l['strength'] >= 0.8):
                ld = bpy.data.lights.new("CIN_Fire_%d" % len(self.points), 'POINT')
                ld.color = (1.0, 0.55, 0.22)
                ld.shadow_soft_size = 0.12
                ob = bpy.data.objects.new(ld.name, ld)
                ob.location = l['pos']
                self.coll.objects.link(ob)
                self.points.append((ob, 70.0 if l['kind'] == 'lighthouse' else 6.0))
        for o in bpy.data.objects:                       # the generator's own lighthouse lights are replaced
            if o.name.startswith("CAP_LighthouseFire_"):
                o.hide_render = True

    def key(self, frame, st):
        cine.key_socket(self.strength, 28.0 * st['lamp'], frame)
        for ob, e in self.points:
            cine.key_value(ob.data, 'energy', e * (0.06 + st['lamp']), frame)

    def finish(self):
        cine.set_interp(self.mat.node_tree, 'LINEAR')
        for i, (ob, e) in enumerate(self.points):
            cine.set_interp(ob.data, 'LINEAR')
            cine.add_noise(ob.data, 'energy', 0, e * 0.25, 2.5, phase=i * 13.0)
