/* Veronica dashboard: Live2D avatar + voice loop + reactive visuals + panels. */
const SR = 16000;
let ws, audioCtx, micStream, workNode, capturing = false, handsFree = false;
let playQueue = [], playing = false, pendingText = null;
let model = null, pixiApp = null;
let micLevel = 0;
let mouthVal = 0, mouthTarget = 0;

// VAD (hands-free)
let vadSpeaking = false, vadSilenceMs = 0, vadLastTick = 0, vadSpeechMs = 0;
const VAD_THRESH = 0.012, VAD_SILENCE_END = 900, VAD_MIN_SPEECH = 300;

const $ = id => document.getElementById(id);
const tx = $('transcript');

/* smart auto-scroll: follow only when user is near the bottom */
function nearBottom() { return tx.scrollHeight - tx.scrollTop - tx.clientHeight < 60; }
function autoScroll(force) {
  if (force || nearBottom()) { tx.scrollTop = tx.scrollHeight; $('jump').classList.remove('show'); }
  else $('jump').classList.add('show');
}
tx && tx.addEventListener && tx.addEventListener('scroll', () => { if (nearBottom()) $('jump').classList.remove('show'); });
document.addEventListener('DOMContentLoaded', () => {
  $('jump').addEventListener('click', () => autoScroll(true));
});

function setState(s) {
  document.body.dataset.vstate = s;
  $('vstate').textContent = s;
}
function addLine(who, text, cls) {
  const follow = nearBottom();
  const d = document.createElement('div');
  d.className = 'line ' + (cls || (who === 'You' ? 'user' : 'veronica'));
  d.innerHTML = `<span class="who">${who}</span><span class="txt"></span>`;
  d.querySelector('.txt').textContent = text;
  tx.appendChild(d); autoScroll(follow);
  return d.querySelector('.txt');
}

