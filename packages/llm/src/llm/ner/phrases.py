"""Stock motion/vote phrase patterns for caption segment scanning."""

from __future__ import annotations

import re

# Raw alternation fragments per phrase_code (design table + stock council phrasing).
_PHRASE_RAW: dict[str, list[str]] = {
    "motion_made": [
        r"i\s+move\s+to",
        r"motion\s+to\s+(?:adopt|approve)",
        r"\bso\s+moved\b",
    ],
    "seconded": [
        r"^\s*second\.?\s*$",
        r"\bi(?:'|')ll\s+second(?:\s+that)?\b",
        r"\bi\s+second(?:\s+that)?\b",
    ],
    "vote_called": [
        r"all\s+in\s+favor",
        r"roll\s+call",
        r"call\s+the\s+question",
    ],
    "vote_cast": [
        r"\baye\b",
        r"\bnay\b",
        r"\byes\b",
        r"\bno\b",
        r"\babstain\b",
    ],
    "result": [
        r"motion\s+carries",
        r"motion\s+passes",
        r"motion\s+fails",
        r"approved\s+\d+\s+to\s+\d+",
        r"\bunanimous\b",
    ],
    "subject_cue": [
        r"ordinance\s+number",
        r"\bresolution\b",
        r"agenda\s+item",
        r"public\s+hearing",
    ],
}

PHRASE_PATTERNS: dict[str, re.Pattern[str]] = {
    code: re.compile("|".join(f"(?:{frag})" for frag in frags), re.IGNORECASE)
    for code, frags in _PHRASE_RAW.items()
}