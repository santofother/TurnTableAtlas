# Valdora Visual Truth Document

## Corivessa and the Great Gate

From the Oravian plains, **the Great Gate appears first**. Its towers and fortifications span the western mouth of the Ventara canyon, with Corivessa pressed against the complex at the foot of the hills. The plains run flat to the horizon. East through the cleft, the Canyon Road follows the Thennara toward the Kervara basin. South from the Gate, the toll-house line carries freight and travelers toward the Oravian crossings and the road to Astera. In the city itself, a cart can come up from a fuller's yard to a royal household and go back down through customs into the ordinary post. That traffic is as important to the city's appearance as the towers. [Atlas Entry, 23–43][Atlas Entry] [Varen I, 19–29][Varen I] [Varen II, 35–39, 163–173][Varen II] [Alys I, 3–7, 63–75][Alys I] [Map descriptions]

**Setting:** Book One, around 2100 CR. Valdora is the kingdom, Corivessa its inland capital, and the Great Gate the fortress-and-tower complex against which the city is built. Corivessa Port is a separate coastal settlement southwest of the capital. Kervara's capital and its own gates lie at the far end of the canyon. [Atlas Entry, 1–17, 39–43][Atlas Entry] [Atlas data] [Ventara illustration]

## Fit to the existing map

| Reference | What to carry into concept art and the build |
| --- | --- |
| Known World capital anchor | Use `settlement:corivessa_great_gate` at UV **(0.47474, 0.34398)**, measured from the top left. The Blender scene places `CITY_corivessa_great_gate` at **X 140.2, Y 172.2**. The lore table records **360 m** and leaves population open. Sample local surface elevations for actual foundations. [Known World] [Atlas data] [Source blend] |
| Painted Caelora map | Use the **Corivessa (The Great Gate)** capital star near **pixel (1830, 1235)** of the 3278 × 1920 map, UV **(0.5583, 0.6432)**. The generic affine estimate lands well west and slightly north of the star. The star serves the painted view, and the Known World anchor registers terrain and geometry. [Painted Geography] [Map bake] |
| Great Gate terrain | The Blender source already has `HERO_GreatGate`, spanning **X 131.9–157.5, Y 163.7–179.7**, as well as `RIVER_river_thennara` and the existing city mesh. Use the inset for close terrain and silhouette, and review `CAM_08_GreatGate` for a west-southwest view into the canyon. The city mesh is a reference for existing massing. The published relief uses the base height texture and an albedo bake that excludes city meshes. [Source blend] [Known World] [Map bake] [S12] |
| East and upstream | The current Known World Kervara marker is at UV **(0.50978, 0.34510)**. It is a regional reference for the eastern end. The walls of Ventara frame a continuous valley with a river low in the cut and a usable road through it. The book illustration gives a readable two-tower arch and road above the water. Use the relief and inset for the actual profiles and bearings. [Known World] [Ventara illustration] [Kervara brief] |
| Downstream and the coast | The Thennara flows west from Kervara toward the Gate, then south to the coast in the Corivessa Port region. The separate port marker is at UV **(0.46526, 0.37731)**, southwest of the capital. Trace the actual downstream channel and bay before placing wharves. The atlas table describes marsh and broken hills toward the Calderran border. [Map descriptions] [Known World] [Atlas data] |
| Plains and ridges | Give the westward opening room to read, with grain and grazing on low ground and broken slopes at the edges. The baked map has overlapping upland ridges around northern Valdora. Keep those outside the Gate's immediate throat and let the terrain guide what appears in each view. The atlas entry describes the Ventaran ranges as smaller than the Spine. [Atlas Entry, 31–43, 64–66][Atlas Entry] [S12] |

For a shared terrain reference, begin with a **north-up overhead** of the baked relief and a **west-southwest oblique** of the same site. Mark the canyon shoulders, river centerline, road through the Gate, southbound toll route, and the two sides of the fortress before composing a skyline. Put concept footprint and camera coordinates in that shared frame. World map XY uses about **16,093 m per unit** and the rendered relief is exaggerated **15×**. Sample rendered relief for the world-map seam and use local distances and physical heights for the detailed scene. Match the terrain surface at the perimeter of any future high-detail patch and refine the benches, building pads, and banks inside it. In the city package, generator and manifest axes are X east, Y north, Z up. Godot uses `(x, z, -y)`. [Known World] [Relief sampler] [Repo coordinates]

