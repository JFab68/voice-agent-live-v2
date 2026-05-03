#!/usr/bin/env bash
# Stop Praxis Voice Agent services
echo "Stopping Praxis Voice Agent..."
pkill -f "llama-server.*8099" 2>/dev/null && echo "  llama-server stopped" || echo "  llama-server was not running"
pkill -f "audiosocket_server.py" 2>/dev/null && echo "  v2 server stopped" || echo "  v2 server was not running"
echo "Done."