"""Build the multi-state metadata keep/skip validation sample (#666).

Usage::

    python -m llm.typesafe.meta_gate_validate --dry-run
    python -m llm.typesafe.meta_gate_validate --seed 20261121 --n-final 1000 --n-pool 2500
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any, Sequence

from loguru import logger

from llm.typesafe.client import JevClient, JevError
from llm.typesafe.meta_gate_sample import (
    DEFAULT_SEED,
    DEFAULT_THRESHOLDS,
    SampledVideo,
    ScoredVideo,
    VideoRow,
    assign_ab_split,
    draw_channel_capped,
    gate_label,
    pick_states,
    pick_threshold,
    rate_table,
    stratified_final_draw,
)
from llm.typesafe.screen_transcripts import (
    CREATE_SQL as TX_CREATE_SQL,
    MEETING_KEEP_KIND_KEYS,
    QUESTION_VERSION as TX_QUESTION_VERSION,
    TABLE as TX_SCREEN_TABLE,
    UPSERT_SQL as TX_UPSERT_SQL,
    _segment_texts,
    meeting_keep_p,
    screen_transcript,
)
from llm.typesafe.screen_video_meta import (
    CREATE_SQL as META_CREATE_SQL,
    QUESTION_VERSION as META_QUESTION_VERSION,
    TABLE as META_SCREEN_TABLE,
    UPSERT_SQL as META_UPSERT_SQL,
    build_meta_state,
    screen_meta,
)

SAMPLE_CSV = Path("data/cache/jev_meta_gate_validation_sample.csv")
DISAGREE_CSV = Path("data/cache/jev_meta_gate_validation_disagreements.csv")
REPORT_JSON = Path("data/cache/jev_meta_gate_validation_report.json")
REPORT_MD = Path("web_docs/docs/development/jev-meta-gate-validation.md")


def _database_url(explicit: str) -> str:
    from llm.gemini.analyze_backlog import _resolve_database_url

    return _resolve_database_url(explicit)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Multi-state metadata keep/skip validation sample (#666)."
    )
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--n-final", type=int, default=1000)
    p.add_argument("--n-pool", type=int, default=2500)
    p.add_argument(
        "--states",
        default=None,
        help="Comma-separated override (skip auto large/small pick)",
    )
    p.add_argument("--n-states", type=int, default=8)
    p.add_argument("--max-per-channel", type=int, default=10)
    p.add_argument("--database-url", default="")
    p.add_argument("--model", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--skip-screen",
        action="store_true",
        help="Do not call Jev; only use existing screen rows",
    )
    p.add_argument("--rescreen", action="store_true")
    p.add_argument("--sample-csv", type=Path, default=SAMPLE_CSV)
    p.add_argument("--disagree-csv", type=Path, default=DISAGREE_CSV)
    p.add_argument("--report-json", type=Path, default=REPORT_JSON)
    p.add_argument("--report-md", type=Path, default=REPORT_MD)
    return p


FRAME_SQL = """
SELECT e.video_id, e.state_code, COALESCE(e.channel_id, '') AS channel_id,
       COALESCE(e.title, '') AS title,
       COALESCE(e.jurisdiction_id, '') AS jurisdiction_id,
       e.description, c.channel_title
FROM bronze.bronze_event_youtube e
JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = e.video_id
LEFT JOIN bronze.bronze_events_channels c ON c.channel_id = e.channel_id
WHERE t.has_transcript IS TRUE
  AND e.state_code IS NOT NULL
  AND (
    COALESCE(NULLIF(TRIM(e.title), ''), NULLIF(TRIM(e.description), '')) IS NOT NULL
  )
