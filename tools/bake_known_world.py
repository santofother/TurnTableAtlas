"""Bake the Known World relief map (~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend) for the Atlas.

Reads the .blend (never saves it) and writes atlas/assets/map/known_world/:
    albedo.png      the blend's own ground colour, unlit: a top-down orthographic EEVEE render of the terrain, hero
                    patches, sea surface (water over seabed), rivers, lakes, roads and villages with every material's
                    Base Color routed to an Emission shader (alpha kept), so Godot can light it with its own sun
    height.png      elevation, 16 bit packed in R (high byte) and G (low byte), normalised to [elev_min, elev_max]
    known_world.json  bounds, elevation range, settlements (uv from the top-left), realm seats, and the affine
                      that maps a uv on the painted Caelora Geography map to a uv on this map
    atlas_data.json   the blend's lore table (kingdoms, houses, characters, settlements, geography), unchanged

    $BLENDER -b ~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend --python tools/bake_known_world.py

Height comes from T_TerrainData (blue channel x 10000 = metres, as in the blend's M_Terrain material). The blend
shows it with 1 unit = scene unit scale (16093.44 m, 10 miles) and the terrain objects' Z scale (15x) as vertical
exaggeration; both go into the json so the Atlas builds the relief at the blend's proportions. The CAM_* cameras
are exported as orbit presets (target on the sea plane, yaw / pitch / distance).
The blend maps world XY to texture uv with the WorldUV mapping node; the same mapping is used here.
"""
import json
import math
import os

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "atlas", "assets", "map", "known_world")
ALBEDO_W = 6144

# Capital stars on the painted map (atlas/assets/map/Caelora_Geography.png, 3278 x 1920), measured by eye from
# the image, uv from the top-left. Used only to fit the painted-map -> Known World affine.
GEO_STARS = {
    "calderra": (1301 / 3278, 1495 / 1920),
    "salmara": (641 / 3278, 1153 / 1920),
    "astera": (1049 / 3278, 1082 / 1920),
    "madravella": (1364 / 3278, 1051 / 1920),
    "corivessa_great_gate": (1830 / 3278, 1235 / 1920),
    "kervara": (1987 / 3278, 1250 / 1920),
    "dovehall": (1727 / 3278, 1707 / 1920),
}


def log(*a):
    print("[KnownWorld]", *a, flush=True)


def world_uv_mapping():
    m = bpy.data.materials["M_Terrain_Fast"].node_tree.nodes["WorldUV"]
    loc = list(m.inputs["Location"].default_value)
    scale = list(m.inputs["Scale"].default_value)
    return loc, scale


def to_uv(x, y, loc, scale):
    """World XY -> image uv from the top-left (Blender's v runs bottom-up)."""
    u = x * scale[0] + loc[0]
    v = y * scale[1] + loc[1]
    return u, 1.0 - v


def pixels(img):
    w, h = img.size
    a = np.empty(w * h * img.channels, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, img.channels)[::-1]          # top row first


def save_png(arr, path, w, h):
    """arr: (h, w, 4) float 0..1, top row first."""
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).ravel().astype(np.float32))
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def fit_affine(src, dst):
    """Least-squares 2D affine: dst = A @ [u, v, 1]."""
    X = np.array([[u, v, 1.0] for u, v in src])
    Y = np.array(dst)
    A, *_ = np.linalg.lstsq(X, Y, rcond=None)
    err = np.abs(X @ A - Y).max()
    return A.T.tolist(), float(err)


GROUND_COLLECTIONS = {"TERRAIN", "WATER", "RIVERS_LAKES", "DECORATION"}
NOT_GROUND = ("TLOD", "SEA_Beyond", "SEA_Surface_Fast", "TREES_")


