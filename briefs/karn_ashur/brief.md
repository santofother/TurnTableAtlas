# City brief: Karn Ashur and the High Dunes (`karn_ashur`)

A large inland trade and pilgrimage metropolis in a red-cliff basin between two snow peaks, and the High Dunes round
it. Sources: the user's build prompt (2026-11-24, summarised below), the concepts and the planning geometry in
`red-cliff-metropolis/` (`01`–`04` views, `05-known-world-overhead.png`, `05-map-coordinates.json`), the earlier
`visual-studies/` and `concept_valley.webp`, `high-dunes-drainage.html`, and the Karn Ashur and High Dunes Atlas
entries (`The Histories/Quadria/The Dune Sea Chronoicles/`). Supersedes card W5's ring city on the Known World.

## 1. Where in the world
- `settlement:karn_ashur` on the Known World (off the painted Caelora map), unchanged; Qasr Samir stays on its harbour.
- Realm: the neutral temple-city of the Ashen Order, inside High Dunes territory without answering to it.

## 2. The pitch (the prompt, in short)
- **World overview:** the High Dunes read as a broad mountain region with two prominent snowy summits, red rock, sand
  at the mountains' feet, narrow green valleys; the grain route from the River Flame delta by sea to Qasr Samir and
  overland to Karn Ashur, clear at every zoom.
- **Regional terrain:** two rocky peaks framing a red-cliff basin (the higher western one carries the First Flame, the
  eastern one has the sharper skyline), cliff terraces, sand aprons, a gradual north-west caravan approach and a
  separate steep pilgrims' trail from Al-Mirah; tributaries that meet below the city and drain south / south-east
  into the farm belt, a northern river to the Gulf of Qamar west of Qasr Samir, a seasonal wadi to the south-west;
  villages, mills, weirs, fields, orchards and market towns on the valley benches: ~300,000 people across the valleys.
- **The city package:** ~500,000 people on ~30 km² of dense two- to four-storey adobe and sandstone courtyard
  terraces; grain warehouses, shaded markets, caravanserais and animal yards at the north-west freight entrance;
  houses above the floodplain, bridges, canals to the lower fields; Al-Mirah a modest spring shrine among palms; the
  Library on a civic terrace; the market → spring → First Flame route legible. Three views: the caravan arrival, the
  terraced neighbourhoods, downstream over the farming villages.

## Agent's reading
- **References:** `01` caravan approach (freight yards with camels and awnings in front, the striated western massif
  left, the snow peaks behind, an ocean of roofs); `02` metropolitan aerial from the SSE (raised terraces, the river's
  gravel floodplain with bridges, canal-fed fields at the edges, Al-Mirah at the foot of the western massif);
  `03` farm belt (river with weirs and a mill, villages and tree lines, the city far off); `04` northern trade valley
  (a separate river to the lowland, a market town on a dry terrace); `05` the overhead plan and its coordinates.
- **Build:** new generator work, `generator/metropolis.py` (`"kind": "metropolis"`): the Roman city generator has no
  inland basin, no adobe terraces and no 20 km plinth. Plinth 20 km (`model_scale` 200), the brief's km layout
  verbatim in `generator/cities/karn_ashur.json`. Houses, terraces and trees are *instances* (`instances.bin`).
- **Map:** the package itself stands on the Known World at 6× true size (`Core/BasinSite.cs`), so the map and the city
  view are one layout; the region round it (rivers, villages, towns, the grain route) is `Core/HighDunesRegion.cs`
  over `atlas/assets/map/known_world/high_dunes.json` (the brief's regional geometry).
- **Choices** (no questions asked; recorded in `docs/DECISIONS.md` #9): see the handoff `docs/handoffs/city_karn_ashur.md`.
