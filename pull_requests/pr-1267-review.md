---
pr: 1267
issue: 1265
branch: fix/1265-dc-story-map-stance-line
title: "fix(stories): Data Center Story map cards show the public-stance line"
reviewed_at: 2026-11-27
reviewer: claude (pr-review)
verdict: approve
---

# PR Review: fix(stories): Data Center Story map cards show the public-stance line

## Summary

This is a small follow-up to #1240, found in its live check. The Data Center Story's national dot map and state county
map rendered `QuoteCard` without `stanceNote`, so their cards had no "Public: …" line while the home and topic maps did.
The PR passes `dataCenterQuoteNote(passage.ai_public_lean)` in both places. It adds `ai_public_lean` to `MapPassage`;
the API already serves that field. A live check confirmed the change: Alabama (Coffee County, Jun 9 2026) now reads
"Public: Against data centers". Approve.

## Scope of Change

- `web_app/src/components/stance/StoryDotMap.tsx`: `MapPassage.ai_public_lean`, plus the `stanceNote` prop.
- `web_app/src/components/stance/StoryCountyMap.tsx`: the `stanceNote` prop.
- `web_docs/docs/guides/data-stories.md`: one clause in the #1230 section.

## CI Status

| Check | State |
|---|---|
| PR conventions | pass |
| CI - Build & Test | merge waits for green on the head commit |

## Scans (secrets, fabricated data, personal data, destructive data changes)

No secrets. No fabricated data: the line only restates the existing `ai_public_lean`, and the audit-only readings get
no line. No personal data. No data changes.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
None.

## Repo-Rule Compliance

| Rule | Status | Note |
|---|---|---|
| Issue first, four parts | ✅ | #1265 |
| Branch / PR naming, `Closes #` | ✅ | |
| Docs in the same PR | ✅ | data-stories.md |
| No Fabricated Data | ✅ | |

## Test Coverage

tsc and vitest (717) pass. `dataCenterQuoteNote` is unit-tested in `topicPositions.test.ts` (from #1240). The live
browser check was done before and after (screenshots in the session scratchpad).

## Verdict

**approve**
