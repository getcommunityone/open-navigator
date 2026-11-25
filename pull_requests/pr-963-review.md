---
pr: 963
branch: fix/962-stories-hub-compact
title: "fix(web): tighten Data Stories hub title, compact stats, hide empty voices"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
verdict: approve
---

# PR Review: fix(web): tighten Data Stories hub title, compact stats, hide empty voices

## Summary

Hub-only UX for #962: shorter sentence title, no National on the counts row under United States, compact key counts so Start fits the first viewport, and the empty "Who spoke up / not loaded yet" block omitted until positions figures exist. Docs updated. No blocking findings.

## Scope of Change

- Files changed: 3
- Areas touched: web_app / web_docs
- Commits: `aecf6972` fix(web): tighten Data Stories hub title, compact stats, hide empty voices
- Range reviewed: `origin/main..HEAD`

## CI Status

See PR checks on the head commit.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean
- Fabricated data: clean
- Personal data: clean
- Destructive data: clean

## Strengths

- Empty not-loaded filler no longer steals the first viewport.
- Care-first hook stays the lead; voices appear only as real evidence.
- Story path still shows the quiet not-loaded line (hub-only change).

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | `fix/962-…`, Closes #962 |
| Conventional Commits | yes | |
| Scope label matches filter | yes | National not repeated under United States |
| No fabricated data | yes | |
| Docs | yes | |

## Test Coverage

Presentation copy/CSS; local `npx tsc --noEmit` passed. CI Frontend/Docs gate the change.

## Verdict

**approve** — merge when required CI is green.
