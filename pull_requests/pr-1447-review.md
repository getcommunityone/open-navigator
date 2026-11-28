---
pr: 1447
branch: feat/1430-seo-sitelinks
title: "feat(seo): real sitemap, per-route head meta and crawlable nav for Sitelinks"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: read-only reviewer subagent and coordinator
verdict: approve-with-nits
---

# PR Review: feat(seo): real sitemap, per-route head meta and crawlable nav for Sitelinks

## Summary
The PR serves `/sitemap.xml` and `/sitemap-app.xml` from FastAPI, built from the real public routes and the live
stories. It renders each page's title, description, canonical, robots, OpenGraph/Twitter tags and story breadcrumbs
into the first HTML response. nginx on the Hugging Face Space routes page requests through FastAPI and falls back to
the static shell. The homepage JSON-LD gets a logo URL that loads (the old `.svg` returns 404 on the live site),
`sameAs` and one brand name. The header nav and the home topic chips become real links.

A read-only reviewer found no blocking issues and six should-fix items. All six are fixed in `00ad49cc`, and each fix
has a test. What remains are optional nits, so the verdict is approve-with-nits.

## Scope of Change
- Areas touched: api, web_app, web_docs, `.huggingface` (nginx), `apps/open-navigator-web/build.sh`
- Commits:
  - `feat(seo): real sitemap, per-route head meta and crawlable nav for Sitelinks`
  - merge of origin/main
  - `fix(seo): noindex thin state pages, shared state names, keep server tags on first load`
- Range reviewed: `origin/main...HEAD`

## CI Status
| Check | Status |
|---|---|
| Required checks | Read on the head commit before merge (see the PR's Checks tab) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The pre-commit secret hooks passed, and nothing new contains a key.
- **Fabricated data:** clean.
  - Story ledes are hand-written copy or a template built from the topic name.
  - `lastmod` is the date of the newest linked meeting, or the deploy date. Unknown dates are left out.
  - When the warehouse is down, only the registry story is listed and no dates are guessed.
  - The JSON-LD is descriptive only.
- **Personal data:** clean. `sameAs` lists only the organization's official profiles.
- **Destructive changes:** the stale `web_app/public/sitemap*.xml` files are deleted and replaced by dynamic routes. No data or tables change.

## Strengths
- The server and client share one copy source: `routes.json`, `story-copy.json` and `states.json`.
- Values written into the page head are escaped, and the breadcrumb JSON-LD escapes `</`. The test runs it with markup in the copy.
- nginx falls back to the static shell on 404/5xx from FastAPI. This was checked against nginx 1.26 in Docker with the API stopped.
- A spoofed `X-Original-URI` only changes that client's own uncached response.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
All six are fixed in `00ad49cc`:
1. **Any two-letter `?state=` was indexable**, with a self-canonical and the raw code in the title.
   - Fix: a code not in `states.json` is now ignored.
   - Fix: a state with no meetings for the story is `noindex, follow`, with the story URL as canonical.
   - Tests: `test_state_without_meetings_is_noindex_with_the_story_as_canonical` (pytest) and the matching vitest case.
2. **Server and client named states differently** ("GA" vs "Georgia").
   - Fix: both now read one `web_app/src/data/seo/states.json`.
   - Tests: `test_state_names_come_from_the_shared_map` (pytest) and `stateName` in vitest.
3. **The client downgraded the server's tags after load.**
   - Fix: `short-term-rentals`, `license-plate-readers` and `pickleball` now have titles in `story-copy.json`. The titles equal the catalog names, so nothing visible changes.
   - Fix: on first load, `RouteMetaSync` keeps the head the server rendered for that page (`<meta name="seo-rendered">`) and only rewrites it on later navigation.
   - Tests: vitest `serverRenderedFor`, plus the title cases.
4. **The retry pause only worked before anything had loaded.**
   - Fix: the pause now applies whenever the warehouse is down, and the last good story list keeps being served.
   - Test: `test_outage_serves_the_stale_list_and_backs_off`.
5. **`/browse-topics/all` had two titles.** It is now "Browse all topics", matching the page.
6. **Unknown paths were marked indexable.**
   - Fix: they are now `noindex, follow`. Real detail routes (`indexablePrefixes`) stay indexable.
   - Fix: paths are percent-decoded before the private check, so `/admi%6e` is `noindex`.

### 🔵 Nits / suggestions (Minor)
- On the Hugging Face Space, `/` is served as static `index.html`. The static file carries the home tags, so this is harmless.
- From the server, `/stories?state=AL` and `/search?q=` get the plain page title. The client then sets a more specific one.
- The topic chips are now links with `role="tab"`. Enter selects; Space no longer activates them. Arrow keys and roving focus are unchanged.
- If the warehouse is down when the sitemap is built, a shortened sitemap is cached for an hour.
- Decision and meeting detail pages are left out of the sitemap until their ids are confirmed stable across rebuilds.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1430 has all four parts; branch `feat/1430-seo-sitelinks`; `Closes #1430` |
| Conventional Commits | Yes | Co-author trailer present |
| No fabricated data | Yes | See scans |
| New Python in `packages/` | N/A | API code under `api/`; nothing added to `scripts/` |
| dbt for transformations | Yes | Python only reads served views (`civicsearch_topic`, `browse_transcript_count`, `topic_transcript_link`) |
| Scope label matches filter | Yes | A state named in the title is the applied `?state=` filter; codes that aren't states are ignored |
| Docs | Yes | `web_docs/docs/operations/seo-sitelinks.md` (kebab-case, frontmatter, in the sidebar) |
| Telemetry and logging | Yes | OpenTelemetry spans on the SEO routes; loguru in `api/seo.py` |
| Tests | Yes | See below |

## Test Coverage
Run locally:
- `pytest tests/test_seo.py`: 19 passed. Covers sitemaps, per-route head tags, noindex rules, escaping, JSON-LD, the warehouse outage, and the state rules.
- `vitest run`: 115 files, 1027 tests passed.
- `tsc --noEmit`: clean.
- `vite build` and `docusaurus build`: pass.

Not covered by an automated test: the nginx routing. It was checked by hand in Docker.

## Verdict
**approve-with-nits.** All six should-fix items are addressed. The remaining nits are optional. Merge once the
required CI checks are green.
