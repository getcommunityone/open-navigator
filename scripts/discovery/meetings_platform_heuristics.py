"""
Heuristics inspired by civic meeting scrapers (e.g. City-Bureau city-scrapers_): detect common
vendor stacks and extract document / navigation URLs — **without** Scrapy.

.. _city-scrapers: https://github.com/City-Bureau/city-scrapers
"""
from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

# Hosts where PDFs / meeting UI often live off the jurisdiction’s marketing domain.
_OFFSITE_SUFFIXES: Tuple[str, ...] = (
    "legistar.com",
    "legistar1.granicus.com",
    "legistarcloud.com",
    "granicus.com",
    "granicusideas.com",
    "civicclerk.com",
    "civicweb.net",
    "revize.com",
    "civicplus.com",
    "streamlinevillage.com",
    "boarddocs.com",
    "municodemeetings.com",
)

# Offsite HTML we may follow (narrow path hints to avoid crawling the whole vendor CDN).
_VENDOR_PATH_SNIPPETS: Tuple[str, ...] = (
    "viewmeeting",
    "viewpublisher",
    "mediaplayer",
    "calendar.aspx",
    "meetingdetail",
    "view.ashx",
    "legistar",
    "granicus",
    "events.aspx",
    "event.aspx",
    "commission",
    "cityclerk",
)

_STACK_PATTERNS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("youtube", re.compile(r"youtube\.com|youtu\.be|youtube-nocookie\.com", re.I)),
    ("legistar", re.compile(r"legistar\.(com|net)|/legistar/|view\.ashx", re.I)),
    ("granicus", re.compile(r"granicus\.com|granicusideas\.com|viewmeeting\.aspx|viewpublisher", re.I)),
    ("civicclerk", re.compile(r"civicclerk\.com", re.I)),
    ("civicweb", re.compile(r"civicweb\.net", re.I)),
    ("revize", re.compile(r"revize\.com", re.I)),
    ("wordpress", re.compile(r"/wp-content/|/wp-json/|wordpress|xmlrpc\.php", re.I)),
    ("boarddocs", re.compile(r"boarddocs\.com", re.I)),
)

_DOC_TYPE_RULES: Tuple[Tuple[str, re.Pattern], ...] = (
    ("minutes", re.compile(r"minute|approved\s*minute", re.I)),
    ("agenda", re.compile(r"agenda|packet", re.I)),
    ("transcript", re.compile(r"transcript|caption|verbatim", re.I)),
    ("video", re.compile(r"video|webcast|recording|youtube|vimeo", re.I)),
)


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _host_matches_suffix(host: str, suffix: str) -> bool:
    h = host.rstrip(".").lower()
    s = suffix.lower().lstrip(".")
    return h == s or h.endswith("." + s)


def is_trusted_offsite(url: str) -> bool:
    h = _host(url)
    if not h:
        return False
    return any(_host_matches_suffix(h, s) for s in _OFFSITE_SUFFIXES)


def _host_without_www(netloc: str) -> str:
    """Compare apex and ``www`` as the same site (Revize / county sites often mix both)."""
    h = (netloc or "").lower().split(":")[0].rstrip(".")
    return h[4:] if h.startswith("www.") else h


def is_same_site(url: str, homepage: str) -> bool:
    try:
        a = urlparse(url).netloc
        b = urlparse(homepage).netloc
        if not a or not b:
            return False
        return _host_without_www(a) == _host_without_www(b)
    except Exception:
        return False


def _path_query_lower(url: str) -> str:
    try:
        p = urlparse(url)
        return f"{p.path.lower()}?{p.query.lower()}"
    except Exception:
        return (url or "").lower()


def is_vendor_meeting_page_url(url: str) -> bool:
    if not is_trusted_offsite(url):
        return False
    pq = _path_query_lower(url)
    return any(snippet in pq for snippet in _VENDOR_PATH_SNIPPETS)


