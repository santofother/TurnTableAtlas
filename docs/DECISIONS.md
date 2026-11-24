# Decisions on the plan's open questions

Taken on 2026-11-23 so the sessions could run unattended. Each is a default; change it and the cards that
depend on it say what to rerun.

| # | Question (PLAN §6) | Decision | Affects |
|---|---|---|---|
| 1 | Are these cities in the Caelora world? | **Yes.** Pins sit on `CaeloraMapv3.png` (copied to `atlas/assets/map/`). Pin positions are `LORE?` placeholders until you place them. | S9 |
| 2 | Is the hippodrome final? | **Yes, treated as final.** This repo's generator is now the only copy that changes. | S1 |
| 3 | City names and latitude | Fantasy Capital (`LORE?` name), **38°N**, day 172. ~~Second city: *Thalassa Minor*~~: removed 2026-11-23 at the user's request (it read as a copy of Calderra); its config is kept as `docs/new_city/example_layout.json`. New cities come from briefs (`docs/new_city/README.md`). | S2, S10 |
| 4 | Art direction for people and night | **Stylised painted miniature**, matching the current renders: tiny low-poly figures tinted by vertex colour, warm window glow, no realistic humans. | S3, S4, S8 |
| 5 | Cinematic or Atlas first? | **Both, in the plan's order** (S3–S5 then S6–S9); they only share S2's package. | all |
| 6 | Events beyond the core four | Core five only: gladiator games, chariot race, theatre play, fleet arrival, festival night. A triumph parade reuses the festival procession data. | S5, S8 |
| 7 | World-map style | ~~Flat painted Caelora map~~ → **3D world map** (S11): the painted Geography map lying flat on a board, and the Known World relief baked from `KnownWorld.blend` (its own materials, unlit; 1 unit = 10 miles; 15× relief), in one frame, with clouds, weather and time of day. | S9, S11 |
| 8 | Landric's villa (S16) | **An estate, not a city**: own builder `generator/villa.py` (`"kind": "estate"` in the config and `city.json`), 300 m plinth (`model_scale` 3). Site: the user's X north-north-west of Calderra (Known World 107.65, 147.95), moved there from the peninsula at the user's request. On the Known World it stands as its own `city.glb` at 12× true size on a hero patch with hills (`EstateSite.cs`). Late October at 38°N. | S16 |
| 9 | Karn Ashur and the High Dunes (city `karn_ashur`) | **A metropolis, not a Roman city**: own builder `generator/metropolis.py` (`"kind": "metropolis"`), 20 km plinth at 1:200 centred on `settlement:karn_ashur`, the brief's km layout verbatim. First Flame summit **3,700 m** (lore 3,695 m), eastern peak 3,380 m, the rivers' confluence 1,046 m, the city's terraces 1,200–1,550 m, the outlet leaves at ~944 m. The model's ground is drawn **1.8× higher** about 1,000 m (a diorama's relief; buildings keep true heights; `terrain_height.png` stays true for the map). **15.8°N** (the Known World graticule: it is off Caelora), **day 75** (snow on the peaks, the snowmelt rivers full, the fields green). ~52k courtyard houses + 3.5k towers ≈ **580k** people at 4.5 a storey. On the Known World the package stands at **6× true size** (as W5's miniature) on a hero patch of half 5.2 units, at the relief's 15×; W5's ring city is removed. The brief's regional traces are graded downhill by a running minimum (cuts ≤ 60 m); the southern trace crossed the old cone under the patch, so it is split into the eastern tributary (to the patch) and the southern river (below it, joined by the basin's outlet). The High Dunes' other summits are capped at **2,950 m**, under the 3,050 m snow line, so Karn Ashur's two peaks are the only snowy ones and the western the largest ("the largest of the High Dunes' snow-crowned peaks"). ~320 villages at 750 people and 6 market towns ≈ **290k** people in the valleys. The grain route: the delta→Qasr Samir shipping route, then the brief's caravan corridor to the freight road. | S-city, W5 |

Other defaults taken while building:
- **Git LFS** tracks `.blend`, `.glb`, `.png`, `.jpg`, `.mp4`, `.exr`. There is no remote yet; nothing is pushed.
- **No ffmpeg on this Mac**: shots are encoded to H.264 `.mp4` by Blender's own FFmpeg (VSE) in `tools/render_shot.sh`.
- **Windows at night** are carried in the vertex-colour alpha (`Col.a < 1` = window, its value = light-up order),
  so Blender and Godot light the same windows in the same order from one attribute.
- **Renders** are 1920×1080, 24 fps, EEVEE 32 samples with motion blur (about 1-2 s per frame on the M1 Pro);
  `--preview` is 960×540, 12 samples, no blur. Event shots are tuned for Fantasy Capital's layout.
- **Race length:** the Atlas runs 5 laps at about 1.9 model-m/s (roughly 2.5 min with the fill); the film runs
  2 laps in 24 s. `laps` in the manifest (7) is the historical figure; `atlas/events/chariot_race.json` sets the shown laps.
- **Speeds at 1:15:** people stroll at 0.09-0.15 model-m/s (real time); ships 1.1-1.5 model-m/s; clouds drift faster
  when the clock runs fast.
- **Karn Ashur's instances:** houses, terraces, walls, awnings, domes, camels and trees are records in
  `instances.bin` (11 float32 each) drawn with GPU instancing from prototypes in `city.json` (city view and map
  alike); the `.blend` has them as real meshes in the `Instanced` collection, which the glTF export leaves out.
  `*.bin` is tracked by Git LFS. People in the 1:200 city view are drawn at 0.3× Calderra's figure size (about 4×
  true); the cinematic shots skip crowds and ships on a metropolis.
- **Atlas performance settings:** FSR 1 at 0.7 render scale, 4k directional shadows, SSAO, MSAA 2×: 72-93 fps at
  1600×900 with life and an event running.
