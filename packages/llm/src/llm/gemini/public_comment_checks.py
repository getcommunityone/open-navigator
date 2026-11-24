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
    python -m llm.gemini.public_comment_checks --analysis a.json b.json --transcript a.txt b.txt --json

Several analysis/transcript pairs are added into one report, which is how a pilot is judged: the
flip-rate bar is only applied once there are 20 side-stating quotes, because below that it is noise.
A quote that reads both ways, hedges, sets a condition or asks a question counts neither way.

Exit 0 when the bars are met (or there is nothing to check), 1 when a bar is missed, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
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

_ADV = r"(?:really|fully|strongly|firmly|totally|completely|absolutely|wholeheartedly)"
_NEG = r"(?:do not|dont|did not|didnt|cannot|can not|cant|will not|wont|would not|wouldnt|am not|are not|arent|not|never)"
_ASK = r"(?:please|urge you to|ask you to|asking you to|you should|you must|you need to)"
# Each rule: (pattern, {core phrase: side}). A negator directly before the core (only an adverb may sit
# between) flips the side. Text is normalised first, so apostrophes are already gone ("don't" -> "dont").
_RULES: list[tuple[re.Pattern[str], dict[str, str]]] = [
    (re.compile(rf"\b(?:i|we) (?P<neg>{_NEG} )?(?:{_ADV} )?(?P<core>support|oppose|object to)\b"),
     {"support": "for", "oppose": "against", "object to": "against"}),
    (re.compile(rf"\b(?:i am|im|we are) (?P<neg>not )?(?:{_ADV} )?(?P<core>in favor|in support|opposed|against)\b"),
     {"in favor": "for", "in support": "for", "opposed": "against", "against": "against"}),
    (re.compile(rf"\b(?P<neg>{_NEG} )?(?P<core>vote no|vote against|vote yes|vote in favor)\b"),
     {"vote no": "against", "vote against": "against", "vote yes": "for", "vote in favor": "for"}),
    (re.compile(rf"\b{_ASK} (?P<neg>{_NEG} )?(?P<core>deny|reject|approve|pass|adopt) (?:this|it|the|that)\b"),
     {"deny": "against", "reject": "against", "approve": "for", "pass": "for", "adopt": "for"}),
    (re.compile(r"\b(?P<neg>do not |dont )(?P<core>deny|reject|approve|pass|adopt) (?:this|it|the|that)\b"),
     {"deny": "against", "reject": "against", "approve": "for", "pass": "for", "adopt": "for"}),
]
# Words that make a plain reading unsafe: hedges, conditions, alternatives, contrasts. With any of
# these the quote counts neither way — a missed check is harmless, a wrong one is not.
_UNSAFE = re.compile(
    r"\b(?:not sure|unsure|dont know|do not know|if|whether|or|nor|but|unless|only|just|enough|should i|would i)\b"
)
_HOT = re.compile(
    r"\b(?:sue (?:you|the city|the county|the town|the board)|file a lawsuit|see you in court|vote you out|recall you|"
    r"you(?:re| are) (?:all )?(?:liars?|corrupt|crooks?|idiots?)|shame on you|i am furious|im furious)\b"
)
MIN_QUOTE_WORDS = 3  # shorter quotes match almost any transcript, so they prove nothing
MIN_SIDED_QUOTES = 20  # below this the flip rate is noise and the bar is not applied
_ELISION = re.compile(r"\.{3,}|…|\[[^\]]*\]")


def _norm(text: str | None) -> str:
    """Casefold, strip accents and apostrophes, join digit groups, and reduce other punctuation to spaces."""
    t = unicodedata.normalize("NFKD", (text or "").casefold())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"['’‘`]", "", t)
    t = re.sub(r"(?<=\d),(?=\d)", "", t)
    return " ".join(re.sub(r"[^\w]+", " ", t, flags=re.UNICODE).replace("_", " ").split())


def quote_checkable(quote: str | None) -> bool:
    """True when the quote is long enough for 'found in the transcript' to mean something."""
    return isinstance(quote, str) and len(_norm(_ELISION.sub(" ", quote)).split()) >= MIN_QUOTE_WORDS


def quote_found(quote: str | None, transcript: str | None) -> bool:
    """True when the quote's words appear in the transcript as whole words, in order.

    A quote the model shortened with ``...`` or ``[inaudible]`` is split there, and each part must
    appear, in order."""
    if not isinstance(quote, str):
        return False
    parts = [seg for seg in (_norm(p) for p in _ELISION.split(quote)) if seg]
    if not parts:
        return False
    haystack = f" {_norm(transcript)} "
    at = 0
    for part in parts:
        hit = haystack.find(f" {part} ", at)
        if hit < 0:
            return False
        at = hit + len(part) + 1
    return True


def side_from_quote(quote: str | None) -> str | None:
    """The side a quote states in plain words: 'for', 'against', 'question', or None.

    None means "no safe reading": no side phrase, a hedge or condition, or phrases on both sides."""
    if not isinstance(quote, str) or not quote.strip():
        return None
    if "?" in quote:
        return "question" if quote.strip().endswith("?") else None
    q = _norm(quote)
    if _UNSAFE.search(q):
        return None
    sides: set[str] = set()
    for pattern, cores in _RULES:
        for m in pattern.finditer(q):
            side = cores[m.group("core")]
            if m.group("neg"):
                side = "against" if side == "for" else "for"
            sides.add(side)
    return sides.pop() if len(sides) == 1 else None


