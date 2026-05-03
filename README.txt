v1 turn-based AGI vs v2 live AudioSocket

Folders
v1:
/home/johnfab/apps/voice-agent

v2:
/home/johnfab/apps/voice-agent-live-v2

What v2 is
- Separate prototype using Asterisk AudioSocket instead of AGI Record/Stream.
- Keeps the working v1 untouched.
- Streams 8 kHz PCM frames over TCP from Asterisk into Python.
- Uses energy-based VAD to detect start/end of utterances.
- Supports simple barge-in: if caller starts talking while TTS is playing, playback is interrupted.
- Still not full duplex human-level conversation, but it is the right direction and should feel less walkie-talkie than v1.

Important comparison
v1:
- Asterisk RECORD FILE
- whole utterance captured first
- Gemma request/response
- Kokoro full WAV
- Asterisk STREAM FILE
- obvious turns

v2:
- Asterisk AudioSocket TCP stream
- continuous inbound audio frames
- utterance end decided by VAD/silence threshold
- TTS can be interrupted by caller speech
- lower latency between turns
- better foundation for future streaming/ARI/barge-in work

Files
Main server:
/home/johnfab/apps/voice-agent-live-v2/audiosocket_server.py

Start script:
/home/johnfab/apps/voice-agent-live-v2/start-live-v2.sh

Asterisk PJSIP snippet:
/home/johnfab/apps/voice-agent-live-v2/asterisk/pjsip-live.conf

Asterisk dialplan snippet:
/home/johnfab/apps/voice-agent-live-v2/asterisk/extensions-live.conf

Runtime output:
/tmp/voice-agent-live-v2

Test account for v2
username: testlive
password: testlive123
context: from-softphone-live

How to run v2 server
1. Make sure Gemma server is already healthy on 127.0.0.1:8099.
2. Start the v2 AudioSocket bridge:
   /home/johnfab/apps/voice-agent-live-v2/start-live-v2.sh
3. It listens on 127.0.0.1:9019.

How to wire Asterisk for v2 testing
Do not overwrite v1 blindly.

Recommended approach:
- Merge the testlive endpoint from:
  /home/johnfab/apps/voice-agent-live-v2/asterisk/pjsip-live.conf
  into /etc/asterisk/pjsip.conf

- Merge the from-softphone-live context from:
  /home/johnfab/apps/voice-agent-live-v2/asterisk/extensions-live.conf
  into /etc/asterisk/extensions.conf

- Reload:
  sudo asterisk -rx 'pjsip reload'
  sudo asterisk -rx 'dialplan reload'

How to test v2 with baresip
Create another account or use a separate config with:
- SIP user: testlive
- password: testlive123
- domain: current LAN IP
- transport: udp

Then dial any number, for example:
- 200
or
- sip:200@CURRENT_LAN_IP

With the provided dialplan, all digits from testlive go to v2 because the context uses _X. routing.

Current VAD / turn settings in v2
Start speaking threshold:
- VAD_START_RMS=700

Continue threshold:
- VAD_CONTINUE_RMS=500

Minimum utterance:
- MIN_UTTERANCE_MS=350

End silence:
- END_SILENCE_MS=1200

Barge-in trigger:
- BARGE_IN_MS=180

Max utterance length:
- MAX_UTTERANCE_MS=9000

These are env-tunable in start-live-v2.sh.

Known limitations of v2 right now
- Uses energy-based VAD, not webrtcvad.
- Single-call oriented prototype.
- Gemma call is still request/response, so it cannot think while continuing to listen forever.
- TTS is still generated as a whole response, but playback can be interrupted.
- Not yet integrated with ARI or externalMedia.

Suggested next improvements
1. Replace RMS VAD with webrtcvad.
2. Split outbound TTS into smaller sentence chunks.
3. Add per-call worker threads so the server handles multiple calls cleanly.
4. Add optional whisper/faster-whisper streaming STT to compare against Gemma audio input.
5. Move to ARI/external media if we want true call control and stronger barge-in.
