# `city.json` v1: the city package manifest

Written by `generator/build_city.py` (via `generator/anchors.py`), read by `blender/cinematic/*` and the Atlas
(`atlas/src/Core/CityManifest.cs`). Checked by `tests/test_manifest.py`.

**Frame:** metres, +X east, +Y north, +Z up, sea level 0; the model covers `extent` = [xmin, ymin, xmax, ymax].
Godot converts with `(x, y, z) -> (x, z, -y)`. Headings are degrees CCW from +X.
Points are `[x, y, z]` unless the field says 2D (`[x, y]`).

| Key | Shape | Meaning |
|---|---|---|
| `id`, `name`, `version` (=1), `model_scale` | | 1 model metre = `model_scale` real metres |
| `extent`, `sea_level` | | plinth bounds |
| `world_map` | `{map, pin_uv?:[u,v], settlement?, lore?}` | The pin uses a settlement ID from `atlas/assets/map/known_world/known_world.json` (e.g. `settlement:calderra`). Older packages can supply `pin_uv` in painted Caelora coordinates, which the Atlas converts to Known World coordinates. |
| `sun` | `{latitude_deg, default_day_of_year, north_offset_deg, sunrise_h, sunset_h}` | defaults for the shared sun-arc (`generator/sunarc.py`) |
| `files` | `{model, proxies, terrain_albedo, thumb}` | package file names |
| `street_graph` | `{nodes:[[x,y,z]], edges:[[a,b,width]]}` | one connected walkable graph (streets, quays, gate passages, country roads) |
| `spawn_zones[]` | `{id, poly:[[x,y]], density, points:[[x,y,z]]}` | places people idle; `points` are pre-sampled walkable spots |
| `ship_lanes[]` | `{id, points:[[x,y]], loop, kinds[], speed, every_s, dwell_s, then}` | sea paths; `then` = lane continued after `dwell_s` (arrive, wait, leave) |
| `moorings[]`, `anchored_ships[]`, `boats[]` | `{object, kind, pos, heading_deg, scale, voyage?}` | Placed ships bob and follow their voyage when present. |
| `berths[]` | `[[x,y]]` | free water spots off the quays for arriving fleets, nearest the harbour centre first |
| `venues[]` | see below | seats, floors, tracks, entrances |
| `routes` | `{id: [[x,y,z]]}` | walkable polylines along the graph (`procession`) |
| `night_lights[]` | `{pos, kind: window/lamp/torch/lighthouse, strength, order?}` | glow points; `window.order` = light-up order (see below) |
| `landmarks[]` | `{id, label, camera:{target, dist, yaw, pitch}}` | camera presets: camera = target + dist·(cos p cos y, cos p sin y, sin p) |
| `steam_vents[]` | `[x,y,z]` | bath steam sources |
| `events[]` | names | events this city supports (an estate lists its own scenes, e.g. `villa_return`; their timelines are `atlas/events/<name>.json`) |
| `kind` | `"city"` (default), `"estate"` or `"metropolis"` | an estate is a country house with its grounds (`generator/villa.py`): no venues or ships, a handful of people, no lighthouse |
| `anchors` (estate) | `{id: [x,y,z]}` | named staging points for the estate's scenes (`gate_stop`, `private_dining`, `hearth_offer`, `aegis_painting`, `cold_pool`, `heated_pool`, `bath_fire`…) |
| `cutaway` (estate) | `{roofs:[prefix], upper:[prefix]}` | object-name prefixes the Atlas hides to look inside (Layers → Roofs, Upper floor) |
| `terrain_grid` (estate) | `{n, z:[n·n]}` | the ground in model metres on an n×n grid over `extent`, row 0 to the south; the Known World stands the estate's miniature on it |
| `world_map.miniature` (estate) | `{exaggeration, hills_radius_units}` | the estate on the Known World: its model drawn `exaggeration`× true size, hills out to that radius (blend units) |
| `kind: "metropolis"` | | an inland terraced city at regional scale (`generator/metropolis.py`, Karn Ashur): no venues or ships |
| `files.instances`, `instances` (metropolis) | `{file, count, stride: 11, fields, kinds:{name:id}, groups:{name:[first, count]}, protos:{name:{v, f}}}` | instanced houses, terraces, walls, awnings, domes, camels and trees: `instances.bin` is `count` × 11 little-endian float32 (`x y z w d h rot r g b kind`: base point and size in model metres, heading in radians CCW from +X, sRGB tint), sorted by kind. A prototype lives in a unit box (x, y in [-0.5, 0.5], z in [0, 1]); each face `{i: [vertex ids, CCW from outside], m: "tint" \| "abs" \| "win", c: [shade] or [r, g, b]}` (tint = the instance colour × shade; win = a window, lit at night by the instance's order) |
| `files.terrain_height`, `terrain_height` (metropolis) | `{file, n, min_m, max_m, model_vertical_exaggeration, model_datum_m}` | the ground in **true metres** (16 bit in R high / G low of a PNG, row 0 to the north) over the extent; the model's own ground is `datum + (true − datum) × exaggeration` |
| `site` (metropolis) | `{anchor, plinth_half_km, peaks, cliff_zones, sand_aprons, districts, fields, rivers, canals, roads, pilgrimage_climb, places, villages, freight_entry_km, outlet_km}` | the basin's layout in **kilometres from the settlement** (+x east, +y north; a river point's third value is its bed in metres); the Known World's basin patch draws the same layout |
| `world_map.miniature` (metropolis) | `{exaggeration, patch_half_units}` | the basin on the Known World: the package's ground and instances at `exaggeration`× true size, on a patch of this half size |
| `stats` (metropolis) | | the generator's counts (houses, blocks, `population_estimate`, …) |

**Boat voyages.** `voyage` contains `points:[[x,y]]`, `speed` in model metres per second, `dwell_s`, and a start offset `phase_s` in seconds. A voyage with no dwell closes from the last point back to the first. A docked voyage starts and ends at the berth and waits there for `dwell_s` each cycle. Blender and the Atlas use the same path and timing.

**Venues**, common: `id, type, label, center[x,y], heading_deg, seat_tiers:[{ring:[[x,y,z]], capacity}], entrances`.
- `arena` (colosseum): `floor_poly[[x,y]]`, `floor_z`, `beast_gates`.
- `circus` (hippodrome): `track_centerline` (closed, counter-clockwise, spina on the left), `lanes`, `lane_width`,
  `lane_radii` (offsets from the spina axis), `start_gates`, `turning_posts`, `laps`, `floor_poly`, `royal_box`.
- `theatre`: `stage[[x,y]]`, `stage_z`.

**Windows at night.** Every glazed window face carries its light-up order in the vertex-colour alpha
(`Col.a` / glTF `COLOR_0.a`; `1.0` = not a window). A window is lit while `order < NightLevel`, with
`NightLevel = sunarc.night_level(sun elevation)` (0 by day, 0.9 at night). Order = 0.6·hash + 0.4·distance
from the harbour, so lamps come on in a wave spreading out from the harbour.