"""


def load_frame(database_url: str) -> list[dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(FRAME_SQL)
            return list(cur.fetchall())
    finally:
        conn.close()


def state_counts(frame: Sequence[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in frame:
        sc = str(r["state_code"]).upper()
        out[sc] = out.get(sc, 0) + 1
    return out


def rows_for_states(
    frame: Sequence[dict[str, Any]], states: Sequence[str]
) -> list[VideoRow]:
    want = {s.upper() for s in states}
    return [
        VideoRow(
            video_id=str(r["video_id"]),
            state_code=str(r["state_code"]).upper(),
            channel_id=str(r.get("channel_id") or ""),
            title=str(r.get("title") or ""),
            jurisdiction_id=str(r.get("jurisdiction_id") or ""),
        )
        for r in frame
        if str(r["state_code"]).upper() in want
    ]


def ensure_tables(database_url: str) -> None:
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(META_CREATE_SQL)
            cur.execute(TX_CREATE_SQL)
        conn.commit()
    finally:
        conn.close()


def load_meta_scores(
    database_url: str, video_ids: Sequence[str]
) -> dict[str, tuple[float | None, str | None, dict[str, float]]]:
    """video_id -> (keep_score, meeting_kind, probs)."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    if not video_ids:
        return {}
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT video_id, meeting_kind, meeting_kind_probabilities
                FROM {META_SCREEN_TABLE}
                WHERE question_version = %s AND video_id = ANY(%s)
                """,
                [META_QUESTION_VERSION, list(video_ids)],
            )
            out: dict[str, tuple[float | None, str | None, dict[str, float]]] = {}
            for r in cur.fetchall():
                probs = r["meeting_kind_probabilities"] or {}
                if isinstance(probs, str):
                    probs = json.loads(probs)
                probs = {k: float(v) for k, v in probs.items()}
                out[r["video_id"]] = (
                    meeting_keep_p(probs),
                    r["meeting_kind"],
                    probs,
                )
            return out
    finally:
        conn.close()


def load_tx_scores(
    database_url: str, video_ids: Sequence[str]
) -> dict[str, tuple[float | None, str | None]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    if not video_ids:
        return {}
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT video_id, meeting_kind, meeting_kind_probabilities
                FROM {TX_SCREEN_TABLE}
                WHERE question_version = %s AND video_id = ANY(%s)
                """,
                [TX_QUESTION_VERSION, list(video_ids)],
            )
            out: dict[str, tuple[float | None, str | None]] = {}
            for r in cur.fetchall():
                probs = r["meeting_kind_probabilities"] or {}
                if isinstance(probs, str):
                    probs = json.loads(probs)
                out[r["video_id"]] = (meeting_keep_p(probs), r["meeting_kind"])
            return out
    finally:
        conn.close()


def screen_meta_videos(
    database_url: str,
    frame_by_id: dict[str, dict[str, Any]],
    video_ids: Sequence[str],
    *,
    model: str,
    rescreen: bool,
) -> dict[str, Any]:
    existing = set() if rescreen else set(load_meta_scores(database_url, video_ids))
    todo = [v for v in video_ids if v not in existing]
    summary = {"todo": len(todo), "screened": 0, "empty": 0, "failed": 0}
    if not todo:
        logger.info("Meta screens already present for all {:,} pool videos", len(video_ids))
        return summary
    logger.info("Meta-screening {:,} / {:,} pool videos", len(todo), len(video_ids))
    import psycopg2

    with JevClient(model=model or None) as client:
        conn = psycopg2.connect(database_url)
        try:
            for i, vid in enumerate(todo, 1):
                row = frame_by_id[vid]
                state = build_meta_state(
                    title=row.get("title"),
                    description=row.get("description"),
                    channel_title=row.get("channel_title"),
                )
                try:
                    result = screen_meta(client, vid, state)
                except JevError as exc:
                    summary["failed"] += 1
                    logger.warning("[meta {}/{}] {}: {}", i, len(todo), vid, exc)
                    if exc.status_code in (401, 403):
                        raise
                    continue
                if result is None:
                    summary["empty"] += 1
                    continue
                with conn.cursor() as cur:
                    cur.execute(META_UPSERT_SQL, result.row())
                conn.commit()
                summary["screened"] += 1
                if i % 50 == 0 or i == len(todo):
                    logger.info("[meta {}/{}] screened so far {:,}", i, len(todo), summary["screened"])
        finally:
            conn.close()
    return summary


