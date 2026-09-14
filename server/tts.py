"""Text-to-speech: edge-tts (en-IN Neerja, primary) -> text-only fallback.

Produces MP3 chunks suitable for progressive playback in the browser.
"""
import asyncio
import logging
import re

import edge_tts

from . import config

log = logging.getLogger("veronica.tts")

_SENT_SPLIT = re.compile(r"(?<=[.!?।])\s+")


async def synthesize(text: str) -> bytes:
    """Synthesize one utterance to MP3 bytes. Raises on total failure."""
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
            log.warning("tts voice %s failed: %s", voice, e)
    raise RuntimeError("all TTS voices failed")


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
