"""
Which Part 1 fields take the output (#269).

Output tokens are the larger half of every Part 1 call. This measures, across
saved analyses or raw model answers, how much of each answer every field takes:
the top-level arrays, and each field inside ``decisions[]`` and
``uncontested_items[]``::

    python -m llm.gemini.part1_field_sizes data/cache/gemini_transcript_policy/AL/**/02_analysis/*.json
    python -m llm.gemini.part1_field_sizes answers/*.txt --count-tokens   # exact tokens via the API

Sizes are the characters of each field's compact JSON, summed over the files,
and their share of the whole. With ``--count-tokens``, each field's text is also
counted by the model's own tokenizer (``models.count_tokens``, which is not
billed). Without it no token figure is shown: characters are not converted to
tokens by a guess.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROW_ARRAYS = ("decisions", "uncontested_items")


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def field_sizes(analysis: dict[str, Any]) -> dict[str, int]:
    """Characters per field path: ``people`` for a top-level key, and
    ``decisions[].headline`` for a field inside a row array. ``(total)`` is the
    whole analysis. Keys starting with ``_`` (pipeline bookkeeping) are left out."""
    sizes: dict[str, int] = {}
    body = {k: v for k, v in analysis.items() if not str(k).startswith("_")}
    sizes["(total)"] = _size(body)
    for key, value in body.items():
        sizes[key] = _size(value)
        if key in ROW_ARRAYS and isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    for field, field_value in row.items():
                        path = f"{key}[].{field}"
                        sizes[path] = sizes.get(path, 0) + _size(field_value)
    return sizes


def field_texts(analysis: dict[str, Any]) -> dict[str, str]:
    """The compact JSON text of each field path (what ``--count-tokens`` counts)."""
    texts: dict[str, list[str]] = defaultdict(list)
    body = {k: v for k, v in analysis.items() if not str(k).startswith("_")}
    for key, value in body.items():
        texts[key].append(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
        if key in ROW_ARRAYS and isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    for field, field_value in row.items():
                        texts[f"{key}[].{field}"].append(
                            json.dumps(field_value, ensure_ascii=False, separators=(",", ":"))
                        )
    return {path: "\n".join(parts) for path, parts in texts.items()}


def summarize(sizes: Iterable[dict[str, int]]) -> list[dict[str, Any]]:
    """Summed characters per path, largest first, with the share of all answers'
    total and the number of answers that have the field."""
    totals: dict[str, int] = defaultdict(int)
    present: dict[str, int] = defaultdict(int)
    count = 0
    for one in sizes:
        count += 1
        for path, chars in one.items():
            totals[path] += chars
            present[path] += 1
    whole = totals.pop("(total)", 0)
    present.pop("(total)", None)
    rows = [
        {"field": path, "chars": chars, "share_pct": round(100 * chars / whole, 1) if whole else None,
         "answers_with_field": present[path], "answer_count": count}
        for path, chars in totals.items()
    ]
    return sorted(rows, key=lambda r: (-r["chars"], r["field"]))


def load_analysis(path: Path) -> dict[str, Any] | None:
    """A saved analysis or a raw model answer, as Part 1 JSON; ``None`` if it isn't one."""
    from llm.gemini.compare_models import parse_answer

    return parse_answer(path.read_text(encoding="utf-8"))


def count_tokens(texts: dict[str, str], model: str) -> dict[str, int]:
    from llm.gemini.browser_policy_analysis import _REPO_ROOT
    from llm.gemini.genai_text_client import _client_for, ensure_valid_gemini_api_key

    client = _client_for(ensure_valid_gemini_api_key(env_path=_REPO_ROOT / ".env"))
    return {path: int(client.models.count_tokens(model=model, contents=text).total_tokens or 0)
            for path, text in texts.items() if text}


def main() -> None:
    from loguru import logger

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    parser.add_argument("paths", nargs="+", type=Path, help="Analysis JSON files or raw model answers")
    parser.add_argument("--count-tokens", action="store_true", help="Count each field's tokens via the API")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Tokenizer for --count-tokens")
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    analyses = []
    for path in args.paths:
        data = load_analysis(path)
        if data is None:
            logger.warning("Not Part 1 JSON, skipped: {}", path)
        else:
            analyses.append(data)
    if not analyses:
        raise SystemExit("No Part 1 analysis among the files given.")
    rows = summarize(field_sizes(a) for a in analyses)[: args.top]
    if args.count_tokens:
        merged: dict[str, list[str]] = defaultdict(list)
        for analysis in analyses:
            for path, text in field_texts(analysis).items():
                merged[path].append(text)
        wanted = {r["field"] for r in rows}
        tokens = count_tokens({p: "\n".join(t) for p, t in merged.items() if p in wanted}, args.model)
        for row in rows:
            row["tokens"] = tokens.get(row["field"])
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    columns = ["field", "chars", "share_pct", "answers_with_field"] + (["tokens"] if args.count_tokens else [])
    print(f"{len(analyses)} answer(s)")
    print("  ".join(c.ljust(28 if c == "field" else 10) for c in columns))
    for row in rows:
        print("  ".join(str(row.get(c, "")).ljust(28 if c == "field" else 10) for c in columns))


if __name__ == "__main__":
    main()
