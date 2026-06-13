"""
CLI: assign canonical policy QUESTIONS to raw transcripts via local CPU embeddings.

LLM-free. Reuses the MiniLM mean-pool encoder (``llm.policy_questions.encoder``) and
the per-question centroids already in ``bronze.bronze_question_centroid`` (384-dim
MiniLM vectors — the ``model_name`` stored there is a source/analysis tag, NOT the
embedder). Each transcript's caption text is chunked into overlapping word windows,
every chunk is embedded on CPU, and we take the MAX cosine similarity to each
question centroid. Questions scoring >= ``--threshold`` are assigned. Results are
cached idempotently in ``bronze.bronze_transcript_question_match`` (PK video_id,
question_id) so re-runs are cheap and downstream dbt can read them.

This is a HIGH-RECALL semantic signal, deliberately kept SEPARATE from the precise
Gemini analysis path. Calibrate the threshold against the REAL known
transcript<->question links (``--calibrate``) before trusting any coverage numbers;
never fabricate assignments (CLAUDE.md: No Fabricated Data).

    # eyeball one jurisdiction, no DB write
    python -m llm.policy_questions.assign_transcripts --state AL --city Tuscaloosa --dry-run --top-k 3

    # recommend a threshold from the ~615 known transcript<->question links
    python -m llm.policy_questions.assign_transcripts --calibrate

    # cache assignments for a scope (writes the bronze table)
    python -m llm.policy_questions.assign_transcripts --state AL --city Tuscaloosa --threshold 0.45
"""

from __future__ import annotations

import argparse
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from loguru import logger

from llm.policy_questions import db, encoder

# Chunking: ~220-word windows with overlap so a question discussed anywhere in a
# long meeting is captured. Very long meetings are evenly subsampled to MAX_CHUNKS
# so a 3-hour transcript doesn't dominate CPU time.
CHUNK_WORDS = 220
CHUNK_STRIDE = 160
# Cap windows per transcript: we only keep the top ~2 questions, and a dominant
# question recurs across a meeting, so an evenly-spread sample of ~30 windows
# catches it. Lower = faster CPU batch (encoding chunks is the bottleneck).
MAX_CHUNKS = 30


# --- targets (questions) ---------------------------------------------------

_TARGETS_SQL = """
select c.question_id,
       q.canonical_text,
       c.coarse_theme,
       c.centroid,
       coalesce(q.is_featured, false) as is_featured
from bronze.bronze_question_centroid c
left join public.policy_question q on q.question_id = c.question_id
where c.centroid is not null
"""


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def load_targets(conn, featured_only: bool) -> Tuple[List[dict], np.ndarray]:
    """Return (question rows, unit-normalized centroid matrix Q of shape (n, dim))."""
    with conn.cursor() as cur:
        cur.execute(_TARGETS_SQL)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    if featured_only:
        rows = [r for r in rows if r["is_featured"]]
    if not rows:
        raise SystemExit("No question centroids found — run the policy_questions pipeline first.")
    mat = np.vstack([_unit(np.asarray(r["centroid"], dtype=np.float32)) for r in rows])
    return rows, mat


# --- transcripts -----------------------------------------------------------

_TRANSCRIPT_SQL = """
select e.video_id,
       e.state_code,
       e.jurisdiction_name,
       coalesce(nullif(t.raw_text, ''), t.caption_text_timed) as text
from intermediate.int_browse_entity_transcripts e
join bronze.bronze_event_youtube_transcript t using (video_id)
where e.entity_type = 'place'
  and coalesce(nullif(t.raw_text, ''), t.caption_text_timed) is not null
  {state_pred}
  {city_pred}
  {video_pred}
order by e.video_id
{limit_clause}
"""


