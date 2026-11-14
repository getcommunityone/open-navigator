---
title: GPU steps on Modal
description: Run speech-to-text and speaker separation on a Modal GPU from GitHub, within Modal's free monthly credit.
---

# GPU steps on Modal

**What it's for:** the GPU step that turns a meeting recording into a transcript with speakers (WhisperX), without a
local GPU. It runs on Modal, a serverless GPU service whose free Starter plan includes a monthly compute credit, and
starts from GitHub Actions, so it can be run from a phone
([#314](https://github.com/getcommunityone/open-navigator/issues/314)). Colab (#297) stays the hands-on option.

<details>
<summary><b>Set it up from a phone (about 10 minutes)</b></summary>

1. **Modal account:** sign up at [modal.com](https://modal.com). The free Starter plan gives a monthly credit (larger
   with a payment method on file). Without a card, work stops when the credit runs out, which caps spending at zero.
   With a card, use past the credit is billed, so watch the dashboard or keep runs small.
2. **Modal token:** modal.com → **Settings** → **API tokens** → **New token**. Copy the token ID and secret.
3. **GitHub secrets:** repository **Settings** → **Secrets and variables** → **Actions** → add `MODAL_TOKEN_ID` and
   `MODAL_TOKEN_SECRET`. Never paste them anywhere else.
4. **Hugging Face token for the speaker models:** on huggingface.co, accept the terms of
   `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`, then make a **read** token (Settings → Access
   tokens). In Modal → **Secrets** → **Create** → custom, name it `huggingface`, key `HF_TOKEN`.
5. **Run it:** GitHub → **Actions** → **GPU diarization on Modal** → **Run workflow**, with the items to process.
</details>

<details>
<summary><b>What to give it</b></summary>

- A path in the Modal volume `open-navigator-audio`, e.g. `meetings/2026-11-03.opus`. Put files there from a laptop:
  `modal volume put open-navigator-audio <file> meetings/<file>`.
- Or a direct link to a media file a city publishes (not YouTube: YouTube blocks cloud servers, see
  `packages/scrapers/src/scrapers/youtube/BYPASS_IP_BLOCK.md`).

Each run takes at most `limit` items (default 3), so one run can't use the month's credit.
</details>

<details>
<summary><b>What comes back, and what it costs</b></summary>

The run's artifact holds `<name>.diarized.json` per item (segments with start, end, speaker and text) and
`usage.jsonl`: one row per item with the GPU, seconds, GPU-hours and an **estimated** cost. The estimate is GPU time at
Modal's published rate (T4 $0.000164 a second, as reported on 2026-11-14); CPU and memory are billed on top, so the
invoice is a little higher. Modal's dashboard shows the real spend.

Not run yet: the first real run checks that the pinned WhisperX version still exposes the diarization pipeline the
code calls (`llm.gemini.diarize_postprocess`).
</details>

<details>
<summary><b>Credentials</b></summary>

| Credential | Where it's made | Scope | Goes to | Lifetime |
|---|---|---|---|---|
| Modal API token | modal.com → Settings → API tokens | the Modal workspace | GitHub secrets `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | until revoked; revoke if unused |
| Hugging Face read token | huggingface.co → Settings → Access tokens | read, gated models accepted | Modal secret `huggingface`, key `HF_TOKEN` | 90 days |
</details>
