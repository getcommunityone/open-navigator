"""Fingerprint the meeting platforms a government website links to (#460).

Pure functions only (no network): give them a page's HTML and URL and they return
every meeting source the page points at, the same-site links worth following, and
whether the body is a bot-challenge page rather than the site.

The host patterns here are deliberately stricter than ``platform_detector``'s
``PLATFORM_PATTERNS``. That table matches loose paths such as ``/play/`` or
``/Portal/``, which is fine for picking a scraper for a known meetings page but
gives false positives when scanning every link on a city homepage. The vendor
hosts are the same (legistar.com, granicus.com, swagit.com, primegov.com,
municode, civicplus ``/AgendaCenter/``, zoom ``/rec/``); this module adds the
platforms that table lacks and the media each one carries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

VIDEO = "video"
DOCUMENTS = "documents"
BOTH = "both"

# Most URLs per platform kept for one government (a page of YouTube embeds would
# otherwise produce dozens of rows that say the same thing).
MAX_URLS_PER_PLATFORM = 5

_ABS_URL_RE = re.compile(r"https?://[^\s\"'<>\\)\]}]+", re.I)

# Link text / URL words that point at meeting pages.
_KEYWORD_WEIGHTS = {
    "agenda": 5,
    "minutes": 5,
    "meeting": 5,
    "video": 4,
    "watch": 3,
    "live": 2,
    "stream": 3,
    "council": 3,
    "commission": 3,
    "board": 2,
}
_KEYWORD_RE = re.compile("|".join(_KEYWORD_WEIGHTS), re.I)
_SKIP_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".jpg", ".jpeg",
    ".png", ".gif", ".mp3", ".mp4", ".ics", ".csv", ".txt",
)

_CHALLENGE_MARKERS = (
    ("cloudflare", ("<title>just a moment...</title>", "cf_chl_opt", "attention required! | cloudflare")),
    ("akamai", ("access denied</title>", "errors.edgesuite.net")),
    ("incapsula", ("_incapsula_resource", "incapsula incident id")),
    ("sucuri", ("sucuri website firewall", "access denied - sucuri")),
    ("aws_waf", ("request unsuccessful. incapsula", "awswaf", "aws-waf-token")),
    ("siteground", ("sgcaptcha", "/.well-known/captcha/", "robot challenge")),
    ("captcha", ("g-recaptcha", "h-captcha", "hcaptcha.com/1/api.js", "please verify you are a human")),
    ("ddos_guard", ("ddos-guard",)),
)


@dataclass(frozen=True)
class MeetingSource:
    """One meeting source found on a page."""

    platform: str
    url: str
    media: str
    found_on: str


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def _path(url: str) -> str:
    return urlsplit(url).path or "/"


def _sub_of(host: str, domain: str) -> bool:
    """``host`` is a real subdomain of ``domain`` (not ``www.`` or the bare vendor site)."""
    if not host.endswith("." + domain):
        return False
    sub = host[: -len(domain) - 1]
    return bool(sub) and sub != "www"


def _host_root(url: str) -> str:
    return f"https://{_host(url)}/"


def _no_query(url: str) -> str:
    parts = urlsplit(url)
    return f"https://{(parts.hostname or '').lower()}{parts.path or '/'}"


# --- per-platform matchers: return a canonical URL or None -----------------------

_YT_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,}$")


def _youtube(url: str) -> Optional[str]:
    host = _strip_www(_host(url))
    parts = urlsplit(url)
    segs = [s for s in parts.path.split("/") if s]
    if host == "youtu.be" and segs:
        return f"https://www.youtube.com/watch?v={segs[0]}"
    if host not in ("youtube.com", "m.youtube.com", "youtube-nocookie.com"):
        return None
    if not segs:
        return None
    head = segs[0]
    if head.startswith("@"):
        return f"https://www.youtube.com/{head}"
    if head in ("channel", "c", "user") and len(segs) > 1:
        return f"https://www.youtube.com/{head}/{segs[1]}"
    if head == "embed" and len(segs) > 1:
        if segs[1] == "videoseries":
            lst = parse_qs(parts.query).get("list", [""])[0]
            return f"https://www.youtube.com/playlist?list={lst}" if lst else None
        if segs[1] == "live_stream":
            ch = parse_qs(parts.query).get("channel", [""])[0]
            return f"https://www.youtube.com/channel/{ch}" if ch else None
        return f"https://www.youtube.com/watch?v={segs[1]}" if _YT_VIDEO_ID_RE.match(segs[1]) else None
    if head == "watch":
        vid = parse_qs(parts.query).get("v", [""])[0]
        return f"https://www.youtube.com/watch?v={vid}" if vid else None
    if head == "playlist":
        lst = parse_qs(parts.query).get("list", [""])[0]
        return f"https://www.youtube.com/playlist?list={lst}" if lst else None
    if head in ("live", "shorts") and len(segs) > 1:
        return f"https://www.youtube.com/watch?v={segs[1]}"
    return None


def _vimeo(url: str) -> Optional[str]:
    host = _strip_www(_host(url))
    segs = [s for s in _path(url).split("/") if s]
    if host == "player.vimeo.com" and len(segs) > 1 and segs[0] == "video":
        return f"https://vimeo.com/{segs[1]}"
    if host != "vimeo.com" or not segs:
        return None
    if segs[0] in ("channels", "showcase", "album", "event") and len(segs) > 1:
        return f"https://vimeo.com/{segs[0]}/{segs[1]}"
    if segs[0] in ("join", "upgrade", "features", "log_in", "login", "watch", "about", "blog", "help"):
        return None
    return f"https://vimeo.com/{segs[0]}"


def _facebook_video(url: str) -> Optional[str]:
    host = _strip_www(_host(url))
    parts = urlsplit(url)
    if host == "fb.watch":
        return _no_query(url)
    if host not in ("facebook.com", "m.facebook.com", "web.facebook.com"):
        return None
    segs = [s for s in parts.path.split("/") if s]
    if segs[:2] == ["plugins", "video.php"]:
        href = parse_qs(parts.query).get("href", [""])[0]
        return _facebook_video(unquote(href)) if href else None
    if not segs:
        return None
    if segs[0] == "watch":
        vid = parse_qs(parts.query).get("v", [""])[0]
        return f"https://www.facebook.com/watch/?v={vid}" if vid else None
    if len(segs) > 1 and segs[1] in ("videos", "live", "live_videos"):
        return f"https://www.facebook.com/{segs[0]}/{segs[1]}" + (f"/{segs[2]}" if len(segs) > 2 else "")
    return None


def _vendor_subdomain(domain: str) -> Callable[[str], Optional[str]]:
    def match(url: str) -> Optional[str]:
        host = _host(url)
        return _host_root(url) if _sub_of(host, domain) else None

    return match


def _swagit(url: str) -> Optional[str]:
    host = _host(url)
    return _host_root(url) if _sub_of(host, "swagit.com") else None


def _boxcast(url: str) -> Optional[str]:
    host = _strip_www(_host(url))
    if host not in ("boxcast.tv", "boxcast.com", "dashboard.boxcast.com", "play.boxcast.com"):
        return None
    segs = [s for s in _path(url).split("/") if s]
    if host in ("boxcast.tv", "play.boxcast.com") and len(segs) > 1 and segs[0] in ("channel", "view"):
        return f"https://boxcast.tv/{segs[0]}/{segs[1]}"
    return None


def _civicclerk(url: str) -> Optional[str]:
    host = _host(url)
    return _host_root(url) if _sub_of(host, "civicclerk.com") else None


def _legistar(url: str) -> Optional[str]:
    host = _host(url)
    if _sub_of(host, "legistar.com") and not host.startswith(("webapi.", "legistarweb-production.")):
        return _host_root(url)
    if host == "webapi.legistar.com":
        segs = [s for s in _path(url).split("/") if s]
        if len(segs) > 1 and segs[0].lower() == "v1":
            return f"https://{segs[1].lower()}.legistar.com/"
    return None


def _municode_meetings(url: str) -> Optional[str]:
    host = _host(url)
    if _sub_of(host, "municodemeetings.com") or host == "meetings.municode.com":
        return _host_root(url)
    return None


def _cablecast(url: str) -> Optional[str]:
    host = _host(url)
    if _sub_of(host, "cablecast.tv"):
        return _host_root(url)
    path = _path(url)
    idx = path.lower().find("/cablecastpublicsite")
    if idx >= 0:
        return f"https://{host}{path[: idx + len('/cablecastpublicsite')]}/"
    return None


def _boarddocs(url: str) -> Optional[str]:
    host = _host(url)
    if not (host == "boarddocs.com" or host.endswith(".boarddocs.com")):
        return None
    segs = [s for s in _path(url).split("/") if s]
    if len(segs) >= 3 and segs[2].lower() == "board.nsf":
        return f"https://{host}/{segs[0]}/{segs[1]}/Board.nsf/Public"
    return None


def _civicplus_agenda_center(url: str) -> Optional[str]:
    path = _path(url)
    idx = path.lower().find("/agendacenter")
    if idx < 0:
        return None
    return f"https://{_host(url)}/AgendaCenter"


def _zoom_recording(url: str) -> Optional[str]:
    host = _host(url)
    if (host == "zoom.us" or host.endswith(".zoom.us") or host.endswith("zoomgov.com")) and "/rec/" in _path(url):
        return _no_query(url)
    return None


# Order matters only for ties on one URL; every link is tested against every matcher.
PLATFORMS: tuple[tuple[str, str, Callable[[str], Optional[str]]], ...] = (
    ("youtube", VIDEO, _youtube),
    ("granicus", BOTH, _vendor_subdomain("granicus.com")),
    ("swagit", VIDEO, _swagit),
    ("vimeo", VIDEO, _vimeo),
    ("facebook_video", VIDEO, _facebook_video),
    ("boxcast", VIDEO, _boxcast),
    ("civicclerk", DOCUMENTS, _civicclerk),
    ("legistar", DOCUMENTS, _legistar),
    ("municode_meetings", BOTH, _municode_meetings),
    ("cablecast", VIDEO, _cablecast),
    ("iqm2", DOCUMENTS, _vendor_subdomain("iqm2.com")),
    ("escribe", DOCUMENTS, _vendor_subdomain("escribemeetings.com")),
    ("boarddocs", DOCUMENTS, _boarddocs),
    ("primegov", DOCUMENTS, _vendor_subdomain("primegov.com")),
    ("civicplus_agenda_center", DOCUMENTS, _civicplus_agenda_center),
    ("suiteone", BOTH, _vendor_subdomain("suiteonemedia.com")),
    ("zoom_recording", VIDEO, _zoom_recording),
    # Not named in #460 but common agenda hosts worth counting.
    ("novusagenda", DOCUMENTS, _vendor_subdomain("novusagenda.com")),
    ("civicweb", DOCUMENTS, _vendor_subdomain("civicweb.net")),
)
PLATFORM_MEDIA = {name: media for name, media, _ in PLATFORMS}
VIDEO_PLATFORMS = frozenset(name for name, media, _ in PLATFORMS if media in (VIDEO, BOTH))


def classify_url(url: str) -> Optional[tuple[str, str, str]]:
    """``(platform, canonical_url, media)`` for a URL on a known meeting platform, else None."""
    if not url.lower().startswith(("http://", "https://")):
        return None
    for name, media, matcher in PLATFORMS:
        try:
            canonical = matcher(url)
        except ValueError:  # malformed URL (bad port, IPv6 junk)
            canonical = None
        if canonical:
            return name, canonical, media
    return None


def _page_urls(html: str, page_url: str) -> Iterable[str]:
    """Every absolute URL a page references: links, iframes, scripts, embeds and raw text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag, attr in (
        ("a", "href"), ("iframe", "src"), ("script", "src"), ("link", "href"),
        ("embed", "src"), ("source", "src"), ("form", "action"), ("iframe", "data-src"),
    ):
        for node in soup.find_all(tag):
            value = node.get(attr)
            if isinstance(value, str) and value.strip():
                yield urljoin(page_url, value.strip())
    # URLs that only appear in inline scripts or JSON config.
    for match in _ABS_URL_RE.finditer(html):
        yield match.group(0).rstrip(".,;")


