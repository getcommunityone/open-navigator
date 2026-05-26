"""
Post-discovery enrichment for ``bronze_jurisdiction_youtube`` rows.

For each discovered channel, fetch the channel's About page (or the channel home page
as fallback) to extract:

- ``channel_description`` — verbatim description text.
- ``external_links`` — outbound URLs the channel owner lists (deduped).
- ``back_links_to_jurisdiction_website`` — True iff any external link's host matches
  the jurisdiction's website host (or a parent .gov of it).
- ``official_meeting_confidence`` — 0.0–1.0 heuristic combining name match, back-link,
  and policy/meeting keywords.

The enricher is intentionally synchronous and uses ``requests`` so it can be called
inside the existing thread-pool runner without colliding with the async event loop
that ``YouTubeChannelDiscovery`` uses internally.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Sequence
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_USER_AGENT = "OpenNavigatorJurisdictionPilot/1.0"
_TIMEOUT_S = 15

# Title-match keywords. Tuned for municipal government channels — official channels
# almost always include one of these in the title.
_GOV_TITLE_KEYWORDS = (
    "city of", "town of", "county of", "village of", "borough of",
    "city council", "town council", "county commission", "board of commissioners",
    "government", "official", "civic", "municipal",
    "tv", "media",  # "CityTV", "GovTV", "MediaCenter"
)

_MEETING_TITLE_KEYWORDS = (
    "meetings", "meeting", "council", "commission", "selectmen", "select board",
    "board of supervisors", "civic", "public access",
)


def _norm_host(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return ""
    return re.sub(r"^www\.", "", host)


def _parent_gov_host(host: str) -> str:
    """``cityofbigtimber.gov`` -> ``cityofbigtimber.gov`` (no parent above gov tld).
    ``meetings.cobbcounty.org`` -> ``cobbcounty.org``."""
    if not host or "." not in host:
        return host
    parts = host.split(".")
    # Keep at most last two labels (e.g. example.org). For .gov sites, last two too.
    return ".".join(parts[-2:])


def _share_host(link_host: str, target_host: str) -> bool:
    """True when link_host == target_host OR they share the same parent registrable host."""
    if not link_host or not target_host:
        return False
    if link_host == target_host:
        return True
    return _parent_gov_host(link_host) == _parent_gov_host(target_host)


def fetch_channel_html(
    channel_url: str,
    *,
    session: requests.Session | None = None,
    cookies_file: str | None = None,
) -> tuple[str, str]:
    """Return ``(html, final_url)`` from the channel About/home page."""
    from scripts.datasources.youtube.youtube_channel_page import fetch_youtube_channel_page

    return fetch_youtube_channel_page(
        channel_url,
        session=session,
        cookies_file=cookies_file,
        timeout_s=_TIMEOUT_S,
    )


# YouTube embeds the description and external link list inside the ytInitialData JSON
# blob. We don't parse the full blob — just pluck the bits we need with regexes.
# These are best-effort; YouTube rotates these payload shapes periodically.

_DESCRIPTION_PATTERNS = (
    re.compile(r'"description"\s*:\s*\{\s*"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"'),
    re.compile(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"'),
    re.compile(r'<meta\s+(?:name|property)="(?:og:)?description"\s+content="([^"]+)"', re.IGNORECASE),
)

# YouTube wraps external links in a redirect: "https://www.youtube.com/redirect?...&q=<URL-encoded-real>".
# Inside JSON-embedded payloads YouTube escapes ``&`` as ``&`` and there's almost always
# at least one parameter (event=, redir_token=) between ``redirect?`` and ``q=``, so we accept
# either ampersand form between the redirect base and the q= param.
_REDIRECT_Q_RE = re.compile(
    r'youtube\.com/redirect[^"\'<>\s]{0,500}?(?:&|\\u0026|\?)q=([^"&\'<>\s\\]+)'
)
_DIRECT_HREF_RE = re.compile(r'href="(https?://[^"]+)"')


def extract_channel_description(html: str) -> str:
    """Return the channel description (first non-empty match across known patterns)."""
    if not html:
        return ""
    for pattern in _DESCRIPTION_PATTERNS:
        m = pattern.search(html)
        if not m:
            continue
        raw = m.group(1)
        # JSON-escaped strings: decode \n \" \u sequences. The og:description path
        # returns plain text and is also safe to pass through json.loads-with-quoting.
        try:
            decoded = json.loads(f'"{raw}"')
        except (json.JSONDecodeError, ValueError):
            decoded = raw.replace("\\n", "\n").replace('\\"', '"')
        text = decoded.strip()
        if text:
            return text
    return ""


def extract_external_links(html: str) -> list[str]:
    """
    Return outbound URLs the channel owner exposed (via the YouTube redirect wrapper
    *and* direct anchor hrefs on the About page). YouTube-internal URLs are stripped.
    """
    if not html:
        return []
    found: list[str] = []
    seen: set[str] = set()

    for raw in _REDIRECT_Q_RE.findall(html):
        try:
            from urllib.parse import unquote
            url = unquote(raw)
        except Exception:
            continue
        # YouTube's redirect URLs frequently lack the scheme (e.g. ``www.co.adams.in.us``
        # instead of ``https://www.co.adams.in.us``). Prepend a scheme so ``_is_external``
        # accepts them and so the resulting URL has a parseable host.
        if url and not url.lower().startswith(("http://", "https://")):
            url = "https://" + url.lstrip("/")
        if _is_external(url) and url not in seen:
            seen.add(url)
            found.append(url)

    for url in _DIRECT_HREF_RE.findall(html):
        if _is_external(url) and url not in seen:
            seen.add(url)
            found.append(url)

    return found[:40]


def _is_external(url: str) -> bool:
    if not url or not url.lower().startswith(("http://", "https://")):
        return False
    host = _norm_host(url)
    if not host:
        return False
    if host.endswith("youtube.com") or host == "youtu.be" or host.endswith(".googleusercontent.com"):
        return False
    if host.endswith("google.com") or host.endswith("gstatic.com"):
        return False
    return True


def back_links_to(
    external_links: Sequence[str],
    jurisdiction_homepage: str,
    *,
    description_text: str = "",
) -> bool:
    """True when ``jurisdiction_website_back_links`` would be non-empty."""
    return bool(
        jurisdiction_website_back_links(
            external_links,
            jurisdiction_homepage,
            description_text=description_text,
        )
    )


def jurisdiction_website_back_links(
    external_links: Sequence[str],
    jurisdiction_homepage: str,
    *,
    description_text: str = "",
) -> list[str]:
    """
    Outbound URLs from the YouTube About page (or description text) that match the
    jurisdiction's official website host.
    """
    target = _norm_host(jurisdiction_homepage)
    if not target:
        return []

    matched: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        u = (url or "").strip()
        if not u or u in seen:
            return
        if not u.lower().startswith(("http://", "https://")):
            u = "https://" + u.lstrip("/")
        if _share_host(_norm_host(u), target):
            seen.add(u)
            matched.append(u)

    for link in external_links:
        _add(link)

    desc_l = (description_text or "").lower()
    if desc_l:
        for raw in re.findall(r"https?://[^\s<>\"']+", description_text):
            _add(raw)
        parent = _parent_gov_host(target)
        for host in {target, parent}:
            if host and host in desc_l:
                _add(f"https://{host}/")

    return matched[:20]


def _jurisdiction_name_tokens(name: str) -> list[str]:
    """Split ``Bristol County`` -> ``[bristol, county]``; ``Cambridge`` -> ``[cambridge]``."""
    if not name:
        return []
    raw = re.sub(r"[^A-Za-z\s]", " ", name).lower()
    tokens = [t for t in raw.split() if len(t) >= 3]
    # Drop generic suffix tokens — these are too weak by themselves.
    return [t for t in tokens if t not in {"city", "town", "county", "village", "borough"}]


def is_discovered_on_jurisdiction_website(discovery_method: str) -> bool:
    """True when the channel URL was found linked from the jurisdiction website crawl."""
    method = (discovery_method or "").strip().lower()
    return method.startswith("website_search") or method.startswith("website_scrape")


def score_official_meeting_channel(
    *,
    channel_title: str,
    channel_description: str,
    jurisdiction_name: str,
    jurisdiction_state_code: str,
    external_links: Sequence[str],
    backlinks_to_jurisdiction: bool,
    video_count: int | None,
    existing_policy_score: int | float | None = None,
    discovered_on_jurisdiction_website: bool = False,
) -> float:
    """
    Return a 0.0–1.0 heuristic confidence that this channel is the jurisdiction's
    official meeting/government channel. Components are additive (clamped at 1.0).

    Title and description are scored symmetrically because YouTube channel scrapes
    frequently return junk titles like "Home" / "Shorts" / "Playlists" when the page
    metadata isn't fully populated, while the description still contains the gold
    ("Adams County, Indiana Government's YouTube channel, to broadcast public meetings.").
    Each signal hits the title-OR-description path, whichever is stronger.

    Weighting (max each, capped at 1.0):
      jurisdiction name token in title OR description       +0.30
      gov-style keyword in title OR description             +0.20
      meeting/council keyword in title OR description       +0.20
      back-links to jurisdiction website                    +0.50  ← strongest signal
      name + state both visible in description              +0.10
      video_count >= 50                                     +0.10
      existing policy_score >= 1 (existing scorer)          +0.10

    Floors (after additive score, still capped at 1.0):
      channel About links to jurisdiction .gov host         min 0.85
      two-way link (channel → .gov and .gov → channel)    min 0.95

    The back-link weight is high enough that a confirmed back-link alone clears the
    default 0.50 threshold. Random channels essentially never link to municipal .gov
    websites — when one does, it's almost always the jurisdiction's own channel even
    if the channel's title is YouTube placeholder text ("Home" / "Shorts" / "Playlists")
    and the description is the default "Share your videos with friends, family, and the
    world." (PVPC for Hampden County MA is the canonical example.)
    """
    score = 0.0
    title_l = (channel_title or "").lower()
    desc_l = (channel_description or "").lower()
    state_l = (jurisdiction_state_code or "").lower()
    name_tokens = _jurisdiction_name_tokens(jurisdiction_name)

    name_in_title = any(tok in title_l for tok in name_tokens)
    name_in_desc = any(tok in desc_l for tok in name_tokens)
    if name_in_title or name_in_desc:
        score += 0.30

    gov_in_title = any(kw in title_l for kw in _GOV_TITLE_KEYWORDS)
    gov_in_desc = any(kw in desc_l for kw in _GOV_TITLE_KEYWORDS)
    if gov_in_title or gov_in_desc:
        score += 0.20

    meeting_in_title = any(kw in title_l for kw in _MEETING_TITLE_KEYWORDS)
    meeting_in_desc = any(kw in desc_l for kw in _MEETING_TITLE_KEYWORDS)
    if meeting_in_title or meeting_in_desc:
        score += 0.20

    if backlinks_to_jurisdiction:
        score += 0.50

    # Extra +0.10 only when BOTH the jurisdiction name AND a state-locator string are
    # in the description — guards against name collisions across states ("Adams County"
    # exists in many states, but "Adams County, Indiana" in the description tells us
    # we have the right one).
    if name_in_desc and state_l:
        if f", {state_l}" in desc_l or f" {state_l} " in desc_l:
            score += 0.10

    if video_count is not None and video_count >= 50:
        score += 0.10

    if existing_policy_score is not None:
        try:
            if float(existing_policy_score) >= 1:
                score += 0.10
        except (TypeError, ValueError):
            pass

    if backlinks_to_jurisdiction:
        score = max(score, 0.85)
        if discovered_on_jurisdiction_website:
            score = max(score, 0.95)

    return round(min(score, 1.0), 3)


def enrich_channel(
    *,
    channel: dict[str, Any],
    jurisdiction_name: str,
    jurisdiction_state_code: str,
    jurisdiction_homepage: str,
    jurisdiction_type: str | None = None,
    session: requests.Session | None = None,
    cookies_file: str | None = None,
) -> dict[str, Any]:
    """
    Fetch the channel page; resolve ``UC…`` id, title, description, external links,
    back-link flag, and ``official_meeting_confidence``. Returns a new merged dict.
    """
    from scripts.datasources.youtube.channel_about_links import parse_channel_about_page
    from scripts.datasources.youtube.youtube_channel_page import (
        canonical_channel_url,
        extract_channel_id_from_youtube_html,
        extract_channel_title_from_youtube_html,
        fetch_latest_upload_date_from_rss,
        is_junk_channel_title,
        resolve_channel_id_from_url,
    )

    channel_url = (channel.get("channel_url") or channel.get("youtube_channel_url") or "").strip()
    sess = session or requests.Session()
    html, final_url = fetch_channel_html(
        channel_url, session=sess, cookies_file=cookies_file
    )
    about = parse_channel_about_page(html)
    description = (about.channel_description or "").strip() or extract_channel_description(html)
    link_rows = about.links or []
    links = [str(row.get("url") or "").strip() for row in link_rows if row.get("url")]
    if not links:
        links = extract_external_links(html)
    website_back_links = jurisdiction_website_back_links(
        links, jurisdiction_homepage, description_text=description
    )
    backlinks = bool(website_back_links)

    channel_id = (
        (channel.get("channel_id") or channel.get("youtube_channel_id") or "").strip()
    )
    if not channel_id.startswith("UC"):
        channel_id = extract_channel_id_from_youtube_html(html, final_url=final_url) or ""
    if not channel_id.startswith("UC"):
        resolved_id, _ = resolve_channel_id_from_url(
            channel_url, session=sess, cookies_file=cookies_file
        )
        if resolved_id:
            channel_id = resolved_id

    title = (channel.get("channel_title") or "").strip()
    html_title = (about.channel_title or "").strip() or extract_channel_title_from_youtube_html(html)
    if html_title and (not title or is_junk_channel_title(title)):
        title = html_title
    elif not title:
        title = html_title

    if not description:
        description = (channel.get("channel_description") or "").strip()

    subscriber_count = about.subscriber_count
    if subscriber_count is None:
        subscriber_count = channel.get("subscriber_count")
    video_count = about.video_count
    if video_count is None:
        video_count = channel.get("video_count")
    view_count = about.view_count
    if view_count is None:
        view_count = channel.get("view_count")

    latest_upload = channel.get("latest_upload")
    if channel_id.startswith("UC"):
        latest_upload = fetch_latest_upload_date_from_rss(channel_id, session=sess) or latest_upload

    normalized_url = canonical_channel_url(channel_id) if channel_id else channel_url

    discovered_on_website = is_discovered_on_jurisdiction_website(
        str(channel.get("discovery_method") or "")
    )
    confidence = score_official_meeting_channel(
        channel_title=title,
        channel_description=description,
        jurisdiction_name=jurisdiction_name,
        jurisdiction_state_code=jurisdiction_state_code,
        external_links=links,
        backlinks_to_jurisdiction=backlinks,
        video_count=video_count if video_count is not None else None,
        existing_policy_score=channel.get("policy_score"),
        discovered_on_jurisdiction_website=discovered_on_website,
    )

    enriched = dict(channel)
    enriched["channel_url"] = normalized_url or channel_url
    enriched["youtube_channel_url"] = normalized_url or channel_url
    enriched["channel_id"] = channel_id or None
    enriched["youtube_channel_id"] = channel_id or None
    enriched["channel_title"] = title or enriched.get("channel_title")
    enriched["channel_description"] = description
    enriched["external_links"] = links
    enriched["jurisdiction_website_back_links"] = website_back_links
    enriched["back_links_to_jurisdiction_website"] = backlinks
    enriched["discovered_on_jurisdiction_website"] = discovered_on_website
    enriched["mutual_official_website_link"] = bool(
        backlinks and discovered_on_website
    )
    enriched["subscriber_count"] = subscriber_count
    enriched["video_count"] = video_count
    enriched["view_count"] = view_count
    enriched["latest_upload"] = latest_upload
    enriched["official_meeting_confidence"] = confidence
    from scripts.discovery.youtube_channel_purpose import classify_channel_purpose

    jtype = str(
        jurisdiction_type or channel.get("jurisdiction_type") or ""
    ).strip()
    enriched["channel_purpose"] = classify_channel_purpose(
        channel_title=title or "",
        channel_description=description or "",
        jurisdiction_type=jtype,
    )
    return enriched
