---
pr: 1471
issue: 1444
branch: feat/1444-officials-heard
title: "feat(dbt): officials heard most recently per body from roster-matched chair calls"
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve-with-nits
---

# PR #1471 review

Reviewed against `.claude/review-rubric.md`.

## Summary

Adds a deterministic caption extractor for roster officials named by the chair or clerk at the moment they speak
(roll call, chair handoff, self-introduction) and the `body_recent_speaker` mart. Runs locally: 212 body x member rows
in 46 places; Tuscaloosa's mayor and four council members with working jump links. Approve with nits.

## Scans

- Secrets: clean. Fabricated data: clean (counts and dates come from caption matches; nothing is estimated).
- Personal data: only officials on a roster can match (unknown surnames never match; shared surnames need a first
  name); residents never appear because every row joins `body_membership`. `matched_text` is at most 120 characters
  of a public meeting caption around an official's title and name, kept in bronze only.
- Destructive data changes: the extractor replaces its own rows per video it re-scans; nothing else.

## Findings

### 🔴 Blocking
None.

### 🟡 Should fix
None.

### 🔵 Nits
- Caption misspellings of surnames ("Laneir", "Eatman") are missed; recall over precision is the right trade here but
  worth a note (it is in the decision page).
- A "Moved and seconded by Mr. Lanier. Yes." moment is labelled `roll_call`; he did speak (moved), so "heard" holds.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first, naming | Yes | #1444 |
| New code in packages; no paid LLM | Yes | regex only |
| Never infer an official from speech alone | Yes | roster-only pattern, tested (`test_name_not_on_roster_never_matches`) |
| PK/FKs | Yes | contract enforced, relationships test |
| Docs with the change | Yes | decision page section |

## Test Coverage

pytest 7 passed on real caption phrasings; `dbt test -s body_recent_speaker` PASS=17.

## Verdict

approve-with-nits.
