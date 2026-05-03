#!/usr/bin/env bash
# Quick start — launches both servers as persistent systemd user services.
set -euo pipefail

LLAMA_DIR="$HOME/apps/llama.cpp/build/bin"
LLAMA_MODEL="$HOME/apps/voice-agent-models/gemma4-e4b/gemma-4-E4B-it-Q4_K_M.gguf"
LLAMA_MMPROJ="$HOME/apps/voice-agent-models/gemma4-e4b/mmproj-F16.gguf"
LLAMA_PORT=8099
LLAMA_CTX=32768
LD_PATH="${LLAMA_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

V2_DIR="$HOME/apps/voice-agent-live-v2"
V2_VENV="$HOME/apps/voice-agent-venv"
V2_PORT=9019
KOKORO_DIR="$HOME/apps/voice-agent-models/kokoro"
LOG_DIR="/tmp/voice-agent-live-v2"
mkdir -p "$LOG_DIR"

# ── Kill existing ──
systemctl --user stop praxis-voice-llama praxis-voice-v2 2>/dev/null || true
fuser -k ${LLAMA_PORT}/tcp 2>/dev/null || true
fuser -k ${V2_PORT}/tcp 2>/dev/null || true
sleep 2

# ── Start llama-server ──
systemd-run --user --unit praxis-voice-llama \
  -E LD_LIBRARY_PATH="$LD_PATH" \
  --working-directory="$LLAMA_DIR" \
  "$LLAMA_DIR/llama-server" \
  -m "$LLAMA_MODEL" \
  --mmproj "$LLAMA_MMPROJ" \
  -ngl 99 -c "$LLAMA_CTX" \
  --host 127.0.0.1 --port "$LLAMA_PORT" \
  --reasoning off

# ── Wait for llama-server ──
echo "Waiting for llama-server..."
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:${LLAMA_PORT}/health >/dev/null 2>&1 && break
  sleep 1
done

# ── Start AudioSocket v2 ──
systemd-run --user --unit praxis-voice-v2 \
  -E AUDIO_SOCKET_HOST=127.0.0.1 \
  -E AUDIO_SOCKET_PORT="$V2_PORT" \
  -E LLM_BASE="http://127.0.0.1:${LLAMA_PORT}" \
  -E LLM_MODEL=gemma-4-E4B-it-Q4_K_M.gguf \
  -E KOKORO_DIR="$KOKORO_DIR" \
  -E DEFAULT_VOICE=am_michael \
  -E VOICE_AGENT_LIVE_OUTPUT_DIR="$LOG_DIR" \
  -E VOICE_AGENT_PROMPT_FILE="$V2_DIR/prompt.md" \
  -E VOICE_AGENT_KNOWLEDGE_FILE="$V2_DIR/knowledge.md" \
  -E VOICE_AGENT_HISTORY_WINDOW=24 \
  -E PYTHONUNBUFFERED=1 \
  --working-directory="$V2_DIR" \
  "$V2_VENV/bin/python3" -u "$V2_DIR/audiosocket_server.py"

# ── Wait for v2 server ──
echo "Waiting for AudioSocket server..."
for i in $(seq 1 15); do
  ss -tlnp 2>/dev/null | grep -q ":${V2_PORT} " && break
  sleep 1
done

echo ""
echo "=== Praxis Voice Agent Status ==="
curl -sf http://127.0.0.1:${LLAMA_PORT}/health && echo " llama-server OK" || echo " llama-server FAILED"
ss -tlnp 2>/dev/null | grep -q ":${V2_PORT} " && echo "AudioSocket server OK" || echo "AudioSocket server FAILED"
echo ""
echo "Services: systemctl --user status praxis-voice-llama praxis-voice-v2"
echo "Logs:     journalctl --user -u praxis-voice-llama | tail -20"
echo "          journalctl --user -u praxis-voice-v2 | tail -20"
echo "Stop:     systemctl --user stop praxis-voice-llama praxis-voice-v2"