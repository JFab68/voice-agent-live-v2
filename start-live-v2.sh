#!/usr/bin/env bash
set -euo pipefail

# Praxis Initiative Voice Agent - Live V2 Startup
# Context window is set on the llama-server command line (-c 32768)

export AUDIO_SOCKET_HOST=127.0.0.1
export AUDIO_SOCKET_PORT=9019
export LLM_BASE=${LLM_BASE:-http://127.0.0.1:8099}
export LLM_MODEL=${LLM_MODEL:-gemma-4-E4B-it-Q4_K_M.gguf}
export KOKORO_DIR=${KOKORO_DIR:-/home/johnfab/apps/voice-agent-models/kokoro}
export DEFAULT_VOICE=${DEFAULT_VOICE:-am_michael}
export VOICE_AGENT_LIVE_OUTPUT_DIR=${VOICE_AGENT_LIVE_OUTPUT_DIR:-/tmp/voice-agent-live-v2}

# Dynamic prompt loading: these files are loaded at startup
export VOICE_AGENT_PROMPT_FILE=${VOICE_AGENT_PROMPT_FILE:-/home/johnfab/apps/voice-agent-live-v2/prompt.md}
export VOICE_AGENT_KNOWLEDGE_FILE=${VOICE_AGENT_KNOWLEDGE_FILE:-/home/johnfab/apps/voice-agent-live-v2/knowledge.md}

# History window: how many conversation turns to keep (increased for 32K context)
export VOICE_AGENT_HISTORY_WINDOW=${VOICE_AGENT_HISTORY_WINDOW:-24}

# VAD settings
export VAD_START_RMS=${VAD_START_RMS:-700}
export VAD_CONTINUE_RMS=${VAD_CONTINUE_RMS:-500}
export BARGE_IN_MS=${BARGE_IN_MS:-180}
export MAX_UTTERANCE_MS=${MAX_UTTERANCE_MS:-9000}

exec /home/johnfab/apps/voice-agent-venv/bin/python3 /home/johnfab/apps/voice-agent-live-v2/audiosocket_server.py