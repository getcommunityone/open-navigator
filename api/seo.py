"""Search-engine surface for the SPA (#1430): sitemaps and per-route ``<head>`` meta in the first HTML response.

Crawlers and link previews read the HTML the server sends, before any JavaScript runs. The React app is one
``index.html`` for every path, so without this module ``/stories/guns`` would carry the home page's title.

- ``route_meta(path, query, stories)``: title, description, canonical, robots and breadcrumbs for one path.
- ``render_index(html, meta)``: the built ``index.html`` with those tags swapped in.
- ``build_sitemap_app(stories, ...)`` / ``build_sitemap_index(...)``: the sitemaps, from the real public routes and the
  live stories.

Route titles and descriptions come from ``web_app/src/data/seo/routes.json`` and the story copy from
``web_app/src/data/seo/story-copy.json``: the same files the React app's ``routeMeta()`` reads, so the server and the
client never name a page differently. Live stories (curated topics with linked meetings) and their dates come from the
warehouse (``load_stories``); nothing is made up when it is unavailable, the fields are just left out.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import re
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode
from xml.sax.saxutils import escape as xml_escape

from loguru import logger

_REPO = Path(__file__).resolve().parent.parent
# The Databricks bundle stages this directory too (apps/open-navigator-web/build.sh).
_SEO_DATA_DIRS = (_REPO / "web_app" / "src" / "data" / "seo",)

# States need at least this many linked meetings before their story URL goes in the sitemap: a state page with a
# handful of meetings is thin content, which hurts more than it helps.
SITEMAP_STATE_MIN_MEETINGS = int(os.getenv("SITEMAP_STATE_MIN_MEETINGS", "25"))
# The sitemap protocol's per-file limit.
SITEMAP_MAX_URLS = 50_000
_STORIES_TTL_S = 3600.0
_STORIES_TIMEOUT_S = 4.0
_STORIES_RETRY_S = 60.0


def _load_json(name: str) -> dict[str, Any]:
    for d in _SEO_DATA_DIRS:
        p = d / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    logger.warning("SEO data file {} not found; serving default meta only", name)
    return {}


ROUTES_DATA = _load_json("routes.json")
STORY_COPY = _load_json("story-copy.json")
SITE: dict[str, Any] = ROUTES_DATA.get("site", {})
SITE_NAME: str = SITE.get("name", "CommunityOne")
TITLE_SUFFIX: str = SITE.get("titleSuffix", SITE_NAME)
DEFAULT_TITLE: str = SITE.get("defaultTitle", SITE_NAME)
DEFAULT_DESCRIPTION: str = SITE.get("defaultDescription", "")
ROUTES: dict[str, dict[str, Any]] = {
    r["path"]: r for r in ROUTES_DATA.get("routes", [])
}
PRIVATE_PREFIXES: list[dict[str, str]] = ROUTES_DATA.get("private", [])
REGISTRY_STORIES: dict[str, dict[str, str]] = STORY_COPY.get("stories", {})
TOPIC_COPY: dict[str, dict[str, str]] = STORY_COPY.get("topics", {})
# The one state-name map the server and the app share (web_app/src/data/seo/states.json): 50 states + DC.
STATE_NAMES: dict[str, str] = _load_json("states.json")
# Real detail routes (decisions, meetings, organizations…): indexable though not listed in the sitemap.
INDEXABLE_PREFIXES: list[str] = ROUTES_DATA.get("indexablePrefixes", [])


def site_url() -> str:
    """The public origin (no trailing slash). ``PUBLIC_SITE_URL`` overrides it for a staging host."""
    return (
        os.getenv("PUBLIC_SITE_URL")
        or SITE.get("baseUrl")
        or "https://www.communityone.com"
    ).rstrip("/")


def page_title(page: str | None) -> str:
    """``"<page> | CommunityOne"``; the site's default title when ``page`` is empty (mirrors ``documentTitle()``)."""
    p = re.sub(r"\s+", " ", page or "").strip()
    return f"{p} | {TITLE_SUFFIX}" if p else DEFAULT_TITLE


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


# ---------------------------------------------------------------------------
# Live stories
# ---------------------------------------------------------------------------


@dataclass
class StoryState:
    state_code: str
    state: str | None
    meetings: int
    last_meeting: date | None = None


