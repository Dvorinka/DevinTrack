#!/usr/bin/env bash
set -euo pipefail

DEVIN_BIN_DIR="${DEVIN_BIN_DIR:-/usr/share/devin-desktop/resources/app/extensions/windsurf/devin/bin}"

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" >&2
   exit 1
fi

if [[ ! -e "$DEVIN_BIN_DIR/devin.real" ]]; then
    echo "No backup found at $DEVIN_BIN_DIR/devin.real" >&2
    exit 1
fi

mv -f "$DEVIN_BIN_DIR/devin.real" "$DEVIN_BIN_DIR/devin"
echo "Restored original devin binary."
