#!/usr/bin/env bash
set -euo pipefail

DEVIN_BIN_DIR="${DEVIN_BIN_DIR:-/usr/share/devin-desktop/resources/app/extensions/windsurf/devin/bin}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER_SRC="${WRAPPER_SRC:-$SCRIPT_DIR/devin}"

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (e.g. sudo ./deploy.sh)" >&2
   exit 1
fi

if [[ ! -x "$DEVIN_BIN_DIR/devin" ]]; then
    echo "Original devin binary not found at $DEVIN_BIN_DIR/devin" >&2
    exit 1
fi

if [[ -e "$DEVIN_BIN_DIR/devin.real" ]]; then
    echo "Backup devin.real already exists; refusing to overwrite." >&2
    exit 1
fi

if [[ ! -x "$WRAPPER_SRC" ]]; then
    echo "Wrapper not found or not executable: $WRAPPER_SRC" >&2
    exit 1
fi

cp -p "$DEVIN_BIN_DIR/devin" "$DEVIN_BIN_DIR/devin.real"
install -m 755 "$WRAPPER_SRC" "$DEVIN_BIN_DIR/devin"

echo "Deployed wrapper: $DEVIN_BIN_DIR/devin"
echo "Original backup: $DEVIN_BIN_DIR/devin.real"
echo "Restart Devin Desktop to start using the tracker."
