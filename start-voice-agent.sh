#!/usr/bin/env bash
# Praxis Voice Agent — Full launcher
# 1. Starts daemon services (llama-server + AudioSocket)
# 2. Launches baresip softphone for calling
set -euo pipefail

DAEMON_SCRIPT="$HOME/apps/voice-agent-live-v2/start-daemons.sh"

# ── Start the backend services ──
bash "$DAEMON_SCRIPT"

# ── Launch baresip ──
if command -v baresip >/dev/null 2>&1; then
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- baresip 2>/dev/null &
  elif command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e baresip 2>/dev/null &
  elif command -v xterm >/dev/null 2>&1; then
    xterm -e baresip &
  else
    echo "No terminal emulator found. Run 'baresip' in another window."
  fi
  echo ""
  echo "baresip launched. Dial: testlive"
else
  echo "baresip not found. Install it or use your own SIP client."
fi

echo ""
echo "Press Enter to close this window (services keep running)..."
read