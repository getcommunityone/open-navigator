---
pr: 1340
branch: feat/1330-all-positions-evidence
title: "feat(stories): stance evidence counts every recorded position, public and official, and headlines where they disagree"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: b67eaf5389aaf90214b4c0558edaec072f7e4306
verdict: approve
---

# PR Review: feat(stories): stance evidence counts every recorded position, public and official, and headlines where they disagree

## Summary

Automated review (#648) for PR #1340 on `feat/1330-all-positions-evidence`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_center_drill.py`
- `api/routes/topic_caption_facts.py`
- `tests/test_api_data_center_drill.py`
- `tests/test_api_topic_caption_facts.py`
- `web_app/src/api/storyDrill.ts`
- `web_app/src/api/topics.ts`
- `web_app/src/components/stance/KpiDrill.tsx`
- `web_app/src/components/stance/PositionsBlock.tsx`
- `web_app/src/components/stance/PositionsSummary.tsx`
- `web_app/src/lib/api.types.ts`
- `web_app/src/pages/DataStory.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/stanceEvidence.ts`
- `web_app/src/utils/stanceHeadline.test.ts`
- `web_docs/docs/development/story-captions.md`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `b67eaf5389aa`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**
