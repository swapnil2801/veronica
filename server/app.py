"""Veronica FastAPI app — Phase 1: browser voice loop.

WebSocket protocol (/ws/voice):
  client -> server:
    binary frame          : float32 mono 16kHz PCM chunk of the utterance
    {"type":"end_utterance"} : utterance finished -> transcribe & respond
    {"type":"text","text":..} : typed input (skips STT)
  server -> client:
    {"type":"transcript","text":..}          user's transcribed words
    {"type":"reply_delta","text":..}         Veronica reply text (streaming)
    {"type":"reply_done"}
    {"type":"audio_sentence"} + binary MP3   one spoken sentence, play in order
    {"type":"speaking_done"}
    {"type":"error","message":..}
"""
import asyncio
import json
import logging

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import bridge, config, stt, tts
from .brain import Brain

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(config.LOG_DIR / "veronica.log")],
)
log = logging.getLogger("veronica.app")

app = FastAPI(title="Veronica")


@app.on_event("startup")
async def warmup():
    """Preload whisper so the first utterance isn't slow."""
    import numpy as np

    def _load():
        stt.get_model()
        stt.transcribe(np.zeros(16000, dtype=np.float32))  # jit warmup

    await asyncio.to_thread(_load)
    log.info("warmup complete")


@app.get("/health")
async def health():
    return {"ok": True, "voice": config.get_voice(), "model": config.get_model()}


# ---------------- Settings API ----------------

@app.get("/api/settings")
async def api_settings():
    return {
        "provider": config.get_provider(),
        "providers": [
            {"id": k, "label": v["label"], "has_key": bool(v["api_key"])}
            for k, v in config.PROVIDERS.items()
        ],
        "model": config.get_model(),
        "voice": config.get_voice(),
        "voices": config.VOICE_OPTIONS,
    }


@app.get("/api/models")
async def api_models(provider: str = ""):
    """Live model list from the active (or given) provider."""
    import httpx
    prov = config.PROVIDERS.get(provider or config.get_provider(), config.PROVIDERS["local"])
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{prov['base_url']}/models",
                            headers={"Authorization": f"Bearer {prov['api_key'] or 'dummy'}"})
            ids = [m["id"] for m in r.json().get("data", [])]
    except Exception as e:  # noqa: BLE001
        return {"models": [prov["default_model"]], "error": str(e)}
    combos = sorted(i for i in ids if i.startswith("auto/") or i == "auto")
    free = sorted(i for i in ids if ":free" in i)
    rest = sorted(i for i in ids if i not in combos and i not in free)
    return {"models": combos + free + rest, "count": len(ids), "default": prov["default_model"]}


@app.post("/api/settings")
async def api_set_settings(payload: dict):
    changed = {}
    if "provider" in payload and payload["provider"] in config.PROVIDERS:
        changed["provider"] = payload["provider"]
        # switching provider resets model to that provider's default unless one given
        changed["model"] = config.PROVIDERS[payload["provider"]]["default_model"]
    if "model" in payload and isinstance(payload["model"], str) and payload["model"].strip():
        changed["model"] = payload["model"].strip()
    if "voice" in payload and isinstance(payload["voice"], str) and payload["voice"].strip():
        changed["voice"] = payload["voice"].strip()
    if changed:
        config.save_settings(changed)
        log.info("settings changed: %s", changed)
    return {"ok": True, "provider": config.get_provider(), "model": config.get_model(), "voice": config.get_voice()}


@app.post("/api/settings/preview_voice")
async def api_preview_voice(payload: dict):
    """Synthesize a short sample in the given voice; returns MP3."""
    from fastapi.responses import Response
    voice = (payload.get("voice") or config.get_voice()).strip()
    text = "Hello Swapnil, this is how I sound. Shall I keep this voice?"
    try:
        import edge_tts
        buf = bytearray()
        communicate = edge_tts.Communicate(text, voice, rate=config.TTS_RATE)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return Response(content=bytes(buf), media_type="audio/mpeg")
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


# ---------------- Dashboard REST API ----------------

@app.get("/api/agents")
async def api_agents():
    return await asyncio.to_thread(bridge.list_agents)


@app.get("/api/system")
async def api_system():
    return await asyncio.to_thread(bridge.system_health)


@app.get("/api/cron")
async def api_cron():
    return await asyncio.to_thread(bridge.list_cron_jobs)


