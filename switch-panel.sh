#!/usr/bin/env bash
# Choose what the display shows on plug-in:  ./switch-panel.sh stats|proxmox
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

case "$1" in
  stats)   TARGET="$ROOT/run.sh" ;;
  proxmox) TARGET="$ROOT/proxmox-panel/run-proxmox.sh" ;;
  *) echo "Usage: $0 stats|proxmox" >&2; exit 1 ;;
esac

# The service always runs /usr/local/bin/smartscreen-launch; this launcher
# decides which panel starts. It lives outside $HOME because SELinux forbids
# systemd from exec'ing user_home_t files directly.
printf '#!/usr/bin/env bash\nexec "%s"\n' "$TARGET" | sudo tee /usr/local/bin/smartscreen-launch > /dev/null
sudo chmod 755 /usr/local/bin/smartscreen-launch
rm -f active-panel.sh  # legacy launcher from older versions

echo "==> Installing smartscreen.service + udev rule..."
sudo systemctl stop smartscreen usbmonitor proxmox-panel 2>/dev/null || true
sudo rm -f /etc/systemd/system/usbmonitor.service /etc/systemd/system/proxmox-panel.service
sudo cp smartscreen.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo cp 99-usbmonitor.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules

if lsusb -d 1a86:5722 >/dev/null 2>&1; then
    sudo systemctl start smartscreen
    echo "==> Display is plugged in: started $1 panel now."
fi
echo "Done. The display will show '$1' on every plug-in."
