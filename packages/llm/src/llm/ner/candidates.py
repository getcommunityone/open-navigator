"""Cluster vote-phrase hits into time windows; optional spaCy EntityRuler span text."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from llm.ner.phrases import PHRASE_STRINGS
from llm.ner.spot import VotePhraseHit

if TYPE_CHECKING:
    from spacy.language import Language

_SPAN_TEXT_MAX = 12


def build_ruler_nlp() -> Language:
    """spaCy ``en_core_web_sm`` with EntityRuler labels = ``phrase_code``."""
    import spacy

    nlp = spacy.load("en_core_web_sm")
    patterns: list[dict[str, str]] = []
    for code, strings in PHRASE_STRINGS.items():
        for text in strings:
            patterns.append({"label": code, "pattern": text})
    ruler = nlp.add_pipe("entity_ruler", config={"overwrite_ents": True}, before="ner")
    ruler.add_patterns(patterns)
    return nlp


def _single_linkage_clusters(
    timed_hits: list[VotePhraseHit], *, window_seconds: float
) -> list[list[VotePhraseHit]]:
    ordered = sorted(timed_hits, key=lambda h: h.start_seconds or 0.0)
    if not ordered:
        return []

    clusters: list[list[VotePhraseHit]] = []
    current: list[VotePhraseHit] = [ordered[0]]
    for hit in ordered[1:]:
        prev = current[-1].start_seconds or 0.0
        cur = hit.start_seconds or 0.0
        if cur - prev <= window_seconds:
            current.append(hit)
        else:
            clusters.append(current)
            current = [hit]
    clusters.append(current)
    return clusters


def _segments_in_window(
    segments: list[dict], t_start: float, t_end: float
) -> str:
    parts: list[str] = []
    for seg in segments:
        start = seg.get("start")
        if start is None:
            continue
        t = float(start)
        if t_start <= t <= t_end:
            text = (seg.get("text") or "").strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _ruler_span_texts(
    nlp: Language,
    segments: list[dict],
    t_start: float,
    t_end: float,
    *,
    max_texts: int = _SPAN_TEXT_MAX,
) -> list[str]:
    blob = _segments_in_window(segments, t_start, t_end)
    if not blob.strip():
        return []
    doc = nlp(blob)
    texts: list[str] = []
    for ent in doc.ents:
        if ent.label_ not in PHRASE_STRINGS:
            continue
        snippet = ent.text.strip()
        if not snippet:
            continue
        texts.append(snippet)
        if len(texts) >= max_texts:
            break
    return texts


def _cluster_dict(
    video_id: str,
    group: list[VotePhraseHit],
    segments: list[dict],
    *,
    nlp: Language | None,
) -> dict[str, Any]:
    starts = [h.start_seconds for h in group if h.start_seconds is not None]
    t_start = min(starts) if starts else 0.0
    t_end = max(starts) if starts else 0.0
    phrase_codes = sorted({h.phrase_code for h in group})
    out: dict[str, Any] = {
        "video_id": video_id,
        "t_start": t_start,
        "t_end": t_end,
        "phrase_codes": phrase_codes,
        "hit_count": len(group),
        "subject_cue_present": "subject_cue" in phrase_codes,
    }
    if nlp is not None:
        span_texts = _ruler_span_texts(nlp, segments, t_start, t_end)
        if span_texts:
            out["span_texts"] = span_texts
    return out


def cluster_candidates(
    video_id: str,
    segments: list[dict],
    hits: list[VotePhraseHit],
    *,
    window_seconds: float = 90.0,
    nlp: Language | None = None,
) -> list[dict]:
    """Single-linkage clusters on ``start_seconds``; optional EntityRuler ``span_texts``."""
    timed = [h for h in hits if h.start_seconds is not None]
    groups = _single_linkage_clusters(timed, window_seconds=window_seconds)
    return [_cluster_dict(video_id, g, segments, nlp=nlp) for g in groups]