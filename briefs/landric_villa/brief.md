# City brief: Landric's Villa (`landric_villa`)

Not a city: Prince Landric Caldravi's country villa outside Calderra. Size it as a villa. Sources: the user's request
(2026-11-24) and the design pack in `docs/design/landrics_villa*.md` (Chapter 1 evidence, the wireframe SVG, the
aerial and overhead concepts `landrics_villa_aerial.png` / `landrics_villa_overhead.png`, and the motion brief).

## 1. Where in the world
- **New place** on the Known World: the user's X on the upland north-north-west of Calderra, between the coast road
  and the river (Known World xy 107.65, 147.95; ~24 km from the city). First placed on the peninsula west of the bay,
  then moved here by the user.
- **Realm / ruler:** Calderra; Prince Landric Caldravi, heir (`char:landric_caldravi`); his family (Yseult, Elenora,
  Cassian) and household.
- **Season:** late autumn (harvest), dusk.

## 2. The pitch
A walled noble estate in autumn vineyards: a two-storey pale-stone villa round one open peristyle, lamp-lit gate and
arrival court, stables, kitchen garden, a bathhouse with a spring-fed cold pool and a heated pool, and a small lake
with a riding path. A model you can go into in detail; on the map a small lake, hills and the house that match it.

## 3–8. See `docs/design/landrics_villa.md` (layout and evidence) and `docs/design/landrics_villa_motion.md` (life, events, views).

## Agent's reading
- **References:** the aerial concept (three-quarter dusk view: U/ring villa, portico with pediment, three arched
  great-hall windows, green shutters, stables on the west wall, kitchen garden and two-pool bathhouse to the east, lake
  top right, vineyards all round, cypresses and autumn trees) and the overhead cutaway (the room plan: great hall SW,
  granite entry with two rearing horses, private dining SE with the hearth, kitchen and stores east, bedrooms above).
- **Build:** the city generator can't express this (no city, walls, harbour), so it is **new generator work**,
  done here as `generator/villa.py` (`"kind": "estate"`), not hacked into `fantasy_capital.py`. Plinth 300 m
  (`model_scale` 3). Estate ~130 × 90 m inside its wall; house 57 × 53 m round a 30 × 20 m court with 40 columns and
  12 statues. Ground and upper floor are furnished; the Atlas lifts roofs and upper floor off (cutaway).
- **Room choices** (the chapter's routes): gallery = north range at the end of the peristyle walk, the *Duel Before
  The Walls* on its west end wall; kitchen and stores = east range, between private dining and the kitchen garden;
  family rooms and library = west range; bedrooms upstairs. Gate faces south; the road runs south-south-east to Calderra.
- **Events:** none of the five city events fit (no venues). The four chapter sequences are left as anchors and routes
  (`anchors`, `routes` in `city.json`) for a later card.
- **Questions:** none asked; defaults recorded in `docs/DECISIONS.md` #8 and the `LORE?` list in the handoff.
