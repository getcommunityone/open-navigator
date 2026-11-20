---
sidebar_position: 34
title: Vote phrase spotting — implementation plan
description: Bite-sized TDD plan for #640 (phrase hits → bronze.transcript_vote_phrase, optional spaCy candidates, Gemini ±60s scoring).
---

# Vote phrase spotting — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land free motion/vote phrase hits in `bronze.transcript_vote_phrase` for meetings that already have Gemini Part 1 decisions, optionally emit spaCy candidate JSONL, and score hit recall within ±60s of each decision’s `media_anchor`.

**Architecture:** Compiled regex over timed caption segments produces durable hit rows (no transcript text in Postgres). The same vocabulary drives an optional spaCy `EntityRuler` pass that clusters hits into JSONL candidates. Scoring joins preferred Part 1 analyses’ `media_anchor.timestamp_start_seconds` to hits by `video_id`. Idempotent loads delete-then-insert by `file_sha256` (SHA-256 of the canonical transcript bytes scanned).

**Tech Stack:** Python 3.11+, `packages/llm` (`llm.ner`), `psycopg2`, `loguru`, `spacy` + `en_core_web_sm` (candidates only), pytest, local warehouse `localhost:5433` / `OPEN_NAVIGATOR_DATABASE_URL`.

**Issue:** [#640](https://github.com/getcommunityone/open-navigator/issues/640). Design: [vote-phrase-spotting.md](./vote-phrase-spotting.md). GLiNER follow-up: [#641](https://github.com/getcommunityone/open-navigator/issues/641) (out of this plan).

## Global Constraints

- Prefer `packages/`; never add files under `scripts/`.
- Table name: `bronze.transcript_vote_phrase` (singular; **no** `bronze.bronze_` prefix).
- Hit rows hold **no** transcript text — only ids, `phrase_code`, times/offsets, provenance.
- First CLI default: videos that already have Part 1 decisions; always support `--dry-run` and `--limit`.
- Idempotent write: `DELETE … WHERE file_sha256 = ANY(%s)` then `INSERT`.
- Before any full-catalog run: print rows written, table size (rows + bytes), linear estimate for ~200k videos.
- Scoring window: ±60 seconds vs `media_anchor.timestamp_start_seconds`.
- Conventional Commits; branch `feat/640-vote-phrase-spot` off latest `main` (do not commit on unrelated Legistar work).
- No fabricated decision text for the site; scoring only measures coverage of existing Gemini decisions.
- Calendar / wire rules N/A; do not store years as a concern here.

---

## File map

| Path | Responsibility |
|---|---|
| `packages/llm/src/llm/ner/__init__.py` | Package exports |
| `packages/llm/src/llm/ner/phrases.py` | Stock phrase lists + compiled regex by `phrase_code` |
| `packages/llm/src/llm/ner/spot.py` | Scan segments → `VotePhraseHit` list; `file_sha256` of canonical bytes |
| `packages/llm/src/llm/ner/store.py` | `CREATE TABLE IF NOT EXISTS`, delete-by-sha, insert, size report |
| `packages/llm/src/llm/ner/part1_videos.py` | SQL: distinct `video_id` with Part 1 decisions + preferred analysis |
| `packages/llm/src/llm/ner/candidates.py` | spaCy EntityRuler + window clustering → JSONL records |
| `packages/llm/src/llm/ner/score.py` | Load Gemini anchors; ±60s match; miss phrase-gap report |
| `packages/llm/src/llm/ner/spot_vote_phrases.py` | CLI `python -m llm.ner.spot_vote_phrases` |
| `packages/llm/src/llm/ner/score_vote_phrases.py` | CLI `python -m llm.ner.score_vote_phrases` |
| `packages/llm/tests/test_vote_phrases.py` | Unit tests (phrases, spot, store SQL shape, score, candidates) |
| `web_docs/docs/development/vote-phrase-spotting.md` | Already written; tweak only if contract drifts |
| `web_docs/sidebars.ts` | Already lists the design page |

**Reuse (do not fork):**

- `llm.gemini.transcript_db.fetch_db_transcript` / `normalize_transcript_row` — timed segments from `bronze.bronze_event_youtube_transcript`.
- Pattern for Python-created bronze: `llm.typesafe.screen_transcripts` (`CREATE_SQL`, usage logging not required for free spotting).

**Join keys (warehouse):**

- `public.event_decision.analysis_id` = `public.event_meeting.event_meeting_id` → `video_id` (~3k videos with decisions today).
- Anchors live in `bronze.bronze_events_analysis_ai.structured_analysis -> 'decisions' -> n -> 'media_anchor' -> 'timestamp_start_seconds'` for the preferred analysis (`int_preferred_event_analysis` / same preference as marts). Scorer may query bronze + `event_meeting` directly; do not invent columns on `public.event_decision`.

**`file_sha256` definition:** SHA-256 hex of UTF-8 bytes of the canonical scan string: for each segment in order, `f"{start:.3f}\t{text}\n"` joined. That fingerprints the transcript *content* scanned (warehouse has no separate file). Context for misses/candidates is re-fetched via `fetch_db_transcript(video_id)`, not stored in bronze.

---

### Task 1: Phrase vocabulary + regex spotter (no DB)

**Files:**
- Create: `packages/llm/src/llm/ner/__init__.py`
- Create: `packages/llm/src/llm/ner/phrases.py`
- Create: `packages/llm/src/llm/ner/spot.py`
- Test: `packages/llm/tests/test_vote_phrases.py`

**Interfaces:**
- Produces: `PHRASE_PATTERNS: dict[str, re.Pattern[str]]` for codes `motion_made`, `seconded`, `vote_called`, `vote_cast`, `result`, `subject_cue`
- Produces: `@dataclass(frozen=True) class VotePhraseHit: video_id: str; phrase_code: str; start_seconds: float | None; char_offset: int; match_end: int`
- Produces: `def canonical_transcript_bytes(segments: list[dict]) -> bytes`
- Produces: `def file_sha256(segments: list[dict]) -> str`
- Produces: `def spot_segments(video_id: str, segments: list[dict]) -> list[VotePhraseHit]` — search each segment’s `text`; set `start_seconds` from segment `start`; `char_offset` is offset within that segment’s text (document in docstring). Prefer longest match first when patterns overlap on the same span (sort patterns by pattern length descending per segment scan, skip overlapping char ranges).

- [ ] **Step 1: Write the failing test**

```python
# packages/llm/tests/test_vote_phrases.py
from llm.ner.spot import file_sha256, spot_segments

def test_spot_motion_and_result_with_seconds():
    segs = [
        {"text": "I move to approve Ordinance Number 12.", "start": 100.0},
        {"text": "Second.", "start": 105.0},
        {"text": "All in favor?", "start": 110.0},
        {"text": "Aye.", "start": 112.0},
        {"text": "Motion carries.", "start": 115.0},
    ]
    hits = spot_segments("vid1", segs)
    codes = [h.phrase_code for h in hits]
    assert "motion_made" in codes
    assert "seconded" in codes
    assert "vote_called" in codes
    assert "vote_cast" in codes
    assert "result" in codes
    assert "subject_cue" in codes
    assert any(h.start_seconds == 115.0 and h.phrase_code == "result" for h in hits)
    assert len(file_sha256(segs)) == 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/developer/projects/open-navigator && .venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py::test_spot_motion_and_result_with_seconds -v`  
Expected: FAIL (import / not found)

- [ ] **Step 3: Write minimal implementation**

In `phrases.py`, define raw string lists per code (include the examples from the design table; case-insensitive). Compile with `re.compile(..., re.IGNORECASE)`. Avoid bare `\byes\b` / `\bno\b` matching inside unrelated words; use word boundaries. For `seconded`, require `second` as a short utterance or “I('|'ll)? second” — not every English “second”.

In `spot.py`, implement `canonical_transcript_bytes`, `file_sha256`, `spot_segments` as above. Empty text segments yield no hits.

`__init__.py` can re-export `spot_segments`, `VotePhraseHit`, `file_sha256`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py::test_spot_motion_and_result_with_seconds -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/llm/src/llm/ner/__init__.py packages/llm/src/llm/ner/phrases.py \
  packages/llm/src/llm/ner/spot.py packages/llm/tests/test_vote_phrases.py
git commit -m "$(cat <<'EOF'
feat(llm): spot stock vote/motion phrases in caption segments

EOF
)"
```

---

### Task 2: Bronze store (create, idempotent replace, size report)

**Files:**
- Create: `packages/llm/src/llm/ner/store.py`
- Modify: `packages/llm/tests/test_vote_phrases.py`

**Interfaces:**
- Consumes: `VotePhraseHit`, `file_sha256` string, `git_commit_sha: str`, `loaded_ts`
- Produces: `TABLE = "bronze.transcript_vote_phrase"`
- Produces: `CREATE_SQL` with columns:  
  `video_id text NOT NULL`,  
  `phrase_code text NOT NULL`,  
  `start_seconds double precision`,  
  `char_offset integer NOT NULL`,  
  `file_sha256 text NOT NULL`,  
  `loaded_ts timestamptz NOT NULL`,  
  `git_commit_sha text NOT NULL`,  
  `PRIMARY KEY (file_sha256, phrase_code, start_seconds, char_offset)`  
  Note: Postgres UNIQUE/PK treats NULLs as distinct — require `start_seconds` NOT NULL in practice by writing `0.0` when the only text is untimed `raw_text` fallback, and document that; keep column nullable only if you instead use `COALESCE(start_seconds, -1)` in the PK via an expression index. **Preferred:** `start_seconds double precision NOT NULL` (use `0.0` for untimed).
- Produces: `def ensure_table(conn) -> None`
- Produces: `def replace_hits(conn, *, file_sha256s: list[str], rows: list[dict]) -> int` — delete where `file_sha256 = ANY(%s)` then executemany insert; return insert count
- Produces: `def table_stats(conn) -> dict` with keys `row_count: int`, `total_bytes: int` from `pg_total_relation_size('bronze.transcript_vote_phrase')`

- [ ] **Step 1: Write the failing test**

```python
def test_create_sql_has_no_text_payload_and_singular_name():
    from llm.ner.store import CREATE_SQL, TABLE
    assert TABLE == "bronze.transcript_vote_phrase"
    assert "bronze.bronze_" not in TABLE
    assert "raw_text" not in CREATE_SQL.lower()
    assert "context" not in CREATE_SQL.lower()
    assert "file_sha256" in CREATE_SQL
    assert "git_commit_sha" in CREATE_SQL
