#!/usr/bin/env bash
# Render and encode every shot in order (about 1.5-2 h at 1080p on an M1 Pro). Usage: tools/render_all.sh [--preview]
set -uo pipefail
cd "$(dirname "$0")/.."
for s in hero_turntable day_night_timelapse fleet_arrival colosseum_games hippodrome_race festival_night theatre_play top_map; do
  tools/render_shot.sh "$s" "$@" || echo "[render_all] $s FAILED"
done
echo "[render_all] done"
