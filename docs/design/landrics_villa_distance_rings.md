# Calderra: 30 and 35 mile rings

![Annotated Atlas screenshot](landrics_villa_distance_rings.png)

The background is an actual 1600 × 900 screenshot of the Turntable Atlas **Known World** map, focused over Calderra at 15:00. The cloud layer was hidden only for this capture so the shore and roads remain visible. The unannotated [capture](landrics_villa_calderra_map_capture.png) is retained beside the overlay.

The [SVG overlay](landrics_villa_distance_rings.svg) preserves the exact vector circles; `draw_distance_rings.swift` regenerates the PNG from the capture.

## Scale and construction

- `atlas/assets/map/known_world/known_world.json` gives `unit_m = 16093.4404`: **one map unit = ten miles**.
- Calderra's settlement UV is `[0.42788, 0.41597]`; using bounds `[-185, -62, 500, 295]`, its map position is approximately **(108.0978 east, 146.4987 north)** in map units.
- The camera capture targets that point at near-vertical pitch (89°), distance 13 units, with 40° vertical field of view. At 1600 × 900, the center scale is about **95.105 pixels per map unit**.
- Therefore the **30-mile** ring is 3 units, about **285.315 pixels** in radius; the **35-mile** ring is 3.5 units, about **332.867 pixels**. The overlay is centered on the Calderra target at `(800, 450)`.

These are **straight-line map distances from Calderra's settlement pin**, not measured road routes from the palace gate. A four-to-six-hour, roughly 30–35-mile horseback journey can end **inside** the corresponding ring if the road bends. The chapter establishes a west-gate departure, passage through a village near the second river, vineyards and a nearby lagoon; it does not identify which lake or a precise villa site. The rings therefore delimit a search area, not a chosen location.
