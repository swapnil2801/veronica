"""Veronica's brain: streaming chat + Hermes tool calling via OmniRoute."""
import asyncio
import json
import logging
from collections import deque
from typing import AsyncIterator

from openai import AsyncOpenAI

from . import bridge, config

log = logging.getLogger("veronica.brain")

MAX_TOOL_ROUNDS = 5


class Brain:
    def __init__(self):
        self.history: deque = deque(maxlen=config.LLM_MAX_TURNS * 2)
        self._client_key = None
        self.client = None

    def _get_client(self) -> AsyncOpenAI:
        llm = config.get_llm()
        key = (llm["base_url"], llm["api_key"])
        if self.client is None or key != self._client_key:
            self.client = AsyncOpenAI(base_url=llm["base_url"], api_key=llm["api_key"], timeout=90)
            self._client_key = key
        return self.client

    async def stream_reply(self, user_text: str, on_tool=None) -> AsyncIterator[str]:
        """Run the request through the real default Hermes agent.

        Veronica remains the voice/UI surface, while Hermes owns model routing,
        tools, skills, memory, approvals, and terminal/file/browser access.
        """
        if on_tool:
            await on_tool("default_hermes_agent", {"profile": "default"})
        result = await asyncio.to_thread(bridge.ask_default_agent, user_text)
        if result.get("ok"):
            reply = result.get("result", "").strip()
        else:
            reply = f"The default Hermes agent could not complete that request: {result.get('error', 'unknown error')}"
        if not reply:
            reply = "The default Hermes agent completed the request without a spoken response."
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        log.info("default-agent reply: %r", reply[:200])
        yield reply

    async def _legacy_stream_reply(self, user_text: str, on_tool=None) -> AsyncIterator[str]:
        """Legacy direct OpenAI-compatible path retained for rollback/debugging."""
        client = self._get_client()
        messages = [{"role": "system", "content": config.PERSONA}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_text})
        full = []

        for _round in range(MAX_TOOL_ROUNDS):
            stream = await client.chat.completions.create(
                model=config.get_model(),
                messages=messages,
                tools=bridge.TOOL_SPECS,
                stream=True,
                temperature=0.7,
                max_tokens=500,
            )
            tool_calls: dict[int, dict] = {}
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full.append(delta.content)
                    yield delta.content
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
            for i, s in sorted(tool_calls.items()):
                try:
                    args = json.loads(s["args"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                if on_tool:
                    await on_tool(s["name"], args)
                result = await bridge.call_tool(s["name"], args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": s["id"] or f"call_{i}",
                    "content": json.dumps(result, default=str)[:6000],
                })

        reply = "".join(full).strip()
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply or "(action performed)"})
        log.info("reply: %r", reply[:200])
