"""Speech-to-text: Deepgram Flux with local Whisper fallback.

Browser sends a complete utterance (endpointed client-side via push-to-talk
or energy VAD in hands-free mode) as 16 kHz mono float32 PCM.
"""
import logging
import time
from urllib.parse import urlencode

import numpy as np
from faster_whisper import WhisperModel
import websockets

from . import config

log = logging.getLogger("veronica.stt")

_model: WhisperModel | None = None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        t0 = time.time()
        _model = WhisperModel(
            config.WHISPER_MODEL,
            device="cpu",
            compute_type=config.WHISPER_COMPUTE,
            cpu_threads=2,
        )
        log.info("whisper %s loaded in %.1fs", config.WHISPER_MODEL, time.time() - t0)
    return _model


def transcribe(pcm_f32: np.ndarray) -> str:
    """Transcribe a float32 mono 16kHz waveform. Returns stripped text ('' if none)."""
    if pcm_f32.size < config.SAMPLE_RATE * 0.3:  # <300ms: ignore
        return ""
    t0 = time.time()
    segments, info = get_model().transcribe(
        pcm_f32,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        initial_prompt=(
            "Veronica, the Hermes command center for Swapnil. "
            "Agents: technologia, gateway, dashboard, cron, OmniRoute, Telegram."
        ),
        beam_size=1,
        condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    log.info("stt %.2fs audio -> %.2fs latency: %r", pcm_f32.size / config.SAMPLE_RATE, time.time() - t0, text)
    return text


async def transcribe_deepgram(pcm_f32: np.ndarray) -> str:
    """Transcribe one complete 16 kHz float32 utterance with Deepgram Flux."""
    key = config.DEEPGRAM_API_KEY
    if not key:
        raise RuntimeError("Deepgram API key is not configured")
    if pcm_f32.size < config.SAMPLE_RATE * 0.3:
        return ""
    params = urlencode({
        "model": config.DEEPGRAM_MODEL,
        "encoding": "linear16",
        "sample_rate": config.SAMPLE_RATE,
        "eot_threshold": 0.7,
        "eot_timeout_ms": 1500,
    })
    uri = f"wss://api.deepgram.com/v2/listen?{params}"
    pcm_i16 = np.clip(pcm_f32, -1.0, 1.0)
    pcm_bytes = (pcm_i16 * 32767).astype("<i2").tobytes()
    t0 = time.time()
    transcripts = []
    async with websockets.connect(
        uri, additional_headers={"Authorization": f"Token {key}"},
        open_timeout=15, close_timeout=5, max_size=4 * 1024 * 1024,
    ) as connection:
        await connection.send(pcm_bytes)
        await connection.send('{"type":"Finalize"}')
        try:
            async for raw in connection:
                msg = raw if isinstance(raw, dict) else __import__("json").loads(raw)
                text = (msg.get("transcript") or "").strip()
                if text:
                    transcripts.append(text)
                if msg.get("event") == "EndOfTurn":
                    break
        except websockets.exceptions.ConnectionClosed:
            pass
    text = transcripts[-1] if transcripts else ""
    log.info("deepgram %.2fs audio -> %.2fs latency: %r", pcm_f32.size / config.SAMPLE_RATE, time.time() - t0, text)
    return text


async def transcribe_async(pcm_f32: np.ndarray) -> str:
    """Use Deepgram when configured; otherwise use the local Whisper path."""
    if config.get_stt_engine() == "deepgram" and config.DEEPGRAM_API_KEY:
        try:
            return await transcribe_deepgram(pcm_f32)
        except Exception as e:  # noqa: BLE001
            log.warning("deepgram failed (%s) -> local whisper fallback", e)
    return await __import__("asyncio").to_thread(transcribe, pcm_f32)
