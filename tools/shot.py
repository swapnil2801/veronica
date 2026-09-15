#!/usr/bin/env python
"""Screenshot + layout audit of Veronica via CDP (headless_shell on :9222).

usage: shot.py <width> <height> <out.png> [--fs] [--tab activity|settings] [--fill]
"""
import asyncio, base64, json, sys, urllib.request

import websockets

W, H, OUT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
FS = "--fs" in sys.argv
FILL = "--fill" in sys.argv
TAB = sys.argv[sys.argv.index("--tab") + 1] if "--tab" in sys.argv else None
URL = "http://127.0.0.1:9140/"

AUDIT = r"""
(() => {
  const out = [];
  const vis = e => { const cs = getComputedStyle(e); return cs.display !== 'none' && cs.visibility !== 'hidden' && e.getBoundingClientRect().width > 0; };
  // 1. children overflowing an overflow:hidden/clip ancestor's box
  document.querySelectorAll('.vcol *, .chat-panel *, .ops *').forEach(e => {
    if (!vis(e) || ['CANVAS','OPTION','I','B'].includes(e.tagName)) return;
    if (e.closest('#transcript, .opsbody, #feedlist') && !e.matches('#transcript, .opsbody')) return; // scroll content by design
    const r = e.getBoundingClientRect(), p = e.parentElement.getBoundingClientRect();
    const over = Math.max(r.right - p.right, r.bottom - p.bottom, p.left - r.left);
    if (over > 2) out.push(`OVERFLOW ${e.tagName}.${e.className}#${e.id} by ${Math.round(over)}px`);
    if (r.right > innerWidth + 1) out.push(`OFFSCREEN ${e.tagName}.${e.className}#${e.id} right=${Math.round(r.right)}`);
  });
  // 2. overlapping siblings among positioned stage widgets + header items
  const sets = [['#stage > *'], ['.opshead > *'], ['.vhead > *'], ['.chat-head > *'], ['.vcontrols > *']];
  for (const [sel] of sets) {
    const els = [...document.querySelectorAll(sel)].filter(e => vis(e) && !['CANVAS'].includes(e.tagName) && !e.matches('#rings,.scan,.hud'));
    for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
      const a = els[i].getBoundingClientRect(), b = els[j].getBoundingClientRect();
      const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left), oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ox > 3 && oy > 3) out.push(`OVERLAP ${els[i].id||els[i].className} x ${els[j].id||els[j].className} (${Math.round(ox)}x${Math.round(oy)})`);
    }
  }
  // 3. text truncated by ellipsis / clipped
  document.querySelectorAll('button, .tab, .aname, .chat-title, .ops-title, h1, #clock, .metric .sub').forEach(e => {
    if (vis(e) && e.scrollWidth > e.clientWidth + 1) out.push(`CLIPPED-TEXT ${e.tagName}.${e.className}#${e.id} "${e.textContent.trim().slice(0,30)}" ${e.scrollWidth}>${e.clientWidth}`);
  });
  // 4. scroll containers
  document.querySelectorAll('*').forEach(e => { if (e.scrollHeight > e.clientHeight + 2 && /auto|scroll/.test(getComputedStyle(e).overflowY)) out.push(`SCROLLS ${e.tagName}.${e.className}#${e.id} ${e.clientHeight}/${e.scrollHeight}`); });
  if (document.documentElement.scrollWidth > innerWidth) out.push(`PAGE-HSCROLL ${document.documentElement.scrollWidth}>${innerWidth}`);
  return out.join('\n') || 'clean';
})()
"""

FILL_JS = r"""
(() => {
  const tx = document.getElementById('transcript');
  const add = (who, t, cls) => { const d = document.createElement('div'); d.className = 'line ' + cls; d.innerHTML = `<span class="who">${who}</span><span class="txt"></span>`; d.querySelector('.txt').textContent = t; tx.appendChild(d); };
  for (let i = 0; i < 12; i++) { add('You', 'Boss message number ' + i + ' asking about the pipeline and the very long status of the instagram reel scheduler this week', 'user'); add('Veronica', 'Sure Boss — here is a fairly long reply that wraps over several lines so we can check bubble widths, scrollbars and spacing inside the chat panel. Everything looks good on my side.', 'veronica'); add('action', '⚙ list agents', 'tool'); }
  const f = document.getElementById('feedlist'); for (let i = 0; i < 40; i++) { const d = document.createElement('div'); d.textContent = `2026-09-15 22:0${i%10} INFO veronica.bridge tool_call=list_agents duration=${i*13}ms status=ok long_line_${'x'.repeat(60)}`; f.appendChild(d); }
  tx.scrollTop = tx.scrollHeight;
})()
"""

async def main():
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
    page = next((t for t in tabs if t["type"] == "page"), None)
    if not page:
        page = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/new?about:blank", data=b""))
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
        mid = 0
        async def call(method, **params):
            nonlocal mid; mid += 1
            await ws.send(json.dumps({"id": mid, "method": method, "params": params}))
            while True:
                m = json.loads(await ws.recv())
                if m.get("id") == mid:
                    return m.get("result", m)
        async def ev(expr):
            r = await call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
            return r.get("result", {}).get("value")
        await call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        await call("Page.enable")
        await call("Network.enable")
        await call("Network.setCacheDisabled", cacheDisabled=True)
        await call("Page.navigate", url=URL + "?t=" + str(int(asyncio.get_event_loop().time()*1000)))
        await asyncio.sleep(4.5)
        if FS:
            await ev("document.body.classList.add('fs'); document.getElementById('fsbtn').textContent='✕'; 1")
            await asyncio.sleep(0.3); await ev("window.dispatchEvent(new Event('resize')); 1"); await asyncio.sleep(0.8)
        if TAB:
            await ev(f"document.querySelector('.tab[data-pane={TAB}]').click(); 1"); await asyncio.sleep(0.4)
        if FILL:
            await ev(FILL_JS); await asyncio.sleep(0.3)
        vp = await ev("innerWidth + 'x' + innerHeight")
        print(f"viewport {vp}  fs={FS} tab={TAB}")
        print(await ev(AUDIT))
        shot = await call("Page.captureScreenshot", format="png")
        open(OUT, "wb").write(base64.b64decode(shot["data"]))
        print("saved", OUT)

asyncio.run(main())
