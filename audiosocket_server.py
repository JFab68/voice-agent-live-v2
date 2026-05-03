#!/home/johnfab/apps/voice-agent-venv/bin/python3
import audioop
import base64
import math
import os
import pickle
import queue
import signal
import socket
import struct
import tempfile
import threading
import time
import traceback
import wave
from dataclasses import dataclass, field
from typing import Optional

import httpx
import numpy as np
import onnxruntime as rt
from kokoro_onnx.tokenizer import Tokenizer
from scipy.signal import resample_poly

FRAME_HANGUP = 0x00
FRAME_UUID = 0x01
FRAME_AUDIO = 0x10
FRAME_ERROR = 0xFF

HOST = os.getenv("AUDIO_SOCKET_HOST", "127.0.0.1")
PORT = int(os.getenv("AUDIO_SOCKET_PORT", "9019"))
LLM_BASE = os.getenv("LLM_BASE", "http://127.0.0.1:8099")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma-4-E4B-it-Q4_K_M.gguf")
KOKORO_DIR = os.getenv("KOKORO_DIR", "/home/johnfab/apps/voice-agent-models/kokoro")
KOKORO_MODEL = os.path.join(KOKORO_DIR, "onnx/model.onnx")
KOKORO_VOICES = os.path.join(KOKORO_DIR, "voices.npy")
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "am_michael")
OUTPUT_DIR = os.getenv("VOICE_AGENT_LIVE_OUTPUT_DIR", "/tmp/voice-agent-live-v2")
LOG_PREFIX = os.getenv("VOICE_AGENT_LIVE_LOG_PREFIX", "[voice-agent-live-v2]")

VAD_START_RMS = int(os.getenv("VAD_START_RMS", "700"))
VAD_CONTINUE_RMS = int(os.getenv("VAD_CONTINUE_RMS", "500"))
MIN_UTTERANCE_MS = int(os.getenv("MIN_UTTERANCE_MS", "350"))
END_SILENCE_MS = int(os.getenv("END_SILENCE_MS", "1200"))
BARGE_IN_MS = int(os.getenv("BARGE_IN_MS", "180"))
MAX_UTTERANCE_MS = int(os.getenv("MAX_UTTERANCE_MS", "9000"))

SYSTEM_PROMPT = os.getenv(
    "VOICE_AGENT_PROMPT",
    """You are a professional business phone agent answering calls.

Rules:
- Keep responses short and highly intelligible over phone audio.
- Speak plainly with common words and crisp phrasing.
- Prefer 1-2 short sentences unless the caller explicitly asks for more.
- If interrupted, stop and address the new request.
- Never invent policies, pricing, hours, or commitments.
- If uncertain, say so briefly and offer the next step.""",
)

_shutdown = False
_tts_lock = threading.Lock()
_tts = None


def log(msg: str) -> None:
    print(f"{LOG_PREFIX} {time.strftime('%H:%M:%S')} {msg}", flush=True)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf


def recv_frame(sock: socket.socket):
    hdr = recv_exact(sock, 3)
    ftype = hdr[0]
    length = struct.unpack(">H", hdr[1:3])[0]
    payload = recv_exact(sock, length) if length else b""
    return ftype, payload


def send_frame(sock: socket.socket, ftype: int, payload: bytes = b"") -> None:
    sock.sendall(bytes([ftype]) + struct.pack(">H", len(payload)) + payload)


def wav_bytes_from_pcm16(pcm16: bytes, sample_rate: int = 8000) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm16)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


class KokoroTTS:
    def __init__(self):
        with open(KOKORO_VOICES, "rb") as f:
            self.voices = pickle.load(f)
        self.sess = rt.InferenceSession(KOKORO_MODEL)
        self.tokenizer = Tokenizer()

    def synthesize(self, text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0):
        phonemes = self.tokenizer.phonemize(text, lang="en-us")
        tokens = self.tokenizer.tokenize(phonemes)
        input_ids = np.array([tokens], dtype=np.int64)
        style = self.voices[voice][:20, 0, :].mean(axis=0, keepdims=True)
        speed_arr = np.array([speed], dtype=np.float32)
        t0 = time.time()
        audio = self.sess.run(None, {
            "input_ids": input_ids,
            "style": style,
            "speed": speed_arr,
        })[0]
        return audio[0].astype(np.float32), 24000, time.time() - t0


