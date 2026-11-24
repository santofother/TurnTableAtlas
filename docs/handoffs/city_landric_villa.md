card: S16 / new city `landric_villa` (Prince Landric's villa, an *estate*)
status: DONE · date: 2026-11-24 · branch `city-landric_villa` (S15's design docs + main merged in)

**Landed**
- `generator/villa.py` (new estate builder, `"kind": "estate"`; `build_city.py` dispatches to it). 300 m plinth, `model_scale` 3,
  ~357k tris, builds in 2 s (9 s with export). A two-storey villa round an open peristyle (40 columns, 12 statues, fountain,
  lemon trees). South range: great hall (long table, fireplace), granite entry with two rearing-horse inlays, private dining
  (hearth). North range: Landric's gallery with *Duel Before The Walls*. East range: kitchen and stores. West range: sitting
  room, library and stair. Bedrooms upstairs. Outside: stables with six horses, hay shed, the gate with its pediment and lamps,
  the kitchen garden, the two-pool bathhouse with its firebox, an annex, ~5,400 vine-row pieces, a lake with a riding path,
  a jetty, a fenced lane with lamp posts and the road to Calderra. 114 windows light in a wave from the gate.
- `city.json` adds `kind`, `anchors` (14, from the motion brief), `cutaway`, `terrain_grid` and `world_map.miniature`
  (`docs/city_schema.md`), plus 7 routes (peristyle_loop, lagoon_riding_loop, garden_to_bath…). No events.
- Atlas: in the city view, Layers → **Roofs / Upper floor** gives the cutaway. People are drawn at the model's scale
  (`Swarm.FigureScale`, 9 household walkers). On the Known World, `Core/EstateSite.cs`, `Game/Estate.cs` and
  `estate_ground.gdshader` add a patch with the plinth's own ground, hills and the lake. The package's `city.glb` stands
  on it at 12× true size (0.22 units across), and `relief.gdshader` gets a `hole2`. New view: Views → "Landric's Villa".
  New flag: `--estates=off`.

**Check:** `tools/run_tests.sh` is green: Python (new estate test), 31 xUnit (3 new), both smoke runs. Look at
`city_landric_villa.jpg` (Blender hero | cutaway, Atlas arrival at dusk | map miniature), or run
`$GODOT --path atlas -- --city=landric_villa --landmark=gallery` and `$GODOT --path atlas -- --view=CAM_Estate_landric_villa`.

**LORE?** The site and its distance from the palace, and the lake (named only "lake/lagoon"). The room plan: the gallery in
the north range, the kitchen in the east range, the bedroom positions. Whether the wall encloses the stables and the garden
(here it does). Where the bath spring rises. Cassian's horse colour. The household's number.
**Gaps / next:** the four Chapter 1 sequences (arrival, supper, peristyle and Aegis, cold spring) as Atlas events and
Blender shots on the anchors; horses that walk the `stable_route` / `lagoon_riding_loop`; lamp glows on the map
miniature; only one estate can cut a hole in the map relief (`hole2`); statues and the painting are blocky at close range.
