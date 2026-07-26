#!/usr/bin/env bash
# Run the Proxmox panel on the smart screen (uses the shared venv).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/../turing-smart-screen-python/venv"
[ -x "$VENV/bin/python" ] || { echo "Run ../setup.sh first." >&2; exit 1; }
cd "$DIR"  # library writes log.log to cwd
exec "$VENV/bin/python" "$DIR/panel.py" "$@"
