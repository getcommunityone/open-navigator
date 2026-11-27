---
pr: 1366
branch: feat/1346-story-nonprofits
title: "feat(stories): Who's working on this \u2014 the scope's nonprofits on a topic story"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: claude (read-only reviewer subagent + author verification)
head_sha: 6392d17136cb150a5f176d9ac751e119570cb6c2
verdict: approve-with-nits
---

# PR Review: feat(stories): Who's working on this — the scope's nonprofits on a topic story

## Summary

Automated review (#648) for PR #1366 on `feat/1346-story-nonprofits`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/api/topicOrganizations.ts`
- `web_app/src/components/stance/NonprofitsPanel.css`
- `web_app/src/components/stance/NonprofitsPanel.tsx`
- `web_app/src/hooks/useTopicOrganizations.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/pages/TopicStory.tsx`
- `web_app/src/utils/dataStory.test.ts`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/topicOrganizations.test.ts`
- `web_app/src/utils/topicOrganizations.ts`
- `web_app/src/utils/topicStoryScreens.test.ts`
- `web_app/src/utils/topicStoryScreens.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `6392d17136cb`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Inherited from #1365 (lower-cased quote, nested marks): fixed in the mart. The panel renders `match_text` with `highlightSnippet`.

### 🔵 Nit (Minor)

- Fixed: for a name match the marked name was never shown. The panel now quotes `match_text` for every method except the IRS category.
- Checked: the scope label and the query move together (TopicStory is state-grain and passes the state only; DataStory passes the city and labels it), hooks run before any return, and list keys are `master_org_id`.
- Fixed during the Playwright pass: on a phone, `useScreenFit` hid the list behind "More" because the count bars came first. The list now comes first and three rows show.

## Verdict

**approve-with-nits**: no blocking findings. The should-fix items were fixed on the branch.
