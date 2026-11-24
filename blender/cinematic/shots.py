"""The shot list. Each shot is built from scratch on the generated city .blend from city.json - nothing is
hand-keyframed - then rendered to blender/renders/<shot>/frames/ and encoded to blender/renders/<shot>/<shot>.mp4.

    $BLENDER -b blender/<city>.blend --python blender/cinematic/run.py -- shot <name> [--preview] [--frames a:b]
"""
import math
import os

import bpy
import numpy as np

import anchors_cam
import cine
import clouds
import crowds as crowds_mod
import events
import ships as ships_mod
import sky
import venues

SHOTS = {
    'hero_turntable': dict(seconds=20, hour=18.75, clouds=4, cloud_height=(33.0, 37.0),
                           cam=dict(kind='orbit', center=(1.0, -2.0, 1.5), radius=92.0,
                                                          height=40.0, deg=360.0, start_deg=-90.0, lens=35),
                           note="360-degree orbit of the whole diorama at golden hour"),
    'day_night_timelapse': dict(seconds=20, hours=(14.5, 23.8), ship_time_scale=8.0, cloud_speed=3.0,
                                cam=dict(kind='fixed', name='CAP_Cam_Hero', push=0.06),
                                note="hero angle, afternoon to midnight: lamps come on in a wave, streets empty"),
    'fleet_arrival': dict(seconds=22, hour=9.6, event='fleet_arrival',
                          cam=dict(kind='dolly', a=(-16.0, -44.0, 13.0), b=(-9.0, -33.0, 9.5),
                                   ta=(3.0, -22.0, 0.5), tb=(1.5, -10.0, 0.5), lens=32),
                          note="a fleet enters between the lighthouses and moors; the quays fill with people"),
    'colosseum_games': dict(seconds=26, hour=15.4, event='gladiator_games', venue_fill=('colosseum', 0.0, 9.0),
                            cam=dict(kind='orbit', center='colosseum', radius=11.5, height=7.5, deg=75.0,
                                     start_deg=-120.0, lens=30),
                            note="the crowd streams in and fills the colosseum, then games and a beast hunt"),
    'hippodrome_race': dict(seconds=24, hour=16.6, event='chariot_race',
                            cam=dict(kind='follow', target='CIN_RaceLeader', offset=(3.8, -8.2, 7.0), smooth=0.05,
                                     lens=30),
                            note="six chariots, two laps, the crowd roaring at the finish"),
    'festival_night': dict(seconds=22, hour=21.4, event='festival_night',
                           cam=dict(kind='follow', target='CIN_ProcHead', offset=(-6.0, -12.0, 16.0), smooth=0.025,
                                    lens=32),
                           note="torch-lit procession through the streets to the lantern-hung forum"),
    'theatre_play': dict(seconds=12, hour=18.3, event='theatre_play',
                         cam=dict(kind='orbit', center='theatre', radius=8.5, height=6.0, deg=35.0, start_deg=-80.0,
                                  lens=32),
                         note="a play in the theatre, applause at the end"),
    'top_map': dict(seconds=10, hours=(10.0, 18.8), haze=0.0, ship_time_scale=6.0, cloud_speed=2.0, clouds=4,
                    cam=dict(kind='fixed', name='CAP_Cam_TopMap'),
                    note="top-down map view (matches the Atlas world map), day to dusk"),
}


def venue_center(man, vid):
    v = next(v for v in man['venues'] if v['id'] == vid)
    z = float(np.mean([t['ring'][0][2] for t in v['seat_tiers']]))
    return (v['center'][0], v['center'][1], z - 0.6)


def make_camera(name, lens):
    ob = bpy.data.objects.get(name)
    if ob is None:
        cd = bpy.data.cameras.new(name)
        ob = bpy.data.objects.new(name, cd)
        bpy.context.scene.collection.objects.link(ob)
    ob.data.lens = lens
    ob.data.clip_start, ob.data.clip_end = 0.1, 1000.0
    return ob


def track_to(cam, target):
    con = cam.constraints.new('TRACK_TO')
    con.target = target
    con.track_axis, con.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'
    return con


