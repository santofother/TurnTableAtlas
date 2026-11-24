# Turntable Atlas — Living City Plan

> Handoff document for a new Claude Code session. Read it top to bottom before touching anything.
> Written 2026-11-23.

## 1. What we are building

Two things, made from **one shared source** (the city generator):

| | **A. Living-city cinematic** | **B. Turntable Atlas (interactive viewer)** |
|---|---|---|
| Tool | Blender 5.2 (EEVEE) | Godot 4.7 C# (Forward+), same stack as `FOMSBattleSimulator` |
| Output | Rendered videos/stills: turntables, flythroughs, day→night timelapses | A desktop app: spin/zoom around a city, scrub the time of day, change the sun's arc, trigger events, switch cities from a world map |
| Interactivity | None. It's a film | Full: camera, time, sun, events, city switching |

**Feel:** a living diorama. The city keeps its **miniature tabletop look** (about 1:15 scale) and the camera orbits it like a turntable. This is an atlas of cities to explore and watch, not a first-person game.

### Everything the user wants in the living city
- Little **people moving around**: streets, forum, harbour quays, gates, roads out to the countryside
- **Ships moving**: arriving and leaving the harbour, galleys rowing, fishing boats drifting, moored ships bobbing
- **Clouds** drifting, with their shadows crossing the city
- A **day/night cycle**: sun arc, sky colour, lamps and windows lighting up at night, lighthouse fires, stars and moon
- The **colosseum filling up** with spectators before an event and emptying afterwards
- The **hippodrome** filling up for races (it already exists in the generator; see §2)
- **Actual events inside**: gladiator games and beast hunts in the colosseum, chariot races in the hippodrome, plays in the theatre, fleet arrivals, festival processions
- "Etc.": ambient life such as steam from the baths, smoke, birds, carts on the roads, water on the aqueduct

### Extra requirements for the Atlas viewer
- Easier navigation than Blender: orbit/turntable, pan, zoom, a free-fly mode, and jump-to-landmark buttons
- **Time-of-day slider** plus a playback speed
- **Sun-arc controls**: latitude, day of year (season), and north offset/azimuth. Changing them visibly changes how high the sun climbs and where it rises
- **Event triggers**: buttons such as "Start Games", "Chariot Race", "Fleet Arrives" and "Festival Night"
- **Several cities**: a world map (the Caelora map from `~/PersonalProjects/FOMSMap`) with city pins. Clicking a pin loads that city. Adding a new city should mean dropping in a city package, with no code changes

---

## 2. Current state (verified 2026-11-23)

**Source files.** Copied into this repo on 2026-11-23 (checksums verified) from a temporary session folder:
- `blender/fantasy_capital.blend` (7.5 MB, saved 16:08 that day)
- `generator/fantasy_capital.py` (about 2,700 lines, the **procedural generator**, which is the real source of truth)
- `blender/renders/` (01_hero, 02_harbour, 03_palace, 04_countryside, 05_top_map, 06_hippodrome)

**Hippodrome: already built.** Another session added it after the stats below were taken. `hippodrome()` is at `generator/fantasy_capital.py:1411` and is called at line 1983. It is U-shaped, with the open straight end on the east harbour quay and the curved end pointing inland toward the colosseum. It has its own level pad, a water stair that replaces the quay, an east harbour road to its south, and the camera `CAP_Cam_Hippodrome`. **Phase 1.1 is now "review and extend it" (seat tiers, spina, gates as anchors), not "build it".** The triangle and object counts below predate it.

