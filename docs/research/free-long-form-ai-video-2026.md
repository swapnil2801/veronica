# Free & Open-Source AI Tools for Long-Form Video (Sept 2026)

Research date: 16 Sep 2026. Scope: genuinely free / open-weight options only. Paid tiers mentioned only where needed to explain a limit.

## TL;DR

No single free model generates a 10-minute video in one shot. Every open model caps a single clip at roughly 5-20 seconds; "long-form" is achieved by (a) autoregressive/streaming models that chain sections (FramePack, SkyReels-V2, LongLive), or (b) generating 5-15 s shots and assembling them with first/last-frame chaining plus a free NLE. Hosted free tiers are trial-sized, mostly watermarked, and almost all forbid commercial use.

Recommendation (short): Wan 2.2 (Apache 2.0) for shots + FramePack (Apache 2.0) for continuous minute-long sequences, assembled in ComfyUI and finished in DaVinci Resolve (free) or Kdenlive. Details in section 5.

---

## 1. Open-weight video generation models

### Wan 2.2 (Alibaba) — best all-round, cleanest license
- License: Apache 2.0; Alibaba claims no rights over generated content.[1] ComfyUI docs confirm commercial use is allowed.[2]
- Variants: TI2V-5B (T2V + I2V, 720p@24fps) and T2V/I2V-A14B MoE (480p/720p).[1]
- Hardware: the 5B model officially targets a 24 GB card (5-second 720p clip in under 9 minutes on an RTX 4090) but ComfyUI docs say it "should fit well on 8GB vram" with native offloading; 14B officially wants 80 GB at FP16, FP8 builds run on 24 GB, GGUF Q5 community-reported on 16 GB.[1][2][3]
- Clip length: 5 s native (1280x704, 24 fps).[3]
- Long-form: First-Last-Frame-to-Video (FLF2V) workflow for 14B lets you chain shots by feeding the last frame as the next first frame.[29] Community reports ~1 minute continuous via FLF chaining.
- Watermark: none. Usage limits: none (local).
- Caveat: "Wan 2.5/2.6/2.7" have no open weights — pages offering "Wan 2.7 downloads" are SEO fabrications; the newest open release is Wan 2.2 (verified against the official HF org, Aug 2026).[4][3]

### LTX-2.5 / LTX-2.3 (Lightricks) — highest quality + native synced audio, but revenue-capped license
- LTX-2.5 (11 Aug 2026): 22B DiT, native multishot generation (connected shots holding character/lighting/voice across cuts), optional duration predictor, distilled 8-step checkpoint.[5]
- Duration: 20 s ceiling at 720p/1080p (24/25 fps); 1440p, 4K and high-frame-rate combos cap at 10 s.[7] LTX-2.3: up to 4K, 20 s per generation, "extendable via a dedicated endpoint"; T2V, I2V, V2V, extend-video, retake-video, keyframe interpolation.[8]
- Hardware: min 16 GB VRAM claimed for 2.5;[7] LTX-2.3 ships FP8 quantized and distilled variants.[8]
- License: LTX-2.x Community License (Aug 11 2026) — free to use/modify/distribute for any purpose, but "Entities with annual revenues of at least $10,000,000" must obtain a paid Commercial Use Agreement.[6] Also forbids using it to build a product that competes with Lightricks' offerings without a separate license.[6] Note: LTX-2.3 was widely reported as Apache 2.0 at launch,[8] but the LTX-2 repo now lists a Community License for all LTX-2 versions since Jan 5 2026 — treat it as the Community License.
- Watermark: none (self-hosted). Hosted API is pay-per-second.

### HunyuanVideo 1.5 (Tencent) — lightest strong model, restrictive territory
- 8.3B params; T2V + I2V; 480p/720p native with built-in SR to 1080p; 129 frames max (~5 s @ 24fps);[9][11]
- Hardware: ~10-12 GB VRAM at FP8 with text-encoder offload; RTX 4070 12 GB minimum.[11]
- License: Tencent Hunyuan Community License — DOES NOT APPLY in the EU, UK and South Korea; >100M MAU products need a separate license.[10] India is inside the licensed territory.
- Watermark: none.

