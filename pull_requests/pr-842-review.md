---
pr: 842
branch: fix/840-meeting-type-unpublished
title: "fix(api): answer with a null meeting type when its relation is not published"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: c012fa85975ff9937c982ee9562522c21c3d8eba
verdict: approve
---

# PR Review: fix(api): answer with a null meeting type when its relation is not published

## Summary

Automated review (#648) for PR #842 on `fix/840-meeting-type-unpublished`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/meeting_type.py`
- `api/routes/decision_browse.py`
- `api/routes/decisions.py`
- `api/routes/meetings.py`
- `tests/test_meeting_type_797.py`
- `web_docs/docs/development/meeting-type-label.md`

## CI Status

See the PR checks on `c012fa85975f`.

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