def detect_meeting_sources(html: str, page_url: str) -> list[MeetingSource]:
    """Meeting sources referenced by one page, de-duplicated by (platform, url)."""
    seen: set[tuple[str, str]] = set()
    found: list[MeetingSource] = []
    for url in _page_urls(html, page_url):
        hit = classify_url(url)
        if not hit:
            continue
        platform, canonical, media = hit
        if (platform, canonical) in seen:
            continue
        seen.add((platform, canonical))
        found.append(MeetingSource(platform, canonical, media, page_url))
    return found


def merge_sources(sources: Iterable[MeetingSource], cap: int = MAX_URLS_PER_PLATFORM) -> list[MeetingSource]:
    """Keep the first sighting of each (platform, url) and at most ``cap`` URLs per platform.

    YouTube channel URLs win over single-video URLs, since a channel is the source.
    """

    def rank(src: MeetingSource) -> int:
        if src.platform == "youtube" and ("/watch?" in src.url or "/playlist?" in src.url):
            return 1
        return 0

    ordered = sorted(enumerate(sources), key=lambda pair: (rank(pair[1]), pair[0]))
    seen: set[tuple[str, str]] = set()
    per_platform: dict[str, int] = {}
    out: list[MeetingSource] = []
    for _, src in ordered:
        key = (src.platform, src.url)
        if key in seen or per_platform.get(src.platform, 0) >= cap:
            continue
        seen.add(key)
        per_platform[src.platform] = per_platform.get(src.platform, 0) + 1
        out.append(src)
    return out


