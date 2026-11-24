# Turntable Atlas

A living miniature city (about 1:15 scale) built by one procedural generator and shown two ways:

- **Cinematic** (Blender 5.2, EEVEE): turntable, day-to-night timelapse, fleet arrival, games, chariot race,
  festival night, theatre play, top-down map. Everything is scripted from the city manifest; nothing is hand-keyed.
- **Atlas** (Godot 4.7 C#): spin and zoom around a city, scrub the time of day, change the sun's arc
  (latitude, season, north), trigger events, toggle layers, and switch cities from the Caelora world map.

Start with `docs/PLAN.md` (the plan), `docs/DECISIONS.md` (the defaults taken), `AGENTS.md` (how to work here)
and `docs/handoffs/` (what each session landed, with screenshots).

## Quick start
```bash
tools/run_tests.sh                                   # python + C# tests, Atlas build, headless self-test per city
/Applications/Godot_mono.app/Contents/MacOS/Godot --path atlas     # run the Atlas (needs DOTNET_ROOT, see AGENTS.md)
tools/build_city.sh fantasy_capital                  # regenerate blender/<id>.blend and the package cities/<id>/
tools/render_shot.sh list                            # the cinematic shot list
tools/render_shot.sh hero_turntable                  # render + encode one shot (add --preview for half res)
tools/render_all.sh                                  # every shot (~1.5-2 h on an M1 Pro)
```
Rendered shots land in `blender/renders/<shot>/<shot>.mp4`.

## In the Atlas
- **Camera:** drag to orbit, right-drag to pan, wheel to zoom, double-click to focus, R auto-rotate,
  F free-fly (WASD, Q/E), Places buttons fly to landmarks, Esc back to the map, F12 screenshot.
- **Time:** slider plus Pause / 1 min/s / 10 min/s / 1 h/s. Events also start by themselves at their hour while
  time plays (games 14:00, race 16:00, play 18:00, fleet 09:00).
- **Sun arc:** latitude, day of year and north offset; "Show sun path" draws today's arc with sunrise/noon/sunset.
- **Events:** Chariot Race, Start Games, Theatre Play, Fleet Arrives, Festival Night (data in `atlas/events/*.json`).
- Command-line flags for testing: `--city=<id> --hour=19.5 --landmark=forum --event=chariot_race --event-speed=5
  --arc --shots=3,6 --quit-after=8 --selftest`.

## Cities
| id | what | latitude |
|---|---|---|
| `fantasy_capital` | crescent harbour capital: palace headland, colosseum, hippodrome, theatre, baths, aqueduct | 38°N |
| `thalassa_minor` | whitewashed island port: acropolis, theatre, amphitheatre, lighthouse moles | 31°N |

Names and map pins are `LORE?` placeholders (see `docs/DECISIONS.md`).

## Adding a city
1. Copy `generator/cities/thalassa_minor.json` to `generator/cities/<id>.json` and edit it: `layout` (coast, walls,
   gates, avenues, landmarks list, terrain hills, palette, ships), `spawn_zones`, `ship_lanes`, `routes`,
   `landmarks` (camera presets), `events`, `sun`, `world_map.pin_uv`.
2. `tools/build_city.sh <id>` (about 15-30 s): writes `blender/<id>.blend` and `cities/<id>/`.
   `$BLENDER -b --factory-startup --python tools/debug/anchor_map.py -- <id> out.png` draws streets, lanes,
   zones and routes over the walk grid while you tune the layout.
3. Start the Atlas: the new pin is on the world map. No code changes.
