# Session cards

One line per card; the detail is in `docs/PLAN.md` §4. Handoffs go to `docs/handoffs/Sxx.md`.

| Card | Scope | Owns | Depends on |
|---|---|---|---|
| S0 | Repo, LFS, rulebook | root docs, `.gitignore`, `.gitattributes` | none |
| S1 | Hippodrome review/extend: carceres, chariots as own object, race/seat anchors | `generator/fantasy_capital.py` (hippodrome only) | S0 |
| S2 | House chunks, `Anchors` collection, `city.json`, proxies, headless build, sun-arc maths + tests | `generator/`, `tools/build_city.sh`, `tests/`, `docs/city_schema.md` | S1 |
| S3 | Sun, sky, night lights, clouds (Blender) | `blender/cinematic/{common,sky,lights,clouds}.py` | S2 |
| S4 | Ships, crowds, venue fill (Blender) | `blender/cinematic/{ships,crowds,venues}.py` | S2 |
| S5 | Events, shot list, renders, encoding | `blender/cinematic/{events,shots}.py`, `tools/render_shot.sh`, `blender/renders/` | S3, S4 |
| S6 | glTF export pipeline | `tools/export_city.py`, `cities/` | S2 |
| S7 | Atlas shell, CityLoader, TurntableCamera, TimeOfDay/SunArc | `atlas/` (shell, loader, camera, time) | S6 |
| S8 | Atlas ambient life, EventSystem, UI | `atlas/` (life, events, UI) | S7 |
| S9 | World map, city switching | `atlas/` (map) | S7 |
| S10 | Generator parametrised by `generator/cities/<id>.json`; second city | `generator/`, `cities/` | S2 |
