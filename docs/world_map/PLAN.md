# Known World map: round 2 plan

Changes to the Atlas's 3D Known World map (built in S11). Reference images:
`docs/world_map/caelora_reference_map.webp` (the painted Caelora map, the target for terrain and borders) and
`briefs/karn_ashur/concept_valley.webp` (Karn Ashur concept).

## How the map is made (why the cards are split this way)
- **Source:** `~/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend`, which holds the terrain (`T_TerrainData`
  heights), water, realms and lore table. `tools/bake_known_world.py` reads it (never saves it) and writes
  `atlas/assets/map/known_world/` (albedo, height, json).
- **Atlas side:** `atlas/src/Game/WorldMap.cs`, `relief.gdshader`, the board under the map and `shipping_routes.json`.
- So **terrain, sea and border changes are edits to the blend, followed by a rebake**, and the board or table is
  Godot only. Cards that edit the blend run **one at a time**. The table card and Karn Ashur can run alongside them.

## Rules for blend-editing cards (W2–W4)
1. Before the first edit, copy the blend to `KnownWorld.<date>.bak.blend`. Never edit without a backup.
2. Make changes with a script you can run again (`tools/kw_edits/<card>.py`, run with `$BLENDER -b <blend> --python`).
   Don't hand-paint anything. The script saves the blend.
3. Rebake (`$BLENDER -b .../KnownWorld.blend --python tools/bake_known_world.py`), then run `tools/run_tests.sh`.
4. Take one before/after screenshot from the same `CAM_*` view and put it in the handoff.

## Cards
| Card | Change | Touches | Depends on |
|---|---|---|---|
| W1 | **Map table, CK3 style.** Replace the plain board and the blue void around it with a 3D war table: a carved wood frame with a raised bevelled rim, a parchment or cloth edge, and the table top running out of view. Add props (candles that light up at night, a brass compass, map weights, scattered markers), a warm room light with falloff, and a dark vignette in place of the blue light. Both map modes sit on the same table. The camera can't go under it. | `WorldMap.cs` (board section), new `MapTable.cs`, new shaders/assets under `atlas/assets/map/table/` | none |
| W2 | **Terrain: Oravian Expanse and Dovaran Crown.** Raise the Oravian Expanse (between Astera, Madravella and Calleway) into rugged hills and low mountains that meet the Veryan Range, as on the reference map. Recut the Dovaran Crown coast as fjords: long, narrow, steep inlets and skerries, keeping Dovehall's site. | blend heights and land/sea masks, `tools/kw_edits/w2_terrain.py` | none |
| W3 | **Sea colour round Dovaran Crown.** Remove the odd blue rectangle (S11 noted "a faint darker sea rectangle near Dovehall, from the blend's water data"). Find the sea patch or texture causing it and make it match the open sea's depth gradient. As a fallback only, correct it in `relief.gdshader`. | blend water, maybe `relief.gdshader` | W2 (the fjords change the coastline) |
| W4 | **Salmara–Calderra border.** Make the two realms share one border along the river (the river is the line), with no unclaimed strip. First find where borders come from (blend realm data, or `FOMSMap/political-overlay/map_config.py` for the painted map) and fix it at the source. Check the other realm pairs for the same gap and list them. | blend realm data / `political-overlay`, rebake | W2 |
| W5 | **Karn Ashur matches the concept.** Two layers. (a) **On the map:** a mountain-ringed valley with waterfalls, a round walled inner city around a lake with a stepped ziggurat temple on an island, fields inside the walls, a dense sandstone outer city, aqueducts, and a switchback road to a hilltop shrine. Build it as a hero patch or settlement model at Karn Ashur's site. (b) **Later, optional:** a full city package through `/new-city karn_ashur` (brief folder already holds the concept image). | (a) blend hero patch or `WorldMap.cs` settlement model; (b) its own S-card | (a) after W2 if it changes terrain |

**Order:** W1 and W5a can start now, in parallel. W2 → W3 → W4 run in sequence because they share the blend.

## Open questions (answer at the start of the card; defaults in brackets)
- W1: wood tone and props? [dark walnut, brass, candles; no figurines]
- W2: how high is the Oravian Expanse? [hills to 1,500 m, below the Veryan snowline]
- W4: does the river belong to one realm or mark the border? [it marks the border]
- W5: is Karn Ashur in the Caelora lore at the site the blend uses? [keep the blend's site; `LORE?` anything new]
