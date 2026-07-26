#!/usr/bin/env bash
# Install auto-start (display starts on plug-in, stops on unplug). Needs sudo.
# Defaults to the system stats panel; use ./switch-panel.sh to change later.
exec "$(dirname "$0")/switch-panel.sh" "${1:-stats}"
