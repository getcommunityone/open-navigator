"""Automated checks for ``public_participation[]`` rows (#818).

Nobody labels public-comment stance by hand, so the rows the analysis prompts emit are checked
against things code can know for certain:

1. **Quote found** — every ``stance_evidence`` is the speaker's own words, so it must appear in the
   meeting transcript. A quote that isn't there was paraphrased or invented.
2. **Quote matches label** — when the quote states a side in plain words ("I oppose this",
   "please approve"), that side must agree with ``stance``. A wrong-side flip is the error that
   would mislead a reader.
6. **Heat matches words** — explicit threats or insults can't sit at heat 1-2, and a comment that
   only asks questions can't sit at 4-5. Reported, not gating: captions carry no tone of voice.

(The numbers follow the design page, web_docs/docs/development/meeting-sentiment-design.md.)

No network, no database and no model call: it reads one analysis JSON and its transcript text::

    python -m llm.gemini.public_comment_checks --analysis a.json --transcript t.txt
    python -m llm.gemini.public_comment_checks --analysis a.json --transcript t.txt --json

Exit 0 when the bars are met (or there is nothing to check), 1 when a bar is missed, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

QUOTE_FOUND_BAR = 0.98  # share of quotes that must be found in the transcript
MAX_FLIP_RATE = 0.05  # share of side-stating quotes allowed on the wrong side

# The five values the prompts allow. dbt's public_stance_bucket macro is the warehouse's source of
# truth; this mirror exists only so the checks can run on a JSON file before anything is loaded.
_BUCKETS = {
    "for": "for",
    "against": "against",
    "asked questions": "question",
    "mixed or neutral": "neutral",
    "not stated": "neutral",
}

_NEG = r"(?:do not|don't|dont|cannot|can't|cant|will not|won't|wont|am not|i'm not|not|never)"
# Ordered: negated forms first, so "do not support" is read before "support".
_SIDE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("against", re.compile(rf"\b{_NEG}\s+(?:\w+\s+){{0,2}}(?:support|approve|in favor|favor)\b")),
    ("for", re.compile(rf"\b{_NEG}\s+(?:\w+\s+){{0,2}}(?:oppose|opposed|against|object)\b")),
    ("against", re.compile(r"\b(?:i|we)\s+(?:strongly\s+|firmly\s+)?(?:oppose|object to)\b")),
    ("against", re.compile(r"\b(?:i am|i'm|im|we are|we're)\s+(?:strongly\s+|firmly\s+)?(?:opposed|against)\b")),
    ("against", re.compile(r"\b(?:vote no|vote against|please (?:deny|reject)|urge you to (?:deny|reject|vote no)|deny this|reject this)\b")),
    ("for", re.compile(r"\b(?:i|we)\s+(?:strongly\s+|fully\s+)?support\b")),
    ("for", re.compile(r"\b(?:i am|i'm|im|we are|we're)\s+(?:strongly\s+)?in (?:favor|support)\b")),
    ("for", re.compile(r"\b(?:vote yes|vote in favor|please (?:approve|pass|adopt)|urge you to (?:approve|pass|adopt|vote yes)|approve this|pass this)\b")),
]
_HOT = re.compile(
    r"\b(?:sue you|lawsuit|see you in court|vote you out|recall you|you(?:'re| are) (?:liars?|corrupt|crooks?|idiots?)|"
    r"shame on you|disgrace|i am furious|i'm furious|outraged)\b"
)


def _norm(text: str | None) -> str:
    """Lowercase, straighten quotes, and reduce everything but letters, digits and apostrophes to spaces."""
    t = (text or "").lower().replace("’", "'").replace("‘", "'")
    return " ".join(re.sub(r"[^a-z0-9']+", " ", t).split())


def quote_found(quote: str | None, transcript: str | None) -> bool:
    """True when the quote's words appear, in order and adjacent, in the transcript."""
    q = _norm(quote)
    return bool(q) and q in _norm(transcript)


def side_from_quote(quote: str | None) -> str | None:
    """The side a quote states in plain words: 'for', 'against', 'question', or None when it states none."""
    q = _norm(quote)
    if not q:
        return None
    for side, pattern in _SIDE_RULES:
        if pattern.search(q):
            return side
    if (quote or "").strip().endswith("?"):
        return "question"
    return None


def stance_bucket(stance: str | None) -> str | None:
    """Bucket for one of the prompt's stance values; None for a missing or unrecognised value."""
    return _BUCKETS.get((stance or "").strip().rstrip(".!").strip().lower())


