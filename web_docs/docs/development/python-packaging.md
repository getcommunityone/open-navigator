---
title: Python Packaging Map
description: Which dependency manifest to use — the canonical uv workspace vs the runtime requirements.txt vs the optional environment-specific requirements-*.txt extras.
---

# Python Packaging Map

The repo carries several dependency manifests for historical and
environment-specific reasons. They are **not interchangeable** — this page is the
authoritative map of what each one is for. If you are onboarding, read the
[**Canonical path**](#canonical-path) first; everything else is an opt-in extra.

## Canonical path

- **`pyproject.toml` + `uv.lock` — the source of truth for the `packages/*` workspace.**
  This is a [uv](https://docs.astral.sh/uv/) workspace (`[tool.uv.workspace] members =
  ["packages/*"]`). The root `pyproject.toml` is *virtual* (not itself buildable). Install
  the workspace with:

  ```bash
  uv sync
  ```

  New Python belongs in `packages/` as a proper library — see `CLAUDE.md` and the
  [Cleanup Roadmap](./cleanup-roadmap.md).

- **`requirements.txt` — the application runtime dependency set.** This is what the
  Docker images, CI (`ci-build-test.yml`), and the `install.sh` / `install.ps1`
  bootstrap scripts install for the FastAPI app + ingestion/scraping runtime. It predates
  the uv workspace and still backs the deploy/runtime paths, so **it is load-bearing —
  do not delete or rename it** without rewiring those consumers (Dockerfile,
  Dockerfile.huggingface, CI, install scripts, deployment docs).

## Optional / environment-specific extras

Each `requirements-*.txt` is a deliberately-separate, self-documented extra (see the
header comment in each file). Install **on top of** the base only when you need that
workflow:

| File | Purpose | Install |
|---|---|---|
| `requirements-dbt.txt` | dbt-postgres for the dbt project. Pulls protobuf 6.x / pathspec that **conflict** with the main `.venv`, so it lives in a **separate** `.venv-dbt`. | `./packages/scrapers/scripts/openstates_setup_dbt_venv.sh` |
| `requirements-gemini-api.txt` | `google-genai` for transcript policy analysis (`meeting_transcript_policy.py`). | `pip install -r requirements-gemini-api.txt` |
| `requirements-transcript-diarize.txt` | Optional WhisperX speaker diarization (`--diarize`); pins `numpy<2`; needs `HF_TOKEN`. | `.venv/bin/pip install -r requirements-transcript-diarize.txt` |
| `requirements-spark.txt` | Spark / Delta Lake (~300 MB, needs a JDK). Only the discovery batch workflows use it. | `pip install -r requirements-spark.txt` |
| `requirements-ollama-scraping.txt` | Local Ollama + LangChain structured scraping. | `.venv/bin/pip install -r requirements.txt -r requirements-ollama-scraping.txt` |
| `requirements-cpu.txt` | CPU-only variant of the runtime (no CUDA), used by `Dockerfile.app` + the databricks/local install scripts. | `pip install -r requirements-cpu.txt` |
| `requirements-intel.txt` | Intel Arc / NPU-optimized ML stack (`intel-extension-for-pytorch`). | `pip install -r requirements-intel.txt` |

## Virtual environments

There is intentionally **more than one** venv:

- **`.venv`** — the main app/runtime + the uv workspace.
- **`.venv-dbt`** — isolated dbt environment (protobuf/pathspec pins conflict with
  `.venv`; see `requirements-dbt.txt`). The dbt project under `dbt_project/` is a
  standalone uv project for the same reason.

## Known cleanup follow-ups

These are **deferred** (each needs its own change + verification), tracked here so the
state is explicit rather than surprising:

- **`setup.py`** is legacy `setuptools` metadata, still referenced by the HuggingFace
  deploy script (`packages/hosting/scripts/huggingface/deploy-huggingface.sh`) and a
  rename-repo doc. It is a removal candidate **once that script is migrated** to the uv
  workspace — not before.
- **Consolidating the runtime onto uv** (so `requirements.txt` / `requirements-cpu.txt`
  are generated via `uv export` rather than hand-maintained) requires rewiring the
  Dockerfiles, CI, and install scripts together. It is a deliberate, scoped effort
  (Theme 4 of the repo-wide refactor & tech-debt plan).
