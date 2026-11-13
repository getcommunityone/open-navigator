"""
Compare models on the transcript Part 1 analysis, on real meetings (#267).

Each *arm* is a model and a thinking budget. Every arm gets the same Part 1
message the pipeline would send for a meeting (``prepare_part1_request``), and
its answer is scored against a *reference*: by default the meeting's existing
analysis in the policy cache, or one of the arms (``--reference``)::

    # 10 meetings that already have an analysis, the default arms
    python -m llm.gemini.compare_models --jurisdiction-id municipality_0177256 --state AL --limit 10

    # Named meetings and arms; score against Flash with thinking instead of the cache
    python -m llm.gemini.compare_models --jurisdiction-id municipality_0177256 --state AL \\
        --video-id ajsME66iXbY --video-id x1y2z3 \\
        --arms gemini-2.5-flash:-1,gemini-2.5-flash-lite:0,gemma-4-26b-a4b-it \\
        --reference gemini-2.5-flash:-1

    # Re-score a finished run without calling any model
    python -m llm.gemini.compare_models --rescore data/cache/model_comparison/20261113T210000Z

An arm is ``model[:thinking_budget]``. The budget only applies to
``gemini-2.5-flash*`` (``0`` = off, ``-1`` = the model's own default) and is
ignored for other models: the 3.x models run at their own default thinking
level, and Gemma does not think.

Gemma generates far slower than Gemini: a Part 1 answer takes minutes. The
google-genai SDK sends the client's request timeout to Google as the server's
deadline, so at the pipeline's 300 s timeout Google itself stops a Gemma request
with "504 DEADLINE_EXCEEDED". This tool therefore raises the timeout to
``--request-timeout-seconds`` (default 1200) for its own process. Answers are written under ``--out-dir``, never into
the policy cache, so nothing in the pipeline changes. A run can be stopped and
re-run: an arm whose answer is on disk is not called again.

What the score measures: agreement with the reference, from the JSON alone, with
no model as judge. An item (contested decision or uncontested vote) matches when
its headline and statement share enough words with a reference item, or when both
start within 90 seconds of each other in the recording. Recall is the share of the
reference's items, people, places and dollar amounts the arm also found; precision
is the share of the arm's items the reference also has; vote agreement is the
share of matched items with the same yes/no count. Agreement is not correctness:
the reference can be the one that is wrong, so ``summary.md`` lists every item an
arm missed or added, for a person to check.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

DEFAULT_ARMS = (
    "gemini-2.5-flash:-1",
    "gemini-2.5-flash:0",
    "gemini-2.5-flash-lite:0",
    # successors: the 2.5 models are reported closed to new users (see usage/prices.yaml)
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    # open-weights models on the Gemini API; slow (minutes per meeting), see --request-timeout-seconds
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
)
DEFAULT_REQUEST_TIMEOUT_SECONDS = 1200
REFERENCE_EXISTING = "existing"

# Output-token ceilings the API enforces per model family; a request above the
# ceiling is refused outright, so the arm's request is capped to it.
_OUTPUT_TOKEN_CAPS = {"gemma-": 32768}

ITEM_MATCH_THRESHOLD = 0.25
TIMESTAMP_MATCH_SECONDS = 90.0
_STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "were", "will", "with", "approve", "approved", "approves", "approval", "council", "city", "board", "motion", "item", "vote", "voted"]
)
_HONORIFICS = frozenset(
    ["mr", "mrs", "ms", "dr", "mayor", "councilmember", "councilman", "councilwoman", "councilor", "commissioner", "alderman", "alderwoman", "chair", "chairman", "chairwoman", "vice", "president", "clerk", "manager", "attorney", "director", "resident", "member", "hon", "honorable", "sen", "rep"]
)
SCORE_COLUMNS = (
    "json_ok", "item_count", "reference_item_count", "decision_count", "reference_decision_count",
    "item_recall", "item_precision", "decision_recall", "vote_agreement", "people_recall",
    "place_recall", "amount_recall",
)  # fmt: skip


# --------------------------------------------------------------------------- #
# Arms
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Arm:
    label: str
    model: str
    thinking_budget: int | None  # None = the model's own default

    @property
    def slug(self) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", self.label)


def parse_arm(spec: str) -> Arm:
    """``model`` or ``model:budget``. No budget means 0 (off), the pipeline default;
    a negative budget means the model's own default."""
    spec = spec.strip()
    if not spec:
        raise ValueError("empty arm")
    model, _, budget = spec.partition(":")
    if not budget:
        return Arm(label=spec, model=model, thinking_budget=0)
    try:
        value = int(budget)
    except ValueError as exc:
        raise ValueError(f"arm {spec!r}: thinking budget must be an integer") from exc
    return Arm(label=spec, model=model, thinking_budget=None if value < 0 else value)


