#!/usr/bin/env bash
# Stop Praxis Voice Agent services - hard kill
echo "Stopping Praxis Voice Agent..."
pkill -9 -f "llama-server.*8099" 2>/dev/null && echo "  llama-server killed" || echo "  llama-server was not running"
pkill -9 -f "audiosocket_server.py" 2>/dev/null && echo "  v2 server killed" || echo "  v2 server was not running"
fuser -k 8099/tcp 2>/dev/null || true
fuser -k 9019/tcp 2>/dev/null || true
sleep 1
echo "Done."
ps aux | grep -E 'llama-server|audiosocket_server' | grep -v grep || echo "All voice agent processes stopped."