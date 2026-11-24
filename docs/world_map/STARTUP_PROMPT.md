# Startup prompt: future world-map changes

Paste the block below into a new Claude Code (or Codex) session and fill in the list.

---

I want to change the Known World map in the Turntable Atlas.

**Changes:**
1. <what, where on the map (realm / place name), and what it should look like>
2. ...

**References:** <image paths; put them in `docs/world_map/refs/`>

Before you start:
- Read `AGENTS.md`, `docs/world_map/PLAN.md` (how the map is built, plus the rules for editing the blend) and the
  latest `docs/handoffs/W*.md` and `S11.md`.
- Work out which layer each change belongs in: the **source blend** (terrain, sea, rivers, borders, settlements:
  edit by script, back it up first, then rebake) or the **Atlas** (`WorldMap.cs`, shaders, table, UI, labels).
- Add the changes to `docs/world_map/PLAN.md` as new W-cards (next free number), with dependencies. Anything that
  edits the blend runs in sequence; everything else can run in parallel.
- Show me the cards and any open questions (with your defaults) **before** building anything. Then run the cards
  one by one: branch `wNN-name`, `tools/run_tests.sh`, a before/after screenshot from the same `CAM_*` view,
  a handoff in `docs/handoffs/WNN.md`, and a commit.
- Mark any name or lore fact that isn't settled as `LORE?` (the lore lives in `~/PersonalProjects/FOMSMap`).
