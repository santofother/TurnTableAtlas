# City briefs

One folder per city you want built: `briefs/<city_id>/brief.md` (what you want) and `briefs/<city_id>/refs/`
(reference images). Make one with:

    tools/new_city.py init <city_id> "Display Name"

then start a session with `/new-city <city_id>` (Claude Code), or tell any agent
"Read docs/new_city/README.md and build the city in briefs/<city_id>/". The full process is in
`docs/new_city/README.md`.
