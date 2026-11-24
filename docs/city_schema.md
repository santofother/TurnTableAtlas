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
| `world_map` | `{map, pin_uv:[u,v], lore?}` | pin on the world map, uv from the top-left |
| `sun` | `{latitude_deg, default_day_of_year, north_offset_deg, sunrise_h, sunset_h}` | defaults for the shared sun-arc (`generator/sunarc.py`) |
| `files` | `{model, proxies, terrain_albedo, thumb}` | package file names |
| `street_graph` | `{nodes:[[x,y,z]], edges:[[a,b,width]]}` | one connected walkable graph (streets, quays, gate passages, country roads) |
| `spawn_zones[]` | `{id, poly:[[x,y]], density, points:[[x,y,z]]}` | places people idle; `points` are pre-sampled walkable spots |
| `ship_lanes[]` | `{id, points:[[x,y]], loop, kinds[], speed, every_s, dwell_s, then}` | sea paths; `then` = lane continued after `dwell_s` (arrive, wait, leave) |
| `moorings[]`, `anchored_ships[]`, `boats[]` | `{object, kind, pos, heading_deg, scale}` | the generator's static ships (they bob) |
| `berths[]` | `[[x,y]]` | free water spots off the quays for arriving fleets, nearest the harbour centre first |
| `venues[]` | see below | seats, floors, tracks, entrances |
| `routes` | `{id: [[x,y,z]]}` | walkable polylines along the graph (`procession`) |
| `night_lights[]` | `{pos, kind: window/lamp/torch/lighthouse, strength, order?}` | glow points; `window.order` = light-up order (see below) |
| `landmarks[]` | `{id, label, camera:{target, dist, yaw, pitch}}` | camera presets: camera = target + dist·(cos p cos y, cos p sin y, sin p) |
| `steam_vents[]` | `[x,y,z]` | bath steam sources |
| `events[]` | names | events this city supports |

**Venues**, common: `id, type, label, center[x,y], heading_deg, seat_tiers:[{ring:[[x,y,z]], capacity}], entrances`.
- `arena` (colosseum): `floor_poly[[x,y]]`, `floor_z`, `beast_gates`.
- `circus` (hippodrome): `track_centerline` (closed, counter-clockwise, spina on the left), `lanes`, `lane_width`,
  `lane_radii` (offsets from the spina axis), `start_gates`, `turning_posts`, `laps`, `floor_poly`, `royal_box`.
- `theatre`: `stage[[x,y]]`, `stage_z`.

**Windows at night.** Every glazed window face carries its light-up order in the vertex-colour alpha
(`Col.a` / glTF `COLOR_0.a`; `1.0` = not a window). A window is lit while `order < NightLevel`, with
`NightLevel = sunarc.night_level(sun elevation)` (0 by day, 0.9 at night). Order = 0.6·hash + 0.4·distance
from the harbour, so lamps come on in a wave spreading out from the harbour.
