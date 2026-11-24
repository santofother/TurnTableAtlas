# Decisions on the plan's open questions

Taken on 2026-11-23 so the sessions could run unattended. Each is a default; change it and the cards that
depend on it say what to rerun.

| # | Question (PLAN §6) | Decision | Affects |
|---|---|---|---|
| 1 | Are these cities in the Caelora world? | **Yes.** Pins sit on `CaeloraMapv3.png` (copied to `atlas/assets/map/`). Pin positions are `LORE?` placeholders until you place them. | S9 |
| 2 | Is the hippodrome final? | **Yes, treated as final.** This repo's generator is now the only copy that changes. | S1 |
| 3 | City names and latitude | Fantasy Capital (`LORE?` name), **38°N**, day 172. Second city: *Thalassa Minor* (`LORE?`), **31°N** (a hotter, southern island port). | S2, S10 |
| 4 | Art direction for people and night | **Stylised painted miniature**, matching the current renders: tiny low-poly figures tinted by vertex colour, warm window glow, no realistic humans. | S3, S4, S8 |
| 5 | Cinematic or Atlas first? | **Both, in the plan's order** (S3–S5 then S6–S9); they only share S2's package. | all |
| 6 | Events beyond the core four | Core five only: gladiator games, chariot race, theatre play, fleet arrival, festival night. A triumph parade reuses the festival procession data. | S5, S8 |
| 7 | World-map style | **Flat painted Caelora map**, zoom and pan, with pins. A 3D tabletop can come later. | S9 |

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
- **Atlas performance settings:** FSR 1 at 0.7 render scale, 4k directional shadows, SSAO, MSAA 2×: 72-93 fps at
  1600×900 with life and an event running.
