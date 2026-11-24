# City brief: <Display Name> (`<city_id>`)

Fill in what you know; leave the rest blank or write "your call". Put reference images in `refs/` next to this file
and list them at the bottom. Then start a session with `/new-city <city_id>` (Claude Code) or tell any agent
"Read docs/new_city/README.md and build the city in briefs/<city_id>/".

## 1. Where in the world
- **Settlement** (from `tools/new_city.py list`, e.g. `settlement:salmara`), or "new place" plus where it is:
- **Realm / ruler / who lives here:**
- **Latitude / season to show** (blank = from the map):

## 2. The pitch (one or two sentences)


## 3. Site and terrain
Coast or inland? Harbour shape, river, lagoon, island, cliffs, hills, plateau/acropolis, marsh, desert edge…


## 4. Layout
Walls and gates, main avenues, districts (port, market, palace quarter, slums, temples), how dense, what sits
outside the walls (farms, villas, salt pans, aqueduct, roads).


## 5. Landmarks
Which of these, how many, how big, where: palace · forum · colosseum (arena) · hippodrome (circus) · baths ·
rotunda · theatre · temple · tholos · castellum (water tower). Anything not on this list (lighthouse, citadel,
bridge city, windmills, ziggurat…) is new generator work: describe it anyway.


## 6. Look
Wall colours, roof colours and shapes (pitched / hipped / flat), stone vs whitewash vs brick, greenery, how
weathered or grand. "Like ref 2's roofs" is fine.


## 7. Life and events
Crowds, ships and boats, events it should support: gladiator games (needs an arena) · chariot race (needs a
hippodrome) · theatre play (needs a theatre) · fleet arrival (needs a harbour) · festival night.


## 8. Views
Camera presets you want in the Places list (e.g. "from the sea at dusk", "down the main avenue").


## 9. Must have / must avoid


## 10. References
| file in `refs/` | what to take from it |
|---|---|
| | |

---
<!-- The agent fills in below this line before building, and you confirm it. -->
## Agent's reading (filled in by the session)
- **What I see in the references:**
- **How I'll build it** (config choices, landmark list, palette, sun):
- **What the generator can't do yet** (needs new generator work):
- **Questions / `LORE?` placeholders:**
