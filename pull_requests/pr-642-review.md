---
pr: 642
branch: feat/640-vote-phrase-spot
title: "feat(llm): phrase-spot vote cues into bronze.transcript_vote_phrase"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: feat(llm): phrase-spot vote cues into bronze.transcript_vote_phrase

## Summary

Implements #640: regex spotting of stock motion/vote phrases over Part 1 caption segments, idempotent loads into `bronze.transcript_vote_phrase` (metadata only—no transcript text in Postgres), optional spaCy candidate JSONL under gitignored `data/cache/`, and a scorer CLI measuring ±60s recall against Gemini `media_anchor`. New code lives in `packages/llm` with nine unit tests; required CI is green. Mandatory scans are clean (env var names only; no api/web_app served paths; no cache deletions). **Approve with nits**—broad `vote_cast` yes/no patterns may add noise until tuned.

## Scope of Change
- Files changed: 15 (+1893 / -0)
- Areas touched: packages/llm, web_docs, .gitignore
- Commits: 10 through `51068448` fix(llm): whole-branch review fixes for vote-phrase spotting
- Range reviewed: merge-base..HEAD (including prior review commit)

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass |
| Documentation Build | pass |
| Backend Tests | pass |
| API Types | pass |
| PR conventions | pass |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean
- Fabricated data (api/web_app served paths): clean
- Personal data: clean (public records; cache paths gitignored)
- Destructive/bulky data: clean

## Strengths
- Meets issue contract: CLIs as `python -m llm.ner.*`, explicit bronze PK, sha-idempotent replace.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- `phrases.py` `\byes\b` / `\bno\b` may over-match casual speech; narrow when scorer miss JSONL is reviewed.

### 🔵 Nits / suggestions (Minor)
- Unused `sys` import in `spot_vote_phrases.py` (ruff F401).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Closes #640 |
| New Python in packages/ | Yes | |

## Test Coverage
`test_vote_phrases.py` (9 tests); Backend Tests CI pass.

## Verdict
**Approve with nits** — pilot is safe to merge; tune `vote_cast` patterns after scorer review.