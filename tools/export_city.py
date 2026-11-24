"""Export a generated city (already built in this Blender session) to its Atlas package:

    cities/<id>/city.glb            meshes by category/chunk; vertex colours as COLOR_0 (alpha = window order);
                                    terrain has a planar UV for the baked albedo; ship meshes shared by kind
    cities/<id>/proxies.glb         low-poly terrain + building/wall boxes for collision and picking
    cities/<id>/terrain_albedo.png  the procedural terrain material baked top-down (Cycles, 2048 px)
    cities/<id>/thumb.png           small golden-hour hero render for the map pin / loading screen
    atlas/assets/props.glb          shared figures / chariot / beast props (generator/figures.py)

Called by generator/build_city.py --export (tools/build_city.sh does that by default).
"""
import math
import os
import sys
import time

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "generator"))

SKIP_PREFIX = ("CAP_Steam", "CAP_LighthouseFire", "CAP_Sun", "CAP_Cam")


def log(*a):
    print("[Export]", *a, flush=True)


def select_only(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.hide_set(False)
        o.hide_select = False
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def unhide_collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        return []
    c.hide_viewport = False
    c.hide_render = False
    lc = find_layer_collection(bpy.context.view_layer.layer_collection, name)
    if lc is not None:
        lc.exclude = False
        lc.hide_viewport = False
    return list(c.all_objects)


def find_layer_collection(lc, name):
    if lc.name == name:
        return lc
    for ch in lc.children:
        r = find_layer_collection(ch, name)
        if r is not None:
            return r
    return None


def gltf(path, objs):
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_vertex_color='NAME', export_vertex_color_name='Col',
                              export_all_vertex_colors=False, export_materials='EXPORT', export_cameras=False,
                              export_lights=False, export_extras=True, export_image_format='NONE',
                              export_normals=True)
    log("wrote", os.path.relpath(path, ROOT), "%.1f MB" % (os.path.getsize(path) / 1e6), "(%d objects)" % len(objs))


def prepare_sea_and_terrain():
    sea = bpy.data.objects.get("CAP_Sea")
    if sea is not None and 'Col' not in sea.data.color_attributes:
        d = np.empty(len(sea.data.vertices), np.float32)
        sea.data.attributes['depth'].data.foreach_get('value', d)
        a = sea.data.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
        rgba = np.ones((len(d), 4), np.float32)
        rgba[:, 0] = d
        a.data.foreach_set('color', rgba.ravel())
    ter = bpy.data.objects.get("CAP_Terrain")
    if ter is not None and not ter.data.uv_layers:
        uv = ter.data.uv_layers.new(name="UVMap")
        co = np.empty(len(ter.data.vertices) * 3, np.float32)
        ter.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        lv = np.empty(len(ter.data.loops), np.int32)
        ter.data.loops.foreach_get('vertex_index', lv)
        half = 50.0
        u = (co[lv, 0] + half) / (2 * half)
        v = (co[lv, 1] + half) / (2 * half)
        uv.data.foreach_set('uv', np.column_stack([u, v]).astype(np.float32).ravel())
    return ter


def bake_terrain(ter, path, size=2048, samples=4):
    t0 = time.time()
    scene = bpy.context.scene
    prev_engine = scene.render.engine
    scene.render.engine = 'CYCLES'
    try:
        scene.cycles.device = 'GPU'
    except Exception:
        pass
    scene.cycles.samples = samples
    ng = bpy.data.node_groups.get("CAP_Haze")
    if ng is not None and "HazeAmount" in ng.nodes:
        ng.nodes["HazeAmount"].outputs[0].default_value = 0.0
    img = bpy.data.images.new("CAP_TerrainAlbedo", size, size, alpha=False)
    mat = ter.data.materials[0]
    nt = mat.node_tree
    tn = nt.nodes.new('ShaderNodeTexImage')
    tn.image = img
    nt.nodes.active = tn
    select_only([ter])
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=4, use_clear=True)
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    nt.nodes.remove(tn)
    scene.render.engine = prev_engine
    if ng is not None and "HazeAmount" in ng.nodes:
        ng.nodes["HazeAmount"].outputs[0].default_value = 1.0
    log("baked terrain albedo %dpx in %.1f s" % (size, time.time() - t0))


def render_thumb(path, man):
    import sunarc
    scene = bpy.context.scene
    cam = bpy.data.objects.get("CAP_Cam_Hero")
    sun = bpy.data.objects.get("CAP_Sun")
    if cam is None:
        return
    from mathutils import Vector
    s = man['sun']
    rise, sset = sunarc.sunrise_sunset(s['latitude_deg'], s['default_day_of_year'])
    d = sunarc.sun_direction(s['latitude_deg'], s['default_day_of_year'], (sset or 19.0) - 1.2, s['north_offset_deg'])
    if sun is not None:
        sun.rotation_euler = (-Vector(d)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = 640, 320
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = 16
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log("thumb", os.path.relpath(path, ROOT))


def export_props():
    import figures
    out = os.path.join(ROOT, "atlas", "assets", "props.glb")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    m = bpy.data.materials.get("PROP_Figure") or bpy.data.materials.new("PROP_Figure")
    c = bpy.data.collections.new("PropsExport")
    bpy.context.scene.collection.children.link(c)
    obs = []
    for k in figures.PROPS:
        ob = figures.to_blender("PROP_" + k, figures.PROPS[k], c, [m])
        obs.append(ob)
    gltf(out, obs)
    for o in obs:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(c)


def export(city_id, out_dir, man):
    t0 = time.time()
    import fantasy_capital as fc
    root = bpy.data.collections.get(fc.ROOT_NAME)
    ter = prepare_sea_and_terrain()
    # city.glb: every render mesh except anchors, proxies, steam volumes
    skip_colls = {"Anchors", "Proxies"}
    objs = []
    for c in [root] + list(root.children_recursive):
        if c.name in skip_colls or any(c.name in [p.name for p in pc.children_recursive] for pc in []):
            continue
        for o in c.objects:
            if o.type == 'MESH' and not o.name.startswith(SKIP_PREFIX) and o not in objs:
                objs.append(o)
    objs = [o for o in objs if not any(o.name in bpy.data.collections[n].all_objects for n in skip_colls
                                        if bpy.data.collections.get(n))]
    gltf(os.path.join(out_dir, "city.glb"), objs)
    gltf(os.path.join(out_dir, "proxies.glb"), unhide_collection("Proxies"))
    for n in ("Proxies", "Anchors"):
        if bpy.data.collections.get(n):
            bpy.data.collections[n].hide_viewport = bpy.data.collections[n].hide_render = True
    if ter is not None:
        bake_terrain(ter, os.path.join(out_dir, "terrain_albedo.png"))
    render_thumb(os.path.join(out_dir, "thumb.png"), man)
    export_props()
    log("OK in %.1f s" % (time.time() - t0))