### FramePack (lllyasviel, Stanford) — best for CONTINUOUS long video on cheap GPUs
- Next-frame-section prediction; compresses context to constant length so workload is invariant to video length. 13B model, 6 GB VRAM minimum on RTX 30/40/50 series.[12]
- Speed: 2.5 s/frame unoptimized, 1.5 s/frame with TeaCache on RTX 4090; laptop 3060/3070ti 4-8x slower.[12] A 60 s @30fps clip (1800 frames) takes ~45 min (TeaCache) to ~75 min on a 4090.[13]
- Duration: demonstrated 60 s; memory is not the limit — generation time and drift are.[13]
- License: Apache 2.0 (repo). Official repo warns that framepack.ai/.co/.net etc. are spam/fake sites.[12]
- Watermark: none. I2V only (start from an image).

### SkyReels-V2 (Skywork) — "infinite-length" diffusion-forcing model
- First open-source autoregressive Diffusion-Forcing video model; DF-14B-720P for infinite-length generation, 30 s demo videos, T2V + I2V, sync/async modes, video extension and start/end frame control.[14][15]
- Hardware: lower --base_num_frames to reduce peak VRAM; --offload and TeaCache supported (14B is heavy; 1.3B-540P variant exists).[15]
- License: Skywork Community License — "supports commercial use" without re-applying, subject to its terms; asks users not to deploy for internet services without security review.[16]

### LongLive (NVIDIA) — real-time interactive minute-long generation
- Fine-tunes a 1.3B short-clip model (Wan-based) to minute-long generation; 20.7 FPS on a single H100; accepts sequential prompts to steer the video as it generates. LongLive 2.0 adds NVFP4 parallel infra; SANA-Video port does 60 s interactive video in real time.[17][19]
- License: Apache 2.0 (v1.0 LICENSE file).[18]
- Hardware: research-grade (H100 class) — not a consumer option yet.

### MiniMax H3 (open weights, Aug 2026) — top quality with audio, but NOT licensed in US/EU/UK/KR
- Up to 15 s video with synchronized stereo audio; open weights generate at 768p short-side; FL2VA (first/last frame) and Ref2VA (up to 9 ref images, 3 clips, 3 audio) variants for consistent characters and clip continuation.[20]
- License: MiniMax H3 Community License — royalty-free commercial use, but >US$20M/yr revenue needs written authorization, products must display "MiniMax H3", no distillation into other models, and Excluded Territories = EU, UK, South Korea, USA.[20][21] India is not excluded.
- Hardware: datacenter-class (reference: 4xB300 for an 8.7 s clip in ~87 s).[20]

Older options not recommended: Mochi 1 (Apache 2.0, 480p, 5 s, 24 GB+), CogVideoX-1.5 (Apache 2.0, 10 s, 40 GB+), Open-Sora 2.0 (Apache 2.0). Superseded on quality by Wan 2.2 / LTX-2.x.

---

## 2. Hosted "free" tiers (reality check, Sept 2026)

Independent ledger checks on signed-in accounts (1 Sep 2026) found far fewer genuinely daily-resetting free tiers than marketing claims.[22]

| Tool | Free quota | Resets | Watermark | Commercial on free | Max clip |
|---|---|---|---|---|---|
| Google Flow (Veo 3.1 Fast) | 50 credits/day (~2 Fast clips) | Daily | SynthID always; visible "Veo" mark reported 2026 | Check ToS | 4-8 s |
| Kling | 66 credits/month (NOT daily) | Monthly | Yes; removal is premium-only | Check ToS | 5-10 s |
| Hailuo (MiniMax) | 200 one-time credits, expire in 3 days | Never | Yes | No | 6 s |
| Pixverse | 60 credits/day (~1 clip, 540p) | Daily | Likely | Check ToS | 8 s |
| Seedance (Dreamina) | daily bonus credits | Daily | Yes | Check ToS | 5 s |
| Pika | 80 credits/month, 480p | Monthly | Yes | Check ToS | 5 s |
| Runway | 125 credits once (~10 s Gen-4.5) | Never | – | – | trial |
| Luma Dream Machine | no free plan published (Sept 2026) | – | was permanent | personal only | ~5 s |
| Adobe Firefly / VEED | clean 720p / 1080p clip on free | daily / one-off | No (frame-checked) | Check ToS | short |

