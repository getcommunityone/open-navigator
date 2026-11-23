---
pr: 769
branch: feat/767-scrape-block-pages
title: "feat(scrapers): retry block pages outside the VPN and remember those hosts"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: claude-code
verdict: approve-with-nits
---

# PR Review: feat(scrapers): retry block pages outside the VPN and remember those hosts

## Summary

Closes #767. A 200 that is a firewall page or an empty shell now gets the same one-shot retry outside the VPN as an
error does; hosts that answered only outside the VPN are saved between runs; `SCRAPE_DIRECT_PROXY` is a way out
where binding to the home interface can't work. Reviewed against `.claude/review-rubric.md`, `AGENTS.md` and
`CLAUDE.md`.

## Scope of change

- `packages/scrapers/src/scrapers/discovery/scrape_http.py`: `looks_blocked_or_partial`, `BLOCK_PAGE_MARKERS`, the
  saved-hosts file, `SCRAPE_DIRECT_PROXY`, the block-page retry, and a direct-first attempt that falls back.
- `packages/scrapers/tests/test_scrape_http_block_pages.py` (new, 10 tests), and
  `test_scrape_http_direct_interface.py` (the fixture turns the hosts file off).
- `web_docs/docs/development/scrape-vpn-direct-egress.md` (new).

## Checks

- `pytest` on every test that sends requests through the module (`test_scrape_http_direct_interface.py`,
  `test_scrape_http_block_pages.py`, `test_youtube_vpn_guard.py`, `tests/test_scrape_http.py`,
  `tests/test_youtube_site_search_scrape.py`): 67 passed, with no file left in `data/cache/`.
- Live: coffeecounty.us without a VPN is 200, 104,784 bytes and not flagged. With the VPN on it is untested; that
  needs the owner's machine.

## Findings

### Blocking

None.

### Should fix (fixed in this PR)

- **A saved host could be stuck outside the VPN.** The direct-first attempt returned whatever the direct route gave,
  so once a host was saved, a later 403 from the home connection was final. That was minor while hosts lived in memory;
  saved across runs, it would last. The direct-first attempt now falls through to the normal route on an error status
  or a block page (`test_a_saved_host_that_fails_direct_falls_back_to_the_vpn`).
- **The old test wrote to the real `data/cache/`.** `test_scrape_http_direct_interface.py` didn't isolate the new
  hosts file, so a run left `city.gov` and `other.gov` in `data/cache/scrape_direct_hosts.json`. Its fixture now sets
  the file to `off`.

- **CI caught the detector raising on an httpx-like stand-in.** The site-search tests use a fake response with no
  `.headers`, and `looks_blocked_or_partial` read `response.headers`; the error escaped the fetch and 5 tests in
  `tests/test_youtube_site_search_scrape.py` found no channels. The detector now never raises: a response without a
  content type, or one it can't read, is not judged (`test_a_response_without_headers_*`).
- **`test_youtube_vpn_guard.py` saved `www.tuscaloosa.com` to the real hosts file.** The root `conftest.py` now sets
  `SCRAPE_DIRECT_HOSTS_FILE=off` for every test run, so no test touches `data/cache/`.

### Nits

- The saved list never expires. A host that later works through the VPN stays direct-first. That is harmless while the
  direct route works, and the fallback above covers it when it doesn't.
- A small legitimate page (under 2,048 bytes, or with no `<title>`) costs one extra direct request. Its host is saved
  only when the direct answer is a full page.
- Ruff's `UP`/`BLE` findings in this file are older than this PR; CI doesn't run ruff.

## Rules

- Issue first with four parts (#767); branch `feat/767-scrape-block-pages`; `Closes #767`; Conventional Commits.
- Docs in the same PR. No secrets, no fabricated numbers: the page sizes are from the live fetch above.
- `data/cache/` is never deleted. The docs say to edit the hosts list, not delete it.
- YouTube still never goes out on the home connection (#488); `test_youtube_vpn_guard.py` passes.

## Verdict

**approve-with-nits**: ready to merge when CI is green.