# Counties sometimes link a short branded host (e.g. ``tallaco.com/commission-meetings/``) that is
# not the GSA/NACO ``website_url`` host. Only follow when the href is present in HTML and path
# looks like a commission/board meeting archive — no blind host generation.
_LINKED_MEETING_ARCHIVE_PATH_MARKERS: Tuple[str, ...] = (
    "commission-meeting",
    "commission_meeting",
    "board-meeting",
    "board_meeting",
    "/meetings/",
    "/minutes/",
    "/agendas/",
    "commission-minute",
    "meeting-archive",
    "meeting_archive",
    "county-commission",
    "county_commission",
)

_THIRD_PARTY_MEETING_NAV_EXCLUDED_HOST_SUFFIXES: Tuple[str, ...] = (
    "facebook.com",
    "fb.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "google.com",
    "tiktok.com",
    "pinterest.com",
    "yelp.com",
    "wikipedia.org",
    "amazon.com",
)


def is_linked_local_meeting_microsite(url: str, homepage: str) -> bool:
    """
    True for http(s) URLs on a host **different** from ``homepage`` whose path/query suggests a
    local meeting archive (linked from the county site). Excludes known social / search hosts and
    vendor stacks handled by :func:`is_vendor_meeting_page_url`.
    """
    if not url or not homepage:
        return False
    if is_same_site(url, homepage):
        return False
    if is_trusted_offsite(url):
        return False
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = p.netloc.lower().split(":")[0].rstrip(".")
        if not host or "." not in host:
            return False
        if any(
            host == s or host.endswith("." + s) for s in _THIRD_PARTY_MEETING_NAV_EXCLUDED_HOST_SUFFIXES
        ):
            return False
        pq = _path_query_lower(url)
        return any(m in pq for m in _LINKED_MEETING_ARCHIVE_PATH_MARKERS)
    except Exception:
        return False


PDF_EXT = re.compile(r"\.pdf(\?|#|$)", re.I)

# Revize / classic ASP / similar CMS “site search” portals (e.g. Autauga
# ``Default.asp?ID=122&pg=Site+Search&action=search``).
_SITE_SEARCH_URL_RE = re.compile(
    r"(?:^|[?&])pg=site\+search"
    r"|(?:^|[?&])pg=site%20search"
    r"|action=search"
    r"|site\+search"
    r"|site%20search"
    r"|/site[_\-]?search"
    r"|sitesearch\.asp"
    r"|pagesearch",
    re.I,
)


