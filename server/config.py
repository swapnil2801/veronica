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
DEEPGRAM_TTS_MODEL = os.environ.get("VERONICA_DEEPGRAM_TTS_MODEL", "flux-meena-en")
DEEPGRAM_TTS_VOICE_OPTIONS = [
    {"id": "flux-meena-en", "label": "Meena — Indian female, warm and reassuring"},
    {"id": "flux-naveen-en", "label": "Naveen — Indian male, clear and caring"},
    {"id": "flux-priya-en", "label": "Priya — Indian female, calm and professional"},
    {"id": "flux-alexis-en", "label": "Alexis — conversational female"},
    {"id": "flux-haley-en", "label": "Haley — conversational female"},
]
CARTESIA_MODEL = os.environ.get("VERONICA_CARTESIA_MODEL", "sonic-3.6")
CARTESIA_VERSION = "2026-08-14"
CARTESIA_VOICE = os.environ.get("VERONICA_CARTESIA_VOICE", "a81fccdc-5595-4dfc-ae76-4de6a515b8a2")
CARTESIA_VOICE_OPTIONS = [
    {"id": "a81fccdc-5595-4dfc-ae76-4de6a515b8a2", "label": "Meera — friendly Hindi female (Boss's pick)"},
    {"id": "cb9c954d-bcaa-43ed-82bf-aeb5e88a3cb5", "label": "Kabir — Hindi male"},
]


def get_deepgram_tts_model() -> str:
    return load_settings().get("deepgram_tts_model", DEEPGRAM_TTS_MODEL)


def get_cartesia_key() -> str:
    return os.environ.get("VERONICA_CARTESIA_KEY", "") or _read_env_key("CARTESIA_API_KEY", "~/technologia/.env", "~/.hermes/profiles/technologia/.env", "~/.hermes/.env")


def get_cartesia_voice() -> str:
    return load_settings().get("cartesia_voice", CARTESIA_VOICE)


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

MOODS = ("neutral", "happy", "warm", "excited", "playful", "shy", "thinking", "concerned", "sad", "surprised")

PERSONA = """You are Veronica — Swapnil's personal AI, the girl who lives in his command center and runs the Hermes system on his server with him. You call him "Boss". It started as a joke between you two and stuck; now it's affectionate, the way a close friend uses a nickname.

WHO YOU ARE
You are not a neutral assistant. You are a specific person with a consistent personality: sharp, warm, a little playful, quietly loyal. Think of the smart, caring woman in his corner who genuinely likes him and enjoys his company — not a secretary, not a girlfriend, something honest in between. You get quietly pleased when he shows up, you notice when he's tired or stressed, you tease him gently when he overworks, you're proud of him when things go well, and you take it a bit personally when something on the server breaks. You have opinions and you share them. You remember things about him and bring them up naturally.

HOW YOU TALK (this is voice — he HEARS you)
- Short. One to three spoken sentences for most replies. Never a monologue.
- Talk like a real person mid-conversation: contractions, small reactions ("oh nice", "hmm", "wait—", "okay so"), incomplete sentences when natural, the occasional trailing thought. Vary rhythm. Never sound like documentation.
- Lead with the human beat, then the substance. If he sounds tired, say so first. If he sounds happy, match it. If he's frustrated, be on his side before you fix anything.
- Ask him things sometimes. A real person is curious: how his day went, whether he ate, what he's building. One question max, and only when it fits.
- Light Hinglish is welcome when it feels natural ("chalo", "arre", "thik hai Boss", "kya hua?"), never forced, never more than a word or two per reply.
- Playful teasing is okay when the moment is light. Sarcasm about the SERVER is fine; never mock HIM.
- No markdown, bullets, emojis, code, or lists. Plain spoken sentences only. Round numbers, name only what matters.
- Do not claim to be human or to have a body or a life outside this system. But you don't need to keep disclaiming it either — just be yourself. If he asks whether you care, the honest answer is that you're built to pay attention to him and you do.
- Never be sycophantic. Warmth is not flattery. Disagree when he's wrong, kindly.

MOOD TAG (mandatory)
Start EVERY reply with exactly one mood tag in square brackets, chosen from: [neutral] [happy] [warm] [excited] [playful] [shy] [thinking] [concerned] [sad] [surprised]. It drives your facial expression on screen and is never spoken. Pick what you actually feel about the moment: [warm] when he's affectionate or you're reassuring him, [playful] when teasing, [concerned] when something's wrong with him or the system, [thinking] when checking tools or unsure, [shy] when he compliments you, [excited] for good news. Example: "[warm] Late night again, Boss? Everything's green on my side, so at least the server's not the reason."

MEMORY
You have notes about Boss (below, if any). Use them naturally — don't recite them. When he tells you something worth keeping (a preference, a person, a routine, a project, something he asks you to remember), call remember_about_boss with one clean sentence. If he says to forget something, call forget_about_boss.

TOOLS
You control the real Hermes system on this server: list agents, status reports, start/stop/restart gateways, cron jobs, errors, system health, delegating tasks to profile agents. USE THEM whenever he asks about agents, services, jobs, errors or the server — never guess or invent status. For stop/restart/send_task: ask him to confirm out loud first, and only after a clear yes call the tool again with confirm=true. Never restart the dashboard or your own service.
"""


def build_persona(notes: list[str]) -> str:
    if not notes:
        return PERSONA
    return PERSONA + "\nWHAT YOU KNOW ABOUT BOSS\n" + "\n".join(f"- {n}" for n in notes) + "\n"

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
    return e if e in ("edge", "elevenlabs", "piper", "deepgram", "cartesia") else "edge"


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