def get_tts() -> KokoroTTS:
    global _tts
    with _tts_lock:
        if _tts is None:
            _tts = KokoroTTS()
            log(f"kokoro loaded voice={DEFAULT_VOICE}")
        return _tts


def float_audio_to_8k_pcm16(audio: np.ndarray, sr: int) -> bytes:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if sr != 8000:
        g = math.gcd(int(sr), 8000)
        audio = resample_poly(audio, 8000 // g, int(sr) // g).astype(np.float32)
    if len(audio):
        audio = audio - float(np.mean(audio))
        audio = np.append(audio[0], audio[1:] - 0.72 * audio[:-1]).astype(np.float32)
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0:
        audio = audio * (0.88 / peak)
    audio = np.clip(audio, -0.98, 0.98)
    int16 = (audio * 32767.0).astype(np.int16)
    return int16.tobytes()


def chunk_pcm16(pcm: bytes, ms: int = 20):
    bytes_per_chunk = 2 * (8000 * ms // 1000)
    for i in range(0, len(pcm), bytes_per_chunk):
        yield pcm[i:i + bytes_per_chunk]


@dataclass
class Session:
    conn: socket.socket
    addr: tuple
    call_id: str = "unknown"
    frame_ms: int = 20
    state_lock: threading.Lock = field(default_factory=threading.Lock)
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    history: list = field(default_factory=list)
    tts_queue: queue.Queue = field(default_factory=queue.Queue)
    active: bool = True
    speech_active: bool = False
    speech_ms: int = 0
    silence_ms: int = 0
    barge_in_ms: int = 0
    processing: bool = False
    playback_generation: int = 0
    playback_active: bool = False
    current_pcm: bytearray = field(default_factory=bytearray)

    def bump_generation(self):
        with self.state_lock:
            self.playback_generation += 1
            return self.playback_generation

    def current_generation(self):
        with self.state_lock:
            return self.playback_generation

    def set_playback_active(self, value: bool):
        with self.state_lock:
            self.playback_active = value

    def interrupt_playback(self):
        gen = self.bump_generation()
        self.set_playback_active(False)
        drained = 0
        try:
            while True:
                self.tts_queue.get_nowait()
                drained += 1
        except queue.Empty:
            pass
        log(f"call={self.call_id} barge-in interrupt generation={gen} drained={drained}")

    def queue_text(self, text: str):
        self.tts_queue.put(text)

    def send_pcm(self, pcm: bytes, generation: int):
        self.set_playback_active(True)
        try:
            for chunk in chunk_pcm16(pcm, ms=self.frame_ms):
                if not self.active or generation != self.current_generation():
                    break
                with self.send_lock:
                    send_frame(self.conn, FRAME_AUDIO, chunk)
                time.sleep(self.frame_ms / 1000.0)
        finally:
            if generation == self.current_generation():
                self.set_playback_active(False)

    def playback_loop(self):
        while self.active:
            try:
                text = self.tts_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                t0 = time.time()
                audio, sr, tts_time = get_tts().synthesize(text)
                pcm = float_audio_to_8k_pcm16(audio, sr)
                generation = self.bump_generation()
                out_path = os.path.join(OUTPUT_DIR, f"call_{self.call_id}_play_{int(time.time()*1000)}.wav")
                with wave.open(out_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(8000)
                    wf.writeframes(pcm)
                log(f"call={self.call_id} tts_ready seconds={len(pcm)/16000:.2f} synth={tts_time:.2f}s total={time.time()-t0:.2f}s text={text[:80]!r}")
                self.send_pcm(pcm, generation)
            except Exception as e:
                log(f"call={self.call_id} playback error: {e}\n{traceback.format_exc()}")

    def llm_reply(self, pcm16: bytes) -> str:
        wav_bytes = wav_bytes_from_pcm16(pcm16, 8000)
        audio_b64 = base64.b64encode(wav_bytes).decode()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *self.history, {
            "role": "user",
            "content": [
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
                {"type": "text", "text": "Respond to the caller."},
            ],
        }]
        with httpx.Client(base_url=LLM_BASE, timeout=30) as client:
            r = client.post(
                "/v1/chat/completions",
                json={
                    "model": LLM_MODEL,
                    "messages": messages,
                    "max_tokens": 120,
                    "temperature": 0.45,
                },
            )
            r.raise_for_status()
            reply = r.json()["choices"][0]["message"]["content"].strip()
        self.history.append({"role": "user", "content": "[audio input]"})
        self.history.append({"role": "assistant", "content": reply})
        self.history = self.history[-12:]
        return reply

    def process_utterance(self, pcm16: bytes):
        with self.state_lock:
            if self.processing or not self.active:
                return
            self.processing = True
        try:
            out_path = os.path.join(OUTPUT_DIR, f"call_{self.call_id}_utt_{int(time.time()*1000)}.wav")
            with wave.open(out_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(8000)
                wf.writeframes(pcm16)
            log(f"call={self.call_id} utterance bytes={len(pcm16)} dur={len(pcm16)/16000:.2f}s")
            t0 = time.time()
            reply = self.llm_reply(pcm16)
            log(f"call={self.call_id} llm_done in={time.time()-t0:.2f}s reply={reply[:120]!r}")
            self.queue_text(reply)
        except Exception as e:
            log(f"call={self.call_id} llm error: {e}\n{traceback.format_exc()}")
            self.queue_text("Sorry, I hit a technical issue. Could you say that again?")
        finally:
            with self.state_lock:
                self.processing = False

    def handle_audio_frame(self, payload: bytes):
        if not payload or len(payload) < 2:
            return
        rms = audioop.rms(payload, 2)
        threshold = VAD_CONTINUE_RMS if self.speech_active else VAD_START_RMS
        speaking = rms >= threshold

        if speaking:
            if self.playback_active:
                self.barge_in_ms += self.frame_ms
                if self.barge_in_ms >= BARGE_IN_MS:
                    self.interrupt_playback()
                    self.barge_in_ms = 0
            else:
                self.barge_in_ms = 0

            if not self.speech_active:
                self.speech_active = True
                self.current_pcm = bytearray()
                self.speech_ms = 0
                self.silence_ms = 0
                log(f"call={self.call_id} speech_start rms={rms}")

            self.current_pcm.extend(payload)
            self.speech_ms += self.frame_ms
            self.silence_ms = 0

            if self.speech_ms >= MAX_UTTERANCE_MS:
                pcm = bytes(self.current_pcm)
                self.speech_active = False
                self.current_pcm = bytearray()
                threading.Thread(target=self.process_utterance, args=(pcm,), daemon=True).start()
            return

        self.barge_in_ms = 0
        if not self.speech_active:
            return

        self.current_pcm.extend(payload)
        self.silence_ms += self.frame_ms
        if self.silence_ms >= END_SILENCE_MS:
            pcm = bytes(self.current_pcm)
            speech_ms = self.speech_ms
            self.speech_active = False
            self.current_pcm = bytearray()
            self.speech_ms = 0
            self.silence_ms = 0
            if speech_ms >= MIN_UTTERANCE_MS:
                threading.Thread(target=self.process_utterance, args=(pcm,), daemon=True).start()
            else:
                log(f"call={self.call_id} discarded short utterance dur={speech_ms}ms")

    def run(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        threading.Thread(target=self.playback_loop, daemon=True).start()
        self.queue_text("Hello, how can I help you today?")
        log(f"connected from={self.addr}")
        try:
            while self.active:
                ftype, payload = recv_frame(self.conn)
                if ftype == FRAME_UUID:
                    raw = payload.decode("utf-8", errors="replace")
                    self.call_id = raw.replace("\x00", "").strip() or self.call_id
                    log(f"call={self.call_id} uuid received")
                elif ftype == FRAME_AUDIO:
                    self.handle_audio_frame(payload)
                elif ftype == FRAME_HANGUP:
                    log(f"call={self.call_id} hangup frame")
                    break
                elif ftype == FRAME_ERROR:
                    log(f"call={self.call_id} error frame={payload!r}")
                    break
                else:
                    log(f"call={self.call_id} unhandled frame type=0x{ftype:02x} bytes={len(payload)}")
        except Exception as e:
            log(f"call={self.call_id} session error: {e}")
        finally:
            self.active = False
            self.set_playback_active(False)
            try:
                self.conn.close()
            except OSError:
                pass
            log(f"call={self.call_id} closed")


def serve():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        log(f"listening on {HOST}:{PORT}")
        while not _shutdown:
            try:
                conn, addr = s.accept()
            except OSError:
                continue
            Session(conn=conn, addr=addr).run()


def handle_signal(signum, frame):
    global _shutdown
    _shutdown = True
    log(f"signal={signum} shutting down")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    serve()
