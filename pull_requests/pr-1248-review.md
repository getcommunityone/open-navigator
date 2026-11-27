---
pr: 1248
branch: fix/1237-gun-control-labels
title: "fix(stories): label the guns topic Gun control, with named sides Favor gun limits / Favor gun rights"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: read-only reviewer subagent (frontend-specialist) and coordinator; supersedes the github-actions auto-review of a350a993
verdict: approve-with-nits
---

# PR Review: label the guns topic Gun control, with named sides Favor gun limits / Favor gun rights

## Summary
This PR changes display copy only. The guns topic now shows as "Gun control" on the home tile, the /stories card, the story eyebrow, the Start button, the tab title, Next story and titles. Its positions say "Favor gun limits" (`mostly_supportive`) and "Favor gun rights" (`mostly_opposed`) where they used to say "Backed / Opposed the gun proposal". The map's "How to read this map" note defines both sides and what isn't counted. Topic id, slug, URLs, data and the classifier are unchanged. The reviewer found no Critical issues, two Important and five Minor. All the Important and Minor findings that apply to this PR are fixed in the follow-up commit. One Important point, that main's classifier lags the stored data, is out of scope and tracked as #1239. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 14 (+~140 / -~60, excluding this review file)
- Areas touched: web_app, web_docs
- Commits:
  - 92acf012 fix(stories): label the guns topic Gun control, with named sides Favor gun limits / Favor gun rights
  - review-fix commit: fix(stories): review fixes for the gun control labels (#1237)
  - plus merges of origin/main (conflict in `topicPositions.test.ts` imports, resolved to keep #1240's quote-note helpers) and the bot's auto-review commit
- Range reviewed: `merge-base(origin/main)..HEAD` (feature commits only)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | success on 8b14b97b; re-checked on the head before merge |
| Documentation Build | success on 8b14b97b |
| Backend Tests | success on 8b14b97b |
| API Types | success on 8b14b97b |
| PR conventions | success |
| Docker Build Test | skipped (no Docker files changed; not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean.
- **Fabricated data:** clean. Only words change. Every count in a title, legend or table still comes from caption-facts or state-map. The definition text restates the classifier question that wrote the stored readings (`question_version` 48468cc5296e).
- **Personal data:** clean. No person is involved.
- **Destructive data changes:** none. No warehouse, seed or dbt change.

## Strengths
- It names both sides instead of a direction that could be read either way, and ties the words to the question that actually wrote the data (checked: 7,036 guns rows, all under `48468cc5296e`).
- It overrides the display name in the web copy layer and leaves the seed alone, with the reason written down. The seed name is denormalized into `meeting_topic_link.link_label` and the browse marts.
- `missingLegend(words)` lets one topic change its missing wording. Every other topic still gets exactly the old `MISSING_LEGEND` string.
- Docs are updated in the same PR, including a dated decision section in `story-captions.md`.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Main's classifier text disagrees with the new words** (`packages/llm/src/llm/typesafe/topic_lean.py:83-92` on main still says "the firearm-related proposal before the body"). Verified: `question_version(TOPICS["guns"])` is `7b0f743c88e3` on main and `48468cc5296e` for the data-writing copy. The UI matches the stored data, but a re-run from main would ask a different question. **Out of scope** (the task keeps the classifier unchanged). It is filed as #1239 and named in the PR body and in `topic-meeting-lean.md`.
2. **The topic_lean guard test could stay skipped forever** (`topicPositions.test.ts`, the `skipIf` keyed on a `sides=` field that `TopicDef` on main lacks). **Fixed:** it now skips only while the old "proposal before the body" wording is present. Once that wording is replaced, under any field names, the test runs and fails unless gun limits are "for" and gun rights "against".

### 🔵 Nits / suggestions (Minor)
3. `QuoteCard.tsx:26-27` doc comment still gave "Public: Opposed the gun proposal" / "Mentions guns" as examples. **Fixed.**
4. `story-captions.md:107,115` quoted the old volume title "took up guns most". **Fixed** to "gun control". The owner's verbatim quote and the dated measurement table are kept as history. `storyCaption.test.ts` now passes `'gun control'` to `captionText`. **Fixed.**
5. `story-captions.md:63-66`: the struck-through #1126 note said "for guns, the proposal before the body". **Fixed:** it is now marked superseded by #1237.
6. Guns says "No reading yet" while the other topics say "No AI reading yet". This follows the owner's spec, so it is kept. The `StoryStatesMap.tsx` comment now says so.
7. The tab title claim was verified in the browser: "Gun control — Data story | Open Navigator". `useDocumentTitle.test.ts` keeps "Guns" as a generic string fixture, which is harmless.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1237 has the four parts; branch `fix/1237-gun-control-labels`; `Closes #1237`; follow-up #1239 filed |
| Conventional Commits | Yes | Co-author trailer on agent commits |
| No fabricated data | Yes | Copy only |
| New Python in `packages/` | n/a | |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label matches filter | Yes | Unchanged; `?state=AL` renders "Alabama is split on gun control" |
| Match evidence on filtered tiles | n/a | |
| Docs | Yes | `guides/data-stories.md`, `development/story-captions.md`, `development/topic-meeting-lean.md` |
| Telemetry and logging | n/a | |
| Tests | Yes | `topicPositions.test.ts` pins the guns words and the note; caption, index and topic-story tests updated |
| Shared libraries | n/a | No `packages/` change |

## Test Coverage
- `npx tsc --noEmit` is clean. `npx vitest run`: 701 passed, 1 skipped (the #1239 guard).
- `npm run build` (web_app) and the Docusaurus build pass. The docs build's broken-link warnings come from other pages and were there before this PR.
- Playwright on /, /stories, /stories/guns and /stories/guns?state=AL at Pixel 7 and 1440x900, against the PR's Vite proxied to API :8001: no visible "Guns", "gun proposal" or "gun measures". The legend reads "Favor gun rights / Favor gun limits / Split / No reading yet, or the public didn't speak on it". The note shows the full definition.

## Verdict
approve-with-nits. Nothing blocking. The remaining Important item (#1239) is a separate classifier commit.
