#!/bin/bash
# devintrack-heal.sh — idempotent self-healing for the DevinTrack wrapper.
#
# Detects whether the Devin binary is the Python wrapper or a real ELF.
# If a Devin update overwrote the wrapper with a fresh real binary, this
# refreshes the devin.real backup from the current binary and reinstalls
# the wrapper. If the wrapper is already current, it does nothing (no file
# change), which prevents re-triggering the systemd path unit in a loop.
#
# Designed to run as root via the devintrack-heal systemd path unit.
# Safe to run manually at any time.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/devin_track"
HEAL_LOG="$LOG_DIR/heal.log"
DEPLOY="$SCRIPT_DIR/deploy.py"

mkdir -p "$LOG_DIR"

log() { printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$HEAL_LOG" >&2; }

# locate the Devin binary dir the same way deploy.py does (Linux candidates).
DEVIN_BIN_DIR="${DEVIN_BIN_DIR:-}"
if [ -z "$DEVIN_BIN_DIR" ]; then
    for c in \
        /usr/share/devin-desktop/resources/app/extensions/windsurf/devin/bin \
        "$HOME/.local/bin" \
        /usr/local/bin; do
        if [ -f "$c/devin" ]; then DEVIN_BIN_DIR="$c"; break; fi
    done
fi

if [ -z "$DEVIN_BIN_DIR" ] || [ ! -f "$DEVIN_BIN_DIR/devin" ]; then
    log "ERROR: Devin binary not found; cannot heal."
    exit 0  # not a failure — the watcher should stay armed for next time
fi

DEVIN="$DEVIN_BIN_DIR/devin"

# Detect wrapper vs real binary by reading the first bytes.
# The wrapper starts with a Python shebang; the real Devin binary is an ELF.
first_bytes="$(head -c 30 "$DEVIN" 2>/dev/null || true)"
if [[ "$first_bytes" == "#!/usr/bin/env python3"* ]]; then
    # Wrapper already installed. deploy.py skips the copy when identical
    # (no file change, no path-unit re-trigger loop).
    log "Wrapper present at $DEVIN; verifying it is current."
else
    log "Real binary detected at $DEVIN (Devin update overwrote wrapper). Reinstalling."
fi

# deploy.py handles: refresh stale devin.real, install wrapper, skip if identical.
if python3 "$DEPLOY" >>"$HEAL_LOG" 2>&1; then
    log "heal complete."
else
    log "ERROR: deploy.py failed; see log above."
    exit 1
fi
