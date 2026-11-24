#!/usr/bin/env bash
# Render one cinematic shot headless and encode it.  Usage: tools/render_shot.sh <shot> [--preview] [--city id]
#   tools/render_shot.sh list           # show the shot list
set -euo pipefail
cd "$(dirname "$0")/.."
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
shot="${1:?shot name or list}"; shift || true
city="fantasy_capital"; extra=()
while [ $# -gt 0 ]; do
  case "$1" in
    --city) city="$2"; shift 2 ;;
    *) extra+=("$1"); shift ;;
  esac
done
if [ "$shot" = "list" ]; then
  "$BLENDER" -b "blender/$city.blend" --python blender/cinematic/run.py -- list 2>&1 | grep "^\[Cine\]"; exit 0
fi
sub=frames; for a in "${extra[@]:-}"; do [ "$a" = "--preview" ] && sub=preview; done
rm -rf "blender/renders/$shot/$sub"
log="blender/renders/$shot.log"; mkdir -p blender/renders
start=$(date +%s)
"$BLENDER" -b "blender/$city.blend" --python blender/cinematic/run.py -- shot "$shot" --city "$city" "${extra[@]:-}" >"$log" 2>&1 || true
if ! grep -q "\[Cine\] OK" "$log"; then echo "[render_shot] $shot FAILED, see $log"; tail -20 "$log"; exit 1; fi
out="blender/renders/$shot/$shot$([ "$sub" = preview ] && echo _preview).mp4"
"$BLENDER" -b --factory-startup --python tools/encode.py -- "blender/renders/$shot/$sub" "$PWD/$out" 24 2>&1 | grep "^\[Encode\]"
echo "[render_shot] $shot done in $(( $(date +%s) - start )) s -> $out"