**Scene facts**
- Blender 5.2.3 LTS, EEVEE. 102 meshes, 5 cameras, 3 lights. About **479k triangles**. 6 materials, colours from **vertex-colour attributes** (`Col`, `zone`, `depth`)
- Spans X,Y from -50 to 50 m, sea level Z = 0, +X east, +Y north. The sea lies to the south and east
- Collections: `Fantasy Capital` > Terrain & Sea, Walls & Harbour, Landmarks (11), City, Countryside, Ships (73 separate objects), Lights & Cameras
- **Merged meshes.** Each category is one big mesh. Biggest: `CAP_Terrain` 205k tris, `CAP_Countryside_Trees` 104k, `CAP_Houses` 64k (every house in one object), `CAP_Sea` 20k
- Scale: house floor 0.27 m, colosseum 10×8 m at (22, 10.5). Theatre at (11.5, 18), baths West (-21.5, 10.5) and East (27.8, 2.2). Gates at (2, 27.8), (-35.5, 6.5), (33.3, 13.4)
- No animation (0 actions), no Geometry Nodes
- Generator entry point: `build_all(stages=("terrain","walls","city","countryside","ships","scene"))`. Layout constants (COAST_LINE, WALL_PATH, ROADS, AVENUES, SHIPS, AQUEDUCT, RIVER, GATES) sit at the top of the file

**User context**
- Godot 4.7 Mono is installed (`/Applications/Godot_mono.app`). The user's existing project `~/PersonalProjects/FOMSBattleSimulator` uses Godot 4.7 C# Forward+ with an `AGENTS.md`/`CLAUDE.md` + session-card workflow. **Follow the same conventions.**
- Blender is at `/Applications/Blender.app/Contents/MacOS/Blender`. The Blender MCP CLI tools need `BLENDER_PATH` set to that path, or run Blender headless directly with `-b file.blend --python script.py`
- The world map art is in `~/PersonalProjects/FOMSMap` (`CaeloraMapv3.png`, `Caelora_Map_Labels*.png`, `political-overlay/`)

---

## 3. Core architecture: one generator, a "city package" per city

```
generator (Python, runs in Blender)
   │
   ├─► city.blend            ← for the cinematic (Blender)
   └─► cities/<id>/          ← the city package (for the Atlas)
         city.glb            ← meshes split by category, plus collision/LOD proxies
         city.json           ← manifest: anchors, paths, venues, sun defaults
         thumb.png           ← map pin / loading image
```

**The manifest is the key idea.** The generator already knows where every street, gate, quay, arena tier and ship lane is. It writes those down once, and **both** Blender and Godot drive their animation from the same data. Neither side hand-places anything.

### `city.json` schema (v1)
```jsonc
{
  "id": "fantasy_capital",
  "name": "Fantasy Capital",
  "version": 1,
  "model_scale": 15,                 // 1 model metre ≈ 15 real metres (for labels/speeds)
  "world_map": { "map": "caelora", "pin_uv": [0.62, 0.41] },
  "sun": { "latitude_deg": 38, "default_day_of_year": 172, "north_offset_deg": 0 },
  "street_graph": { "nodes": [[x,y,z], ...], "edges": [[a,b,width], ...] },   // pedestrians + carts
  "spawn_zones": [ { "id": "forum", "poly": [[x,y],...], "density": 1.0 }, ... ],
  "ship_lanes": [ { "id": "harbour_in", "points": [[x,y],...], "loop": false, "kinds": ["galley","merchant"] }, ... ],
  "moorings":   [ { "pos": [x,y,z], "heading_deg": 90 }, ... ],
  "venues": [
    { "id": "colosseum", "type": "arena",   "center": [22,10.5], "seat_tiers": [ {"ring": [[x,y,z],...], "capacity": 900}, ... ],
      "floor_poly": [[x,y],...], "entrances": [[x,y,z], ...] },
    { "id": "hippodrome", "type": "circus", "track_centerline": [[x,y],...], "lanes": 6, "seat_tiers": [...], "gates": [...] },
    { "id": "theatre",    "type": "theatre", "seat_tiers": [...], "stage": [[x,y],...] }
  ],
  "night_lights": [ { "pos": [x,y,z], "kind": "window|torch|lighthouse", "strength": 1.0 }, ... ],
  "landmarks":    [ { "id": "palace", "label": "Palace", "camera": { "target": [x,y,z], "dist": 18, "yaw": 210, "pitch": 35 } }, ... ],
  "events": [ "gladiator_games", "chariot_race", "theatre_play", "fleet_arrival", "festival_night" ]
}
```

