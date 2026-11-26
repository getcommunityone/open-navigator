---
pr: 974
branch: feat/969-challenge-scroll-reveal
title: "feat(web): Challenge scroll-to-answer and scroll reveal"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator (SDD final approve-with-nits + snap fix)
verdict: approve-with-nits
---

# PR Review: Challenge scroll-to-answer and scroll reveal

## Summary

Implements #969: three full-viewport stops per challenge round (Finding → Question with stacked answers → Reveal), `useActs.goToStop`, snap fence on stop holds, docs. Opinion-only; no quiz framing. Final SDD review was approve-with-nits; snap stop fencing was fixed in `0b4f91f2`. Manual phone QA still recommended.

## Scope of Change

- Areas: web_app (RoundPanel, useActs, Challenge, stance.css, stanceGame), web_docs
- Closes #969

## Scans

- Secrets / fabricated data / personal / destructive: clean

## Findings

### 🔴 Blocking

None.

### 🟡 Should fix

None blocking merge. Manual wide/phone/reduced-motion smoke still valuable after deploy.

### 🔵 Nits

- Deferred: extra roundStop test case; stop-aware onSettled focus; useActs unit tests.

## Verdict

**approve-with-nits** — merge when required CI is green.
