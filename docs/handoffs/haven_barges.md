# Haven: royal palace, flowing red river, grain barges (follow-up to city-haven)

**Status: DONE.** Branch `haven-barges`, `tools/run_tests.sh` all green.

## What landed
- **Royal palace** (`generator/cities/haven.json` `great_pyramid.royal`, `rivercity.py` `royal_court`): the Great Pyramid
  is 840 m across, 285 m high, 9 tiers, with a gilded frieze and a colonnade on every tier, a white throne hall under a gold
  dome on the summit, and its own walled court (merlons, gilded corner bastions, a pylon gate on the processional way,
  three lesser gates, colonnades, palm gardens, pools, an avenue of gilt-capped obelisks, courtiers' halls).
- **River** (`atlas/shaders/river_flow.gdshaderinc`): silt clouds, streaks and foam threads drift downstream, wavelets run
  with the current, the shallows are paler. City view: `water.gdshader` (the river mesh now carries UV across/downstream
  and Col.b = 0 for "flowing"). Known World: the new `flame_river.gdshader` on FlameValley's reaches and Haven's patch.
- **Barges** (`atlas/src/Core/RiverBarges.cs`, `atlas/src/Game/BargeFleet.cs`): laden grain barges (`barge_grain`) run
  downstream in the lane east of the middle, empty sailing barges (`barge_empty`) run upstream in the west lane. Each lane
  moves at one speed with gaps of at least `min_gap`, so barges never close up; the generator checks the lanes against the
  banks, the bridge piers (the lanes pass through the arches at +-75 m), the water gates' booms (now open in the middle)
  and the moored barges. City view: `city.json` `river_traffic` (46 barges). Known World: 300 along the whole Flame,
  through Haven's patch to the sea, shown when the camera is within 30 units. Moored and harbour barges get their own slots.
- New city landmark `barges` (a close view of the river at the granary quays).
- FIX(haven) in `Basin.cs`: stacked instances (pyramid tiers) keep their height on the Known World (they were flat slabs).

## Check
`$GODOT --path atlas -- --city=haven --landmark=barges` (or `great_pyramid`); Known World:
`--orbit=178.2,63.29,0.03,-150,28,0.75`. Shots: `haven_palace.jpg`, `haven_river.jpg`.

## Left / LORE?
Palace court layout and the gate forms are proposals (LORE?). Known World barges are at the miniature's true scale (small).
