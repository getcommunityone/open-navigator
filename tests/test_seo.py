"""Sitemaps, per-route <head> meta and JSON-LD (#1430).

The live-story catalog is stubbed here (the stub never leaves the tests); the shapes match what ``api.seo._fetch_stories``
reads from ``civicsearch_topic`` / ``browse_transcript_count`` / ``topic_transcript_link``.
"""

from __future__ import annotations

import asyncio
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest

from api import seo
from api.main import app
from api.routes import seo as seo_routes

REPO = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO / "web_app" / "index.html"
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
BASE = "https://www.communityone.com"
PRIVATE = (
    "/dashboard",
    "/analytics",
    "/profile",
    "/settings",
    "/debate-grader",
    "/services",
    "/admin",
    "/feed-setup",
)

TOPIC_ROWS = [
    {
        "topic_id": 100001,
        "name": "Data centers",
        "query_id": "data-centers",
        "meetings": 2257,
    },
    {"topic_id": 100005, "name": "Guns", "query_id": "guns", "meetings": 7684},
    {
        "topic_id": 100006,
        "name": "Pickleball",
        "query_id": "pickleball",
        "meetings": 4014,
    },
]
STATE_ROWS = [
    {
        "topic_id": 100005,
        "state_code": "AL",
        "state": "Alabama",
        "meetings": 120,
        "last_meeting": date(2026, 11, 19),
    },
    {
        "topic_id": 100005,
        "state_code": "WY",
        "state": "Wyoming",
        "meetings": 3,
        "last_meeting": date(2026, 10, 2),
    },
    {
        "topic_id": 100001,
        "state_code": "VA",
        "state": "Virginia",
        "meetings": 300,
        "last_meeting": date(2026, 11, 23),
    },
    {
        "topic_id": 100006,
        "state_code": "TX",
        "state": "Texas",
        "meetings": 80,
        "last_meeting": date(2026, 11, 18),
    },
]


@pytest.fixture
def stories(monkeypatch):
    shaped = seo.shape_stories(TOPIC_ROWS, STATE_ROWS)

    async def fake_fetch():
        return shaped

    monkeypatch.setattr(seo, "_fetch_stories", fake_fetch)
    seo._stories_cache.update(at=0.0, value=None, retry_at=0.0)
    yield shaped
    seo._stories_cache.update(at=0.0, value=None, retry_at=0.0)


def _get(path: str, headers: dict | None = None) -> httpx.Response:
    async def go():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path, headers=headers or {})

    return asyncio.run(go())


