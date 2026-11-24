---
name: new-city
description: Build a new Turntable Atlas city for the Caelora world from the user's brief and reference images in briefs/<city_id>/. Use when the user wants to add, make, design or start a new city (or asks for the new-city prompt), passing the city id as the argument.
---

# New city

The argument is the city id (e.g. `salmara`), or a path to its brief folder.

1. If there is no argument, ask the user for the city id (lower case, `_` between words) and stop.
2. If `briefs/<city_id>/brief.md` does not exist, run `tools/new_city.py init <city_id>`, tell the user to put
   reference images in `briefs/<city_id>/refs/` and fill in the brief, show them the brief's path, and stop.
3. Otherwise read `AGENTS.md` and `docs/new_city/README.md` in full and follow the README's steps exactly. It
   says where every file is, what the generator can build, where the lore lives, and when to ask questions.
