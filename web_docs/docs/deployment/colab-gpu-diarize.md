---
title: GPU speakers on Colab
description: Run speech-to-text and speaker separation (WhisperX) on the owner's Colab GPU against the Databricks landing volume, and record what it used.
---

# GPU speakers on Colab

**What it's for:** the GPU step that turns a meeting recording into a transcript with speakers (WhisperX). It runs on
the owner's Google Colab, reading audio from the landing volume `/Volumes/open_navigator/open_navigator_landing/crawl`
([Databricks Free Edition](databricks-free-edition.md)) and writing `<name>.diarized.json` to
`crawl/diarized/<run_date>/` ([#297](https://github.com/getcommunityone/open-navigator/issues/297)).

Colab is where GPU runs go ([GPU compute decisions](../development/gpu-compute-decisions.md)). The
[Modal workflow](modal-gpu.md) still exists, but runs don't go there.

**A run uses the owner's Colab compute units.** It starts only on the owner's explicit yes for that run, the usage is
read before and after, and the cost goes in the run's issue or PR (`AGENTS.md`, "GPU and paid compute").

The logic is in the `llm.gpu.colab_diarize` module; the notebook
[`notebooks/colab_gpu_diarize.ipynb`](https://github.com/getcommunityone/open-navigator/blob/main/notebooks/colab_gpu_diarize.ipynb)
only installs it and calls it.

<details>
<summary><b>Open the notebook in Colab</b></summary>

Open
[colab.research.google.com/github/getcommunityone/open-navigator/blob/main/notebooks/colab_gpu_diarize.ipynb](https://colab.research.google.com/github/getcommunityone/open-navigator/blob/main/notebooks/colab_gpu_diarize.ipynb),
signed in with the owner's Google account (the one with the Colab subscription). Or in Colab: **File** → **Open
notebook** → **GitHub** → `getcommunityone/open-navigator` → `notebooks/colab_gpu_diarize.ipynb`.

The notebook clones the repository at `main` each session, so it always runs the merged code.
</details>

<details>
<summary><b>Choose a T4</b></summary>

**Runtime** → **Change runtime type** → **T4 GPU** → **Save**. The T4 is Colab's cheapest GPU, and WhisperX `small`
fits in its 16 GB. Cell 1 stops with a message if no GPU is attached. L4 or A100 cost more compute units an hour and
aren't needed for `small`.
</details>

<details>
<summary><b>Add the secrets</b></summary>

In Colab, the key icon in the left bar → **Add new secret**, and switch on **Notebook access** for each:

| Secret | What it is | Where it's made |
|---|---|---|
| `HF_TOKEN` | Hugging Face **read** token for the gated speaker models | huggingface.co → Settings → Access tokens, after accepting the conditions of [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) (see [GPU steps on Modal](modal-gpu.md) for the older models) |
| `DATABRICKS_HOST` | The Free Edition workspace URL, e.g. `https://dbc-xxxx.cloud.databricks.com` | the browser's address bar in the workspace |
| `DATABRICKS_TOKEN` | A personal access token, 30 days | workspace → profile → **Settings** → **Developer** → **Access tokens** |

The notebook prints only whether each secret is set, never its value, and the module redacts tokens from error
messages. Without the two Databricks secrets the notebook mounts Google Drive and reads and writes
`MyDrive/open-navigator/crawl/` instead (audio under `audio/`, results under `diarized/<run_date>/`).
</details>

<details>
<summary><b>Put the audio on the landing volume</b></summary>

YouTube blocks cloud IPs, Colab's included, so YouTube audio is fetched on the laptop and uploaded. If the laptop is
blocked too, see `packages/scrapers/src/scrapers/youtube/BYPASS_IP_BLOCK.md` (browser cookies).

1. On the laptop, download the audio, e.g.
   `yt-dlp -x --audio-format opus -o "%(upload_date)s_%(id)s.%(ext)s" <video URL>`, or the city's own scripts such as
   `download_tuscaloosa_city_meeting_audio.py --download-only --limit 3`.
2. Upload it under `audio/` in the volume, either in the workspace (**Catalog** → `open_navigator` →
   `open_navigator_landing` → `crawl` → **Upload to this volume**) or with the Databricks CLI:
   `databricks fs cp <file> dbfs:/Volumes/open_navigator/open_navigator_landing/crawl/audio/<file>`.

A city's own archive file can be given straight to the notebook as a URL (a direct media link, or the meeting page
when it links its video); those don't need uploading.
</details>

<details>
<summary><b>Run a batch</b></summary>

Run cells 1 to 4 in order: GPU check, install, secrets, usage before. In cell 4, type the compute-unit balance and the
rate Colab's **Resources** panel shows (RAM/Disk at the top right → **View resources**).

Cell 5 runs the batch. Its form fields:

- **items:** comma-separated landing-volume paths such as `crawl/audio/20170913_essex-trustees.opus`, or media URLs;
- **limit:** at most this many items (default 3);
- **model_size:** `small` by default;
- **run_date:** blank for today (UTC);
- **owner_said_yes_to_this_run:** the cell stops unless it's ticked.

Each finished item is written before the next starts. If Colab disconnects, run cells 1 to 3 again and then cell 5
with the same items and run date. Items already in `crawl/diarized/<run_date>/` are skipped.

From a terminal with a GPU, the same thing is `python -m llm.gpu.colab_diarize --items crawl/audio/<file> --limit 3`.
Add `--dry-run` to see what would run and what would be skipped, without a GPU.
</details>

<details>
<summary><b>What comes back</b></summary>

In `crawl/diarized/<run_date>/`:

- `<name>.diarized.json` per item: segments with start, end, speaker and text (`diarize_audio_whisperx`'s output);
- `usage.jsonl`: one row per item in the same shape as the Modal rows (`platform_name` `colab`), with the GPU,
  measured seconds, GPU-hours, status, and `compute_units` with `compute_units_source`. The run's measured CU is one
  more row, `row_kind` `batch_measured_cu`;
- `llm_usage/gpu_runs_*.jsonl`: the `llm.usage` `gpu_run` rows for the session (utilization, peak memory).

Cell 5 prints a table per item: segments, speakers, speaking time, GPU seconds and CU.
</details>

<details>
<summary><b>Record the cost</b></summary>

Colab has no API for compute units, so the module can't measure them itself:

- **Per item (an estimate):** GPU seconds × the CU-per-hour rate. Without a rate typed in cell 4, the documented rate
  is used: T4 1.76, L4 4.82, A100 11.77 CU an hour. Colab users report these figures; Colab publishes no table. Each
  row's `compute_units_source` says which rate was used and that it is an estimate. `estimated_cost_usd` prices those
  units at Colab's pay-as-you-go rate, US$9.99 for 100.
- **Per batch (measured):** the balance before (cell 4) minus the balance after (cell 6), from the Resources panel.
  Cell 6 writes it to `usage.jsonl` and prints a "usage after" line.

Paste the "usage before" and "usage after" lines and the summary table into the run's issue or PR.
</details>

<details>
<summary><b>How long a batch takes</b></summary>

So far there is one measured run, and it ran **on a Modal T4, not Colab**.
The Essex Junction Trustees meeting of 2017-09-13 used about **401 seconds of GPU** for about **81 minutes of
audio**, and gave 981 segments and 12 speakers. That's about 0.11 GPU-hours per 81-minute meeting, so a batch of three
such meetings should take about a third of a GPU-hour. At the documented T4 rate that's an estimated 0.2 CU per
meeting.

Colab adds model downloads at the start of each session, and its T4 may differ from Modal's. The first Colab run gives
the first Colab measurement; add it here.
</details>
