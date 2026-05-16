# Governance pipeline (Google Colab + Drive)

Use this when you **do not** have a high-end local GPU: heavy work runs in Colab or remote APIs; artifacts live on **Google Drive** so WSL and Colab see the same folders after sync.

**Colab vs local (notebooks):** [`colab_paths.py`](colab_paths.py) — `maybe_mount_google_drive()` (no-op locally), `setup_notebook_paths()` (Colab: pipeline data under `…/CommunityOne/governance_pipeline_data` next to your Drive clone; local: `<repo>/data/governance_pipeline_data` unless **`GOVERNANCE_PIPELINE_DATA_ROOT`** is set). Set **`OPEN_NAVIGATOR_ROOT`** if Jupyter’s cwd is not inside the repo.

Pipeline folder layout under that root: [`scripts/utils/gdrive_paths.py`](../utils/gdrive_paths.py) (`GovernancePipelinePaths`). Drive mount defaults for WSL are documented next to [`scripts/utils/log_sync.py`](../utils/log_sync.py).

## Notebooks & scripts (this folder)

| Step | Notebook / script | Verb | What it does |
|---|------|------|----------------|
| 1 | [`01_copy_scraped_meetings_cache_to_gdrive.py`](01_copy_scraped_meetings_cache_to_gdrive.py) | **Sync** | WSL / Linux: by default copies **only** four inventory folders under ``data/cache/scraped_meetings`` (Tuscaloosa county/city + Big Timber county/city) → ``My Drive/CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs``. Use ``--all-cache`` for the full tree. |
| 2 | [`01_init_drive_layout.ipynb`](01_init_drive_layout.ipynb) | **Init** | Create `01_raw_inputs`, `02_reference_data/orbis_files`, `03_processed_outputs/…` → zone README stubs. **Colab or local** via `colab_paths.py`. |
| 3 | [`02_run_meeting_llm.ipynb`](02_run_meeting_llm.ipynb) | **Run** | Load `prompts/policy_analysis.md` + transcript → remote LLM → JSON / summaries. **Colab or local**; API key from Colab Secrets or env `TOGETHER_API_KEY`. |

Legacy notebook names (old Colab links): [`02_init_drive_layout.ipynb`](02_init_drive_layout.ipynb) matches **step 2** but use **`01_init_…`** for new work; [`03_run_meeting_llm.ipynb`](03_run_meeting_llm.ipynb) matches **step 3** but prefer **`02_run_…`**.

Python helper (not a notebook): [`governance_meeting_llm.py`](governance_meeting_llm.py) — parsing, chunking, Orbis merge (imported by **`02_run_meeting_llm.ipynb`**).

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

### 5) Run Gemma / LLM structured analysis — notebook **`02_run_meeting_llm.ipynb`**

1. Open [`02_run_meeting_llm.ipynb`](02_run_meeting_llm.ipynb) (or the legacy [`03_run_meeting_llm.ipynb`](03_run_meeting_llm.ipynb) alias).
2. **Bootstrap** — First code cells: repo discovery (`OPEN_NAVIGATOR_ROOT` or walk parents for `scripts/colab/colab_paths.py`), optional Drive mount in Colab only, `PATHS = setup_notebook_paths()`, then git + `GOVERNANCE_PIPELINE_DATA_ROOT` + imports (same pattern as **`01_init_drive_layout.ipynb`**).
3. **`%pip install`** cell (OpenAI-compatible client).
4. **Secrets / API** — Colab Secrets or `TOGETHER_API_KEY` in the environment; adjust `BASE_URL` / `MODEL` if not using Together + Gemma 2 27B.
5. **Transcript + chunk** cell — confirms input and chunk count.
6. **Run model** cell — writes per chunk:
   - **`03_processed_outputs/02_gemma_json/`** — `.json`, `.raw.txt`, `.extra.md`
   - **`03_processed_outputs/03_human_summaries/`** — `.summary.md`
7. **Optional — Orbis** cell — expects **`02_reference_data/orbis_files/orbis_lookup_by_org_id.json`** (keys = `org_id` from the model). Writes enriched JSON back under `02_gemma_json/`.
8. **Optional — Gemini** cell — commented example at the bottom.

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
| [`governance_meeting_llm.py`](governance_meeting_llm.py) | Helpers for **`02_run_meeting_llm.ipynb`** (parse `---DOCUMENT_BREAK---`, chunk text, Orbis merge). |
| [`colab_paths.py`](colab_paths.py) | `in_colab`, `maybe_mount_google_drive`, `setup_notebook_paths` for init/run notebooks. |

---

## Environment variables (quick reference)

| Variable | Meaning |
|----------|---------|
| `OPEN_NAVIGATOR_ROOT` | Absolute path to the `open-navigator` checkout when Jupyter cwd is not inside the repo (local + Colab). |
| `GOVERNANCE_PIPELINE_DATA_ROOT` | Absolute path to pipeline root (recommended on Colab; optional locally — default is `data/governance_pipeline_data` in the repo). |
| `GOVERNANCE_PIPELINE_GDRIVE_BASE` | Path under `LOG_GDRIVE_MOUNT` when `DATA_ROOT` is not set (default `CommunityOne/governance_pipeline_data`). |
| `LOG_GDRIVE_MOUNT` | Mounted Drive root (default `/mnt/g/My Drive`). |
| `SCRAPED_MEETINGS_ROOT` | Local scraped meetings root when not using default `data/cache/scraped_meetings` (used by **01** / sync util default `--src-root`). |
| `SCRAPED_MEETINGS_GDRIVE_MIRROR` | Absolute path to the Drive **mirror root** for scraped meetings (default: `<mount>/CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs`). |
