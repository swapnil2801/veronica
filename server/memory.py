"""Veronica's long-term memory: conversation continuity + notes about Boss.

Everything lives in server/memory.json (git-ignored). Small on purpose:
this is the "she remembers" layer, not a database.
"""
import json
import logging
import time
from collections import deque
from pathlib import Path

from . import config

log = logging.getLogger("veronica.memory")

_FILE = config.BASE_DIR / "server" / "memory.json"
MAX_NOTES = 40
MAX_TURNS = config.LLM_MAX_TURNS * 2

_state = {"history": [], "notes": [], "last_seen": 0.0, "sessions": 0}


def _load():
    global _state
    try:
        d = json.loads(_FILE.read_text())
        _state.update({k: d.get(k, v) for k, v in _state.items()})
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        log.warning("memory unreadable, starting fresh: %s", e)


def _save():
    try:
        _FILE.write_text(json.dumps(_state, ensure_ascii=False, indent=1))
    except Exception as e:  # noqa: BLE001
        log.warning("memory save failed: %s", e)


_load()

# ---- conversation history (shared by every connection) ----
history: deque = deque(_state["history"], maxlen=MAX_TURNS)


def record(user_text: str, reply: str):
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    _state["history"] = list(history)
    _state["last_seen"] = time.time()
    _save()


# ---- notes about Boss ----
def notes() -> list[str]:
    return list(_state["notes"])


def remember(note: str) -> dict:
    note = " ".join((note or "").split())[:200]
    if not note:
        return {"error": "empty note"}
    low = note.lower()
    if any(low == n.lower() for n in _state["notes"]):
        return {"ok": True, "note": note, "already_known": True}
    _state["notes"].append(note)
    if len(_state["notes"]) > MAX_NOTES:
        _state["notes"] = _state["notes"][-MAX_NOTES:]
    _save()
    log.info("remembered: %s", note)
    return {"ok": True, "note": note, "total": len(_state["notes"])}


def forget(fragment: str) -> dict:
    frag = (fragment or "").lower().strip()
    before = len(_state["notes"])
    _state["notes"] = [n for n in _state["notes"] if frag not in n.lower()] if frag else _state["notes"]
    _save()
    return {"ok": True, "removed": before - len(_state["notes"])}


# ---- session context for greetings ----
def session_context() -> dict:
    now = time.time()
    gap = now - _state["last_seen"] if _state["last_seen"] else None
    _state["sessions"] += 1
    _save()
    return {"seconds_since_last": gap, "sessions": _state["sessions"], "notes": len(_state["notes"])}


def describe_gap(seconds) -> str:
    if seconds is None:
        return "this is your very first conversation together"
    if seconds < 90:
        return "you were talking less than two minutes ago"
    if seconds < 3600:
        return f"you last talked about {int(seconds // 60)} minutes ago"
    if seconds < 86400:
        return f"you last talked about {seconds / 3600:.0f} hours ago"
    return f"you last talked about {seconds / 86400:.0f} days ago"


TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "remember_about_boss",
        "description": "Save one short durable fact about Boss for future conversations: preferences, people, routines, ongoing projects, how he likes things, things he told you to remember. Do NOT save temporary status or things you can look up with tools.",
        "parameters": {"type": "object", "properties": {"note": {"type": "string", "description": "One plain sentence, e.g. 'Boss prefers voice replies under 2 sentences late at night.'"}}, "required": ["note"]}}},
    {"type": "function", "function": {
        "name": "forget_about_boss",
        "description": "Remove saved notes about Boss that contain the given text. Use when Boss asks you to forget something or a fact is outdated.",
        "parameters": {"type": "object", "properties": {"fragment": {"type": "string"}}, "required": ["fragment"]}}},
]

TOOLS = {"remember_about_boss": lambda note="": remember(note),
         "forget_about_boss": lambda fragment="": forget(fragment)}