def stance_bucket(stance: Any) -> str | None:
    """Bucket for one of the prompt's stance values; None for a missing, non-text or unrecognised value."""
    if not isinstance(stance, str):
        return None
    return _BUCKETS.get(stance.strip().rstrip(".!").strip().lower())


def _heat(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return int(n) if n in (1, 2, 3, 4, 5) else None


def heat_flag(row: dict[str, Any]) -> str | None:
    """Why a row's heat contradicts the speaker's quoted words, or None.

    Only ``stance_evidence`` is read: the summary is the model's wording, not the speaker's."""
    heat = _heat(row.get("heat"))
    if heat is None:
        return None
    quote = row.get("stance_evidence")
    hot = bool(_HOT.search(_norm(quote if isinstance(quote, str) else "")))
    if heat <= 2 and hot:
        return f"heat {heat} but the quote includes a threat or insult"
    if heat >= 4 and stance_bucket(row.get("stance")) == "question" and not hot:
        return f"heat {heat} on a comment that only asked questions"
    return None


@dataclass
class Report:
    analyses: int = 0
    rows: int = 0
    quotes: int = 0  # quotes long enough to verify
    quotes_found: int = 0
    short_quotes: int = 0  # too short to verify; counted neither way
    sided_quotes: int = 0  # quotes that state for/against in plain words, on a row whose stance is for/against
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
    def flip_bar_applied(self) -> bool:
        return self.sided_quotes >= MIN_SIDED_QUOTES

    @property
    def passed(self) -> bool:
        """Bars met. A quote that isn't in the transcript counts at any sample size; the flip rate is
        only judged once there are enough side-stating quotes for it to mean something."""
        found, flip = self.quote_found_rate, self.flip_rate
        quotes_ok = found is None or found >= QUOTE_FOUND_BAR
        flips_ok = not self.flip_bar_applied or (flip is not None and flip <= MAX_FLIP_RATE)
        return quotes_ok and flips_ok

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "quote_found_rate": self.quote_found_rate, "flip_rate": self.flip_rate,
                "flip_bar_applied": self.flip_bar_applied, "passed": self.passed}


def check_analysis(analysis: dict[str, Any], transcript: str, report: Report | None = None) -> Report:
    """Run the checks on one analysis's ``public_participation`` rows, adding to ``report`` when given.

    Check 2 only compares a quote with the label when both state for or against: a plain "I oppose"
    on a row marked neutral or as a question is not counted either way."""
    report = report if report is not None else Report()
    report.analyses += 1
    rows = analysis.get("public_participation") or []
    if not isinstance(rows, list):
        return report
    for i, row in enumerate(r for r in rows if isinstance(r, dict)):
        report.rows += 1
        who = str(row.get("speaker_id") or f"row {i}")
        bucket = stance_bucket(row.get("stance"))
        if bucket is None:
            report.unknown_stance += 1
            report.findings.append({"speaker_id": who, "check": "stance", "problem": f"unrecognised stance {row.get('stance')!r}"})
        quote = row.get("stance_evidence")
        if isinstance(quote, str) and quote.strip():
            if not quote_checkable(quote):
                report.short_quotes += 1
            else:
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
    parser = argparse.ArgumentParser(description="Automated checks for public_participation[] rows (#818).")
    parser.add_argument("--analysis", type=Path, required=True, nargs="+", help="Analysis JSON file(s)")
    parser.add_argument("--transcript", type=Path, required=True, nargs="+",
                        help="Transcript text file(s), one per analysis, in the same order")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    args = parser.parse_args(argv)
    if len(args.analysis) != len(args.transcript):
        logger.error("Give one transcript per analysis ({} analyses, {} transcripts)", len(args.analysis), len(args.transcript))
        return 2
    report = Report()
    for analysis_path, transcript_path in zip(args.analysis, args.transcript):
        try:
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            transcript = transcript_path.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            logger.error("Could not read the inputs: {}", exc)
            return 2
        if not isinstance(analysis, dict):
            logger.error("{} is not a JSON object", analysis_path)
            return 2
        check_analysis(analysis, transcript, report)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        logger.info("{} analyses, {} public-comment rows; {} quotes checked, {} too short to check",
                    report.analyses, report.rows, report.quotes, report.short_quotes)
        if report.quote_found_rate is not None:
            logger.info("Quotes found in the transcript: {}/{} ({:.0%}; bar {:.0%})", report.quotes_found,
                        report.quotes, report.quote_found_rate, QUOTE_FOUND_BAR)
        if report.flip_rate is not None:
            logger.info("Wrong-side flips: {}/{} ({:.0%}; at most {:.0%}{})", report.flips, report.sided_quotes,
                        report.flip_rate, MAX_FLIP_RATE,
                        "" if report.flip_bar_applied else f"; bar not applied below {MIN_SIDED_QUOTES} quotes")
        logger.info("Heat flags: {}; unrecognised stances: {}", report.heat_flags, report.unknown_stance)
        for f in report.findings:
            logger.warning("{}: [{}] {}", f["speaker_id"], f["check"], f["problem"])
        (logger.success if report.passed else logger.error)("Bars {}", "met" if report.passed else "missed")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
