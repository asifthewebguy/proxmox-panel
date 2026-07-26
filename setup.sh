#!/usr/bin/env bash
# One-time setup for the UsbPCMonitor 3.5" display (USB ID 1a86:5722)
set -e
cd "$(dirname "$0")/turing-smart-screen-python"

echo "==> Creating Python virtual environment..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip

echo "==> Installing dependencies..."
./venv/bin/pip install -r requirements.txt

echo "==> Installing udev rule (needs sudo) so the display is accessible without root..."
sudo cp ../99-usbmonitor.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

echo
echo "Done! Unplug and replug the display, then run:"
echo "  cd turing-smart-screen-python && ./venv/bin/python main.py"
