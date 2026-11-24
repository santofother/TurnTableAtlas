# Turntable Atlas

A living miniature city (about 1:15 scale) built by one procedural generator and shown two ways:

- **Cinematic** (Blender 5.2, EEVEE): turntables, day-to-night timelapses, a fleet arrival, games and a chariot race.
- **Atlas** (Godot 4.7 C#): spin and zoom around a city, scrub the time of day, change the sun's arc,
  trigger events, and switch cities from the Caelora world map.

Start with `docs/PLAN.md` (the plan), `docs/DECISIONS.md` (the defaults taken) and `AGENTS.md` (how to work here).

## Quick start
```bash
tools/run_tests.sh                        # python + C# tests, headless Godot smoke run
tools/build_city.sh fantasy_capital       # regenerate blender/fantasy_capital.blend and cities/fantasy_capital/
tools/render_shot.sh hero_turntable       # render and encode one cinematic shot
/Applications/Godot_mono.app/Contents/MacOS/Godot --path atlas   # run the Atlas
```

## Adding a city
1. Write `generator/cities/<id>.json` (copy an existing one; layout, landmarks, palette, sun, map pin).
2. `tools/build_city.sh <id>`: this writes `blender/<id>.blend` and the package `cities/<id>/`.
3. Start the Atlas: the new pin appears on the world map. No code changes.