@app.get("/api/errors")
async def api_errors(minutes: int = 60):
    return await asyncio.to_thread(bridge.get_errors, minutes)


@app.post("/api/agents/{name}/{action}")
async def api_control(name: str, action: str):
    return await asyncio.to_thread(bridge.control_agent, name, action, True)


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """5s ticks: system health + agent statuses + recent journal lines."""
    await ws.accept()
    proc = await asyncio.create_subprocess_exec(
        "journalctl", "--user", "-u", "hermes-gateway*", "-u", "hermes-dashboard",
        "-f", "-n", "10", "--no-pager", "-o", "short",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )

    async def tail():
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                await ws.send_json({"type": "log", "line": line.decode(errors="replace").rstrip()[:400]})
            except Exception:
                break

    tail_task = asyncio.create_task(tail())
    try:
        n = 0
        while True:
            sysd = await asyncio.to_thread(bridge.system_health)
            payload = {"type": "tick", "system": sysd}
            if n % 3 == 0:  # full agent scan only every 15s
                agents = await asyncio.to_thread(bridge.list_agents)
                payload["agents"] = agents["services"]
            await ws.send_json(payload)
            n += 1
            await asyncio.sleep(5)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        tail_task.cancel()
        try:
            proc.terminate()
        except ProcessLookupError:
            pass


@app.websocket("/ws/voice")
async def ws_voice(ws: WebSocket):
    if config.AUTH_TOKEN and ws.query_params.get("token") != config.AUTH_TOKEN:
        await ws.close(code=4401)
        return
    await ws.accept()
    brain = Brain()
    audio_buf: list[np.ndarray] = []
    log.info("voice session connected")

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                audio_buf.append(np.frombuffer(msg["bytes"], dtype=np.float32))
                continue
            if msg.get("text") is None:
                continue
            import json
            data = json.loads(msg["text"])

            if data.get("type") == "end_utterance":
                if not audio_buf:
                    continue
                pcm = np.concatenate(audio_buf)
                audio_buf = []
                text = await asyncio.to_thread(stt.transcribe, pcm)
                if not text:
                    await ws.send_json({"type": "transcript", "text": ""})
                    continue
                await ws.send_json({"type": "transcript", "text": text})
                await respond(ws, brain, text)

            elif data.get("type") == "text":
                user_text = (data.get("text") or "").strip()
                if user_text:
                    await ws.send_json({"type": "transcript", "text": user_text})
                    await respond(ws, brain, user_text)

    except WebSocketDisconnect:
        log.info("voice session closed")
    except Exception:
        log.exception("voice session error")
        try:
            await ws.send_json({"type": "error", "message": "internal error"})
        except Exception:
            pass


async def respond(ws: WebSocket, brain: Brain, user_text: str):
    """Stream LLM reply; TTS each sentence eagerly and ship audio in order."""
    streamer = tts.SentenceStreamer()
    tts_queue: asyncio.Queue = asyncio.Queue()

    async def tts_worker():
        while True:
            sentence = await tts_queue.get()
            if sentence is None:
                break
            try:
                mp3 = await tts.synthesize(sentence)
                await ws.send_json({"type": "audio_sentence", "text": sentence})
                await ws.send_bytes(mp3)
            except Exception as e:  # noqa: BLE001
                log.warning("tts failed, text-only: %s", e)
                await ws.send_json({"type": "caption", "text": sentence})
        await ws.send_json({"type": "speaking_done"})

    worker = asyncio.create_task(tts_worker())

    async def on_tool(name, args):
        await ws.send_json({"type": "tool", "name": name, "args": args})

    try:
        async for delta in brain.stream_reply(user_text, on_tool=on_tool):
            await ws.send_json({"type": "reply_delta", "text": delta})
            for sentence in streamer.feed(delta):
                await tts_queue.put(sentence)
        tail = streamer.flush()
        if tail:
            await tts_queue.put(tail)
        await ws.send_json({"type": "reply_done"})
    except Exception as e:  # noqa: BLE001
        log.exception("brain error")
        await ws.send_json({"type": "error", "message": f"LLM error: {e}"})
    finally:
        await tts_queue.put(None)
        await worker


app.mount("/", StaticFiles(directory=str(config.BASE_DIR / "web"), html=True), name="web")
