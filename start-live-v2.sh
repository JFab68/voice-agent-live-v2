#!/usr/bin/env bash
set -euo pipefail

export AUDIO_SOCKET_HOST=127.0.0.1
export AUDIO_SOCKET_PORT=9019
export LLM_BASE=${LLM_BASE:-http://127.0.0.1:8099}
export LLM_MODEL=${LLM_MODEL:-gemma-4-E4B-it-Q4_K_M.gguf}
export KOKORO_DIR=${KOKORO_DIR:-/home/johnfab/apps/voice-agent-models/kokoro}
export DEFAULT_VOICE=${DEFAULT_VOICE:-am_michael}
export VOICE_AGENT_LIVE_OUTPUT_DIR=${VOICE_AGENT_LIVE_OUTPUT_DIR:-/tmp/voice-agent-live-v2}

exec /home/johnfab/apps/voice-agent-venv/bin/python3 /home/johnfab/apps/voice-agent-live-v2/audiosocket_server.py
