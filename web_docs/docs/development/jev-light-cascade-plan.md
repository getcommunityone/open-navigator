---
sidebar_position: 40
title: Jev-light cascade implementation plan
description: Bite-sized tasks for #702–#705 — topic flags, analyze gate, keeper blurb.
---

# Jev-light cascade implementation plan

> **For agentic workers:** Implement task-by-task; each task ends with tests green and its own PR (`Closes #<issue>`).

**Goal:** Ship Approach A from [jev-light-cascade-design.md](./jev-light-cascade-design.md) — cheap Jev coverage, blurb for keepers, Gemini only for high-value keepers.

**Architecture:** Extend `screen_transcripts` questions in-place (same request); wire `--skip-jev-meeting-below 0.6` on data-centers analyze; add `bronze_transcript_blurb_light` + short chat call for keepers; UI excerpt precedence later in #705.

**Tech Stack:** Python 3.11+, pytest, loguru, TypeSafe Jev, existing `batch_backlog` / launch scripts.

**Global constraints:** No fabricated summaries; calendar years as strings on JSON wire; new Python in `packages/` only; Conventional Commits; one issue per PR.

---

### Task 1: Design doc (#702)

**Files:** `web_docs/docs/development/jev-light-cascade-design.md`, link from `jev-meta-and-scale-design.md`

- [x] Design written and linked
- [ ] Commit + PR `Closes #702` (docs only)

### Task 2: Topic flags on screen (#703)

**Files:**
- Modify: `packages/llm/src/llm/typesafe/screen_transcripts.py`
- Modify: `packages/llm/tests/test_typesafe.py` (or create if missing coverage)
- Modify: `web_docs/docs/development/jev-transcript-screening.md` (list new questions)

**Produces:** `QUESTIONS` includes `mentions_zoning`, `mentions_budget`, `mentions_housing`, `mentions_environment`; `QUESTION_VERSION` bumps; CREATE/UPSERT/aggregate/`ScreenResult` persist new `*_p` columns; `ALTER TABLE` / create-if-not-exists adds columns.

- [ ] Failing tests for aggregate max-noul on new keys + version change
- [ ] Implement questions + schema + aggregate
- [ ] pytest green; PR `Closes #703`

### Task 3: Data-centers analyze gate (#704)

**Files:**
- Modify: `packages/scrapers/scripts/youtube_run_priority_states_last_n.sh` (or the path the API launch uses)
- Modify: `api/routes/batch_jobs.py` launch argv if it builds analyze CLI
- Docs: note in design / screening doc

**Produces:** data_centers (or env `SKIP_JEV_MEETING_BELOW=0.6`) analyze passes `--skip-jev-meeting-below 0.6`; skip counts logged.

- [ ] Find launch command construction; add flag for data_centers cohort
- [ ] Smoke: `--help` / dry argparse; PR `Closes #704`

### Task 4: Keeper blurb (#705)

**Files:** new `packages/llm/src/llm/typesafe/light_blurb.py` (or `llm.gemini` sibling — prefer `llm.typesafe` orchestration calling `call_gemini_text` / DeepSeek); bronze DDL; tests with mocked client.

- [ ] Table + CLI `python -m …` for keepers lacking Part‑1 and blurb
- [ ] Usage stage `light_blurb`
- [ ] PR `Closes #705`

### Task 5: UI excerpt (follow-up under #705 or new issue)

Blurb → long YouTube description → extractive → empty. Only after bronze blurb exists.