/* ---------------- clock ---------------- */
setInterval(() => {
  $('clock').textContent = new Date().toLocaleString('en-IN', { hour12:false,
    weekday:'short', day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit', second:'2-digit' });
}, 1000);

/* ---------------- Live2D ---------------- */
function fitModel() {
  if (!model || !pixiApp) return;
  const stage = $('stage');
  const w = stage.clientWidth, h = stage.clientHeight;
  pixiApp.renderer.resize(w, h);
  const mw = model.internalModel.width, mh = model.internalModel.height;
  if (document.body.classList.contains('fs')) {
    // fullscreen: cinematic portrait — zoom to head + upper body
    const scale = (h / mh) * 2.35;
    model.scale.set(scale);
    model.anchor.set(0.5, 0);
    model.position.set(w / 2, -h * 0.12); // slight lift so face sits in upper third
  } else {
    // sidebar: contain, full body visible
    const scale = Math.min(w / mw, h / mh) * 0.95;
    model.scale.set(scale);
    model.anchor.set(0.5, 0);
    model.position.set(w / 2, h * 0.02);
  }
}
async function initLive2D() {
  const canvas = $('live2d'), stage = $('stage');
  pixiApp = new PIXI.Application({ view: canvas, backgroundAlpha: 0,
    width: stage.clientWidth, height: stage.clientHeight, autoDensity: true,
    resolution: Math.min(window.devicePixelRatio || 1, 1.5), antialias: true });
  pixiApp.ticker.maxFPS = 30; // halve GPU/CPU load
  try {
    model = await PIXI.live2d.Live2DModel.from('models/haru/haru_greeter_t03.model3.json');
    pixiApp.stage.addChild(model);
    fitModel();
    window.addEventListener('resize', fitModel);
    model.on('hit', () => { try { model.motion('Tap'); } catch(e){} });

    // frame-locked lip-sync: re-apply mouth AFTER motion update so idle
    // animations can never overwrite it mid-speech
    const mm = model.internalModel.motionManager;
    const origUpdate = mm.update.bind(mm);
    mm.update = (...a) => {
      const r = origUpdate(...a);
      // smooth attack/decay toward target
      mouthVal += (mouthTarget - mouthVal) * 0.5;
      if (playing) {
        try { model.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', mouthVal); } catch (e) {}
      }
      return r;
    };
  } catch (e) {
    console.error('live2d failed', e);
    stage.insertAdjacentHTML('beforeend', '<div style="position:absolute;top:40%;width:100%;text-align:center;color:#666;z-index:2">avatar failed to load — voice still works</div>');
  }
}

/* mouth target from analyser (time domain RMS — tracks speech energy better) */
let analyser = null, tdData = null;
setInterval(() => {
  if (!playing || !analyser) { mouthTarget = 0; return; }
  analyser.getByteTimeDomainData(tdData);
  let sum = 0;
  for (let i = 0; i < tdData.length; i++) { const v = (tdData[i] - 128) / 128; sum += v * v; }
  const rms = Math.sqrt(sum / tdData.length);
  mouthTarget = Math.min(1, Math.pow(rms * 6.5, 1.15));
}, 33);

/* ---------------- waveform canvas (30fps) ---------------- */
const waveC = $('wave');
const wctx = waveC.getContext('2d');
const freqData = new Uint8Array(128);
let lastWave = 0;
function drawWave(ts) {
  requestAnimationFrame(drawWave);
  if (ts - lastWave < 33) return;
  lastWave = ts;
  const st = document.body.dataset.vstate;
  const w = waveC.clientWidth, h = waveC.clientHeight;
  if (w === 0) return;
  if (waveC.width !== w) { waveC.width = w; waveC.height = h; }
  wctx.clearRect(0, 0, waveC.width, waveC.height);
  if (st !== 'speaking' && st !== 'listening') return;

  const N = 40, cx = waveC.width / 2, mid = waveC.height / 2;
  const bw = Math.min(6, waveC.width / (N * 2.1));
  if (st === 'speaking' && analyser) analyser.getByteFrequencyData(freqData);
  for (let i = 0; i < N; i++) {
    let amp;
    if (st === 'speaking' && analyser) amp = freqData[Math.floor(i / N * 60) + 2] / 255;
    else amp = Math.min(1, micLevel * 14) * (0.35 + 0.65 * Math.abs(Math.sin(Date.now() / 130 + i * 0.9)));
    const bh = Math.max(2, amp * mid * 1.7);
    wctx.fillStyle = `rgba(255,255,255,${0.25 + amp * 0.6})`;
    wctx.fillRect(cx + (i - N / 2) * bw * 2.1, mid - bh / 2, bw, bh);
  }
}
requestAnimationFrame(drawWave);

/* ---------------- fullscreen mode ---------------- */
$('fsbtn').addEventListener('click', () => {
  document.body.classList.toggle('fs');
  $('fsbtn').textContent = document.body.classList.contains('fs') ? '✕' : '⛶';
  if (document.body.classList.contains('fs') && document.documentElement.requestFullscreen && !document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else if (!document.body.classList.contains('fs') && document.fullscreenElement) {
    document.exitFullscreen().catch(() => {});
  }
  setTimeout(fitModel, 150);
});
document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement && document.body.classList.contains('fs')) {
    document.body.classList.remove('fs'); $('fsbtn').textContent = '⛶'; setTimeout(fitModel, 150);
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && document.body.classList.contains('fs')) {
    document.body.classList.remove('fs'); $('fsbtn').textContent = '⛶'; setTimeout(fitModel, 150);
  }
});

/* ---------------- Voice WS ----------------
   Caption sync: reply text is NOT streamed into the transcript.
   Each sentence appears exactly when its audio starts playing. */
let replySpan = null;
function connectVoice() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/voice`);
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => { $('connTxt').textContent = 'online'; $('connState').classList.add('on'); };
  ws.onclose = () => { $('connTxt').textContent = 'reconnecting'; $('connState').classList.remove('on'); setTimeout(connectVoice, 2000); };
  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      if (pendingText !== null) { playQueue.push({ buf: ev.data, text: pendingText }); pendingText = null; pump(); }
      return;
    }
    const m = JSON.parse(ev.data);
    if (m.type === 'transcript') {
      if (m.text) { addLine('You', m.text); setState('thinking'); replySpan = null; }
      else setState(handsFree ? 'listening' : 'idle');
    } else if (m.type === 'tool') {
      addLine('action', `⚙ ${m.name.replaceAll('_',' ')}`, 'tool');
    } else if (m.type === 'audio_sentence') {
      pendingText = m.text || '';
    } else if (m.type === 'caption') {
      showCaption(m.text); // TTS failed for this sentence: text-only
    } else if (m.type === 'error') {
      addLine('system', m.message, 'tool'); setState('idle');
    }
  };
}
function showCaption(text) {
  const follow = nearBottom();
  if (!replySpan) replySpan = addLine('Veronica', '');
  replySpan.textContent += (replySpan.textContent ? ' ' : '') + text;
  autoScroll(follow);
}

async function pump() {
  if (playing || playQueue.length === 0) return;
  playing = true; setState('speaking');
  while (playQueue.length) {
    const item = playQueue.shift();
    try {
      ensureCtx();
      const decoded = await audioCtx.decodeAudioData(item.buf.slice(0));
      showCaption(item.text); // caption appears in sync with its audio
      await new Promise(res => {
        const src = audioCtx.createBufferSource();
        src.buffer = decoded;
        src.connect(analyser); analyser.connect(audioCtx.destination);
        src.onended = res; src.start();
      });
    } catch (e) { console.warn('decode failed', e); showCaption(item.text); }
  }
  playing = false; mouthTarget = 0;
  setState(capturing || handsFree ? 'listening' : 'idle');
}

function ensureCtx() {
  if (!audioCtx) audioCtx = new AudioContext();
  if (!analyser) {
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    tdData = new Uint8Array(analyser.fftSize);
  }
}

/* ---------------- Mic ---------------- */
async function startMic() {
  if (micStream) return;
  micStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount:1, echoCancellation:true, noiseSuppression:true } });
  ensureCtx();
  const srcNode = audioCtx.createMediaStreamSource(micStream);
  await audioCtx.audioWorklet.addModule('capture-worklet.js');
  workNode = new AudioWorkletNode(audioCtx, 'capture', { processorOptions: { targetRate: SR, sourceRate: audioCtx.sampleRate } });
  workNode.port.onmessage = (e) => onPcm(e.data);
  srcNode.connect(workNode);
}
function onPcm(f32) {
  let sum = 0; for (let i = 0; i < f32.length; i++) sum += f32[i] * f32[i];
  micLevel = Math.sqrt(sum / f32.length);
  const now = performance.now();
  if (handsFree && !playing) {
    const rms = micLevel;
    const dt = vadLastTick ? now - vadLastTick : 0; vadLastTick = now;
    if (rms > VAD_THRESH) {
      if (!vadSpeaking) { vadSpeaking = true; vadSpeechMs = 0; setState('listening'); }
      vadSilenceMs = 0; vadSpeechMs += dt;
    } else if (vadSpeaking) {
      vadSilenceMs += dt;
      if (vadSilenceMs > VAD_SILENCE_END) {
        vadSpeaking = false;
        if (vadSpeechMs > VAD_MIN_SPEECH) endUtterance(); else setState('listening');
      }
    }
    if (vadSpeaking || vadSilenceMs < VAD_SILENCE_END) sendPcm(f32);
  } else if (capturing) sendPcm(f32);
}
const sendPcm = f32 => { if (ws && ws.readyState === 1) ws.send(f32.buffer); };
const endUtterance = () => { if (ws && ws.readyState === 1) { ws.send(JSON.stringify({type:'end_utterance'})); setState('thinking'); } };

const ptt = $('ptt');
async function pttDown(e) { e.preventDefault(); await startMic(); if (audioCtx.state==='suspended') await audioCtx.resume(); capturing = true; ptt.classList.add('active'); setState('listening'); }
function pttUp(e) { e.preventDefault(); if (!capturing) return; capturing = false; ptt.classList.remove('active'); endUtterance(); }
ptt.addEventListener('mousedown', pttDown); ptt.addEventListener('mouseup', pttUp); ptt.addEventListener('mouseleave', pttUp);
ptt.addEventListener('touchstart', pttDown); ptt.addEventListener('touchend', pttUp);

$('handsfree').addEventListener('click', async () => {
  handsFree = !handsFree;
  $('handsfree').classList.toggle('active', handsFree);
  if (handsFree) { await startMic(); if (audioCtx.state==='suspended') await audioCtx.resume(); setState('listening'); }
  else setState('idle');
});

const tin = $('textin');
function sendText() {
  const t = tin.value.trim(); if (!t || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({type:'text', text:t})); tin.value = ''; setState('thinking');
}
$('send').addEventListener('click', sendText);
tin.addEventListener('keydown', e => { if (e.key === 'Enter') sendText(); });

/* ---------------- Dashboard data ---------------- */
function connectEvents() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const es = new WebSocket(`${proto}://${location.host}/ws/events`);
  es.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === 'tick') { renderHealth(m.system); if (m.agents) renderAgents(m.agents); }
    if (m.type === 'log') addFeed(m.line);
  };
  es.onclose = () => setTimeout(connectEvents, 3000);
}
function renderHealth(s) {
  $('hcpu').textContent = s.cpu_pct.toFixed(0) + '%'; $('bcpu').style.width = s.cpu_pct + '%';
  $('hload').textContent = 'load ' + s.load_avg.join(' · ');
  $('hram').textContent = s.ram.pct.toFixed(0) + '%'; $('bram').style.width = s.ram.pct + '%';
  $('hramsub').textContent = s.ram.used_gb + ' / ' + s.ram.total_gb + ' GB';
  $('hdisk').textContent = s.disk.pct.toFixed(0) + '%'; $('bdisk').style.width = s.disk.pct + '%';
  $('hdisksub').textContent = s.disk.used_gb + ' / ' + s.disk.total_gb + ' GB';
  $('hup').textContent = (s.uptime_hours / 24).toFixed(1) + 'd';
}
function renderAgents(list) {
  const el = $('agents'); el.innerHTML = '';
  const cnt = $('agentcnt');
  if (cnt) cnt.textContent = list.filter(a => a.status === 'active').length + '/' + list.length;
  for (const a of list) {
    const name = a.unit.replace('hermes-','').replace('.service','');
    const ctl = name.startsWith('gateway');
    const on = a.status === 'active';
    el.insertAdjacentHTML('beforeend', `
      <div class="arow ${on ? 'on' : ''}">
        <span class="sdot"></span>
        <span class="aname">${name}</span>
        <span class="astat">${a.status}</span>
        <span class="ameta">${a.mem_mb ? a.mem_mb + ' MB' : ''}${a.since ? ' · ' + a.since.replace(/^\w+ /,'').slice(0,17) : ''}</span>
        <span class="abtns">${ctl ? `
          <button onclick="ctlAgent('${name}','restart')">Restart</button>
          <button onclick="ctlAgent('${name}','${on ? 'stop' : 'start'}')">${on ? 'Stop' : 'Start'}</button>` : '<span class="prot">protected</span>'}
        </span>
      </div>`);
  }
}

