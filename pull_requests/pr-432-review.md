---
pr: 432
branch: fix/421-homepage-channel-discovery
title: "fix(discovery): scan each city's homepage for its channel, and never make a search hit its channel"
author: jcbowyer
reviewed_at: 2026-11-16
reviewer: coordinator (Claude Code session; no reviewer subagent, as the rubric allows)
verdict: approve-with-nits
---

# PR Review: fix(discovery): scan each city's homepage for its channel, and never make a search hit its channel

## Summary
The PR makes four changes. First, it fixes a race: `ComprehensiveDiscoveryPipeline._discovery_context` becomes a
`ContextVar`-backed property, so concurrent discoveries stop overwriting each other's jurisdiction and the homepage
scan steps run. Second, a search hit now needs a backlink to the jurisdiction's site before it can become the primary
channel, while a homepage link always qualifies. Third, it adds `python -m scrapers.youtube.rescan_homepage_channels`,
which rescans saved homepages (or every known website), writes the links to the scraped bronze tables, and is a dry
run by default. Fourth, the direct-egress retry binds to the home interface when a full-tunnel VPN is up. The code is
sound and well tested; the race test fails on the old code. The only change made in review is a stale-docstring fix
(f6404746). The verdict is approve-with-nits.

## Scope of Change
- Files changed: 8 (+965 / -5, including the review fix)
- Areas touched: packages (scrapers), tests
- Commits:
  - 4413c0c3 fix(discovery): scan each city's homepage, and never make a search hit its channel
  - b17b495f feat(youtube): rescan saved city homepages for the channels they link to
  - 49fe0736 feat(scrapers): retry blocked sites outside a full-tunnel VPN
  - 4a42dac2 fix(youtube): let a homepage link replace a search-picked primary channel
  - 8e5866bb fix(youtube): save the homepage rescan every 200 cities
  - 9f5ef19d feat(youtube): rescan counties, school districts and every city with a known website
  - f6404746 docs(youtube): say which primary channels the homepage rescan may replace (review fix)
- Range reviewed: `fb865cc2..f6404746`

## CI Status
CI ran on 9f5ef19d, before the review commit. The review commit changes only a docstring.

| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | pass |
| API Types (OpenAPI -> TypeScript) | pass |
| PR conventions (linked issue) | pass |
| Docker Build Test | skipped |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean. `_database_url()` falls back to `postgres:${POSTGRES_PASSWORD or 'password'}@localhost:5433`,
  which is the local-default pattern already used in about 40 places under `packages/`. It is not a real credential.
- Fabricated data in a served path: clean (no `api/` or `web_app/src/` changes).
- Personal data: clean. The scans read public government websites only.
- Destructive or bulky data changes: clean. The rescan `UPDATE`s scraped bronze rows: it merges links into `payload`
  and replaces a primary channel only when that channel was blank, guessed or a search hit. It deletes nothing, writes
  only with `--apply`, and is Python ingestion into bronze, which `CLAUDE.md` allows.

## Strengths
- The `ContextVar` fix keeps the legacy subclass (`scripts/discovery/jurisdiction_discovery_pipeline.py`) working
  unchanged: its plain attribute assignments go through the property setter. The test reproduces the race with 12
  concurrent cities.
- I checked every column the rescan SQL uses against the warehouse (`usps`, `homepage_url`, `homepage_final_url`,
  `payload`, and the channel columns on the municipality and county tables; `int_jurisdiction_websites.website_url`
  and `domain_name`). All exist, and the school district table rightly has no channel columns.
- The interface binding happens before `connect()`, which is correct; httpx's `socket_options` are applied too late
  for this. It is off without a tunnel and can be turned off with `SCRAPE_DIRECT_INTERFACE=off`.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- **Fixed in f6404746.** `packages/scrapers/src/scrapers/youtube/rescan_homepage_channels.py:1-16`: the module
  docstring said only a blank or pattern-guess primary is replaced and that "a channel chosen any other way is never
  replaced". Since 4a42dac2, `REPLACEABLE_METHODS` also covers `domain_search` and `youtube_api`. The docstring now
  matches the code.
- `packages/scrapers/src/scrapers/discovery/scrape_http.py:311-315`: for a host remembered as direct-first, a direct
  response with status 400 or above is returned as is, without trying the normal route. If such a host later starts
  refusing the home connection, it keeps failing for the rest of the process. Not fixed: it is rare, and falling
  through would retry direct a second time.
- `scrape_http.py` `_InterfaceBoundBackend.connect_tcp`: it imports the private
  `httpcore._backends.anyio.AnyIOStream` and swaps the private `transport._pool._network_backend`, ignores
  `local_address` and `socket_options`, and supports IPv4 only. The tests check how the transport is built but never
  call `connect_tcp`, so an httpcore upgrade would break it only at run time. A loopback test that binds to `lo` would
  cover it.
- The PR description says the Playwright problem is a "follow-up issue" without naming it. It is #443; link it from
  the PR.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Branch `fix/421-...`; `Closes #421`; #421 has all four parts; follow-up #443 exists |
| Conventional Commits | Yes | All scoped, with co-author trailers |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | Yes | New CLI is `python -m scrapers.youtube.rescan_homepage_channels`; nothing new in `scripts/` |
| dbt for transformations | Yes | Ingestion writes to bronze only |
| Naming | Yes | `website_url` is used |
| Keys | N/A | No `public` models |
| Calendar years | N/A | |
| Scope label matches filter | N/A | |
| Match evidence on filtered tiles | N/A | |
| Docs | N/A | |
| Telemetry and logging | Yes | loguru throughout |
| Tests | Yes | Race, primary-channel gate, rescan merge/choose/SQL, interface detection and remembered hosts |
| Shared libraries | Yes | `packages/scrapers` and `packages/ingestion` plus root primary-channel tests |

## Test Coverage
Ran locally with the worktree's packages on `PYTHONPATH`: `pytest packages/scrapers/tests packages/ingestion/tests
tests/test_youtube_primary_channel.py tests/test_pattern_match_gate.py`, 819 passed. `ruff check` on the changed
files reports 19 errors, all in `comprehensive_discovery_pipeline.py`; the file has the same 19 on `main`, so none are
new. The rescan was not re-run against the warehouse in review.

## Verdict
approve-with-nits. Nothing has to change before merge.
