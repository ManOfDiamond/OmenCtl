#!/usr/bin/env bash
# Apply the on-demand (no background processes) model to the live install.
# Usage: sudo ./apply-on-demand.sh
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root: sudo $0"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INSTALL_DIR=/usr/libexec/hp-manager
DATA_DIR=/usr/share/hp-manager

echo "[i] Stopping always-on services and leftover GUI/tray..."
for svc in fan rgb power mux platform; do
  systemctl disable "hpm-${svc}.service" 2>/dev/null || true
  systemctl stop "hpm-${svc}.service" 2>/dev/null || true
done
pkill -f '/usr/share/hp-manager/gui/main_window.py' 2>/dev/null || true
pkill -f '/usr/bin/omen-tray' 2>/dev/null || true
pkill -f 'omenctl --hidden' 2>/dev/null || true
pkill -f 'sleep 5 && omenctl' 2>/dev/null || true

echo "[i] Deploying daemon + GUI..."
cp -r src/daemon/* "$INSTALL_DIR/"
mkdir -p "$DATA_DIR/gui/pages" "$DATA_DIR/gui/widgets"
cp src/gui/main_window.py "$DATA_DIR/gui/"
cp src/gui/i18n.py "$DATA_DIR/gui/"
cp src/gui/pages/*.py "$DATA_DIR/gui/pages/"
cp src/gui/widgets/*.py "$DATA_DIR/gui/widgets/" 2>/dev/null || true
# Prefer utils.py if present in source tree
[[ -f src/gui/utils.py ]] && cp src/gui/utils.py "$DATA_DIR/gui/" || true
rm -f /usr/bin/omen-tray "$INSTALL_DIR/omen-tray.py"

echo "[i] Installing D-Bus on-demand units..."
mkdir -p /usr/share/dbus-1/system-services
for svc in fan rgb power mux platform; do
  cp "data/hpm-${svc}.service" /etc/systemd/system/
  chmod 644 "/etc/systemd/system/hpm-${svc}.service"
  cp "data/dbus-system-services/com.yyl.hpmanager.${svc}.service" /usr/share/dbus-1/system-services/
  chmod 644 "/usr/share/dbus-1/system-services/com.yyl.hpmanager.${svc}.service"
done

echo "[i] Removing login autostart..."
rm -f /etc/xdg/autostart/omenctl-bg.desktop
rm -f /home/*/.config/autostart/omenctl-bg.desktop 2>/dev/null || true

systemctl daemon-reload
systemctl reload dbus 2>/dev/null || true

for svc in fan rgb power mux platform; do
  systemctl disable "hpm-${svc}.service" 2>/dev/null || true
done

echo
echo "[✓] On-demand model applied."
echo "    Services no longer start at boot; they activate when you open OmenCtl"
echo "    and exit after ~45s idle when you close it."
echo
echo "Verify:"
echo "  systemctl is-enabled hpm-rgb.service   # expect: disabled / static"
echo "  systemctl is-active  hpm-rgb.service   # expect: inactive"
echo "  pgrep -af 'hp-manager|omenctl|omen-tray'  # expect: empty"
