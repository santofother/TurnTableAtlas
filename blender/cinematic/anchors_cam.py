"""Cameras from the manifest's landmark presets (same convention as the Atlas: yaw CCW from +X, pitch up)."""
import math

import bpy

import cine


def cam_position(c):
    y, p = math.radians(c['yaw']), math.radians(c['pitch'])
    t = c['target']
    return (t[0] + c['dist'] * math.cos(p) * math.cos(y), t[1] + c['dist'] * math.cos(p) * math.sin(y),
            t[2] + c['dist'] * math.sin(p))


def camera_for(man, lm_id, lens=35, dist_scale=1.0):
    lm = next(l for l in man['landmarks'] if l['id'] == lm_id)
    c = dict(lm['camera'])
    c['dist'] *= dist_scale
    name = "CIN_Cam_" + lm_id
    ob = bpy.data.objects.get(name)
    if ob is None:
        cd = bpy.data.cameras.new(name)
        cd.clip_start, cd.clip_end = 0.1, 1000
        ob = bpy.data.objects.new(name, cd)
        bpy.context.scene.collection.objects.link(ob)
    ob.data.lens = lens
    ob.location = cam_position(c)
    cine.look_at(ob, c['target'])
    return ob
