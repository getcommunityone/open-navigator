---
pr: 982
branch: feat/981-story-stance-continuum
title: "feat(web_app): ask agree/disagree in the story and show where the reader sits; retire the Challenge"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: general-purpose subagent (read-only) and coordinator
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: ask agree/disagree in the story and show where the reader sits

## Summary

Closes #981. The story's contested screens ask the statement their record is about (Agree / Disagree / Not sure). After an
answer, **Where you sit** places the reader among readers (the most specific place at the minimum sample) and, only for
statements that lean to one side, among meeting speakers. The separate Challenge is retired: its links are removed, its
routes redirect to the story, and its page and own components are deleted.

The independent pass said **request-changes**. Every Blocking and Should-fix finding is fixed on the branch, and the
coordinator verified the fixes in a browser.

## Findings and their fixes

### 🔴 Blocking (fixed)
1. **The readers sentence said "here" even when the bar fell back to a wider group.** Fixed:
   - the sentence names the group used ("60% of the 100 readers across the country answered agree, as you did");
   - a 0% own segment reads "None of the N readers … answered … so far".

   Tested.

### 🟡 Should fix (fixed)
- **A saved answer was invisible when the results request failed.** The confirmed answer and its results are now kept
  locally.
- **One global `posting` dropped answers on other screens.** Saving is now tracked per statement.
- **Keyboard focus fell to the page after answering.** It now moves to **Change**, and after Change to the chosen
  answer. Verified in a browser.
- **The charts' "Sources and limits" link pointed at the archived page.** The section now lives in
  `guides/data-stories.md`, updated for the story, with the link repointed. The dev notes point at the archived path.

### 🔵 Nits
- **Fixed:**
  - "Where you sit" is a labelled group;
  - the **You** label hangs inward at the bar's ends;
  - the dead `/challenge` tab check is gone;
  - an unknown minimum sample no longer prints "once 0 have answered".
- **Open:**
  - `/challenge/:packId` assumes each pack has a story (true for the only pack);
  - challenge-only helpers in `stanceGame.ts` could be pruned;
  - the `speaker_lean` mapping is an editorial call, recorded with its reason on the decision page.

## Scans
- Secrets, personal data, destructive changes: none. The deleted code is the retired Challenge page; no data is deleted.
- Fabricated data: none. Every bar comes from real counts. No split is shown below the minimum sample, and there is no
  speaker line without a lean.

## Tests
- **pytest** `tests/test_stance_api.py`: 49 passed.
- **Frontend:** vitest 404 passed; `tsc` is clean; eslint has no new warnings. Docs build OK; no broken links on the
  touched pages.
- **Browser** (answer POST intercepted; no rows written):
  - the statement, answer and Where you sit render;
  - focus lands on Change after answering;
  - `/challenge/data-centers?state=TX` → `/stories/data-centers?state=TX`.

## Verdict

**approve-with-nits**: merge when the required checks are green.