def _heat(value: Any) -> int | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return int(n) if n in (1, 2, 3, 4, 5) else None


def heat_flag(row: dict[str, Any]) -> str | None:
    """Why a row's heat contradicts its words, or None."""
    heat = _heat(row.get("heat"))
    if heat is None:
        return None
    words = _norm(f"{row.get('stance_evidence') or ''} {row.get('summary') or ''}")
    if heat <= 2 and _HOT.search(words):
        return f"heat {heat} but the words include a threat or insult"
    if heat >= 4 and stance_bucket(row.get("stance")) == "question" and not _HOT.search(words):
        return f"heat {heat} on a comment that only asked questions"
    return None


@dataclass
class Report:
    rows: int = 0
    quotes: int = 0
    quotes_found: int = 0
    sided_quotes: int = 0  # quotes that state for/against in plain words, on a row with a for/against stance
    flips: int = 0
    heat_flags: int = 0
    unknown_stance: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def quote_found_rate(self) -> float | None:
        return self.quotes_found / self.quotes if self.quotes else None

    @property
    def flip_rate(self) -> float | None:
        return self.flips / self.sided_quotes if self.sided_quotes else None

    @property
    def passed(self) -> bool:
        """Bars met. A rate with nothing to measure doesn't fail: there is no evidence either way."""
        found, flip = self.quote_found_rate, self.flip_rate
        return (found is None or found >= QUOTE_FOUND_BAR) and (flip is None or flip <= MAX_FLIP_RATE)

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "quote_found_rate": self.quote_found_rate, "flip_rate": self.flip_rate,
                "passed": self.passed}


def check_analysis(analysis: dict[str, Any], transcript: str) -> Report:
    """Run the checks on one analysis's ``public_participation`` rows."""
    report = Report()
    rows = analysis.get("public_participation") or []
    if not isinstance(rows, list):
        return report
    for i, row in enumerate(r for r in rows if isinstance(r, dict)):
        report.rows += 1
        who = row.get("speaker_id") or f"row {i}"
        bucket = stance_bucket(row.get("stance"))
        if bucket is None:
            report.unknown_stance += 1
            report.findings.append({"speaker_id": who, "check": "stance", "problem": f"unrecognised stance {row.get('stance')!r}"})
        quote = row.get("stance_evidence")
        if isinstance(quote, str) and quote.strip():
            report.quotes += 1
            if quote_found(quote, transcript):
                report.quotes_found += 1
            else:
                report.findings.append({"speaker_id": who, "check": "quote_found", "problem": "quote is not in the transcript", "quote": quote})
            side = side_from_quote(quote)
            if side in ("for", "against") and bucket in ("for", "against"):
                report.sided_quotes += 1
                if side != bucket:
                    report.flips += 1
                    report.findings.append({"speaker_id": who, "check": "quote_matches_label", "problem": f"quote reads {side}, stance is {row.get('stance')}", "quote": quote})
        flag = heat_flag(row)
        if flag:
            report.heat_flags += 1
            report.findings.append({"speaker_id": who, "check": "heat", "problem": flag})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--analysis", type=Path, required=True, help="Analysis JSON (the model's answer)")
    parser.add_argument("--transcript", type=Path, required=True, help="Transcript text of the same meeting")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    args = parser.parse_args(argv)
    try:
        analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
        transcript = args.transcript.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        logger.error("Could not read the inputs: {}", exc)
        return 2
    if not isinstance(analysis, dict):
        logger.error("The analysis file is not a JSON object")
        return 2
    report = check_analysis(analysis, transcript)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        logger.info("{} public-comment rows; {} with a quote", report.rows, report.quotes)
        if report.quote_found_rate is not None:
            logger.info("Quotes found in the transcript: {}/{} ({:.0%}; bar {:.0%})", report.quotes_found,
                        report.quotes, report.quote_found_rate, QUOTE_FOUND_BAR)
        if report.flip_rate is not None:
            logger.info("Wrong-side flips: {}/{} ({:.0%}; at most {:.0%})", report.flips, report.sided_quotes,
                        report.flip_rate, MAX_FLIP_RATE)
        logger.info("Heat flags: {}; unrecognised stances: {}", report.heat_flags, report.unknown_stance)
        for f in report.findings:
            logger.warning("{speaker_id}: [{check}] {problem}", **f)
        (logger.success if report.passed else logger.error)("Bars {}", "met" if report.passed else "missed")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
