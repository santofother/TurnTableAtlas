# Haven, capital of Hamen — visual concept brief

Status: concept only. The images are design references for a later Blender build, not settled geography or a city config. Revised visual direction: a Nile-inspired agricultural valley around one of the world's largest cities (roughly **400,000–600,000 residents**, per the user).

## Canon from the supplied texts

- Haven is Hamen's capital on the River Flame floodplain, upriver from the coast. River barges, caravan roads, grain trade, and an inland harbor meet here.
- Erros the Founder built an inner city and began a vast outer wall. The outer enclosure protects canal-fed fields large enough to sustain a long siege. The palaces and wall took generations to complete.
- The skyline is dominated by **multiple colossal stepped stone pyramid-palaces**. House Amaranth still rules from them and holds ceremonies on their steps, despite their Var Kaled origin.
- House Nereth's canals, sluices, flood markers, and irrigation engineering are central to the city's form and economy. Granaries and working quays matter more than purely decorative monuments.
- The Dareth Archive and a modest Selenne river shrine belong in the civic program. Selenne uses river water at coronations and did not inherit Solaran's grand-temple role.
- Hamen controls both banks of the River Flame. Queen Meret secretly builds a war fleet under the guise of harbor renewal. That need not appear in an ordinary city overview.

## Proposed design for review (not canon)

- Put the principal palace district and dense inner city on the east bank, with a west-bank agricultural district and a single stone bridge. The texts do not specify the city's exact bank plan or bridge count.
- Use a broad, earthy red, silt-heavy river. “Flame” is a name; the water is not literal fire or lava.
- Show an expansive inner wall enclosing an immense, tightly packed city. Thousands of houses, workshops, streets, markets, granaries, and quays should read as a metropolitan fabric around the palace cluster. The palaces are landmarks within the city, not most of its footprint.
- Beyond the inner wall, show a still larger productive outer enclosure and continuous irrigated farmland on **both** riverbanks. Fields, feeder canals, levees, and agricultural villages should cover most river-adjacent land, with a sharp green-to-desert transition farther out. Use the Nile and Egypt as landscape and water-management inspiration, without copying Egyptian religious monuments.
- Frame the primary image from far enough away that the whole dense inner city occupies a minority of the visible valley. The regional image is the preferred reference for overall scale; the closer aerial is a supporting density study.
- Blend courtyard houses, flat roofs, pale stone, warm ochre plaster, muted terracotta, and sparse riverbank palms. This palette and mix are an interpretation of the lore's Middle Eastern and central Italian influence.
- Favor a peaceful working capital: barges, grain carts, markets, canals, and palace ceremony. Avoid copying Calderra's Roman arena or coastal composition.

## Reference images

| File | Intended use | Caution |
|---|---|---|
| `refs/haven-regional-concept-v2.png` | **Primary overall reference:** far zoom, vast two-bank farmland, extensive outer wall, metropolitan inner city | The wall and river geometry are illustrative; the image does not prove a canonical bank layout. |
| `refs/haven-aerial-concept-v2.png` | Secondary reference for house density, palace-to-city ratio, quays and irrigation | Closer than the preferred overall framing. |
| `refs/haven-palace-concept.png` | Stepped palace masonry, broad stairs, occupied upper halls, ceremonial plaza and human scale | Rooftop shapes, arches, and shrine placement are design proposals. |
| `refs/haven-plan-wireframe-v2.svg` | Updated top-down zoning guide: broad inner city and irrigated land on both banks | Diagram is not surveyed geography or final dimensions. |
| `refs/haven-plan-wireframe.svg` | Early top-down zoning study | Superseded: its core is too small. |
| `refs/haven-aerial-concept.png` | Original draft retained for comparison | Superseded: inner city too small and riverbank farmland too limited. |

## Later Blender handoff

1. Model Haven as one of the world's largest cities, with a credible visual population of roughly 400,000–600,000. Preserve the hierarchy of massive dense inner city, even larger cultivated outer enclosure, and a wide agricultural valley on both banks. A small Atlas miniature may need selective detail and a separate broad landscape render; do not force the full geography into the current 100 × 100 m city plinth without a deliberate scale solution.
2. Build the palace cluster as a new procedural landmark type; the current generator's `palace` is not a stepped pyramid-palace. Canal grid, sluice structures, granaries, and this outer agricultural enclosure also need generator work or deliberate approximations.
3. The exact bank/bridge plan remains provisional. Use the far-zoomed regional concept as the primary composition reference for now.

## Source

- `Hamen Atlas Entry.md`, especially Terrain and Economy and Architecture Note.
- `The River Flame Chronicles - Volume I.md`, Chapter IV (Founding of Haven) and Chapter VI (Great Houses).
- `The River Flame Chronicles - Volume II.md`, Books One and Two (eastern-bank lordship, reunification, harbor and grain economy).
