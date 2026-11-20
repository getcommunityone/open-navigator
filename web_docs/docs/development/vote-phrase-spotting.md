---
sidebar_position: 33
title: Vote phrase spotting
description: Free phrase hits for motions and votes in transcripts, optional spaCy candidates, scored against Gemini Part 1 before any full-catalog run.
---

# Vote phrase spotting

Gemini Part 1 writes the decisions and votes the site shows, and it is billed per
call. Motions and votes are announced in a small set of stock phrases. A plain
pattern search finds those phrases on an ordinary computer, costs nothing, and
gives a timestamp (or character offset) plus surrounding lines read from the
transcript file when needed. That hit layer is durable. Grouping hits into
decision *candidates* is experimental until we score against Gemini Part 1 (and
later Jev), so candidates stay JSONL only.

Issue: [#640](https://github.com/getcommunityone/open-navigator/issues/640).
Implementation plan: [vote-phrase-spotting-plan.md](./vote-phrase-spotting-plan.md).
Sibling person/place NER → Splink → Jev: [#623](https://github.com/getcommunityone/open-navigator/issues/623).
GLiNER comparison if spaCy plateaus: [#641](https://github.com/getcommunityone/open-navigator/issues/641).

## In short

- **Hits are facts; candidates are not.** Hits go to
  `bronze.transcript_vote_phrase` (singular name, no doubled `bronze_` prefix).
  Candidate clusters go to JSONL under `data/cache/vote_phrase_candidates/<run>/`
  (or Drive `crawl/` for shared pilots).
- **No transcript text in the table.** A hit stores meeting/`video_id`,
  `phrase_code`, `start_seconds` or `char_offset`, `file_sha256`, `loaded_ts`,
  and `git_commit_sha`. Context lines are re-read from the file by offset or
  seconds.
- **First runs stay on Gemini-scored meetings.** The CLI defaults to videos that
  already have Part 1 decisions, with `--dry-run` and `--limit`. A full ~200k
  pass is not started until the run report’s size estimate is acceptable
  (transcript text already does not fit on free Neon; this table must not hit
  the same wall).
- **Idempotent load.** Delete then insert by `file_sha256` so a rerun never
  doubles rows.
- **Same pass, two tools.** Compiled phrase patterns always produce hits. With
  `--candidates`, spaCy `en_core_web_sm` + `EntityRuler` (same stock phrases)
  labels spans for JSONL clustering. GLiNER is out of scope until [#641](https://github.com/getcommunityone/open-navigator/issues/641).

## Phrase codes

| `phrase_code` | What people say (examples) |
|---|---|
| `motion_made` | “I move to approve”, “motion to adopt”, “so moved” |
| `seconded` | “second”, “I’ll second that” |
| `vote_called` | “all in favor”, “roll call”, “call the question” |
| `vote_cast` | “aye”, “nay”, “yes”, “no”, “abstain” |
| `result` | “motion carries”, “motion passes”, “motion fails”, “approved 5 to 2”, “unanimous” |
| `subject_cue` | “ordinance number”, “resolution”, “agenda item”, “public hearing” |

## Where each piece lives

| Piece | Where | What it does |
|---|---|---|
| Spotter CLI | `python -m llm.ner.spot_vote_phrases` | Reads timed captions for Part 1 meetings; writes hits; optional `--candidates` JSONL |
| Scorer CLI | `python -m llm.ner.score_vote_phrases` | ±60s coverage of Gemini `media_anchor.timestamp_start_seconds`; miss phrase gaps |
| Table | `bronze.transcript_vote_phrase` | One row per phrase occurrence per transcript file |
| Patterns | `packages/llm/src/llm/ner/` (phrase lists + compiled regex; EntityRuler patterns when `--candidates`) | Shared vocabulary for both layers |
| Candidates | `data/cache/vote_phrase_candidates/<run>/` | Experimental grouping only |

### Hit row (contract)

- Grain: one row per phrase occurrence in one transcript file.
- Keys: prefer `start_seconds` when caption segments exist; otherwise `char_offset`
  into the stored transcript file. PK:
  `(file_sha256, phrase_code, start_seconds, char_offset)` (or a stable hash of
  those).
- Provenance: `file_sha256`, `loaded_ts`, `git_commit_sha` of the runner.
- **Forbidden:** caption text, surrounding lines, or LLM output in this table.

### Run report (required before any larger run)

After each load (including dry-run estimates):

1. Rows written (or that would be written).
2. Current table size: row count and relation size on disk.
3. Linear estimate for ~200k transcripts from this sample’s hits-per-video and
   bytes-per-hit.

Do not start a full-catalog run from this issue.

## Scoring against Gemini Part 1

For each decision in the scored set with
`media_anchor.timestamp_start_seconds`:

- **Hit** if at least one `transcript_vote_phrase` row for that `video_id` falls
  within **±60 seconds** of the anchor.
- Report: decisions with a hit / decisions with an anchor; list misses.
- For misses: re-read nearby caption lines from the file and record which
  `phrase_code`s were absent (what stock phrases we still need).

This does not invent decisions. It only measures whether the free layer fires
near decisions Gemini already extracted.

## Division of labor (cheap → paid)

```text
phrase regex  →  bronze.transcript_vote_phrase     (free, durable)
     └─ --candidates + spaCy EntityRuler → JSONL   (cheap, experimental)
Jev           →  typed confirm when a roster/window exists (later)
Gemma / Gemini Part 1 → event_decision               (full extract)
```

[Jev](./jev-transcript-screening.md) still does not write decision text; once
candidates are good enough, Jev can score approve/reject/table over a known
window. Until then, Gemini (or [Gemma on Colab](../deployment/colab-gemma-policy-analysis.md))
remains the extractor of record.

## How to run

From the repo root with `OPEN_NAVIGATOR_DATABASE_URL` set (local warehouse on
`localhost:5433`):

```bash
.venv/bin/python -m llm.ner.spot_vote_phrases --limit 50 --dry-run
.venv/bin/python -m llm.ner.spot_vote_phrases --limit 50
.venv/bin/python -m llm.ner.spot_vote_phrases --limit 50 --candidates
.venv/bin/python -m llm.ner.score_vote_phrases --limit 50
```

Flags:

- `--database-url` — override the database URL (default: env
  `OPEN_NAVIGATOR_DATABASE_URL`).
- `--limit` — cap Part 1 videos scanned or decisions scored.
- `--dry-run` — spot only; no `bronze.transcript_vote_phrase` writes (still prints
  row counts and ~200k estimates).
- `--candidates` — also write spaCy EntityRuler clusters to
  `data/cache/vote_phrase_candidates/<run>/candidates.jsonl` (requires
  `en_core_web_sm`).
- `--video-id` — repeatable; spot specific videos instead of the Part 1 default
  set.

If `python -m llm.ner…` fails on import, install the package in the worktree
venv (`pip install -e packages/llm`) or run with
`PYTHONPATH=packages/llm/src`.

## Out of scope (this design)

- Writing `public.event_decision` from phrase hits or candidates.
- Screening the full YouTube catalog.
- GLiNER (see [#641](https://github.com/getcommunityone/open-navigator/issues/641)).
- Person/place MDM ([#623](https://github.com/getcommunityone/open-navigator/issues/623)).
