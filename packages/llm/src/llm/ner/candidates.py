"""Propose person and place spans from meeting transcript text (spaCy NER).

These are *candidates* for bronze → Splink MDM → Jev confirmation. They are not
Part 1 analysis rows and must not be written straight to ``public``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from loguru import logger

# spaCy labels we keep for the roster path.
PERSON_LABELS = frozenset({"PERSON"})
PLACE_LABELS = frozenset({"GPE", "LOC", "FAC"})

# Drop obvious non-person captions noise.
_BAD_PERSON = re.compile(
    r"^(unknown|speaker|chairman|chair|mayor|council|board|motion|second)$",
    re.I,
)


@dataclass(frozen=True)
class Candidate:
    """One NER span ready to serialize or confirm with Jev."""

    text: str
    label: str  # PERSON | PLACE
    start_char: int
    end_char: int
    spacy_label: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def load_nlp(model: str = "en_core_web_sm"):
    """Load a spaCy pipeline. Raises a clear error if the model is missing."""
    try:
        import spacy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "spaCy is not installed. Install project requirements, then "
            f"python -m spacy download {model}"
        ) from exc
    try:
        return spacy.load(model)
    except OSError as exc:
        raise RuntimeError(
            f"spaCy model {model!r} is not installed. Run: python -m spacy download {model}"
        ) from exc


def extract_candidates(
    text: str,
    *,
    nlp: Any | None = None,
    model: str = "en_core_web_sm",
) -> list[Candidate]:
    """Return deduped person/place candidates in document order."""
    if not (text or "").strip():
        return []
    pipe = nlp or load_nlp(model)
    doc = pipe(text)
    out: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for ent in doc.ents:
        raw = " ".join(ent.text.split())
        if len(raw) < 2:
            continue
        if ent.label_ in PERSON_LABELS:
            if _BAD_PERSON.match(raw) or " " not in raw:
                # Prefer first+last for roster MDM; skip bare first names.
                continue
            kind = "PERSON"
        elif ent.label_ in PLACE_LABELS:
            kind = "PLACE"
        else:
            continue
        key = (kind, _normalize_key(raw))
        if key in seen or not key[1]:
            continue
        seen.add(key)
        out.append(
            Candidate(
                text=raw,
                label=kind,
                start_char=int(ent.start_char),
                end_char=int(ent.end_char),
                spacy_label=str(ent.label_),
            )
        )
    logger.info("NER candidates: {} people, {} places", 
                sum(1 for c in out if c.label == "PERSON"),
                sum(1 for c in out if c.label == "PLACE"))
    return out


def jev_confirm_people(
    document: str,
    people: Iterable[Candidate],
    *,
    client: Any,
    threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Ask Jev whether each person candidate is really mentioned in the transcript."""
    from llm.typesafe.client import noul

    people = list(people)
    if not people:
        return []
    questions = {
        f"p{i}": noul(
            f'The transcript mentions the person named "{c.text}" '
            f"(speaking, addressed, nominated, or clearly referred to)."
        )
        for i, c in enumerate(people)
    }
    resp = client.system_one(state=document, questions=questions)
    rows = []
    for i, c in enumerate(people):
        p = resp.answers[f"p{i}"].noul
        rows.append(
            {
                **c.to_dict(),
                "jev_p": p,
                "jev_present": (p or 0) >= threshold,
            }
        )
    return rows
