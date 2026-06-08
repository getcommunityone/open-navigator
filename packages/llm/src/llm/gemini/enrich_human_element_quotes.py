"""Backfill verbatim quotes + exact timestamps onto EXISTING human_element moments.

Why this exists (vs re-analysis): the decision page's "jump to this moment" links
need a real timestamp. The stored `human_element` stories/lighter-moments carry a
paraphrased `summary`/`story_detail` but no quote, so the UI can't locate them and
used to fuzzy-match the paraphrase → wrong spot. Full re-analysis would regenerate
everything and can re-classify a contested decision as uncontested, silently
DELETING the very moments we want to keep.

This pass is non-destructive: it reads each existing analysis JSON, asks the model
ONLY to extract the verbatim transcript line for each moment (a span-selection task,
not generation), then locates that exact quote in the timestamped segments to stamp
`timestamp_start_seconds` (via :mod:`llm.gemini.quote_timestamps`). Moments keep all
their existing fields; we only ADD `evidence_quote`/`quote` + `timestamp_start_seconds`.

Run (dry-run by default)::

    python -m llm.gemini.enrich_human_element_quotes --limit 5 --model gemini-2.5-flash-lite
    python -m llm.gemini.enrich_human_element_quotes --limit 5 --write   # persist to cache JSON
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from loguru import logger

from llm.gemini.diarize_postprocess import format_diarized_transcript
from llm.gemini.genai_text_client import call_gemini_text, resolve_gemini_api_keys
from llm.gemini.quote_timestamps import resolve_human_element_timestamps
from llm.gemini.transcript_db import fetch_db_transcript

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_CACHE = _REPO_ROOT / "data/cache/gemini_transcript_policy"


def _database_url() -> Optional[str]:
    return (
        os.getenv("OPEN_NAVIGATOR_DATABASE_URL")
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("DATABASE_URL")
    )


# A "moment" is one story/humor entry that may need a quote. We carry the dict by
# reference so writing the quote back mutates the loaded analysis in place.
class _Moment:
    __slots__ = ("entry", "field", "kind", "speaker", "paraphrase")

    def __init__(self, entry: Dict[str, Any], field: str, kind: str):
        self.entry = entry
        self.field = field
        self.kind = kind
        self.speaker = entry.get("speaker_id") or entry.get("person_id") or ""
        self.paraphrase = (
            entry.get("summary")
            or entry.get("story_detail")
            or entry.get("story_headline")
            or ""
        )


def _iter_moments(analysis: Dict[str, Any]) -> List[_Moment]:
    out: List[_Moment] = []
    for dec in analysis.get("decisions") or []:
        if not isinstance(dec, dict):
            continue
        he = dec.get("human_element")
        if not isinstance(he, dict):
            continue
        for entry in he.get("personal_stories") or []:
            if isinstance(entry, dict):
                out.append(_Moment(entry, "evidence_quote", "story"))
        # Canonical key is humor_and_light_moments; accept the short `humor` too.
        for key in ("humor_and_light_moments", "humor"):
            for entry in he.get(key) or []:
                if isinstance(entry, dict):
                    out.append(_Moment(entry, "quote", "humor"))
    return out


def _build_prompt(transcript_block: str, pending: List[_Moment]) -> str:
    lines = [
        "You are given a meeting TRANSCRIPT with [MM:SS] timestamps and a numbered "
        "list of MOMENTS (paraphrased things that happened in the meeting).",
        "",
        "For each moment, find the ONE transcript line it refers to and return that "
        "line's words EXACTLY as written (VERBATIM — copy the text after the speaker "
        "label; do NOT include the [timestamp] or the speaker label; do NOT "
        "paraphrase, fix, or shorten). If no line clearly matches, return null.",
        "",
        'Return ONLY a JSON array, no prose: [{"index": <int>, "quote": "<verbatim '
        'text>" | null}]',
        "",
        "MOMENTS:",
    ]
    for i, m in enumerate(pending):
        who = f" (speaker={m.speaker})" if m.speaker else ""
        lines.append(f'{i}. [{m.kind}]{who} {m.paraphrase}')
    lines.append("")
    lines.append(f"<transcript>\n{transcript_block}\n</transcript>")
    return "\n".join(lines)


def _parse_quotes(text: str) -> Dict[int, str]:
    """Map index -> verbatim quote from the model's JSON array (fence-tolerant)."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw.strip("`")
        raw = raw[raw.find("[") :] if "[" in raw else raw
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end <= start:
        return {}
    try:
        items = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}
    out: Dict[int, str] = {}
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        idx, q = it.get("index"), it.get("quote")
        if isinstance(idx, int) and isinstance(q, str) and q.strip():
            out[idx] = q.strip()
    return out


