---
pr: 1046
branch: fix/1045-lenses-auto-window
title: "fix(web_app): home Contested and Raised Eyebrows open on the newest window that has decisions"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: ccceaf4d01c5fb31b049161f4e4309f4accfe2db
verdict: approve
---

# PR Review: fix(web_app): home Contested and Raised Eyebrows open on the newest window that has decisions

## Summary

Automated review (#648) for PR #1046 on `fix/1045-lenses-auto-window`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/pages/HomeV9.tsx`
- `web_docs/docs/development/code-walkthrough.md`

## CI Status

See the PR checks on `ccceaf4d01c5`.

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

## Agent review

- Scans: no secrets, no fabricated data, no personal data, no data changes.
- Correctness: the lenses ask for window=auto until the reader picks a period; the highlighted chip and the empty-state wording come from the response's window, so label and cards match (scope-label rule). Picking a chip sends that window, as before. Checked in the browser at /?state=AL: Past year highlighted with real contested cards.
- Docs: code-walkthrough.md.

No blocking findings.