def load_transcripts(
    conn,
    state: Optional[str],
    city: Optional[str],
    limit: Optional[int],
    video_ids: Optional[Sequence[str]],
) -> List[dict]:
    params: List[object] = []
    state_pred = city_pred = video_pred = ""
    if state:
        params.append(state.upper())
        state_pred = f"and e.state_code = %s"
    if city:
        params.append(f"%{city}%")
        city_pred = f"and e.jurisdiction_name ilike %s"
    if video_ids:
        params.append(list(video_ids))
        video_pred = f"and e.video_id = any(%s)"
    limit_clause = ""
    if limit:
        params.append(int(limit))
        limit_clause = "limit %s"
    sql = _TRANSCRIPT_SQL.format(
        state_pred=state_pred, city_pred=city_pred, video_pred=video_pred, limit_clause=limit_clause
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def chunk_text(text: str) -> List[str]:
    """Overlapping word windows, evenly subsampled to MAX_CHUNKS for long texts."""
    words = (text or "").split()
    if not words:
        return []
    windows = [
        " ".join(words[i : i + CHUNK_WORDS])
        for i in range(0, max(1, len(words) - CHUNK_WORDS + 1), CHUNK_STRIDE)
    ] or [" ".join(words)]
    if len(windows) <= MAX_CHUNKS:
        return windows
    idx = np.linspace(0, len(windows) - 1, MAX_CHUNKS).round().astype(int)
    return [windows[i] for i in dict.fromkeys(idx)]


def score_transcripts(transcripts: List[dict], Q: np.ndarray) -> np.ndarray:
    """Return (n_transcripts, n_questions) max-cosine matrix. Encodes all chunks in
    one batched CPU pass, then max-pools each transcript's chunks against Q."""
    all_chunks: List[str] = []
    spans: List[Tuple[int, int]] = []
    for t in transcripts:
        chunks = chunk_text(t["text"])
        start = len(all_chunks)
        all_chunks.extend(chunks)
        spans.append((start, len(all_chunks)))
        t["_n_chunks"] = len(chunks)
    if not all_chunks:
        return np.zeros((len(transcripts), Q.shape[0]), dtype=np.float32)
    logger.info("Encoding {} chunks from {} transcripts (CPU)…", len(all_chunks), len(transcripts))
    vecs = encoder.encode(all_chunks)  # (n_chunks, dim), unit vectors
    sims = vecs @ Q.T  # (n_chunks, n_questions)
    out = np.zeros((len(transcripts), Q.shape[0]), dtype=np.float32)
    for i, (a, b) in enumerate(spans):
        if b > a:
            out[i] = sims[a:b].max(axis=0)
    return out


# --- calibration against the real known links ------------------------------

_LABELS_SQL = """
select distinct video_id, entity_id as question_id
from intermediate.int_browse_entity_transcripts
where entity_type = 'question'
"""


def calibrate(conn, Q: np.ndarray, qrows: List[dict], sample: int) -> None:
    """Score the REAL known transcript<->question links and compare positive-pair
    scores against negative (non-linked) scores to recommend a threshold."""
    qindex = {r["question_id"]: i for i, r in enumerate(qrows)}
    with conn.cursor() as cur:
        cur.execute(_LABELS_SQL)
        labels = [(v, q) for v, q in cur.fetchall() if q in qindex]
    by_video: Dict[str, List[str]] = {}
    for v, q in labels:
        by_video.setdefault(v, []).append(q)
    vids = list(by_video)[:sample]
    if not vids:
        logger.warning("No calibration labels overlap the centroid set.")
        return
    transcripts = load_transcripts(conn, None, None, None, vids)
    have = {t["video_id"] for t in transcripts}
    logger.info("Calibrating on {} labeled videos ({} have transcript text)…", len(vids), len(have))
    scores = score_transcripts(transcripts, Q)
    pos, neg = [], []
    for row, s in zip(transcripts, scores):
        linked = {qindex[q] for q in by_video.get(row["video_id"], []) if q in qindex}
        for j in range(Q.shape[0]):
            (pos if j in linked else neg).append(float(s[j]))
    pos_a, neg_a = np.array(pos), np.array(neg)

    def pct(a, p):
        return float(np.percentile(a, p)) if len(a) else float("nan")

    logger.success("=== Threshold calibration (real known links) ===")
    logger.info("positive pairs n={}  median={:.3f}  p25={:.3f}  p10={:.3f}",
                len(pos_a), pct(pos_a, 50), pct(pos_a, 25), pct(pos_a, 10))
    logger.info("negative pairs n={}  median={:.3f}  p95={:.3f}  p99={:.3f}",
                len(neg_a), pct(neg_a, 50), pct(neg_a, 95), pct(neg_a, 99))
    # A sane default: catch most true links while staying above negative noise.
    rec = round((pct(pos_a, 25) + pct(neg_a, 95)) / 2, 3)
    for thr in (0.35, 0.40, 0.45, 0.50, 0.55):
        recall = float((pos_a >= thr).mean()) if len(pos_a) else 0.0
        fpr = float((neg_a >= thr).mean()) if len(neg_a) else 0.0
        logger.info("  thr={:.2f}  recall(known)={:.0%}  neg-rate={:.1%}", thr, recall, fpr)
    logger.success("Suggested --threshold ≈ {:.2f}", rec)


# --- main run --------------------------------------------------------------

def run(state=None, city=None, limit=None, video_ids=None, threshold=0.45, top_k=3,
        max_per_transcript=2, featured_only=False, dry_run=False, calibrate_mode=False,
        sample=300, database_url=None) -> int:
    conn = db.connect(database_url)
    db.ensure_tables(conn)
    qrows, Q = load_targets(conn, featured_only)
    logger.info("Loaded {} question targets (dim={})", len(qrows), Q.shape[1])

    if calibrate_mode:
        calibrate(conn, Q, qrows, sample)
        conn.close()
        return 0

    transcripts = load_transcripts(conn, state, city, limit, video_ids)
    if not transcripts:
        logger.warning("No transcripts matched the scope (state={}, city={}).", state, city)
        conn.close()
        return 0
    scores = score_transcripts(transcripts, Q)
    model = encoder.model_name()

    assignments, shown = [], 0
    distinct_q = set()
    covered = 0
    for row, s in zip(transcripts, scores):
        order = np.argsort(-s)
        # Cap to the strongest few per transcript: above ~0.55 the #1/#2 question
        # is reliable, but the tail fills with generic catch-alls (land use, admin
        # structure) that match nearly every meeting. order is desc, so slice.
        hits = [(qrows[j], float(s[j])) for j in order if s[j] >= threshold][:max_per_transcript]
        if hits:
            covered += 1
        for q, sc in hits:
            distinct_q.add(q["question_id"])
            assignments.append((
                row["video_id"], q["question_id"], sc, row.get("_n_chunks"),
                row["state_code"], row["jurisdiction_name"], model, threshold,
            ))
        if dry_run and shown < 25:
            shown += 1
            top = [(qrows[j], float(s[j])) for j in order[:top_k]]
            logger.info("📺 {} · {}", row["video_id"], row["jurisdiction_name"])
            for q, sc in top:
                mark = "✓" if sc >= threshold else " "
                logger.info("    [{}] {:.3f}  {}", mark, sc, (q["canonical_text"] or "")[:90])

    logger.success(
        "{} transcripts → {} assignments (>= {:.2f}); {} ({:.0%}) covered, {} distinct questions",
        len(transcripts), len(assignments), threshold, covered,
        covered / len(transcripts) if transcripts else 0, len(distinct_q),
    )
    if dry_run:
        logger.info("DRY RUN — nothing written. Re-run without --dry-run to cache.")
    elif assignments:
        n = db.upsert(
            conn, "bronze.bronze_transcript_question_match",
            ["video_id", "question_id", "score", "n_chunks", "state_code",
             "jurisdiction_name", "model_name", "threshold"],
            assignments, conflict_key="video_id,question_id",
        )
        logger.success("Upserted {} transcript→question rows.", n)
    conn.close()
    return len(assignments)


def main() -> None:
    ap = argparse.ArgumentParser(description="Assign canonical questions to transcripts via local embeddings.")
    ap.add_argument("--state", default=None, help="2-letter state code scope.")
    ap.add_argument("--city", default=None, help="Jurisdiction-name substring scope (ILIKE).")
    ap.add_argument("--limit", type=int, default=None, help="Max transcripts.")
    ap.add_argument("--video-id", action="append", dest="video_ids", help="Specific video id(s).")
    ap.add_argument("--threshold", type=float, default=0.45, help="Min max-cosine to assign.")
    ap.add_argument("--top-k", type=int, default=3, help="Top questions to print per transcript in --dry-run.")
    ap.add_argument("--max-per-transcript", type=int, default=2, help="Max questions to assign per transcript (strongest first).")
    ap.add_argument("--featured-only", action="store_true", help="Restrict to is_featured questions.")
    ap.add_argument("--dry-run", action="store_true", help="Print, don't write.")
    ap.add_argument("--calibrate", action="store_true", help="Recommend a threshold from known links.")
    ap.add_argument("--sample", type=int, default=300, help="Labeled videos to use in --calibrate.")
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()
    run(state=args.state, city=args.city, limit=args.limit, video_ids=args.video_ids,
        threshold=args.threshold, top_k=args.top_k, max_per_transcript=args.max_per_transcript,
        featured_only=args.featured_only, dry_run=args.dry_run, calibrate_mode=args.calibrate,
        sample=args.sample, database_url=args.database_url)


if __name__ == "__main__":
    main()
