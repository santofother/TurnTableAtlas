"""Shared helpers for the cinematic scripts: paths, the manifest, keyframing, small mesh builders.

Every cinematic module is driven by cities/<id>/city.json and the generated blender/<id>.blend, so a regenerated
city (or a different one) re-renders with no hand edits. Units: model metres, +X east, +Y north, +Z up.
"""
import json
import math
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (os.path.join(ROOT, "generator"), os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

import sunarc  # noqa: E402

FPS = 24


CITY_ID = None


def load_manifest(city_id):
    global CITY_ID
    CITY_ID = city_id
    with open(os.path.join(ROOT, "cities", city_id, "city.json")) as f:
        return json.load(f)


_applied = None


def generator():
    """The generator module, with the current city's layout applied (harbour, ship scale, ...)."""
    global _applied
    import fantasy_capital
    if CITY_ID and _applied != CITY_ID:
        cfg_path = os.path.join(ROOT, "generator", "cities", CITY_ID + ".json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                fantasy_capital.apply_config(json.load(f))
        _applied = CITY_ID
    return fantasy_capital


def coll(name, parent=None, hide_render=False):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    c.hide_render = hide_render
    return c


def clear_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        return
    for o in list(c.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for ch in list(c.children_recursive):
        bpy.data.collections.remove(ch)


def key_value(socket_owner, attr, value, frame):
    setattr(socket_owner, attr, value)
    socket_owner.keyframe_insert(attr, frame=frame)


def key_socket(sock, value, frame):
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=frame)


def set_interp(idblock, interp='LINEAR'):
    ad = getattr(idblock, "animation_data", None)
    if ad is None or ad.action is None:
        return
    for fc in fcurves(ad.action):
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def fcurves(action):
    """F-curves of an action (Blender 5 layered actions keep them in channelbags)."""
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                out += list(cb.fcurves)
    return out


def add_noise(idblock, data_path, index, strength, scale, phase=0.0):
    ad = idblock.animation_data
    if ad is None or ad.action is None:
        return
    for fc in fcurves(ad.action):
        if fc.data_path == data_path and fc.array_index == index:
            mod = fc.modifiers.new('NOISE')
            mod.strength = strength
            mod.scale = scale
            mod.phase = phase
            return mod


def mat_emit(name, color, strength=10.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color, 1.0)
    em.inputs['Strength'].default_value = strength
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m


def mat_principled(name, color, rough=0.8, emission=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs['Base Color'].default_value = (*color, 1.0)
    bs.inputs['Roughness'].default_value = rough
    if emission:
        bs.inputs['Emission Color'].default_value = (*emission[0], 1.0)
        bs.inputs['Emission Strength'].default_value = emission[1]
    return m


def mesh_object(name, verts, faces, coll_, mats=(), colors=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if colors is not None:
        a = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        lt = np.fromiter((len(f) for f in faces), dtype=np.int64, count=len(faces))
        rgba = np.repeat(np.asarray(colors, np.float32), lt, axis=0)
        a.data.foreach_set('color', rgba.ravel())
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll_.objects.link(ob)
    return ob


def octa(center, r):
    x, y, z = center
    V = [(x + r, y, z), (x - r, y, z), (x, y + r, z), (x, y - r, z), (x, y, z + r), (x, y, z - r)]
    F = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    return V, F


def look_at(ob, target):
    from mathutils import Vector
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def poly_resample(P, step):
    P = np.asarray(P, float)
    out = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        n = max(1, int(round(np.linalg.norm(b[:2] - a[:2]) / step)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return np.array(out)


def arclen(P):
    P = np.asarray(P, float)
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1))])


def at_arc(P, s_arr, s, closed=False):
    """Point and heading (rad, CCW from +X) at arc length s along a polyline."""
    if closed:
        s = s % s_arr[-1]
    s = min(max(s, 0.0), s_arr[-1])
    i = int(np.clip(np.searchsorted(s_arr, s) - 1, 0, len(P) - 2))
    t = (s - s_arr[i]) / max(1e-9, s_arr[i + 1] - s_arr[i])
    p = P[i] + (P[i + 1] - P[i]) * t
    d = P[i + 1] - P[i]
    return p, math.atan2(d[1], d[0])


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def frame_of(sec, f0=1):
    return int(round(f0 + sec * FPS))
