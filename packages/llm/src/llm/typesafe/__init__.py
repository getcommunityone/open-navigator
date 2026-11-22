"""TypeSafe's Jev decision model: typed, calibrated answers about a text.

Jev doesn't write text. It answers Choice, Score and Noul (yes/no) questions about a
``state`` in one request, with probabilities. Open Navigator uses it to screen
transcripts before the paid Gemini analysis (see ``llm.typesafe.screen_transcripts``). Keepers can get a short chat blurb via ``llm.typesafe.light_blurb`` (#705).

Docs: https://docs.typesafe.ai/introduction
"""

from llm.typesafe.client import (
    JevAnswer,
    JevClient,
    JevError,
    JevResponse,
    choice,
    noul,
    score,
)

__all__ = [
    "JevAnswer",
    "JevClient",
    "JevError",
    "JevResponse",
    "choice",
    "noul",
    "score",
]