### Shared sun-arc maths (same function in Python and C#)
Inputs: latitude φ, day of year N, solar hour h (0 to 24), north offset.
- Declination δ = 23.44° · sin(360°/365 · (N − 81))
- Hour angle H = 15° · (h − 12)
- Elevation = asin(sin φ sin δ + cos φ cos δ cos H)
- Azimuth (from north, clockwise) = atan2(sin H, cos H sin φ − tan δ cos φ) + 180°, then add the north offset

Put both versions under unit tests against the same table of expected values, so the Blender render and the Atlas view always agree.

---

## 4. Phases

Each phase ends in something visible. Don't start a phase until the one before it meets its acceptance check.

### Phase 0: Permanent home + repo (small)
**Done 2026-11-23:** the folder, the layout below and the copied source files. **Still to do:** `git init`, `.gitignore`/LFS, AGENTS.md/CLAUDE.md/README, and moving this file to `docs/PLAN.md`.
1. Create `~/PersonalProjects/TurntableAtlas/` and `git init`
2. Layout:
   ```
   TurntableAtlas/
     AGENTS.md  CLAUDE.md  README.md  docs/PLAN.md (this file)
     generator/        fantasy_capital.py  → refactor into package (Phase 1)
     blender/          fantasy_capital.blend, cinematic scripts, renders/
     atlas/            Godot 4.7 C# project
     cities/           exported city packages
     tools/            export_city.py, headless run scripts
   ```
3. Copy the `.blend`, `.py` and `renders/` out of the temporary folder **before that session is deleted**
4. Add a `.gitignore` (Godot `.godot/`, `bin/`, `obj/`, Blender `*.blend1`) and Git LFS for `.blend`, `.glb` and `.png`
- **Acceptance:** the repo exists, the original files are committed, and `blender -b blender/fantasy_capital.blend` opens cleanly

### Phase 1: Generator upgrades (foundation for both outputs)
1. **Review the existing hippodrome** (`hippodrome()`, line 1411; render `06_hippodrome.png`). Check it has a central spina (obelisks, turning posts), seat tiers, starting gates (carceres) and an imperial box, and add whatever is missing. Make sure its track centreline, seat tiers and gates can be emitted as anchors in step 3
2. **Stop merging the houses into one mesh.** Either split by district/chunk (about 8 to 16 chunks) or emit house **prototypes plus instance transforms**. Chunks help Godot culling and LOD; instances shrink the file
3. **Emit anchors** to the manifest and, in the `.blend`, as Empties/curves in a hidden `Anchors` collection:
   - Street graph built from AVENUES, ROADS and the gaps left between houses by the occupancy grid
   - Seat tiers for colosseum, hippodrome and theatre (rings of points with capacities), floor/track polygons, entrances
   - Ship lanes (harbour mouth between the moles, open sea, coast hops) and mooring spots (existing SHIPS placements)
   - Night light points: house windows (sample a subset), wall torches, lighthouse fires
   - Landmark camera presets
4. **Collision/LOD proxies:** a low-poly terrain (about 20k tris), box proxies for buildings, and simplified walls
5. **Headless build:** `tools/build_city.sh <city_id>` runs Blender `-b` to generate the `.blend` and the package in one go
- **Acceptance:** the hippodrome is visible in renders, the `Anchors` collection exists, `city.json` validates against the schema, and the build runs headless without errors

