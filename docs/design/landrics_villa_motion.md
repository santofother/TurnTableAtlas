# Landric's villa — animation and event brief

**Source scope:** Chapter 1, *Before The Walls*, from the draft supplied by the author. This is a visual direction sheet for a future small Blender estate render and an optional Atlas location. A cited action happens in the chapter; **proposed** movement or timing is a staging choice. The palace mare reveal, the proposed games, and Elenora's wedding are not villa events in this chapter.

## Ambient life: what the estate does without a trigger

| Zone | Loop or time change | Evidence and staging boundary |
|---|---|---|
| Road and vineyards | A few distant harvest carts pass; vine leaves move lightly; one or two workers move between rows **(proposed)**. The estate grows its own wine and lies on the harvest-season route. | The ride passes carts and stubble fields (219–224); vineyard surrounds the villa (272); its wine is served (324). Do not show a crowd or festival at the villa. |
| Gate and arrival court | Lamps along both storeys and the wall turn on in a staggered dusk wave **(proposed timing)**; one household figure waits or crosses the path. | All lamps are already lit when the riders arrive (272–274). The chapter does not state the lighting mechanism. |
| Stables | Grooms lead horses from arrival court into the stable area, then return to a low-activity idle. A horse shifts weight, turns its head or swishes its tail **(proposed idle)**. | Two stable boys take the party's reins (308); Cassian exercises a grey horse around the lagoon (328–332). |
| Kitchen and private dining | Hearth flame and low smoke, serving trips, wine and food appearing on the table. Keep the great hall quiet during the family meal. | Private dining rather than great hall; fire already roaring (314); serving, offering and clearing (316, 378). |
| Peristyle and gallery | Lake breeze moves cloth and foliage subtly **(proposed visual cue)**; candle points flicker in the gallery; the largest painting is the brightest visual focus. Statues are still objects. | Lake breeze, marble walk and statues (382); candle-lit *Duel Before The Walls* painting (384). |
| Bathhouse | Cold pool has a soft spring-fed current; heated pool has a faint heat shimmer or steam **(proposed visual cue)**; firebox glows. | Spring-fed cold water and continually heated second pool (434). Steam intensity is a visual choice, not a described cloud of vapour. |
| Shore | Gentle water and a path that could support a horse loop. | Cassian says he rode around the lake/lagoon every day (328–332); the water is near enough for a cool breeze (314, 382). |

At **map distance**, read movement as lamp changes, a few horses, a cart, hearth glow and a very small number of figures. At **closer camera distance**, add gestures, table service, painted gallery detail and water motion. The villa should feel occupied but private, with a much lower figure count than Calderra's streets.

## Chapter event sequences

| Event / suggested Atlas label | Beats to animate | Camera and visual payoff | Source |
|---|---|---|---|
| **Return to the Villa** | Four riders approach at a walk after sunset; the camera reveals the fully lit house and wall above the dark vineyard. Yseult waits by the gate, with Sabine and Cassian approaching along the path. The riders stop; Landric embraces Yseult and Elenora greets her. Sabine reaches Radgar's horse; Radgar dismounts; grooms take the reins. | Start high and wide to establish estate, lake and road; lower toward the gate for the family reunion; end on horses led toward stables. Suggested film length **16–22 s**; Atlas event can finish in a held nighttime state. | 270–308. The mare was gifted at the palace, not here. |
| **Family Supper** | Enter across the horse-inlaid granite. Family gathers in the **private** dining room. A household servant places a portion of the first dish into the hearth as an offering to Ignara; everyone joins hands for Landric's prayer. Food and wine service continues. The table settles as the wedding and games are discussed; plates are cleared. | Begin on granite floor detail, then warm hearth and intimate table. Keep gestures readable without trying to lip-sync dialogue at miniature scale. Suggested **12–18 s**. The great hall stays unoccupied. | 310–378. The proposed games and wedding remain conversation, not visible events at the estate. |
| **The Peristyle and the Aegis** | After supper Landric and Radgar leave the table and walk around the courtyard's marble peristyle. They pass individual Oravessan statues, reach Landric's gallery, and stop before the large candle-lit *Duel Before The Walls*. Landric gestures toward the Aegis; Radgar studies the painted fighters; the two men stand in a quieter pause before parting. | Follow at cloister height, then reveal the gallery and push toward the large painting. The painting's light and scale carry the scene. Suggested **14–20 s**. | 380–431. A full historical duel is depicted *in the painting*; it is not a live fight at the villa. |
| **The Cold Spring** | Radgar leaves the gallery, crosses the peristyle, passes through the kitchen garden and between the two bathhouse entrance statues. He sets aside his clothes and gloves, enters the cold pool, submerges, surfaces briefly, and submerges again in silent prayer. The heated pool remains visible but unused. | Slow tracking route from gallery to bathhouse; finish in a still, close view of cold water, dim fire glow and an empty heated pool. Suggested **12–18 s**. | 432–440. Keep his painful reaction to cold water subtle; the novel gives interior experience that a miniature cannot show literally. |

**Scene continuity:** the events above occur in that order on one late-autumn evening. Use warm lamps against dark vineyards, a cool lake breeze, and later quiet at the bathhouse. The household characters are tiny painted figures in the established Atlas style; recognizable clothing colour and blocking matter more than facial animation.

## Optional vignettes (recounted, not witnessed at the villa)

- **Cassian's lake ride:** one young rider on a grey horse completes a calm circuit of the lagoon in daylight. Cassian reports doing this daily; the chapter does not show the ride (328–332). Suitable as a low-key daytime loop once the shore path exists.
- **The covered statues:** Yseult once covered the peristyle's nude statues while Landric was away, causing an argument. This is backstory, not part of the chapter's present evening (382). If used, label it as a memory or alternate state; do not mix covered statues into the supper-to-gallery sequence.

## Shared animation data for a future build

The diagram and images are concepts; the builder should emit named anchors/routes into the villa's package so Blender and Godot use the same placements. Suggested IDs are design targets, not fields already supported by the current schema:

| Proposed ID | Purpose |
|---|---|
| `road_to_gate`, `gate_stop`, `arrival_court`, `stable_route` | Horse approach, stop, dismount and groom exit. |
| `entry_hall`, `private_dining`, `hearth_offer`, `kitchen_service` | Supper staging and service paths. |
| `peristyle_loop`, `gallery_entry`, `aegis_painting` | Walk and gallery camera targets. |
| `garden_to_bath`, `bath_entry`, `cold_pool`, `heated_pool`, `bath_fire` | Bath route and pool effects. |
| `lagoon_riding_loop`, `lamp_points`, `vineyard_rows` | Ambient route, dusk lights and landscape motion. |

Build the **arrival** and **peristyle/gallery** sequences first: they communicate the estate's identity from a map camera. The supper and bath scenes need closer cutaway cameras or a cinematic render; roofs and walls will otherwise hide the action. None of these villa events are implemented by the current five city event scripts, and the existing generic countryside villa has no anchors for them.
