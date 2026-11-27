---
pr: 1215
branch: feat/1200-topic-positions-headline
title: "feat(stories): each topic's public position in its own words, and the place's conclusion in the headline"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: read-only reviewer subagent (general-purpose) and coordinator; supersedes the github-actions auto-review of 417dde02
verdict: approve
---

# PR Review: each topic's public position in its own words, and the place's conclusion in the headline

## Summary
This PR adds a per-topic position vocabulary (`utils/topicPositions.ts`). The words for for / against / split / missing restate the stance each topic is read against in `llm.typesafe.topic_lean.TOPICS`; guns is "Backed / Opposed the gun proposal", never "gun limits". It also adds caption rule (p), which states the place's majority position with its count, and makes caption-facts and state-map serve split and silent counts. The words appear in the topic map legend, hover line and data table, the unit matrix and the data-center tint label. The reviewer found four Important and five Minor issues. All were verified and are fixed in 8a6e2988, with tests. Nothing blocking remains. Verdict: approve.

## Scope of Change
- Files changed: 22 (+935 / -44, excluding this review file)
- Areas touched: api, web_app, web_docs
- Commits:
  - 56ff9edf feat(stories): each topic's public position in its own words, and the place's conclusion in the headline (#1200)
  - 8a6e2988 fix(stories): review fixes for topic positions (#1200)
  - plus merges of origin/main and the bot's auto-review commit
- Range reviewed: `merge-base(origin/main)..HEAD` (feature commits only)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | success on 417dde02; re-run on the head before merge |
| Documentation Build | success on 417dde02; re-run on the head |
| Backend Tests | success on 417dde02; re-run on the head |
| API Types | success on 417dde02; re-run on the head |
| PR conventions | success |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. Every number in a title, basis, legend or table comes from caption-facts or state-map fields. Missing readings are said to be missing ("No AI reading yet", "N meetings have an AI reading so far"). A failed read (null) makes no claim. Test fixtures stay in tests.
- **Personal data:** clean. These are meeting-level classifier counts and no person is involved.
- **Destructive data changes:** none. The only data step was a local `dbt build` of `stg_jev__transcript_topic_lean` and `topic_meeting_lean`, rebuilt from existing rows with no paid run.

## Strengths
- One source for the words, and a vitest that reads `topic_lean.py`, so a new topic can't ship without words, and guns and short-term rentals can't drift from their stance.
- Against, for, split and silent are counted explicitly in SQL. A label outside the question's choices counts in none of them, so the water-fluoridation rows with off-schema labels (#1204) are never shown as a side.
- The older API is handled: without the new fields the earlier rules run unchanged.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
All fixed in 8a6e2988:
1. `storyCaption.ts`: (p2), the broader scope's conclusion, ran before the place's own counted-speaker and disagreement titles. It now takes (a2)'s place, and with the position counts the against-only (a2) no longer runs, because it could contradict a split national reading. Test: "a place's own counted-speaker title still beats the broader scope's conclusion".
2. `storyCaption.ts` `positionBasis`: readings with off-list labels were called "not read yet". They are now stated separately, and "not read yet" uses `lean_meetings`. Tested.
3. `storyCaption.ts`: the (p2) basis could say "the public speaking in 0". It now says "in none of them did the public speak on it". Tested.
4. `unitMatrix` / `data_centers.py`: the matrix labelled a lean under P 0.7 "For data centers" while the title called it split. `meeting-mentions` now serves such a lean as `mixed`.

### 🔵 Nits / suggestions (Minor)
Fixed:
- A failed lean read no longer claims "no reading yet". caption-facts sends `lean_meetings: 0` when the read ran and found nothing, and null when it failed (pytest).
- The map note now handles the case where every reading is silent, and the split note shows only when a split legend shows.
- The silent column is gated on stance data.
- The doc names the colours correctly (muted red, teal, plum).
- The `positionLine` docstring order is fixed.

Left as is: the basis wording "30 end fluoridation" is clumsy, but it is accurate.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | #1200 has all four parts; branch `feat/1200-…`; `Closes #1200`; follow-up #1204 filed |
| Conventional Commits | yes | co-author trailer on each |
| No fabricated data | yes | scan above |
| New Python in `packages/` | n/a | no new Python modules |
| dbt for transformations | yes | API counts are aggregates over the marts; no dbt model changed |
| Naming / Keys / Calendar years | n/a | no model change |
| Scope label matches filter | yes | the picker ignores facts for another scope; p2 names its broader scope as text |
| Match evidence on filtered tiles | n/a | |
| Docs | yes | `guides/data-stories.md`, `development/story-captions.md`, `development/topic-meeting-lean.md` |
| Telemetry | yes | existing spans; no new route |
| Tests | yes | new vitest and pytest cases for each behaviour |
| Shared libraries | n/a | `packages/` unchanged |

## Test Coverage
- vitest: 72 files, 679 tests. New:
  - `topicPositions.test.ts`: vocabulary vs topic_lean; guns and STR direction.
  - `storyCaptionPosition.test.ts`: majority, hates, split, too few, no reading, p2, off-list labels, failed read, older API, zero rule.
- pytest: `tests/test_api_topic*.py` and `tests/test_api_data_center*.py`, 157 passing.
- `ruff`: no new findings. `topics.py` had 41 findings on main and has 40 here.
- `tsc --noEmit`, `npm run build` and the docs build pass. The docs build's broken-link warnings were already on main.
- Playwright, before the review fixes:
  - Run at 1440x900 and on iPhone 13, against my own Vite and API from the worktree.
  - Pages: /stories/guns, ?state=OH, ?state=CA, short-term-rentals, pickleball, license-plate-readers, water-fluoridation and /.
  - Titles, legends, hover lines and table headers read as described in the PR body. No page scrolls horizontally.
  - After the fixes, the local warehouse lost `public.civicsearch_topic` (parallel rebuild; the main API also returns 503), so the fixes are verified by unit tests only.
- `dbt ls --select topic_meeting_lean+` lists only the mart. The local build passes except for an `accepted_values` failure on 4 off-schema labels (#1204).

## Verdict
approve. CI on the head commit must be green before merge.
