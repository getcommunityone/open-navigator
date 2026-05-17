# Governance pipeline (Google Colab + Drive)

Use this when you **do not** have a high-end local GPU: heavy work runs in Colab or remote APIs; artifacts live on **Google Drive** so WSL and Colab see the same folders after sync.

**Colab vs local (notebooks):** [`colab_paths.py`](colab_paths.py) — `maybe_mount_google_drive()` (no-op locally), `setup_notebook_paths()` (Colab: pipeline data under `…/CommunityOne/governance_pipeline_data` next to your Drive clone; local: `<repo>/data/governance_pipeline_data` unless **`GOVERNANCE_PIPELINE_DATA_ROOT`** is set). Set **`OPEN_NAVIGATOR_ROOT`** if Jupyter’s cwd is not inside the repo.

Pipeline folder layout under that root: [`scripts/utils/gdrive_paths.py`](../utils/gdrive_paths.py) (`GovernancePipelinePaths`). Drive mount defaults for WSL are documented next to [`scripts/utils/log_sync.py`](../utils/log_sync.py).

## Notebooks & scripts (this folder)

| Step | Notebook / script | Verb | What it does |
|---|------|------|----------------|
| 1 | [`01_copy_scraped_meetings_cache_to_gdrive.py`](01_copy_scraped_meetings_cache_to_gdrive.py) | **Sync** | WSL / Linux: by default copies **only** four inventory folders under ``data/cache/scraped_meetings`` (Tuscaloosa county/city + Big Timber county/city) → ``My Drive/CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs``. Use ``--all-cache`` for the full tree. |
| 2 | [`01_init_drive_layout.ipynb`](01_init_drive_layout.ipynb) | **Init** | Create `01_raw_inputs`, `02_reference_data/orbis_files`, `03_processed_outputs/…` → zone README stubs. **Colab or local** via `colab_paths.py`. |
| 3 | [`gatekeeper_triage.py`](gatekeeper_triage.py) | **Triage** | Walks `01_raw_inputs/` with `os.walk`, sends each PDF / audio to Gemma 4 for a strict-JSON verdict. Rejects stay in place by default (optional `excluded_inputs/` move). Runs standalone as a CLI or as **Demo step 0** inside the run notebook. |
| 4 | [`02_run_meeting_llm.ipynb`](02_run_meeting_llm.ipynb) | **Run** | Five labeled Gemma 4 demo cells over every PDF / audio / contact image discovered under `01_raw_inputs`, mirroring outputs to `03_processed_outputs/02_gemma_json/<STATE>/<scope>/<jurisdiction>/…`. **Colab or local**; API key from Colab Secrets or env `GEMINI_API_KEY` / `GOOGLE_API_KEY`. |

Legacy notebook names (old Colab links): [`02_init_drive_layout.ipynb`](02_init_drive_layout.ipynb) matches step **2** but use **`01_init_…`** for new work; [`03_run_meeting_llm.ipynb`](03_run_meeting_llm.ipynb) matches step **4** but prefer **`02_run_…`** — both are kept in sync by the builder so old Colab bookmarks still work.

Python helper (not a notebook): [`governance_meeting_llm.py`](governance_meeting_llm.py) — tree walker (`walk_raw_inputs`, `mirror_output_path`, `JurisdictionDir.jurisdiction_id`), multimodal Gemma client wrapper (`call_google_genai_multimodal` with `media_resolution` + `thinking_config`), PDF page rendering + token-budget classifier, audio chunking via `ffmpeg`, policy drift detector, Orbis merge by `jurisdiction_id`. Imported by **`02_run_meeting_llm.ipynb`** and (selectively) by `gatekeeper_triage.py`.

---

## Prerequisites

1. **Repo for Colab** — Use **GitHub** (Colab “Open from GitHub”) or clone under Drive if you prefer. **Local Jupyter:** open the repo checkout and start the kernel with cwd at the repo root, or set **`OPEN_NAVIGATOR_ROOT`** so the bootstrap cell finds `scripts/colab/colab_paths.py`.
2. **Scraped meetings on Drive (optional)** — Run **01** from WSL to mirror the **default four inventory** folders under ``data/cache/scraped_meetings`` → ``My Drive/CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs`` (use ``--all-cache`` only if you need the entire cache).
3. **Pipeline root** — Default on Colab:  
   `My Drive/CommunityOne/governance_pipeline_data`  
   Override with env **`GOVERNANCE_PIPELINE_DATA_ROOT`** (absolute path) if you want a different root.
