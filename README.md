# VERONICA — Voice AI Command Center for Hermes

Jarvis-style voice assistant with a Live2D anime avatar that controls and monitors a [Hermes Agent](https://hermes-agent.nousresearch.com) multi-agent setup — by voice, from the browser.

![status](https://img.shields.io/badge/status-live-white) ![python](https://img.shields.io/badge/python-3.11-white) ![license](https://img.shields.io/badge/license-MIT-white)

## Features

- 🎙 **Voice loop in the browser** — push-to-talk or hands-free VAD; Whisper STT on the server; streaming sentence-by-sentence neural TTS (Indian-English "Neerja" default)
- 👩‍💼 **Live2D avatar** — anime character with real-time lip-sync driven by actual speech audio, listening/thinking/speaking reactions, fullscreen portrait mode
- 🤖 **Hermes bridge** — voice-controls real agents: status reports, start/stop/restart gateways, cron jobs, error queries, task delegation, system health (allowlisted, confirmation-gated, audit-logged)
- 🧠 **Switchable brain** — provider cards (local OmniRoute / OpenRouter / Experiential Labs) + live model list + voice picker with preview, hot-swap without restart
- 📊 **Ops dashboard** — dark futuristic UI: health metrics, agent rows with controls, cron schedule, live activity feed

## Monorepo layout

```
veronica/
├── server/            # FastAPI backend
│   ├── app.py         #   WS voice loop + REST API + static hosting
│   ├── brain.py       #   streaming LLM client with tool-calling
│   ├── bridge.py      #   Hermes/system command bridge (the "hands")
│   ├── stt.py         #   faster-whisper transcription
│   ├── tts.py         #   edge-tts + sentence streamer
│   └── config.py      #   settings, persona, providers, voices
├── web/               # Frontend (vanilla JS + PixiJS/Live2D)
│   ├── index.html     #   dashboard UI
│   ├── app.js         #   voice, avatar, panels, settings
│   ├── capture-worklet.js  # mic downsampler (AudioWorklet)
│   ├── models/        #   Haru, Hiyori, Epsilon, Tsumiki, Shizuku, Kei (Live2D sample models)
│   └── vendor/        #   pixi.js, pixi-live2d-display, cubism core
├── deploy/
│   └── veronica.service   # systemd user unit
├── requirements.txt
└── README.md
```

## Architecture

```
Browser mic ─AudioWorklet 16kHz PCM─▶ WS /ws/voice
  ─▶ faster-whisper (base int8, CPU) ─▶ LLM (tool-calling loop ⇄ Hermes bridge)
  ─▶ sentence split ─▶ edge-tts ─▶ MP3 chunks ─▶ browser playback + lip-sync
```

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 9140
# open http://localhost:9140 (via SSH tunnel on a server)
```

Systemd (user) service:
```bash
cp deploy/veronica.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now veronica
```

## Configuration

Environment variables (all optional):

| Var | Default | Notes |
|---|---|---|
| `VERONICA_LLM_BASE` | `http://localhost:20128/v1` | OpenAI-compatible endpoint |
| `VERONICA_LLM_MODEL` | `auto/best-chat` | default model |
| `VERONICA_VOICE` | `en-IN-NeerjaNeural` | edge-tts voice |
| `VERONICA_WHISPER_MODEL` | `base` | `tiny` for faster/weaker |
| `VERONICA_TOKEN` | (empty) | if set, WS requires `?token=` |

Runtime choices (provider/model/voice) are made in the **Settings** tab and persist to `server/settings.json` (gitignored). Provider API keys are read from local `.env` files at runtime — **no keys live in this repo**.

## Security notes

- Binds to `127.0.0.1` — expose only via SSH tunnel or an authenticated reverse proxy
- Bridge commands are allowlisted; destructive actions require explicit confirmation; protected units (dashboard, veronica itself) can never be stopped
- All bridge actions are audit-logged to `server/logs/actions.log`

## License

MIT (code). The bundled Haru, Hiyori, Epsilon, Tsumiki, Shizuku and Kei models are © Live2D Inc. and redistributed under the [Live2D sample-model terms](https://www.live2d.com/eula/live2d-sample-model-terms_en.html); vendor JS libraries keep their upstream licenses. See `docs/CHARACTERS.md` and `web/models/LIVE2D-LICENSE.md` before commercial redistribution.
