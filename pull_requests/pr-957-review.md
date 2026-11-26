---
pr: 957
branch: fix/954-stories-hub-lede
title: "fix(web): tighten Data Stories hub title and care-first lede"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator (refined automated #648)
head_sha: a20cb2098dd3bc1f1d87f0b932fc6c1fd08156d5
verdict: approve
---

# PR Review: fix(web): tighten Data Stories hub title and care-first lede

## Summary

Tightens `/stories` hub UX for #954: the place/topic sentence is clamped to two lines with smaller type, the card drops the repeated "Data centers" title for a care-first hook, and the lede prompts **Start the story** instead of saying "overview". Docs hub paragraph matches. Small, scoped copy/CSS change; no blocking findings.

## Scope of Change

- Files changed: 3 (+26 / -15, excluding generated)
- Areas touched: web_app / web_docs
- Commits: `a20cb209` fix(web): tighten Data Stories hub title and care-first lede
- Range reviewed: `7c87b392..a20cb209`

## CI Status

See the PR checks on the head commit.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean
- Fabricated data in a served path: clean (no hard-coded counts; lede uses scope label only)
- Personal data: clean
- Destructive or bulky data changes: clean

## Strengths

- Matches Done when on #954 (two-line title, no double topic, care-first Start prompt).
- Docs updated in the same PR.
- CSS clamp + font-size reduction is a light, reversible fix.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- `web_app/src/pages/DataStories.tsx`: StatRow still says "What the data center records cover" — fine for the counts row; not a second title. No change required.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | yes | `fix/954-…`, Closes #954, issue has four parts |
| Conventional Commits | yes | |
| No fabricated data | yes | |
| Docs | yes | `web_docs/docs/guides/data-stories.md` |
| Scope label matches filter | yes | unchanged; label still drives lede place |
| Tests | n/a | copy/CSS only; behaviour contract unchanged |

## Test Coverage

No new automated test (presentation copy). Local: `npx tsc --noEmit` in `web_app` passed. CI Frontend/Docs builds gate the change.

## Verdict

**approve** — merge when required CI is green on the head commit.
