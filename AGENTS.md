# Turntable Atlas: rules for every coding agent

Read this whole file at the start of every session (Claude Code and Codex both do). The full plan is
`docs/PLAN.md`; the decisions taken on its open questions are in `docs/DECISIONS.md`.

**What this is:** one procedural city generator (Python, runs inside Blender) feeds two outputs:
- **A. Living-city cinematic** (Blender 5.2, EEVEE): script-driven turntables, timelapses and event shots.
- **B. Turntable Atlas** (Godot 4.7 C#, Forward+): a desktop viewer that loads *city packages* at runtime.

Both read the same per-city manifest `cities/<id>/city.json`. Neither side hand-places anything.

## Layout
| Path | What | Owner card |
|---|---|---|
| `generator/` | `fantasy_capital.py` (the builder; `apply_config()` loads a city's layout), `anchors.py`, `sunarc.py`, `figures.py`, `build_city.py`, `cities/<id>.json` configs | S1, S2, S10 |
| `blender/cinematic/` | shot scripts driven by `city.json` | S3–S5 |
| `blender/renders/<shot>/` | encoded shots (`.mp4`) and stills; frame sequences are gitignored | S5 |
| `tools/` | `build_city.sh`, `export_city.py`, `render_shot.sh`, `run_tests.sh` | S2, S6 |
| `cities/<id>/` | city package: `city.glb`, `terrain_albedo.png`, `city.json`, `thumb.png` | generated |
| `atlas/` | Godot project; pure logic in `atlas/src/Core` (no Godot refs), tests in `atlas/tests` | S7–S9 |
| `tests/` | Python tests (sun arc, manifest schema) | S2 |
| `briefs/<id>/` | a new city's brief and reference images (the user's) | |
| `docs/new_city/` | **the new-city startup prompt** (`README.md`), brief template, full layout example | |

## Coordinates (contract)
- Generator / Blender / `city.json`: metres, **+X east, +Y north, +Z up**, sea level Z = 0, model spans [-50, 50].
- Godot: **+X east, +Y up, -Z north**. Convert with `godot = (x, z, -y)` (that is what glTF export does too).
- Headings in `city.json` are degrees counter-clockwise from +X (Blender convention).

## A session, every time
1. Read this file and your card in `docs/sessions/README.md`, plus the handoffs of the cards it depends on.
2. Work on branch `sNN-short-name`; fast-forward `main` when green.
3. Edit only files your card owns (plus tests and your handoff). Mark unavoidable outside fixes `# FIX(Sxx): why`.
4. Run `tools/run_tests.sh`. Everything must pass.
5. Write `docs/handoffs/Sxx.md` (max ~25 lines: status, what landed, how to check it, what's left).
6. Commit. Never force-push, never rewrite history.

## Commands
```bash
export DOTNET_ROOT="$HOME/.dotnet" PATH="$HOME/.dotnet:$PATH" DOTNET_CLI_TELEMETRY_OPTOUT=1
export GODOT=/Applications/Godot_mono.app/Contents/MacOS/Godot
export BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
```
| What | Command |
|---|---|
| All tests | `tools/run_tests.sh` |
| Rebuild a city (blend + package) | `tools/build_city.sh fantasy_capital` |
| Render a cinematic shot | `tools/render_shot.sh hero_turntable [--preview]` |
| Run the Atlas | `$GODOT --path atlas` |

## Token rules
- Edit `.py`, `.cs`, `.tscn`, `.json`, `.gdshader` as text. Never open the Godot editor GUI.
- Prove things with tests and logs; screenshots only for visual cards, few and small.
- Stuck after ~3 attempts on the same problem: stop and write `status: PARTIAL` in the handoff.

## New cities
Building a city from a brief? Read `docs/new_city/README.md` first (Claude Code: `/new-city <id>`).

## Lore
Cities sit in the Caelora world (`~/PersonalProjects/FOMSMap`). If a card needs a name or fact that
isn't decided, use a placeholder marked `LORE?` and list it in the handoff.
