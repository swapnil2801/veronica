"""Speech-to-text: faster-whisper with built-in Silero VAD filter.

Browser sends a complete utterance (endpointed client-side via push-to-talk
or energy VAD in hands-free mode) as 16 kHz mono float32 PCM.
"""
import logging
import time

import numpy as np
from faster_whisper import WhisperModel

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
