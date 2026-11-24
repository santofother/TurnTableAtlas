"""Encode a PNG frame folder to H.264 .mp4 with Blender's own FFmpeg (no ffmpeg binary on this Mac).
    $BLENDER -b --factory-startup --python tools/encode.py -- <frames_dir> <out.mp4> [fps]"""
import os
import sys

import bpy

a = sys.argv[sys.argv.index('--') + 1:]
src, out = a[0], a[1]
fps = int(a[2]) if len(a) > 2 else 24
files = sorted(f for f in os.listdir(src) if f.lower().endswith('.png'))
if not files:
    raise SystemExit("[Encode] no frames in %s" % src)
sc = bpy.context.scene
se = sc.sequence_editor_create()
coll = getattr(se, 'strips', None) or se.sequences
st = coll.new_image(name="frames", filepath=os.path.join(src, files[0]), channel=1, frame_start=1)
for f in files[1:]:
    st.elements.append(f)
img = bpy.data.images.load(os.path.join(src, files[0]))
sc.render.resolution_x, sc.render.resolution_y = img.size
sc.render.resolution_percentage = 100
sc.frame_start, sc.frame_end = 1, len(files)
sc.render.fps = fps
r = sc.render
r.image_settings.file_format = 'FFMPEG'
r.ffmpeg.format = 'MPEG4'
r.ffmpeg.codec = 'H264'
r.ffmpeg.constant_rate_factor = 'HIGH'
r.ffmpeg.ffmpeg_preset = 'GOOD'
r.use_sequencer = True
r.filepath = out
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.render.render(animation=True)
# Blender appends the frame range unless the path has an extension it recognises; normalise the name
d = os.path.dirname(out)
for f in os.listdir(d):
    if f.startswith(os.path.basename(out).replace('.mp4', '')) and f.endswith('.mp4') and f != os.path.basename(out):
        os.replace(os.path.join(d, f), out)
print("[Encode] wrote", out, len(files), "frames")