```

(Optional integration test skipped unless `OPEN_NAVIGATOR_DATABASE_URL` is set: insert two rows, call `replace_hits` again with same sha, assert count unchanged.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py::test_create_sql_has_no_text_payload_and_singular_name -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Implement `store.py` with `loguru` logger. Use `psycopg2` like `transcript_db.py`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/llm/src/llm/ner/store.py packages/llm/tests/test_vote_phrases.py
git commit -m "$(cat <<'EOF'
feat(llm): bronze.transcript_vote_phrase store with sha replace

EOF
)"
```

---

### Task 3: Part 1 video selection + spot CLI

**Files:**
- Create: `packages/llm/src/llm/ner/part1_videos.py`
- Create: `packages/llm/src/llm/ner/spot_vote_phrases.py`
- Modify: `packages/llm/tests/test_vote_phrases.py`

**Interfaces:**
- Produces: `def list_part1_video_ids(database_url: str, *, limit: int | None = None) -> list[str]`  

```sql
SELECT DISTINCT m.video_id
FROM public.event_decision d
JOIN public.event_meeting m ON m.event_meeting_id = d.analysis_id
WHERE COALESCE(m.video_id, '') <> ''
ORDER BY m.video_id
LIMIT %s  -- omit LIMIT when limit is None
```

