---
pr: 923
branch: fix/922-chat-sentence-search
title: "fix(chat): find meetings for a question asked as a sentence"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: f5693ebf3a701c2bea792a9b0659fcdcea8e12b8
verdict: approve-with-nits
---

# PR Review: fix(chat): find meetings for a question asked as a sentence

## Summary

The chat search matched the whole question as one string, so a sentence found nothing. It now falls back to the question's content words: all of them, then any of them ranked by how many a meeting matches, with terms passed as one array parameter. The response carries how it matched, and the model is told when the match was loose.

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

- The queries were run against a throwaway Postgres 16 with a handful of rows, which caught an invalid ORDER BY in the first draft. Speed on the production table is unmeasured; the wider steps have no index and run only after the typed search finds nothing.
- The stop-word list is hand-picked. A real topic word that is also civic filler (for example a question about a county board itself) is dropped; a quoted phrase is the way around it.
- The page does not show the match kind to the visitor yet.
- Answer quality on real questions is unverified until deploy.

## Verdict

**approve-with-nits**
