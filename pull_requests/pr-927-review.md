---
pr: 927
branch: fix/926-chat-wide-search-speed
title: "perf(chat): search a sentence's terms with one combined text query"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 20dec58bfad7521434275857faa56bd20be0576e
verdict: approve-with-nits
---

# PR Review: perf(chat): search a sentence's terms with one combined text query

## Summary

The wider chat search from #923 took over a minute on the live site because it probed decisions once per meeting per term. It now builds one combined text query from the terms and uses it like the typed search, so the decision lookup is planned as a join. On a local table of 15,000 meetings and 80,000 decisions the data-centers sentence went from 59 s to about 3 s.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `api/routes/chat_meetings.py`
- `tests/test_chat_meetings.py`
- `web_docs/docs/development/meeting-chat-model.md`

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

- Times are from a synthetic local table; production times are confirmed only after deploy.
- The meaning of all_terms narrows: all terms in the meeting's own text, or all in one decision. A meeting with one term in its summary and the other only in a decision no longer matches at that step and falls to any_term.
- A sentence that matches nothing still runs two wider passes, about 5 s locally. A stored tsvector column with an index is the follow-up.
- #923 shipped without a production-scale timing; the PR body there said so, and this is the cost of that gap.

## Verdict

**approve-with-nits**