4. **WSL + Google Drive Desktop (optional)** — Same relative path appears under your mount, e.g.  
   `/mnt/g/My Drive/CommunityOne/...`  
   Set **`LOG_GDRIVE_MOUNT`** if your mount is not `/mnt/g/My Drive`.
5. **API keys** — Colab: **Secrets** (key icon). Local: export **`TOGETHER_API_KEY`** (or another provider key) in the environment. The run notebook tries Colab `userdata` first, then `os.environ`.

Folder semantics for `01_raw_inputs`, `02_reference_data`, `03_processed_outputs` are summarized in [`scripts/doc_processing/readme.md`](../doc_processing/readme.md).

---

## What to run (order)

### 1) Mirror scraped meetings cache → Drive (optional)

| Where | What to run |
|--------|-------------|
| **WSL / Linux** | From repo root: `python scripts/colab/01_copy_scraped_meetings_cache_to_gdrive.py --dry-run` then without `--dry-run`. **Default:** only the four Tuscaloosa/Big Timber inventory paths. Pass `--all-cache` to sync the whole `scraped_meetings` tree. If Drive is not visible under WSL but **rclone** is configured (`gdrive:` remote), the script falls back to rclone automatically. Use `--rclone` to force, or `--local` to stage under `data/export/` in the repo. |

Skip if you only use local cache or another sync path.

---

### 2) Create the directory tree (pick one)

| Where | What to run |
|--------|-------------|
| **Google Colab** | Open [`01_init_drive_layout.ipynb`](01_init_drive_layout.ipynb) → **Run all**. Mounts Drive (in Colab only), sets paths via `colab_paths.py`, imports `GovernancePipelinePaths`, creates folders, writes zone READMEs. |
| **Local / WSL** | From repo root: open **`01_init_drive_layout.ipynb`** in Jupyter (same cells as Colab; Drive mount is skipped), **or** run `python scripts/utils/ensure_governance_pipeline_drive_layout.py` with **`GOVERNANCE_PIPELINE_DATA_ROOT`** set if needed. |

If the WSL script errors (no `/mnt/g` or permission denied), mount Drive or set **`GOVERNANCE_PIPELINE_DATA_ROOT`** to a writable directory first.

You only need to repeat this when you create a new Drive account or change the pipeline root path.

---

### 3) Ingest raw files (manual)

- Put videos and PDFs under **`01_raw_inputs/<jurisdiction_slug>/<body_slug>/`** (keep **city** and **county** separate).
- Rename with strict slugs, e.g. `tuscaloosa_city_council_2026-03-15_regular_session.mp4` (see zone README under `01_raw_inputs` after step 2).
- Put Orbis (or other registry) CSVs/spreadsheets under **`02_reference_data/orbis_files/`** only.

No notebook required for this step.

---

### 4) Build transcripts (your choice of tool)

- Run **Whisper** (video → text) and/or **Marker** (PDF → Markdown) locally, on Colab, or elsewhere.
- Save outputs into **`03_processed_outputs/01_transcripts/`** on Drive.

For the run notebook’s default input, add **`transcript.txt`** in that folder, **or** in Colab upload **`/content/transcript.txt`**, **or** locally put **`transcript.txt`** in the Jupyter cwd (notebook tries the pipeline transcripts folder first, then Colab `/content`, then cwd).

---

### 5) Gatekeeper Triage — standalone CLI (optional but recommended)

Run **before** the demo notebook to drop non-meeting files out of the queue:

```bash
# dry-run audit first
python scripts/colab/gatekeeper_triage.py --dry-run --max-files 20 --verbose

# real sweep, writes JSON report
python scripts/colab/gatekeeper_triage.py --report-path /tmp/triage_report.json
```

The triage layer:
- Walks `01_raw_inputs/<STATE>/<scope>/<jurisdiction>/...` with `os.walk`.
- Visual PDF gate: first **1–2 pages** rendered with `pdf2image` at 200 DPI, sent to Gemma 4 at HIGH `media_resolution` (~1,120 image tokens) to decide `meeting_agenda` / `meeting_minutes` / `other`.
- Multimodal audio gate: first **120 seconds** (`--audio-window-seconds`) clipped via `ffmpeg`, sent to Gemma 4 to listen for gavel / roll call / motion-vote cadence / public-comment turns.
- Strict-JSON output: `{is_governance_meeting, document_or_audio_type, confidence_score, reasoning}` (uses `response_schema` when the SDK supports it).
- **Rejects (default):** failed triage is logged in the JSON report; files stay in `01_raw_inputs/`. Set `GOVERNANCE_GATEKEEPER_MOVE_EXCLUDED=1` to move rejects under `excluded_inputs/` (legacy).
- **Robust:** every API call, ffmpeg clip, pdf2image render, and `shutil.move` is wrapped in `try/except`; a single bad file never aborts a batch sweep. Each line logs `KEEP | <STATE>/<scope>/<jurisdiction>/... | <file> | type=... conf=...` so the geographic origin is always visible.