def enrich_analysis(
    analysis: Dict[str, Any],
    segments: List[Dict[str, Any]],
    *,
    api_key: str,
    model: str,
) -> Tuple[int, int]:
    """Add verbatim quotes (via the model) + timestamps (deterministic) to existing
    human_element moments. Mutates ``analysis``. Returns (quotes_added, ts_stamped)."""
    moments = _iter_moments(analysis)
    pending = [m for m in moments if not str(m.entry.get(m.field) or "").strip() and m.paraphrase]
    quotes_added = 0
    if pending and segments:
        prompt = _build_prompt(format_diarized_transcript(segments), pending)
        result = call_gemini_text(
            api_key=api_key, model=model, user_text=prompt, max_output_tokens=8192
        )
        quotes = _parse_quotes(result.text or "")
        for i, m in enumerate(pending):
            q = quotes.get(i)
            if q:
                m.entry[m.field] = q
                quotes_added += 1
    ts = resolve_human_element_timestamps(analysis, segments)
    return quotes_added, ts


def _analysis_files(jurisdiction_id: str, state: str, cache_dir: Path) -> List[Path]:
    # .../<state>/<segment>/<jurisdiction_id>/<channel>/02_analysis/<name>.json
    roots = list(cache_dir.glob(f"{state}/*/{jurisdiction_id}"))
    files: List[Path] = []
    for r in roots:
        files.extend(sorted(r.glob("*/02_analysis/*.json")))
    return files


def _video_id_for(analysis_path: Path) -> Optional[str]:
    """Read the sibling 04_runs/<stem>.meta.json for this analysis' video_id."""
    meta = analysis_path.parent.parent / "04_runs" / f"{analysis_path.stem}.meta.json"
    if not meta.is_file():
        return None
    try:
        return (json.loads(meta.read_text(encoding="utf-8")).get("video_id") or "").strip() or None
    except (json.JSONDecodeError, OSError):
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction-id", default="tuscaloosa_0177256")
    parser.add_argument("--state", default="AL")
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE)
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    parser.add_argument("--limit", type=int, default=None, help="Max analyses to process")
    parser.add_argument(
        "--video-id", action="append", default=[], help="Only these video ids (repeatable)"
    )
    parser.add_argument("--write", action="store_true", help="Persist changes to the cache JSON")
    args = parser.parse_args(argv)

    load_dotenv(_REPO_ROOT / ".env")
    dsn = _database_url()
    if not dsn:
        logger.error("No database URL configured (OPEN_NAVIGATOR_DATABASE_URL / NEON_DATABASE_URL_DEV)")
        return 2
    keys = resolve_gemini_api_keys()
    if not keys:
        logger.error("No Gemini API keys configured")
        return 2

    files = _analysis_files(args.jurisdiction_id, args.state, args.cache_dir)
    want = set(args.video_id)
    logger.info("Found {} analysis files for {}", len(files), args.jurisdiction_id)

    processed = totals = ts_total = 0
    for path in files:
        if args.limit is not None and processed >= args.limit:
            break
        vid = _video_id_for(path)
        if want and vid not in want:
            continue
        if not vid:
            logger.warning("No video_id for {} — skipping", path.name)
            continue
        try:
            analysis = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Unreadable analysis {}: {}", path.name, exc)
            continue
        if not _iter_moments(analysis):
            continue  # nothing to enrich
        yt = fetch_db_transcript(dsn, vid)
        segments = list((yt or {}).get("segments") or [])
        if not segments:
            logger.warning("No DB transcript for {} ({}) — skipping", vid, path.name)
            continue

        added, stamped = enrich_analysis(
            analysis, segments, api_key=keys[0], model=args.model
        )
        processed += 1
        totals += added
        ts_total += stamped
        logger.info(
            "{} [{}]: +{} quotes, {} timestamps{}",
            path.name, vid, added, stamped, "" if args.write else " (dry-run)",
        )
        if args.write:
            path.write_text(
                json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    logger.success(
        "Done: {} analyses, {} quotes added, {} timestamps stamped{}",
        processed, totals, ts_total, "" if args.write else " (DRY-RUN; use --write to persist)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
