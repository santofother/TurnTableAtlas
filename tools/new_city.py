#!/usr/bin/env python3
"""Helpers for adding a city (docs/new_city/README.md). Plain Python, no Blender.

    tools/new_city.py init <city_id> ["Display Name"]   make briefs/<city_id>/brief.md (from the template) and refs/
    tools/new_city.py list                              Known World settlements, and which already have a city package
    tools/new_city.py place <settlement>                where a settlement sits: pin_uv on the painted Caelora map
                                                        (or "off Caelora"), Known World uv, latitude, lore description

<settlement> may be the bare id ("calderra") or the full one ("settlement:calderra").
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KW_DIR = os.path.join(ROOT, "atlas", "assets", "map", "known_world")
TEMPLATE = os.path.join(ROOT, "docs", "new_city", "BRIEF_TEMPLATE.md")
# The Known World map frame runs from about 55°N (top edge) to 3.5°N (bottom edge), linearly
# (FOMSMap/2D-Map-Prompts/01_Known_World_Description.md).
LAT_TOP, LAT_BOTTOM = 55.0, 3.5


def load(name):
    with open(os.path.join(KW_DIR, name)) as f:
        return json.load(f)


def packages():
    out = {}
    for p in glob.glob(os.path.join(ROOT, "generator", "cities", "*.json")):
        with open(p) as f:
            c = json.load(f)
        out[c.get("world_map", {}).get("settlement")] = c["id"]
    return out


def to_geo(kw, u, v):
    """Known World uv -> painted Caelora map uv (inverse of known_world.json's geo_to_kw affine)."""
    (a, b, c), (d, e, f) = kw["geo_to_kw"]
    det = a * e - b * d
    x, y = u - c, v - f
    return (e * x - b * y) / det, (-d * x + a * y) / det


def find(kw, sid):
    sid = sid if sid.startswith("settlement:") else "settlement:" + sid
    s = next((s for s in kw["settlements"] if s["id"] == sid), None)
    if s is None:
        sys.exit(f"no settlement {sid}; see `tools/new_city.py list`")
    return s


def cmd_init(city_id, name=None):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", city_id):
        sys.exit("city id: lower case letters, digits and _ (e.g. salmara, corivessa_port)")
    d = os.path.join(ROOT, "briefs", city_id)
    os.makedirs(os.path.join(d, "refs"), exist_ok=True)
    brief = os.path.join(d, "brief.md")
    if os.path.exists(brief):
        print(f"exists: {os.path.relpath(brief, ROOT)} (left as it is)")
    else:
        with open(TEMPLATE) as f:
            t = f.read()
        t = t.replace("<city_id>", city_id).replace("<Display Name>", name or city_id.replace("_", " ").title())
        with open(brief, "w") as f:
            f.write(t)
        print(f"wrote {os.path.relpath(brief, ROOT)}")
    print(f"put reference images in {os.path.relpath(os.path.join(d, 'refs'), ROOT)}/, fill in the brief, then start a session with:")
    print(f"    /new-city {city_id}        (Claude Code)")
    print(f"    Read docs/new_city/README.md and build the city in briefs/{city_id}/.   (any other agent)")


def cmd_list():
    kw, lore = load("known_world.json"), load("atlas_data.json")
    built = packages()
    desc = {s["id"]: s for s in lore.get("settlements", [])}
    print(f"{'settlement':34} {'type':8} {'realm':28} {'continent':10} city package")
    for s in kw["settlements"]:
        cont = desc.get(s["id"], {}).get("continent", "")
        print(f"{s['id']:34} {s.get('type') or '':8} {s.get('realm') or '':28} {cont or '':10} {built.get(s['id'], '')}")


def cmd_place(sid):
    kw, lore = load("known_world.json"), load("atlas_data.json")
    s = find(kw, sid)
    u, v = s["uv"]
    gu, gv = to_geo(kw, u, v)
    on_geo = 0 <= gu <= 1 and 0 <= gv <= 1
    lat = LAT_TOP - v * (LAT_TOP - LAT_BOTTOM)
    rec = next((r for r in lore.get("settlements", []) if r["id"] == s["id"]), {})
    print(f"{s['name']} ({s['id']}), {s.get('type')}, realm {s.get('realm')}")
    print(f"  Known World uv      [{u:.5f}, {v:.5f}]")
    if on_geo:
        print(f"  painted-map pin_uv  [{gu:.4f}, {gv:.4f}]   (affine estimate, up to ~0.02 off: check it against the")
        print(f"                      capital star / town dot on atlas/assets/map/Caelora_Geography.png, 3278x1920)")
    else:
        print("  off the painted Caelora map: leave out pin_uv; the city is pinned on the Known World only")
    print(f"  latitude            ~{lat:.1f}°N from the Known World graticule (Calderra's package uses 38°N, a choice")
    print(f"                      in docs/DECISIONS.md #3; keep new cities consistent with it or say why not)")
    for k in ("display", "kingdom", "tier", "elev_m", "ruler", "population", "continent", "description", "source"):
        if rec.get(k) not in (None, ""):
            print(f"  {k:19} {rec[k]}")


def main(argv):
    if len(argv) >= 2 and argv[0] == "init":
        cmd_init(argv[1], " ".join(argv[2:]) or None)
    elif argv[:1] == ["list"]:
        cmd_list()
    elif len(argv) == 2 and argv[0] == "place":
        cmd_place(argv[1])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
