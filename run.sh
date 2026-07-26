#!/usr/bin/env bash
# Start the UsbPCMonitor 3.5" display — run this after plugging it in.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)/turing-smart-screen-python"
cd "$DIR"

# First run? Do setup automatically.
if [ ! -x venv/bin/python ]; then
    echo "==> First run: setting up..."
    ../setup.sh
fi

# Wait up to 10s for the display to enumerate
echo -n "==> Waiting for display (1a86:5722)"
for i in $(seq 1 10); do
    lsusb -d 1a86:5722 >/dev/null 2>&1 && break
    echo -n "."
    sleep 1
done
echo
if ! lsusb -d 1a86:5722 >/dev/null 2>&1; then
    echo "ERROR: display not found. Is it plugged in?" >&2
    exit 1
fi
sleep 1  # let the serial port settle

exec ./venv/bin/python main.py