### Phase 2: Blender living-city cinematic
Build everything as **scripts** (`blender/cinematic/*.py`) driven by `city.json`, so it reruns on any city.
1. **Sun and sky.** A sun lamp driven by the shared sun-arc function, keyframed over the shot. Use Blender's physical sky (or a ramp-driven world for the painted look). Blend sun strength, colour temperature, ambient and haze from dawn to noon to dusk to night. Add a moon and a star dome at night
2. **Night lights.** Windows and torches emit by time of day (a driver on an emission strength attribute). Lighthouse fires flicker. Light the lamps in a staggered wave at dusk
3. **Clouds.** Low-poly cloud volumes or painted cards drifting on a wind vector, casting soft shadows
4. **Ships.** Follow-path constraints on the ship lanes with eased speed, plus bobbing/roll noise for moored ships. Galleys get rowing oar motion (simple rotation cycle)
5. **People (crowds).** Geometry Nodes: instance 2 or 3 tiny low-poly figure variants (about 0.1 m tall, 50 to 150 tris each, tinted with vertex colour) along street-graph curves with offset/speed noise. Fade density by time of day (busy at noon, sparse at night, crowds streaming to venues before events)
6. **Venues filling up.** Geometry Nodes fill on the seat-tier points. A `fill` value from 0 to 1 per venue reveals seats in a random order, so the venue fills over time. Add idle motion (bob, stand-up wave on cheers)
7. **Events (scripted keyframed sequences):**
   - *Chariot race:* 4 to 8 chariots follow the track centreline for 7 laps with speed variation, overtakes and a crowd wave at the finish
   - *Gladiator games:* fighter groups on the arena floor, a beast release from the entrances, crowd reactions
   - *Fleet arrival:* a fleet enters between the lighthouses and moors, and crowds gather on the quays
   - *Festival night:* a procession along the main avenue with torches, plus lanterns over the forum
8. **Ambient extras:** bath steam (existing `mat_steam`), chimney smoke, bird flocks, carts on the country roads
9. **Shot list** (cameras already exist as `CAP_Cam_*`):
   - 360° hero turntable, 20 s
   - Day-to-night timelapse from the hero angle
   - Harbour fleet arrival
   - Colosseum fill and games
   - Hippodrome race flyover
   - Top-down "map" shot, to match the Atlas world-map aesthetic
10. **Render settings:** EEVEE, 1920×1080 at 24 fps, motion blur on, and output a PNG image sequence (`blender/renders/<shot>/`) then encode with ffmpeg
- **Acceptance:** every shot renders headless from a script, nothing is hand-keyframed, and re-running on a regenerated city still works

### Phase 3: Export pipeline to Godot
1. `tools/export_city.py`: from the generated `.blend`, export `cities/<id>/city.glb` (glTF binary with vertex colours `COLOR_0`, no Blender shader nodes, proxies included with a `-colonly` suffix or as a separate glb), plus `city.json` and `thumb.png`
2. Bake anything the glTF can't carry (the terrain "zone" blend, haze) into vertex colours or a small texture
- **Acceptance:** dropping `cities/fantasy_capital/` into the Atlas loads the city with correct colours and collision