@dataclass
class Story:
    slug: str
    title: str
    lede: str
    meetings: int | None = None
    last_meeting: date | None = None
    states: dict[str, StoryState] = field(default_factory=dict)


def registry_story(slug: str) -> Story | None:
    """A story in the stories registry (the Data Center Story); it is live whatever the warehouse says."""
    s = REGISTRY_STORIES.get(slug)
    if not s:
        return None
    return Story(
        slug=slug,
        title=cap(s.get("topic", slug)),
        lede=s.get("lede") or s.get("question", ""),
    )


def topic_story(slug: str, name: str) -> Story:
    """A curated topic's story, with its hand-written copy when it has some (``deriveTopicStories`` in the app)."""
    copy = TOPIC_COPY.get(slug, {})
    return Story(
        slug=slug,
        title=copy.get("title") or name,
        lede=copy.get("lede")
        or f"What local governments said about {name.lower()}, in the words said at the meeting.",
    )


def shape_stories(
    topic_rows: Iterable[Mapping[str, Any]], state_rows: Iterable[Mapping[str, Any]]
) -> dict[str, Story]:
    """The live stories, keyed by slug: the registry first, then curated topics with linked meetings, ordered by
    meetings (most first), as ``liveStories()`` orders them in the app."""
    out: dict[str, Story] = {slug: registry_story(slug) for slug in REGISTRY_STORIES}  # type: ignore[misc]
    by_topic: dict[int, Story] = {}
    topics = sorted(
        topic_rows, key=lambda r: (-(r.get("meetings") or 0), str(r.get("name") or ""))
    )
    for r in topics:
        slug = r.get("query_id")
        if not slug or not (r.get("meetings") or 0) > 0:
            continue
        story = out.get(slug) or topic_story(slug, str(r.get("name") or slug))
        story.meetings = int(r["meetings"])
        out[slug] = story
        by_topic[int(r["topic_id"])] = story
    for r in state_rows:
        story = by_topic.get(int(r["topic_id"]))
        code = (r.get("state_code") or "").upper()
        if story is None or not re.fullmatch(r"[A-Z]{2}", code):
            continue
        st = StoryState(
            code, r.get("state"), int(r.get("meetings") or 0), r.get("last_meeting")
        )
        story.states[code] = st
        if st.last_meeting and (
            story.last_meeting is None or st.last_meeting > story.last_meeting
        ):
            story.last_meeting = st.last_meeting
    return out


# Curated topics with linked meetings: the same rule as `isLiveTopic` (source = 'curated', a query_id, meetings > 0).
_LIVE_TOPICS_SQL = """
    SELECT t.topic_id, t.name, t.query_id, n.transcript_count AS meetings
    FROM civicsearch_topic t
    JOIN browse_transcript_count n ON n.entity_type = 'topic' AND n.entity_id = t.topic_id::text
    WHERE to_jsonb(t) ->> 'source' = 'curated' AND t.query_id IS NOT NULL AND n.transcript_count > 0
"""

_STORY_STATES_SQL = """
    SELECT l.topic_id, l.state_code, max(l.state) AS state, count(DISTINCT l.video_id)::int AS meetings,
           max(l.event_date) AS last_meeting
    FROM topic_transcript_link l
    WHERE l.topic_id = ANY($1::int[]) AND l.state_code IS NOT NULL
    GROUP BY l.topic_id, l.state_code
"""

_stories_cache: dict[str, Any] = {"at": 0.0, "value": None}
_stories_lock = asyncio.Lock()


async def _fetch_stories() -> dict[str, Story]:
    from api.routes.search_postgres import get_db_pool

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        topics = [dict(r) for r in await conn.fetch(_LIVE_TOPICS_SQL)]
        states = [
            dict(r)
            for r in await conn.fetch(
                _STORY_STATES_SQL, [int(t["topic_id"]) for t in topics]
            )
        ]
    return shape_stories(topics, states)