/* tabs */
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('sel'));
  document.querySelectorAll('.pane').forEach(x => x.classList.remove('sel'));
  t.classList.add('sel');
  document.getElementById('pane-' + t.dataset.pane).classList.add('sel');
}));
async function ctlAgent(name, action) {
  if ((action === 'stop' || action === 'restart') && !confirm(`${action} ${name}?`)) return;
  addFeed(`[ui] ${action} ${name}…`, true);
  const r = await fetch(`/api/agents/${name}/${action}`, { method: 'POST' });
  const j = await r.json();
  addFeed(`[ui] ${name} → ${j.status_now || JSON.stringify(j)}`, true);
}
window.ctlAgent = ctlAgent;

async function loadCron() {
  const r = await fetch('/api/cron'); const j = await r.json();
  const el = $('cron'); el.innerHTML = '';
  const cnt = $('croncnt');
  if (cnt) cnt.textContent = j.jobs.length;
  for (const c of j.jobs) {
    const sched = (c.schedule && (c.schedule.display || c.schedule.expr)) || c.schedule || '';
    el.insertAdjacentHTML('beforeend',
      `<div class="cj"><span class="cp">${c.profile}</span><span>${c.name || c.id || ''}</span><span class="cs">${sched}${c.last_error ? ' ⚠' : ''}</span></div>`);
  }
}
const feed = $('feedlist');
function addFeed(line, ui) {
  const d = document.createElement('div');
  if (ui) d.className = 'ui';
  else if (/error|fail|warn/i.test(line)) d.className = 'err';
  d.textContent = line;
  feed.appendChild(d);
  while (feed.children.length > 300) feed.removeChild(feed.firstChild);
  feed.scrollTop = feed.scrollHeight;
}