### Phase 4: Turntable Atlas (Godot 4.7 C#)
Project `atlas/`, mirroring `FOMSBattleSimulator` conventions (C#, Forward+, `AGENTS.md` rules, session cards).

**Scenes**
- `AtlasRoot`: app shell, holds the UI and swaps between WorldMap and CityView
- `WorldMap`: the Caelora map as a zoomable 2D map (or a 3D tabletop), with city pins from each `city.json` `world_map.pin_uv`. Hover shows the thumb; click loads the city
- `CityView`: the loaded city on a turntable base

**Systems (C# autoloads/components)**
1. **CityLoader:** loads a `cities/<id>/` package **at runtime** (`GLTFDocument`/`GLTFState`, so new cities need no editor re-import), builds collision from the proxies, and parses `city.json` into C# records
2. **TurntableCamera:** orbit (drag), pan (middle/right drag), zoom (wheel, eased), auto-rotate toggle, free-fly toggle (WASD), landmark jump buttons with smooth tweens, and min/max distance and pitch limits
3. **TimeOfDay:** hour from 0 to 24 with a playback speed (pause, 1 min/s, 1 h/s), the shared sun-arc function (C# port) driving a `DirectionalLight3D`, a `ProceduralSkyMaterial` or a custom sky shader, ambient/fog curves, and a moon light at night. Night-light points become a `MultiMesh` of emissive quads plus a few `OmniLight3D`s near the camera
4. **SunArc controls:** latitude, day of year and north offset sliders, a preview arc gizmo drawn over the city (a line with sunrise/noon/sunset markers), and a reset to the city's defaults
5. **Ambient life:**
   - *Ships:* `Path3D` per lane, ships on `PathFollow3D` with bobbing, spawn/despawn at the map edges
   - *People:* a `MultiMeshInstance3D` crowd on the street graph with a simple agent update (pick an edge, walk, repeat), a GPU-friendly vertex-shader walk bob and density by hour. Thousands of tiny figures are fine with MultiMesh; skip NavigationServer since the graph is already known
   - *Clouds:* drifting billboard or low-poly clouds plus a moving cloud-shadow texture projected on the terrain
6. **EventSystem:** data-driven (`events/*.json`). Each event is a timeline of steps: `fill_venue(colosseum, 0→1, 60s)`, `spawn_group(gladiators, floor)`, `race(hippodrome, chariots=6, laps=7)`, `crowd_reaction(cheer)`, `empty_venue(...)`. Triggered from UI buttons or scheduled by time of day (for example, games start at 14:00). Crowds stream from spawn zones to venue entrances before the fill
7. **UI:** side panel with a time slider, speed, sun-arc controls, event buttons, layer toggles (people, ships, clouds, labels, night lights), a landmark list, a "Back to world map" button and a screenshot button
8. **Performance budget:** 60 fps on the user's Mac. The city is about 480k tris now; with chunking and LOD aim for under 300k visible, people as MultiMesh (under 5k instances), and at most 16 dynamic lights

- **Acceptance:** open the app, pick Fantasy Capital on the map, orbit around it, scrub dawn to night, change the latitude and see the arc change, press "Chariot Race" and watch the hippodrome fill and the race run, then go back to the map

### Phase 5: More cities
1. Parametrise the generator: move layout constants (coast, walls, roads, landmarks, venues, ships) into a per-city config (`generator/cities/<id>.toml|json`). `fantasy_capital` becomes the first config
2. Add city archetypes (river city, mountain fortress, desert city, island port) that reuse the building kit with different layouts and palettes
3. Each new city = a config, then `tools/build_city.sh <id>`, then a package in `cities/`, which then appears on the world map automatically
- **Acceptance:** a second city builds, exports and loads in the Atlas with no code changes

---

## 5. Suggested session breakdown
| # | Session | Depends on | Size |
|---|---|---|---|
| S0 | Phase 0: repo + copy files | none | small |
| S1 | Phase 1.1: review/extend the existing hippodrome | S0 | small |
| S2 | Phase 1.2–1.5: split meshes, anchors, manifest, proxies, headless build | S1 | large |
| S3 | Phase 2.1–2.3: sun/sky/night lights/clouds (Blender) | S2 | medium |
| S4 | Phase 2.4–2.6: ships, crowds, venue fill (Blender) | S2 | large |
| S5 | Phase 2.7–2.10: events + shot list + renders | S3, S4 | large |
| S6 | Phase 3: glTF export pipeline | S2 | medium |
| S7 | Phase 4: Atlas shell, loader, camera, time/sun | S6 | large |
| S8 | Phase 4: ambient life + events + UI | S7 | large |
| S9 | Phase 4: world map + city switching | S7 | medium |
| S10 | Phase 5: generator parametrisation + second city | S2 | large |

The Blender cinematic (S3–S5) and the Atlas (S6–S9) can run in parallel once S2 is done.

---

## 6. Open decisions (ask the user at the start of the relevant phase)
1. Are these cities in the Caelora world?
2. Is the hippodrome another session built on the harbour quay final, or will that session keep changing the city? If it is still running, sync its latest `.blend`/`.py` before Phase 1
3. City names and real-world latitude for the sun arc (default 38°N, Mediterranean)
4. Art direction for people and night: stylised painted miniature (matching the current look) or more realistic
5. Is the cinematic the priority, or the Atlas? (The plan supports either order after S2)
6. Which events matter most beyond games, races, fleet and festival (a triumph parade? a fire? a siege?)
7. World-map style: flat painted Caelora map or a 3D tabletop with cities as mini dioramas