async def load_stories() -> dict[str, Story] | None:
    """The live stories, cached for an hour. During a warehouse outage the last good list keeps being served (stale)
    and the warehouse is retried at most once a minute, so story pages never queue behind a dead connection.
    ``None`` only when nothing has ever loaded (callers then fall back to the registry's stories, rather than guess)."""

    def fresh() -> bool:
        return (
            _stories_cache["value"] is not None
            and time.monotonic() - _stories_cache["at"] < _STORIES_TTL_S
        )

    def backing_off() -> bool:
        return time.monotonic() < _stories_cache.get("retry_at", 0.0)

    if fresh() or backing_off():
        return _stories_cache["value"]
    async with _stories_lock:
        # Another request may have refreshed the list, or just failed and set the back-off, while this one waited.
        if fresh() or backing_off():
            return _stories_cache["value"]
        try:
            value = await asyncio.wait_for(_fetch_stories(), timeout=_STORIES_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SEO: live stories unavailable ({}); serving the last good list", exc
            )
            _stories_cache["retry_at"] = time.monotonic() + _STORIES_RETRY_S
            return _stories_cache["value"]
        _stories_cache.update(at=time.monotonic(), value=value, retry_at=0.0)
        return value


def fallback_stories() -> dict[str, Story]:
    return {slug: registry_story(slug) for slug in REGISTRY_STORIES}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Route meta
# ---------------------------------------------------------------------------


@dataclass
class Breadcrumb:
    name: str
    url: str


@dataclass
class RouteMeta:
    title: str
    description: str
    canonical: str
    robots: str = "index, follow"
    og_type: str = "website"
    breadcrumbs: list[Breadcrumb] = field(default_factory=list)
    # The path (and query) these tags were rendered for; set by render_spa_page.
    rendered_for: str = ""


def _norm_path(path: str) -> str:
    """Decoded, slash-trimmed path, so `/admi%6e` is checked as `/admin`."""
    return "/" + unquote(path or "").strip("/")


def _first(query: Mapping[str, Any], key: str) -> str | None:
    v = query.get(key)
    if isinstance(v, (list, tuple)):
        v = v[0] if v else None
    v = (v or "").strip() if isinstance(v, str) else None
    return v or None


def story_page_title(topic_title: str, state_name: str | None = None) -> str:
    """``"Gun control in Alabama — Data story"`` (the app's ``storyPageTitle``)."""
    where = f" in {state_name}" if state_name else ""
    return f"{cap(topic_title)}{where} — Data story"


def route_meta(
    path: str,
    query: Mapping[str, Any] | None = None,
    stories: Mapping[str, Story] | None = None,
) -> RouteMeta:
    """The ``<head>`` meta for one path. ``query`` is a parsed query string (``parse_qs`` shape or plain values).

    ``stories`` is the live-story catalog; ``None`` means it could not be loaded, so an unknown story slug keeps a
    plain "Data story" title and stays indexable rather than be marked missing on a guess."""
    query = query or {}
    base = site_url()
    p = _norm_path(path)

    for priv in PRIVATE_PREFIXES:
        pre = priv["prefix"]
        if p == pre or p.startswith(pre + "/"):
            return RouteMeta(
                page_title(priv.get("title")),
                DEFAULT_DESCRIPTION,
                f"{base}{p}",
                robots="noindex, nofollow",
            )

    m = re.fullmatch(r"/stories/([^/]+)", p)
    if m:
        slug = m.group(1)
        catalog = stories if stories is not None else fallback_stories()
        story = catalog.get(slug)
        if story is None and stories is None and TOPIC_COPY.get(slug, {}).get("title"):
            # Catalog unavailable: a topic with a hand-written title still gets it (the app's `storyCopyTitle`).
            story = topic_story(slug, TOPIC_COPY[slug]["title"])
        if story is None:
            robots = "noindex, follow" if stories is not None else "index, follow"
            return RouteMeta(
                page_title("Data story"),
                DEFAULT_DESCRIPTION,
                f"{base}{p}",
                robots=robots,
            )
        # Only a real state (states.json) is a scope; anything else is ignored rather than named in the title.
        state_code = (_first(query, "state") or "").upper() or None
        if state_code not in STATE_NAMES:
            state_code = None
        story_url = f"{base}/stories/{quote(slug)}"
        state_url = (
            f"{story_url}?{urlencode({'state': state_code})}"
            if state_code
            else story_url
        )
        label = STATE_NAMES.get(state_code) if state_code else None
        # A state with no meetings for this story is a real filter (the page says so) but a thin page: keep it out
        # of the index and point its canonical at the story. Only when the catalog loaded; never on a guess.
        thin = (
            bool(state_code) and stories is not None and state_code not in story.states
        )
        canonical = story_url if thin else state_url
        robots = "noindex, follow" if thin else "index, follow"
        crumbs = [
            Breadcrumb(SITE_NAME, f"{base}/"),
            Breadcrumb("Data stories", f"{base}/stories"),
            Breadcrumb(cap(story.title), story_url),
        ]
        if state_code and not thin:
            crumbs.append(Breadcrumb(label or state_code, state_url))
        description = f"{label}: {story.lede}" if label else story.lede
        return RouteMeta(
            page_title(story_page_title(story.title, label)),
            description,
            canonical,
            robots=robots,
            og_type="article",
            breadcrumbs=crumbs,
        )

    route = ROUTES.get(p)
    if route is None and p.startswith("/data-explorer/map/"):
        route = ROUTES.get("/data-explorer/map/us/2024/median_household_income")
        if route is not None:
            return RouteMeta(
                page_title(route.get("title")),
                route.get("description") or DEFAULT_DESCRIPTION,
                f"{base}{p}",
            )
    if route is not None:
        canonical = f"{base}/" if p == "/" else f"{base}{p}"
        return RouteMeta(
            page_title(route.get("title")),
            route.get("description") or DEFAULT_DESCRIPTION,
            canonical,
        )

    # A real detail page (decision, meeting, organization…): the site default, canonical to itself.
    if any(p.startswith(pre) or p == pre.rstrip("/") for pre in INDEXABLE_PREFIXES):
        return RouteMeta(DEFAULT_TITLE, DEFAULT_DESCRIPTION, f"{base}{p}")
    # Anything else (a mistyped path the app shows as Not found, a legacy redirect): served, but not indexed.
    return RouteMeta(
        DEFAULT_TITLE, DEFAULT_DESCRIPTION, f"{base}{p}", robots="noindex, follow"
    )