/* ---------------- settings: provider + model + voice ---------------- */
let curSettings = null;
function renderProviders() {
  const g = $('provGrid'); g.innerHTML = '';
  for (const p of curSettings.providers) {
    const d = document.createElement('div');
    d.className = 'prov' + (p.id === curSettings.provider ? ' sel' : '') + (p.has_key ? '' : ' nokey');
    d.innerHTML = `<div class="pname">${p.label}</div><div class="pmeta">${p.has_key ? p.id : 'no API key found'}</div>`;
    if (p.has_key) d.addEventListener('click', async () => {
      if (p.id === curSettings.provider) return;
      $('setStatus').textContent = 'switching provider…';
      await saveSettings({ provider: p.id });
      await loadSettings();
    });
    g.appendChild(d);
  }
}
async function loadModels() {
  const sm = $('selModel');
  sm.innerHTML = '<option>loading…</option>';
  const m = await fetch('/api/models').then(r => r.json()).catch(() => ({ models: [] }));
  sm.innerHTML = '';
  const models = m.models || [];
  if (!models.includes(curSettings.model)) models.unshift(curSettings.model);
  for (const id of models) {
    const o = document.createElement('option');
    o.value = id; o.textContent = id;
    if (id === curSettings.model) o.selected = true;
    sm.appendChild(o);
  }
}
function renderEngines() {
  const g = $('engGrid'); g.innerHTML = '';
  const engines = [
    { id:'edge', label:'Edge Neural', meta:'free · cloud', ok:true },
    { id:'piper', label:'Piper', meta:curSettings.piper_available ? 'free · runs on server · offline' : 'not installed', ok:curSettings.piper_available },
    { id:'elevenlabs', label:'ElevenLabs', meta:curSettings.el_has_key ? 'premium · needs paid plan' : 'no API key', ok:curSettings.el_has_key },
  ];
  for (const e of engines) {
    const d = document.createElement('div');
    d.className = 'prov' + (e.id === curSettings.tts_engine ? ' sel' : '') + (e.ok ? '' : ' nokey');
    d.innerHTML = `<div class="pname">${e.label}</div><div class="pmeta">${e.meta}</div>`;
    if (e.ok) d.addEventListener('click', async () => {
      if (e.id === curSettings.tts_engine) return;
      await saveSettings({ tts_engine: e.id });
      curSettings.tts_engine = e.id;
      renderEngines(); renderVoices();
    });
    g.appendChild(d);
  }
}
function renderVoices() {
  const sv = $('selVoice');
  sv.innerHTML = '';
  const eng = curSettings.tts_engine;
  const list = eng === 'elevenlabs' ? curSettings.el_voices
             : eng === 'piper' ? curSettings.piper_voices
             : curSettings.voices;
  const active = eng === 'elevenlabs' ? curSettings.el_voice
               : eng === 'piper' ? curSettings.piper_voice
               : curSettings.voice;
  for (const v of list) {
    const o = document.createElement('option');
    o.value = v.id; o.textContent = v.label;
    if (v.id === active) o.selected = true;
    sv.appendChild(o);
  }
}
async function loadSettings() {
  try {
    curSettings = await fetch('/api/settings').then(r => r.json());
    renderProviders();
    await loadModels();
    renderEngines();
    renderVoices();
    $('setStatus').textContent = `active → ${curSettings.provider} · ${curSettings.model} · ${curSettings.tts_engine}:${curSettings.tts_engine === 'elevenlabs' ? curSettings.el_voice : curSettings.voice}`;
  } catch (e) { $('setStatus').textContent = 'failed to load settings'; }
}
async function saveSettings(part) {
  $('setStatus').textContent = 'saving…';
  const r = await fetch('/api/settings', { method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(part) });
  const j = await r.json();
  curSettings = Object.assign(curSettings || {}, j);
  $('setStatus').textContent = `saved ✓ — ${j.provider} · ${j.model} · ${j.voice}`;
  addFeed(`[ui] settings → ${JSON.stringify(part)}`, true);
}
document.addEventListener('DOMContentLoaded', () => {
  $('selModel').addEventListener('change', e => saveSettings({ model: e.target.value }));
  $('selVoice').addEventListener('change', e => {
    if (curSettings.tts_engine === 'elevenlabs') { curSettings.el_voice = e.target.value; saveSettings({ el_voice: e.target.value }); }
    else if (curSettings.tts_engine === 'piper') { curSettings.piper_voice = e.target.value; saveSettings({ piper_voice: e.target.value }); }
    else { curSettings.voice = e.target.value; saveSettings({ voice: e.target.value }); }
  });
  $('previewVoice').addEventListener('click', async () => {
    const btn = $('previewVoice');
    btn.disabled = true; btn.textContent = '…';
    try {
      const r = await fetch('/api/settings/preview_voice', { method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ voice: $('selVoice').value, engine: curSettings.tts_engine }) });
      const ct = r.headers.get('content-type') || '';
      if (!ct.includes('audio')) {
        const j = await r.json();
        $('setStatus').textContent = `preview failed: ${j.error || 'unknown'}${j.detail ? ' — ' + j.detail.slice(0, 90) : ''}`;
      } else {
        const buf = await r.arrayBuffer();
        ensureCtx();
        if (audioCtx.state === 'suspended') await audioCtx.resume();
        const decoded = await audioCtx.decodeAudioData(buf);
        const src = audioCtx.createBufferSource();
        src.buffer = decoded; src.connect(audioCtx.destination); src.start();
      }
    } catch (e) { $('setStatus').textContent = 'preview failed'; }
    btn.disabled = false; btn.textContent = '▶ Preview';
  });
  loadSettings();
});

initLive2D();
connectVoice();
connectEvents();
loadCron();
setInterval(loadCron, 60000);
