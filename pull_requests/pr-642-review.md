---
pr: 642
branch: feat/640-vote-phrase-spot
title: "feat(llm): phrase-spot vote cues into bronze.transcript_vote_phrase"
author: jcbowyer
reviewed_at: 2026-11-20
reviewer: independent-subagent (composer) + coordinator request
verdict: approve-with-nits
---

# PR Review: feat(llm): phrase-spot vote cues into bronze.transcript_vote_phrase

## Summary

This PR closes #640 by adding regex-based vote/motion phrase spotting in `packages/llm`, landing hits in
`bronze.transcript_vote_phrase` without caption text, optional spaCy candidate JSONL under `data/cache/`, and a scorer CLI
that measures ±60s recall against Gemini Part 1 `media_anchor` timestamps. The design matches the issue contract (CLI
entry points, table grain/PK, idempotent `file_sha256` replace, run report with ~200k linear estimate). Unit tests cover
spotting, estimates, anchor merge, clustering, and scoring. Local `pytest packages/llm/tests/test_vote_phrases.py` passed
(9/9); CI on `51068448` is green. No blocking scan findings. Verdict: **approve-with-nits** — ship the pilot; tighten
`vote_cast` patterns when scorer noise shows up.

## Scope of Change

- Files changed: 14 (+1769 / -0, excluding generated files)
- Areas touched: packages/llm, web_docs, .gitignore
- Commits:
  - `b74f0330` docs(llm): vote phrase spotting design and implementation plan
  - `b5f773af` feat(llm): spot stock vote/motion phrases in caption segments
  - `6bb916b8` feat(llm): bronze.transcript_vote_phrase store with sha replace
  - `99998196` feat(llm): CLI spot_vote_phrases over Part 1 meetings
  - `bfc115b9` feat(llm): optional spaCy vote-phrase candidate JSONL
  - `39685ad7` feat(llm): score vote-phrase hits against Gemini media anchors
  - `0062954a` fix(llm): ensure bronze table exists before score CLI
  - `14d23743` docs(llm): how to run vote phrase spotting and scoring
  - `51068448` fix(llm): whole-branch review fixes for vote-phrase spotting
- Range reviewed: `bc27a719..51068448`

## CI Status

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean. Diff references `OPEN_NAVIGATOR_DATABASE_URL` and Gemini only by name; no keys or credentialed URLs.
- **Fabricated data in a served path:** clean. No `api/` or `web_app/src/` changes; bronze rows store codes and offsets
  only; CLI estimates are derived from the current run (with a documented 120-byte fallback when the table is empty on
  dry-run).
- **Personal data:** clean. Public meeting transcripts and decisions; cache JSONL is under gitignored `data/`.
- **Destructive or bulky data changes:** clean. No `data/cache/` deletions or large binaries committed; bronze writes are
  scoped DELETE-by-`file_sha256` then INSERT (pilot loader pattern).

## Strengths

- Issue contract is met: singular table name, no text columns, PK on `(file_sha256, phrase_code, start_seconds,
  `char_offset)`, both CLIs as `python -m llm.ner.*`, docs at `vote-phrase-spotting.md` with sidebar entry.
- Idempotent `replace_hits` and `ensure_table` mirror `llm.typesafe.screen_transcripts` as #640's "Read first" asked.
- Scorer prefers `event_decision`-linked analyses with Part 1 fallback only for gaps (`merge_anchor_rows`).
- Miss JSONL enriches with `nearby_lines` for debugging without storing text in bronze.
- Nine focused unit tests; PR conventions and required CI checks pass on head.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

1. **`packages/llm/src/llm/ner/phrases.py:64-69` — `vote_cast` patterns `\byes\b` and `\bno\b` are very broad.** They
   will match casual speech in captions, inflating hit counts and making ±60s recall look better or noisier than vote-only
   signal. *Verified:* patterns in `_PHRASE_RAW["vote_cast"]`; `spot_segments` applies all codes per segment.
   *Fix:* narrow to vote-context (e.g. require roll-call adjacency, or drop yes/no until post-scorer review); track in a
   follow-up issue if not in this PR.

### 🔵 Nits / suggestions (Minor)

1. **`packages/llm/src/llm/ner/spot_vote_phrases.py:9` — unused import `sys`.** *Verified:* `.venv/bin/ruff check
   packages/llm/src/llm/ner` reports F401. *Fix:* remove the import (or use `--fix`).
2. **`web_docs/docs/development/vote-phrase-spotting-plan.md` — large agent implementation plan (~480 lines).** Useful
   for workers but heavy next to the user-facing design page; consider trimming or moving plan detail to the issue/PR only
   later. *Verified:* file added in diff; linked from `vote-phrase-spotting.md`.
3. **`.gitignore` — adds `.worktrees/` (unrelated to #640).** Harmless housekeeping; note for reviewers scanning scope.
4. **No integration test for `replace_hits` delete-then-insert idempotency** (only `CREATE_SQL` shape is asserted).
   Acceptable for pilot; add when CI has a disposable Postgres fixture.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `feat/640-vote-phrase-spot`; `Closes #640`; issue has all four sections |
| Conventional Commits | Yes | `feat(llm):` / `docs(llm):` / `fix(llm):`; co-author trailers on commits |
| No fabricated data | Yes | No served-path placeholders |
| New Python in `packages/` | Yes | All new code under `packages/llm`; CLIs as `python -m` |
| dbt for transformations | Partial | Bronze DDL in Python loader (explicit #640 contract / `screen_transcripts` pattern) |
| Naming | n/a | No new public mart columns |
| Keys | Yes | Explicit PK on bronze table in `store.py` |
| Calendar years | n/a | |
| Scope label / match evidence | n/a | No UI/API surface |
| Docs | Yes | Kebab-case under `web_docs/docs/development/` with frontmatter |
| Telemetry and logging | Yes | `loguru` in CLIs and store |
| Tests | Yes | Behaviour covered; see nit on store integration |
| Shared libraries | Yes | `packages/llm` tests run locally |

## Test Coverage

- **Run locally** (worktree `51068448`):
  - `pytest packages/llm/tests/test_vote_phrases.py -q` — **9 passed** in ~1.9s
  - `ruff check packages/llm/src/llm/ner` — **1 error** (F401 unused `sys` in `spot_vote_phrases.py`)
- **CI:** all required checks success on `51068448` (see table).
- **Not run:** full CLI against warehouse (read-only review); PR body documents pilot runs.

## Verdict

**approve-with-nits** — Safe to merge for the #640 pilot. Address `vote_cast` yes/no noise when scorer miss JSONL is
reviewed; drop the unused `sys` import when convenient.