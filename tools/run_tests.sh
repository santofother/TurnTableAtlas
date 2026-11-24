#!/usr/bin/env bash
# Every card runs this: python tests (sun arc, manifests), C# core tests, Atlas build + headless smoke run.
set -euo pipefail
cd "$(dirname "$0")/.."
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}" PATH="$HOME/.dotnet:$PATH" DOTNET_CLI_TELEMETRY_OPTOUT=1
GODOT="${GODOT:-/Applications/Godot_mono.app/Contents/MacOS/Godot}"

echo "[Test] python"
python3 -m unittest discover -s tests

echo "[Test] C# core"
dotnet test atlas/tests/Atlas.Core.Tests -nologo -v q

echo "[Test] Atlas build"
dotnet build atlas/Atlas.csproj -nologo -v q

if [ ! -d atlas/.godot/imported ]; then
  echo "[Test] first import"
  "$GODOT" --headless --path atlas --import >/dev/null 2>&1 || "$GODOT" --headless --path atlas --import >/dev/null 2>&1 || true
fi

for city in $(ls cities); do
  [ -f "cities/$city/city.json" ] || continue
  echo "[Test] smoke $city (headless, 5 s, self-test)"
  log="$(mktemp)"
  set +e
  "$GODOT" --headless --path atlas -- --city="$city" --selftest --quit-after=6 >"$log" 2>&1
  rc=$?
  set -e
  if [ $rc -ne 0 ] || grep -qE "ERROR|Unhandled exception|SELFTEST FAIL" "$log" || ! grep -q "\[Atlas\] quit-after" "$log"; then
    echo "[Test] smoke $city FAILED (exit $rc):"; cat "$log"; rm -f "$log"; exit 1
  fi
  grep -E "^\[(Atlas|Selftest)\]" "$log" || true
  rm -f "$log"
done
echo "[Test] all green"
