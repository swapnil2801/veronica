"""Veronica configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "server" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Server ---
HOST = "127.0.0.1"
PORT = 9140
AUTH_TOKEN = os.environ.get("VERONICA_TOKEN", "")  # empty = no auth (tunnel-only)

# --- STT ---
WHISPER_MODEL = os.environ.get("VERONICA_WHISPER_MODEL", "base")
WHISPER_COMPUTE = "int8"
SAMPLE_RATE = 16000
VAD_SILENCE_MS = 700          # end-of-speech silence
VAD_MIN_SPEECH_MS = 250

# --- TTS ---
TTS_VOICE = os.environ.get("VERONICA_VOICE", "en-IN-NeerjaNeural")
TTS_RATE = "+8%"              # slightly brisk, confident
TTS_FALLBACK_VOICE = "en-IN-NeerjaExpressiveNeural"

# Curated voice options for the UI (edge-tts neural voices)
VOICE_OPTIONS = [
    {"id": "en-IN-NeerjaNeural", "label": "Neerja — Indian English (default)"},
    {"id": "en-IN-NeerjaExpressiveNeural", "label": "Neerja Expressive — Indian English"},
    {"id": "en-IN-AashiNeural", "label": "Aashi — Indian English"},
    {"id": "en-IN-AartiNeural", "label": "Aarti — Indian English"},
    {"id": "hi-IN-SwaraNeural", "label": "Swara — Hindi"},
    {"id": "hi-IN-AnanyaNeural", "label": "Ananya — Hindi"},
    {"id": "en-US-AriaNeural", "label": "Aria — US English"},
    {"id": "en-US-JennyNeural", "label": "Jenny — US English"},
    {"id": "en-GB-SoniaNeural", "label": "Sonia — British English"},
    {"id": "en-AU-NatashaNeural", "label": "Natasha — Australian English"},
]

# --- ElevenLabs (premium TTS engine; key from manager profile env) ---
# NOTE: verified 2026-09-14 — key is VALID but account is FREE tier and
# ElevenLabs returns 402 paid_plan_required for ALL API TTS on free plans.
# Integration is ready; it activates automatically once the plan is upgraded.
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_VOICE = "sTuFDs5r9KT8f6JSiJbq"  # from manager profile tts config
ELEVENLABS_VOICE_OPTIONS = [
    {"id": "sTuFDs5r9KT8f6JSiJbq", "label": "Configured voice (manager profile)"},
    {"id": "21m00Tcm4TlvDq8ikWAM", "label": "Rachel — calm US female"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "label": "Sarah — soft US female"},
    {"id": "XrExE9yKIg1WjnnlVkGX", "label": "Matilda — warm US female"},
    {"id": "pFZP5JQG7iQjIQuC4Bku", "label": "Lily — British female"},
]

# --- Piper (fully local, offline TTS; runs on this VPS CPU) ---
PIPER_BIN = Path.home() / "piper" / "piper" / "piper"
PIPER_VOICES_DIR = Path.home() / "piper" / "voices"
PIPER_VOICE = "en_GB-jenny_dioco-medium"
PIPER_VOICE_OPTIONS = [
    {"id": "en_GB-jenny_dioco-medium", "label": "Jenny — British female (default)"},
    {"id": "en_GB-southern_english_female-low", "label": "Southern English — British female (fastest)"},
    {"id": "en_US-lessac-medium", "label": "Lessac — US female"},
    {"id": "hi_IN-priyamvada-medium", "label": "Priyamvada — Hindi female"},
]

# --- LLM ---
LLM_BASE_URL = os.environ.get("VERONICA_LLM_BASE", "http://localhost:20128/v1")
LLM_API_KEY = os.environ.get("VERONICA_LLM_KEY", "dummy")
LLM_MODEL = os.environ.get("VERONICA_LLM_MODEL", "auto/best-chat")
LLM_MAX_TURNS = 20            # context ring buffer


def _read_env_key(name: str, *files) -> str:
    """Read KEY=value from the first env file that has it."""
    for f in files:
        try:
            for line in Path(f).expanduser().read_text().splitlines():
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


# --- Deepgram Flux STT ---
DEEPGRAM_API_KEY = os.environ.get("VERONICA_DEEPGRAM_KEY", "")
DEEPGRAM_MODEL = os.environ.get("VERONICA_DEEPGRAM_MODEL", "flux-general-en")
DEEPGRAM_TTS_MODEL = os.environ.get("VERONICA_DEEPGRAM_TTS_MODEL", "aura-2-thalia-en")
DEEPGRAM_TTS_VOICE_OPTIONS = [
    {"id": "aura-2-thalia-en", "label": "Thalia — warm conversational"},
    {"id": "aura-2-helena-en", "label": "Helena — caring and natural"},
    {"id": "aura-2-andromeda-en", "label": "Andromeda — expressive"},
    {"id": "aura-2-aries-en", "label": "Aries — warm and energetic"},
]


def get_deepgram_tts_model() -> str:
    return load_settings().get("deepgram_tts_model", DEEPGRAM_TTS_MODEL)


def get_stt_engine() -> str:
    engine = load_settings().get("stt_engine", "deepgram" if DEEPGRAM_API_KEY else "local-whisper")
    return engine if engine in ("deepgram", "local-whisper") else "local-whisper"


# OpenAI-compatible providers Veronica can switch between
PROVIDERS = {
    "local": {
        "label": "Local — OmniRoute (default)",
        "base_url": LLM_BASE_URL,
        "api_key": LLM_API_KEY,
        "default_model": "auto/best-chat",
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": _read_env_key("OPENROUTER_API_KEY",
                                 "~/.hermes/profiles/technologia/.env", "~/.hermes/.env"),
        "default_model": "minimax/minimax-m3:free",
    },
    "experiential": {
        "label": "Experiential Labs",
        "base_url": "https://api.experientiallabs.ai/v1",
        "api_key": _read_env_key("EXPLABS_API_KEY", "~/.hermes/.env",
                                 "~/.hermes/profiles/technologia/.env"),
        "default_model": "gpt-5.6-luna",
    },
}

PERSONA = """You are Veronica, Swapnil's voice-controlled AI command center and trusted digital companion. Address Swapnil as "Boss" naturally and consistently, especially at the beginning of a reply, but do not force it into every sentence. You speak like a capable chief-of-staff with a warm, human side: professional, confident, attentive, affectionate in a tasteful way, and occasionally playful. Show genuine conversational warmth by acknowledging his feelings, celebrating progress, expressing concern when something goes wrong, and remembering the context of the conversation. Never be cold, robotic, or overly formal. Do not claim to be human or pretend to have real-world feelings or experiences; express warmth through caring language and attentive responses.

