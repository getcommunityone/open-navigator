"""
Classify state-associated YouTube channels into policy categories for the
jurisdiction mapping quality dashboard (State analysis tab).

Categories:
- ``overall`` — official state government / general state channel
- ``public_health`` — state health department / public health agency
- ``education`` — state education department / state board of education
- ``transportation`` — state DOT / transportation department
"""

from __future__ import annotations

import re
from typing import Mapping, Optional

STATE_YOUTUBE_CATEGORIES: tuple[str, ...] = (
    "overall",
    "public_health",
    "education",
    "transportation",
)

_LOCAL_GOV_TITLE_RE = re.compile(
    r"\b("
    r"county(?:\s+commission|\s+government|\s+board)?|"
    r"city of|town of|village of|borough of|"
    r"school district|\bisd\b|\busd\b|"
    r"commissioners?\s+meeting|council meeting"
    r")\b",
    re.I,
)

_CATEGORY_SIGNALS: dict[str, tuple[str, ...]] = {
    "public_health": (
        "department of health",
        "department of public health",
        "public health",
        "health department",
        "health and human services",
        "health & human services",
        "dph ",
        " dhhs",
        "medicaid",
        "behavioral health",
    ),
    "education": (
        "department of education",
        "state board of education",
        "board of education",
        "office of education",
        "state superintendent",
        "k-12",
        "k12",
    ),
    "transportation": (
        "department of transportation",
        "transportation department",
        " dot ",
        "highway department",
        "motor vehicles",
        "dmv",
        "transit authority",
        "turnpike",
        "port authority",
    ),
    "overall": (
        "state government",
        "official youtube",
        "official channel",
        "government channel",
        "state of ",
        " governor",
        "secretary of state",
    ),
}


def _blob(title: str, description: str) -> str:
    return f"{title or ''} {description or ''}".lower()


def _state_name_tokens(state_name: str, state_code: str) -> set[str]:
    name = (state_name or "").strip().lower()
    code = (state_code or "").strip().lower()
    out = {code} if code else set()
    if name:
        out.add(name)
        if name.startswith("state of "):
            out.add(name.removeprefix("state of "))
    if name == "district of columbia":
        out.update({"dc", "washington dc", "washington, dc"})
    return out


def looks_like_local_government_channel(title: str, description: str = "") -> bool:
    text = _blob(title, description)
    return bool(_LOCAL_GOV_TITLE_RE.search(text))


def score_channel_for_category(
    *,
    title: str,
    description: str,
    channel_type: str,
    state_name: str,
    state_code: str,
    category: str,
) -> float:
    """Return a non-negative match score; 0 means no match."""
    if category not in STATE_YOUTUBE_CATEGORIES:
        return 0.0

    text = _blob(title, description)
    if not text.strip():
        return 0.0

    ct = (channel_type or "").strip().lower()
    score = 0.0

    if category != "overall" and looks_like_local_government_channel(title, description):
        return 0.0

    for sig in _CATEGORY_SIGNALS[category]:
        if sig in text:
            score += 0.35

    tokens = _state_name_tokens(state_name, state_code)
    title_l = (title or "").lower()
    if any(tok and tok in title_l for tok in tokens):
        score += 0.25
    if any(tok and tok in text for tok in tokens):
        score += 0.1

    if category == "overall":
        if ct == "state":
            score += 0.6
        if re.search(r"\bstate of\b", title_l):
            score += 0.45
        if re.search(r"\b(governor|legislature|general assembly)\b", text):
            score += 0.2
    elif category == "education":
        if "school board" in text and "state" not in text:
            score -= 0.5
    elif category == "transportation":
        if "county" in text and "department of transportation" not in text:
            score -= 0.4

    if ct == "state" and category != "overall":
        score += 0.15

    return max(0.0, score)


def pick_best_channel_for_category(
    channels: list[Mapping[str, object]],
    *,
    state_name: str,
    state_code: str,
    category: str,
    min_score: float = 0.45,
) -> Optional[dict[str, object]]:
    best: tuple[float, dict[str, object]] | None = None
    for ch in channels:
        sc = score_channel_for_category(
            title=str(ch.get("channel_title") or ""),
            description=str(ch.get("channel_description") or ""),
            channel_type=str(ch.get("channel_type") or ""),
            state_name=state_name,
            state_code=state_code,
            category=category,
        )
        if sc < min_score:
            continue
        row = dict(ch)
        row["match_score"] = round(sc, 3)
        if best is None or sc > best[0]:
            best = (sc, row)
    return best[1] if best else None