def rig_camera(man, spec, f0, f1, ev):
    k = spec['kind']
    if k == 'fixed':
        cam = bpy.data.objects[spec['name']]
        if spec.get('push'):
            tgt = (3.0, 2.0, 1.5)
            a = np.array(cam.location)
            b = a + (np.array(tgt) - a) * spec['push']
            cam.location = a
            cam.keyframe_insert('location', frame=f0)
            cam.location = b
            cam.keyframe_insert('location', frame=f1)
        return cam
    cam = make_camera("CIN_ShotCam", spec.get('lens', 35))
    cam.constraints.clear()
    tgt = bpy.data.objects.get("CIN_CamTarget") or bpy.data.objects.new("CIN_CamTarget", None)
    if tgt.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(tgt)
    if k == 'orbit':
        c = spec['center']
        c = venue_center(man, c) if isinstance(c, str) else c
        tgt.location = c
        a0 = math.radians(spec.get('start_deg', 0.0))
        for f in range(f0, f1 + 1, 2):
            u = (f - f0) / max(1, f1 - f0)
            a = a0 + math.radians(spec['deg']) * u
            cam.location = (c[0] + spec['radius'] * math.cos(a), c[1] + spec['radius'] * math.sin(a), c[2] + spec['height'])
            cam.keyframe_insert('location', frame=f)
    elif k == 'dolly':
        for f, pos, t in ((f0, spec['a'], spec['ta']), (f1, spec['b'], spec['tb'])):
            cam.location = pos
            cam.keyframe_insert('location', frame=f)
            tgt.location = t
            tgt.keyframe_insert('location', frame=f)
        for idb in (cam, tgt):
            for fc in cine.fcurves(idb.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'
                    kp.easing = 'EASE_IN_OUT'
    elif k == 'follow':
        src = bpy.data.objects[spec['target']]
        off = np.array(spec['offset'])
        sm = None
        smt = None
        for f in range(f0, f1 + 1):
            bpy.context.scene.frame_set(f)
            p = np.array(src.matrix_world.translation)
            sm = p if sm is None else sm + (p - sm) * spec.get('smooth', 0.05)
            smt = p if smt is None else smt + (p - smt) * spec.get('smooth', 0.05) * 2
            if f % 2 == 0 or f in (f0, f1):
                cam.location = tuple(sm + off)
                cam.keyframe_insert('location', frame=f)
                tgt.location = tuple(smt)
                tgt.keyframe_insert('location', frame=f)
    track_to(cam, tgt)
    return cam


def build(name, man, preview=False):
    spec = SHOTS[name]
    scene = bpy.context.scene
    f0, f1 = 1, int(spec['seconds'] * cine.FPS)
    scene.frame_start, scene.frame_end = f0, f1
    scene.render.fps = cine.FPS
    # time of day
    tod = sky.TimeOfDay(scene, man)
    if 'hours' in spec:
        h0, h1 = spec['hours']
        tod.animate(lambda f: h0 + (h1 - h0) * (f - f0) / (f1 - f0), f0, f1, step=3)
        hour_of = lambda f: h0 + (h1 - h0) * (f - f0) / (f1 - f0)  # noqa: E731
    else:
        h = spec['hour']
        tod.animate(lambda f: h, f0, f1, step=f1 - f0)
        hour_of = lambda f: h  # noqa: E731
    if spec.get('haze') is not None and tod.haze is not None:
        tod.haze.outputs[0].default_value = spec['haze']
        ad = bpy.data.node_groups["CAP_Haze"].animation_data
        if ad is not None:
            ad.action = None
    # clouds, ships, people
    clouds.setup_clouds(man, f0, f1, count=spec.get('clouds', 10), speed=0.55 * spec.get('cloud_speed', 1.0),
                        height=spec.get('cloud_height', (15.0, 21.0)))
    import extras
    h_mid = spec.get('hour', sum(spec.get('hours', (12, 12))) / 2)
    extras.add(man, f0, f1, daylight=6.0 < h_mid < 20.0)
    sh = ships_mod.Ships(man, f0, f1, time_scale=spec.get('ship_time_scale', 1.0))
    if spec.get('event') != 'fleet_arrival':
        sh.traffic()
    else:
        sh.traffic(only=['coast_south', 'coast_east', 'fishing_west', 'fishing_east'])
    cr = crowds_mod.Crowds(man)
    cr.add_walkers(900 if preview else 1500)
    cr.add_idlers()
    for f in range(f0, f1 + 1, 24 if 'hours' in spec else f1):
        cr.key_density(f, hour_of(f))
    ev = {}
    e = spec.get('event')
    if spec.get('venue_fill'):
        vid, s_open, s_full = spec['venue_fill']
        vl = venues.VenueLife(cr, man, vid, stream_count=500)
        vl.schedule(cine.frame_of(s_open), cine.frame_of(s_full), base_fill=0.25)
    if e == 'gladiator_games':
        g0 = cine.frame_of(spec['venue_fill'][2] - 1.0) if spec.get('venue_fill') else f0
        ev = events.gladiator_games(man, cr, g0, f1)
    elif e == 'chariot_race':
        ev = events.chariot_race(man, cr, f0, f1)
    elif e == 'fleet_arrival':
        ev = events.fleet_arrival(man, cr, sh, f0, f1)
    elif e == 'festival_night':
        ev = events.festival_night(man, cr, f0, f1)
    elif e == 'theatre_play':
        ev = events.theatre_play(man, cr, f0, f1)
    sh.bob_all()
    cam = rig_camera(man, spec['cam'], f0, f1, ev)
    scene.camera = cam
    # render settings
    r = scene.render
    r.resolution_x, r.resolution_y = (960, 540) if preview else (1920, 1080)
    r.resolution_percentage = 100
    scene.eevee.taa_render_samples = 12 if preview else 32
    r.use_motion_blur = not preview
    r.image_settings.file_format = 'PNG'
    return f0, f1


def render(name, man, preview=False, frames=None):
    f0, f1 = build(name, man, preview)
    scene = bpy.context.scene
    if frames:
        a, b = (int(x) for x in frames.split(':'))
        scene.frame_start, scene.frame_end = max(f0, a), min(f1, b)
    sub = 'preview' if preview else 'frames'
    out = os.path.join(cine.ROOT, 'blender', 'renders', name, sub)
    os.makedirs(out, exist_ok=True)
    scene.render.filepath = os.path.join(out, '')
    print("[Cine] rendering %s %d..%d -> %s" % (name, scene.frame_start, scene.frame_end, out), flush=True)
    bpy.ops.render.render(animation=True)
    return out


def main(o):
    if o['cmd'] == 'list':
        for k, v in SHOTS.items():
            print("[Cine] %-22s %4.0fs  %s" % (k, v['seconds'], v['note']))
        return
    name = o['args'][0]
    man = cine.load_manifest(o['city'])
    render(name, man, preview=bool(o.get('preview')), frames=o.get('frames'))