# ---------------------------------------------------------------------------
# index.html rendering
# ---------------------------------------------------------------------------


def _attr(v: str) -> str:
    return html.escape(v, quote=True)


def breadcrumb_jsonld(crumbs: list[Breadcrumb]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": c.name, "item": c.url}
            for i, c in enumerate(crumbs, start=1)
        ],
    }


def _sub_or_insert(doc: str, pattern: str, replacement: str) -> str:
    new, n = re.subn(
        pattern, lambda _m: replacement, doc, count=1, flags=re.IGNORECASE | re.DOTALL
    )
    if n:
        return new
    return re.sub(
        r"</head>",
        lambda _m: f"    {replacement}\n  </head>",
        doc,
        count=1,
        flags=re.IGNORECASE,
    )


def _meta_pattern(attr: str, name: str) -> str:
    return rf'<meta\s+{attr}="{re.escape(name)}"[^>]*>'


def render_index(doc: str, meta: RouteMeta) -> str:
    """``index.html`` with this route's title, description, canonical, robots and OpenGraph/Twitter tags, plus a
    BreadcrumbList JSON-LD block when the route has breadcrumbs."""
    t, d, c = _attr(meta.title), _attr(meta.description), _attr(meta.canonical)
    doc = _sub_or_insert(doc, r"<title>.*?</title>", f"<title>{t}</title>")
    for attr, name, value in (
        ("name", "title", t),
        ("name", "description", d),
        ("name", "robots", _attr(meta.robots)),
        ("property", "og:type", _attr(meta.og_type)),
        ("property", "og:url", c),
        ("property", "og:title", t),
        ("property", "og:description", d),
        ("name", "twitter:url", c),
        ("name", "twitter:title", t),
        ("name", "twitter:description", d),
    ):
        doc = _sub_or_insert(
            doc,
            _meta_pattern(attr, name),
            f'<meta {attr}="{name}" content="{value}" />',
        )
    doc = _sub_or_insert(
        doc, r'<link\s+rel="canonical"[^>]*>', f'<link rel="canonical" href="{c}" />'
    )
    # Tells the app these tags were rendered for this page, so it doesn't overwrite them on first load (#1430).
    if meta.rendered_for:
        doc = _sub_or_insert(
            doc,
            _meta_pattern("name", "seo-rendered"),
            f'<meta name="seo-rendered" content="{_attr(meta.rendered_for)}" />',
        )
    if meta.breadcrumbs:
        # `</` can't appear inside the JSON text, so a name can't close the script element early.
        payload = json.dumps(
            breadcrumb_jsonld(meta.breadcrumbs), ensure_ascii=False
        ).replace("</", "<\\/")
        block = f'<script type="application/ld+json" data-seo="breadcrumbs">{payload}</script>'
        doc = re.sub(
            r"</head>",
            lambda _m: f"    {block}\n  </head>",
            doc,
            count=1,
            flags=re.IGNORECASE,
        )
    return doc