- Produces: CLI argparse: `--database-url` (default env `OPEN_NAVIGATOR_DATABASE_URL`), `--limit`, `--dry-run`, `--candidates` (wire stub OK until Task 4), `--video-id` (repeatable, bypasses Part 1 filter when set)
- Behavior: for each video, `fetch_db_transcript`; skip if None; `hits = spot_segments(...)`; `sha = file_sha256(segments)`; collect rows with `git_commit_sha` from `subprocess.check_output(["git","rev-parse","HEAD"], text=True).strip()` (or `"unknown"` if not a git checkout); if not dry-run, `ensure_table` + `replace_hits` batched by sha; always print report:

```text
videos_scanned=N videos_with_hits=M hits=H table_rows=R table_bytes=B
estimate_200k_hits≈… estimate_200k_bytes≈…
```

Estimate: `hits_per_video = H / max(N,1)`; `bytes_per_hit = B / max(R,1)` after write (dry-run: estimate bytes as `H * 120` if table empty).  
`estimate_200k_hits = hits_per_video * 200_000`, similarly for bytes.

- [ ] **Step 1: Write the failing test**

```python
def test_estimate_scales_to_200k():
    from llm.ner.spot_vote_phrases import estimate_full_catalog
    est = estimate_full_catalog(videos_scanned=100, hits=250, table_rows=250, table_bytes=50_000)
    assert est["estimate_200k_hits"] == 500_000
    assert est["estimate_200k_bytes"] == 100_000_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py::test_estimate_scales_to_200k -v`  