def unlit(mat):
    """Route the Principled BSDF's Base Color (and Alpha) straight to the output as emission (scratch copy only)."""
    if mat is None or not mat.use_nodes:
        return
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if out is None or bsdf is None:
        return
    em = nt.nodes.new("ShaderNodeEmission")
    bc = bsdf.inputs["Base Color"]
    if bc.is_linked:
        nt.links.new(bc.links[0].from_socket, em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = bc.default_value
    shader = em.outputs[0]
    a = bsdf.inputs["Alpha"]
    if a.is_linked or a.default_value < 1.0:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        if a.is_linked:
            nt.links.new(a.links[0].from_socket, mix.inputs[0])
        else:
            mix.inputs[0].default_value = a.default_value
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        shader = mix.outputs[0]
    nt.links.new(shader, out.inputs["Surface"])


def render_albedo(x0, x1, y0, y1, w, h, path):
    sc = bpy.context.scene
    mats = set()
    for ob in sc.objects:
        ground = ob.type == "MESH" and {c.name for c in ob.users_collection} & GROUND_COLLECTIONS and not ob.name.startswith(NOT_GROUND)
        if not ground:
            ob.hide_render = True
        elif not ob.hide_render:
            if ob.name.startswith("HERO_"):
                # the close-up patches fill holes in the base terrain but poke just above the sea surface and carry
                # their own close-up material: sink them under the water and give them the base terrain material
                # (same world-uv data) so they read exactly like their surroundings from above
                ob.location.z -= 0.6
                for slot in ob.material_slots:
                    slot.link = "OBJECT"
                    slot.material = bpy.data.materials["M_Terrain"]
            mats.update(s.material for s in ob.material_slots)
    for m in mats:
        unlit(m)
    log(f"albedo: {len(mats)} materials unlit, {sum(1 for o in sc.objects if not o.hide_render)} objects")
    if sc.world and sc.world.use_nodes:
        for n in sc.world.node_tree.nodes:
            if n.type == "BACKGROUND":
                n.inputs["Strength"].default_value = 0.0
    cam_data = bpy.data.cameras.new("BAKE_TopDown")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(x1 - x0, y1 - y0)
    cam_data.clip_start, cam_data.clip_end = 1.0, 1000.0
    cam = bpy.data.objects.new("BAKE_TopDown", cam_data)
    sc.collection.objects.link(cam)
    cam.location = ((x0 + x1) / 2, (y0 + y1) / 2, 300.0)     # far enough that the materials use their distant look
    cam.rotation_euler = (0.0, 0.0, 0.0)
    sc.camera = cam
    r = sc.render
    r.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 32
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.film_transparent = False
    r.use_compositing = False
    r.use_sequencer = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    r.filepath = path
    bpy.ops.render.render(write_still=True)


def exaggeration():
    for m in bpy.data.materials:
        if m.name == "M_Terrain" and m.use_nodes and "Exaggeration" in m.node_tree.nodes:
            return float(m.node_tree.nodes["Exaggeration"].outputs[0].default_value)
    return 15.0


def cameras():
    """CAM_* cameras as orbit presets: the point they look at on the sea plane, heading (deg CCW from +X, from the
    target towards the camera), pitch above the horizon and distance; blend units, +X east, +Y north."""
    out = []
    for ob in sorted((o for o in bpy.data.objects if o.type == "CAMERA" and o.name.startswith("CAM_")), key=lambda o: o.name):
        loc = ob.matrix_world.translation
        fwd = ob.matrix_world.to_3x3() @ __import__("mathutils").Vector((0, 0, -1))
        if fwd.z > -1e-3:
            continue
        t = -loc.z / fwd.z
        tgt = loc + fwd * t
        off = loc - tgt
        dist = off.length
        out.append({"id": ob.name, "name": ob.name.split("_", 2)[-1].replace("_", " "),
                    "target": [round(tgt.x, 3), round(tgt.y, 3), 0.0],
                    "yaw": round(math.degrees(math.atan2(off.y, off.x)), 2),
                    "pitch": round(math.degrees(math.asin(off.z / dist)), 2), "dist": round(dist, 3)})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    loc, scale = world_uv_mapping()
    x0, x1 = -loc[0] / scale[0], (1 - loc[0]) / scale[0]
    y0, y1 = -loc[1] / scale[1], (1 - loc[1]) / scale[1]
    log(f"bounds x [{x0:.1f}, {x1:.1f}] y [{y0:.1f}, {y1:.1f}]")

    # elevation
    td = bpy.data.images["T_TerrainData"]
    td.reload()
    # The Atlas uses the native height grid. Summed-area resampling here used to
    # lose hundreds of metres to float32 cancellation far from the image origin.
    e = pixels(td)[..., 2] * 10000.0
    hh, hw = e.shape
    emin, emax = float(e.min()), float(e.max())
    log(f"elevation {emin:.0f} .. {emax:.0f} m, {hw}x{hh}")
    q = np.round((e - emin) / (emax - emin) * 65535).astype(np.uint32)
    rgba = np.zeros((hh, hw, 4), dtype=np.float32)
    rgba[..., 0] = (q >> 8) / 255.0
    rgba[..., 1] = (q & 255) / 255.0
    rgba[..., 3] = 1.0
    save_png(rgba, os.path.join(OUT, "height.png"), hw, hh)

    # albedo: the blend's materials, unlit, from straight above
    aw = ALBEDO_W
    ah = round(aw * (y1 - y0) / (x1 - x0))
    render_albedo(x0, x1, y0, y1, aw, ah, os.path.join(OUT, "albedo.png"))
    log(f"albedo {aw}x{ah}")

    # settlements and realms
    data = json.loads(bpy.data.texts["atlas_data.json"].as_string())
    kingdoms = {k["id"]: k for k in data.get("kingdoms", [])}
    settlements = []
    for s in data.get("settlements", []):
        sid = s["id"].split(":", 1)[1]
        ob = bpy.data.objects.get("CITY_" + sid)
        if ob is None:
            continue
        u, v = to_uv(ob.location.x, ob.location.y, loc, scale)
        k = kingdoms.get(s.get("kingdom") or "", {})
        settlements.append({"id": s["id"], "name": s["name"], "type": s.get("type"), "realm": k.get("name"),
                            "uv": [round(u, 5), round(v, 5)]})
    realms = []
    for k in kingdoms.values():
        ob = bpy.data.objects.get("KINGDOM_" + k["id"].split(":", 1)[1])
        if ob is None:
            continue
        u, v = to_uv(ob.location.x, ob.location.y, loc, scale)
        realms.append({"id": k["id"], "name": k["name"], "uv": [round(u, 5), round(v, 5)], "colour": k.get("colour")})

    by_id = {s["id"].split(":", 1)[1]: s["uv"] for s in settlements}
    pairs = [(GEO_STARS[i], by_id[i]) for i in GEO_STARS if i in by_id]
    A, err = fit_affine([p[0] for p in pairs], [p[1] for p in pairs])
    log(f"settlements {len(settlements)}, realms {len(realms)}, geo->kw affine max error {err:.4f} uv")

    meta = {
        "source": "~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend (tools/bake_known_world.py)",
        "bounds_xy": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
        "elev_min_m": round(emin, 2), "elev_max_m": round(emax, 2),
        "unit_m": round(bpy.context.scene.unit_settings.scale_length, 4), "exaggeration": exaggeration(),
        "cameras": cameras(),
        "albedo": "albedo.png", "height": "height.png", "height_size": [hw, hh],
        "geo_to_kw": [[round(c, 6) for c in row] for row in A], "geo_to_kw_max_err": round(err, 5),
        "settlements": settlements, "realms": realms,
    }
    with open(os.path.join(OUT, "known_world.json"), "w") as f:
        json.dump(meta, f, indent=1)
    # the blend's lore table as is (kingdoms, houses, characters, settlements with descriptions, geography), so a
    # new-city session can read it without Blender (docs/new_city/README.md)
    with open(os.path.join(OUT, "atlas_data.json"), "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    log("wrote", OUT)


main()
