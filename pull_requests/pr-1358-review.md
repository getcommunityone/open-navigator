---
pr: 1358
branch: fix/1357-map-hover-state-meetings
title: "fix(stories): hovering different boxes in a state switches the meeting panel"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator
verdict: approve
---

# PR Review: fix(stories): hovering different boxes in a state switches the meeting panel

## Summary

Fixes #1357 so hovering across different stance bands or box zones within the same state on `StoryStatesMap` (home page data-center and topic heroes, plus topic story pages) and `StoryDotMap` (Data Center Story Overview) switches the meeting quote/video panel through that state's real speaker and meeting passages instead of locking onto a single passage. Adds a pure, tested helper (`web_app/src/utils/mapQuote.ts`) that matches hovered stance bands (using `band` for topic meetings so no bogus speaker-side pill appears) and partitions each band/state into contiguous zones to avoid iframe reload jitter. Adds an optional `quotes_per_state` (`1..6`, default `1`) query parameter to `GET /api/topics/{topic_id}/states` with stance-balanced distinct-video selection so topic maps also carry multiple meetings per state. Verified with Vitest, pytest, ruff, TypeScript/Vite build, Docusaurus build, and a live Playwright hover check across Texas on `/`. Verdict: **approve**.

## Scope of Change

- Files changed: 11 (+414 / -31, excluding review file)
- Areas touched: `api`, `tests`, `web_app`, `web_docs`
- Commits:
  - `6097c7b1` `fix(stories): hovering different boxes in a state switches the meeting panel (#1357)`
  - `ac2a1235` `docs(pr-1358): auto-write rubric review [skip review]`
- Range reviewed: `origin/main..HEAD`

## CI Status

| Check | Status |
|---|---|
| Frontend Build | Pending on new push (passed locally: `vitest`, `tsc --noEmit`, `npm run build`) |
| Documentation Build | Pending on new push (passed locally: `cd web_docs && npm run build`) |
| Backend Tests | Pending on new push (passed locally: `pytest` 16 passed, 3 live-DB skipped) |
| API Types | Pending on new push (verified locally via `export_openapi.py` + `openapi-typescript`) |
| PR conventions | Pending on new push |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean (pre-commit `detect-secrets` and `detect-private-key` passed; diff inspected).
- **Fabricated data in a served path:** clean (all passages come from real API responses; no hard-coded/placeholder figures; `StateQuote.band` avoids rendering fabricated speaker-side badges on meeting passages).
- **Personal data & privacy (`AGENTS.md` #1080):** clean (existing `speaker_fields()` enforces `"First L."` for residents; no private personal data added or logged).
- **Destructive or bulky data changes:** clean (no deletions in `data/cache/`, no raw/binary dumps committed).

## Strengths

- Contiguous zone partitioning (`pickZoneIndex`) avoids rapid YouTube iframe reloads on tiny pointer movements while still cycling cleanly across every speaker/meeting in a state.
- Separating `StateQuote.band` from `StateQuote.side` keeps `QuoteCard` strictly accurate for topic meeting passages (no invented speaker-side badge).
- `GET /api/topics/{topic_id}/states` keeps `quotes_per_state=1` as the default with the original SQL intact, preserving backwards compatibility.
- Governed guide (`web_docs/docs/guides/data-stories.md`) updated in the same PR.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Issue #1357 has Problem, Done when, Contract, Read first; branch `fix/1357-map-hover-state-meetings`; PR has `Closes #1357` |
| Conventional Commits | Yes | `fix(stories): ...`, `docs(pr-1358): ...` with co-author trailer |
| No fabricated data | Yes | Only real API records rendered; test stand-ins stay in tests |
| New Python in `packages/` | Yes | Only existing FastAPI route `api/routes/topics.py` modified; nothing added to `scripts/` |
| dbt for transformations | Yes | No warehouse transformations added in Python; read-only serving SQL query |
| Naming / Keys / Calendar years | Yes | Unchanged response model `TopicStates` (`state_code`, `state`, ISO date strings) |
| Scope label matches filter | Yes | State/city URL params and filters preserved unchanged |
| Match evidence on filtered tiles | Yes | Verbatim `<mark>` excerpts rendered via `highlightSnippet` |
| Docs | Yes | Updated `web_docs/docs/guides/data-stories.md` |
| Telemetry and logging | Yes | Added `topics.quotes_per_state` OpenTelemetry span attribute; `loguru` warning on fallback |
| Tests | Yes | Added 10 Vitest unit tests (`mapQuote.test.ts`), 2 pytest route tests (`test_api_story_map_quotes.py`), and desktop hover check in `map-taps.check.mjs` |

## Test Coverage

- `cd web_app && npx vitest run src/utils/mapQuote.test.ts src/utils/boxSplit.test.ts src/components/stance/QuoteCard.test.tsx`: 35 passed (35)
- `cd web_app && npx tsc --noEmit && npm run build`: passed
- `.venv/bin/pytest tests/test_api_story_map_quotes.py tests/test_api_passage_speakers.py -v`: 16 passed, 3 skipped (live-DB gated)
- `.venv/bin/ruff check --select F,E9,W api/routes/topics.py tests/test_api_story_map_quotes.py`: all checks passed
- `cd web_docs && npm run build`: succeeded
- Live Playwright desktop hover check on `http://localhost:5173/` across Texas: confirmed switching across all 3 stance bands and 5 distinct speakers/meetings.

## Verdict

**approve** — clean, scoped fix with unit, API, build, docs, and live browser verification; ready to merge once required CI checks are green.
