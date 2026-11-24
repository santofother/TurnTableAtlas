#!/usr/bin/env bash
# Double-click to open the Atlas project in the Godot editor with .NET found (C# scripts load, no hostfxr errors).
cd "$(dirname "$0")"
if [ -x /usr/local/share/dotnet/dotnet ]; then export DOTNET_ROOT=/usr/local/share/dotnet PATH="/usr/local/share/dotnet:$PATH"
else export DOTNET_ROOT="$HOME/.dotnet" PATH="$HOME/.dotnet:$PATH"; fi
export DOTNET_CLI_TELEMETRY_OPTOUT=1
GODOT=/Applications/Godot_mono.app/Contents/MacOS/Godot
dotnet build atlas/Atlas.csproj -nologo -v q || { echo "Build failed - see above."; read -n1 -p "Press a key to close"; exit 1; }
"$GODOT" --path atlas --editor
