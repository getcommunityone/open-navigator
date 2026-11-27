---
pr: 1363
branch: feat/1361-all-major-meeting-topics
title: "feat(topics): show all major meeting topics on Browse all topics"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: research subagent and coordinator
verdict: approve
---

# PR Review: feat(topics): show all major meeting topics on Browse all topics

## Summary

Adds the `topic_meeting_year` dbt mart (`gold` → `public`, ODCS/ODPS contracts, Neon sync allow-list) aggregating distinct meetings per `(topic_id, state_code, jurisdiction_name, meeting_year)` across all 95 topics in `civicsearch_topic` (20 `curated` + 75 `civicsearch`), updates `GET /api/topics/yoy` to query it with optional `source` filtering and `has_story` flags, and adds `All major topics` / `Not yet a story` / `Live stories` filtering (`?show=`) and `Biggest rise` / `Most discussed` sorting (`?sort=`) on `/browse-topics/all`. Both minor nits found during review (a stray `api.types.ts` diff from local `api/static/` and an ambiguous `Change` table header in `Count` view) were fixed on the branch before merge.

## Scope of Change

- Files changed: 13 (+618 / -90, excluding generated files)
- Areas touched: `dbt_project` / `packages/hosting` / `api` / `tests` / `web_app` / `web_docs`
- Commits:
  - `396f9f38` `feat(topics): show all major meeting topics on Browse all topics (#1361)`
  - `56c9b1db` `Merge remote-tracking branch 'origin/main' into feat/1361-all-major-meeting-topics`
  - `41de7a74` `docs(pr-1363): auto-write rubric review [skip review]`
- Range reviewed: `origin/main..HEAD`

## CI Status

| Check | Status |
|---|---|
| `CI - Build & Test` (Frontend, Docs, Backend, API Types) | Passed on `56c9b1db`; re-running on nit fix + review commit |
| `PR conventions` | Passed on `56c9b1db`; re-running on nit fix + review commit |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** Clean. No API keys, passwords, tokens, credentialed URLs, `.env` contents, or cookies.
- **Fabricated data in a served path:** Clean. `topic_meeting_year` aggregates real rows from `data_center_meeting_mention` and `int_transcript_keyword_topic` + `event_documents`; uncomputable shares/changes stay `null`/`—` and thin topics stay in "Too few meetings to compare".
- **Personal data & privacy (`AGENTS.md`, #1080):** Clean. Topic-level aggregate counts only; no private persons, sensitive traits, minors, scraping, or user tracking.
- **Destructive or bulky data changes:** Clean. No `data/cache/` deletions or raw files committed. `gold.topic_meeting_year` is 100,545 rows (`19 MB` total with indexes; `13,029` rows in launch scope).

## Strengths

- **Enforced dbt contract & Neon sync readiness:** `topic_meeting_year` defines PK (`topic_meeting_year_id`), FK (`topic_id -> civicsearch_topic`), unique-combination test, null/trim normalization before MD5 hashing, and both `state_code` and `state`; registered in `publish_public_serving.sql`, ODCS/ODPS contracts, and `sync_public_to_neon.py`.
- **Verified warehouse parity:** Querying local Postgres confirmed 0 duplicate grain rows, exact match against `topic_transcript_link` (`100002–100006`) and dated `data_center_meeting_mention` (`100001`), and accurate `has_story` detection via `topic_transcript_link` + `data-centers`.
- **URL-driven filters & smart routing:** `?show=` and `?sort=` stay in URL search params, survive place broadening, and route live stories to `/stories/<slug>` and candidate topics to `/browse-topics?topic_id=<id>`.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important)
None.

### 🔵 Nits / suggestions (Minor)
1. `web_app/src/lib/api.types.ts` — *Resolved:* reverted the stray `"/{full_path}"` diff caused by local `api/static/` existing during `npm run gen:api`.
2. `web_app/src/pages/BrowseAllTopics.tsx` — *Resolved:* updated the expandable `DataTable` final column header from `'Change'` to `metric === 'share' ? 'Share change' : 'Count change'`.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1361 opened with Problem, Done when, Contract, Read first; branch `feat/1361-all-major-meeting-topics`; PR body has `Closes #1361` |
| Conventional Commits | Yes | Conventional Commit messages with `Co-Authored-By` trailer |
| No fabricated data | Yes | Scan clean; explicit empty/thin states and `null`/`—` |
| New Python in `packages/` | Yes | Only 2 lines added to `packages/hosting/src/hosting/neon/sync_public_to_neon.py` |
| dbt for transformations | Yes | Pure SQL in `dbt_project/models/marts/topic_meeting_year.sql` |
| Naming | Yes | `state_code` and `state` both present; no `dim_`/`fact_` |
| Keys | Yes | PK (`topic_meeting_year_id`) and FK (`topic_id -> civicsearch_topic`) declared in `_schema_topic_meeting_year.yml` |
| Calendar years | Yes | `meeting_year` is `integer` in Postgres, `str` (`year_a`/`year_b`) on the wire |
| Scope label matches filter | Yes | Eyebrow, 📍 chip, heading, and API/URL params move together |
| Docs with the change | Yes | `web_docs/docs/guides/data-stories.md` updated in the same PR |
| Telemetry and logging | Yes | OpenTelemetry span (`topics-yoy`) and `loguru.logger.exception` in `api/routes/topic_yoy.py` |
| Tests | Yes | dbt tests, ODCS/ODPS checks, pytest (`test_api_topic_yoy.py` + `datamodels` + `hosting`), Vitest (`topicsYoy.test.ts`), tsc, and Vite/Docusaurus builds |

## Test Coverage

- `dbt run --select topic_meeting_year && dbt test --select topic_meeting_year` → 6/6 passed
- `dbt ls --select topic_meeting_year+` → clean
- `python -m models.odcs --check` → 106 ODCS contracts + 1 ODPS product valid
- `POSTGRES_PASSWORD=password .venv/bin/pytest tests/test_api_topic_yoy.py -v` → 10/10 passed (including live warehouse parity `[None]` and `[GA]`)
- `.venv/bin/pytest -q packages/datamodels/tests packages/hosting/tests` → 87 passed
- `.venv/bin/ruff check api/routes/topic_yoy.py tests/test_api_topic_yoy.py` → passed
- `cd web_app && npx vitest run src/utils/topicsYoy.test.ts && npx tsc --noEmit && npm run build` → passed
- `cd web_docs && npm run build` → passed

## Verdict

**approve** — All scans clean, warehouse parity verified, both minor nits resolved.