The same triage layer is exposed as **Step 0** inside `02_run_meeting_llm.ipynb`; set `GOVERNANCE_GATEKEEPER_ENABLED=0` to skip when running the notebook end-to-end.

With `GOVERNANCE_ORGANIZE_MEETINGS=1` (default), kept/scoped files move under  
`…/meetings/YYYY_MM_DD/{instance_slug}/` (e.g. `2026_04_01/city-council/`) with  
`agenda/`, `minutes/`, `collateral/`, and `audio/` subfolders. Demo 4 builds a text brief from agenda+minutes PDFs (names, topics, title) and prepends it to the audio policy prompt.

### 6) Run Gemma / LLM structured analysis — notebook **`02_run_meeting_llm.ipynb`**

1. Open [`02_run_meeting_llm.ipynb`](02_run_meeting_llm.ipynb) (or the legacy [`03_run_meeting_llm.ipynb`](03_run_meeting_llm.ipynb) alias).
2. **Bootstrap** — repo discovery (`OPEN_NAVIGATOR_ROOT` or walk parents for `scripts/colab/colab_paths.py`), optional Drive mount in Colab only, `PATHS = setup_notebook_paths()`, then git + `GOVERNANCE_PIPELINE_DATA_ROOT` + imports (same pattern as **`01_init_drive_layout.ipynb`**).
3. **`%pip install`** cell — `google-genai`, **`transformers>=5.5.0`** (Gemma 4 / `gemma4` on HF), `accelerate`, `pymupdf`, `pdf2image` (+ `poppler-utils` on Colab). **Restart runtime** after install.
4. **Secrets / API + caps** — Colab Secret `GEMINI_API_KEY` or env `GEMINI_API_KEY` / `GOOGLE_API_KEY`. Adjust `GOVERNANCE_GENAI_MODEL` if your AI Studio project lists a different Gemma 4 id. Demo caps in env: `GOVERNANCE_DEMO_MAX_PDFS_PER_JUR` (3), `GOVERNANCE_DEMO_MAX_PAGES_PER_PDF` (8), `GOVERNANCE_DEMO_MAX_AUDIO_PER_JUR` (1), `GOVERNANCE_DEMO_MAX_AUDIO_CHUNKS` (4), `GOVERNANCE_DEMO_MAX_IMAGES_PER_JUR` (12), `GOVERNANCE_DEMO_THINKING_BUDGET` (-1).
5. **Step 0 — Gatekeeper** cell — runs `gatekeeper_triage.run_triage()` on the raw root. Skip with `GOVERNANCE_GATEKEEPER_ENABLED=0`; audit with `GOVERNANCE_GATEKEEPER_DRY_RUN=1`.
6. **Walker** cell — `walk_raw_inputs(RAW_ROOT)` yields one `MeetingInventory` per `<STATE>/<scope>/<jurisdiction>` with PDFs, audio, and images. Prints the inventory and stores it in `INVENTORIES`.
7. **Demo 1 — Native multimodality / visual document parsing.** For every PDF: probe digital-text layer with PyMuPDF, flag <200 chars as **scanned (dark data)**, then send to Gemma 4 for visual OCR. Output: `…/<mirrored>/<pdf>.visual_ocr.txt`.
8. **Demo 2 — Adjustable visual token budget.** Render every PDF page to PNG, classify each (`scanned` / `financial_or_tabular` / `text_heavy`), route financial + scanned pages at **HIGH** (~1,120 image tokens), text-heavy pages at **LOW** (~64 tokens). One JSON per page + per-PDF `_token_budget_report.json`.
9. **Demo 3 — Built-in thinking mode.** Pick a representative PDF per jurisdiction (priority for `demolition`/`minutes`/`council`/etc. filenames) and run `prompts/policy_analysis_v1.md` with `include_thoughts=True` and `thinking_budget=-1`. Writes `.thinking.json`, `.thinking.raw.txt`, `.thinking.thoughts.md`, `.thinking.summary.md`.
10. **Demo 4 — Long-meeting chunking + Policy Drift Detector.** `ffmpeg`-split each audio into 15-minute chunks, run `policy_analysis_v1.md` per chunk, then run `policy_drift_summarize()` over the assembled chunk JSONs. Output: `…/<audio_stem>/chunk_<n>.json` + `policy_drift.json` + Mermaid `policy_drift.mmd`.
11. **Demo 5 — Contact image enrichment.** For every image discovered (typically under `_contact_images/`): if it's a person, return perceived `age_range`, `race`, `gender`, `ethnicity`, `demeanor` (nullable, with confidence); otherwise return a brief `subject_tag`. Cap via `GOVERNANCE_DEMO_MAX_IMAGES_PER_JUR`.
12. **Optional — Orbis enrichment.** Attaches the matching `02_reference_data/orbis_files/orbis_lookup_by_jurisdiction_id.json` row to every generated JSON, keyed by `jurisdiction_id` derived from the output's mirrored path. Legacy `orbis_lookup_by_org_id.json` is also merged for backwards compatibility.

