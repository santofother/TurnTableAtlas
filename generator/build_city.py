"""Blender entry point: build one city from its config and write the .blend and the manifest.

    $BLENDER -b --factory-startup --python generator/build_city.py -- <city_id> [--no-save] [--export]

Writes blender/<city_id>.blend and cities/<city_id>/city.json. With --export it also runs tools/export_city.py
(city.glb, proxies.glb, terrain_albedo.png, thumb.png). Prints `[Build] OK` on success, exits non-zero on failure.
"""
import json
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "generator"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def main(argv):
    import bpy
    import fantasy_capital as m
    import anchors

    city_id = argv[0] if argv else "fantasy_capital"
    with open(os.path.join(ROOT, "generator", "cities", city_id + ".json")) as f:
        cfg = json.load(f)
    t0 = time.time()
    if hasattr(m, "apply_config"):
        m.apply_config(cfg)
    stats = m.build_all()
    print("[Build] generator", json.dumps(stats))
    report = {}
    root = m.ANCHORS['_root']
    man, G, graph = anchors.build_manifest(m, cfg, report)
    anchors.write_blend_anchors(m, man, root)
    anchors.write_proxies(m, root)
    out_dir = os.path.join(ROOT, "cities", city_id)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "city.json"), "w") as f:
        json.dump(man, f, separators=(",", ":"))
    print("[Build] anchors", json.dumps(report))
    print("[Build] manifest %s: %d nodes, %d edges, %d zones, %d lanes, %d venues, %d lights, %d landmarks (%.0f KB)" % (
        city_id, len(graph['nodes']), len(graph['edges']), len(man['spawn_zones']), len(man['ship_lanes']),
        len(man['venues']), len(man['night_lights']), len(man['landmarks']),
        os.path.getsize(os.path.join(out_dir, "city.json")) / 1024))
    if "--no-save" not in argv:
        path = os.path.join(ROOT, "blender", city_id + ".blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        print("[Build] saved", path)
    if "--export" in argv:
        import export_city
        export_city.export(city_id, out_dir, man)
    print("[Build] OK in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    try:
        main(args)
    except Exception:
        traceback.print_exc()
        print("[Build] FAILED")
        sys.exit(1)
