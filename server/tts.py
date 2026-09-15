"""Text-to-speech: switchable engine.

edge      -> edge-tts neural voices (free cloud, default)
piper     -> Piper local ONNX TTS (fully offline, runs on this CPU)
elevenlabs-> ElevenLabs API (premium; requires paid plan for API TTS).


Every engine falls back to edge automatically on failure; piper is also
the fallback if edge itself dies (offline resilience), so Veronica only
goes text-only if ALL engines fail.
"""
import asyncio
import base64
import logging
import re

import edge_tts
import httpx

from . import config

log = logging.getLogger("veronica.tts")

_SENT_SPLIT = re.compile(r"(?<=[.!?।])\s+")


async def _synth_piper(text: str, voice: str | None = None) -> bytes:
    """Local Piper synthesis -> MP3 bytes (WAV piped through ffmpeg)."""
    v = voice or config.get_piper_voice()
    model = config.PIPER_VOICES_DIR / f"{v}.onnx"
    if not config.PIPER_BIN.exists() or not model.exists():
        raise RuntimeError(f"piper or voice missing: {v}")
    # piper (WAV to stdout) | ffmpeg (WAV -> MP3) — browser expects MP3
    cmd = (
        f"{config.PIPER_BIN} -m {model} -f - -q | "
        f"ffmpeg -v error -i - -codec:a libmp3lame -b:a 64k -f mp3 -"
    )
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await asyncio.wait_for(proc.communicate(text.encode()), timeout=30)
    if proc.returncode != 0 or not out:
        raise RuntimeError(f"piper failed: {err.decode()[:150]}")
    return out


async def _synth_elevenlabs(text: str) -> bytes:
    key = config.get_elevenlabs_key()
    if not key:
        raise RuntimeError("no ELEVENLABS_API_KEY")
    voice = config.get_el_voice()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={"text": text, "model_id": config.ELEVENLABS_MODEL,
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
        )
        if r.status_code != 200:
            raise RuntimeError(f"elevenlabs {r.status_code}: {r.text[:120]}")
        return r.content


        return r.content


async def _synth_deepgram(text: str, model: str | None = None) -> bytes:
    """Deepgram Flux TTS batch endpoint -> MP3 bytes."""
    if not config.DEEPGRAM_API_KEY:
        raise RuntimeError("Deepgram API key is not configured")
    voice_model = model or config.get_deepgram_tts_model()
    async with httpx.AsyncClient(timeout=45) as c:
        r = await c.post("https://api.deepgram.com/v2/speak",
                         params={"model": voice_model, "encoding": "mp3"},
                         headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}", "Content-Type": "application/json"},
                         json={"text": text})
        if r.status_code != 200:
            raise RuntimeError(f"deepgram {r.status_code}: {r.text[:160]}")
        if not r.content:
            raise RuntimeError("Deepgram returned empty audio")
        return r.content


async def _synth_cartesia(text: str) -> bytes:
    """Cartesia Sonic cloud TTS -> MP3 bytes."""
    key = config.get_cartesia_key()
    if not key:
        raise RuntimeError("Cartesia API key is not configured")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post("https://api.cartesia.ai/tts/bytes",
                         headers={"X-API-Key": key, "Cartesia-Version": config.CARTESIA_VERSION, "Content-Type": "application/json"},
                         json={"model_id": config.CARTESIA_MODEL, "transcript": text, "voice": {"id": config.get_cartesia_voice()}, "language": "en", "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000}})
        if r.status_code != 200:
            raise RuntimeError(f"cartesia {r.status_code}: {r.text[:160]}")
        if not r.content:
            raise RuntimeError("Cartesia returned empty audio")
        return r.content


async def _synth_sarvam(text: str, voice: str | None = None) -> bytes:
    """Sarvam Bulbul v3 cloud TTS -> MP3 bytes."""
    key = config.get_sarvam_key()
    if not key:
        raise RuntimeError("Sarvam API key is not configured")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.sarvam.ai/text-to-speech",
                         headers={"api-subscription-key": key, "Content-Type": "application/json"},
                         json={"text": text[:1500], "target_language_code": config.SARVAM_LANG,
                               "speaker": voice or config.get_sarvam_voice(), "model": config.SARVAM_TTS_MODEL,
                               "output_audio_codec": "mp3", "speech_sample_rate": 24000})
        if r.status_code != 200:
            raise RuntimeError(f"sarvam {r.status_code}: {r.text[:160]}")
        audios = r.json().get("audios") or []
        if not audios:
            raise RuntimeError("Sarvam returned empty audio")
        return base64.b64decode(audios[0])


async def _synth_edge(text: str) -> bytes:
    for voice in (config.get_voice(), config.TTS_FALLBACK_VOICE):
        try:
            buf = bytearray()
            communicate = edge_tts.Communicate(text, voice, rate=config.TTS_RATE)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
            if buf:
                return bytes(buf)
        except Exception as e:  # noqa: BLE001
            log.warning("edge voice %s failed: %s", voice, e)
    raise RuntimeError("all edge voices failed")


async def synthesize(text: str) -> bytes:
    """Synthesize one utterance to MP3 bytes. Raises on total failure."""
    engine = config.get_tts_engine()
    if engine == "cartesia":
        try:
            return await _synth_cartesia(text)
        except Exception as e:  # noqa: BLE001
            log.warning("cartesia failed (%s) -> edge fallback", e)
    elif engine == "sarvam":
        try:
            return await _synth_sarvam(text)
        except Exception as e:  # noqa: BLE001
            log.warning("sarvam failed (%s) -> edge fallback", e)
    elif engine == "deepgram":
        try:
            return await _synth_deepgram(text)
        except Exception as e:  # noqa: BLE001
            log.warning("deepgram TTS failed (%s) -> edge fallback", e)
    elif engine == "elevenlabs":
        try:
            return await _synth_elevenlabs(text)
        except Exception as e:  # noqa: BLE001
            log.warning("elevenlabs failed (%s) -> edge fallback", e)
    elif engine == "piper":
        try:
            return await _synth_piper(text)
        except Exception as e:  # noqa: BLE001
            log.warning("piper failed (%s) -> edge fallback", e)

    try:
        return await _synth_edge(text)
    except Exception as e:  # noqa: BLE001
        if engine != "piper":  # edge died: last resort = local piper
            log.warning("edge failed (%s) -> piper last-resort", e)
            return await _synth_piper(text)
        raise


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text)]
    return [p for p in parts if p]


class SentenceStreamer:
    """Accumulates LLM token deltas; yields complete sentences for eager TTS."""

    def __init__(self):
        self._buf = ""

    def feed(self, delta: str) -> list[str]:
        self._buf += delta
        out = []
        while True:
            m = _SENT_SPLIT.search(self._buf)
            if not m:
                break
            out.append(self._buf[: m.start()].strip())
            self._buf = self._buf[m.end():]
        return [s for s in out if s]

    def flush(self) -> str:
        s, self._buf = self._buf.strip(), ""
        return s
