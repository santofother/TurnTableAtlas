#!/usr/bin/env bash
# Double-click to run the Turntable Atlas (builds the C# first if needed).
cd "$(dirname "$0")"
export DOTNET_ROOT="$HOME/.dotnet" PATH="$HOME/.dotnet:$PATH" DOTNET_CLI_TELEMETRY_OPTOUT=1
GODOT=/Applications/Godot_mono.app/Contents/MacOS/Godot
dotnet build atlas/Atlas.csproj -nologo -v q || { echo "Build failed - see above."; read -n1 -p "Press a key to close"; exit 1; }
[ -d atlas/.godot/imported ] || "$GODOT" --headless --path atlas --import >/dev/null 2>&1
"$GODOT" --path atlas
