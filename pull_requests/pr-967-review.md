---
pr: 967
branch: fix/966-stories-sound-cues
title: "fix(web): play Data Stories sound cues while reading"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
verdict: approve
---

# PR Review: fix(web): play Data Stories sound cues while reading

## Summary

Fixes #966: Data Stories showed **Sound on** but almost never played audio. Soft `open` cues now fire on screen advance and the first idle nudge; `AudioContext.resume()` is awaited before scheduling so the first cue after unlock is not dropped. Docs match. Unit tests cover the resume path.

## Scope of Change

- Files changed: 5
- Areas touched: web_app / web_docs
- Commits: `b2c3293c` fix(web): play Data Stories sound cues while reading
- Range reviewed: `origin/main..HEAD`

## CI Status

See PR checks on the head commit.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean
- Fabricated data: clean
- Personal data: clean
- Destructive data: clean

## Strengths

- Matches challenge idle-nudge sound pattern without making the story loud.
- Resume-before-schedule fixes a real silent-first-cue bug.

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
| Issue first | yes | `fix/966-…`, Closes #966 |
| Conventional Commits | yes | |
| Tests | yes | `stanceSound.test.ts` resume case |
| Docs | yes | |

## Test Coverage

`npx vitest run src/utils/stanceSound.test.ts` — 9 passed.

## Verdict

**approve** — merge when required CI is green.
