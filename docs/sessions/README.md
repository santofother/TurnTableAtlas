# Session cards

One line per card; the detail is in `docs/PLAN.md` §4. Handoffs (with screenshots) are in `docs/handoffs/`.
The original eleven cards ran on 2026-11-23 in one unattended session.

| Card | Scope | Owns | Depends on | Status |
|---|---|---|---|---|
| S0 | Repo, LFS, rulebook | root docs, `.gitignore`, `.gitattributes` | none | DONE |
| S1 | Hippodrome review/extend: carceres, chariots as own object, race/seat anchors | `generator/fantasy_capital.py` (hippodrome only) | S0 | DONE |
| S2 | House chunks, `Anchors` collection, `city.json`, proxies, headless build, sun-arc maths + tests | `generator/`, `tools/build_city.sh`, `tests/`, `docs/city_schema.md` | S1 | DONE |
| S3 | Sun, sky, night lights, clouds (Blender) | `blender/cinematic/{cine,sky,lights,clouds,run}.py` | S2 | DONE |
| S4 | Ships, crowds, venue fill (Blender) | `blender/cinematic/{gn,ships,crowds,venues}.py`, `generator/figures.py` | S2 | DONE |
| S5 | Events, shot list, renders, encoding | `blender/cinematic/{events,shots}.py`, `tools/render_*.sh`, `tools/encode.py`, `blender/renders/` | S3, S4 | DONE |
| S6 | glTF export pipeline | `tools/export_city.py`, `cities/` | S2 | DONE |
| S7 | Atlas shell, CityLoader, TurntableCamera, TimeOfDay/SunArc | `atlas/` (shell, loader, camera, time) | S6 | DONE |
| S8 | Atlas ambient life, EventSystem, UI | `atlas/` (life, events, UI) | S7 | DONE |
| S9 | World map, city switching | `atlas/` (map) | S7 | DONE |
| S10 | Generator parametrised by `generator/cities/<id>.json`; second city | `generator/`, `cities/` | S2 | DONE |
| S13 | Calderra voyages, port shipping, Known World-only viewer | `generator/`, `cities/fantasy_capital/city.json`, `blender/cinematic/ships.py`, `atlas/`, `docs/city_schema.md` | S4, S8, S11, S12 | DONE |
| S14 | Known World fog banks, shipping routes, and trireme miniatures | `WorldMap.cs`, `regional_fog.gdshader`, `WorldShipping.cs`, `shipping_routes.json` | S11, S12, S13 | DONE |
| S15 | Landric's villa first wireframe from Chapter 1 | `docs/design/landrics_villa*` | none | DONE (design only) |

## Known World round 2 (planned 2026-11-23, detail in `docs/world_map/PLAN.md`)

| Card | Scope | Depends on | Status |
|---|---|---|---|
| W1 | CK3-style 3D map table and frame | none | DONE |
| W2 | Terrain: Oravian Expanse mountains, Dovaran Crown fjords (blend) | none | DONE |
| W3 | Fix sea colour round Dovaran Crown | W2 | DONE |
| W4 | Salmara–Calderra shared border, no no-man's-land | W2 | DONE |
| W5 | Karn Ashur matches the concept (map model; city package later) | W2 if terrain | TODO |