Expected: FAIL

- [ ] **Step 3: Implement `estimate_full_catalog` + CLI `main()`**

`if __name__ == "__main__": raise SystemExit(main())`

- [ ] **Step 4: Run unit tests; smoke dry-run**

Run:

```bash
.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py -v
.venv/bin/python -m llm.ner.spot_vote_phrases --limit 5 --dry-run
```

Expected: tests PASS; dry-run logs hits and estimates; **no** INSERT.

- [ ] **Step 5: Commit**

```bash
git add packages/llm/src/llm/ner/part1_videos.py packages/llm/src/llm/ner/spot_vote_phrases.py \
  packages/llm/tests/test_vote_phrases.py
git commit -m "$(cat <<'EOF'
feat(llm): CLI spot_vote_phrases over Part 1 meetings

EOF
)"
```

---

### Task 4: Optional spaCy candidates (JSONL only)

**Files:**
- Create: `packages/llm/src/llm/ner/candidates.py`
- Modify: `packages/llm/src/llm/ner/spot_vote_phrases.py` (honor `--candidates`)
- Modify: `packages/llm/tests/test_vote_phrases.py`

**Interfaces:**
- Consumes: same phrase vocabulary (build EntityRuler patterns from the raw phrase strings in `phrases.py` — export `PHRASE_STRINGS: dict[str, list[str]]`)
- Produces: `def build_ruler_nlp()` → spaCy `Language` with `en_core_web_sm` + EntityRuler (`overwrite_ents=True`), labels = phrase codes uppercased or as-is (document choice; prefer exact `phrase_code` as ent label)
- Produces: `def cluster_candidates(video_id: str, segments: list[dict], hits: list[VotePhraseHit], *, window_seconds: float = 90.0) -> list[dict]`  
  Cluster hits whose `start_seconds` fall within `window_seconds` of neighbors (single-linkage). Each candidate dict: `video_id`, `t_start`, `t_end`, `phrase_codes`, `hit_count`, `subject_cue_present: bool` — **no** full transcript dump; optional `span_texts` capped at 12 short strings from EntityRuler ents in window for debugging JSONL only.
- Produces: write `data/cache/vote_phrase_candidates/<utc_run_id>/candidates.jsonl` one object per line when `--candidates`

- [ ] **Step 1: Write the failing test**

