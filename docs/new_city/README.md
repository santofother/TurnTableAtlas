# New city: the startup prompt

Read this whole file before doing anything else, along with `AGENTS.md` (the repo rules). You are adding one city
to the Turntable Atlas from a brief the user wrote: `briefs/<city_id>/brief.md` and reference images in
`briefs/<city_id>/refs/`.

**Start a session with:** `/new-city <city_id>` (Claude Code), or tell any agent
`Read docs/new_city/README.md and build the city in briefs/<city_id>/.`
**No brief yet?** `tools/new_city.py init <city_id> "Display Name"` makes the folder and the template.

## What you are making
The Turntable Atlas turns procedurally generated cities of the **Caelora** world (the user's fantasy setting)
into two things: cinematic renders in Blender, and a Godot viewer with a 3D world map. Every city is one config
file, `generator/cities/<city_id>.json`. `tools/build_city.sh <city_id>` turns it into `blender/<city_id>.blend`
and a **city package** `cities/<city_id>/` (`city.glb`, `proxies.glb`, `terrain_albedo.png`, `thumb.png`,
`city.json`). The Atlas finds the package by itself and puts a pin on the world map. **No code changes** for a city
the generator can already express.

## Where everything is
| What | Where |
|---|---|
| The brief and reference images | `briefs/<city_id>/brief.md`, `briefs/<city_id>/refs/` |
| The city config you write | `generator/cities/<city_id>.json` |
| A full config example (every `layout` key) | `docs/new_city/example_layout.json`: an island port built as a test, removed as a city because it read like a copy of Calderra. Use it for the keys, **not** the design. |
| The first city (defaults for every missing key) | `generator/cities/fantasy_capital.json` (Calderra), defaults in `generator/fantasy_capital.py` (`_LAYOUT_KEYS`, `LANDMARKS`, `apply_config`) |
| The generator | `generator/fantasy_capital.py` (layout, buildings), `generator/anchors.py` (streets, zones, venues → `city.json`), `generator/build_city.py` |
| Manifest schema | `docs/city_schema.md`, checked by `tests/test_manifest.py` |
| Layout debug drawing | `$BLENDER -b --factory-startup --python tools/debug/anchor_map.py -- <city_id> /tmp/<city_id>_anchors.png` |
| The output package | `cities/<city_id>/` (generated: never edit by hand) |
| Painted Caelora map (pins, `pin_uv`) | `atlas/assets/map/Caelora_Geography.png` (3278×1920, uv from the top-left) |
| Known World relief data | `atlas/assets/map/known_world/known_world.json` (settlements, realms, affine to the painted map) |
| **Lore table** | `atlas/assets/map/known_world/atlas_data.json`: kingdoms, houses, characters, settlements (with descriptions, rulers, elevation), geography. Exported from the .blend by `tools/bake_known_world.py`. |
| World descriptions | `~/PersonalProjects/FOMSMap/2D-Map-Prompts/0*_Description.md` (Known World, Caelora, Quadria, Eastern Vesperra) |
| World source (read only) | `~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend` (never save it) |
| Session rules, coordinates, commands | `AGENTS.md`; decisions so far: `docs/DECISIONS.md` |

`tools/new_city.py list` shows every settlement and which already has a city. `tools/new_city.py place <settlement>`
prints its painted-map `pin_uv` (or "off Caelora"), its latitude and its lore entry.

## Lore rules
- The user's lore wins. Take names, rulers, realm, character and the site from `atlas_data.json` and the
  description files; quote the `description` into `world_map.lore`.
- Anything the brief and the lore don't settle: use a placeholder marked `LORE?` and list it in the handoff.
  Never invent canon silently.
- Never edit anything under `~/PersonalProjects/FOMSMap`.

## Frame and scale (the contract)
- The model is metres in a **100 × 100 m plinth**, `[-50, 50]` on X (east) and Y (north), +Z up, sea level 0.
  `model_scale` 15 means 1 model metre is 15 real metres, so the plinth is a 1.5 km square of city.
- Headings: degrees counter-clockwise from +X. Godot converts with `(x, y, z) -> (x, z, -y)`.
- The camera presets in `landmarks` use target, dist, yaw and pitch (see `docs/city_schema.md`).

## What the generator can build
It builds a walled Mediterranean / Roman-style city. The config's `layout` sets:
- **Site:** `coast_line`/`coast_poly` (sea vs land), `harbor`, `harbor_center`, moles (`w_mole`, `e_mole`),
  `piers`, `terrain` (`base_slope`, `hills: [[x, y, r, h]]`, `north_ridge`, `west_hills`), a `plateau`
  (acropolis), a `river` with a `bridge`, `boulders`.
- **City:** `wall_path`, `gates`, `ring_center`, `avenues`, `paved_avenues`, `roads`, `road_stubs`, an
  `aqueduct`, `harbour_front` (quay rows).
- **Landmarks** (`layout.landmarks`, built in order): `palace`, `forum`, `colosseum`, `hippodrome` (`hippo`),
  `baths`, `rotunda`, `theatre`, `temple`, `tholos`, `castellum`.
- **Look:** `wall_cols`, `roof_cols` (RGB lists), `roof_hip` and `roof_flat` (odds), `steam_extra`.
- **Sea:** `ships`, `ship_scale`; plus at the top level `ship_lanes`, `spawn_zones`, `portals`,
  `extra_walkways`, `routes`, `landmarks` (camera presets), `events`, `sun`, `world_map`.

Two other builders exist: `generator/villa.py` (`"kind": "estate"`, a country house and its grounds) and
`generator/metropolis.py` (`"kind": "metropolis"`, an inland terraced city in a mountain basin at regional scale:
peaks, cliff bands, graded rivers, canals, fields, instanced courtyard houses on terraces, freight yards,
caravanserais, a market, villages; see `generator/cities/karn_ashur.json` for its `layout` keys). Anything else (a
citadel, a lighthouse as its own building, windmills, other architecture, another plinth size for the Roman city) is
**new generator work**. Say so in the brief's
"Agent's reading", build the closest city the generator can make now, and write what's missing as a proposed
card in the handoff. Don't hack it into `fantasy_capital.py` unasked.

## Steps
1. **Read the brief and every reference image** (open each file in `refs/`). Run `tools/new_city.py place
   <settlement>` and read the settlement's lore.
2. **Fill in "Agent's reading"** at the bottom of the brief: what you see in each reference, the build plan
   (site, walls, landmark list with rough positions, palette, sun, events, views), what the generator can't do,
   and your questions. If a question changes the layout, ask the user **once, all questions together**, before
   building. Otherwise go ahead and note your choices.
3. **Branch** `city-<city_id>`.
4. **Write `generator/cities/<city_id>.json`.** Start from the keys in `example_layout.json`, but design from the
   brief: a different coastline, landmark set and palette from Calderra's. Set `world_map`: `map`
   `caelora_geography`, `pin_uv` (check the `place` estimate against the star or dot on the painted map), and
   `settlement`. Leave out `pin_uv` for a city off Caelora. Set `sun.latitude_deg` and `default_day_of_year`;
   list only `events` the city has venues for.
5. **Build:** `tools/build_city.sh <city_id>` (15–30 s). Read its stats (houses, triangles, warnings). Draw the
   anchor map to check streets, zones, lanes and routes.
6. **Look at it**, few and small: `cities/<city_id>/thumb.png`, and Atlas stills
   `$GODOT --path atlas -- --city=<city_id> --hour=17 --shots=4 --quit-after=5` (saved in
   `atlas/perf_results/`). Compare with the references and the brief, adjust the config, rebuild. Stop after
   about 3 rounds on the same problem and write down what's left.
7. **Check it differs from Calderra:** put the two thumbnails side by side. If a stranger would call it the same
   city, it isn't done.
8. **Test:** `tools/run_tests.sh` (it smoke-tests every city package, including yours). Everything must pass.
9. **Hand off:** `docs/handoffs/city_<city_id>.md` (≤ 25 lines: status, what landed, how to check it, `LORE?`
   list, generator gaps). Add the city to the table in `README.md`. Commit on the branch; never force-push.

## Done means
- `cities/<city_id>/` exists and the Atlas opens it from its pin on both maps (or only the Known World, for a
  city off Caelora).
- It reads as the place in the brief and the lore, not as Calderra with new colours.
- Tests are green, and the handoff lists every placeholder and every generator gap.
