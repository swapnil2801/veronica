# Free / free-tier AI video generation APIs (no local GPU) — research snapshot

Checked: 16 September 2026 (IST). Everything below is from official pricing/docs pages
unless marked otherwise. Quotas in this space change monthly; anything that looked
stale, promotional, or contradictory is flagged with **[verify]**. Leaked, shared or
"reseller" keys are deliberately excluded.

## TL;DR

There is no longer any official, ongoing, *unlimited-time* free API for frontier
video models. What exists is:

1. **Cloud trial credits** that happen to cover video models — Google Cloud $300/90 days
   (Veo 3.1 via Vertex AI)[4][5], Azure $200/30 days[27]. Largest real budgets.
2. **Provider new-user free quotas** — Alibaba Model Studio (Singapore) gives each Wan
   video model its own 50-second free quota for 90 days[6][7]; BytePlus ModelArk gives
   new users a per-model free token quota[20].
3. **Small "try it" allowances** — Replicate "Try for Free" limited runs[9], Hugging Face
   $0.10/month routed credits[11], Shotstack 10 render-minutes[28], Creatomate 50 credits[29].
4. **Paid-only** (no free tier at all on the API): Gemini API Veo[1], OpenAI Sora[23],
   Runway Dev[15], Kling[16], Luma[24], Vidu[17], fal (API)[12][13].

Best practical stack for a long-form video from short clips, at zero cash outlay:
**Google Cloud trial ($300) -> Veo 3.1 Fast/Lite on Vertex AI** for the clips, plus
**Alibaba Wan 2.x free seconds** as a second free pool, assembled with **Shotstack's free
10 minutes** (or ffmpeg on any cheap VM). Details in the recommendation section.

---

## 1. Google — Veo 3.1 (Gemini API and Vertex AI)

**Gemini Developer API (AI Studio key)**
- Veo 3.1 has **no free tier**: the pricing table lists "Not available" under Free Tier
  for Standard, Fast and Lite.[1]
- Paid rates (per second of output, with audio): Standard $0.40 (720p/1080p), $0.60 (4K);
  Fast $0.10 (720p), $0.12 (1080p), $0.30 (4K); Lite $0.05 (720p), $0.08 (1080p), no 4K.[1]
- You are only charged if the video is successfully generated.[1]
- Clip specs: 8-second clips at 720p/1080p/4K with native audio; durations 4/6/8 s
  (must be 8 s for 1080p/4K, extension, or reference images); 16:9 or 9:16.[2]
- Extension: Veo 3.1 / 3.1 Fast can extend a previous Veo video by 7 s up to 20 times,
  to ~141–148 s total; 720p only; source videos are stored 2 days.[2]
- Model IDs are still `*-preview` on the Gemini API (`veo-3.1-generate-preview`,
  `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview`).[1] Veo 2 shuts down
  30 June 2026 and Veo 3 is marked deprecated.[2] **[verify: the docs also now push
  "Gemini Omni Flash" as the default video model — paid tier only.[1]]**
- Terms: Google does not claim ownership of generated content; you must be 18+; API is
  for professional/business use; available only in listed regions (India is listed);
  EEA/CH/UK deployments must use paid services.[3][30] Unpaid-quota data may be used to
  improve Google products and reviewed by humans.[3]