---

### 6) Optional — other Drive sync in this repo

These use the same **`CommunityOne/`** style paths under your Drive mount but **different** subfolders:

| Script | Purpose |
|--------|---------|
| [`scripts/utils/log_sync.py`](../utils/log_sync.py) | Copies run logs → `CommunityOne/open-navigator-logs/...` |

Scraped meetings mirror is **step 1** above ([`01_copy_scraped_meetings_cache_to_gdrive.py`](01_copy_scraped_meetings_cache_to_gdrive.py)); it is not a separate util under `scripts/utils/`.

## Other files in this folder

| File | Purpose |
|------|---------|
| [`governance_meeting_llm.py`](governance_meeting_llm.py) | Tree walker (`walk_raw_inputs`, `JurisdictionDir.jurisdiction_id`, `mirror_output_path`), Gemma client wrapper with `media_resolution` + `thinking_config`, PDF page rendering + per-page token-budget classifier, `ffmpeg` audio chunking, policy drift detector, Orbis merge by `jurisdiction_id`, `---DOCUMENT_BREAK---` parser. Imported by **`02_run_meeting_llm.ipynb`**. |
| [`gatekeeper_triage.py`](gatekeeper_triage.py) | "Ledger of Influence" data gate. `os.walk` over `01_raw_inputs/`, multimodal Gemma triage on every PDF (first 1–2 pages) and audio (first 120 s via `ffmpeg`). Rejects stay in place unless `GOVERNANCE_GATEKEEPER_MOVE_EXCLUDED=1`. Standalone CLI or imported by the run notebook as Step 0. |
| [`colab_paths.py`](colab_paths.py) | `in_colab`, `maybe_mount_google_drive`, `setup_notebook_paths` for init/run notebooks. |

---

## Environment variables (quick reference)