```python
def test_cluster_groups_nearby_hits():
    from llm.ner.spot import VotePhraseHit
    from llm.ner.candidates import cluster_candidates
    hits = [
        VotePhraseHit("v", "motion_made", 10.0, 0, 5),
        VotePhraseHit("v", "result", 40.0, 0, 5),
        VotePhraseHit("v", "motion_made", 400.0, 0, 5),
    ]
    clusters = cluster_candidates("v", [{"text": "x", "start": 10.0}], hits, window_seconds=90.0)
    assert len(clusters) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py::test_cluster_groups_nearby_hits -v`  
Expected: FAIL

- [ ] **Step 3: Implement clustering + optional spaCy spans; wire `--candidates`**

If `en_core_web_sm` is missing, log a clear error and exit non-zero only when `--candidates` is set (phrase spotting without the flag must not require loading spaCy).

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/llm/src/llm/ner/candidates.py packages/llm/src/llm/ner/phrases.py \
  packages/llm/src/llm/ner/spot_vote_phrases.py packages/llm/tests/test_vote_phrases.py
git commit -m "$(cat <<'EOF'
feat(llm): optional spaCy vote-phrase candidate JSONL

EOF
)"
```

---

### Task 5: Score against Gemini Part 1 anchors

**Files:**
- Create: `packages/llm/src/llm/ner/score.py`
- Create: `packages/llm/src/llm/ner/score_vote_phrases.py`
- Modify: `packages/llm/tests/test_vote_phrases.py`

**Interfaces:**
- Produces: `def load_gemini_anchors(database_url: str, *, limit: int | None = None) -> list[dict]`  
  Each dict: `video_id`, `decision_id`, `headline`, `anchor_seconds: float`  
  SQL sketch (adjust to preferred-analysis filter used in marts — join `int_preferred_event_analysis` if exposed in Postgres as a relation, else filter `bronze_events_analysis_ai` the same way `event_decision` prefers one model):

```sql
SELECT m.video_id,
       dec->>'decision_id' AS decision_id,
       dec->>'headline' AS headline,
       (dec->'media_anchor'->>'timestamp_start_seconds')::double precision AS anchor_seconds
FROM bronze.bronze_events_analysis_ai a
JOIN public.event_meeting m ON m.event_meeting_id = a.id
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(a.structured_analysis->'decisions', '[]'::jsonb)) AS dec
WHERE COALESCE(m.video_id, '') <> ''
  AND dec->'media_anchor'->>'timestamp_start_seconds' IS NOT NULL
  AND a.analysis_type LIKE '%policy%'  -- tighten to the real analysis_type value in DB
```

Verify `analysis_type` and preferred-model filter against a live `SELECT DISTINCT analysis_type` before locking the query in code; prefer joining only analyses that appear in `public.event_decision` for that `video_id` so scoring matches the mart.

- Produces: `def score_anchors(anchors: list[dict], hits_by_video: dict[str, list[tuple[float, str]]], *, window: float = 60.0) -> dict`  
  Returns `decisions_with_anchor`, `decisions_hit`, `decisions_missed` (list of miss records with `video_id`, `decision_id`, `headline`, `anchor_seconds`, `nearby_phrase_codes` within ±120s for gap analysis, `missing_codes_guess` = design codes not present nearby).

- Produces: CLI prints summary counts + writes `data/cache/vote_phrase_score/<utc>/misses.jsonl`

- [ ] **Step 1: Write the failing test**

```python
def test_score_hit_within_60s():
    from llm.ner.score import score_anchors
    anchors = [{"video_id": "v", "decision_id": "D001", "headline": "Rezone", "anchor_seconds": 100.0}]
    hits = {"v": [(95.0, "motion_made"), (110.0, "result")]}
    out = score_anchors(anchors, hits, window=60.0)
    assert out["decisions_hit"] == 1
    assert out["decisions_missed"] == []

