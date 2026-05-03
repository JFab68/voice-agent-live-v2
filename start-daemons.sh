#!/usr/bin/env bash
# Praxis Voice Agent — Start both servers as background daemons
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

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── Kill existing ──
echo -e "${YELLOW}Stopping existing processes...${NC}"
pkill -f "llama-server.*8099" 2>/dev/null || true
pkill -f "audiosocket_server.py" 2>/dev/null || true
fuser -k ${LLAMA_PORT}/tcp 2>/dev/null || true
fuser -k ${V2_PORT}/tcp 2>/dev/null || true
sleep 2

# ── Start llama-server ──
echo -e "${YELLOW}Starting Gemma 4 E4B llama-server on :${LLAMA_PORT}...${NC}"
cd "$LLAMA_DIR"
LD_LIBRARY_PATH="$LD_PATH" nohup "$LLAMA_DIR/llama-server" \
  -m "$LLAMA_MODEL" \
  --mmproj "$LLAMA_MMPROJ" \
  -ngl 99 -c "$LLAMA_CTX" \
  --host 127.0.0.1 --port "$LLAMA_PORT" \
  --reasoning off \
  >> "$LOG_DIR/llama-server.log" 2>&1 &
LLAMA_PID=$!
echo "  PID: $LLAMA_PID"

echo -e "${YELLOW}  Waiting for llama-server...${NC}"
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:${LLAMA_PORT}/health >/dev/null 2>&1 && break
  if [ $i -eq 30 ]; then
    echo -e "${RED}  FAILED: llama-server did not start${NC}"
    exit 1
  fi
  sleep 1
done
echo -e "${GREEN}  llama-server OK${NC}"

# ── Start AudioSocket v2 ──
echo -e "${YELLOW}Starting Praxis Voice Agent v2 on :${V2_PORT}...${NC}"
export AUDIO_SOCKET_HOST=127.0.0.1
export AUDIO_SOCKET_PORT=$V2_PORT
export LLM_BASE="http://127.0.0.1:${LLAMA_PORT}"
export LLM_MODEL=gemma-4-E4B-it-Q4_K_M.gguf
export KOKORO_DIR="$KOKORO_DIR"
export DEFAULT_VOICE=am_michael
export VOICE_AGENT_LIVE_OUTPUT_DIR="$LOG_DIR"
export VOICE_AGENT_PROMPT_FILE="$V2_DIR/prompt.md"
export VOICE_AGENT_KNOWLEDGE_FILE="$V2_DIR/knowledge.md"
export VOICE_AGENT_HISTORY_WINDOW=24
export PYTHONUNBUFFERED=1

cd "$V2_DIR"
nohup "$V2_VENV/bin/python3" -u "$V2_DIR/audiosocket_server.py" \
  >> "$LOG_DIR/v2-server.log" 2>&1 &
V2_PID=$!
echo "  PID: $V2_PID"

echo -e "${YELLOW}  Waiting for AudioSocket server...${NC}"
for i in $(seq 1 15); do
  ss -tlnp 2>/dev/null | grep -q ":${V2_PORT} " && break
  if [ $i -eq 15 ]; then
    echo -e "${RED}  FAILED: AudioSocket server did not bind${NC}"
    exit 1
  fi
  sleep 1
done
echo -e "${GREEN}  AudioSocket server OK${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Praxis Voice Agent is LIVE${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  Gemma 4 E4B  : 127.0.0.1:${LLAMA_PORT} (PID $LLAMA_PID)"
echo -e "  AudioSocket   : 127.0.0.1:${V2_PORT} (PID $V2_PID)"
echo -e "  Prompt        : $V2_DIR/prompt.md"
echo -e "  Knowledge     : $V2_DIR/knowledge.md"
echo -e "  Logs          : $LOG_DIR/"
echo -e "  Stop          : pkill -f 'llama-server.*8099'; pkill -f audiosocket_server"
echo -e "${GREEN}========================================${NC}"