| Variable | Meaning |
|----------|---------|
| `OPEN_NAVIGATOR_ROOT` | Absolute path to the `open-navigator` checkout when Jupyter cwd is not inside the repo (local + Colab). |
| `GOVERNANCE_PIPELINE_DATA_ROOT` | Absolute path to pipeline root (recommended on Colab; optional locally — default is `data/governance_pipeline_data` in the repo). |
| `GOVERNANCE_PIPELINE_GDRIVE_BASE` | Path under `LOG_GDRIVE_MOUNT` when `DATA_ROOT` is not set (default `CommunityOne/governance_pipeline_data`). |
| `GOVERNANCE_RAW_INPUTS_ROOT` | Override the `01_raw_inputs/` location for the run notebook + Gatekeeper. |
| `GOVERNANCE_LLM_BACKEND` | Default `google` (hybrid). Set `huggingface` to force all calls local. |
| `GOVERNANCE_GENAI_MODEL` | Demos 1–5 on **AI Studio** (default `gemma-4-26b-a4b-it`). |
| `GOVERNANCE_GATEKEEPER_MODEL` | Gatekeeper on **AI Studio** (default `gemma-3n-e2b-it`). |
| `GOVERNANCE_GATEKEEPER_FORCE_HF` | Set `1` to load [google/gemma-4-E2B](https://huggingface.co/google/gemma-4-E2B) locally (~10GB; needs `HF_TOKEN` + `transformers>=5.5.0`). |
| `GOVERNANCE_HF_ONLY_MODELS` | Optional comma-separated demo model ids to route to HF. |
| `GOVERNANCE_GATEKEEPER_API_TIMEOUT_SECONDS` | Per-file Gemma triage timeout (default `120`). |
| `GOVERNANCE_GATEKEEPER_SOCKET_ALARM` | `1` (default on Linux/Colab): `SIGALRM` aborts frozen HTTP sockets (`timeout` + buffer). `0` to disable. |
| `GOVERNANCE_GATEKEEPER_SOCKET_ALARM_BUFFER_SECONDS` | Added to API timeout for wall clock (default `30` → 150s when timeout is 120). |
| `GOVERNANCE_GATEKEEPER_ENABLED` | `0` to skip the triage step inside the notebook. |
| `GOVERNANCE_GATEKEEPER_DRY_RUN` | `1` to log triage verdicts without moving files. |
| `GOVERNANCE_GATEKEEPER_MOVE_EXCLUDED` | `1` to create `excluded_inputs/` and move rejects (default `0` — leave files in place). |
| `GOVERNANCE_MEETING_AI_IDENTITY` | `1` (default): same-day clustering via AI (PDF pages 1–2 + audio triage); ≤1 agenda + ≤1 minutes → one meeting. |
| `GOVERNANCE_MEETING_IDENTITY_TIMEOUT_SECONDS` | Per jurisdiction-day identity call (default `90`). |
| `GOVERNANCE_GATEKEEPER_KINDS` | Comma-separated kinds — `pdf`, `audio`, or both (default both). |
| `GOVERNANCE_GATEKEEPER_PDF_PAGES` | First **1–2** pages sent as PDF bytes to the model (default `2`). |
| `GOVERNANCE_GATEKEEPER_PDF_DIRECT` | `1` (default): AI Studio gets `application/pdf` subset — no PNG render. `0` = text-only. |
| `GOVERNANCE_GATEKEEPER_COPY_TO_TMP` | Copy Drive PDFs to `/tmp` before read (default `1`). |
| `GOVERNANCE_GATEKEEPER_TEXT_FIRST` | Include digital text from pages 1–N in the prompt (default `1`). |
| `GOVERNANCE_GATEKEEPER_LARGE_PDF_BYTES` | Files ≥ this size triage page 1 only (default `1500000`). |
| `GOVERNANCE_GATEKEEPER_AUDIO_WINDOW` | Seconds of audio sent to triage (default `120`). |
| `GOVERNANCE_GATEKEEPER_CONFIDENCE` | Minimum confidence to keep a file (default `0.6`). |
| `GOVERNANCE_DEMO_YEAR_SCOPE` | In DEMO mode, only descend into each jurisdiction's **newest** `20xx/` folder (default **on**). Skips older year trees during Gatekeeper walk. |
| `GOVERNANCE_DEMO_MEETING_DATES` | After year filter, keep only the last **N** meeting **dates** per jurisdiction (default **3**): pdfs, collateral, and audio with an inferred `YYYY-MM-DD`. |
| `GOVERNANCE_DEMO_DATE_SCOPE` | Set `0` to disable date scope and fall back to count caps. |
| `GOVERNANCE_GATEKEEPER_MAX_FILES` | Legacy count cap (newest N by mtime) when date scope is off. |
| `GOVERNANCE_DEMO_MAX_PDFS_PER_JUR` | PDFs processed per jurisdiction in Demo 1 + 2 (default `3`). |
| `GOVERNANCE_DEMO_MAX_PAGES_PER_PDF` | Pages processed per PDF in Demo 2 (default `8`). |
| `GOVERNANCE_DEMO_MAX_AUDIO_PER_JUR` | Audio files processed per jurisdiction in Demo 4 (default `1`). |
| `GOVERNANCE_DEMO_MAX_AUDIO_CHUNKS` | 15-minute audio chunks processed per file in Demo 4 (default `4`). |
| `GOVERNANCE_DEMO_MAX_IMAGES_PER_JUR` | Images processed per jurisdiction in Demo 5 (default `12`). |
| `GOVERNANCE_DEMO_THINKING_BUDGET` | Thinking-token budget for Demo 3 (`-1` = unlimited). |
| `GOVERNANCE_DRIFT_FOCUS` | Optional subject string to bias the policy drift detector. |
| `LOG_GDRIVE_MOUNT` | Mounted Drive root (default `/mnt/g/My Drive`). |
| `SCRAPED_MEETINGS_ROOT` | Local scraped meetings root when not using default `data/cache/scraped_meetings` (used by **01** / sync util default `--src-root`). |
| `SCRAPED_MEETINGS_GDRIVE_MIRROR` | Absolute path to the Drive **mirror root** for scraped meetings (default: `<mount>/CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs`). |
