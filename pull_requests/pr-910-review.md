---
pr: 910
branch: feat/899-challenge-quiz-pacing-sound
title: "feat(web_app): pace each Data Center Challenge round in three beats, with sound"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 8086597c3831c86e0ca309fd6540c80a08d5d01a
verdict: approve-with-nits
---

# PR Review: feat(web_app): pace each Data Center Challenge round in three beats, with sound

## Summary

Each challenge round now plays in three beats: what the record shows (no answer buttons rendered), then Where do you stand with Agree, Disagree, Not sure, then the results landing one scope at a time. Sound cues are synthesized with Web Audio after the first gesture, with a remembered on/off control. Per the owner's correction, nothing implies a right or wrong answer, and an optional both-sides quote block is ready for #900 to feed.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `web_app/src/components/stance/ResultBars.tsx`
- `web_app/src/components/stance/RoundPanel.tsx`
- `web_app/src/components/stance/ScopeBar.tsx`
- `web_app/src/components/stance/SidesBlock.test.tsx`
- `web_app/src/components/stance/SidesBlock.tsx`
- `web_app/src/components/stance/SoundToggle.tsx`
- `web_app/src/components/stance/useActs.ts`
- `web_app/src/components/stance/useAskTimer.ts`
- `web_app/src/pages/Challenge.tsx`
- `web_app/src/styles/stance.css`
- `web_app/src/utils/stanceBeat.test.ts`
- `web_app/src/utils/stanceGame.ts`
- `web_app/src/utils/stanceSound.test.ts`
- `web_app/src/utils/stanceSound.ts`
- `web_docs/docs/development/where-you-stand-game-design.md`
- `web_docs/docs/guides/data-center-challenge.md`

## CI Status

Required checks are read on the head commit before merge. Locally: tsc clean, vitest passed, build ok.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. Fabricated data: none. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- Nobody has heard the audio; scheduling and note counts are verified, the sound itself needs the owner's ear.
- SidesBlock is unit-tested only and has not been seen in a real round on a phone; verify when #900 wires it.
- On phones the chart is hidden in beats 2 and 3 so the round fits one screen.
- On phones ?round=N does not scroll to that round; this predates the change and needs its own issue.
- With no rows for a place, the beat 1 title is the chart caption, not a finding sentence.

## Verdict

**approve-with-nits**
