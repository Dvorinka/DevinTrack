#!/bin/bash
# install-heal.sh — one-shot sudo installer for DevinTrack auto-heal.
#
# Does two things:
#   1. Repairs the wrapper now (refreshes stale devin.real, reinstalls wrapper).
#   2. Installs a root systemd path unit that re-runs the repair automatically
#      whenever a Devin update overwrites the wrapper binary.
#
# Run with:  sudo bash install-heal.sh
# Uninstall: sudo bash install-heal.sh --uninstall

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The invoking user (not root). systemd system units run as root, but we bake
# the real user's home into the service so logs land in the right place.
REAL_USER="${SUDO_USER:-${USER:-}}"
if [ -z "$REAL_USER" ] || [ "$REAL_USER" = "root" ]; then
    echo "ERROR: run this with sudo from your normal user account." >&2
    exit 1
fi
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
if [ -z "$REAL_HOME" ]; then
    echo "ERROR: could not resolve home for $REAL_USER." >&2
    exit 1
fi

BIN_DIR="/usr/share/devin-desktop/resources/app/extensions/windsurf/devin/bin"
WATCHED="$BIN_DIR/devin"
UNIT_DIR="/etc/systemd/system"

write_units() {
    cat > "$UNIT_DIR/devintrack-heal.path" <<EOF
[Unit]
Description=Watch Devin binary for updates (DevinTrack auto-heal)

[Path]
PathChanged=$WATCHED
Unit=devintrack-heal.service

[Install]
WantedBy=multi-user.target
EOF

    cat > "$UNIT_DIR/devintrack-heal.service" <<EOF
[Unit]
Description=Reinstall DevinTrack wrapper after Devin update

[Service]
Type=oneshot
Environment=HOME=$REAL_HOME
Environment=XDG_DATA_HOME=$REAL_HOME/.local/share
ExecStart=$SCRIPT_DIR/devintrack-heal.sh
EOF
}

if [ "${1:-}" = "--uninstall" ]; then
    echo "Disabling DevinTrack auto-heal watcher..."
    systemctl disable --now devintrack-heal.path 2>/dev/null || true
    rm -f "$UNIT_DIR/devintrack-heal.path" "$UNIT_DIR/devintrack-heal.service"
    systemctl daemon-reload
    echo "Watcher removed. The wrapper itself is left installed;"
    echo "run 'python3 $SCRIPT_DIR/deploy.py --undeploy' to restore the raw binary."
    exit 0
fi

echo "DevinTrack auto-heal installer"
echo "  user:  $REAL_USER"
echo "  home:  $REAL_HOME"
echo "  watch: $WATCHED"
echo

if [ ! -f "$WATCHED" ]; then
    echo "ERROR: Devin binary not found at $WATCHED." >&2
    echo "Set DEVIN_BIN_DIR or update this script if Devin is installed elsewhere." >&2
    exit 1
fi

echo "[1/3] Repairing wrapper now (refreshes stale backup, reinstalls wrapper)..."
python3 "$SCRIPT_DIR/deploy.py"

echo
echo "[2/3] Installing systemd path unit + service..."
write_units
chmod 644 "$UNIT_DIR/devintrack-heal.path" "$UNIT_DIR/devintrack-heal.service"
systemctl daemon-reload
systemctl enable --now devintrack-heal.path

echo
echo "[3/3] Done. Verifying..."
systemctl status devintrack-heal.path --no-pager -n 0 || true
echo
echo "Auto-heal armed. Future Devin updates that overwrite the wrapper will"
echo "trigger an automatic reinstall within seconds. Heal log:"
echo "  $REAL_HOME/.local/share/devin_track/heal.log"
echo
echo "Restart Devin Desktop now so the new wrapper takes effect for the next"
echo "'devin acp' invocation. The currently running session is unaffected."
