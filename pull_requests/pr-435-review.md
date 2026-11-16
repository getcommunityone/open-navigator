---
pr: 435
branch: feat/424-jev-transcript-screening
title: "feat(llm): screen transcripts with TypeSafe's Jev before Gemini analysis"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (Claude Code session; no reviewer subagent, as the rubric allows)
verdict: approve-with-nits
---

# PR Review: feat(llm): screen transcripts with TypeSafe's Jev before Gemini analysis

## Summary
The PR adds `llm.typesafe.client`, an httpx client for Jev's `POST /v1/systemone` that retries 429 and 529 and writes
one usage row per call. It also adds `python -m llm.typesafe.screen_transcripts`, which asks three questions per
transcript, chunked at caption segments under Jev's 32k-token limit, and upserts one row per video into
`bronze.bronze_transcript_screen_jev`. Finally, `batch_backlog submit` gets an opt-in `--skip-jev-below P` that leaves
out screened videos whose `has_decisions_p` is below P. It never skips an unscreened video and never changes a
transcript. The code is clean and well tested against the documented response shapes. One 🟡 finding (usage rows had
no stage or video label) was fixed in 73e33542. The verdict is approve-with-nits.

## Scope of Change
- Files changed: 9 (+1,229 / -3, excluding `uv.lock`; including the review fix)
- Areas touched: packages (llm), web_docs, `.env.example`
- Commits:
  - 9d40b67d feat(llm): screen transcripts with TypeSafe's Jev before Gemini analysis
  - 73e33542 fix(llm): label Jev screening usage rows with the stage and video (review fix)
- Range reviewed: `fb865cc2..73e33542`

## CI Status
CI ran on 9d40b67d, before the review commit.

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | pass |
| API Types (OpenAPI -> TypeScript) | pass |
| PR conventions (linked issue) | pass |
| Docker Build Test | skipped |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. `.env.example` adds only a commented `TYPESAFE_API_KEY=your_typesafe_api_key_here`, and the tests
  use `api_key="test-key"` with `httpx.MockTransport`.
- Fabricated data in a served path: clean (no `api/` or `web_app/src/` changes). The Jev price in `prices.yaml` has
  its `source` and `read_date`.
- Personal data: clean. Public meeting transcripts only.
- Destructive or bulky data changes: clean. The screen writes a new bronze landing table (`CREATE TABLE IF NOT
  EXISTS` plus upsert) and changes no transcript. It is model output landed by Python, which `CLAUDE.md` allows.

## Strengths
- Safe by default: `--skip-jev-below` is opt-in, `jev_skip_video_ids` returns only current-question-version screens
  with a non-null probability, and `to_regclass` guards against a missing table.
- `QUESTION_VERSION` is a hash of the question text, so rewording a question makes every video eligible again
  without manual bookkeeping.
- Fits the existing usage and cost tooling: `model_price` matches the longest prefix, so the `jev-` entry prices both
  `jev-1.14.0` and the `jev-latest` used on failed calls, and the rows default to `api_mode="interactive"`, which the
  entry defines.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **Fixed in 73e33542.** `packages/llm/src/llm/typesafe/screen_transcripts.py` (`screen_transcript`): Jev calls were
  made outside `llm_call_context`, so every usage row had `stage` and `video_id` empty. The Gemini paths
  (`meeting_transcript_policy.py:1270`, `compare_models.py:485`) set both, which lets the cost report attribute spend
  per stage and video. Verified by reading `record_llm_call`, which takes those labels only from the context. The
  calls are now wrapped in `llm_call_context(stage="jev_screen", video_id=...)`, and the new test
  `test_screen_usage_rows_name_the_stage_and_video` checks the rows.

### 🔵 Nits / suggestions (Minor)
- `screen_transcripts.py` `DEFAULT_CHUNK_CHARS = 100_000`: sizing assumes 4 characters per token, which leaves about
  25k tokens of the 32k limit. A denser transcript (numbers, names, non-English) could pass 32k. The resulting 4xx
  isn't retried and that video counts as failed. A smaller default, or one retry at half the chunk size on a
  length error, would remove the risk.
- `screen_transcript`: if a later chunk fails, the chunks already answered (and billed) are discarded. At Jev's price
  this costs little.
- `bronze.bronze_transcript_screen_jev` is created by Python and isn't declared as a dbt source yet. Declare it when a
  model reads it, so the lineage shows.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/424-...`; `Closes #424`; #424 has all four parts |
| Conventional Commits | Yes | Scoped, with co-author trailers |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | Yes | `packages/llm/src/llm/typesafe/`; CLI is `python -m llm.typesafe.screen_transcripts` |
| dbt for transformations | Yes | No SQL transformation in Python; bronze landing only |
| Naming | N/A | |
| Keys | Yes | `video_id` primary key on the bronze table; not exposed in `public` |
| Calendar years | N/A | |
| Scope label matches filter | N/A | |
| Match evidence on filtered tiles | N/A | |
| Docs | Yes | `web_docs/docs/development/jev-transcript-screening.md`, kebab-case, with frontmatter |
| Telemetry and logging | Yes | loguru, plus usage rows (now labelled) |
| Tests | Yes | 15 tests: request shape, retries, errors, chunking, aggregation, SQL, price, flag parsing, usage labels |
| Shared libraries | Yes | Whole `packages/llm` suite run |

## Test Coverage
Ran locally with the worktree's packages on `PYTHONPATH`: `pytest packages/llm/tests`, 200 passed (199 before the
review test). `ruff check` passes on `llm/typesafe/` and its test; `batch_backlog.py` has no ruff errors. Nothing was
run against the live Jev API (there is no key on this machine, and the PR says so).

## Verdict
approve-with-nits. The 🟡 finding is fixed. The chunk-size margin is worth a look before the first large run.