def test_score_miss_outside_60s():
    from llm.ner.score import score_anchors
    anchors = [{"video_id": "v", "decision_id": "D001", "headline": "Rezone", "anchor_seconds": 100.0}]
    hits = {"v": [(20.0, "result")]}
    out = score_anchors(anchors, hits, window=60.0)
    assert out["decisions_hit"] == 0
    assert len(out["decisions_missed"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py::test_score_hit_within_60s packages/llm/tests/test_vote_phrases.py::test_score_miss_outside_60s -v`  
Expected: FAIL

- [ ] **Step 3: Implement `score.py` + CLI**

Load hits from `bronze.transcript_vote_phrase` for the video set (or accept `--from-spot-dry` only in unit tests via injected hits). Default CLI: read hits from bronze after a real spot run.

- [ ] **Step 4: Run unit tests**

Run: `.venv/bin/python -m pytest packages/llm/tests/test_vote_phrases.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/llm/src/llm/ner/score.py packages/llm/src/llm/ner/score_vote_phrases.py \
  packages/llm/tests/test_vote_phrases.py
git commit -m "$(cat <<'EOF'
feat(llm): score vote-phrase hits against Gemini media anchors

EOF
)"
```

---

### Task 6: Docs cross-link + end-to-end dry run on Part 1 sample

**Files:**
- Modify: `web_docs/docs/development/vote-phrase-spotting.md` (add “How to run” matching real CLI flags)
- Modify: `web_docs/docs/development/vote-phrase-spotting-plan.md` (check off completed tasks only when done)
- Modify: `web_docs/sidebars.ts` if the plan page should appear (optional; design page is enough — add plan under AI category only if you want it browsable)

- [ ] **Step 1: Add “How to run” to the design doc**

```bash
.venv/bin/python -m llm.ner.spot_vote_phrases --limit 50 --dry-run
.venv/bin/python -m llm.ner.spot_vote_phrases --limit 50
.venv/bin/python -m llm.ner.spot_vote_phrases --limit 50 --candidates
.venv/bin/python -m llm.ner.score_vote_phrases --limit 50
```

- [ ] **Step 2: Run limited load + score on the warehouse**

```bash
.venv/bin/python -m llm.ner.spot_vote_phrases --limit 50
.venv/bin/python -m llm.ner.score_vote_phrases --limit 50
```

Expected: table created; report includes `estimate_200k_*`; score summary with hit/miss counts; no transcript text in `SELECT * FROM bronze.transcript_vote_phrase LIMIT 5`.

- [ ] **Step 3: Commit docs**

```bash
git add web_docs/docs/development/vote-phrase-spotting.md \
  web_docs/docs/development/vote-phrase-spotting-plan.md web_docs/sidebars.ts
git commit -m "$(cat <<'EOF'
docs(llm): how to run vote phrase spotting and scoring

EOF
)"
```

- [ ] **Step 4: Open PR for #640**

Branch `feat/640-vote-phrase-spot`, `Closes #640`, include Attributes link to design doc. Do **not** close #641.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|---|---|
| Phrase spotting stock phrases | 1 |
| spaCy EntityRuler on same pass / `--candidates` | 4 |
| Bronze hits always; candidates JSONL only | 2, 4 |
| Scope = Part 1 meetings; `--dry-run` | 3 |
| No transcript text in hit row; provenance cols | 2 |
| Idempotent delete/insert by `file_sha256` | 2 |
| Report rows + size + 200k estimate | 3 |
| Singular `bronze.transcript_vote_phrase` | 2 |
| Score ±60s + miss phrase gaps | 5 |
| Docs / how to run | 6 |
| GLiNER | **#641 — not this plan** |

## Placeholder scan

No TBD/TODO steps; concrete SQL, flags, and test code included. Tighten `analysis_type` / preferred-analysis join in Task 5 against live DB during implementation (one discovery query, then lock the string in code + test with fixtures).

## Type consistency

`VotePhraseHit` fields (`video_id`, `phrase_code`, `start_seconds`, `char_offset`, `match_end`) are shared by Tasks 1, 2, 4, 5. `phrase_code` set is fixed in Task 1 and reused by EntityRuler labels and scoring gap analysis.
EOF
