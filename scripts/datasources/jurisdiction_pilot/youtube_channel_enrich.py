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


def fetch_channel_html(channel_url: str, *, session: requests.Session | None = None) -> str:
    """Return the channel page HTML (About tab when possible). Empty string on failure."""
    if not channel_url:
        return ""
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", _USER_AGENT)
    sess.headers.setdefault("Accept-Language", "en-US,en;q=0.9")
    candidates = []
    base = channel_url.rstrip("/")
    candidates.append(f"{base}/about")
    candidates.append(base)
    for url in candidates:
        try:
            resp = sess.get(url, timeout=_TIMEOUT_S, allow_redirects=True)
            if resp.status_code == 200 and resp.text:
                return resp.text
        except requests.RequestException as exc:
            logger.debug("channel fetch error %s: %s", url, exc)
    return ""


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
    """
    True when:
      - any external link host matches the jurisdiction website host, OR
      - the description text mentions the jurisdiction's host (or its parent registrable host).

    The text fallback catches the common case where YouTube renders the About-page link
    list via JS and it isn't present in static HTML.
    """
    target = _norm_host(jurisdiction_homepage)
    if not target:
        return False
    for link in external_links:
        if _share_host(_norm_host(link), target):
            return True
    if description_text:
        desc_l = description_text.lower()
        if target in desc_l:
            return True
        parent = _parent_gov_host(target)
        if parent and parent != target and parent in desc_l:
            return True
    return False


def _jurisdiction_name_tokens(name: str) -> list[str]:
    """Split ``Bristol County`` -> ``[bristol, county]``; ``Cambridge`` -> ``[cambridge]``."""
    if not name:
        return []
    raw = re.sub(r"[^A-Za-z\s]", " ", name).lower()
    tokens = [t for t in raw.split() if len(t) >= 3]
    # Drop generic suffix tokens — these are too weak by themselves.
    return [t for t in tokens if t not in {"city", "town", "county", "village", "borough"}]


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

    return round(min(score, 1.0), 3)


def enrich_channel(
    *,
    channel: dict[str, Any],
    jurisdiction_name: str,
    jurisdiction_state_code: str,
    jurisdiction_homepage: str,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """
    Fetch the channel's About page; compute description, external_links, back-link
    indicator, and official_meeting_confidence. Returns a NEW dict merging the
    enrichment into ``channel`` (does not mutate input).
    """
    channel_url = channel.get("channel_url") or ""
    html = fetch_channel_html(channel_url, session=session)
    description = extract_channel_description(html)
    links = extract_external_links(html)
    backlinks = back_links_to(links, jurisdiction_homepage, description_text=description)

    confidence = score_official_meeting_channel(
        channel_title=channel.get("channel_title") or "",
        channel_description=description,
        jurisdiction_name=jurisdiction_name,
        jurisdiction_state_code=jurisdiction_state_code,
        external_links=links,
        backlinks_to_jurisdiction=backlinks,
        video_count=channel.get("video_count"),
        existing_policy_score=channel.get("policy_score"),
    )

    enriched = dict(channel)
    enriched["channel_description"] = description
    enriched["external_links"] = links
    enriched["back_links_to_jurisdiction_website"] = backlinks
    enriched["official_meeting_confidence"] = confidence
    return enriched
