"""Veronica's brain: streaming chat + Hermes tool calling via OmniRoute."""
import asyncio
import json
import logging
import re
from typing import AsyncIterator

from openai import AsyncOpenAI

from . import bridge, config, memory

log = logging.getLogger("veronica.brain")

MAX_TOOL_ROUNDS = 5
_MOOD_RE = re.compile(r"^\s*\[(\w+)\]\s*")
_TOOLS = {**bridge.TOOLS, **memory.TOOLS}
_TOOL_SPECS = bridge.TOOL_SPECS + memory.TOOL_SPECS


class MoodFilter:
    """Peels the leading [mood] tag off a token stream without blocking it.

    Buffers only until the tag is resolved (a few tokens), then passes
    everything through untouched.
    """

    def __init__(self):
        self.mood = None
        self._buf = ""
        self._done = False

    def feed(self, delta: str) -> str:
        if self._done:
            return delta
        self._buf += delta
        m = _MOOD_RE.match(self._buf)
        if m:
            self.mood = m.group(1).lower() if m.group(1).lower() in config.MOODS else "neutral"
            self._done = True
            return self._buf[m.end():]
        # no tag possible any more (didn't start with '[' or tag too long)
        if not self._buf.lstrip().startswith("[") or len(self._buf) > 24:
            self._done = True
            self.mood = "neutral"
            return self._buf
        return ""  # still deciding

    def flush(self) -> str:
        if self._done:
            return ""
        self._done = True
        self.mood = self.mood or "neutral"
        return self._buf


class Brain:
    def __init__(self):
        self.history = memory.history  # shared, persisted across sessions
        self._client_key = None
        self.client = None

    def _get_client(self) -> AsyncOpenAI:
        llm = config.get_llm()
        key = (llm["base_url"], llm["api_key"])
        if self.client is None or key != self._client_key:
            self.client = AsyncOpenAI(base_url=llm["base_url"], api_key=llm["api_key"], timeout=90)
            self._client_key = key
        return self.client

    async def stream_reply(self, user_text: str, on_tool=None, on_mood=None) -> AsyncIterator[str]:
        """Stream normal Veronica conversations through the direct LLM path.

        Yields spoken text only; the leading [mood] tag is intercepted and
        reported through on_mood.
        """
        async for delta in self._direct_stream_reply(user_text, on_tool=on_tool, on_mood=on_mood):
            yield delta

    async def stream_greeting(self, on_mood=None) -> AsyncIterator[str]:
        """Say hello when Boss opens the app. Uses memory for continuity."""
        ctx = memory.session_context()
        prompt = (
            f"[system event] Boss just opened the app. Context: {memory.describe_gap(ctx['seconds_since_last'])}. "
            "Greet him in ONE short natural sentence (two at most) as yourself, like someone who's glad he's back. "
            "Reference something real from your notes or the last conversation if there is one; otherwise just be warm. "
            "Do not call any tools. Do not ask more than one question."
        )
        async for delta in self._direct_stream_reply(prompt, on_mood=on_mood, record_user=False, tools=False):
            yield delta

    async def stream_full_agent(self, user_text: str) -> AsyncIterator[str]:
        """Run an explicitly requested task through the full Hermes CLI agent."""
        result = await asyncio.to_thread(bridge.ask_default_agent, user_text)
        if result.get("ok"):
            reply = result.get("result", "").strip()
        else:
            reply = f"The full Hermes agent could not complete that request: {result.get('error', 'unknown error')}"
        if not reply:
            reply = "The full Hermes agent completed the request without a spoken response."
        memory.record(user_text, reply)
        log.info("full-agent reply: %r", reply[:200])
        yield reply

    async def _direct_stream_reply(self, user_text: str, on_tool=None, on_mood=None,
                                   record_user: bool = True, tools: bool = True) -> AsyncIterator[str]:
        """Direct OpenAI-compatible streaming path with safe bridge tools."""
        client = self._get_client()
        messages = [{"role": "system", "content": config.build_persona(memory.notes())}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_text})
        full = []
        mood = MoodFilter()

        for _round in range(MAX_TOOL_ROUNDS):
            kwargs = dict(model=config.get_model(), messages=messages, stream=True, temperature=0.8, max_tokens=500)
            if tools:
                kwargs["tools"] = _TOOL_SPECS
            stream = await client.chat.completions.create(**kwargs)
            tool_calls: dict[int, dict] = {}
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    out = mood.feed(delta.content)
                    if mood.mood and on_mood and not getattr(mood, "_sent", False):
                        mood._sent = True
                        await on_mood(mood.mood)
                    if out:
                        full.append(out)
                        yield out
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        slot = tool_calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function and tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            slot["args"] += tc.function.arguments

            if not tool_calls:
                break  # final answer done

            # execute tools, append results, loop for another round
            assistant_msg = {
                "role": "assistant",
                "content": "".join(full) or None,
                "tool_calls": [
                    {"id": s["id"] or f"call_{i}", "type": "function",
                     "function": {"name": s["name"], "arguments": s["args"] or "{}"}}
                    for i, s in sorted(tool_calls.items())
                ],
            }
            messages.append(assistant_msg)
            if on_mood and not getattr(mood, "_sent", False):
                mood._sent = True
                await on_mood("thinking")
            for i, s in sorted(tool_calls.items()):
                try:
                    args = json.loads(s["args"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                if on_tool:
                    await on_tool(s["name"], args)
                result = await self._call_tool(s["name"], args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": s["id"] or f"call_{i}",
                    "content": json.dumps(result, default=str)[:6000],
                })
            # the next round starts a fresh sentence; allow a new mood tag
            mood = MoodFilter()

        tail = mood.flush()
        if tail:
            full.append(tail)
            yield tail
        if on_mood and not getattr(mood, "_sent", False) and mood.mood:
            await on_mood(mood.mood)

        reply = "".join(full).strip()
        if record_user:
            memory.record(user_text, reply or "(action performed)")
        else:
            self.history.append({"role": "assistant", "content": reply})
        log.info("reply: %r", reply[:200])

    @staticmethod
    async def _call_tool(name: str, args: dict) -> dict:
        fn = _TOOLS.get(name)
        if fn is None:
            return {"error": f"unknown tool {name}"}
        if name in memory.TOOLS:
            try:
                return fn(**args)
            except Exception as e:  # noqa: BLE001
                return {"error": str(e)}
        return await bridge.call_tool(name, args)
