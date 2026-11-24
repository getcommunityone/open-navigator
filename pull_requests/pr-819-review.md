---
pr: 819
branch: feat/818-public-comment-checks
title: "feat(llm): add automated checks for public-comment stance rows"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: python-packages-specialist subagent (read-only, ran the module) and coordinator
verdict: approve-with-nits
---

# PR Review: feat(llm): add automated checks for public-comment stance rows

## Summary
Adds a package CLI that checks `public_participation[]` rows against the transcript: quotes must be found, a quote that
states a side must agree with the stance, and heat must be consistent with the words. The first review pass at
`41168ea1` returned **request-changes**: the reviewer ran about 80 quotes through the module and found five blocking
defects, all in the module's core job (it misread negations, mixed statements and questions, and crashed on a
non-text stance). The matching was rewritten so that any quote without one safe reading counts neither way, and every
reported input is now a regression test. With those fixes the verdict is approve-with-nits. It has not run on a real
analysis, because none carries these rows yet.

## Scope of Change
- Files changed: 3 (excluding this review)
- Areas touched: packages (llm) / web_docs
- Commits: `ac1c159d`, `41168ea1`, plus the review-fix commit that carries this file
- Range reviewed: `origin/main...origin/feat/818-public-comment-checks` at `41168ea1`; fixes verified by the coordinator

## CI Status
| Check | Status |
|---|---|
| Frontend Build, Documentation Build, Backend Tests, API Types | Read on the commit that carries this file before merging. |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean. Test transcripts are constructed and live only in the test file.

## Strengths
- No network, database or model call; exit codes for bad input were confirmed by running them.
- Logging survives braces and extra keys in findings.

## Findings
### 🔴 Blocking (Critical)
All fixed on the branch, each with regression cases in `test_side_from_quote` and neighbours.
1. Negation did not scope: "We don't oppose; we support" read against; "I'm not sure I support" read against. Fixed: a
   negator must sit directly before the phrase (one adverb allowed), and hedges, conditions and alternatives return None.
2. Negation was ignored for "vote no", "deny", "reject", "pass": "please do not deny this" read against, "do not pass
   this" read for. Fixed: every rule takes a negator.
3. Mixed statements took the first matching rule: "I support this but I oppose the amendment" read against. Fixed: all
   matches are collected and conflicting sides return None; "but" alone also returns None.
4. A question containing a side word read as a stance: "Why should I support this?" read for. Fixed: any quote with a
   question mark is a question or None, before the side rules.
5. A non-text `stance` raised `AttributeError` and aborted the run. Fixed: non-text values are an unrecognised stance.

### 🟡 Should fix (Important, non-blocking)
All fixed.
6. `quote_found("no", "I know")` was True. Fixed: whole-word matching, and quotes under three words are not counted.
7. Non-ASCII letters were dropped, so a Spanish or Cyrillic quote was reported missing. Fixed: Unicode-aware, accents stripped.
8. "1,000" vs "1000", apostrophes, `...` and `[inaudible]` in a quote caused false misses. Fixed: digit groups joined,
   apostrophes dropped, elided quotes matched part by part in order.
9. "I cannot oppose enough" read for. Fixed: "enough" returns None.
10. `_heat(True)` returned 1. Fixed.
11. The prompt-vocabulary test parsed by string split and checked one direction. Fixed: regex with an explicit
    assertion, and set equality with the module's buckets.
12. Tests covered only easy phrases. Fixed: 51 tests, including every input above.

### 🔵 Nits / suggestions (Minor)
- One flip in one quote failed the bar. Changed: the flip-rate bar applies from 20 side-stating quotes, and the CLI
  adds several analyses into one report; an invented quote still fails at any size.
- `_HOT` matched a neutral "lawsuit" and read the model's summary. Changed: threats only, and only the quoted words.
- Left as is: the rule set is narrow ("I'm for this" is not recognised); check 2 ignores rows whose stance is neutral
  or a question, now stated in the docstring.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #818 with the four parts; branch `feat/818-public-comment-checks`; `Closes #818` |
| Conventional Commits | Yes | |
| No fabricated data | Yes | |
| New Python in `packages/` | Yes | A `python -m llm.gemini.public_comment_checks` CLI |
| dbt for transformations | Yes | The five-value bucket mirror is for checking files before load; the dbt macro stays the warehouse's source, and a test ties both to the prompts |
| Docs | Yes | `web_docs/docs/development/meeting-sentiment-design.md`, "Checks" |
| Telemetry and logging | Yes | loguru |
| Tests | Yes | 51 constructed cases |
| Shared libraries | Yes | `packages/llm` tests run |

## Test Coverage
`pytest packages/llm/tests/test_public_comment_checks.py packages/llm/tests/test_part1_public_participation.py` passes;
`ruff check` on the two new files is clean. Not run: any real analysis.

## Verdict
approve-with-nits. Nothing must change first. Expect to tune the phrase rules after the pilot shows real quotes.
