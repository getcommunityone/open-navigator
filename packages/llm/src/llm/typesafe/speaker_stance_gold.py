"""Check the speaker side question against hand-labelled speakers before any run at scale (#1391).

The gold set (``gold/speaker_stance_gold.json``) is a list of real public speakers, per topic, each labelled by hand
from the exact passage Jev is sent (:func:`llm.typesafe.speaker_stance.build_state`): ``for``, ``against``,
``concerns_only``, ``no_position`` or ``off_topic``, and ``clear`` when the speaker's side is plain from their words.
The file holds no speech: only the speaker key (a hash), the topic, the label and the passage's SHA-256, so the
passage is rebuilt from the warehouse and checked unchanged before it is sent.

A topic passes when, on its clear for / against items, Jev's side agrees at least ``PASS_ACCURACY`` of the time and
never swaps for and against (:func:`agreement`). The answers of the committed run are in
``gold/speaker_stance_gold_results.json``; ``tests/test_speaker_stance.py`` recomputes the numbers from them.

Usage::

    python -m llm.typesafe.speaker_stance_gold sample --per-topic 30 --out <scratch>/candidates.jsonl   # free
    python -m llm.typesafe.speaker_stance_gold score                                                    # paid, cents
    python -m llm.typesafe.speaker_stance_gold report                                                   # free
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from loguru import logger

from llm.typesafe import speaker_stance as ss

GOLD_DIR = Path(__file__).with_name("gold")
GOLD_FILE = GOLD_DIR / "speaker_stance_gold.json"
RESULTS_FILE = GOLD_DIR / "speaker_stance_gold_results.json"
#: Round 2 (#1436): the coverage topics plus more items for held bike lanes and zoning. Its labels were made by an AI
#: helper from the exact passage (blind to Jev), and the file says so in ``labelled_by``.
ROUND2_GOLD_FILE = GOLD_DIR / "speaker_stance_gold_round2.json"
ROUND2_RESULTS_FILE = GOLD_DIR / "speaker_stance_gold_round2_results.json"
PASS_ACCURACY = 0.85
#: A topic also needs this many clear items (fewer can't show 85%), and at least this share of its served sides
#: (for / against at the confidence floor, on all its gold items) matching the hand label.
MIN_CLEAR = 8
MIN_SIDED_PRECISION = 0.80
SIDED = ("for", "against")
#: First-person stance cues near the topic passage (round 2 of sampling: the free shape rules read a speaker's whole
#: text, so their cue is often about something else; this asks for one inside the passage Jev sees).
CUE_RE = re.compile(
    r"\b(?:i|we)(?:'m| am| are)?\s+(?:strongly\s+|really\s+|fully\s+)?(?:support|oppose|object|urge|ask you|"
    r"am against|are against|am opposed|are opposed|am in favor|are in favor|am for|do not support|don't support|"
    r"don't want|do not want|want you to)|\bplease\s+(?:vote|deny|reject|approve|support|oppose|do not|don't)|"
    r"\bvote\s+(?:no|yes|against|in favor)\b",
    re.IGNORECASE,
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def agreement(items: Sequence[Mapping[str, Any]], predictions: Mapping[str, Mapping[str, Any]],
              *, min_confidence: float = 0.0) -> dict[str, dict[str, Any]]:
    """Per topic: on clear for / against items, how often Jev's side matches (``clear_accuracy``), how many it swapped
    (for read as against or back) and how many it still serves at ``min_confidence``; the precision of the sides it
    serves at ``min_confidence`` over all items (``sided_precision``); exact agreement on all items. ``passes``: at least
    MIN_CLEAR clear items, clear accuracy >= PASS_ACCURACY, no swap, and sided precision >= MIN_SIDED_PRECISION."""
    out: dict[str, dict[str, Any]] = {}
    for it in items:
        key = f"{it['topic']}|{it['meeting_speaker_id']}"
        pred = predictions.get(key)
        if pred is None:
            continue
        t = out.setdefault(it["topic"], {"items": 0, "exact": 0, "clear": 0, "clear_correct": 0, "swaps": 0,
                                         "clear_kept": 0, "clear_kept_correct": 0, "sided": 0, "sided_correct": 0})
        t["items"] += 1
        t["exact"] += int(pred["side"] == it["label"])
        if pred["side"] in SIDED and (pred.get("side_confidence") or 0) >= min_confidence:
            t["sided"] += 1
            t["sided_correct"] += int(pred["side"] == it["label"])
        if it.get("clear") and it["label"] in SIDED:
            t["clear"] += 1
            t["clear_correct"] += int(pred["side"] == it["label"])
            t["swaps"] += int(pred["side"] in SIDED and pred["side"] != it["label"])
            if (pred.get("side_confidence") or 0) >= min_confidence:
                t["clear_kept"] += 1
                t["clear_kept_correct"] += int(pred["side"] == it["label"])
    for t in out.values():
        t["exact_accuracy"] = round(t["exact"] / t["items"], 3) if t["items"] else None
        t["clear_accuracy"] = round(t["clear_correct"] / t["clear"], 3) if t["clear"] else None
        t["clear_kept_accuracy"] = round(t["clear_kept_correct"] / t["clear_kept"], 3) if t["clear_kept"] else None
        t["sided_precision"] = round(t["sided_correct"] / t["sided"], 3) if t["sided"] else None
        t["passes"] = bool(
            t["clear"] >= MIN_CLEAR and t["clear_accuracy"] >= PASS_ACCURACY and t["swaps"] == 0
            and t["sided_precision"] is not None and t["sided_precision"] >= MIN_SIDED_PRECISION
        )
    return out


def load_gold(path: Path = GOLD_FILE) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def _speaker_texts(conn: Any, ids: Sequence[str]) -> dict[str, tuple[str, str, Any]]:
    sql = ss.SPEAKERS_SQL.replace("WHERE p.is_public_comment", "WHERE p.meeting_speaker_id = ANY(%s) AND p.is_public_comment")
    with conn.cursor() as cur:
        cur.execute(sql, [list(ids)])
        return {r[0]: (r[1], r[3], r[2]) for r in cur.fetchall()}


def sample(args: argparse.Namespace) -> None:
    """Candidates to label (free): per topic, public speakers whose passage is short enough to read, half with a
    'for' cue shape and half with an 'against' one where they exist, then others. Writes JSONL to ``--out`` (a scratch
    path: it holds speech and is never committed)."""
    import psycopg2

    from llm.typesafe.screen_transcripts import _database_url

    topics = ss.resolve_topics(args.topic)
    conn = psycopg2.connect(_database_url(args.database_url))
    try:
        patterns = ss.topic_patterns(conn, topics)
        with conn.cursor() as cur:
            cur.execute("SELECT meeting_speaker_id, stance_shape FROM gold.meeting_speaker_position WHERE is_public_comment")
            shapes = dict(cur.fetchall())
        speakers = ss.load_speakers(conn)
    finally:
        conn.close()
    skip: set[str] = set()
    for prior in args.exclude or []:
        skip |= {json.loads(line)["state_sha256"] for line in Path(prior).read_text(encoding="utf-8").splitlines()}
    rng = random.Random(1391)
    rng.shuffle(speakers)
    with Path(args.out).open("w", encoding="utf-8") as fh:
        for t in topics:
            buckets: dict[str, list[dict[str, Any]]] = {"for": [], "against": [], "other": []}
            for sid, vid, mdate, txt in speakers:
                state = ss.build_state(txt or "", patterns[t.slug])
                if not state or len(state) > args.max_chars:
                    continue
                if args.cue and not CUE_RE.search(state):
                    continue
                if sha(state) in skip:
                    continue
                shape = shapes.get(sid, "unclear")
                b = "for" if shape in ("clear_for", "conditional", "for_concept_against_project") else (
                    "against" if shape in ("clear_against", "against_concept_open_to_terms") else "other")
                buckets[b].append({"topic": t.slug, "meeting_speaker_id": sid, "stance_shape": shape,
                                   "meeting_date": str(mdate), "state_sha256": sha(state), "state": state})
            n = args.per_topic
            picked = buckets["for"][: n * 2 // 5] + buckets["against"][: n * 2 // 5]
            picked += buckets["other"][: n - len(picked)]
            fh.writelines(json.dumps(row) + "\n" for row in picked)
            logger.info("{}: {} candidates (for-cue {}, against-cue {}, other {})", t.slug, len(picked),
                        len(buckets["for"]), len(buckets["against"]), len(buckets["other"]))


def score(args: argparse.Namespace) -> None:
    """Send each gold passage to Jev (paid, cents) and write the answers to RESULTS_FILE."""
    import psycopg2

    from llm.typesafe.client import JevClient, JevError
    from llm.typesafe.screen_transcripts import _database_url
    from llm.usage.prices import load_prices, model_price

    args.rate = (model_price("jev-", "interactive", load_prices()) or {}).get("input_usd_per_1m") or 0.0
    if not args.rate:
        raise SystemExit("No sourced Jev price in llm/usage/prices.yaml: refusing to score without a cost bound")
    gold_file = Path(args.gold) if args.gold else GOLD_FILE
    results_file = Path(args.results) if args.results else RESULTS_FILE
    items = load_gold(gold_file)
    conn = psycopg2.connect(_database_url(args.database_url))
    try:
        # every topic the gold items name, held ones included (a gold check is how a held topic is released)
        topics = [ss.TOPICS[slug] for slug in sorted({it["topic"] for it in items})]
        patterns = ss.topic_patterns(conn, topics)
        texts = _speaker_texts(conn, sorted({it["meeting_speaker_id"] for it in items}))
    finally:
        conn.close()
    # resumable: answers already in the results file at the topic's current question version are kept, not re-asked
    preds: dict[str, dict[str, Any]] = {}
    if results_file.exists():
        prior = json.loads(results_file.read_text(encoding="utf-8")).get("predictions", {})
        preds = {k: v for k, v in prior.items()
                 if v.get("question_version") == ss.question_version(ss.TOPICS[k.split("|", 1)[0]])}
    tokens = sum(v.get("input_tokens") or 0 for v in preds.values())
    stopped = None
    with JevClient() as client:
        for it in items:
            if f"{it['topic']}|{it['meeting_speaker_id']}" in preds:
                continue
            if args.max_usd and tokens * args.rate / 1_000_000 >= args.max_usd:
                stopped = f"budget ${args.max_usd}"
                break
            topic = ss.TOPICS[it["topic"]]
            vid, txt, _ = texts.get(it["meeting_speaker_id"], (None, None, None))
            state = ss.build_state(txt or "", patterns[topic.slug])
            if not state or sha(state) != it["state_sha256"]:
                logger.warning("{} {}: passage changed or missing; skipped", it["topic"], it["meeting_speaker_id"])
                continue
            try:
                r = ss.ask(client, speaker_id=it["meeting_speaker_id"], video_id=vid, topic=topic, state=state)
            except JevError as exc:
                if exc.status_code in ss.STOP_STATUSES:
                    stopped = f"Jev {exc.status_code}"
                    logger.error("Stopping cleanly: {} (rerun the same command after a top-up)", exc)
                    break
                logger.warning("{} {}: {}", it["topic"], it["meeting_speaker_id"], exc)
                continue
            tokens += r.input_tokens or 0
            preds[f"{it['topic']}|{it['meeting_speaker_id']}"] = {
                "side": r.side, "side_confidence": r.side_confidence, "side_probabilities": r.side_probabilities,
                "heat": r.heat, "question_version": ss.question_version(topic), "input_tokens": r.input_tokens,
                "input_chars": len(state),
            }
    results_file.write_text(json.dumps({"model_versions": sorted({"jev"}), "input_tokens": tokens,
                                        "predictions": preds}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    logger.success("Scored {} gold items, {:,} input tokens; stopped: {}", len(preds), tokens, stopped)
    report(args)


def combined(gold_files: Sequence[Path], results_files: Sequence[Path]) -> dict[str, dict[str, Any]]:
    """The gate over several rounds at once (held bike lanes / zoning: round 1 + round 2 items together). An item in
    two rounds counts once; answers are matched by topic and speaker."""
    items: dict[str, dict[str, Any]] = {}
    for g in gold_files:
        for it in load_gold(g):
            items.setdefault(f"{it['topic']}|{it['meeting_speaker_id']}", it)
    preds: dict[str, Any] = {}
    for r in results_files:
        if r.exists():
            preds.update(json.loads(r.read_text(encoding="utf-8"))["predictions"])
    return agreement(list(items.values()), preds, min_confidence=ss.MIN_SIDE_CONFIDENCE)


def report(args: argparse.Namespace) -> None:
    g = getattr(args, "gold", "") or ""
    r = getattr(args, "results", "") or ""
    if getattr(args, "all_rounds", False):
        res = combined([GOLD_FILE, ROUND2_GOLD_FILE], [RESULTS_FILE, ROUND2_RESULTS_FILE])
        print(json.dumps(res, indent=1, sort_keys=True))
        return
    preds = json.loads(Path(r or RESULTS_FILE).read_text(encoding="utf-8"))["predictions"]
    res = agreement(load_gold(Path(g or GOLD_FILE)), preds, min_confidence=ss.MIN_SIDE_CONFIDENCE)
    print(json.dumps(res, indent=1, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--topic", default="all")
    s.add_argument("--per-topic", type=int, default=30)
    s.add_argument("--max-chars", type=int, default=1800)
    s.add_argument("--out", required=True)
    s.add_argument("--cue", action="store_true", help="only passages with a first-person stance cue")
    s.add_argument("--exclude", action="append", help="a prior candidates file whose passages to skip")
    s.add_argument("--database-url", default="")
    for name in ("score", "report"):
        q = sub.add_parser(name)
        q.add_argument("--database-url", default="")
        q.add_argument("--gold", default="", help=f"gold file (default {GOLD_FILE.name}; round 2: {ROUND2_GOLD_FILE.name})")
        q.add_argument("--results", default="", help=f"answers file (default {RESULTS_FILE.name})")
        q.add_argument("--max-usd", type=float, default=0.5, help="score: stop once spend reaches this")
        q.add_argument("--all-rounds", action="store_true", help="report: the gate over round 1 + round 2 together")
        q.add_argument("--rate", type=float, default=0.0, help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    {"sample": sample, "score": score, "report": report}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
