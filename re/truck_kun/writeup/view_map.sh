#!/usr/bin/env bash
# View the DISTRIBUTED game map live in Godot. Mounts the binary's own
# resource pack and instantiates its real Main scene into a throwaway
# viewer project, then drops you into a free-fly camera. No decompilation,
# no custom rendering -- geometry loads straight from the pack as data.
#
# Needs a real display (don't run with --headless).
#
# Usage:
#   ./view_map.sh /path/to/truck-kun.x86_64 [res://scene/path.tscn]
#
# Controls: WASD move, mouse look, Q/E down/up, Shift faster, Esc releases mouse.

set -euo pipefail

GODOT="${GODOT:-godot4}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIEWER_DIR="$SCRIPT_DIR/viewer"

BINARY="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
SCENE_PATH="${2:-res://scenes/Main.tscn}"

if [[ ! -f "$BINARY" ]]; then
    echo "error: '$BINARY' not found" >&2
    exit 1
fi

if ! command -v "$GODOT" >/dev/null 2>&1; then
    echo "error: '$GODOT' not found on PATH (set GODOT=/path/to/godot4 to override)" >&2
    exit 1
fi

# Built under this script's dir, not /tmp: some Godot installs (snap) are
# sandboxed and can't see /tmp.
WORKDIR="$(mktemp -d "$SCRIPT_DIR/.view-map-workdir-XXXXXX")"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

# Copy the viewer project in. Files live at the project root with unique
# names so mounting the target's pack can't shadow them (which would
# trigger Godot's live script-reload in a loop).
cp "$VIEWER_DIR/project.godot" \
   "$VIEWER_DIR/ViewerFreeCamera.gd" \
   "$VIEWER_DIR/ViewerMain.gd" \
   "$VIEWER_DIR/ViewerRoot.tscn" \
   "$WORKDIR/"

echo "Mounting: $BINARY"
echo "Scene:    $SCENE_PATH"
"$GODOT" --path "$WORKDIR" -- "$BINARY" "$SCENE_PATH"
