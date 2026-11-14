---
pr: 319
branch: fix/318-whisperx-token-arg
title: "fix(llm): build WhisperX's diarization pipeline with the token argument it takes"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: fix(llm): build WhisperX's diarization pipeline with the token argument it takes

## Summary

The diarization pipeline is built with token= and falls back to use_auth_token=; the guide names the current gated
model. 3 new tests. Closes #318. Approve.

## Scans

Secrets: clean. Fabricated data: none. Costs are labelled estimates from Modal's published rate, dated; no transcript text is logged. Personal data: none. Destructive changes: none.

## Findings

None blocking, none to fix.

None.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #318 with four parts |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in packages/ | Yes | `llm.gpu`, run with modal run |

## Verdict

Approve once the required checks are green.
