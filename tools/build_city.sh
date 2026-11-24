#!/usr/bin/env bash
# Build one city headless: blender/<id>.blend + cities/<id>/ (city.json; plus glb/png when --export or by default).
# Usage: tools/build_city.sh <city_id> [--no-export] [--no-save]
set -euo pipefail
cd "$(dirname "$0")/.."
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
id="${1:-fantasy_capital}"; shift || true
export_flag="--export"; save_flag=""
for a in "$@"; do
  case "$a" in
    --no-export) export_flag="" ;;
    --no-save) save_flag="--no-save" ;;
  esac
done
args=("$id")
[ -n "$export_flag" ] && args+=("$export_flag")
[ -n "$save_flag" ] && args+=("$save_flag")
log="$(mktemp)"
set +e
"$BLENDER" -b --factory-startup --python generator/build_city.py -- "${args[@]}" >"$log" 2>&1
rc=$?
set -e
grep -E "^\[(Build|Export)\]|Error|Traceback|line [0-9]+," "$log" || true
if [ $rc -ne 0 ] || ! grep -q "\[Build\] OK" "$log"; then
  echo "[build_city] FAILED (exit $rc); full log: $log"; exit 1
fi
rm -f "$log"
