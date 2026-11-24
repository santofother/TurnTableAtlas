"""Low-poly cotton clouds drifting on a wind vector, high above the diorama, casting soft shadows."""
import math

import bmesh
import bpy
import numpy as np

import cine


def cloud_mesh(name, rng):
    bm = bmesh.new()
    n = int(rng.integers(5, 9))
    for k in range(n):
        r = rng.uniform(1.4, 3.0)
        off = (rng.uniform(-4.5, 4.5), rng.uniform(-2.2, 2.2), rng.uniform(-0.3, 0.9))
        geom = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
        for v in geom['verts']:
            v.co.x = v.co.x * 1.15 + off[0]
            v.co.y = v.co.y + off[1]
            v.co.z = max(v.co.z * 0.75, -r * 0.35) + off[2]       # flat-ish bottoms
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def setup_clouds(man, f0, f1, count=10, seed=4, wind=(1.0, 0.35), speed=0.55, height=(15.0, 21.0), area=62.0):
    cine.clear_coll("CIN_Clouds")
    c = cine.coll("CIN_Clouds")
    rng = np.random.default_rng(seed)
    mat = bpy.data.materials.get("CIN_Cloud") or bpy.data.materials.new("CIN_Cloud")
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs['Base Color'].default_value = (0.82, 0.82, 0.86, 1.0)
    bs.inputs['Roughness'].default_value = 1.0
    w = np.array(wind, float)
    w /= np.linalg.norm(w)
    dur = (f1 - f0) / cine.FPS
    obs = []
    for i in range(count):
        ob = bpy.data.objects.new("CIN_Cloud_%02d" % i, cloud_mesh("CIN_CloudMesh_%02d" % i, rng))
        ob.data.materials.append(mat)
        c.objects.link(ob)
        p = np.array([rng.uniform(-area, area), rng.uniform(-area, area)]) - w * speed * dur / 2
        z = rng.uniform(*height)
        s = rng.uniform(0.8, 1.35)
        ob.scale = (s, s, s)
        ob.rotation_euler = (0, 0, math.atan2(w[1], w[0]) + rng.uniform(-0.3, 0.3))
        ob.location = (p[0], p[1], z)
        ob.keyframe_insert('location', frame=f0)
        q = p + w * speed * dur
        ob.location = (q[0], q[1], z)
        ob.keyframe_insert('location', frame=f1)
        cine.set_interp(ob, 'LINEAR')
        obs.append(ob)
    return obs