def _locs(xml_text: str, tag: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [el.findtext(f"{SM}loc") for el in root.findall(f"{SM}{tag}")]


# --- sitemaps -----------------------------------------------------------------------------------------------------


def test_sitemap_index_is_valid_xml_pointing_at_app_and_docs(stories):
    r = _get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(r.text)
    assert root.tag == f"{SM}sitemapindex"
    assert _locs(r.text, "sitemap") == [
        f"{BASE}/sitemap-app.xml",
        f"{BASE}/docs/sitemap.xml",
    ]


def test_sitemap_app_lists_public_routes_and_live_stories(stories):
    r = _get("/sitemap-app.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(r.text)
    assert root.tag == f"{SM}urlset"
    locs = _locs(r.text, "url")
    assert len(locs) == len(set(locs)) and len(locs) < 50_000
    for expected in (
        f"{BASE}/",
        f"{BASE}/stories",
        f"{BASE}/stories/data-centers",
        f"{BASE}/stories/guns",
        f"{BASE}/stories/pickleball",
        f"{BASE}/browse-topics",
        f"{BASE}/browse-topics/all",
        f"{BASE}/browse-causes",
        f"{BASE}/data-explorer/map/us/2024/median_household_income",
        f"{BASE}/stories/guns?state=AL",
        f"{BASE}/stories/data-centers?state=VA",
    ):
        assert expected in locs, expected
    # A state below the meeting threshold stays out (thin page).
    assert f"{BASE}/stories/guns?state=WY" not in locs
    for loc in locs:
        path = urlparse(loc).path
        assert not path.startswith("/api"), loc
        assert not any(path == p or path.startswith(p + "/") for p in PRIVATE), loc


def test_sitemap_lastmod_is_the_newest_meeting(stories):
    root = ET.fromstring(_get("/sitemap-app.xml").text)
    by_loc = {
        u.findtext(f"{SM}loc"): u.findtext(f"{SM}lastmod")
        for u in root.findall(f"{SM}url")
    }
    assert by_loc[f"{BASE}/stories/guns"] == "2026-11-19"
    assert by_loc[f"{BASE}/stories/guns?state=AL"] == "2026-11-19"
    assert by_loc[f"{BASE}/stories/data-centers"] == "2026-11-23"
    for v in by_loc.values():
        assert v is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)


def test_sitemap_without_the_warehouse_keeps_the_registry_story_and_invents_nothing(
    monkeypatch,
):
    async def down():
        raise ConnectionError("warehouse down")

    monkeypatch.setattr(seo, "_fetch_stories", down)
    seo._stories_cache.update(at=0.0, value=None, retry_at=0.0)
    try:
        locs = _locs(_get("/sitemap-app.xml").text, "url")
        assert f"{BASE}/stories/data-centers" in locs
        assert f"{BASE}/stories/guns" not in locs
        assert not any("?state=" in loc for loc in locs)
        # A story page still gets its hand-written title, and is not marked missing on a guess.
        meta = seo.route_meta("/stories/guns", {}, None)
        assert (
            meta.title == "Gun control — Data story | CommunityOne"
            and meta.robots == "index, follow"
        )
    finally:
        seo._stories_cache.update(at=0.0, value=None, retry_at=0.0)


# --- per-route meta in the first HTML ----------------------------------------------------------------------------


class _Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta: dict[str, str] = {}
        self.canonical = None
        self.jsonld: list[str] = []
        self._in_title = False
        self._in_ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and ("name" in a or "property" in a):
            self.meta[a.get("name") or a.get("property")] = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self.jsonld.append("")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self.jsonld[-1] += data


def _head(html_text: str) -> _Head:
    h = _Head()
    h.feed(html_text)
    return h


@pytest.fixture
def built_index(monkeypatch):
    monkeypatch.setattr(seo_routes, "SPA_INDEX", INDEX_HTML)
    return INDEX_HTML


def test_story_page_html_has_its_own_title_and_description(stories, built_index):
    r = _get("/api/spa-shell", headers={"X-Original-URI": "/stories/guns"})
    assert r.status_code == 200
    assert "no-cache" in r.headers["cache-control"]
    h = _head(r.text)
    assert h.title == "Gun control — Data story | CommunityOne"
    assert h.meta["description"].startswith("Firearm rules")
    assert h.canonical == f"{BASE}/stories/guns"
    assert h.meta["og:title"] == h.title and h.meta["twitter:title"] == h.title
    assert h.meta["og:url"] == h.canonical and h.meta["og:type"] == "article"
    assert h.meta["og:description"] == h.meta["description"]
    home = _head(_get("/api/spa-shell", headers={"X-Original-URI": "/"}).text)
    assert home.title != h.title and home.meta["description"] != h.meta["description"]
    assert home.canonical == f"{BASE}/"


def test_state_story_page_names_the_state_and_keeps_only_state_in_canonical(
    stories, built_index
):
    h = _head(
        _get(
            "/api/spa-shell",
            headers={"X-Original-URI": "/stories/guns?state=AL&screen=overview"},
        ).text
    )
    assert h.title == "Gun control in Alabama — Data story | CommunityOne"
    assert h.canonical == f"{BASE}/stories/guns?state=AL"
    assert h.meta["description"].startswith("Alabama: ")


def test_core_pages_get_distinct_titles(stories, built_index):
    titles = {}
    for path in (
        "/",
        "/stories",
        "/browse-topics",
        "/browse-topics/all",
        "/browse-causes",
        "/search",
        "/stories/data-centers",
    ):
        titles[path] = _head(
            _get("/api/spa-shell", headers={"X-Original-URI": path}).text
        ).title
    assert len(set(titles.values())) == len(titles), titles


def test_private_pages_are_noindex_and_unknown_stories_are_not_indexed(
    stories, built_index
):
    assert (
        _head(_get("/api/spa-shell?uri=/settings").text)
        .meta["robots"]
        .startswith("noindex")
    )
    assert (
        _head(_get("/api/spa-shell?uri=/stories/no-such-topic").text)
        .meta["robots"]
        .startswith("noindex")
    )
    assert (
        _head(_get("/api/spa-shell?uri=/stories/guns").text).meta["robots"]
        == "index, follow"
    )


def test_render_escapes_markup_in_copy():
    meta = seo.RouteMeta(
        'A "quoted" <b>title</b>',
        "x & y",
        f"{BASE}/x",
        breadcrumbs=[seo.Breadcrumb("</script><b>", f"{BASE}/")],
    )
    out = seo.render_index(INDEX_HTML.read_text(encoding="utf-8"), meta)
    assert "<title>A &quot;quoted&quot; &lt;b&gt;title&lt;/b&gt;</title>" in out
    assert 'content="x &amp; y"' in out
    assert "</script><b>" not in out


# --- JSON-LD ------------------------------------------------------------------------------------------------------

REQUIRED = {
    "Organization": ("name", "url", "logo", "sameAs"),
    "WebSite": ("name", "url", "potentialAction"),
    "WebApplication": ("name", "url", "applicationCategory"),
    "ItemList": ("itemListElement", "numberOfItems"),
    "BreadcrumbList": ("itemListElement",),
}


def _check_node(node: dict) -> None:
    assert node.get("@context") == "https://schema.org"
    t = node.get("@type")
    assert t in REQUIRED, t
    for key in REQUIRED[t]:
        assert node.get(key), f"{t} is missing {key}"
    for key in ("url",):
        if key in node:
            assert node[key].startswith(BASE + "/"), node[key]
    if t in ("ItemList", "BreadcrumbList"):
        items = node["itemListElement"]
        assert [i["position"] for i in items] == list(range(1, len(items) + 1))
        for i in items:
            assert i["@type"] == "ListItem"
        if t == "ItemList":
            assert node["numberOfItems"] == len(items)
        else:
            for i in items:
                assert i["name"] and i["item"].startswith(BASE + "/")


def _site_jsonld() -> list[dict]:
    return [json.loads(b) for b in _head(INDEX_HTML.read_text(encoding="utf-8")).jsonld]


def test_homepage_jsonld_is_well_formed_and_current():
    nodes = _site_jsonld()
    for n in nodes:
        _check_node(n)
    by_type = {n["@type"]: n for n in nodes}
    org, site = by_type["Organization"], by_type["WebSite"]
    # One brand name everywhere: the Organization, the WebSite and the site config agree.
    assert org["name"] == site["name"] == seo.SITE_NAME == "CommunityOne"
    assert site["publisher"]["@id"] == org["@id"]
    # The logo is a raster file the app actually ships (the old .svg URL returned 404 on the live site).
    logo_path = urlparse(org["logo"]["url"]).path
    assert (
        logo_path.endswith(".png")
        and (REPO / "web_app" / "public" / logo_path.lstrip("/")).is_file()
    )
    assert org["sameAs"] == seo.ROUTES_DATA["sameAs"]
    assert all(u.startswith("https://") for u in org["sameAs"])
    template = site["potentialAction"]["target"]["urlTemplate"]
    assert (
        "{search_term_string}" in template
        and site["potentialAction"]["query-input"] == "required name=search_term_string"
    )
    # No stale or private page in the section list: each is a public sitemap route.
    sitemap_paths = {r["path"] for r in seo.ROUTES_DATA["routes"] if r.get("sitemap")}
    for item in by_type["ItemList"]["itemListElement"]:
        assert urlparse(item["item"]["url"]).path in sitemap_paths, item


def test_og_image_is_the_shipped_raster_logo():
    h = _head(INDEX_HTML.read_text(encoding="utf-8"))
    for key in ("og:image",):
        path = urlparse(h.meta[key]).path
        assert (REPO / "web_app" / "public" / path.lstrip("/")).is_file(), h.meta[key]
    assert h.meta["twitter:image"] == h.meta["og:image"]


def test_story_page_has_breadcrumb_jsonld(stories, built_index):
    h = _head(
        _get(
            "/api/spa-shell", headers={"X-Original-URI": "/stories/guns?state=AL"}
        ).text
    )
    crumbs = [json.loads(b) for b in h.jsonld if '"BreadcrumbList"' in b]
    assert len(crumbs) == 1
    _check_node(crumbs[0])
    assert [i["name"] for i in crumbs[0]["itemListElement"]] == [
        "CommunityOne",
        "Data stories",
        "Gun control",
        "Alabama",
    ]
    assert crumbs[0]["itemListElement"][-1]["item"] == f"{BASE}/stories/guns?state=AL"
    # Every other JSON-LD block on the page still parses.
    for b in h.jsonld:
        _check_node(json.loads(b))


# --- review follow-ups (#1430) ------------------------------------------------------------------------------------


def test_state_without_meetings_is_noindex_with_the_story_as_canonical(
    stories, built_index
):
    h = _head(
        _get(
            "/api/spa-shell", headers={"X-Original-URI": "/stories/guns?state=GA"}
        ).text
    )
    assert h.title == "Gun control in Georgia — Data story | CommunityOne"
    assert h.meta["robots"] == "noindex, follow"
    assert h.canonical == f"{BASE}/stories/guns"
    # A code that isn't a state is ignored, not named in the title.
    zz = _head(
        _get(
            "/api/spa-shell", headers={"X-Original-URI": "/stories/guns?state=ZZ"}
        ).text
    )
    assert zz.title == "Gun control — Data story | CommunityOne"
    assert zz.canonical == f"{BASE}/stories/guns"


def test_state_names_come_from_the_shared_map(stories):
    # The warehouse's spelling is not used for the label: server and app read the same states.json.
    assert seo.STATE_NAMES["GA"] == "Georgia" and len(seo.STATE_NAMES) == 51
    meta = seo.route_meta("/stories/guns", {"state": ["al"]}, stories)
    assert meta.title == "Gun control in Alabama — Data story | CommunityOne"
    assert meta.robots == "index, follow"


def test_unknown_paths_are_noindex_and_detail_pages_stay_indexable():
    assert seo.route_meta("/no-such-page").robots == "noindex, follow"
    assert seo.route_meta("/decisions/123").robots == "index, follow"
    assert seo.route_meta("/organizations/abc").robots == "index, follow"


def test_private_check_decodes_the_path():
    assert seo.route_meta("/admi%6e").robots == "noindex, nofollow"
    assert seo.route_meta("/%73ettings").robots == "noindex, nofollow"


def test_browse_all_topics_title_matches_the_page():
    assert (
        seo.route_meta("/browse-topics/all").title == "Browse all topics | CommunityOne"
    )


def test_rendered_page_marks_which_page_it_was_rendered_for(stories, built_index):
    text = _get(
        "/api/spa-shell", headers={"X-Original-URI": "/stories/guns?state=AL"}
    ).text
    assert _head(text).meta["seo-rendered"] == "/stories/guns?state=AL"


def test_outage_serves_the_stale_list_and_backs_off(monkeypatch, stories):
    calls = {"n": 0}

    async def down():
        calls["n"] += 1
        raise ConnectionError("warehouse down")

    async def run():
        first = await seo.load_stories()  # fresh fetch from the `stories` fixture
        assert first is not None and "guns" in first
        monkeypatch.setattr(seo, "_fetch_stories", down)
        seo._stories_cache["at"] = -1e9  # the cached list is now stale
        again = await seo.load_stories()
        third = await seo.load_stories()
        return first, again, third

    first, again, third = asyncio.run(run())
    assert again is first and third is first  # the last good list keeps being served
    assert (
        calls["n"] == 1
    )  # the second call is inside the back-off and doesn't hit the warehouse