_index_cache: dict[str, Any] = {"path": None, "mtime": None, "text": None}


def read_index(index_file: Path) -> str:
    mtime = index_file.stat().st_mtime
    if _index_cache["path"] != index_file or _index_cache["mtime"] != mtime:
        _index_cache.update(
            path=index_file, mtime=mtime, text=index_file.read_text(encoding="utf-8")
        )
    return _index_cache["text"]


def parse_original_uri(uri: str) -> tuple[str, dict[str, list[str]]]:
    path, _, qs = (uri or "/").partition("?")
    return path or "/", parse_qs(qs)


async def render_spa_page(index_file: Path, path: str, query: Mapping[str, Any]) -> str:
    """The built ``index.html`` for ``path``, with its own meta. Story pages read the live-story catalog."""
    stories = await load_stories() if _norm_path(path).startswith("/stories/") else None
    meta = route_meta(path, query, stories)
    qs = urlencode(query, doseq=True)
    meta.rendered_for = path + (f"?{qs}" if qs else "")
    return render_index(read_index(index_file), meta)


# ---------------------------------------------------------------------------
# Sitemaps
# ---------------------------------------------------------------------------


@dataclass
class SitemapUrl:
    loc: str
    lastmod: date | None = None
    changefreq: str | None = None
    priority: str | None = None


def sitemap_urls(
    stories: Mapping[str, Story] | None, static_lastmod: date | None = None
) -> list[SitemapUrl]:
    """Every indexable URL: the public routes flagged ``sitemap`` in routes.json, every live story, and each story's
    state pages (``/stories/<slug>?state=XX``, the app's own scope pattern) for states with enough meetings.

    ``static_lastmod`` is the date the built app was deployed (index.html's mtime); a story's lastmod is the date of
    its newest linked meeting. A date that isn't known is left out."""
    base = site_url()
    urls: list[SitemapUrl] = []
    for r in ROUTES_DATA.get("routes", []):
        if not r.get("sitemap"):
            continue
        loc = f"{base}/" if r["path"] == "/" else f"{base}{r['path']}"
        urls.append(
            SitemapUrl(loc, static_lastmod, r.get("changefreq"), r.get("priority"))
        )
    catalog = stories if stories is not None else fallback_stories()
    for story in catalog.values():
        story_url = f"{base}/stories/{quote(story.slug)}"
        urls.append(SitemapUrl(story_url, story.last_meeting, "daily", "0.9"))
        for code in sorted(story.states):
            st = story.states[code]
            if st.meetings >= SITEMAP_STATE_MIN_MEETINGS:
                urls.append(
                    SitemapUrl(
                        f"{story_url}?{urlencode({'state': code})}",
                        st.last_meeting,
                        "weekly",
                        "0.6",
                    )
                )
    seen: set[str] = set()
    out = []
    for u in urls:
        if u.loc not in seen:
            seen.add(u.loc)
            out.append(u)
    return out[:SITEMAP_MAX_URLS]


def build_urlset(urls: list[SitemapUrl]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape(u.loc)}</loc>")
        if u.lastmod:
            lines.append(f"    <lastmod>{u.lastmod.isoformat()}</lastmod>")
        if u.changefreq:
            lines.append(f"    <changefreq>{u.changefreq}</changefreq>")
        if u.priority:
            lines.append(f"    <priority>{u.priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def build_sitemap_index(app_lastmod: date | None) -> str:
    base = site_url()
    entries = [
        (f"{base}/sitemap-app.xml", app_lastmod),
        (f"{base}/docs/sitemap.xml", None),
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in entries:
        lines.append("  <sitemap>")
        lines.append(f"    <loc>{xml_escape(loc)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod.isoformat()}</lastmod>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines) + "\n"


def deployed_on(index_file: Path) -> date | None:
    """The date the built app was deployed: index.html's mtime, or None without a build."""
    try:
        return date.fromtimestamp(index_file.stat().st_mtime)
    except OSError:
        return None