Sources: [22][23][24][25][26][32]. Kling's own policy lists 1080p, watermark removal and video extension as premium-only.[23] All Veo 3 output carries a SynthID digital watermark.[25]

Verdict: hosted free tiers are for testing prompts, not for producing long-form content — you would need dozens of clips, and free tiers give 1-3 per day, watermarked, non-commercial.

---

## 3. Free assembly / editing tools

- MoneyPrinterTurbo (MIT, ~122k stars): topic -> LLM script -> stock footage (Pexels/Pixabay) or local clips -> TTS (Edge TTS free) -> subtitles (Whisper) -> BGM -> 1080x1920 or 1920x1080 MP4 via MoviePy/FFmpeg. Runs CPU-only with a cloud LLM; ships WebUI, REST API and CLI.[27][28] Caveat: default BGM files have unclear licensing — replace for commercial use.[28] Good for narrated explainer/faceless long videos; swap the stock-footage step for your AI-generated clips.
- ComfyUI: native Wan 2.2 workflows (T2V, I2V, 5B and 14B), FLF2V workflow for shot chaining, GGUF loaders for low VRAM, Lightx2v 4-step LoRA for speed.[2][29]
- DaVinci Resolve 21 (free edition): edit, color, Fusion VFX, Fairlight audio; Studio is $295 one-time.[31]
- Kdenlive 26.08 (GPL, free): cross-platform NLE (Linux/Windows/macOS).[30]

---

## 4. Comparison matrix (open models)

| Model | License | Commercial | Region limits | Single-clip max | Long-form mechanism | Min VRAM (practical) | Audio |
|---|---|---|---|---|---|---|---|
| Wan 2.2 5B / 14B | Apache 2.0 | Yes, unrestricted | None | 5 s 720p | FLF2V chaining, VACE extension | 8 GB (5B) / 16-24 GB (14B) | No |
| LTX-2.5 | LTX Community | Yes if < $10M revenue | None | 20 s 1080p / 10 s 4K | Native multishot, extend endpoint | 16 GB | Yes, synced |
| HunyuanVideo 1.5 | Tencent Community | Yes (<100M MAU) | Not EU/UK/KR | ~5 s 720p (+SR 1080p) | Chaining | 12 GB | No |
| FramePack | Apache 2.0 | Yes | None | 60 s+ continuous | Native (next-frame-section) | 6 GB | No |
| SkyReels-V2 DF | Skywork Community | Yes | None stated | "infinite" (30 s demos) | Native diffusion forcing | high (14B); 1.3B variant | No |
| LongLive | Apache 2.0 | Yes | None | ~minute | Native, interactive | H100-class | No |
| MiniMax H3 | H3 Community | Yes if < $20M, must credit | Not US/EU/UK/KR | 15 s 768p | Ref2VA clip continuation | datacenter | Yes, stereo |

---

## 5. Recommendation and practical workflow

Primary stack (free, commercial-safe from India, runs on a 12-24 GB consumer GPU or a rented 4090):