def screen_tx_videos(
    database_url: str,
    video_ids: Sequence[str],
    *,
    model: str,
    rescreen: bool,
) -> dict[str, Any]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    existing = set() if rescreen else set(load_tx_scores(database_url, video_ids))
    todo = [v for v in video_ids if v not in existing]
    summary = {"todo": len(todo), "screened": 0, "empty": 0, "failed": 0}
    if not todo:
        logger.info("Transcript screens already present for all {:,}", len(video_ids))
        return summary
    logger.info("Transcript-screening {:,} / {:,} final videos", len(todo), len(video_ids))
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT t.video_id, t.language, t.is_auto_generated,
                       t.segments, t.caption_text_timed, t.raw_text
                FROM bronze.bronze_event_youtube_transcript t
                WHERE t.video_id = ANY(%s) AND t.has_transcript IS TRUE
                """,
                [todo],
            )
            tx_rows = {r["video_id"]: r for r in cur.fetchall()}
    finally:
        conn.close()

    with JevClient(model=model or None) as client:
        conn = psycopg2.connect(database_url)
        try:
            for i, vid in enumerate(todo, 1):
                row = tx_rows.get(vid)
                if not row:
                    summary["empty"] += 1
                    continue
                try:
                    result = screen_transcript(client, vid, _segment_texts(row))
                except JevError as exc:
                    summary["failed"] += 1
                    logger.warning("[tx {}/{}] {}: {}", i, len(todo), vid, exc)
                    if exc.status_code in (401, 403):
                        raise
                    continue
                if result is None:
                    summary["empty"] += 1
                    continue
                with conn.cursor() as cur:
                    cur.execute(TX_UPSERT_SQL, result.row())
                conn.commit()
                summary["screened"] += 1
                if i % 25 == 0 or i == len(todo):
                    logger.info("[tx {}/{}] screened so far {:,}", i, len(todo), summary["screened"])
        finally:
            conn.close()
    return summary


def build_export_rows(
    sampled: Sequence[SampledVideo],
    meta: dict[str, tuple[float | None, str | None, dict[str, float]]],
    tx: dict[str, tuple[float | None, str | None]],
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in sampled:
        m_keep, m_kind, _ = meta.get(s.video_id, (s.meta_keep_score, None, {}))
        t_keep, t_kind = tx.get(s.video_id, (None, None))
        m_gate = gate_label(m_keep, threshold)
        t_gate = gate_label(t_keep, threshold)
        out.append(
            {
                "video_id": s.video_id,
                "title": s.title,
                "state_code": s.state_code,
                "jurisdiction_id": s.jurisdiction_id,
                "channel_id": s.channel_id,
                "stratum": s.stratum,
                "sampling_weight": s.sampling_weight,
                "split": s.split,
                "transcript_kind": t_kind,
                "meta_kind": m_kind,
                "transcript_keep_score": t_keep,
                "meta_keep_score": m_keep,
                "transcript_gate": t_gate,
                "meta_gate": m_gate,
                "agree_at_threshold": t_gate == m_gate,
                "threshold": threshold,
                "youtube_url": f"https://www.youtube.com/watch?v={s.video_id}",
                "keep_kind_keys": ",".join(MEETING_KEEP_KIND_KEYS),
            }
        )
    return out


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fieldnames))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def write_report_md(
    path: Path,
    *,
    states: Sequence[str],
    seed: int,
    half_a: Sequence[dict[str, Any]],
    half_b: Sequence[dict[str, Any]],
    pick: dict[str, Any],
    n_sample: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "sidebar_position: 38",
        "title: Jev metadata gate validation results",
        "description: Half-A/B threshold table from the multi-state validation sample.",
        "---",
        "",
        "# Jev metadata gate validation results",
        "",
        f"Seed `{seed}`, states `{', '.join(states)}`, N={n_sample}. "
        "Design: [validation design](./jev-meta-gate-validation-design.md).",
        "",
        "## Half A (exploratory)",
        "",
        "| T | n | wrong skip | wrong keep | ws rate | wk rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in half_a:
        lines.append(
            f"| {r['threshold']:.1f} | {r['n']} | {r['wrong_skip_n']} | "
            f"{r['wrong_keep_n']} | {r['wrong_skip_rate']:.4f} | {r['wrong_keep_rate']:.4f} |"
        )
    lines += [
        "",
        "## Half B (binding)",
        "",
        "| T | n | wrong skip | wrong keep | ws rate | ws 95% CI | wk rate | wk 95% CI |",
        "|---|---:|---:|---:|---:|---|---:|---|",
    ]
    for r in half_b:
        lines.append(
            f"| {r['threshold']:.1f} | {r['n']} | {r['wrong_skip_n']} | {r['wrong_keep_n']} | "
            f"{r['wrong_skip_rate']:.4f} | [{r['wrong_skip_lo']:.4f}, {r['wrong_skip_ub']:.4f}] | "
            f"{r['wrong_keep_rate']:.4f} | [{r['wrong_keep_lo']:.4f}, {r['wrong_keep_ub']:.4f}] |"
        )
    chosen = pick.get("chosen")
    meets = pick.get("meets_bound")
    extra = pick.get("extra_transcripts")
    lines += [
        "",
        "## Chosen threshold",
        "",
        f"- **Chosen T:** `{chosen}`",
        f"- **Meets wrong-skip UB ≤ 2%:** `{meets}`",
        f"- **Extra transcripts (wrong keeps on half B):** `{extra}`",
        "",
        "Artifacts: `data/cache/jev_meta_gate_validation_sample.csv`, "
        "`jev_meta_gate_validation_disagreements.csv`, "
        "`jev_meta_gate_validation_report.json`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    database_url = _database_url(args.database_url)
    rng = random.Random(args.seed)
    ensure_tables(database_url)

    logger.info("Loading transcripted catalog frame…")
    frame = load_frame(database_url)
    counts = state_counts(frame)
    if args.states:
        states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    else:
        states = pick_states(
            counts, rng=rng, n_states=args.n_states, min_count=50
        )
    logger.success("States ({:,}): {}", len(states), ", ".join(states))

    frame_by_id = {str(r["video_id"]): r for r in frame}
    candidates = rows_for_states(frame, states)
    # Per-state quotas for the pool
    per_state_n = max(1, args.n_pool // max(1, len(states)))
    pool: list[VideoRow] = []
    for st in states:
        st_rows = [r for r in candidates if r.state_code == st]
        pool.extend(
            draw_channel_capped(
                st_rows,
                rng=rng,
                n=per_state_n,
                max_per_channel=args.max_per_channel,
            )
        )
    # Trim / top-up to n_pool
    if len(pool) > args.n_pool:
        rng.shuffle(pool)
        pool = pool[: args.n_pool]
    elif len(pool) < args.n_pool:
        have = {r.video_id for r in pool}
        extra = [r for r in candidates if r.video_id not in have]
        pool.extend(
            draw_channel_capped(
                extra,
                rng=rng,
                n=args.n_pool - len(pool),
                max_per_channel=args.max_per_channel,
            )
        )

    logger.info("Phase-1 pool: {:,} videos", len(pool))
    if args.dry_run:
        logger.success(
            "Dry run: states={} pool={:,} final target={:,}. Nothing screened.",
            states,
            len(pool),
            args.n_final,
        )
        return {"states": states, "pool": len(pool), "dry_run": True}

    pool_ids = [r.video_id for r in pool]
    if not args.skip_screen:
        screen_meta_videos(
            database_url,
            frame_by_id,
            pool_ids,
            model=args.model,
            rescreen=args.rescreen,
        )

    meta = load_meta_scores(database_url, pool_ids)
    scored: list[ScoredVideo] = []
    for r in pool:
        keep, _, _ = meta.get(r.video_id, (None, None, {}))
        if keep is None:
            continue
        scored.append(
            ScoredVideo(
                video_id=r.video_id,
                state_code=r.state_code,
                channel_id=r.channel_id,
                title=r.title,
                jurisdiction_id=r.jurisdiction_id,
                meta_keep_score=float(keep),
            )
        )
    logger.info("Scored pool with meta keep-score: {:,}", len(scored))

    sampled = stratified_final_draw(
        scored,
        rng=rng,
        n_final=args.n_final,
        max_per_channel=args.max_per_channel,
    )
    sampled = assign_ab_split(sampled, rng=rng)
    logger.info(
        "Final sample {:,}: band={:,} srs={:,} A={:,} B={:,}",
        len(sampled),
        sum(1 for s in sampled if s.stratum == "band"),
        sum(1 for s in sampled if s.stratum == "srs"),
        sum(1 for s in sampled if s.split == "A"),
        sum(1 for s in sampled if s.split == "B"),
    )

    final_ids = [s.video_id for s in sampled]
    if not args.skip_screen:
        screen_tx_videos(
            database_url, final_ids, model=args.model, rescreen=args.rescreen
        )

    meta = load_meta_scores(database_url, final_ids)
    tx = load_tx_scores(database_url, final_ids)
    # Drop rows without transcript answer key
    labeled = [s for s in sampled if s.video_id in tx and tx[s.video_id][0] is not None]
    if len(labeled) < len(sampled):
        logger.warning(
            "Dropping {:,} sample rows without transcript keep-score",
            len(sampled) - len(labeled),
        )

    # Use placeholder threshold for export gates; rewrite after pick
    export_probe = build_export_rows(labeled, meta, tx, threshold=0.5)
    half_a = rate_table(export_probe, thresholds=DEFAULT_THRESHOLDS, split_filter="A")
    half_b = rate_table(export_probe, thresholds=DEFAULT_THRESHOLDS, split_filter="B")
    pick = pick_threshold(half_b)
    chosen_t = float(pick["chosen"] if pick["chosen"] is not None else 0.5)
    export_rows = build_export_rows(labeled, meta, tx, threshold=chosen_t)
    # Recompute tables so gates in CSV match chosen T rates already computed
    half_a = rate_table(export_rows, thresholds=DEFAULT_THRESHOLDS, split_filter="A")
    half_b = rate_table(export_rows, thresholds=DEFAULT_THRESHOLDS, split_filter="B")
    pick = pick_threshold(half_b)

    fields = list(export_rows[0].keys()) if export_rows else [
        "video_id",
        "title",
        "state_code",
        "jurisdiction_id",
        "channel_id",
        "stratum",
        "sampling_weight",
        "split",
        "transcript_kind",
        "meta_kind",
        "transcript_keep_score",
        "meta_keep_score",
        "transcript_gate",
        "meta_gate",
        "agree_at_threshold",
        "threshold",
        "youtube_url",
        "keep_kind_keys",
    ]
    write_csv(args.sample_csv, export_rows, fields)

    disagrees = [
        {**r, "human_decision": ""}
        for r in export_rows
        if not r["agree_at_threshold"]
    ]
    write_csv(
        args.disagree_csv,
        disagrees,
        list(fields) + ["human_decision"],
    )

    report = {
        "seed": args.seed,
        "states": states,
        "n_pool": len(pool),
        "n_scored_pool": len(scored),
        "n_sample": len(export_rows),
        "n_disagreements": len(disagrees),
        "half_a": half_a,
        "half_b": half_b,
        "pick": {
            "chosen": pick["chosen"],
            "meets_bound": pick["meets_bound"],
            "extra_transcripts": pick["extra_transcripts"],
            "row": pick.get("row"),
        },
        "meta_question_version": META_QUESTION_VERSION,
        "transcript_question_version": TX_QUESTION_VERSION,
    }
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_report_md(
        args.report_md,
        states=states,
        seed=args.seed,
        half_a=half_a,
        half_b=half_b,
        pick=report["pick"],
        n_sample=len(export_rows),
    )

    logger.success(
        "Wrote sample={:,} disagrees={:,} chosen_T={} meets_bound={} extra_tx={}",
        len(export_rows),
        len(disagrees),
        pick["chosen"],
        pick["meets_bound"],
        pick["extra_transcripts"],
    )
    logger.info("CSV {} | {} | report {}", args.sample_csv, args.disagree_csv, args.report_json)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except JevError as exc:
        logger.error("{}", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
