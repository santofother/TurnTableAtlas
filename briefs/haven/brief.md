# Haven, capital of Hamen — visual concept brief

Status: concept only. The images are design references for a later Blender build, not settled geography or a city config.

## Canon from the supplied texts

- Haven is Hamen's capital on the River Flame floodplain, upriver from the coast. River barges, caravan roads, grain trade, and an inland harbor meet here.
- Erros the Founder built an inner city and began a vast outer wall. The outer enclosure protects canal-fed fields large enough to sustain a long siege. The palaces and wall took generations to complete.
- The skyline is dominated by **multiple colossal stepped stone pyramid-palaces**. House Amaranth still rules from them and holds ceremonies on their steps, despite their Var Kaled origin.
- House Nereth's canals, sluices, flood markers, and irrigation engineering are central to the city's form and economy. Granaries and working quays matter more than purely decorative monuments.
- The Dareth Archive and a modest Selenne river shrine belong in the civic program. Selenne uses river water at coronations and did not inherit Solaran's grand-temple role.
- Hamen controls both banks of the River Flame. Queen Meret secretly builds a war fleet under the guise of harbor renewal. That need not appear in an ordinary city overview.

## Proposed design for review (not canon)

- Put the principal palace district and dense inner city on the east bank, with a smaller west-bank landing and a single stone bridge. The texts do not specify the city's exact bank plan or bridge count.
- Use a broad, earthy red, silt-heavy river. “Flame” is a name; the water is not literal fire or lava.
- Show the inner city as a compact island of masonry inside a much larger productive outer enclosure. Keep most protected land visibly planted, not filled with houses.
- Blend courtyard houses, flat roofs, pale stone, warm ochre plaster, muted terracotta, and sparse riverbank palms. This palette and mix are an interpretation of the lore's Middle Eastern and central Italian influence.
- Favor a peaceful working capital: barges, grain carts, markets, canals, and palace ceremony. Avoid copying Calderra's Roman arena or coastal composition.

## Reference images

| File | Intended use | Caution |
|---|---|---|
| `refs/haven-aerial-concept.png` | Overall massing: palace skyline, compact inner city, river quay, huge cultivated enclosure | The wall and river geometry are illustrative; the image does not prove a canonical bank layout. |
| `refs/haven-palace-concept.png` | Stepped palace masonry, broad stairs, occupied upper halls, ceremonial plaza and human scale | Rooftop shapes, arches, and shrine placement are design proposals. |
| `refs/haven-plan-wireframe.svg` | Labeled top-down zoning guide for a procedural build | Diagram is not surveyed geography or final dimensions. |

## Later Blender handoff

1. Model Haven as a **smaller city presentation than Calderra**, while preserving the contrast between its tiny dense core and extensive protected fields. Do not treat the full ancient outer-wall perimeter as physically fitting inside the current 100 × 100 m city plinth without a deliberate scale solution.
2. Build the palace cluster as a new procedural landmark type; the current generator's `palace` is not a stepped pyramid-palace. Canal grid, sluice structures, granaries, and this outer agricultural enclosure also need generator work or deliberate approximations.
3. Ask the user to settle exact bank/bridge plan and whether the visual target is an Atlas city miniature, a broader landscape render, or both before locking geometry.

## Source

- `Hamen Atlas Entry.md`, especially Terrain and Economy and Architecture Note.
- `The River Flame Chronicles - Volume I.md`, Chapter IV (Founding of Haven) and Chapter VI (Great Houses).
- `The River Flame Chronicles - Volume II.md`, Books One and Two (eastern-bank lordship, reunification, harbor and grain economy).