def parse_arms(spec: str | None) -> list[Arm]:
    raw = [s for s in re.split(r"[,\s]+", spec or "") if s.strip()] or list(DEFAULT_ARMS)
    arms: list[Arm] = []
    for item in raw:
        arm = parse_arm(item)
        if arm.label not in {a.label for a in arms}:
            arms.append(arm)
    return arms


def output_token_cap(model: str, requested: int) -> int:
    for prefix, cap in _OUTPUT_TOKEN_CAPS.items():
        if model.startswith(prefix):
            return min(requested, cap)
    return requested


# --------------------------------------------------------------------------- #
# Scoring (pure)
# --------------------------------------------------------------------------- #
def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_vote(value: Any) -> tuple[int, int] | None:
    """``(yes, no)`` from a ``vote_tally`` dict or a vote string such as ``"5-2"``."""
    if isinstance(value, dict):
        yes, no = _as_number(value.get("yes")), _as_number(value.get("no"))
        return (int(yes), int(no)) if yes is not None and no is not None else None
    if isinstance(value, str):
        m = re.search(r"(\d+)\s*(?:-|–|to)\s*(\d+)", value)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def analysis_items(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Contested decisions and uncontested votes as one list of comparable items."""
    items: list[dict[str, Any]] = []
    for kind, key, text_keys, vote_key in (
        ("decision", "decisions", ("headline", "decision_statement"), "vote_tally"),
        ("uncontested", "uncontested_items", ("headline", "one_line_summary"), "vote"),
    ):
        for row in analysis.get(key) or []:
            if not isinstance(row, dict):
                continue
            headline = str(row.get("headline") or "").strip()
            anchor = row.get("media_anchor") if isinstance(row.get("media_anchor"), dict) else {}
            items.append(
                {
                    "kind": kind,
                    "headline": headline or str(row.get(text_keys[1]) or "")[:120],
                    "words": _words(" ".join(str(row.get(k) or "") for k in text_keys)),
                    "start": _as_number(anchor.get("timestamp_start_seconds")),
                    "vote": parse_vote(row.get(vote_key)),
                }
            )
    return items


def item_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    score = _jaccard(a["words"], b["words"])
    if a["start"] is not None and b["start"] is not None and abs(a["start"] - b["start"]) <= TIMESTAMP_MATCH_SECONDS:
        score = max(score, 0.5)
    return score


def match_items(candidate: list[dict[str, Any]], reference: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Greedy one-to-one matching, most similar pairs first. ``[(candidate_i, reference_j)]``."""
    pairs = sorted(
        (
            (item_similarity(c, r), i, j)
            for i, c in enumerate(candidate)
            for j, r in enumerate(reference)
        ),
        reverse=True,
    )
    used_c: set[int] = set()
    used_r: set[int] = set()
    matched: list[tuple[int, int]] = []
    for score, i, j in pairs:
        if score < ITEM_MATCH_THRESHOLD:
            break
        if i in used_c or j in used_r:
            continue
        used_c.add(i)
        used_r.add(j)
        matched.append((i, j))
    return matched


def normalize_name(name: str) -> str:
    words = [w for w in re.findall(r"[a-z]+", (name or "").lower()) if w not in _HONORIFICS]
    return " ".join(words)


def _names(analysis: dict[str, Any]) -> list[str]:
    out = []
    for person in analysis.get("people") or []:
        if isinstance(person, dict):
            name = normalize_name(str(person.get("full_name") or ""))
            if name:
                out.append(name)
    return out


def _name_found(name: str, pool: list[str]) -> bool:
    """Same normalized name, or the same last name with a matching (or missing) first name."""
    if name in pool:
        return True
    parts = name.split()
    for other in pool:
        other_parts = other.split()
        same_last = bool(parts and other_parts) and parts[-1] == other_parts[-1]
        if same_last and (len(parts) == 1 or len(other_parts) == 1 or parts[0][0] == other_parts[0][0]):
            return True
    return False


_STREET_ABBREVIATIONS = {
    "street": "st", "avenue": "ave", "road": "rd", "drive": "dr", "court": "ct", "boulevard": "blvd",
    "lane": "ln", "place": "pl", "parkway": "pkwy", "highway": "hwy", "north": "n", "south": "s",
    "east": "e", "west": "w",
}  # fmt: skip


def _places(analysis: dict[str, Any]) -> list[set[str]]:
    out = []
    for place in analysis.get("places") or []:
        if isinstance(place, dict):
            raw = _words(str(place.get("normalized_address") or place.get("raw_text") or ""))
            words = {_STREET_ABBREVIATIONS.get(w, w) for w in raw}
            if words:
                out.append(words)
    return out


def _amounts(analysis: dict[str, Any]) -> set[float]:
    out = set()
    for item in analysis.get("financial_items") or []:
        if isinstance(item, dict):
            amount = _as_number(item.get("amount"))
            if amount:
                out.add(round(amount, 2))
    return out


def _ratio(found: int, total: int) -> float | None:
    return round(found / total, 3) if total else None


def score_analysis(candidate: dict[str, Any] | None, reference: dict[str, Any]) -> dict[str, Any]:
    """Agreement of one arm's analysis with the reference (see the module docstring).
    A ratio with nothing to count (an empty reference list) is ``None``, not 1."""
    ref_items = analysis_items(reference)
    ref_decisions = [i for i in ref_items if i["kind"] == "decision"]
    if not isinstance(candidate, dict) or not isinstance(candidate.get("meeting"), dict):
        return {
            "json_ok": False, "item_count": 0, "reference_item_count": len(ref_items), "decision_count": 0,
            "reference_decision_count": len(ref_decisions), "item_recall": 0.0 if ref_items else None,
            "item_precision": None, "decision_recall": 0.0 if ref_decisions else None, "vote_agreement": None,
            "people_recall": 0.0 if _names(reference) else None, "place_recall": 0.0 if _places(reference) else None,
            "amount_recall": 0.0 if _amounts(reference) else None, "missed": [i["headline"] for i in ref_items],
            "added": [], "vote_mismatches": [],
        }  # fmt: skip
    cand_items = analysis_items(candidate)
    matched = match_items(cand_items, ref_items)
    matched_ref = {j for _, j in matched}
    matched_cand = {i for i, _ in matched}
    decision_hits = sum(1 for _, j in matched if ref_items[j]["kind"] == "decision")
    voted = [(cand_items[i]["vote"], ref_items[j]["vote"]) for i, j in matched if ref_items[j]["vote"] is not None]
    ref_names, cand_names = _names(reference), _names(candidate)
    ref_places, cand_places = _places(reference), _places(candidate)
    ref_amounts, cand_amounts = _amounts(reference), _amounts(candidate)
    return {
        "json_ok": True,
        "item_count": len(cand_items),
        "reference_item_count": len(ref_items),
        "decision_count": sum(1 for i in cand_items if i["kind"] == "decision"),
        "reference_decision_count": len(ref_decisions),
        "item_recall": _ratio(len(matched), len(ref_items)),
        "item_precision": _ratio(len(matched), len(cand_items)),
        "decision_recall": _ratio(decision_hits, len(ref_decisions)),
        "vote_agreement": _ratio(sum(1 for c, r in voted if c == r), len(voted)),
        "people_recall": _ratio(sum(1 for n in ref_names if _name_found(n, cand_names)), len(ref_names)),
        "place_recall": _ratio(
            sum(1 for p in ref_places if any(_jaccard(p, q) >= 0.5 for q in cand_places)), len(ref_places)
        ),
        "amount_recall": _ratio(len(ref_amounts & cand_amounts), len(ref_amounts)),
        "missed": [ref_items[j]["headline"] for j in range(len(ref_items)) if j not in matched_ref],
        "added": [cand_items[i]["headline"] for i in range(len(cand_items)) if i not in matched_cand],
        "vote_mismatches": [
            f"{ref_items[j]['headline']}: reference {_vote_text(ref_items[j]['vote'])}, "
            f"arm {_vote_text(cand_items[i]['vote'])}"
            for i, j in matched
            if ref_items[j]["vote"] is not None and cand_items[i]["vote"] != ref_items[j]["vote"]
        ],
    }


def _vote_text(vote: tuple[int, int] | None) -> str:
    return f"{vote[0]}-{vote[1]}" if vote else "none"


def parse_answer(text: str | None) -> dict[str, Any] | None:
    """An arm's raw answer as Part 1 JSON, or ``None`` when it isn't any."""
    from llm.gemini.genai_text_client import extract_json_from_model_text
    from llm.gemini.meeting_transcript_policy import coalesce_part1_analysis

    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = extract_json_from_model_text(text)
    data = coalesce_part1_analysis(data) if isinstance(data, dict) else None
    return data if data and isinstance(data.get("meeting"), dict) else None


# --------------------------------------------------------------------------- #
# Summary (pure)
# --------------------------------------------------------------------------- #
def _mean(values: list[Any]) -> float | None:
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return round(statistics.fmean(nums), 3) if nums else None


def summarize(rows: list[dict[str, Any]], arm_labels: list[str], prices: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per arm: mean scores over the meetings, mean usage per call, and the
    mean cost per call when every call has a priced model (else ``None``)."""
    from llm.usage.prices import call_cost_usd

    out = []
    for label in arm_labels:
        mine = [r for r in rows if r["arm"] == label]
        if not mine:
            continue
        costs = [call_cost_usd(r, prices) for r in mine if r.get("is_ok")]
        summary: dict[str, Any] = {"arm": label, "meeting_count": len(mine)}
        summary["call_failed_count"] = sum(1 for r in mine if not r.get("is_ok"))
        summary["json_ok_rate"] = _mean([1.0 if r.get("json_ok") else 0.0 for r in mine])
        for column in ("item_recall", "item_precision", "decision_recall", "vote_agreement",
                       "people_recall", "place_recall", "amount_recall"):  # fmt: skip
            summary[column] = _mean([r.get(column) for r in mine])
        for column in ("input_token_count", "output_token_count", "thinking_token_count", "latency_seconds"):
            summary[f"mean_{column}"] = _mean([r.get(column) for r in mine])
        summary["mean_cost_usd"] = (
            round(statistics.fmean(costs), 5) if costs and all(c is not None for c in costs) else None
        )
        out.append(summary)
    return out


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".") if abs(value) < 1000 else f"{value:,.0f}"
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
    return str(value)


def render_markdown(meta: dict[str, Any], summary: list[dict[str, Any]], rows: list[dict[str, Any]]) -> str:
    columns = ["arm", "meeting_count", "call_failed_count", "json_ok_rate", "item_recall", "item_precision",
               "decision_recall", "vote_agreement", "people_recall", "place_recall", "amount_recall",
               "mean_input_token_count", "mean_output_token_count", "mean_thinking_token_count",
               "mean_latency_seconds", "mean_cost_usd"]  # fmt: skip
    lines = [
        "# Model comparison: transcript Part 1",
        "",
        (
            f"Run `{meta['run_id']}`, {meta['created_at']}. Reference: **{meta['reference']}**. "
            f"Meetings: {len(meta['video_ids'])}."
        ),
        "",
        (
            "Scores are agreement with the reference, not correctness. A dash means there was nothing to "
            "count (or, for cost, no sourced price in `prices.yaml`)."
        ),
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for s in summary:
        lines.append("| " + " | ".join(_fmt(s.get(c)) for c in columns) + " |")
    lines += ["", "## Items to check by hand", ""]
    for row in rows:
        if not (row.get("missed") or row.get("added") or row.get("vote_mismatches") or not row.get("json_ok")):
            continue
        lines.append(f"### {row['video_id']} · {row['arm']}")
        if not row.get("is_ok"):
            lines.append(f"- call failed: {row.get('error') or 'unknown'}")
        elif not row.get("json_ok"):
            lines.append("- the answer was not Part 1 JSON")
        lines += [f"- missed: {h}" for h in row.get("missed") or []]
        lines += [f"- added: {h}" for h in row.get("added") or []]
        lines += [f"- vote differs: {v}" for v in row.get("vote_mismatches") or []]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Running the arms
# --------------------------------------------------------------------------- #
def _reference_analysis(request: Any) -> dict[str, Any] | None:
    from llm.gemini.meeting_transcript_policy import coalesce_part1_analysis
    from llm.gemini.transcript_cache_paths import resolve_analysis_path

    video = request.video
    path = resolve_analysis_path(
        request.out_dir,
        video.jurisdiction_id,
        video_id=video.video_id,
        title=video.title or "",
        event_date=video.event_date,
        state_code=request.state_code,
        channel_id=getattr(video, "channel_id", None),
    )
    if path is None:
        return None
    try:
        data = coalesce_part1_analysis(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data.get("meeting"), dict) else None


def run_arm(arm: Arm, request: Any, video_dir: Path, args: argparse.Namespace, api_key: str) -> dict[str, Any]:
    """Call one arm for one meeting (or read its saved answer). Returns the call record."""
    from llm.gemini.genai_text_client import call_gemini_text
    from llm.usage.calls import llm_call_context

    answer_path = video_dir / f"{arm.slug}.txt"
    record_path = video_dir / f"{arm.slug}.call.json"
    if answer_path.is_file() and record_path.is_file():
        return json.loads(record_path.read_text(encoding="utf-8"))
    record: dict[str, Any] = {"arm": arm.label, "model": arm.model, "api_mode": "interactive",
                              "video_id": request.video.video_id}  # fmt: skip
    try:
        with llm_call_context(stage="compare", video_id=request.video.video_id,
                              jurisdiction_id=request.video.jurisdiction_id):  # fmt: skip
            result = call_gemini_text(
                api_key=api_key,
                model=arm.model,
                user_text=request.user_message,
                temperature=args.temperature,
                max_output_tokens=output_token_cap(arm.model, args.max_output_tokens),
                thinking_budget=arm.thinking_budget,
                json_mode=not args.no_json_mode,
            )
        answer_path.write_text(result.text, encoding="utf-8")
        record.update(result.usage.as_dict() if result.usage is not None else {})
        record["is_ok"] = True
    except Exception as exc:  # noqa: BLE001 - one arm failing must not stop the comparison
        logger.warning("{} failed on {}: {}", arm.label, request.video.video_id, exc)
        record.update({"is_ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]})
        return record  # not saved: a failed arm is tried again on the next run
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def score_run(run_dir: Path, arms: list[Arm], reference: str) -> list[dict[str, Any]]:
    """Score every saved answer in a run against the reference."""
    rows: list[dict[str, Any]] = []
    for video_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        ref_path = video_dir / "reference.json"
        if reference == REFERENCE_EXISTING:
            ref = json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.is_file() else None
        else:
            ref_arm = next((a for a in arms if a.label == reference), None)
            ref_file = video_dir / f"{ref_arm.slug}.txt" if ref_arm else None
            ref = parse_answer(ref_file.read_text(encoding="utf-8")) if ref_file and ref_file.is_file() else None
        if ref is None:
            logger.warning("No reference for {} — not scored", video_dir.name)
            continue
        for arm in arms:
            if arm.label == reference:
                continue
            record_path = video_dir / f"{arm.slug}.call.json"
            failed_path = video_dir / f"{arm.slug}.failed.json"
            if record_path.is_file():
                record = json.loads(record_path.read_text(encoding="utf-8"))
                answer = (video_dir / f"{arm.slug}.txt").read_text(encoding="utf-8")
                scored = score_analysis(parse_answer(answer), ref)
            elif failed_path.is_file():
                record = json.loads(failed_path.read_text(encoding="utf-8"))
                scored = score_analysis(None, ref)
            else:
                continue
            rows.append({"video_id": video_dir.name, **record, **scored})
    return rows


def write_outputs(run_dir: Path, meta: dict[str, Any], rows: list[dict[str, Any]], arms: list[Arm]) -> Path:
    from llm.usage.prices import load_prices

    labels = [a.label for a in arms if a.label != meta["reference"]]
    summary = summarize(rows, labels, load_prices())
    columns = ["video_id", "arm", "model", "is_ok", *SCORE_COLUMNS, "input_token_count",
               "cached_input_token_count", "output_token_count", "thinking_token_count",
               "latency_seconds", "attempt_count", "error"]  # fmt: skip
    with (run_dir / "comparison.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    out = run_dir / "summary.md"
    out.write_text(render_markdown(meta, summary, rows), encoding="utf-8")
    return out


def _requests(args: argparse.Namespace) -> list[Any]:
    """The meetings to compare: ``--video-id`` ones, else the newest with an existing analysis."""
    from llm.gemini.analyze_backlog import (
        JurisdictionPlan,
        _resolve_database_url,
        build_pipeline_namespace,
    )
    from llm.gemini.meeting_transcript_policy import (
        _policy_state_code,
        load_speaker_context,
        prepare_part1_request,
        select_bronze_videos,
    )
    from llm.gemini.transcript_cache_paths import resolve_canonical_jurisdiction_id

    database_url = _resolve_database_url(args.database_url or None)
    plan = JurisdictionPlan(jurisdiction_id=args.jurisdiction_id, state_code=args.state or "",
                            pending=0, newest_pending=None)  # fmt: skip
    ns = build_pipeline_namespace(plan, model="", database_url=database_url, limit=None)
    ns.output_dir = Path(args.output_dir)
    ns.limit = None if args.video_id else max(args.limit * 4, args.limit)
    jurisdiction_id = resolve_canonical_jurisdiction_id(args.jurisdiction_id)
    speaker_hints, known = load_speaker_context(ns, jurisdiction_id)
    wanted = set(args.video_id or [])
    requests: list[Any] = []
    for video in select_bronze_videos(ns, jurisdiction_id):
        if wanted and video.video_id not in wanted:
            continue
        request = prepare_part1_request(video, ns, speaker_hints=speaker_hints, known=known)
        if request is None:
            continue
        request.state_code = request.state_code or _policy_state_code(ns)
        if args.reference == REFERENCE_EXISTING and _reference_analysis(request) is None:
            continue
        requests.append(request)
        if not wanted and len(requests) >= args.limit:
            break
    return requests


def run_comparison(args: argparse.Namespace) -> Path:
    from llm.gemini.browser_policy_analysis import _REPO_ROOT
    from llm.gemini.genai_text_client import ensure_valid_gemini_api_key

    arms = parse_arms(args.arms)
    meta: dict[str, Any] = {}
    if args.rescore:
        run_dir = Path(args.rescore)
        meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        arms = parse_arms(",".join(meta["arms"]))
        if args.reference != REFERENCE_EXISTING:
            meta["reference"] = args.reference
    reference = meta.get("reference", args.reference)
    if reference != REFERENCE_EXISTING and reference not in {a.label for a in arms}:
        raise SystemExit(f"--reference {reference!r} is not one of the arms: {[a.label for a in arms]}")
    if not args.rescore:
        requests = _requests(args)
        if not requests:
            raise SystemExit("No meeting to compare (with --reference existing, a meeting needs an analysis).")
        now = datetime.now(UTC)
        run_dir = Path(args.out_dir) / now.strftime("%Y%m%dT%H%M%SZ") if not args.run_dir else Path(args.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        meta = {"run_id": run_dir.name, "created_at": now.isoformat(), "reference": args.reference,
                "arms": [a.label for a in arms], "video_ids": [r.video.video_id for r in requests],
                "jurisdiction_id": args.jurisdiction_id}  # fmt: skip
        (run_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        api_key = ensure_valid_gemini_api_key(env_path=_REPO_ROOT / ".env")
        for n, request in enumerate(requests, 1):
            video_dir = run_dir / request.video.video_id
            video_dir.mkdir(exist_ok=True)
            if args.reference == REFERENCE_EXISTING:
                ref = _reference_analysis(request)
                (video_dir / "reference.json").write_text(json.dumps(ref, ensure_ascii=False) + "\n", encoding="utf-8")
            for arm in arms:
                logger.info("[{}/{}] {} · {}", n, len(requests), request.video.video_id, arm.label)
                record = run_arm(arm, request, video_dir, args, api_key)
                failed = video_dir / f"{arm.slug}.failed.json"
                if record.get("is_ok"):
                    failed.unlink(missing_ok=True)
                else:
                    failed.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    rows = score_run(run_dir, arms, meta["reference"])
    out = write_outputs(run_dir, meta, rows, arms)
    logger.success("Comparison written to {}", out)
    return out


def build_parser() -> argparse.ArgumentParser:
    from llm.gemini.browser_policy_analysis import _REPO_ROOT
    from llm.gemini.meeting_transcript_policy import DEFAULT_OUTPUT_DIR

    parser = argparse.ArgumentParser(
        description="Compare models on the transcript Part 1 analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--jurisdiction-id", default="", help="Jurisdiction whose meetings to compare")
    parser.add_argument("--state", default="", help="State code of the jurisdiction")
    parser.add_argument("--video-id", action="append", default=None, help="A meeting to compare (repeatable)")
    parser.add_argument("--limit", type=int, default=10, help="Meetings to compare when no --video-id is given")
    parser.add_argument("--arms", default="", help=f"Comma-separated model[:thinking_budget] (default: {','.join(DEFAULT_ARMS)})")
    parser.add_argument("--reference", default=REFERENCE_EXISTING,
                        help="'existing' (the meeting's analysis in the policy cache) or one of the arms")  # fmt: skip
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Policy cache root (read only)")
    parser.add_argument("--out-dir", type=Path, default=_REPO_ROOT / "data" / "cache" / "model_comparison")
    parser.add_argument("--run-dir", default="", help="Resume this run folder instead of starting a new one")
    parser.add_argument("--rescore", default="", help="Score a finished run folder again, with no model calls")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-output-tokens", type=int, default=65536)
    parser.add_argument("--no-json-mode", action="store_true")
    parser.add_argument("--request-timeout-seconds", type=int, default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
                        help="Per-request timeout, also Google's server deadline (default 1200 for Gemma)")  # fmt: skip
    return parser


def main() -> None:
    from dotenv import load_dotenv

    from llm.gemini.browser_policy_analysis import _REPO_ROOT

    load_dotenv(_REPO_ROOT / ".env")
    args = build_parser().parse_args()
    # Before any client exists: clients are built once per key with this timeout.
    os.environ["GOVERNANCE_GENAI_REQUEST_TIMEOUT_SECONDS"] = str(args.request_timeout_seconds)
    if not args.rescore and not args.jurisdiction_id:
        raise SystemExit("--jurisdiction-id is required (or --rescore <run folder>)")
    run_comparison(args)


if __name__ == "__main__":
    main()