def same_site(url: str, site_url: str) -> bool:
    """``url`` is on the government's own site (same host, or a sub/parent domain of it)."""
    a, b = _strip_www(_host(url)), _strip_www(_host(site_url))
    if not a or not b:
        return False
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def meeting_page_links(html: str, page_url: str, site_url: str, limit: int = 10) -> list[str]:
    """Same-site links whose URL or text mentions meetings, best first, at most ``limit``."""
    soup = BeautifulSoup(html, "html.parser")
    scored: dict[str, int] = {}
    for node in soup.find_all("a"):
        href = node.get("href")
        if not isinstance(href, str) or not href.strip() or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(page_url, href.strip()).split("#", 1)[0]
        if not url.lower().startswith(("http://", "https://")) or not same_site(url, site_url):
            continue
        if _path(url).lower().endswith(_SKIP_EXTENSIONS) or classify_url(url):
            continue
        if url.rstrip("/") == page_url.rstrip("/"):
            continue
        text = " ".join(node.get_text(" ", strip=True).split())[:120]
        words = {m.group(0).lower() for m in _KEYWORD_RE.finditer(f"{url} {text}")}
        if not words:
            continue
        score = sum(_KEYWORD_WEIGHTS[w] for w in words)
        scored[url] = max(score, scored.get(url, 0))
    ranked = sorted(scored.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))
    return [url for url, _ in ranked[:limit]]


def challenge_reason(html: str, status_code: int) -> Optional[str]:
    """Short token when the response is a bot-protection page rather than the site, else None."""
    if status_code in (403, 429):
        return f"http_{status_code}"
    if not html:
        return None
    # Challenge pages are small; a full site page can carry a captcha widget on a
    # form or a vendor's bot-management script without being a wall.
    if len(html) > 50000:
        return None
    low = html.lower()
    for name, needles in _CHALLENGE_MARKERS:
        if any(n in low for n in needles):
            if name == "captcha" and link_count(html) > 15:
                continue
            return name
    return None


def link_count(html: str) -> int:
    """Number of ``<a href>`` links in a page (low counts suggest JavaScript-rendered links)."""
    return len(BeautifulSoup(html, "html.parser").find_all("a", href=True))