- Watermark: Veo output carries SynthID (invisible). **[unverified — not on the pages
  fetched; it is Google's stated policy elsewhere.]**

**Vertex AI (Google Cloud) — the actual free route**
- Google Cloud Free Trial: **$300 welcome credit, valid 90 days**, for users who have
  never paid for Google Cloud/Maps/Firebase and never had the trial; a card is required
  for identity verification (temporary $0–1 hold, no charge); you are not billed unless
  you upgrade; when credit or 90 days run out the trial account and its resources
  stop.[4]
- Veo 3.1 on Vertex is listed at $0.40 (Standard, 720p/1080p), $0.10 (Fast, 720p) and
  $0.05 (Lite, 720p) per second with audio; only 200-responses are charged.[5]
- Rough budget: $300 ≈ 3,000 s (50 min) of Veo 3.1 Fast 720p or ≈ 6,000 s (100 min) of
  Lite, before retries. Realistically plan on 2–4 attempts per keeper.
- Commercial use: allowed under Google Cloud/Generative AI terms (same "no ownership
  claim" posture as Gemini API).[3] Trial-account resources are not for production
  until you upgrade.[4]

## 2. Alibaba Cloud Model Studio — Wan 2.x / 3.0 (International, Singapore)

- New users activating Model Studio in the **Singapore** region get an automatic
  per-model free quota, **valid 90 days** from activation/model release; only
  "International" deployment scope models are eligible; re-registering does not grant
  another quota; unused quota expires.[6]
- Video quotas: every listed Wan text-to-video model (wan2.7-t2v, wan2.6-t2v,
  wan2.5-t2v-preview, wan2.2-t2v-plus, wan2.1-t2v-turbo/plus, dated snapshots) has its
  **own 50-second free quota**; Wan 3.0 has 30 s combined input+output.[7] Because quotas
  are per model ID and dated snapshots count separately, stacking all of them yields
  several minutes of free footage.[6][7]
- Paid rates after quota: wan2.7-t2v $0.10/s (720p), $0.15/s (1080p); wan2.2-t2v-plus
  $0.02/s (480p), $0.10/s (1080p); wan2.1-t2v-turbo $0.036/s.[7] Failed requests are
  not billed and do not consume quota.[7]
- New users **cannot** keep calling after the quota is exhausted until they complete
  account info; a "Free Quota Only" switch hard-stops billing.[6]
- Watermark: console/playground videos always carry an "AI generated" watermark; **API
  calls default to `watermark=false`** (no watermark).[8]
- Commercial use: not restricted in the pages fetched; governed by Alibaba Cloud
  service terms. **[verify before commercial release.]**
- Geo: International scope is scheduled worldwide excluding mainland China; data stored
  in Singapore.[8]

## 3. BytePlus ModelArk — Seedance 2.0 / 2.5

- "ModelArk offers new users a free inference trial quota … simply register BytePlus to
  get a certain amount of free calls"; quota is per model, shared under the primary
  account, and covers only pay-as-you-go online inference (not batch).[20] The page does
  not state the video-token amount. **[verify in console after signup.]**
- Seedance resource-pack token rates: Seedance 2.5 $0.0064/k token (480p/720p),
  Seedance 2.0 $0.0043, 2.0 fast $0.0033, 2.0 mini $0.0021.[21] Seedance 2.5 advertises
  30-second single-shot output (marketing page, not docs). **[verify]**
- Region gating: BytePlus has an "International Availability" doc for its model
  service; check it for India.[20]

## 4. Replicate — "Try for Free" collection

- Models in the collection can be run **without purchasing credit** for a limited number
  of runs after creating an account; then billing must be added.[9] Video models in the
  collection: `minimax/video-01` (6 s clips), `luma/reframe-video`, `topazlabs/video-upscale`.[9]
- Replicate does not publish the run count. Commercial use "depends on the model's
  license."[9]
- Paid reference: Wan 3.0 $0.05/s (480p), $0.10/s (720p), $0.20/s (1080p).[10]

## 5. Hugging Face Inference Providers

- Free accounts: **$0.10/month** in routed credits ("subject to change"); PRO $2.00/month;
  no HF markup over provider prices; pay-as-you-go after.[11] Video models route to
  fal/Replicate etc., so $0.10 buys about one second of cheap video — useful only for
  smoke tests.

## 6. fal.ai

- Prepaid credits; new accounts start at 2 concurrent requests; account locks when the
  balance drops below a threshold.[12]
- "Free credits and free request coupons are only usable in Sandbox and the Playground —
  they cannot be used through the API or Workflows."[13] Third-party blogs claiming
  "$1" or "$20 signup credit" are **not** confirmed by fal's docs. **[flagged: treat
  fal as paid-only for API use.]**
- Commercial use: per-model; each model page shows "Commercial use" or "Research only".[12]

## 7. Paid-only, no free API tier (for completeness)

| Provider | Free API? | Entry cost | Clip limits | Notes |
|---|---|---|---|---|
| Runway Dev | No — "$10 minimum" credit purchase at $0.01/credit[15] | gen4_turbo 5 cr/s = $0.05/s; gen4.5 12 cr/s; veo3.1_fast 15 cr/s (audio)[14] | per model | Web-app free plan (125 one-time credits, watermarked) is separate from the API. **[verify — from third-party pricing pages]** |
| Kling | No — prepaid packages; smallest standard pack $700 (5,000 units); a "Trial Plan" tab exists[16] | Kling 3.0 $0.084/s 720p no audio; 3.0 Turbo $0.112/s 720p with audio[16] | 720p/1080p/4K | Trial pack price not on the fetched page; third-party sites quote $9.80/100 units. **[verify]** |
| Luma | No | Ray3.2 T2V/I2V 5 s: $0.15 (540p) / $0.30 (720p) / $1.20 (1080p)[24] | 5 s / 10 s | Consumer Dream Machine free tier is watermarked/non-commercial and not the API. |
| Vidu | No free credits; "First-Time User Credit Pack" is **$15** for 5,000 credits[17] | credits $0.005 each[18] | model dependent | one pack per user, valid 3 months[17] |
| MiniMax (Hailuo H3) | No free API quota shown[19] | H3 768p $0.08/s, 2K $0.13/s; H3-Max 480p $0.05/s[19] | 4–15 s | Consumer app has a free watermarked tier — not the API. |
| OpenAI Sora 2 | No — "Free: Not supported" rate-limit tier[23] | sora-2 $0.10/s 720p; sora-2-pro $0.30/s[23] | up to 20 s; extensions to 120 s[22] | **Deprecated: Videos API and all sora-2 models shut down 24 Sept 2026**[22] — do not build on it. |
| Amazon Nova Reel | No free tier | Bedrock pricing page | 6 s increments up to 2 min, 1280x720, 24 fps; us-east-1 only for v1:1[25] | **EOL 30 Sept 2026**, marked Legacy[26] |
| Azure (OpenAI Sora on Foundry) | $200 credit, 30 days, card required[27] | Azure OpenAI rates | — | Sora upstream deprecation makes this moot **[verify Azure's own timeline]** |

## 8. Cloud assembly (stitching) with free tiers

- **Shotstack**: 10 free credits valid 30 days; 1 credit = 1 minute of rendered video at
  any resolution, rounded down to the second; developer sandbox on all plans; 1080p max
  on PAYG/subscription; 3-hour render length; outputs are hosted, API-first.[28]
  After trial: PAYG $0.30/min ($75 one-time for 250 credits) or $39/month for 200.[28]
- **Creatomate**: 50 free API credits, no card; ~14 credits per minute of 720p video
  (so roughly 3.5 free minutes); rendered files hosted 30 days then deleted; API on all
  plans.[29]
- **Zero-cost fallback**: ffmpeg concat on any free-tier VM (Oracle/GCP e2-micro, or the
  Google Cloud trial itself). No provider limits, no watermark.

---

## Recommendation: long-form video from short clips, cloud-only, ~$0

**Primary generator: Google Cloud trial -> Vertex AI Veo 3.1 Fast (or Lite for drafts)**
- Why: the only official route where a frontier model with native audio is covered by a
  real budget ($300 / 90 days)[4][5]. Fast at $0.10/s gives ~50 min of raw 720p footage;
  Lite at $0.05/s gives ~100 min for rough cuts.[5]
- How: sign up for the Free Trial (card for verification only)[4], enable Vertex AI, call
  `veo-3.1-fast-generate-001` (GA on Vertex) or the preview IDs, 8-second clips, 16:9,
  `sampleCount=1` to avoid multiplying spend. Set a budget alert at $250.
- Caveats: 8 s per clip; extension is 720p-only and Gemini-API-side stores sources 2
  days[2]; trial resources stop the moment credit or 90 days expire[4]; Veo model IDs
  churn (Veo 2 gone 30 Jun 2026, Veo 3 deprecated)[2].

**Secondary free pool: Alibaba Model Studio Singapore -> Wan 2.7 / 2.6 / 2.2 t2v**
- 50 free seconds **per model ID**, 90 days, no watermark on API output[6][7][8]. Stack
  the dated snapshots and older models for several extra minutes at 720p–1080p, then
  flip on "Free Quota Only" so you cannot be billed.[6]

**Micro-tests / model comparison:** Replicate Try-for-Free (`minimax/video-01`)[9] and
HF's $0.10/month[11] — enough to validate prompts, not to produce.

**Assembly:** Shotstack free 10 minutes for a polished, API-driven timeline (transitions,
text, music)[28]; Creatomate's 50 credits for template-driven outputs[29]; ffmpeg on the
same GCP trial VM for anything longer.

**Workflow sketch**
1. Script -> shot list of N × 8 s beats (target 5–8 min => 40–60 keepers, budget 2–3
   attempts each).
2. Generate first frames with a cheap image model (Wan image models have 50–200 free
   images each[7]) and drive Veo/Wan image-to-video for continuity.
3. Store clips in GCS/OSS, run Shotstack (or ffmpeg) to concat, add narration/music
   (Veo has native audio; mute or keep per clip).
4. Export 1080p; upscale only keepers if needed.

**Do not build on:** OpenAI Sora 2 API (shutdown 24 Sept 2026)[22], Amazon Nova Reel
(EOL 30 Sept 2026)[26], Veo 2 (gone 30 Jun 2026)[2], fal "free credits" for API use
(playground-only)[13], or any third-party "cheap Sora/Veo key" service.

**Commercial-use summary:** Google — no ownership claim, business use permitted[3];
Alibaba — no restriction found, verify terms; Replicate/fal — per-model license[9][12];
Runway/Kling/Luma/Vidu API — commercial (paid); consumer free plans (Luma Dream Machine,
Hailuo app, Runway web free) are watermarked and/or non-commercial and are **not** API
access — third-party reporting, **[verify]**.

**Things most likely to have changed by the time you read this:** Google trial amount
and Veo preview-vs-GA IDs; Alibaba per-model free seconds (the doc notes a validity
change effective "September 8"[6]); BytePlus trial token amounts; HF $0.10 credit
("subject to change"[11]); Replicate's undisclosed free-run count; Kling trial-pack price.

## Sources

[1] https://ai.google.dev/gemini-api/docs/pricing — Gemini Developer API pricing
[2] https://ai.google.dev/gemini-api/docs/veo — Generate videos with Veo 3.1 in Gemini API
[3] https://ai.google.dev/gemini-api/terms — Gemini API Additional Terms of Service
[4] https://cloud.google.com/free/docs/free-cloud-features — Free Google Cloud features and trial offer
[5] https://cloud.google.com/vertex-ai/generative-ai/pricing — Google Cloud (Vertex AI / Agent Platform) generative AI pricing
[6] https://docs.modelstudio.console.alibabacloud.com/en/model-studio/new-free-quota — Alibaba Cloud Model Studio - Free quota for new users
[7] https://docs.modelstudio.console.alibabacloud.com/en/model-studio/model-pricing — Alibaba Cloud Model Studio - Model inference pricing
[8] https://docs.modelstudio.console.alibabacloud.com/en/model-studio/use-video-generation — Alibaba Cloud Model Studio - Video generation
[9] https://replicate.com/collections/try-for-free — Replicate - Try AI models for free
[10] https://replicate.com/alibaba/wan-3 — Replicate - Wan 3.0
[11] https://huggingface.co/docs/inference-providers/en/pricing — Hugging Face Inference Providers - Pricing and Billing
[12] https://fal.ai/docs/documentation/model-apis/faq — fal Model APIs FAQ
[13] https://fal.ai/docs/documentation/model-apis/sandbox — fal Sandbox
[14] https://docs.dev.runwayml.com/guides/pricing — Runway Dev - API Pricing & Costs
[15] https://docs.dev.runwayml.com/guides/setup — Runway Dev - API Setup & Configuration
[16] https://kling.ai/dev/pricing — Kling AI Developer Pricing
[17] https://platform.vidu.com — Vidu API platform
[18] https://platform.vidu.com/docs/pricing — Vidu API Pricing
[19] https://platform.minimax.io/docs/guides/pricing-paygo — MiniMax API - Pay as You Go pricing
[20] https://docs.byteplus.com/en/docs/ModelArk/1399514 — BytePlus ModelArk - Inference free trial
[21] https://docs.byteplus.com/en/docs/ModelArk/2191775 — BytePlus ModelArk - Seedance resource packs
[22] https://developers.openai.com/api/docs/guides/video-generation — OpenAI - Video generation with Sora
[23] https://developers.openai.com/api/docs/models/sora-2 — OpenAI - Sora 2 model page
[24] https://lumalabs.ai/api — Luma - Build with Luma APIs
[25] https://docs.aws.amazon.com/nova/latest/userguide/video-generation.html — Amazon Nova Reel - Generating videos
[26] https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-reel.html — Amazon Bedrock - Nova Reel model card
[27] https://azure.com/free — Azure free account
[28] https://shotstack.io/pricing — Shotstack pricing
[29] https://creatomate.com/pricing — Creatomate pricing
[30] https://ai.google.dev/gemini-api/docs/available-regions — Gemini API available regions
