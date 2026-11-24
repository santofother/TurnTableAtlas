"""Cinematic entry point (run inside Blender on a generated city .blend):

    $BLENDER -b blender/<city>.blend --python blender/cinematic/run.py -- <command> [options]

Commands
    tod_stills  --hours 6,12,19,22 [--cam CAP_Cam_Hero]          stills at several times of day (S3 check)
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


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    o = opts(argv)
    o.setdefault('city', os.path.splitext(os.path.basename(bpy.data.filepath))[0])
    o.setdefault('out', os.path.join(cine.ROOT, 'blender', 'renders', 'scratch'))
    if o['cmd'] == 'tod_stills':
        tod_stills(o)
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
