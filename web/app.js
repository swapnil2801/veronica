/* Veronica dashboard: Live2D avatar + voice loop + reactive visuals + panels. */
const SR = 16000;
let ws, audioCtx, micStream, workNode, capturing = false, handsFree = false;
let playQueue = [], playing = false, pendingText = null;
let model = null, pixiApp = null;
let activeCharacter = localStorage.getItem('veronica-character') || 'haru';
let micLevel = 0;

const CHARACTERS = {
  haru: { label: 'Haru · current', model: 'models/haru/haru_greeter_t03.model3.json', note: 'Live2D sample model' },
  hiyori: { label: 'Hiyori · new option', model: 'models/Hiyori/Hiyori.model3.json', note: 'Live2D sample model' },
};
let mouthVal = 0, mouthTarget = 0, moodRelax = null;

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
  document.querySelectorAll('.mood-row button').forEach(b => b.addEventListener('click', () => setMood(b.dataset.mood, 6000)));
});

const HINTS = { idle:'ready', listening:'listening…', thinking:'thinking…', speaking:'speaking' };
function setState(s) {
  document.body.dataset.vstate = s;
  $('vstate').textContent = s;
  const h = $('chatHint'); if (h) h.textContent = HINTS[s] || s;
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

/* ---------------- Expressions (mood -> face) ----------------
   Moods arrive from the server as the first token of every reply. We blend
   raw Cubism parameters ourselves (Haru and Hiyori share the standard eye,
   brow, mouth and cheek parameter ids) so one table works for every
   character and eases smoothly instead of snapping.
   Eye-open values are multipliers (1 = untouched) so blinking still works;
   everything else is added on top of the running motion. */
const EYE_KEYS = new Set(['ParamEyeLOpen', 'ParamEyeROpen']);
const MOODS = {
  neutral:   {},
  happy:     { ParamEyeLSmile:1, ParamEyeRSmile:1, ParamMouthForm:1.2, ParamMouthOpenY:.25, ParamBrowLY:.4, ParamBrowRY:.4, ParamCheek:.6, ParamAngleZ:3 },
  warm:      { ParamEyeLSmile:.45, ParamEyeRSmile:.45, ParamEyeLOpen:.75, ParamEyeROpen:.75, ParamMouthForm:.6, ParamBrowLY:.1, ParamBrowRY:.1, ParamCheek:.5, ParamAngleZ:-4 },
  excited:   { ParamEyeLOpen:1.25, ParamEyeROpen:1.25, ParamEyeLSmile:.5, ParamEyeRSmile:.5, ParamMouthForm:1, ParamBrowLY:.7, ParamBrowRY:.7, ParamCheek:.5, ParamBodyAngleY:3 },
  playful:   { ParamEyeLOpen:.55, ParamEyeLSmile:.6, ParamMouthForm:.8, ParamBrowLY:.3, ParamBrowRY:-.1, ParamBrowRAngle:.3, ParamAngleZ:6, ParamCheek:.3 },
  shy:       { ParamEyeLOpen:.6, ParamEyeROpen:.6, ParamEyeBallY:-.4, ParamEyeBallX:.3, ParamMouthForm:.35, ParamBrowLY:-.1, ParamBrowRY:-.1, ParamCheek:1, ParamTere:1, ParamAngleZ:-6, ParamAngleY:-6 },
  thinking:  { ParamEyeLOpen:.8, ParamEyeROpen:.85, ParamEyeBallX:.5, ParamEyeBallY:.4, ParamBrowLY:-.2, ParamBrowRY:.2, ParamBrowRAngle:.3, ParamMouthForm:-.2, ParamAngleZ:5, ParamAngleX:-6 },
  concerned: { ParamEyeLOpen:.9, ParamEyeROpen:.9, ParamBrowLY:-.55, ParamBrowRY:-.55, ParamBrowLAngle:.35, ParamBrowRAngle:.35, ParamBrowLForm:-.6, ParamBrowRForm:-.6, ParamMouthForm:-.7, ParamAngleY:-4 },
  sad:       { ParamEyeLOpen:.55, ParamEyeROpen:.55, ParamEyeBallY:-.5, ParamBrowLY:-.7, ParamBrowRY:-.7, ParamBrowLAngle:.5, ParamBrowRAngle:.5, ParamMouthForm:-1.2, ParamAngleY:-10, ParamBodyAngleY:-3 },
  surprised: { ParamEyeLOpen:1.4, ParamEyeROpen:1.4, ParamBrowLY:1, ParamBrowRY:1, ParamBrowLForm:1, ParamBrowRForm:1, ParamMouthForm:-.6, ParamMouthOpenY:.7, ParamEyeBallForm:-.6, ParamEyeBallY:.2, ParamAngleY:6, ParamBodyAngleY:-3 },
};
const MOOD_ICON = { neutral:'·', happy:'☺', warm:'♡', excited:'✦', playful:'~', shy:'…', thinking:'?', concerned:'!', sad:'↓', surprised:'!?' };
const MOOD_PARAMS = [...new Set(Object.values(MOODS).flatMap(Object.keys))];
let moodName = 'neutral', moodCur = {}, moodHoldUntil = Infinity;
const restOf = k => EYE_KEYS.has(k) ? 1 : 0;
function setMood(name, holdMs) {
  if (!MOODS[name]) name = 'neutral';
  moodName = name;
  moodHoldUntil = holdMs ? performance.now() + holdMs : Infinity;
  document.body.dataset.mood = name;
  const el = $('moodTag'); if (el) el.textContent = `${MOOD_ICON[name] || ''} ${name}`;
  document.querySelectorAll('.mood-row button').forEach(b => b.classList.toggle('sel', b.dataset.mood === name));
}
function applyMood(core) {
  if (moodHoldUntil !== Infinity && performance.now() > moodHoldUntil) setMood('neutral');
  const tgt = MOODS[moodName] || {};
  for (const k of MOOD_PARAMS) {
    const t = (k in tgt) ? tgt[k] : restOf(k);
    const c = (k in moodCur) ? moodCur[k] : restOf(k);
    const v = moodCur[k] = c + (t - c) * 0.08; // ~0.4 s ease at 30 fps
    try {
      if (EYE_KEYS.has(k)) { if (Math.abs(v - 1) > 0.002) core.multiplyParameterValueById(k, v); }
      else if (Math.abs(v) > 0.002) core.addParameterValueById(k, v);
    } catch (e) {}
  }
}

/* ---------------- Live2D ---------------- */
function fitModel() {
  if (!model || !pixiApp) return;
  const stage = $('stage');
  const w = stage.clientWidth, h = stage.clientHeight;
  if (!w || !h) return;
  pixiApp.renderer.resize(w, h);

  // Use the rendered Pixi bounds at scale 1, not Cubism's internal canvas
  // dimensions. The latter vary between models and made Hiyori render too
  // small inside the stage.
  model.scale.set(1);
  model.anchor.set(0.5, 0);
  const base = model.getLocalBounds();
  const mw = Math.max(base.width, 1);
  const mh = Math.max(base.height, 1);
  const fullscreen = document.body.classList.contains('fs');

  // Fill the stage horizontally and vertically. The intentional overscan
  // crops the lower body while keeping the face and shoulders prominent.
  const fillScale = Math.max((w * (fullscreen ? 1.04 : 0.98)) / mw,
                             (h * (fullscreen ? 1.16 : 1.04)) / mh);
  model.scale.set(fillScale);
  // Leave headroom under the top stage bar so the face is never covered.
  model.position.set(w / 2, fullscreen ? -h * 0.05 : -h * 0.01);
}
let characterLoadId = 0;
async function loadCharacter(characterId) {
  const chosenId = CHARACTERS[characterId] ? characterId : 'haru';
  const chosen = CHARACTERS[chosenId];
  const loadId = ++characterLoadId;
  $('characterStatus').textContent = `${chosen.label} · loading…`;
  try {
    // Load first. Keep the current avatar visible if the replacement fails.
    const nextModel = await PIXI.live2d.Live2DModel.from(chosen.model);

    // A newer selection won while this model was loading; discard this result.
    if (loadId !== characterLoadId) {
      nextModel.destroy({ children: true });
      return;
    }

    const previousModel = model;
    model = nextModel;
    pixiApp.stage.addChild(model);
    fitModel();
    if (previousModel) {
      pixiApp.stage.removeChild(previousModel);
      previousModel.destroy({ children: true });
    }
    activeCharacter = chosenId;
    localStorage.setItem('veronica-character', activeCharacter);
    const picker = $('characterSelect');
    if (picker) picker.value = activeCharacter;
    model.on('hit', () => { setMood(Math.random() < 0.5 ? 'playful' : 'shy', 4000); try { model.motion('Tap'); } catch(e) { try { model.motion('TapBody'); } catch (_) {} } });
    setMood(moodName);

    // Keep lip-sync frame-locked after each motion update for every model option.
    const mm = model.internalModel.motionManager;
    const origUpdate = mm.update.bind(mm);
    mm.update = (...a) => {
      const r = origUpdate(...a);
      mouthVal += (mouthTarget - mouthVal) * 0.5;
      const core = model.internalModel.coreModel;
      applyMood(core);
      if (playing) {
        try { core.setParameterValueById('ParamMouthOpenY', mouthVal); } catch (e) {}
      }
      return r;
    };
    $('characterStatus').textContent = `${chosen.label} · ready`;
  } catch (e) {
    // Ignore stale failures; a newer request owns the status now.
    if (loadId !== characterLoadId) return;
    console.error('character failed to load', e);
    $('characterStatus').textContent = `${chosen.label} · unavailable`;
  }
}
async function initLive2D() {
  const canvas = $('live2d'), stage = $('stage');
  pixiApp = new PIXI.Application({ view: canvas, backgroundAlpha: 0,
    width: stage.clientWidth, height: stage.clientHeight, autoDensity: true,
    resolution: Math.min(window.devicePixelRatio || 1, 1.5), antialias: true });
  pixiApp.ticker.maxFPS = 30;
  await loadCharacter(activeCharacter);
  window.addEventListener('resize', fitModel);
  const picker = $('characterSelect');
  if (picker) {
    picker.value = activeCharacter;
    picker.addEventListener('change', () => loadCharacter(picker.value));
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
   Text renders as tokens arrive; audio continues independently so the chat
   never feels blocked by TTS or audio decoding. */
let replySpan = null, greeted = false;
function connectVoice() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/voice`);
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => {
    $('connTxt').textContent = 'online'; $('connState').classList.add('on');
    if (!greeted) { greeted = true; setTimeout(() => { if (ws.readyState === 1) { ws.send(JSON.stringify({ type:'greet' })); setState('thinking'); } }, 900); }
  };
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
    } else if (m.type === 'reply_delta') {
      showReplyDelta(m.text || '');
    } else if (m.type === 'tool') {
      addLine('action', `⚙ ${m.name.replaceAll('_',' ')}`, 'tool');
    } else if (m.type === 'mood') {
      setMood(m.mood);
    } else if (m.type === 'audio_sentence') {
      pendingText = m.text || '';
    } else if (m.type === 'caption') {
      if (!replySpan) showCaption(m.text); // fallback if no text stream arrived
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
function showReplyDelta(text) {
  if (!text) return;
  const follow = nearBottom();
  if (!replySpan) replySpan = addLine('Veronica', '');
  replySpan.textContent += text;
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
  clearTimeout(moodRelax); moodRelax = setTimeout(() => setMood('neutral'), 9000);
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
const endUtterance = () => { if (ws && ws.readyState === 1) { ws.send(JSON.stringify({type:'end_utterance'})); setState('thinking'); setMood('thinking'); } };

const ptt = $('ptt');
async function pttDown(e) { e.preventDefault(); await startMic(); if (audioCtx.state==='suspended') await audioCtx.resume(); capturing = true; ptt.classList.add('active'); setState('listening'); }
function pttUp(e) { e.preventDefault(); if (!capturing) return; capturing = false; ptt.classList.remove('active'); endUtterance(); }
ptt.addEventListener('mousedown', pttDown); ptt.addEventListener('mouseup', pttUp); ptt.addEventListener('mouseleave', pttUp);
ptt.addEventListener('touchstart', pttDown, { passive:false }); ptt.addEventListener('touchend', pttUp); ptt.addEventListener('touchcancel', pttUp);
ptt.addEventListener('contextmenu', e => e.preventDefault());

$('handsfree').addEventListener('click', async () => {
  handsFree = !handsFree;
  $('handsfree').classList.toggle('active', handsFree);
  $('handsfree').setAttribute('aria-pressed', String(handsFree));
  if (handsFree) { await startMic(); if (audioCtx.state==='suspended') await audioCtx.resume(); setState('listening'); }
  else setState('idle');
});

const tin = $('textin');
function sendText() {
  const t = tin.value.trim(); if (!t || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({type:'text', text:t})); tin.value = ''; setState('thinking'); setMood('thinking');
}
const chatForm = $('chatForm');
chatForm.addEventListener('submit', e => { e.preventDefault(); sendText(); });
tin.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(); }
});

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
    { id:'deepgram', label:'Deepgram Aura', meta:curSettings.deepgram_tts_available ? 'cloud · fast voice agent' : 'not configured', ok:curSettings.deepgram_tts_available },
    { id:'cartesia', label:'Cartesia Sonic', meta:curSettings.cartesia_available ? 'cloud · expressive voice' : 'not configured', ok:curSettings.cartesia_available },
    { id:'sarvam', label:'Sarvam Bulbul', meta:curSettings.sarvam_available ? 'cloud · Indian voices · Hinglish' : 'not configured', ok:curSettings.sarvam_available },
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
function renderSttOptions() {
  const g = $('sttGrid'); if (!g || !curSettings.stt_options) return;
  g.innerHTML = '';
  for (const option of curSettings.stt_options) {
    const d = document.createElement('div');
    d.className = 'prov' + (option.id === curSettings.stt_engine ? ' sel' : '') + (option.available ? '' : ' nokey');
    d.innerHTML = `<div class="pname">${option.label}</div><div class="pmeta">${option.available ? option.meta : 'not configured'}</div>`;
    if (option.available) d.addEventListener('click', async () => { await saveSettings({ stt_engine: option.id }); await loadSettings(); });
    g.appendChild(d);
  }
}
function renderVoices() {
  const sv = $('selVoice');
  sv.innerHTML = '';
  const eng = curSettings.tts_engine;
  const list = eng === 'elevenlabs' ? curSettings.el_voices
             : eng === 'piper' ? curSettings.piper_voices
             : eng === 'deepgram' ? curSettings.deepgram_tts_voices
             : eng === 'cartesia' ? curSettings.cartesia_voices
             : eng === 'sarvam' ? curSettings.sarvam_voices
             : curSettings.voices;
  const active = eng === 'elevenlabs' ? curSettings.el_voice
               : eng === 'piper' ? curSettings.piper_voice
               : eng === 'deepgram' ? curSettings.deepgram_tts_model
               : eng === 'cartesia' ? curSettings.cartesia_voice
               : eng === 'sarvam' ? curSettings.sarvam_voice
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
    renderSttOptions();
    renderVoices();
    $('setStatus').textContent = `active → ${curSettings.provider} · ${curSettings.model} · ${curSettings.tts_engine}:${curSettings.tts_engine === 'elevenlabs' ? curSettings.el_voice : curSettings.tts_engine === 'deepgram' ? curSettings.deepgram_tts_model : curSettings.voice}`;
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
    else if (curSettings.tts_engine === 'deepgram') { curSettings.deepgram_tts_model = e.target.value; saveSettings({ deepgram_tts_model: e.target.value }); }
    else if (curSettings.tts_engine === 'cartesia') { curSettings.cartesia_voice = e.target.value; saveSettings({ cartesia_voice: e.target.value }); }
    else if (curSettings.tts_engine === 'sarvam') { curSettings.sarvam_voice = e.target.value; saveSettings({ sarvam_voice: e.target.value }); }
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