def strip_url_fragment(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def dedupe_repeated_url_path(url: str) -> str:
    """
    Collapse duplicated consecutive path blocks, e.g.
    ``/departments/board/departments/board/index.php`` -> ``/departments/board/index.php``.

    Some CMS pages use site-root-style relative hrefs (``departments/...``) **without** a leading
    ``/``; :func:`urllib.parse.urljoin` then resolves them under the current directory and repeats the
    path prefix (Burke County GA ``board_of_commissioners`` nav, etc.).
    """
    if not url or not url.strip():
        return url
    try:
        p = urlparse(url)
        path = p.path or "/"
        parts = [s for s in path.split("/") if s != ""]
        min_block = 2
        if len(parts) < min_block * 2:
            return url
        changed = True
        while changed and len(parts) >= min_block * 2:
            changed = False
            max_block = len(parts) // 2
            for block in range(max_block, min_block - 1, -1):
                if parts[:block] == parts[block : 2 * block]:
                    parts = parts[block:]
                    changed = True
                    break
        new_path = "/" + "/".join(parts) if parts else "/"
        if new_path == path:
            return url
        return urlunparse((p.scheme, p.netloc, new_path, p.params, p.query, ""))
    except Exception:
        return url


def resolve_page_href(page_url: str, href: str) -> str:
    """Absolute URL from ``page_url`` + ``href``, strip fragment, fix duplicated path segments."""
    full = strip_url_fragment(urljoin((page_url or "").strip(), (href or "").strip()))
    return dedupe_repeated_url_path(full)


def site_search_portal_variants(portal_url: str) -> List[str]:
    """
    For same-site search portal URLs, return the base URL plus a few GET variants with meeting
    keywords (CMS-specific; harmless 404s are dropped later).
    """
    base = strip_url_fragment((portal_url or "").strip())
    if not base:
        return []
    low = base.lower()
    if "content-search" in low and ("keyword" in low or "dlv_" in low):
        return opencivic_content_search_query_variants(base)
    if not _SITE_SEARCH_URL_RE.search(base):
        return [base]
    sep = "&" if "?" in base else "?"
    out: List[str] = [base]
    for param in (
        "keywords=meetings",
        "keyword=meetings",
        "search=meetings",
        "q=meetings",
        "Search=meetings",
        "txtSearch=meetings",
        "criteria=meetings",
        "SearchString=meetings",
        "keywords=youtube",
        "keywords=video",
        "keywords=webcast",
        "search=live+stream",
    ):
        cand = f"{base}{sep}{param}"
        if cand not in out:
            out.append(cand)
    return out


def html_suggests_wordpress_site(html: str) -> bool:
    """
    Heuristic: HTML likely comes from WordPress, so root ``/?s=`` site search is plausible.

    Avoids hammering non-WP sites (e.g. Revize, Granicus OpenCivic) with WordPress-only URLs.
    """
    if not html:
        return False
    sample = html[:600_000]
    low = sample.lower()
    if "/wp-json/" in low or "/wp-content/" in low or "/wp-includes/" in low:
        return True
    if "wp-embed.min.js" in low or 'content="wordpress' in low:
        return True
    if re.search(r'<link[^>]+rel=["\']https://api\.w\.org/', sample, re.I):
        return True
    if re.search(
        r'<form[^>]{0,600}action=["\'][^"\']*["\'][^>]{0,1200}name=["\']s["\']',
        sample,
        re.I | re.DOTALL,
    ):
        return True
    if re.search(
        r'name=["\']s["\'][^>]{0,400}action=["\'][^"\']*[\?&]s=',
        sample,
        re.I | re.DOTALL,
    ):
        return True
    return False


def extract_opencivic_content_search_portals(html: str, page_url: str, homepage: str) -> List[str]:
    """
    Granicus / OpenCivic-style site search, e.g.
    ``/Content-search?dlv_…Public%20Site%20Search=(keyword=)`` (filled per-query later).

    Example host: ``dallascounty-al.org`` (Granicus OpenCivic ``Content-search``).
    """
    soup = BeautifulSoup(html or "", "html.parser")
    found: List[str] = []
    seen: Set[str] = set()

    def consider(raw: str) -> None:
        u0 = (raw or "").strip()
        if not u0 or u0.startswith("#") or u0.lower().startswith("javascript:"):
            return
        if "content-search" not in u0.lower():
            return
        if "keyword" not in u0.lower() and "dlv_" not in u0.lower():
            return
        full = resolve_page_href(page_url, u0)
        if not is_same_site(full, homepage):
            return
        if full not in seen:
            seen.add(full)
            found.append(full)

    for a in soup.find_all("a", href=True):
        consider(a.get("href") or "")

    for form in soup.find_all("form", action=True):
        if (form.get("method") or "get").upper() != "GET":
            continue
        consider(form.get("action") or "")

    return found


def opencivic_content_search_query_variants(
    template_url: str,
    keywords: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Turn one ``Content-search`` template into concrete GET URLs by filling ``(keyword=…)``.

    If there is no ``(keyword=)`` placeholder, returns the template unchanged (single URL).
    """
    base = strip_url_fragment((template_url or "").strip())
    if not base:
        return []
    terms: Tuple[str, ...] = tuple(keywords) if keywords else (
        "meetings",
        "minutes",
        "agenda",
        "board",
        "council",
        "commission",
        "youtube",
        "video",
        "webcast",
        "live",
        "meeting minutes",
    )
    if "(keyword=" not in base and "(keyword%3d=" not in base.lower():
        return [base]
    out: List[str] = []
    for kw in terms:
        filled = re.sub(
            r"\(keyword=\)",
            f"(keyword={quote_plus(kw)})",
            base,
            count=1,
            flags=re.I,
        )
        if filled != base:
            out.append(filled)
    return list(dict.fromkeys(out))


def extract_site_search_portal_urls(html: str, page_url: str, homepage: str) -> List[str]:
    """
    Discover same-site links to vendor “site search” pages (ASP ``Default.asp``, etc.).

    These are not covered by WordPress ``/?s=`` heuristics; we scrape the homepage/nav HTML for
    ``pg=Site+Search``, ``action=search``, and similar patterns.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    found: List[str] = []
    seen: Set[str] = set()

    def add(raw: str) -> None:
        u = resolve_page_href(page_url, raw.strip())
        if not u or u in seen:
            return
        if not is_same_site(u, homepage):
            return
        if not _SITE_SEARCH_URL_RE.search(u):
            return
        seen.add(u)
        found.append(u)

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        full = resolve_page_href(page_url, href)
        if _SITE_SEARCH_URL_RE.search(full) or _SITE_SEARCH_URL_RE.search(href):
            add(full)
            continue
        text = (a.get_text() or "").strip().lower()
        if "site search" in text and "search" in full.lower():
            add(full)

    for form in soup.find_all("form", action=True):
        action = (form.get("action") or "").strip()
        if not action:
            continue
        if (form.get("method") or "get").upper() != "GET":
            continue
        full = resolve_page_href(page_url, action)
        if is_same_site(full, homepage) and _SITE_SEARCH_URL_RE.search(full):
            add(full)

    for u in extract_opencivic_content_search_portals(html, page_url, homepage):
        if u not in seen:
            seen.add(u)
            found.append(u)

    return found


def _is_youtube_related_host(host: str) -> bool:
    h = (host or "").lower().split(":")[0].lstrip(".")
    if h in ("youtu.be", "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        return True
    if h.endswith(".youtube.com") or h.endswith(".youtu.be"):
        return True
    if "youtube-nocookie.com" in h:
        return True
    return False


def normalize_youtube_url(raw: str, page_url: str) -> Optional[str]:
    """Return canonical ``https`` YouTube URL without fragment, or ``None`` if not YouTube."""
    u = (raw or "").strip()
    if not u or u.lower().startswith(("javascript:", "mailto:", "tel:")):
        return None
    if u.startswith("//"):
        u = "https:" + u
    u = dedupe_repeated_url_path(strip_url_fragment(urljoin(page_url, u)))
    try:
        p = urlparse(u)
    except Exception:
        return None
    host = (p.netloc or "").lower().split(":")[0]
    if not _is_youtube_related_host(host):
        return None
    scheme = "https"
    if host == "youtu.be":
        vid = (p.path or "").strip("/").split("/")[0]
        if not vid:
            return None
        vid = vid.split("?")[0]
        return strip_url_fragment(f"{scheme}://www.youtube.com/watch?v={vid}")
    netloc = host
    if "youtube-nocookie.com" in netloc:
        netloc = "www.youtube-nocookie.com"
    elif netloc in ("youtube.com", "m.youtube.com"):
        netloc = "www.youtube.com"
    return strip_url_fragment(urlunparse((scheme, netloc, p.path, p.params, p.query, "")))


def classify_youtube_link(url: str) -> str:
    """Rough bucket: ``video``, ``channel``, ``playlist``, or ``other``."""
    low = (url or "").lower()
    if "/playlist" in low and "list=" in low:
        return "playlist"
    if "/playlist/" in low:
        return "playlist"
    if "/channel/" in low:
        return "channel"
    if "/@" in low:
        return "channel"
    if "/user/" in low:
        return "channel"
    if "/c/" in low and "/channel/" not in low:
        return "channel"
    if "/watch" in low or "/embed/" in low or "/shorts/" in low or "/live" in low:
        return "video"
    if "youtu.be/" in low:
        return "video"
    return "other"


_YOUTUBE_MEETING_STRONG = re.compile(
    r"\b(?:city|town|village|borough)\s+council\b|"
    r"\bcounty\s+commission\b|\bboard\s+of\s+(?:commissioners|supervisors|trustees)\b|"
    r"\b(?:school|planning|zoning|park|library)\s+board\b|"
    r"\b(?:public|town)\s+hearing\b|"
    r"\b(?:committee|commission)\s+of\s+the\s+whole\b|"
    r"\b(?:regular|special|study|work)\s+session\b|\bworkshop\b|"
    r"\b(?:full|complete)\s+meeting\b|\bmeeting\s+(?:video|recording|replay)\b|"
    r"\b(?:live|recorded)\s+(?:stream|meeting)\b|"
    r"\bagenda\b|\bminutes\b|\bwebcast\b|\bgovernment\s+meeting\b|"
    r"\bmunicipal\b|\b(?:city|county)\s+hall\b",
    re.I,
)

_YOUTUBE_MEETING_WEAK = re.compile(
    r"\b(?:meeting|hearing|session|council|commission|board|supervisor|trustee|"
    r"alderm(?:an|en)|mayor|clerk|agenda|minutes|townhall)\b",
    re.I,
)

_YOUTUBE_NON_MEETING = re.compile(
    r"\b(?:music\s+video|official\s+video|lyrics|gameplay|minecraft|fortnite|"
    r"tutorial|asmr|unboxing|reaction\s+video|highlights\s+only|sports\s+highlights)\b",
    re.I,
)


def youtube_url_for_oembed(url: str) -> Optional[str]:
    """
    Normalize to a ``https://www.youtube.com/watch?v=…`` URL for YouTube's public oEmbed API.

    Returns ``None`` for channels, playlists, and other shapes oEmbed does not resolve to
    a single video.
    """
    u = (url or "").strip()
    if not u:
        return None
    if classify_youtube_link(u) != "video":
        return None
    try:
        p = urlparse(u)
    except Exception:
        return None
    host = (p.netloc or "").lower().split(":")[0]
    path = p.path or ""
    q = p.query or ""

    if host in ("youtu.be", "www.youtu.be"):
        vid = path.strip("/").split("/")[0]
        return f"https://www.youtube.com/watch?v={vid}" if vid else None

    if "/embed/" in path:
        m = re.search(r"/embed/([^/?&]+)", path)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"

    if "/shorts/" in path:
        m = re.search(r"/shorts/([^/?&]+)", path)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"

    if "/watch" in path or path.rstrip("/").endswith("watch"):
        vids = parse_qs(q).get("v") or []
        if vids and vids[0]:
            return strip_url_fragment(f"https://www.youtube.com/watch?v={vids[0]}")

    if "/live" in path:
        vids = parse_qs(q).get("v") or []
        if vids and vids[0]:
            return strip_url_fragment(f"https://www.youtube.com/watch?v={vids[0]}")

    return None


def score_youtube_meeting_relevance(
    title: str,
    author_name: str = "",
    *,
    homepage_host: str = "",
) -> Tuple[str, float, List[str]]:
    """
    Score oEmbed ``title`` / ``author_name`` for civic-meeting similarity.

    Returns ``(label, score, signal_tags)`` where ``label`` is one of:
    ``likely_meeting``, ``possible_meeting``, ``weak_signal``, ``unlikely_meeting``, ``unclear``,
    or ``unknown`` (empty text).
    """
    t = (title or "").strip()
    a = (author_name or "").strip()
    blob = f"{t}\n{a}".strip()
    signals: List[str] = []
    if not blob:
        return "unknown", 0.0, []

    score = 0.0
    if _YOUTUBE_NON_MEETING.search(blob):
        score -= 2.5
        signals.append("non_meeting_topic_hint")
    if _YOUTUBE_MEETING_STRONG.search(blob):
        score += 4.0
        signals.append("strong_meeting_term")
    if _YOUTUBE_MEETING_WEAK.search(blob):
        score += 1.5
        signals.append("weak_meeting_term")

    h = (homepage_host or "").lower().split(":")[0].lstrip(".")
    if h and h in a.lower():
        score += 1.25
        signals.append("author_matches_homepage_host")

    if score >= 3.5:
        label = "likely_meeting"
    elif score >= 2.0:
        label = "possible_meeting"
    elif score > 0:
        label = "weak_signal"
    elif score < 0:
        label = "unlikely_meeting"
    else:
        label = "unclear"

    return label, score, signals


def extract_youtube_refs(html: str, page_url: str) -> List[Dict[str, str]]:
    """
    Collect YouTube video and channel URLs from ``<a href>``, ``<iframe>`` / ``<embed>`` src,
    ``<link href>``, and common ``data-*`` lazy attributes.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    out: List[Dict[str, str]] = []
    seen: Set[str] = set()

    def consider(raw: str, found_via: str) -> None:
        nu = normalize_youtube_url(raw, page_url)
        if not nu:
            return
        if nu in seen:
            return
        seen.add(nu)
        out.append(
            {
                "url": nu,
                "link_type": classify_youtube_link(nu),
                "found_via": found_via,
            }
        )

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        if "youtube" in href.lower() or "youtu.be" in href.lower():
            consider(href, "a_href")

    for tag in soup.find_all(["iframe", "embed", "object"], src=True):
        src = (tag.get("src") or "").strip()
        if not src:
            continue
        if "youtube" in src.lower() or "youtu.be" in src.lower():
            consider(src, tag.name)

    for tag in soup.find_all(True):
        for attr in ("data-youtube-url", "data-src", "data-url"):
            v = tag.get(attr)
            if v and isinstance(v, str) and ("youtube" in v.lower() or "youtu.be" in v.lower()):
                consider(v, attr)

    for link in soup.find_all("link", href=True):
        href = (link.get("href") or "").strip()
        if "youtube.com" in href.lower() or "youtu.be" in href.lower():
            consider(href, "link_href")

    return out


def _looks_like_youtube_url(url: str) -> bool:
    low = (url or "").lower()
    return "youtube.com" in low or "youtu.be" in low or "youtube-nocookie.com" in low


def _absolute_http_stream_url(raw: str, page_url: str) -> Optional[str]:
    u = (raw or "").strip()
    if not u or u.startswith("#") or u.lower().startswith(("javascript:", "mailto:", "tel:")):
        return None
    if u.startswith("//"):
        u = "https:" + u
    try:
        full = dedupe_repeated_url_path(strip_url_fragment(urljoin(page_url, u)))
        p = urlparse(full)
    except Exception:
        return None
    if p.scheme not in ("http", "https"):
        return None
    if len(full) > 2500:
        return None
    return full


# Non-YouTube players and meeting-video hosts (YouTube handled by :pyfunc:`extract_youtube_refs`).
_OTHER_VIDEO_STREAM_PATTERNS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("vimeo", re.compile(r"vimeo\.com|player\.vimeo\.com", re.I)),
    (
        "facebook",
        re.compile(
            r"facebook\.com/(?:watch|plugins/video|[^/]+/videos)|fb\.watch|fb\.com/plugins/video",
            re.I,
        ),
    ),
    ("twitch", re.compile(r"twitch\.tv|player\.twitch\.tv", re.I)),
    ("dailymotion", re.compile(r"dailymotion\.com|dai\.ly", re.I)),
    ("zoom", re.compile(r"(?:[\w.-]+\.)?zoom\.us/(?:j/|wc/|w/|join|my/|rec/)", re.I)),
    ("google_meet", re.compile(r"meet\.google\.com/[a-z0-9\-]+", re.I)),
    ("teams", re.compile(r"teams\.microsoft\.com|teams\.live\.com", re.I)),
    ("webex", re.compile(r"webex\.com|(?:[\w.-]+\.)?webex\.com", re.I)),
    ("granicus", re.compile(r"granicus\.com|granicusideas\.com", re.I)),
    ("civicclerk", re.compile(r"civicclerk\.com", re.I)),
    ("civicengage_video", re.compile(r"videoplayer\.civicengage\.|streamingvideoplayer", re.I)),
    ("wistia", re.compile(r"wistia\.com|wistia\.net|fast\.wistia\.net", re.I)),
    ("brightcove", re.compile(r"brightcove\.com|players\.brightcove\.net|edge\.brightcove\.com", re.I)),
    ("boxcast", re.compile(r"boxcast\.tv|boxcast\.io", re.I)),
    ("swagit", re.compile(r"swagit\.com|swagit\.net", re.I)),
    ("dacast", re.compile(r"dacast\.com", re.I)),
    ("panopto", re.compile(r"panopto\.com", re.I)),
    ("kaltura", re.compile(r"kaltura\.com|cdnsecakmi\.kaltura\.com", re.I)),
    ("microsoft_stream", re.compile(r"microsoftstream\.com|web\.microsoftstream\.com", re.I)),
    ("jwplayer", re.compile(r"jwplayer\.com|cdn\.jwplayer\.com", re.I)),
    ("uscreen", re.compile(r"uscreen\.io|videodelivery\.net", re.I)),
)


def _classify_other_stream_platform(full: str) -> Optional[str]:
    if _looks_like_youtube_url(full):
        return None
    if re.search(r"\.m3u8(?:\?|#|$)", full, re.I):
        return "hls_manifest"
    for platform, pat in _OTHER_VIDEO_STREAM_PATTERNS:
        if pat.search(full):
            return platform
    return None


def extract_other_video_stream_refs(html: str, page_url: str) -> List[Dict[str, str]]:
    """
    Collect **non-YouTube** video / livestream URLs (Vimeo, Facebook video, Granicus, Zoom links,
    Teams, Wistia, Brightcove, ``.m3u8`` manifests, …). Same discovery surfaces as YouTube:
    ``<a href>``, ``<iframe>`` / ``<embed>`` ``src``, ``<video>`` / ``<source>``, and common
    ``data-*`` player attributes.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    out: List[Dict[str, str]] = []
    seen: Set[str] = set()

    def consider(raw: str, found_via: str) -> None:
        full = _absolute_http_stream_url(raw, page_url)
        if not full:
            return
        plat = _classify_other_stream_platform(full)
        if not plat:
            return
        if full in seen:
            return
        seen.add(full)
        out.append({"url": full, "platform": plat, "found_via": found_via})

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        consider(href, "a_href")

    for tag in soup.find_all(["iframe", "embed", "object"], src=True):
        src = (tag.get("src") or "").strip()
        if src:
            consider(src, tag.name)

    for tag in soup.find_all("object", data=True):
        d = (tag.get("data") or "").strip()
        if d:
            consider(d, "object_data")

    for tag in soup.find_all("video", src=True):
        src = (tag.get("src") or "").strip()
        if src:
            consider(src, "video_tag")

    for tag in soup.find_all("source", src=True):
        src = (tag.get("src") or "").strip()
        if src:
            consider(src, "source_tag")

    for tag in soup.find_all(True):
        for attr in (
            "data-src",
            "data-url",
            "data-stream-url",
            "data-video-url",
            "data-embed-url",
            "data-player-url",
            "data-live-url",
        ):
            v = tag.get(attr)
            if v and isinstance(v, str):
                consider(v, attr)

    for link in soup.find_all("link", href=True):
        href = (link.get("href") or "").strip()
        if href:
            consider(href, "link_href")

    return out


def classify_document(url: str, anchor_text: str = "") -> str:
    blob = f"{url} {anchor_text}".lower()
    for name, pat in _DOC_TYPE_RULES:
        if pat.search(blob):
            return name
    return "unknown"


def detect_meeting_stacks(html: str, page_url: str) -> List[str]:
    """Return ordered unique stack ids (strong signals first)."""
    blob = f"{html[:120_000]} {page_url}".lower()
    found: List[str] = []
    seen: Set[str] = set()
    for name, pat in _STACK_PATTERNS:
        if pat.search(blob) and name not in seen:
            seen.add(name)
            found.append(name)
    return found


def merge_stack_hints(existing: Sequence[str], page_hints: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for seq in (existing, page_hints):
        for h in seq:
            if h not in seen:
                seen.add(h)
                out.append(h)
    return out


def extract_meeting_urls(
    html: str,
    page_url: str,
    homepage: str,
    *,
    generic_hint: re.Pattern,
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Return ``(nav_urls, pdf_pairs)`` to crawl or download.

    ``pdf_pairs`` are ``(absolute_url, anchor_text)`` for :pyfunc:`classify_document`.

    - Same-site links matching ``generic_hint`` on URL or anchor text, or PDFs.
    - Trusted offsite PDFs (Legistar / Granicus / …).
    - Trusted offsite vendor meeting pages (narrow path heuristics).
    """
    soup = BeautifulSoup(html or "", "html.parser")
    nav: List[str] = []
    pdfs: List[Tuple[str, str]] = []
    seen_nav: Set[str] = set()
    seen_pdf: Set[str] = set()

    def add_nav(u: str) -> None:
        if u not in seen_nav:
            seen_nav.add(u)
            nav.append(u)

    def add_pdf(u: str, anchor: str) -> None:
        if u not in seen_pdf:
            seen_pdf.add(u)
            pdfs.append((u, anchor))

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        full = resolve_page_href(page_url, href)
        text = (a.get_text() or "").strip()
        text_l = text.lower()
        if PDF_EXT.search(full):
            if (
                is_same_site(full, homepage)
                or is_same_site(full, page_url)
                or is_trusted_offsite(full)
            ):
                add_pdf(full, text)
            continue
        if is_same_site(full, homepage) or is_same_site(full, page_url):
            if (
                generic_hint.search(full)
                or generic_hint.search(text_l)
                or _SITE_SEARCH_URL_RE.search(full)
                or _SITE_SEARCH_URL_RE.search(href)
            ):
                add_nav(full)
        elif is_vendor_meeting_page_url(full):
            add_nav(full)
        elif is_linked_local_meeting_microsite(full, homepage):
            if (
                generic_hint.search(full)
                or generic_hint.search(text_l)
                or _SITE_SEARCH_URL_RE.search(full)
                or _SITE_SEARCH_URL_RE.search(href)
            ):
                add_nav(full)

    # iframes (embedded Legistar / Granicus calendars)
    for tag in soup.find_all(["iframe", "frame"], src=True):
        src = (tag.get("src") or "").strip()
        if not src:
            continue
        full = resolve_page_href(page_url, src)
        if (
            is_same_site(full, homepage)
            or is_same_site(full, page_url)
            or is_vendor_meeting_page_url(full)
        ):
            add_nav(full)

    return nav, pdfs


def all_pdf_urls_from_page(
    html: str,
    page_url: str,
    homepage: str,
    generic_hint: re.Pattern,
) -> FrozenSet[str]:
    _, pairs = extract_meeting_urls(html, page_url, homepage, generic_hint=generic_hint)
    return frozenset(u for u, _ in pairs)
