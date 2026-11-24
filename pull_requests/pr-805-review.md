---
pr: 805
branch: feat/797-meeting-type-label
title: "feat(web): show the meeting type on decision cards, decision detail and meeting pages"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: f3a6cca02616d803243ad6904ffae450780318ea
verdict: approve
---

# PR Review: feat(web): show the meeting type on decision cards, decision detail and meeting pages

## Summary

Automated review (#648) for PR #805 on `feat/797-meeting-type-label`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/meeting_type.py`
- `api/routes/decision_browse.py`
- `api/routes/decisions.py`
- `api/routes/lenses.py`
- `api/routes/meetings.py`
- `tests/test_meeting_type_797.py`
- `web_app/src/components/StoryLenses.tsx`
- `web_app/src/components/storyLensesMeetingType.test.ts`
- `web_app/src/pages/DecisionDetail.tsx`
- `web_app/src/pages/MeetingDetail.tsx`
- `web_docs/docs/development/meeting-type-label.md`

## CI Status

See the PR checks on `f3a6cca02616`.

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
