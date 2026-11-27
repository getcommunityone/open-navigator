---
pr: 1358
branch: fix/1357-map-hover-state-meetings
title: "fix(stories): hovering different boxes in a state switches the meeting panel"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: coordinator (Antigravity)
verdict: approve
---

# PR Review: fix(stories): hovering different boxes in a state switches the meeting panel

## Summary

Fixes #1357 so hovering across different boxes, stance bands, or zones within the same state on `StoryStatesMap` (home hero and topic stories) and `StoryDotMap` (Data Center Story Overview) updates the desktop meeting quote/video panel instead of locking onto the state's first speaker. Adds a pure zone-partitioning helper (`web_app/src/utils/mapQuote.ts`) that prefers named speakers without discarding unnamed meeting passages, matches stance bands (using `StateQuote.band` for topic stories so meeting passages don't display speaker-side pills), and extends `GET /api/topics/{topic_id}/states` with an optional bounded `quotes_per_state` parameter (`1..6`, default `1` unchanged). Every scan is clean, unit/build/live Playwright checks pass, and the verdict is **approve**.

## Scope of Change

- Files changed: 11 (+414 / -31)
- Areas touched: `api`, `web_app`, `web_docs`, `tests`
- Commits:
  - `6097c7b1` `fix(stories): hovering different boxes in a state switches the meeting panel (#1357)`
- Range reviewed: `fdc52a07..6097c7b1`

## CI Status

| Check | Status |
|---|---|
| Frontend Build | Pending on review push (verified locally: `tsc && vite build` passed) |
| Documentation Build | Pending on review push (verified locally: `docusaurus build` passed) |
| Backend Tests | Pending on review push (verified locally: 16 passed, 3 live-DB skipped) |
| API Types | Pending on review push (verified locally: `openapi-typescript` generated cleanly) |
| PR conventions | Passed on `6097c7b1` |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean (pre-commit `detect-secrets` and `detect-private-key` passed; diff scan clean).
- **Fabricated data in a served path:** clean (every quote/speaker/stance comes from live API responses; test fixtures live strictly in `*.test.ts` and `tests/`).
- **Personal data & privacy (`AGENTS.md` #1080):** clean (resident speaker names continue passing through `speaker_fields()` `"First L."` enforcement in `api/routes/topics.py`; no private enrichment or user location storage added).
- **Destructive or bulky data changes:** clean (`data/cache/` untouched; no warehouse changes outside dbt).

## Strengths

- Contiguous zone partitioning (`pickZoneIndex`) avoids rapid YouTube iframe reloads on small pointer jitter inside a meeting's block while cleanly switching meetings across stance bands and zones.
- Separating `StateQuote.band` from `StateQuote.side` lets topic stories match hovered map bands to meeting stances without triggering a speaker-side badge on `QuoteCard`.
- Defaulting `quotes_per_state=1` on `GET /api/topics/{topic_id}/states` preserves 100% backward compatibility with existing callers and tests, while `quotes_per_state > 1` deduplicates per video and round-robins across stances (`stance_rn`) with fallback SQL when `meeting_video_kind` / `topic_meeting_lean` are absent.

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
| Issue first | Yes | Issue #1357 has Problem, Done when, Contract, Read first; branch `fix/1357-map-hover-state-meetings`; PR says `Closes #1357` |
| Conventional Commits | Yes | `fix(stories): ...` and `docs(review): ...` with co-author trailer |
| No fabricated data | Yes | Clean scan |
| New Python in `packages/` | Yes | Only existing `api/routes/topics.py` and `tests/` touched; nothing in `scripts/` |
| dbt for transformations | Yes | No dbt/warehouse schema changes |
| Naming | Yes | `state_code` and `state` preserved |
| Keys | Yes | N/A (no new public tables) |
| Calendar years | Yes | N/A |
| Scope label matches filter | Yes | Preserved; state/city scope unchanged |
| Match evidence on filtered tiles | Yes | Existing `highlightSnippet` preserved; no `dangerouslySetInnerHTML` |
| Docs | Yes | `web_docs/docs/guides/data-stories.md` updated in the same PR |
| Telemetry and logging | Yes | OpenTelemetry span attribute `topics.quotes_per_state` added in `api/routes/topics.py`; `loguru` used for fallback warning |
| Tests | Yes | 10 new Vitest unit tests (`mapQuote.test.ts`), 2 new FastAPI route tests (`test_api_story_map_quotes.py`), and desktop Playwright check in `e2e/map-taps.check.mjs` |
| Shared libraries | Yes | No `packages/` files changed |

## Test Coverage

- `cd web_app && npx vitest run src/utils/mapQuote.test.ts src/utils/boxSplit.test.ts src/components/stance/QuoteCard.test.tsx` → 35 passed (35)
- `cd web_app && npx tsc --noEmit && npm run build` → passed (0 errors)
- `.venv/bin/pytest tests/test_api_story_map_quotes.py tests/test_api_passage_speakers.py -v` → 16 passed, 3 live-DB skipped
- `.venv/bin/ruff check --select F,E9,W api/routes/topics.py tests/test_api_story_map_quotes.py` → All checks passed
- `cd web_docs && npm run build` → succeeded
- Live Playwright desktop verification on `http://localhost:5173/`: hovering across Texas boxes switched cleanly across all 3 stance bands and 5 distinct speakers/meetings (`James C.`, `Marshall B.`, `Kirk C.`, Corpus Christi, El Paso).

## Verdict

**approve** — ready to merge once required CI checks pass on the latest commit.