## Places and sightlines established in Book One

| Place | What to draw and preserve |
| --- | --- |
| Great Gate and Canyon Road | A working fortress wall and towers braced against the canyon sides. Include the **outer arch**, then the **barbican** in the outbound procession, with the toll-house line visible running south. The canyon face has pegged ladders and roped inspection stations visited by masons. On the western approach, keep a long open view of the plains. [Atlas Entry, 31–43][Atlas Entry] [Varen I, 21][Varen I] [Varen II, 163–173][Varen II] |
| Freight and customs | The queue reaches from the second toll-house to the outer arch and around the hill shoulder. At the Book One traffic peak, wagons stand three deep with mule strings and factors attending their loads. Grain, cloth, pitch, forage, wheels, weigh points and clerks give that width a purpose. Lay out enough approach space to show the queue continuing around the bend. The Kervaran preferential rate belongs to the clerks' ledgers and processing. [Varen I, 19–23][Varen I] [Varen II, 35–39, 163–171][Varen II] [Atlas Entry, 25–27, 62–65][Atlas Entry] |
| Palace and lower town | The palace is uphill from the lower town, with Gate watchfires and waiting toll traffic visible below Varen's shuttered study. Place working service streets and yards below the palace, including the fuller's wet-cloth yard. Alys's route from the palace goes roughly **two miles through the lower town and along a shoulder** to the east toll. A north-road rider can cut across home pastures directly toward the palace yard, avoiding the half-mile detour attributed to the alternative gate route. [Varen I, 67–87][Varen I] [Alys I, 3–7, 63–73][Alys I] [Alys II, 3–17, 109–149][Alys II] [Alys III, 3–19][Alys III] |
| East toll and Battina's hostel | Weighing and post handling at the east toll. The hostel is a **long, low building inside the gate** with a smoking chimney, forty pallets, a fire, drying racks, and wet wool. One winter view adds four **thatched, roped hayricks on brushwood platforms**, two pitch carts, and a farrier's fire under a new lean-to. Preserve enough space for carts to pull over for forage traffic. [Alys I, 63–73][Alys I] [Alys II, 113–149, 187–209][Alys II] [Alys IV, 93–117][Alys IV] |
| Palace working rooms | A **small audience room off the counting halls**, with Severin's table, squared papers, a window for Renata and a drinks sideboard. A **long gallery** with old Corivane banners, two steps for the king, and room for roughly three hundred people standing tightly along both walls. The mending-room window looks onto the yard and the route to the King's stair. [Varen I, 19–43][Varen I] [Varen II, 45–89][Varen II] [Alys III, 3–47][Alys III] |
| Flame-chapel | Old palace chapel used for state weddings. Make it small, bright with candles, warm with beeswax, with a low entrance arch, open door, front bench and room on the floor for heaps of undyed wool. In the mourning chapter the household keeps a three-day and three-night vigil here in relays. [Varen I, 45–63][Varen I] [Varen II, 103–125][Varen II] [Alys III, 41–47][Alys III] |
| Royal household and riding | Alys's small writing desk has good east light by day and candlelight after dark, with household accounts, ink, sand and folded letters. The good south room has braziers and needlework baskets. The family supper has two candles and a wine jug. Include service stairs, corridors, mews and the railed outer riding ring near the stable life. At departure Elara holds a lantern in the wet yard at the fifth hour. After Miriel's death, Elara sleeps next door to Alys and the household guard becomes visibly denser. [Alys I, 3–21, 23–63][Alys I] [Alys II, 29–47][Alys II] [Varen I, 67–79][Varen I] [Varen II, 149–159][Varen II] [Alys III, 45–79, 115–127][Alys III] [Alys IV, 43–49, 67–105][Alys IV] |
| Valdoran roads and marches | Old imperial stone under much of the regional road network, open grazing and grain country, patches of border hills, and river crossings with gravel or shingle. Along the southward road, eleven old stations are put back into use, nine inside the frontier and two beyond the last Valdoran toll. Show board-and-turf roofs, wells, bridges and fallback fords where the story supports them. The wet ford shown in Varen II is an unnamed route location. [Varen I, 3–17][Varen I] [Varen II, 3–17, 73–83][Varen II] [Alys II, 45–97, 169–179][Alys II] |

