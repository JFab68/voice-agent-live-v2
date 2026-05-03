#!/usr/bin/env bash
# Praxis Voice Agent — Full launcher
# Starts servers, opens baresip, auto-dials the voice agent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Start backend services ──
bash "$SCRIPT_DIR/start-daemons.sh"

# ── Launch baresip with auto-dial ──
# baresip -e runs commands after startup. We wait for registration then dial.
# The '/dial testlive' command auto-dials the Praxis Voice Agent.

echo ""
echo -e "${CYAN}Launching softphone...${NC}"
echo -e "${CYAN}Auto-dialing testlive (Praxis Voice Agent)...${NC}"
echo ""

if command -v baresip >/dev/null 2>&1; then
  # -e '/dial testlive' auto-dials after baresip starts
  # --regint=0 means don't keep re-registering (we just want to make a call)
  baresip -e '/dial testlive'
else
  echo -e "${YELLOW}baresip not found. Install it: sudo apt install baresip${NC}"
  echo -e "${YELLOW}Then dial: testlive${NC}"
fi