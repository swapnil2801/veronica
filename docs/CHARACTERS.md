# Veronica characters

All avatars are official Live2D Inc. sample models (© Live2D Inc.), downloaded from
https://www.live2d.com/en/learn/sample/ and used under the
[Live2D sample-model terms](https://www.live2d.com/eula/live2d-sample-model-terms_en.html)
(free for individuals / businesses under ¥10M annual revenue; larger businesses need a
Cubism SDK Release License — see `web/models/LIVE2D-LICENSE.md`).

Selection criteria: female, half-body-friendly framing, and **full face rigging** — every
model below has eye-open, eye-smile (except Shizuku), brow Y/angle/form, mouth-form and
mouth-open parameters, so the mood engine (`MOODS` in `web/app.js`) and RMS lip-sync work
on every one of them.

| id | dir | rig ids | expressions | idle/tap motions | notes |
|---|---|---|---|---|---|
| `haru` (default) | `models/haru` | standard | 8 | 3 / 2 | original |
| `hiyori` | `models/Hiyori` | standard | 0 | 9 / 1 | original |
| `epsilon` | `models/Epsilon` | legacy `PARAM_*` | 8 | 1 / 4 (+flick/shake) | has `PARAM_TERE` (blush) |
| `tsumiki` | `models/Tsumiki` | legacy `PARAM_*` | 10 | 3 / 5 (+flicks/shake) | 4 cheek params; small-canvas model → zoomed via `fit` |
| `shizuku` | `models/Shizuku` | legacy `PARAM_*` | 0 | 1 / 1 (+flicks) | classic Cubism 2 sample; no eye-smile params |
| `kei` | `models/Kei` | standard | 0 | 0 / 1 | `kei_basic_free`; bundled `sounds/` and JP/ZH/KO motions removed (we drive the mouth from our own TTS) |

## How the code handles model differences

* `CHARACTERS[id].legacy` is informational; the real work is `buildParamMap(core)`, which maps
  each standard id (`ParamMouthForm`…) to the id that actually exists in the loaded `.moc3`
  (`PARAM_MOUTH_FORM`, `PARAM_CHEEK_01`, `PARAM_BODY_Y`…). `applyMood` and lip-sync go through
  this map. **Do not use `core.getParameterIndex(id) >= 0` to test existence** — the Cubism
  framework allocates a phantom slot for unknown ids and always returns ≥ 0; check
  `core._parameterIds` instead.
* `CHARACTERS[id].fit = { n: [wMul, hMul, yShift], fs: [...] }` adjusts framing per layout so the
  face is large and the head is never cut (models have very different canvas sizes).

## Removed

Mao, Rice, Ren, Wanko (added in a previous pass) were dropped: Rice has no lip-sync/mouth-form
rig, Mao's mouth is `ParamA` with no `ParamMouthForm`, Ren failed to load, Wanko is a mascot
dog. None matched the "expressive companion" brief.

## Verification (headless_shell + swiftshader, see `tools/shot.py`)

Every model was loaded through the real selector, `paramMap` was checked for missing ids,
`setMood('happy')` was confirmed to move `ParamEyeLSmile`, and `ParamMouthOpenY` was confirmed
writable. Framing screenshots taken at 1366×768 normal and fullscreen; layout audit clean at
1920×1080 (normal + fs) and 1280×720 fs.
