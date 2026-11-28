---
sidebar_position: 10
title: SEO and Google Sitelinks
description: How communityone.com tells search engines about its pages, and the Search Console steps only the owner can do.
---

# SEO and Google Sitelinks

Google chooses Sitelinks (the extra links under a site's main search result) by itself. Nothing in the page asks for
them. What a site can do is make its structure easy to read: a sitemap that lists the real pages, a distinct title and
description on each page, plain links between pages, and consistent brand signals. Issue
[#1430](https://github.com/getcommunityone/open-navigator/issues/1430) set those up.

## What the site serves

| Piece | Where it comes from |
|---|---|
| `/sitemap.xml` | Sitemap index, built by FastAPI (`api/routes/seo.py`). It points to `/sitemap-app.xml` and the docs' `/docs/sitemap.xml`. |
| `/sitemap-app.xml` | Built per request (cached for an hour) from the public routes in `web_app/src/data/seo/routes.json`, every live data story (curated topics with linked meetings), and each story's state page (`/stories/<slug>?state=XX`) for states with at least 25 linked meetings (`SITEMAP_STATE_MIN_MEETINGS`). A story's `lastmod` is the date of its newest linked meeting; a static page's `lastmod` is the deploy date. Private pages (`/dashboard`, `/profile`, `/settings`, `/admin` and others) and `/api/` are never listed. |
| Page `<title>`, description, canonical, OpenGraph and Twitter tags | Rendered into the first HTML response by `api/seo.py`, so crawlers and link previews see them without running JavaScript. On the Hugging Face Space, nginx sends page requests to `GET /api/spa-shell` (`.huggingface/nginx.conf`) and falls back to the plain shell if the API is down. In the app, `RouteMetaSync` keeps them current as the reader moves between pages. |
| Titles | `"<page> \| CommunityOne"`. Story pages read `"Gun control — Data story \| CommunityOne"`, or `"Gun control in Alabama — Data story \| CommunityOne"` with `?state=AL`. Story titles and ledes come from `web_app/src/data/seo/story-copy.json`, the same copy the stories use. |
| Structured data | `web_app/index.html`: Organization (name **CommunityOne**, logo `communityone_logo_512.png`, `sameAs` to the official profiles), WebSite with SearchAction, WebApplication (Open Navigator, created by CommunityOne), and an ItemList of the main public sections. Story pages also get a BreadcrumbList (Home › Data stories › topic › state). `tests/test_seo.py` checks every block. |
| Crawlable navigation | The header's Data Stories, Search and How It Works links and the home page's topic chips are real `<a href>` links (to `/stories`, `/search` and `/stories/<slug>`). A plain click still scrolls or switches in place. |

To add a page to the sitemap, add it to `routes.json` with `"sitemap": true`, a distinct title and a description.
Detail pages keyed by warehouse ids (decisions, meetings) are left out until their ids are confirmed stable across
rebuilds.

## Owner checklist (needs the owner's Google account)

These steps need Google Search Console access for communityone.com, so an agent can't do them.

1. **Submit the sitemap.** In [Search Console](https://search.google.com/search-console), open the communityone.com
   property, go to **Indexing → Sitemaps**, enter `sitemap.xml` and press **Submit**. Come back a day later: the status
   should read **Success**, with a count of discovered pages for `sitemap-app.xml`. Remove any old entry for a sitemap
   that no longer exists.
2. **Test a live URL.** Use **URL Inspection** on `https://www.communityone.com/` and press **Test Live URL**. Then do the
   same for a story, such as `https://www.communityone.com/stories/guns`. Check that the page is reported as available
   to Google, that the rendered HTML shows the story's own title, and that the canonical Google picked is the URL you
   entered. Press **Request indexing** for each.
3. **Run the Rich Results Test.** Open the [Rich Results Test](https://search.google.com/test/rich-results) with the home
   page (expect Organization and Sitelinks search box / WebSite) and a story page (expect Breadcrumbs). Fix anything it
   lists under errors; warnings for optional fields can wait.
4. **Check what Google has indexed.** Search `site:communityone.com`. The story pages and the main sections should show
   up with their own titles, not all with the home page's. It can take a few weeks after the sitemap is processed.
5. **Brand-name signals.** Sitelinks usually appear only when the site ranks first for its own name. Another brand
   currently holds the top result for "CommunityOne", so the name signals matter:
   - keep the Organization name exactly **CommunityOne** everywhere (site, docs, social profiles);
   - keep the same logo on the site and on the social profiles;
   - link each official profile (LinkedIn, Facebook, Instagram, X, YouTube, GitHub) back to
     `https://www.communityone.com`, and add any new official profile to `sameAs` in `routes.json` and `index.html`;
   - if a Google Business Profile or Wikidata entry exists for the nonprofit, make sure it uses the same name, URL and
     logo.

## Checking it locally

```bash
curl -s http://localhost:8001/sitemap-app.xml | head
curl -s -H 'X-Original-URI: /stories/guns' http://localhost:8001/api/spa-shell | grep -E '<title>|canonical'
```

The second command needs a built frontend (`api/static/index.html`, from `npm run build` in `web_app/`).