The naming supports drawing the **east toll and its hostel** as a local service precinct, the **outer arch and barbican** as the fortress crossing, and the **southbound toll-house line** as a route beyond it. Their exact junctions and the location of any river crossing remain open. The post leaves through the east toll before continuing west toward Calderra, so preserve that local routing detail even if the toll's mapped bearing changes. [Alys I, 3–7, 63–75][Alys I] [Varen II, 163–173][Varen II]

**Astera reference:** Varen III depicts the Astera river house, colonnade, 206-step pilgrimage stair, Narrows, timber scaffold and cedar-oil basin at the top. These belong in an Astera or journey study. Corivessa's established counterpart is the intimate, low-arched palace Flame-chapel and the separate east-toll hostel. [Varen III, 3–35, 59–93, 115][Varen III] [Varen I, 45–63][Varen I] [Alys II, 125–149][Alys II]

## Visual direction for concept art

- **Massing and materials.** Start with a broad, maintained masonry crossing, towers visible first, low and compact town roofs against its hill feet, and the palace a step higher. Warm grey or buff stone, muted clay or weathered timber roofs, plain wooden shutters, iron fittings and visible masonry repairs are working design choices. The illustrated twin towers are a starting silhouette. The manuscript gives us towers, an arch, masonry maintenance and practical court dress. Precise profiles, roof finish, and the palace silhouette remain open. [Ventara illustration] [Atlas Entry, 31–43, 53–66][Atlas Entry] [Varen I, 19–23, 81–87][Varen I] [Alys IV, 43–47][Alys IV]
- **Landscape and weather.** Dry-weather views can use straw-gold plains and dusty approaches. The winter freight scene uses lead-grey skies, standing water, mud up to the axles, smoke and rain-darkened stone. Use the map's lowland colors and adjoining uplands for the overall palette. Reserve rich color for selected freight, heraldry, and textiles. [Varen I, 19–23][Varen I] [Varen II, 3–15, 33–43, 163–171][Varen II] [Alys II, 113–145][Alys II] [Alys III, 3–7][Alys III]
- **People and dress.** Miriel is slight and fair in plain, undyed pilgrim wool. Alys is Calderran and dresses in understated grey in Corivessa. Elara is dark-haired with fine Caldravi features, six in the spring dinner and seven at the rainy departure. Varen is large and heavily built, in mail for departure. Severin dresses well and plainly, Renata has ink-stained fingertips, and the Valdoran background population can range from fair to warm-olive with dark, chestnut, and some lighter hair. The long gallery carries old Corivane banners, and one later banquet cloth has a gate embroidered in gold. Detailed arms and uniform colors are open. [Atlas Entry, 7–9, 45–66][Atlas Entry] [Varen I, 65–79][Varen I] [Varen II, 153–169][Varen II] [Alys I, 25–41][Alys I] [Alys III, 23–45, 119–127][Alys III] [Alys IV, 55–63][Alys IV]
- **Time layers.** A prosperous working baseline can use ordinary customs, fulling, riding and road maintenance. The backed-up freight queue and new forage yard are a Book One shipping-disruption layer. The later mourning layer adds the chapel vigil, extra guards, and a covered Corivane cart in place of the borrowed fish cart. Keep each layer on the same terrain and floor plan. [Varen II, 35–39][Varen II] [Alys II, 45–97, 109–149][Alys II] [Alys III, 41–47, 119–127][Alys III] [Alys IV, 93–117][Alys IV]

## First image set

