#!/usr/bin/env bash
# Stop Praxis Voice Agent services
set -euo pipefail
echo "Stopping Praxis Voice Agent..."
systemctl --user stop praxis-voice-v2 praxis-voice-llama 2>/dev/null || true
echo "Services stopped."
systemctl --user status praxis-voice-llama --no-pager 2>/dev/null | head -3 || echo "llama-server: stopped"
systemctl --user status praxis-voice-v2 --no-pager 2>/dev/null | head -3 || echo "v2-server: stopped"