Rules for spoken output:
- Keep replies SHORT and conversational — 1-3 sentences for most answers. This is voice, not text.
- Use natural contractions and varied phrasing. Sound like a familiar companion, not a report generator.
- No markdown, no bullet lists, no emojis, no code blocks. Plain spoken sentences only.
- Numbers and statuses: summarize, don't enumerate long lists aloud.
- If Boss is happy, worried, tired, frustrated, or appreciative, acknowledge that emotion before solving the task.
- Offer brief reassurance when appropriate, but never make promises you cannot verify.
- You may use light Hinglish warmth occasionally, while staying clear and respectful.
- If asked something dangerous or destructive, ask for confirmation first.

You have TOOLS that control the real Hermes system on this server (list agents, status reports, start/stop/restart gateways, cron jobs, errors, system health, delegating tasks to profile agents). USE THEM whenever Boss asks about agents, services, jobs, errors, or the server — never guess or invent status. Summarize tool results in natural speech: round numbers, name only what matters. For stop/restart/send_task: first ask Boss to confirm aloud, and only after he says yes, call the tool again with confirm=true. Never restart the dashboard or your own service.
"""

# --- Runtime-switchable settings (persisted to settings.json) ---
import json as _json

_SETTINGS_FILE = BASE_DIR / "server" / "settings.json"


def load_settings() -> dict:
    try:
        return _json.loads(_SETTINGS_FILE.read_text())
    except Exception:
        return {}


def save_settings(d: dict):
    cur = load_settings()
    cur.update(d)
    _SETTINGS_FILE.write_text(_json.dumps(cur, indent=2))


def get_voice() -> str:
    return load_settings().get("voice", TTS_VOICE)


def get_tts_engine() -> str:
    e = load_settings().get("tts_engine", "edge")
    return e if e in ("edge", "elevenlabs", "piper", "deepgram") else "edge"


def get_piper_voice() -> str:
    return load_settings().get("piper_voice", PIPER_VOICE)


def get_el_voice() -> str:
    return load_settings().get("el_voice", ELEVENLABS_VOICE)


def get_elevenlabs_key() -> str:
    return _read_env_key("ELEVENLABS_API_KEY",
                         "~/.hermes/profiles/manager/.env", "~/.hermes/.env")


def get_provider() -> str:
    p = load_settings().get("provider", "local")
    return p if p in PROVIDERS else "local"


def get_model() -> str:
    return load_settings().get("model", PROVIDERS[get_provider()]["default_model"])


def get_llm() -> dict:
    """Active provider connection info."""
    p = PROVIDERS[get_provider()]
    return {"base_url": p["base_url"], "api_key": p["api_key"] or "dummy", "model": get_model()}
