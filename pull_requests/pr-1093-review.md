---
pr: 1093
branch: fix/1081-scrape-429-backoff
title: "fix(scrapers): back off on 429 instead of retrying outside the VPN"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: fb235863b298cdb8262b5541218a8cf965f504bf
verdict: approve
---

# PR Review: fix(scrapers): back off on 429 instead of retrying outside the VPN

## Summary

Automated review (#648) for PR #1093 on `fix/1081-scrape-429-backoff`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `packages/scrapers/src/scrapers/discovery/scrape_http.py`
- `packages/scrapers/tests/test_scrape_http_rate_limit.py`
- `web_docs/docs/development/scrape-vpn-direct-egress.md`

## CI Status

See the PR checks on `fb235863b298`.

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
