---
pr: 1298
issue: 1289
verdict: approve-with-nits
---

# PR Review: fix(stories): displays fit the amount of data; stance headline agrees with recorded votes

## Summary
The PR checks the story's stance headline against recorded votes and hand-counted speakers. Below 3 decisions and 5
speakers, the title becomes "Not enough recorded activity to say." with the facts. A side opposite the votes becomes
"divided". One shared rule (`pickDisplay`) picks each panel's figure from its count, and the speaker wording no longer
contradicts itself. A read-only reviewer (subagent, against this rubric, `AGENTS.md` and `CLAUDE.md`) found two
should-fix issues; both are fixed in the second code commit, along with most nits. Verdict: approve-with-nits. The owner
should still confirm the national title change before merge (see Notes).

## Scope of Change
- API: `api/routes/topic_caption_facts.py`, which adds `speakers.meetings_reviewed` and `votes`; its test.
- Web: `utils/storyCaption.ts`, `utils/stanceEvidence.ts` (new), `utils/displayFit.ts` (new), `utils/dataStory.ts`,
  `utils/stanceGame.ts`, `components/stance/{FitDisplay (new), ChartPanel, PositionsBlock, StoryScreenView, TimelineChart}`,
  `pages/DataStory.tsx`, `styles/stance.css`; `ConcernsDumbbell.tsx` removed (unused).
- Docs: `story-captions.md` (a new decision) and `story-display-fit.md` (new).

## CI Status
| Check | Status |
|---|---|
| Local: vitest | 773/773 passed |
| Local: tsc --noEmit | clean |
| Local: pytest tests/test_api_topic_caption_facts.py | 19/19 passed |
| GitHub required checks | pending at the time of writing |

## Scans (secrets, fabricated data, personal data, destructive data changes)
No secrets. No fabricated data: every number on screen comes from an API count, and a missing count reads "—" or "not
available yet", never a stand-in. No personal data. No data or warehouse changes; the API reads one more sum from an
existing mart.

## Strengths
- The tests were written first, one per rule row, and one test fails if any headline disagrees with the votes across a
  grid of fixtures.
- There is one display rule with named thresholds; no panel makes its own choice.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- ~~`stanceEvidence.ts` `belowStanceMinimum`: a data-center scope with nothing reviewed (both null) escaped the
  minimum.~~ **Fixed:** the minimum now applies whenever the server reports `votes`, with null counted as none. There is a
  new test.
- ~~`TimelineChart.tsx`: the line/sentence choice counted the share series but printed the counts.~~ **Fixed:** it now
  reads the counts series.
### 🔵 Nits / suggestions (Minor)
- ~~Speakers on record but `meetings_reviewed` missing read "not available".~~ Fixed ("N public speakers on record").
- ~~The lead stated a capped list as a total.~~ Fixed ("At least N …" when there is no whole-scope total).
- ~~`aria-label` on `<dd>`.~~ Fixed (visually hidden "not available yet").
- ~~`ConcernsDumbbell.tsx` unused.~~ Removed.
- ~~An `insufficient` basis repeats the AI reading with `ai: false`.~~ Fixed (`ai` is true when the reading is included).
- Open: summed votes treat "passed" as "for" (a passed moratorium reads as support). This is documented as a caveat in
  story-captions.md and flagged for the owner in the PR body.

## Repo-Rule Compliance
| Rule | Status | Note |
|---|---|---|
| Issue first, four parts | ✅ | #1289 |
| Branch / `Closes #` | ✅ | `fix/1289-story-display-fit` |
| Conventional Commits | ✅ | |
| No fabricated data | ✅ | Missing counts read "—"; no invented zeros |
| Scope label matches filter | ✅ | Unchanged; the insufficient title keeps the place control in its subhead |
| Docs with the change | ✅ | story-captions.md, story-display-fit.md |
| New Python in packages/ | n/a | API route only |

## Test Coverage
Every rule-table row, the vote-agreement check, the minimum (both sides of each threshold), the nothing-reviewed case,
the older-server case (the existing fixtures) and the API fields including a real 0.

## Verdict
approve-with-nits. Notes for merge: the national title changes from "America hates data centers." to "America is divided
on data centers." (votes 79–10 for), and the vote-direction proxy needs owner confirmation. The PR body asks the owner to
confirm both before merge.