1. Script & shot list — LLM (or MoneyPrinterTurbo's script step) breaks the video into 5-15 s shots with consistent character/scene descriptions.
2. Keyframes — generate a still per shot (any free image model) so every clip starts from a controlled image; this is what keeps characters consistent across a long video.
3. Shots — Wan 2.2 I2V (14B FP8 on 24 GB, 5B on 8-12 GB) in ComfyUI. Use the FLF2V workflow to chain: last frame of clip N = first frame of clip N+1.[29][2]
4. Continuous sequences — where you need one unbroken 30-60 s take (a dance, a walk-through, a talking scene), use FramePack from the keyframe; budget ~45-75 min per minute on a 4090.[13]
5. Voice/subtitles/music — Edge TTS (free) + Whisper subtitles via MoneyPrinterTurbo, or your existing Cartesia/Sarvam TTS pipeline; replace the bundled music with licensed tracks.[28]
6. Assembly — DaVinci Resolve free (or Kdenlive): cut, crossfade seams, color-match clips, upscale 720p->1080p, mix audio.[31][30]

When to deviate:
- Need synced dialogue/SFX generated with the picture and you are under $10M revenue: use LTX-2.5 (20 s clips, native multishot) instead of Wan for those scenes.[5][6]
- Only a 6-8 GB GPU: Wan 2.2 5B GGUF Q8 for shots + FramePack for long takes.[3][12]
- No GPU: rent a 4090 by the hour (FramePack: pay for time, not VRAM)[13] — still far cheaper than any hosted plan for minutes of output. Hosted free tiers cannot realistically produce long-form.

Honest limits: expect drift and identity wobble past ~30-60 s of continuous generation; plan cuts every 5-15 s like a real edit, and keep total AI-generated runtime per session realistic (one 4090 produces roughly 2-5 minutes of usable 720p footage per working day with re-rolls).

## Sources

[1] https://github.com/Wan-Video/Wan2.2 — Wan2.2 GitHub (Apache 2.0, TI2V-5B, 14B)
[2] https://docs.comfy.org/tutorials/video/wan/wan2_2 — ComfyUI Wan2.2 native workflow docs
[3] https://localaimaster.com/blog/wan-vram-requirements-by-gpu — Wan 2.2 VRAM by GPU (Local AI Master)
[4] https://localaimaster.com/blog/wan-2-7-open-source — Is Wan 2.7 open source? (no)
[5] https://huggingface.co/Lightricks/LTX-2.5 — LTX-2.5 model card
[6] https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x — LTX-2.x Community License
[7] https://dreampixelforge.com/blog/ltx-2-5 — LTX 2.5 specs, license, hardware
[8] https://rits.shanghai.nyu.edu/ai/ltx-2-3-sharper-video-native-portrait-and-cleaner-audio-in-lightricks-latest-open-source-model — LTX-2.3 overview (20s, 4K, extend endpoint)
[9] https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5 — HunyuanVideo-1.5 GitHub
[10] https://huggingface.co/tencent/HunyuanVideo-1.5/blob/main/LICENSE — Tencent Hunyuan Community License
[11] https://willitrunai.com/blog/hunyuanvideo-1-5-vram-requirements — HunyuanVideo 1.5 VRAM requirements
[12] https://github.com/lllyasviel/FramePack — FramePack GitHub (official)
[13] https://www.runpod.io/articles/guides/framepack-runpod — FramePack long video on single GPU (Runpod)
[14] https://github.com/SkyworkAI/SkyReels-V2 — SkyReels-V2 GitHub
[15] https://huggingface.co/Skywork/SkyReels-V2-I2V-1.3B-540P-Diffusers — SkyReels-V2 HF model card (DF long video)
[16] https://github.com/SkyworkAI/SkyReels-V2/blob/main/LICENSE.txt — Skywork Community License
[17] https://github.com/NVlabs/LongLive — NVlabs LongLive GitHub
[18] https://raw.githubusercontent.com/NVlabs/LongLive/v1.0/LICENSE — LongLive v1.0 LICENSE (Apache 2.0)
[19] https://arxiv.org/html/2509.22622v1 — LongLive paper
[20] http://hub.minimax.io/h3 — MiniMax H3 open hub FAQ
[21] https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE — MiniMax H3 Community License
[22] https://vibedex.ai/blog/best-free-ai-video-generator-2026 — VibeDex free AI video tiers audit (Sept 2026)
[23] https://kling.ai/docs/point-policy — Kling AI Credits Policy
[24] https://genrates.com/platforms/hailuo-app — Hailuo free tier facts (GenRates)
[25] https://developers.googleblog.com/veo-3-now-available-gemini-api — Veo 3 Gemini API (SynthID, pricing)
[26] https://support.google.com/gemini/thread/415039803/watermark-in-video-generations-for-ultra-user?hl=en — Veo visible watermark thread
[27] https://github.com/harry0703/MoneyPrinterTurbo — MoneyPrinterTurbo GitHub (MIT)
[28] https://aiaffer.com/tools/moneyprinterturbo-review-2026 — MoneyPrinterTurbo review 2026
[29] https://comfy.org/workflows/video_wan2_2_14B_flf2v-7016f027bcf1 — Wan 2.2 FLF2V ComfyUI workflow
[30] https://kdenlive.org/en — Kdenlive
[31] https://www.blackmagicdesign.com/products/davinciresolve — DaVinci Resolve
[32] https://skorykh.com/blog/free-text-to-video-ai-tools-without-watermark — Free T2V without watermark (Skorykh)
