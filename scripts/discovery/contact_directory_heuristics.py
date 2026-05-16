"""
Heuristics to flag HTML pages that look like elected-official / board / council / contact directories.

Used by the jurisdiction scrape pipeline to drive structured contact extraction and manifest flags.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

_URL_HINTS: List[tuple[str, str, int]] = [
    (r"commissioner[-_/]?bio", "officials", 28),
    (r"county[-_]?commission", "commission", 20),
    (r"major[-_]?council", "council", 22),
    (r"mayor[-_]?&?[-_]?council", "council", 20),
    (r"city\s*council", "council", 22),
    (r"town\s*council", "council", 22),
    (r"county[-_]?official", "officials", 24),
    (r"/official", "officials", 18),
    (r"board[-_]?of[-_]?education", "board", 24),
    (r"meet[-_]?the[-_]?board", "board", 26),
    (r"board[-_]?member", "board", 20),
    (r"commission(er)?s?", "commission", 18),
    (r"mayor", "mayor", 16),
    (r"council", "council", 14),
    (r"contact[-_]?us", "contacts", 16),
    (r"/contacts?/", "contacts", 14),
    (r"directory", "directory", 12),
    (r"elected", "officials", 14),
    (r"leadership", "directory", 10),
    (r"staff", "directory", 8),
]

_TITLE_HINTS = (
    "board of",
    "commissioner bio",
    "mayor and council",
    "mayor & council",
    "school board",
    "city council",
    "town council",
    "county commission",
    "commissioner",
    "mayor",
    "council member",
    "elected official",
    "county official",
    "contact us",
    "meet the",
    "trustee",
    "superintendent",
)


def classify_contact_directory_page(page_url: str, html: Optional[str]) -> Dict[str, Any]:
    """
    Return a dict with ``is_directory``, ``directory_kind``, ``score``, ``matched_signals``.

    ``directory_kind`` is a coarse bucket: ``board``, ``council``, ``commission``, ``mayor``,
    ``officials``, ``contacts``, ``directory``, ``mixed``, or ``unknown``.
    """
    url = (page_url or "").strip()
    path = ""
    try:
        path = (urlparse(url).path or "").lower()
    except Exception:
        path = ""
    path_flat = re.sub(r"[_\s]+", "-", path)
    blob_l = f"{url.lower()} {path_flat}"
    signals: List[str] = []
    kinds: Set[str] = set()
    score = 0

    for pattern, kind, weight in _URL_HINTS:
        if re.search(pattern, blob_l, re.I):
            signals.append(f"url_re:{pattern}")
            kinds.add(kind)
            score += weight

    title_l = ""
    text_head_l = ""
    if html:
        tl = re.search(r"<title[^>]*>([^<]{1,300})</title>", html, re.I | re.S)
        if tl:
            title_l = re.sub(r"\s+", " ", tl.group(1)).strip().lower()
        raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
        raw = re.sub(r"(?i)<[^>]+>", " ", raw)
        text_head_l = re.sub(r"\s+", " ", raw)[:9000].lower()

        for kw in _TITLE_HINTS:
            if kw in title_l:
                signals.append(f"title:{kw}")
                score += 12
                if "board" in kw or "trustee" in kw or "school board" in kw:
                    kinds.add("board")
                elif "council" in kw:
                    kinds.add("council")
                elif "commission" in kw:
                    kinds.add("commission")
                elif "mayor" in kw:
                    kinds.add("mayor")
                elif "official" in kw:
                    kinds.add("officials")
                elif "contact" in kw:
                    kinds.add("contacts")

        body_kw = (
            "board of commissioners",
            "county commission",
            "county commissioners",
            "commission chairman",
            "commission district",
            "city council",
            "council president",
            "district representative",
            "board member",
            "superintendent",
            "mayor",
            "vice mayor",
            "county administrator",
        )
        for kw in body_kw:
            if kw in text_head_l:
                signals.append(f"body:{kw}")
                score += 6

    directory_kind = "unknown"
    if kinds:
        if len(kinds) >= 2:
            directory_kind = "mixed"
        else:
            directory_kind = next(iter(kinds))

    person_adjacent_image_score = 0
    if html:
        from scripts.discovery.contact_profile_images import score_person_adjacent_images

        person_adjacent_image_score = score_person_adjacent_images(html, page_url=url)
        if person_adjacent_image_score >= 3:
            signals.append(f"person_adjacent_images:{person_adjacent_image_score}")
            score += min(person_adjacent_image_score * 2, 26)

    is_directory = score >= 18
    return {
        "is_directory": bool(is_directory),
        "directory_kind": directory_kind,
        "score": int(min(score, 100)),
        "matched_signals": signals[:40],
        "page_title_snippet": (title_l[:200] if title_l else ""),
        "person_adjacent_image_score": int(person_adjacent_image_score),
    }
