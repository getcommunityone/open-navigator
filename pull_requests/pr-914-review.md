---
pr: 914
branch: fix/913-no-cache-service-worker
title: "fix(hosting): never cache the service worker files on the Space"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 76656979cfb6f3e6d2f2bef225c1cf7c68ecc6c2
verdict: approve
---

# PR Review: fix(hosting): never cache the service worker files on the Space

## Summary

Automated review (#648) for PR #914 on `fix/913-no-cache-service-worker`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `.huggingface/nginx.conf`
- `tests/test_hf_nginx_cache.py`
- `web_docs/docs/deployment/huggingface-spaces.md`

## CI Status

See the PR checks on `76656979cfb6`.

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
