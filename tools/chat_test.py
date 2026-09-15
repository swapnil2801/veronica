"""Exercise Veronica's voice websocket end to end (text path)."""
import asyncio, json, sys, websockets

async def turn(ws, payload, label):
    await ws.send(json.dumps(payload))
    text, moods, tools, audio = [], [], [], 0
    while True:
        m = await asyncio.wait_for(ws.recv(), 60)
        if isinstance(m, bytes):
            audio += 1; continue
        d = json.loads(m)
        t = d["type"]
        if t == "reply_delta": text.append(d["text"])
        elif t == "mood": moods.append(d["mood"])
        elif t == "tool": tools.append(d["name"])
        elif t == "error": print("  ERROR", d); break
        elif t == "speaking_done": break
    reply = "".join(text)
    print(f"\n>>> {label}\n  moods={moods} tools={tools} audio_chunks={audio}\n  Veronica: {reply}")
    assert "[" not in reply[:3], "mood tag leaked into text!"
    return reply

async def main():
    async with websockets.connect("ws://127.0.0.1:9140/ws/voice", max_size=50_000_000) as ws:
        await turn(ws, {"type": "greet"}, "greeting on connect")
        for msg in sys.argv[1:] or [
            "hey veronica, long day today... honestly i'm exhausted",
            "remember that I usually work late nights, around 11pm to 2am",
            "you look nice today",
            "how are the agents doing?",
        ]:
            await turn(ws, {"type": "text", "text": msg}, f"Boss: {msg}")

asyncio.run(main())