| Image | Composition and continuity check |
| --- | --- |
| 1. Gate from the plains | West-southwest approach based on the existing Great Gate camera. Show flat farmland opening out on one side, towers anchored to both canyon shoulders, town gathered at their base, and the palace higher. Let the canyon continue east behind the fortifications. |
| 2. Terrain and circulation overhead | North-up relief overlay of the same footprint. Show the river, canyon road, fortress walls, arch and barbican, palace, lower town, east toll and hostel, and the southbound toll route. Add a small regional inset for the Kervara direction and separate port. Use this as the registration image for later modeling. |
| 3. Miriel at the outer arch | Grey winter morning at freight level, rain, cloth wagon, pitch mules, undyed wool, mail and the arch resolving through the queue. Show wheel and pedestrian clearance, the bend down the toll line, and the low plains beyond. |
| 4. Lower town to east toll | View along the muddy shoulder road past the fish cart, forage traffic and raised winter hayricks toward the long, low hostel. Keep the main Gate mass or a ridge shoulder in the distance if the registered sightline supports it. |
| 5. Palace and Gate after dark | Varen's study window and shutter in the foreground, the watchfires of the same Gate below, and waiting freight along the approach. A companion interior can show Miriel sewing in the low-arched Flame-chapel with the open door and warm candles. |

## Open for the next design pass

- **LORE?** Final fortress footprint, gate and bridge alignment, roads and river banks through the choke point, and the east-toll junction. Confirm on the detailed terrain before fixing them in aerial art.
- **LORE?** City population and extent, palace exterior, tower and roof profiles, masonry palette, official heraldry, and local season-specific planting. Use visibly provisional shapes in the overhead.
- **LORE?** Individual post, ford and farm locations, and the port's formal name and waterfront. Keep them regional until there is a mapped location.

## Sources

I read all four **Alys** chapters as the likely intended reading for “Ayns,” which has no chapter title or text match in the supplied Book One folder. Chapter citations refer to source Markdown line numbers.

[Alys I]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Book One/Part One/05 - Alys I.md>
[Alys II]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Book One/Part Two/21 - Alys II.md>
[Alys III]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Book One/Part Three/49 - Alys III.md>
[Alys IV]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Book One/Part Four/59 - Alys IV.md>
[Varen I]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Book One/Part One/04 - Varen I.md>
[Varen II]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Book One/Part Two/20 - Varen II.md>
[Varen III]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Book One/Part Three/39 - Varen III.md>
[Atlas Entry]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Caelora/Valdora/Valdora Atlas Entry.md>
[Ventara illustration]: </Users/santofothergill/Documents/CreativeWriting/FOMS-Working-Title/FireOnTheMiddleSea-main/The Histories/Book One/epub-assets/images/map-ventara-canyon.png>
[Map descriptions]: </Users/santofothergill/PersonalProjects/FOMSMap/2D-Map-Prompts/06_Prompts_Caelora.md>
[Source blend]: </Users/santofothergill/PersonalProjects/FOMSMap/KnownWorld-Map/KnownWorld.blend>
[Known World]: ../../atlas/assets/map/known_world/known_world.json
[Atlas data]: ../../atlas/assets/map/known_world/atlas_data.json
[Painted Geography]: ../../atlas/assets/map/Caelora_Geography.png
[Map bake]: ../../tools/bake_known_world.py
[Relief sampler]: ../../atlas/src/Core/ReliefSampler.cs
[Repo coordinates]: ../../AGENTS.md
[S12]: ../../docs/handoffs/S12.md
[Kervara brief]: ../kervara/brief.md

Manuscript: [Alys I], [Alys II], [Alys III], [Alys IV], [Varen I], [Varen II], [Varen III], [Atlas Entry], [Ventara illustration].

Map and build references: [Source blend], [Known World], [baked relief color](../../atlas/assets/map/known_world/albedo.png), [baked relief height](../../atlas/assets/map/known_world/height.png), [Atlas data], [Painted Geography], [Map descriptions], [Map bake], [Relief sampler], [Repo coordinates], [S12], [Kervara brief].
