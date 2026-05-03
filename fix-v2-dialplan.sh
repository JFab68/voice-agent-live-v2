#!/usr/bin/env bash
set -euo pipefail

echo "=== Fixing extensions.conf ==="
sudo cp /home/johnfab/apps/voice-agent/asterisk/extensions.conf /etc/asterisk/extensions.conf
echo "Restored base dialplan"

# AudioSocket requires UUID in 8-4-4-4-12 hex format.
# The server uses the UUID only for logging. A fixed valid UUID is fine.
sudo bash -c 'cat >> /etc/asterisk/extensions.conf' << 'EOF'

[from-softphone-live]
exten => _X.,1,NoOp(Live v2 call: ${CALLERID(all)})
 same => n,Answer()
 same => n,AudioSocket(00000000-0000-0000-0000-000000000001,127.0.0.1:9019)
 same => n,Hangup()
EOF
echo "Appended from-softphone-live context with fixed valid UUID"

echo "=== Reloading Asterisk dialplan ==="
sudo asterisk -rx 'dialplan reload'
echo "Dialplan reloaded"

echo "=== Verifying from-softphone-live ==="
sudo asterisk -rx 'dialplan show from-softphone-live'

echo "=== Checking v2 AudioSocket server ==="
ss -lntp | grep 9019 || echo "WARNING: v2 server not listening"

echo ""
echo "DONE. Ready to test v2."