# Decisions on the plan's open questions

Taken on 2026-11-23 so the sessions could run unattended. Each is a default; change it and the cards that
depend on it say what to rerun.

| # | Question (PLAN §6) | Decision | Affects |
|---|---|---|---|
| 1 | Are these cities in the Caelora world? | **Yes.** Pins sit on `CaeloraMapv3.png` (copied to `atlas/assets/map/`). Pin positions are `LORE?` placeholders until you place them. | S9 |
| 2 | Is the hippodrome final? | **Yes, treated as final.** This repo's generator is now the only copy that changes. | S1 |
| 3 | City names and latitude | Fantasy Capital (`LORE?` name), **38°N**, day 172. Second city: *Thalassa Minor* (`LORE?`), **31°N**, day 200 (a hotter, southern island port on the south-west island). | S2, S10 |
| 4 | Art direction for people and night | **Stylised painted miniature**, matching the current renders: tiny low-poly figures tinted by vertex colour, warm window glow, no realistic humans. | S3, S4, S8 |
| 5 | Cinematic or Atlas first? | **Both, in the plan's order** (S3–S5 then S6–S9); they only share S2's package. | all |
| 6 | Events beyond the core four | Core five only: gladiator games, chariot race, theatre play, fleet arrival, festival night. A triumph parade reuses the festival procession data. | S5, S8 |
| 7 | World-map style | **Flat painted Caelora map**, zoom and pan, with pins. A 3D tabletop can come later. | S9 |

Other defaults taken while building:
- **Git LFS** tracks `.blend`, `.glb`, `.png`, `.jpg`, `.mp4`, `.exr`. There is no remote yet; nothing is pushed.
- **No ffmpeg on this Mac**: shots are encoded to H.264 `.mp4` by Blender's own FFmpeg (VSE) in `tools/render_shot.sh`.
- **Windows at night** are carried in the vertex-colour alpha (`Col.a < 1` = window, its value = light-up order),
  so Blender and Godot light the same windows in the same order from one attribute.
