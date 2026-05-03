#!/usr/bin/env python3
"""Start both voice agent servers as detached background processes."""

import os
import subprocess
import sys
import time

LLAMA_DIR = os.path.expanduser("~/apps/llama.cpp/build/bin")
LLAMA_MODEL = os.path.expanduser("~/apps/voice-agent-models/gemma4-e4b/gemma-4-E4B-it-Q4_K_M.gguf")
LLAMA_MMPROJ = os.path.expanduser("~/apps/voice-agent-models/gemma4-e4b/mmproj-F16.gguf")
LLAMA_PORT = 8099
LLAMA_CTX = 32768

V2_DIR = os.path.expanduser("~/apps/voice-agent-live-v2")
V2_VENV = os.path.expanduser("~/apps/voice-agent-venv")
V2_PORT = 9019
KOKORO_DIR = os.path.expanduser("~/apps/voice-agent-models/kokoro")
LOG_DIR = "/tmp/voice-agent-live-v2"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def kill_existing():
    """Kill any existing instances."""
    print(f"{YELLOW}Stopping existing processes...{NC}")
    for pattern in ["llama-server.*8099", "audiosocket_server.py"]:
        subprocess.run(["pkill", "-f", pattern], capture_output=True)
    # Also kill by port
    subprocess.run(["fuser", "-k", f"{LLAMA_PORT}/tcp"], capture_output=True)
    subprocess.run(["fuser", "-k", f"{V2_PORT}/tcp"], capture_output=True)
    time.sleep(2)


def start_llama():
    """Start llama-server as a fully detached process."""
    print(f"{YELLOW}Starting Gemma 4 E4B llama-server on :{LLAMA_PORT}...{NC}")
    ld_path = f"{LLAMA_DIR}{os.environ.get('LD_LIBRARY_PATH', '')}"
    log_path = os.path.join(LOG_DIR, "llama-server.log")
    os.makedirs(LOG_DIR, exist_ok=True)

    with open(log_path, "a") as logf:
        proc = subprocess.Popen(
            [os.path.join(LLAMA_DIR, "llama-server"),
             "-m", LLAMA_MODEL,
             "--mmproj", LLAMA_MMPROJ,
             "-ngl", "99", "-c", str(LLAMA_CTX),
             "--host", "127.0.0.1", "--port", str(LLAMA_PORT),
             "--reasoning", "off"],
            cwd=LLAMA_DIR,
            stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True,  # Detach from process group
            env={**os.environ, "LD_LIBRARY_PATH": ld_path},
        )
    print(f"  PID: {proc.pid}")
    return proc


def start_v2():
    """Start AudioSocket v2 as a fully detached process."""
    print(f"{YELLOW}Starting Praxis Voice Agent v2 on :{V2_PORT}...{NC}")
    log_path = os.path.join(LOG_DIR, "v2-server.log")
    v2_python = os.path.join(V2_VENV, "bin", "python3")
    v2_script = os.path.join(V2_DIR, "audiosocket_server.py")

    env = os.environ.copy()
    env.update({
        "AUDIO_SOCKET_HOST": "127.0.0.1",
        "AUDIO_SOCKET_PORT": str(V2_PORT),
        "LLM_BASE": f"http://127.0.0.1:{LLAMA_PORT}",
        "LLM_MODEL": "gemma-4-E4B-it-Q4_K_M.gguf",
        "KOKORO_DIR": KOKORO_DIR,
        "DEFAULT_VOICE": "am_michael",
        "VOICE_AGENT_LIVE_OUTPUT_DIR": LOG_DIR,
        "VOICE_AGENT_PROMPT_FILE": os.path.join(V2_DIR, "prompt.md"),
        "VOICE_AGENT_KNOWLEDGE_FILE": os.path.join(V2_DIR, "knowledge.md"),
        "VOICE_AGENT_HISTORY_WINDOW": "24",
        "PYTHONUNBUFFERED": "1",
    })

    with open(log_path, "a") as logf:
        proc = subprocess.Popen(
            [v2_python, "-u", v2_script],
            cwd=V2_DIR,
            stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True,  # Detach from process group
            env=env,
        )
    print(f"  PID: {proc.pid}")
    return proc


def wait_for_health(url, timeout=30):
    """Wait for a service to respond to health check."""
    for _ in range(timeout):
        try:
            subprocess.run(["curl", "-sf", url], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            time.sleep(1)
    return False


def wait_for_port(port, timeout=15):
    """Wait for a port to be listening."""
    for _ in range(timeout):
        try:
            r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=2)
            if f":{port} " in r.stdout:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    kill_existing()

    # Start llama-server
    llama_proc = start_llama()
    print(f"{YELLOW}  Waiting for llama-server...{NC}")
    if not wait_for_health(f"http://127.0.0.1:{LLAMA_PORT}/health"):
        print(f"{RED}  FAILED: llama-server did not start{NC}")
        sys.exit(1)
    print(f"{GREEN}  llama-server OK{NC}")

    # Start v2 server
    v2_proc = start_v2()
    print(f"{YELLOW}  Waiting for AudioSocket server...{NC}")
    if not wait_for_port(V2_PORT):
        print(f"{RED}  FAILED: AudioSocket server did not bind{NC}")
        sys.exit(1)
    print(f"{GREEN}  AudioSocket server OK{NC}")

    print()
    print(f"{GREEN}========================================{NC}")
    print(f"{GREEN} Praxis Voice Agent is LIVE{NC}")
    print(f"{GREEN}========================================{NC}")
    print(f"  Gemma 4 E4B  : 127.0.0.1:{LLAMA_PORT} (PID {llama_proc.pid})")
    print(f"  AudioSocket   : 127.0.0.1:{V2_PORT} (PID {v2_proc.pid})")
    print(f"  Logs          : {LOG_DIR}/")
    print(f"  Stop          : pkill -f 'llama-server.*8099'; pkill -f audiosocket_server")
    print(f"{GREEN}========================================{NC}")


if __name__ == "__main__":
    main()
