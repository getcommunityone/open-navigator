"""
Normalize Part 2 Smart Brevity Markdown (layout rules not enforced by the model).
"""

from __future__ import annotations

import re

_ONE_BIG_THING_LINE = re.compile(
    r"^\s*\*\*The One Big Thing:\*\*\s*.+$",
    re.IGNORECASE | re.MULTILINE,
)
_DUPLICATE_WHY = re.compile(
    r"(\*\*Why it matters:\*\*[^\n]*\n)(?:\s*\n)?\* \*\*Why it matters:\*\*",
    re.IGNORECASE,
)


def strip_one_big_thing_lines(markdown: str) -> str:
    """Remove legacy ``**The One Big Thing:**`` lines; thesis belongs under **Why it matters**."""
    lines = markdown.splitlines()
    out: list[str] = []
    for line in lines:
        if _ONE_BIG_THING_LINE.match(line.strip()):
            continue
        out.append(line)
    text = "\n".join(out)
    text = _DUPLICATE_WHY.sub(r"\1", text)
    return re.sub(r"\n{3,}", "\n\n", text)
