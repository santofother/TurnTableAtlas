"""Cinematic entry point (run inside Blender on a generated city .blend):

    $BLENDER -b blender/<city>.blend --python blender/cinematic/run.py -- <command> [options]

Commands
    tod_stills  --hours 6,12,19,22 [--cam CAP_Cam_Hero]          stills at several times of day (S3 check)
    landmark_stills --ids a,b,c [--hour 16] [--lens 30]          stills from the manifest's landmark presets
    shot <name> [--preview] [--frames a:b]                       render one shot from shots.SHOTS (S5)
    list                                                         list the shots
Common options: --city <id> (default: from the .blend name), --out <dir>, --res WxH, --samples N
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import cine  # noqa: E402


def opts(argv):
    o = {'cmd': argv[0] if argv else 'list', 'args': []}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a.startswith('--'):
            if i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                o[a[2:]] = argv[i + 1]
                i += 2
            else:
                o[a[2:]] = True
                i += 1
        else:
            o['args'].append(a)
            i += 1
    return o


def setup_render(scene, res, samples):
    w, h = (int(v) for v in res.split('x'))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = int(samples)
    scene.render.fps = cine.FPS
    scene.render.image_settings.file_format = 'PNG'


def tod_stills(o):
    import clouds
    import sky
    scene = bpy.context.scene
    man = cine.load_manifest(o['city'])
    setup_render(scene, o.get('res', '960x480'), o.get('samples', 16))
    tod = sky.TimeOfDay(scene, man)
    hours = [float(h) for h in o.get('hours', '6.3,12,18.9,22').split(',')]
    clouds.setup_clouds(man, 1, 1 + len(hours))
    scene.camera = bpy.data.objects[o.get('cam', 'CAP_Cam_Hero')]
    os.makedirs(o['out'], exist_ok=True)
    for i, h in enumerate(hours):
        f = i + 1
        tod.key(f, h)
    for i, h in enumerate(hours):
        scene.frame_set(i + 1)
        scene.render.filepath = os.path.join(o['out'], "tod_%05.2f.png" % h)
        bpy.ops.render.render(write_still=True)
        print("[Cine] still", h, scene.render.filepath)


def life_stills(o):
    """S4 check: ships on lanes + bobbing, walkers/idlers, a venue filling; stills from several cameras."""
    import crowds
    import ships
    import sky
    import venues
    scene = bpy.context.scene
    man = cine.load_manifest(o['city'])
    setup_render(scene, o.get('res', '960x540'), o.get('samples', 16))
    f0, f1 = 1, int(o.get('frames', 480))
    scene.frame_start, scene.frame_end = f0, f1
    tod = sky.TimeOfDay(scene, man)
    hour = float(o.get('hour', 11.0))
    tod.animate(lambda f: hour, f0, f1, step=f1)
    sh = ships.Ships(man, f0, f1)
    sh.traffic()
    n = sh.bob_all()
    c = crowds.Crowds(man)
    c.add_walkers(int(o.get('walkers', 1400)))
    c.add_idlers()
    c.key_density(f0, hour)
    vl = venues.VenueLife(c, man, o.get('venue', 'colosseum'))
    vl.schedule(f0 + 24, f1 - 48)
    print("[Cine] ships moving", len(sh.moving), "bobbing", n)
    os.makedirs(o['out'], exist_ok=True)
    cams = o.get('cams', 'CAP_Cam_Harbour').split(',')
    for fr in [int(x) for x in o.get('at', '240').split(',')]:
        scene.frame_set(fr)
        for cam in cams:
            ob = bpy.data.objects.get(cam)
            if ob is None:
                ob = _landmark_cam(man, cam)
            scene.camera = ob
            scene.render.filepath = os.path.join(o['out'], "life_%s_f%04d.png" % (cam, fr))
            bpy.ops.render.render(write_still=True)
            print("[Cine] still", scene.render.filepath)


def landmark_stills(o):
    """Stills from the manifest's landmark cameras (the same presets the Atlas flies to), no crowds or ships."""
    import anchors_cam
    import clouds
    import sky
    scene = bpy.context.scene
    man = cine.load_manifest(o['city'])
    setup_render(scene, o.get('res', '1600x800'), o.get('samples', 24))
    tod = sky.TimeOfDay(scene, man)
    tod.animate(lambda f: float(o.get('hour', 16.0)), 1, 2, step=1)
    if o.get('clouds'):
        clouds.setup_clouds(man, 1, 2, count=int(o['clouds']), height=(60.0, 70.0))
    scene.frame_set(1)
    ids = o.get('ids', ','.join(l['id'] for l in man['landmarks'])).split(',')
    os.makedirs(o['out'], exist_ok=True)
    for lid in ids:
        scene.camera = anchors_cam.camera_for(man, lid, float(o.get('lens', 30)))
        scene.camera.data.clip_end = 2000.0
        scene.render.filepath = os.path.join(o['out'], "%s_%s.png" % (o['city'], lid))
        bpy.ops.render.render(write_still=True)
        print("[Cine] still", scene.render.filepath, flush=True)


def _landmark_cam(man, lm_id, lens=35):
    import anchors_cam
    return anchors_cam.camera_for(man, lm_id, lens)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    o = opts(argv)
    o.setdefault('city', os.path.splitext(os.path.basename(bpy.data.filepath))[0])
    o.setdefault('out', os.path.join(cine.ROOT, 'blender', 'renders', 'scratch'))
    if o['cmd'] == 'tod_stills':
        tod_stills(o)
    elif o['cmd'] == 'life_stills':
        life_stills(o)
    elif o['cmd'] == 'landmark_stills':
        landmark_stills(o)
    elif o['cmd'] in ('shot', 'list'):
        import shots
        shots.main(o)
    else:
        raise SystemExit("unknown command %s" % o['cmd'])
    print("[Cine] OK")


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print("[Cine] FAILED")
        sys.exit(1)
