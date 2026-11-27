---
pr: 1327
branch: feat/1320-decision-supporters
title: "feat(stories): who supported and opposed each decision, and its vote, on the Decisions screens"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: github-actions
head_sha: 2004d18507a4c70de197b057b9bc1f195e912aa5
verdict: approve
---

# PR Review: feat(stories): who supported and opposed each decision, and its vote, on the Decisions screens

## Summary

Automated review (#648) for PR #1327 on `feat/1320-decision-supporters`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/routes/data_centers.py`
- `api/routes/decision_people.py`
- `api/routes/topics.py`
- `tests/test_api_decision_people.py`
- `tests/test_api_topic_said.py`
- `web_app/src/api/dataCenters.ts`
- `web_app/src/api/topics.ts`
- `web_app/src/components/stance/FitDisplay.tsx`
- `web_app/src/components/stance/TopicRecordCards.tsx`
- `web_app/src/styles/topic-story.css`
- `web_app/src/utils/saidCards.test.ts`
- `web_app/src/utils/saidCards.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_docs/docs/guides/data-stories.md`

## CI Status

See the PR checks on `2004d18507a4`.

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
