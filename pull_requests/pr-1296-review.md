---
pr: 1296
branch: feat/1288-story-kpi-drilldown
title: "feat(stories): tap a \"Who spoke up\" number to see the records behind it"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: general-purpose reviewer subagent (read-only) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(stories): tap a "Who spoke up" number to see the records behind it

## Summary

Each "Who spoke up" number on the Data Center Story that has records behind it (spoke for / against / asked a question, votes for / against, the caption public-comment line, Mention AI, Name &lt;company&gt;) is now a button that opens the list behind it for the URL scope, through three new paged endpoints that count with the tile's own filter. A read-only reviewer re-ran the tile-vs-list parity on the local warehouse (speakers 3 = 3, 18 = 18; votes 79 = 79, 10 = 10) and found no critical bugs. Two accessibility findings and one nit were fixed in a follow-up commit; Escape inside the open list no longer closes the whole story (found while verifying the fix in Playwright). One latent data finding is logged as #1299. Verdict: approve-with-nits.

## Scope of Change

- Files changed: 15 (about +1,490 / -12, excluding `web_app/src/lib/api.types.ts`)
- Areas touched: api / web_app / web_docs / tests
- Commits:
  - 70f33c0b feat(stories): tap a "Who spoke up" number to see the records behind it
  - 53e2e1b4 docs(pr-1296): auto-write rubric review [skip review] (bot)
  - fix(stories): KPI list returns focus, traps it on phones, keeps its own Escape (this review's fixes)
- Range reviewed: `origin/main...HEAD`

## CI Status

| Check | Status |
|---|---|
| Frontend Build | success on 70f33c0b; re-run on the final head |
| Documentation Build | success on 70f33c0b; re-run on the final head |
| Backend Tests | success on 70f33c0b; re-run on the final head |
| API Types | success on 70f33c0b; re-run on the final head |
| PR conventions | success |
| Docker Build Test | skipped (no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data in a served path: clean. Every row comes from `public.data_center_public_comment`, `data_center_decision`, `data_center_meeting_position` or `data_center_comment`; totals are `count(*)` / `sum` of those; a missing mart returns `available: false` with null totals, never 0.
- Personal data / privacy: clean. Residents appear only as the mart's "First L." `speaker_display_name`; a `possible_minor` caption comment is listed (so the count adds up) with name, link, timestamp and keywords withheld on the server. Caption comments have no quote because `meeting_comment` stores no text by design (#1233); the PR doesn't work around that.
- Destructive or bulky data changes: none. No dbt, no warehouse writes, no Neon.

## Strengths

- List total equals the tile by construction: speakers and votes join `data_center_meeting_position` and scope on its `state_code` / `jurisdiction_name` exactly as `/positions`; comments reuse `/comment-metrics`' `_where`. pytest asserts the filters are identical.
- Vote tiles count votes, so their lists are decisions whose tallies sum to the tile, and the header says so ("8 votes for in 1 decision").
- 0 / "not recorded" tiles are never wrapped; tile text and wording are unchanged (the wording belongs to the parallel on-fitdisplay work).
- Quotes go through `highlightSnippet` (server `<mark>` on data center words); no `dangerouslySetInnerHTML`.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

1. **Vote totals can drift from the tile** (latent). `data_center_meeting_position.dc_decisions` reads `event_decision` without the preferred-analysis join that `data_center_decision` uses, so a superseded analysis with a tally would count in the tile with no drill row. Verified by reading both models; the sums match on the warehouse today. It's a dbt fix outside this PR: logged as **#1299** (bug, action-item).
2. **Focus lost on close** (`KpiDrill.tsx`). Close / Escape / scrim unmounted the focused sheet and dropped focus to `<body>`. **Fixed:** the opener is saved on mount and refocused on unmount; focus moves into the sheet again when it moves into the phone portal.

### 🔵 Nits / suggestions (Minor)

3. **Phone dialog didn't trap focus** (`aria-modal` without an inert background). **Fixed:** `#root` gets `inert` while the phone sheet is open (the sheet is portalled outside it); the inert cleanup runs before the focus restore. Playwright at Pixel 7: focus starts in the sheet, Tab stays in it, `inert` is removed on close, focus returns to the "spoke against" number.
4. **Escape closed every open list and, on desktop, the story** (`KpiDrill.tsx`, `StoryClose.tsx`). **Fixed:** Escape is handled on the list itself (`onKeyDown`), and `StoryClose`'s capture-phase handler skips an element inside `[data-keeps-escape]`. Playwright at 1440: Escape closes the list, the URL stays on `screen=voices`, focus returns to the number.
5. **Company key lowercased in the drill but not on the tile.** **Fixed:** the key is passed through as-is.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1288 has all four parts; branch `feat/1288-story-kpi-drilldown`; `Closes #1288`; follow-ups #1292, #1299 |
| Conventional Commits | Yes | co-author trailer on agent commits |
| No fabricated data | Yes | see scans |
| New Python in `packages/` | n/a | API route only; nothing in `scripts/` |
| dbt for transformations | Yes | Python only counts and lists served marts; the `<mark>` wrap is presentation on a verbatim quote |
| Naming | Yes | `state_code` (+ scope `state`) |
| Keys | n/a | no new models |
| Calendar years | Yes | `year` serialized as a string |
| Scope label matches filter | Yes | each list header names the scope it was queried with (`storyScopeLabel`), from the same `?state=&city=` |
| Match evidence on filtered tiles | Yes | verbatim quotes, `highlightSnippet`; caption comments say why there's no quote |
| Docs | Yes | `web_docs/docs/guides/data-stories.md`, "Tap a number to see the records behind it (#1288)" |
| Telemetry and logging | Yes | OTel span per endpoint; loguru for errors; `withSpan` on the client |
| Tests | Yes | see below |
| Shared libraries | n/a | no `packages/` change |

## Test Coverage

- `tests/test_api_data_center_drill.py` (9): filter parity with `/positions` and `/comment-metrics`, paging params, `<mark>` marking, possible-minor withholding, unavailable mart → null. Ran with the positions and comment-metrics suites: 35 passed. `ruff check` clean.
- `web_app/src/components/stance/KpiDrill.test.tsx` (7): non-tappable zero/null, figure → endpoint mapping, vote summary, rows with quote/name/link, decision link, minors withheld, "Show more" until the total. Full vitest: 767 passed. `tsc --noEmit` clean.
- Playwright (Chromium, swiftshader) at Pixel 7 and 1440 against a worktree API: list lengths after "Show more" equal the tiles (AL comments 60, AZ spoke against 11, AL votes for 1 decision = 8 votes); focus and Escape behaviour as above.
- Not covered by an automated test: focus restore / inert (DOM behaviour, checked in Playwright only).

## Verdict

**approve-with-nits.** No blocking findings; the important a11y finding and the nits are fixed on the branch; the latent dbt drift is #1299. Merge once the required checks are green on the final head.
