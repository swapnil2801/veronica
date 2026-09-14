"""Text-to-speech: switchable engine.

edge      -> edge-tts neural voices (free, default)
elevenlabs-> ElevenLabs API (premium; requires paid plan for API TTS).
             Falls back to edge automatically on any failure, so a dead
             key / free-tier 402 never silences Veronica.
"""
import asyncio
import logging
import re

import edge_tts
import httpx

from . import config

log = logging.getLogger("veronica.tts")

_SENT_SPLIT = re.compile(r"(?<=[.!?।])\s+")


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
    if config.get_tts_engine() == "elevenlabs":
        try:
            return await _synth_elevenlabs(text)
        except Exception as e:  # noqa: BLE001
            log.warning("elevenlabs failed (%s) -> edge fallback", e)
    return await _synth_edge(text)


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
