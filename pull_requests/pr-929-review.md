---
pr: 929
branch: fix/928-heading-local-meetings
title: "fix(web_app): head Data Stories with what local meetings in a place said, and spell out a count label"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: da2610738ff321336a5bfdcad6f3f1724af83f55
verdict: approve-with-nits
---

# PR Review: fix(web_app): head Data Stories with what local meetings in a place said, and spell out a count label

## Summary

Copy only: the Data Stories heading becomes What did local meetings in [place] say about [topic]?, and the hub's agenda count label says a data center where it said one.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `web_app/src/pages/DataStories.tsx`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/utils/dataStory.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

Required checks are read on the head commit before merge. Locally: tsc clean, vitest passed, build ok.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. Fabricated data: none. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- The heading was checked at two phone sizes and desktop; the count label was changed afterwards and not re-shot. On desktop the counts sit in a row, so the longer label may wrap to three lines there.
- The stat row on desktop was not looked at with the new label.

## Verdict

**approve-with-nits**
