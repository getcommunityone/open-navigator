---
pr: 769
branch: feat/767-scrape-block-pages
title: "feat(scrapers): retry block pages outside the VPN and remember those hosts"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: github-actions
head_sha: 70c7a570904483c9711000f7977023b446deac68
verdict: approve
---

# PR Review: feat(scrapers): retry block pages outside the VPN and remember those hosts

## Summary

Automated review (#648) for PR #769 on `feat/767-scrape-block-pages`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/scrapers/src/scrapers/discovery/scrape_http.py`
- `packages/scrapers/tests/test_scrape_http_block_pages.py`
- `packages/scrapers/tests/test_scrape_http_direct_interface.py`
- `web_docs/docs/development/scrape-vpn-direct-egress.md`

## CI Status

See the PR checks on `70c7a5709044`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**
